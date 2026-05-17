"""
trace_collector.py — End-to-end query trace (Phase 54.5)

Records a full span for every /query call:
    intent → profile → retrieval → LLM → memory_write → total_latency

Writes to PostgreSQL query_traces table. Surfaced via GET /api/traces
and the dashboard Intelligence lane.

Schema:
    query_traces(
        trace_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        query_text      TEXT,
        intent          TEXT,
        profile         TEXT,
        retrieval_hits  INTEGER DEFAULT 0,
        retrieval_ms    INTEGER DEFAULT 0,
        rag_skipped     BOOLEAN DEFAULT FALSE,
        llm_model       TEXT,
        tokens_in       INTEGER DEFAULT 0,
        tokens_out      INTEGER DEFAULT 0,
        llm_ms          INTEGER DEFAULT 0,
        total_ms        INTEGER DEFAULT 0,
        trace_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )

Usage:
    async with TraceCollector(pg_client) as tc:
        tc.set_intent("knowledge_lookup")
        tc.set_profile("local-tool-calling")
        tc.set_retrieval(hits=5, latency_ms=42, skipped=False)
        tc.set_llm("qwen3", tokens_in=1200, tokens_out=300, latency_ms=9800)
        # on __aexit__ → writes row to DB

    # Standalone (no postgres):
    tc = TraceCollector(None)
    tc.set_intent("code_generation")
    result = tc.to_dict()
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("hybrid-coordinator")

_DDL_TRACES = """
CREATE TABLE IF NOT EXISTS query_traces (
    trace_id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    query_text      TEXT,
    intent          TEXT,
    profile         TEXT,
    retrieval_hits  INTEGER DEFAULT 0,
    retrieval_ms    INTEGER DEFAULT 0,
    rag_skipped     BOOLEAN DEFAULT FALSE,
    llm_model       TEXT,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    llm_ms          INTEGER DEFAULT 0,
    total_ms        INTEGER DEFAULT 0,
    trace_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_query_traces_intent   ON query_traces (intent);
CREATE INDEX IF NOT EXISTS idx_query_traces_trace_at ON query_traces (trace_at DESC);
"""

# Module-level pg reference — injected via init()
_pg: Optional[Any] = None
_schema_ready: bool = False


def init(postgres_client: Any) -> None:
    """Inject postgres client. Call once from server.py startup."""
    global _pg
    _pg = postgres_client
    logger.info("trace_collector: initialized with postgres client")


async def ensure_schema(postgres_client: Optional[Any] = None) -> None:
    """Idempotently create query_traces table."""
    global _schema_ready
    if _schema_ready:
        return
    pg = postgres_client or _pg
    if pg is None:
        return
    try:
        await pg.execute(_DDL_TRACES)
        _schema_ready = True
        logger.info("trace_collector: schema ready")
    except Exception as exc:
        logger.warning("trace_collector: schema setup failed: %s", exc)


class TraceCollector:
    """
    Context manager that accumulates span data for one /query call and
    commits a row to query_traces on exit.
    """

    def __init__(self, postgres_client: Optional[Any] = None, query: str = "") -> None:
        self._pg = postgres_client or _pg
        self.trace_id = str(uuid.uuid4())
        self.query_text = query[:500] if query else ""
        self.intent: str = "unknown"
        self.profile: str = "unknown"
        self.retrieval_hits: int = 0
        self.retrieval_ms: int = 0
        self.rag_skipped: bool = True
        self.llm_model: str = ""
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        self.llm_ms: int = 0
        self._start: float = time.perf_counter()

    async def __aenter__(self) -> "TraceCollector":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        total_ms = int((time.perf_counter() - self._start) * 1000)
        await self._commit(total_ms)
        if total_ms > 30_000:
            logger.warning(
                "trace_collector: SLOW QUERY trace_id=%s total_ms=%d intent=%s",
                self.trace_id, total_ms, self.intent,
            )

    # ------------------------------------------------------------------
    # Setters (call within the context block)
    # ------------------------------------------------------------------

    def set_intent(self, intent: str) -> None:
        self.intent = intent

    def set_profile(self, profile: str) -> None:
        self.profile = profile

    def set_retrieval(self, hits: int, latency_ms: int, skipped: bool = False) -> None:
        self.retrieval_hits = hits
        self.retrieval_ms = latency_ms
        self.rag_skipped = skipped

    def set_llm(self, model: str, tokens_in: int = 0, tokens_out: int = 0, latency_ms: int = 0) -> None:
        self.llm_model = model
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.llm_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        total_ms = int((time.perf_counter() - self._start) * 1000)
        return {
            "trace_id": self.trace_id,
            "query_text": self.query_text,
            "intent": self.intent,
            "profile": self.profile,
            "retrieval_hits": self.retrieval_hits,
            "retrieval_ms": self.retrieval_ms,
            "rag_skipped": self.rag_skipped,
            "llm_model": self.llm_model,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "llm_ms": self.llm_ms,
            "total_ms": total_ms,
            "trace_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal commit
    # ------------------------------------------------------------------

    async def _commit(self, total_ms: int) -> None:
        if self._pg is None:
            return
        try:
            await self._pg.execute(
                """
                INSERT INTO query_traces
                    (trace_id, query_text, intent, profile,
                     retrieval_hits, retrieval_ms, rag_skipped,
                     llm_model, tokens_in, tokens_out, llm_ms, total_ms, trace_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                self.trace_id,
                self.query_text,
                self.intent,
                self.profile,
                self.retrieval_hits,
                self.retrieval_ms,
                self.rag_skipped,
                self.llm_model,
                self.tokens_in,
                self.tokens_out,
                self.llm_ms,
                total_ms,
            )
            logger.debug(
                "trace_collector.commit trace_id=%s intent=%s total_ms=%d",
                self.trace_id, self.intent, total_ms,
            )
            
            # Phase 54.5 — Observability Spine Metrics
            try:
                from metrics import QUERY_TRACES_COMMITTED, QUERY_TRACE_TOTAL_LATENCY
                QUERY_TRACES_COMMITTED.inc()
                QUERY_TRACE_TOTAL_LATENCY.observe(total_ms / 1000.0)
            except (ImportError, Exception):
                pass
        except Exception as exc:
            logger.debug("trace_collector.commit error: %s", exc)


# ---------------------------------------------------------------------------
# HTTP handler — GET /api/traces
# ---------------------------------------------------------------------------

async def handle_get_traces(request) -> Any:
    """
    GET /api/traces?limit=100&intent=<intent>&min_latency_ms=<n>

    Returns last N query traces from PostgreSQL.
    """
    from aiohttp import web  # local import
    if _pg is None:
        return web.json_response({"error": "postgres_unavailable"}, status=503)

    try:
        limit = min(int(request.rel_url.query.get("limit", 100)), 500)
        intent_filter = request.rel_url.query.get("intent", "")
        min_latency = int(request.rel_url.query.get("min_latency_ms", 0))

        where_clauses = []
        params = []
        if intent_filter:
            where_clauses.append("intent = %s")
            params.append(intent_filter)
        if min_latency > 0:
            where_clauses.append("total_ms >= %s")
            params.append(min_latency)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(limit)

        rows = await _pg.fetch(
            f"""
            SELECT trace_id, query_text, intent, profile,
                   retrieval_hits, retrieval_ms, rag_skipped,
                   llm_model, tokens_in, tokens_out, llm_ms, total_ms, trace_at
            FROM query_traces
            {where_sql}
            ORDER BY trace_at DESC
            LIMIT %s
            """,
            *params,
        )
        traces = []
        for r in rows:
            traces.append({
                "trace_id": r["trace_id"],
                "query_text": (r["query_text"] or "")[:120],
                "intent": r["intent"],
                "profile": r["profile"],
                "retrieval_hits": r["retrieval_hits"],
                "retrieval_ms": r["retrieval_ms"],
                "rag_skipped": r["rag_skipped"],
                "llm_model": r["llm_model"],
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "llm_ms": r["llm_ms"],
                "total_ms": r["total_ms"],
                "trace_at": r["trace_at"].isoformat() if r["trace_at"] else None,
            })
        return web.json_response({"traces": traces, "count": len(traces)})
    except Exception as exc:
        logger.warning("handle_get_traces error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)
