"""
memory_crystallizer.py - idempotent session distillation pipeline.

Phase 55.2 turns raw session transcripts into bounded episodic insights while
recording processed session hashes so repeated runs are no-ops.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

DDL_CRYSTALLIZED_SESSIONS = """
CREATE TABLE IF NOT EXISTS crystallized_sessions (
    session_hash      TEXT PRIMARY KEY,
    session_path      TEXT NOT NULL,
    insights_stored   INTEGER NOT NULL DEFAULT 0,
    processed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crystallized_sessions_processed_at
    ON crystallized_sessions (processed_at DESC);
"""


class MemoryCrystallizer:
    def __init__(
        self,
        postgres_client: Optional[Any] = None,
        *,
        store_insight_fn: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
    ) -> None:
        self._pg = postgres_client
        self._store_insight = store_insight_fn
        self._schema_ready = False
        self._processed: Dict[str, Dict[str, Any]] = {}
        self._last_run: Optional[str] = None
        self._insights_stored = 0

    async def ensure_schema(self) -> None:
        if self._schema_ready or self._pg is None:
            return
        await self._pg.execute(DDL_CRYSTALLIZED_SESSIONS)
        self._schema_ready = True

    async def crystallize_session(self, session_path: str) -> Dict[str, Any]:
        path = Path(session_path).expanduser()
        if not path.is_file():
            raise ValueError("session_path must point to an existing file")

        raw = path.read_bytes()
        session_hash = hashlib.sha256(raw).hexdigest()
        await self.ensure_schema()
        if await self._already_processed(session_hash):
            return {"status": "already_processed", "session_hash": session_hash, "insights_stored": 0}

        insight = _distill_session_payload(raw)
        if self._store_insight is not None:
            await self._store_insight(insight)

        now = datetime.now(timezone.utc).isoformat()
        if self._pg is not None:
            await self._pg.execute(
                """
                INSERT INTO crystallized_sessions
                    (session_hash, session_path, insights_stored, processed_at)
                VALUES (%s, %s, %s, %s)
                """,
                session_hash,
                str(path),
                1,
                now,
            )
        self._processed[session_hash] = {
            "session_hash": session_hash,
            "session_path": str(path),
            "insights_stored": 1,
            "processed_at": now,
        }
        self._last_run = now
        self._insights_stored += 1
        return {"status": "crystallized", "session_hash": session_hash, "insights_stored": 1}

    async def status(self) -> Dict[str, Any]:
        sessions_processed = len(self._processed)
        if self._pg is not None:
            await self.ensure_schema()
            try:
                rows = await self._pg.fetch_all(
                    """
                    SELECT count(*)::int AS sessions_processed,
                           coalesce(sum(insights_stored), 0)::int AS insights_stored,
                           max(processed_at)::text AS last_run
                    FROM crystallized_sessions
                    """
                )
                if rows:
                    row = dict(rows[0])
                    return {
                        "sessions_processed": row["sessions_processed"],
                        "insights_stored": row["insights_stored"],
                        "last_run": row["last_run"],
                    }
            except Exception as exc:
                logger.warning("memory_crystalline_status_pg_failed error=%s", exc)
        return {
            "sessions_processed": sessions_processed,
            "insights_stored": self._insights_stored,
            "last_run": self._last_run,
        }

    async def _already_processed(self, session_hash: str) -> bool:
        if session_hash in self._processed:
            return True
        if self._pg is None:
            return False
        rows = await self._pg.fetch_all(
            "SELECT session_hash FROM crystallized_sessions WHERE session_hash = %s LIMIT 1",
            session_hash,
        )
        return bool(rows)


def _distill_session_payload(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        payload = raw.decode("utf-8", errors="replace")
    text = json.dumps(payload, sort_keys=True) if isinstance(payload, (dict, list)) else str(payload)
    compact = " ".join(text.split())
    return compact[:4000]


_crystallizer = MemoryCrystallizer()


def init(
    postgres_client: Optional[Any] = None,
    *,
    store_insight_fn: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
) -> None:
    global _crystallizer
    _crystallizer = MemoryCrystallizer(
        postgres_client=postgres_client,
        store_insight_fn=store_insight_fn,
    )


def get_crystallizer() -> MemoryCrystallizer:
    return _crystallizer


async def handle_memory_crystalline_status(_request: web.Request) -> web.Response:
    return web.json_response(await _crystallizer.status())


async def handle_memory_crystalline_run(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        session_path = str(data.get("session_path") or "").strip()
        if not session_path:
            raise ValueError("session_path required")
        asyncio.create_task(_crystallizer.crystallize_session(session_path))
        return web.json_response({"accepted": True, "session_path": session_path}, status=202)
    except ValueError as exc:
        return web.json_response({"error": "memory_crystalline_invalid", "detail": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("memory_crystalline_run_failed")
        return web.json_response({"error": "memory_crystalline_run_failed", "detail": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/memory/crystalline/status", handle_memory_crystalline_status)
    http_app.router.add_post("/memory/crystalline/run", handle_memory_crystalline_run)
