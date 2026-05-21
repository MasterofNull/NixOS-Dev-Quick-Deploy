"""
memory_superseder.py — Unified Phase 55 temporal supersession service.

This module is the single source of truth for both:
- broker-facing lineage helpers used during memory writes, and
- HTTP-facing supersession ledger/history endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

DDL_MEMORY_SUPERSESSIONS = """
CREATE TABLE IF NOT EXISTS memory_supersessions (
    supersession_id TEXT PRIMARY KEY,
    fact_id         TEXT NOT NULL,
    replacement     TEXT NOT NULL,
    reason          TEXT NOT NULL,
    old_valid_until TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_memory_supersessions_fact_id
    ON memory_supersessions (fact_id);
CREATE INDEX IF NOT EXISTS idx_memory_supersessions_created_at
    ON memory_supersessions (created_at DESC);
"""


@dataclass
class SupersessionEvent:
    supersession_id: str
    fact_id: str
    replacement: str
    reason: str
    old_valid_until: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "supersession_id": self.supersession_id,
            "fact_id": self.fact_id,
            "replacement": self.replacement,
            "reason": self.reason,
            "old_valid_until": self.old_valid_until,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class MemorySuperseder:
    """Unified supersession service for lineage decisions and ledger writes."""

    def __init__(self, postgres_client: Optional[Any] = None) -> None:
        self._pg = postgres_client
        self._schema_ready = False
        self._events: List[SupersessionEvent] = []
        # Phase 60.2: in-process superseded-ID cache for O(1) read-time filtering.
        # Populated by supersede(); consulted by is_superseded().
        self._superseded_ids: Dict[str, datetime] = {}

    async def ensure_schema(self) -> None:
        if self._schema_ready or self._pg is None:
            return
        await self._pg.execute(DDL_MEMORY_SUPERSESSIONS)
        self._schema_ready = True
        logger.info("memory_superseder: PostgreSQL schema verified")

    def resolve_lineage(self, new_fact: str, existing_facts: List[Dict[str, Any]]) -> Optional[str]:
        if not existing_facts:
            return None
        sorted_existing = sorted(existing_facts, key=lambda x: x.get("score", 0.0), reverse=True)
        top_fact = sorted_existing[0]
        return top_fact.get("memory_id") or top_fact.get("id")

    def prepare_superseded_metadata(self, predecessor_id: str) -> Dict[str, Any]:
        return {
            "supersedes": predecessor_id,
            "version_update": True,
            "logical_clock": datetime.now(timezone.utc).timestamp(),
        }

    async def supersede(
        self,
        *,
        fact_id: str,
        replacement: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        fact_id = str(fact_id or "").strip()
        replacement = str(replacement or "").strip()
        reason = str(reason or "").strip()
        if not fact_id:
            raise ValueError("fact_id required")
        if not replacement:
            raise ValueError("replacement required")
        if not reason:
            raise ValueError("reason required")

        now = datetime.now(tz=timezone.utc).isoformat()
        event = SupersessionEvent(
            supersession_id=str(uuid4()),
            fact_id=fact_id,
            replacement=replacement,
            reason=reason,
            old_valid_until=now,
            created_at=now,
            metadata=metadata or {},
        )

        await self.ensure_schema()
        if self._pg is not None:
            await self._pg.execute(
                """
                INSERT INTO memory_supersessions
                    (supersession_id, fact_id, replacement, reason, old_valid_until, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                event.supersession_id,
                event.fact_id,
                event.replacement,
                event.reason,
                event.old_valid_until,
                event.created_at,
            )

        self._events.append(event)
        self._events = self._events[-200:]
        # Phase 60.2: stamp into cache so read-time filter can exclude this ID
        # without needing a Qdrant payload mutation.
        self._superseded_ids[fact_id] = datetime.fromisoformat(event.created_at)
        return {
            "superseded": True,
            "fact_id": event.fact_id,
            "old_valid_until": event.old_valid_until,
            "supersession_id": event.supersession_id,
            "ledger": "postgres" if self._pg is not None else "memory",
        }

    def is_superseded(self, fact_id: str, *, valid_at: Optional[datetime] = None) -> bool:
        """Return True if fact_id is superseded at `valid_at` or now.

        Historical bitemporal reads must still be able to see a fact that was
        superseded after the requested valid_at point.
        """
        superseded_at = self._superseded_ids.get(fact_id)
        if superseded_at is None:
            return False
        if valid_at is None:
            return True
        if valid_at.tzinfo is None:
            valid_at = valid_at.replace(tzinfo=timezone.utc)
        return valid_at >= superseded_at

    async def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 20), 100))
        if self._pg is not None:
            await self.ensure_schema()
            try:
                rows = await self._pg.fetch_all(
                    """
                    SELECT supersession_id, fact_id, replacement, reason,
                           old_valid_until::text AS old_valid_until,
                           created_at::text AS created_at
                    FROM memory_supersessions
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    limit,
                )
                return [dict(row) for row in rows]
            except Exception as exc:
                logger.warning("memory_supersession_history_pg_failed error=%s", exc)
        return [event.to_dict() for event in reversed(self._events[-limit:])]


_superseder = MemorySuperseder()


def init(postgres_client: Optional[Any] = None) -> None:
    global _superseder
    _superseder = MemorySuperseder(postgres_client=postgres_client)
    logger.info("memory_superseder: initialized (Phase 55.1 Active)")


def get_superseder() -> MemorySuperseder:
    return _superseder


async def handle_memory_supersede(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = await _superseder.supersede(
            fact_id=data.get("fact_id"),
            replacement=data.get("replacement") or data.get("replacement_text"),
            reason=data.get("reason"),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )
        return web.json_response(result)
    except ValueError as exc:
        return web.json_response({"error": "memory_supersede_invalid", "detail": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("memory_supersede_failed")
        return web.json_response({"error": "memory_supersede_failed", "detail": str(exc)}, status=500)


async def handle_memory_supersede_history(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", "20"))
        return web.json_response({"events": await _superseder.history(limit=limit)})
    except Exception as exc:
        return web.json_response({"error": "memory_supersede_history_failed", "detail": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/memory/supersede", handle_memory_supersede)
    http_app.router.add_get("/memory/supersede/history", handle_memory_supersede_history)
