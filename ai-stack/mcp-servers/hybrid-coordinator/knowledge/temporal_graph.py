"""
temporal_graph.py — Temporal Knowledge Graph (Phase 69.3)

Stores (subject, predicate, object, valid_from, valid_to) fact tuples in
Postgres.  When a new fact conflicts with an existing one on the same
(subject, predicate) key, the old fact's valid_to is set to now()
("supersession"), preserving the full provenance chain.

query_at(timestamp) returns all facts that were valid at that point in time,
enabling time-travel queries over the knowledge state.

Schema:
    fact_chain(
        id          BIGSERIAL PRIMARY KEY,
        subject     TEXT NOT NULL,
        predicate   TEXT NOT NULL,
        object      TEXT NOT NULL,
        valid_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
        valid_to    TIMESTAMPTZ,           -- NULL = currently active
        source      TEXT,                  -- free-form provenance tag
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )

HTTP endpoint (wired in router.py):
    GET /knowledge/graph/fact-chain?subject=<s>&predicate=<p>&at=<iso8601>
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("temporal-graph")

_DDL_FACT_CHAIN = """
CREATE TABLE IF NOT EXISTS fact_chain (
    id          BIGSERIAL PRIMARY KEY,
    subject     TEXT NOT NULL,
    predicate   TEXT NOT NULL,
    object      TEXT NOT NULL,
    valid_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to    TIMESTAMPTZ,
    source      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fact_chain_subject
    ON fact_chain (subject, predicate);
CREATE INDEX IF NOT EXISTS idx_fact_chain_valid
    ON fact_chain (valid_from, valid_to);
"""


class TemporalGraph:
    """
    Append-only temporal knowledge graph backed by Postgres.

    One instance is shared across the coordinator process.
    All methods are async and safe for concurrent use.
    """

    def __init__(self, postgres_client: Any) -> None:
        self._pg = postgres_client
        self._schema_ready = False

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def ensure_schema(self) -> None:
        """Idempotent DDL bootstrap."""
        if self._schema_ready:
            return
        try:
            await self._pg.execute(_DDL_FACT_CHAIN)
            self._schema_ready = True
            logger.info("temporal_graph: schema ready")
        except Exception as exc:
            logger.warning("temporal_graph: schema setup failed: %s", exc)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def add_fact(
        self,
        subject: str,
        predicate: str,
        object_: str,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert a new fact and supersede any currently-active conflicting fact
        on the same (subject, predicate) key by setting its valid_to = now().

        Returns a dict describing the inserted fact and whether supersession
        occurred.
        """
        if not self._schema_ready:
            await self.ensure_schema()

        superseded_id: Optional[int] = None
        try:
            # Find the currently-active fact for this (subject, predicate)
            rows = await self._pg.fetch_all(
                """
                SELECT id FROM fact_chain
                WHERE subject = %s AND predicate = %s AND valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT 1
                """,
                subject, predicate,
            )
            if rows:
                old_id = rows[0]["id"]
                await self._pg.execute(
                    "UPDATE fact_chain SET valid_to = now() WHERE id = %s",
                    old_id,
                )
                superseded_id = old_id
                logger.debug(
                    "temporal_graph.add_fact: superseded id=%d (%s, %s)",
                    old_id, subject, predicate,
                )

            # Insert the new fact
            insert_rows = await self._pg.fetch_all(
                """
                INSERT INTO fact_chain (subject, predicate, object, source)
                VALUES (%s, %s, %s, %s)
                RETURNING id, valid_from
                """,
                subject, predicate, object_, source,
            )
            new_id = insert_rows[0]["id"] if insert_rows else None
            valid_from = insert_rows[0]["valid_from"].isoformat() if insert_rows else None

        except Exception as exc:
            logger.warning("temporal_graph.add_fact failed: %s", exc)
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "id": new_id,
            "subject": subject,
            "predicate": predicate,
            "object": object_,
            "valid_from": valid_from,
            "superseded_id": superseded_id,
        }

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def query_at(
        self,
        at: Optional[datetime] = None,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return facts that were valid at the given timestamp (default: now).

        A fact is valid at time T when:
            valid_from <= T  AND  (valid_to IS NULL OR valid_to > T)

        Optionally filter by subject and/or predicate.
        """
        if not self._schema_ready:
            await self.ensure_schema()

        if at is None:
            at = datetime.now(timezone.utc)

        filters = ["valid_from <= %s", "(valid_to IS NULL OR valid_to > %s)"]
        params: list = [at, at]

        if subject:
            filters.append("subject = %s")
            params.append(subject)
        if predicate:
            filters.append("predicate = %s")
            params.append(predicate)

        params.append(limit)
        where = " AND ".join(filters)

        try:
            rows = await self._pg.fetch_all(
                f"""
                SELECT id, subject, predicate, object, valid_from, valid_to, source
                FROM fact_chain
                WHERE {where}
                ORDER BY valid_from DESC
                LIMIT %s
                """,
                *params,
            )
            return [_row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.warning("temporal_graph.query_at failed: %s", exc)
            return []

    async def get_fact_chain(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Return the full provenance chain for (subject, predicate) — both active
        and superseded facts, ordered by valid_from descending.
        """
        if not self._schema_ready:
            await self.ensure_schema()

        filters: list[str] = []
        params: list = []

        if subject:
            filters.append("subject = %s")
            params.append(subject)
        if predicate:
            filters.append("predicate = %s")
            params.append(predicate)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)

        try:
            rows = await self._pg.fetch_all(
                f"""
                SELECT id, subject, predicate, object, valid_from, valid_to, source
                FROM fact_chain
                {where}
                ORDER BY valid_from DESC
                LIMIT %s
                """,
                *params,
            )
            return [_row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.warning("temporal_graph.get_fact_chain failed: %s", exc)
            return []

    async def active_facts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all currently-active facts (valid_to IS NULL)."""
        if not self._schema_ready:
            await self.ensure_schema()
        try:
            rows = await self._pg.fetch_all(
                """
                SELECT id, subject, predicate, object, valid_from, valid_to, source
                FROM fact_chain
                WHERE valid_to IS NULL
                ORDER BY valid_from DESC
                LIMIT %s
                """,
                limit,
            )
            return [_row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.warning("temporal_graph.active_facts failed: %s", exc)
            return []


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# aiohttp HTTP handler + route registration
# ------------------------------------------------------------------

def register_routes(app: Any) -> None:
    """Register temporal graph HTTP endpoints on the aiohttp Application."""
    from aiohttp import web as _web

    async def _get_fact_chain(request: _web.Request) -> _web.Response:
        """GET /knowledge/graph/fact-chain — query fact provenance chain.

        Query params:
          subject   — filter by subject (optional)
          predicate — filter by predicate (optional)
          at        — ISO-8601 timestamp for time-travel query (optional; default=now)
          mode      — "chain" (default, full provenance) | "active" (current only)
          limit     — max rows (default 100)
        """
        tg: TemporalGraph = request.app.get("temporal_graph")
        if tg is None:
            return _web.json_response({"error": "TemporalGraph not initialised"}, status=503)

        subject = request.rel_url.query.get("subject") or None
        predicate = request.rel_url.query.get("predicate") or None
        mode = request.rel_url.query.get("mode", "chain")
        limit = min(int(request.rel_url.query.get("limit", "100")), 500)
        at_str = request.rel_url.query.get("at")

        try:
            if mode == "active":
                facts = await tg.active_facts(limit=limit)
            elif at_str:
                at_dt = datetime.fromisoformat(at_str.replace("Z", "+00:00"))
                facts = await tg.query_at(at=at_dt, subject=subject, predicate=predicate, limit=limit)
            else:
                facts = await tg.get_fact_chain(subject=subject, predicate=predicate, limit=limit)
        except Exception as exc:
            return _web.json_response({"error": str(exc)}, status=500)

        active = sum(1 for f in facts if f.get("status") == "active")
        return _web.json_response({
            "facts": facts,
            "total": len(facts),
            "active": active,
            "superseded": len(facts) - active,
        })

    async def _post_fact(request: _web.Request) -> _web.Response:
        """POST /knowledge/graph/fact-chain — insert a new fact."""
        tg: TemporalGraph = request.app.get("temporal_graph")
        if tg is None:
            return _web.json_response({"error": "TemporalGraph not initialised"}, status=503)
        try:
            body = await request.json()
        except Exception:
            return _web.json_response({"error": "invalid JSON"}, status=400)

        subject = body.get("subject", "").strip()
        predicate = body.get("predicate", "").strip()
        object_ = body.get("object", "").strip()
        source = body.get("source")

        if not (subject and predicate and object_):
            return _web.json_response({"error": "subject, predicate, object are required"}, status=400)

        result = await tg.add_fact(subject, predicate, object_, source=source)
        status = 200 if result.get("ok") else 500
        return _web.json_response(result, status=status)

    app.router.add_get("/knowledge/graph/fact-chain", _get_fact_chain)
    app.router.add_post("/knowledge/graph/fact-chain", _post_fact)
    logger.info("temporal_graph: routes registered (/knowledge/graph/fact-chain)")


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a DB row (dict-like) to a serialisable dict."""
    valid_from = row.get("valid_from") if hasattr(row, "get") else getattr(row, "valid_from", None)
    valid_to = row.get("valid_to") if hasattr(row, "get") else getattr(row, "valid_to", None)
    return {
        "id": row["id"] if hasattr(row, "__getitem__") else getattr(row, "id", None),
        "subject": row["subject"] if hasattr(row, "__getitem__") else getattr(row, "subject", ""),
        "predicate": row["predicate"] if hasattr(row, "__getitem__") else getattr(row, "predicate", ""),
        "object": row["object"] if hasattr(row, "__getitem__") else getattr(row, "object", ""),
        "valid_from": valid_from.isoformat() if hasattr(valid_from, "isoformat") else str(valid_from or ""),
        "valid_to": valid_to.isoformat() if hasattr(valid_to, "isoformat") else (None if valid_to is None else str(valid_to)),
        "source": row["source"] if hasattr(row, "__getitem__") else getattr(row, "source", None),
        "status": "active" if valid_to is None else "superseded",
    }
