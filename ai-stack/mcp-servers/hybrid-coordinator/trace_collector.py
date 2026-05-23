"""
trace_collector.py — End-to-end query trace (Phase 54.5 + Phase E OTel GenAI SemConv)

Records a full span for every /query call:
    intent → profile → retrieval → LLM → memory_write → total_latency

Writes to PostgreSQL query_traces table (additive otel_attributes JSONB column added
in Phase E). Surfaced via GET /api/traces and the dashboard Intelligence lane.

Phase E addition: OTel GenAI Semantic Conventions 2026
  - TraceCollector.otel_span() returns gen_ai.* attribute dict (no external SDK needed)
  - If OTEL_EXPORTER_OTLP_ENDPOINT env var is set, span is pushed via aiohttp in background
  - Gracefully skips if OTLP endpoint is not configured
  - Internal attribute names (gen_ai.maeah.*) are MAEAH-specific extensions; all standard
    gen_ai.* names follow the OTel GenAI SemConv 2026 specification pin

OTel GenAI SemConv attributes emitted (spec pin: OTel GenAI SemConv 2026-01):
  gen_ai.system                 llama_cpp | anthropic | openai
  gen_ai.operation.name         chat | text_completion | embeddings
  gen_ai.request.model          model name from request
  gen_ai.response.model         actual model used
  gen_ai.usage.input_tokens     prompt token count
  gen_ai.usage.output_tokens    completion token count
  gen_ai.response.finish_reason stop | length | tool_calls | content_filter
  gen_ai.maeah.intent           MAEAH intent class (extension)
  gen_ai.maeah.profile          routing profile (extension)
  gen_ai.maeah.retrieval_hits   RAG hit count (extension)
  gen_ai.maeah.retrieval_ms     RAG latency ms (extension)
  gen_ai.maeah.ttft_ms          LLM response latency (extension)
  gen_ai.maeah.rag_skipped      RAG was bypassed (extension)

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
        otel_attributes JSONB,           -- Phase E: gen_ai.* span attrs
        trace_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )

Usage:
    async with TraceCollector(pg_client) as tc:
        tc.set_intent("knowledge_lookup")
        tc.set_profile("local-tool-calling")
        tc.set_retrieval(hits=5, latency_ms=42, skipped=False)
        tc.set_llm("qwen3", tokens_in=1200, tokens_out=300, latency_ms=9800)
        # on __aexit__ → writes row to DB + emits OTLP span if endpoint configured

    # Inspect OTel attributes without DB:
    tc = TraceCollector(None)
    tc.set_intent("code_generation")
    span = tc.otel_span()   # returns gen_ai.* dict
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
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
    otel_attributes JSONB,
    trace_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_query_traces_intent   ON query_traces (intent);
CREATE INDEX IF NOT EXISTS idx_query_traces_trace_at ON query_traces (trace_at DESC);
"""

# Phase E: additive migration — adds otel_attributes column if not present
_DDL_MIGRATE_OTEL = """
ALTER TABLE query_traces ADD COLUMN IF NOT EXISTS otel_attributes JSONB;
"""

# Phase 64.1: additive migration — adds prompt_hash column for prompt versioning
_DDL_MIGRATE_PROMPT_HASH = """
ALTER TABLE query_traces ADD COLUMN IF NOT EXISTS prompt_hash TEXT;
"""

# OTel GenAI SemConv spec pin (Phase E — update when upgrading spec version)
_OTEL_SEMCONV_VERSION = "2026-01"
_OTEL_EXPORTER_URL = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

# Profile → gen_ai.system mapping
_PROFILE_TO_SYSTEM: Dict[str, str] = {
    "local-tool-calling": "llama_cpp",
    "embedded-assist": "llama_cpp",
    "remote": "openai",
    "claude": "anthropic",
    "gemini": "google",
}

# Module-level pg reference — injected via init()
_pg: Optional[Any] = None
_schema_ready: bool = False


def init(postgres_client: Any) -> None:
    """Inject postgres client. Call once from server.py startup."""
    global _pg
    _pg = postgres_client
    logger.info("trace_collector: initialized with postgres client")


async def ensure_schema(postgres_client: Optional[Any] = None) -> None:
    """Idempotently create query_traces table and apply Phase E migration."""
    global _schema_ready
    if _schema_ready:
        return
    pg = postgres_client or _pg
    if pg is None:
        return
    try:
        await pg.execute(_DDL_TRACES)
        # Phase E: add otel_attributes column to existing tables
        try:
            await pg.execute(_DDL_MIGRATE_OTEL)
        except Exception:
            pass  # column may already exist
        # Phase 64.1: add prompt_hash column for prompt versioning
        try:
            await pg.execute(_DDL_MIGRATE_PROMPT_HASH)
        except Exception:
            pass
        _schema_ready = True
        logger.info("trace_collector: schema ready (Phase E otel_attributes + 64.1 prompt_hash)")
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
        self.retrieval_collection_count: int = 0
        self.rag_skipped: bool = True
        self.llm_model: str = ""
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        self.llm_ms: int = 0
        self.finish_reason: str = "stop"   # Phase E: OTel gen_ai.response.finish_reason
        self.prompt_hash: str = ""          # Phase 64.1: SHA256[:8] of system prompt
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

    def set_retrieval(self, hits: int, latency_ms: int, skipped: bool = False, collection_count: int = 0) -> None:
        self.retrieval_hits = hits
        self.retrieval_ms = latency_ms
        self.rag_skipped = skipped
        self.retrieval_collection_count = collection_count

    def set_system_prompt(self, system_prompt: str) -> None:
        """Phase 64.1: hash the system prompt for prompt versioning. SHA256[:8]."""
        if system_prompt:
            self.prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:8]

    def set_llm(self, model: str, tokens_in: int = 0, tokens_out: int = 0, latency_ms: int = 0,
                finish_reason: str = "stop") -> None:
        self.llm_model = model
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.llm_ms = latency_ms
        self.finish_reason = finish_reason

    def otel_span(self, total_ms: Optional[int] = None) -> Dict[str, Any]:
        """Return OTel GenAI SemConv 2026 span attributes.

        Follows spec pin _OTEL_SEMCONV_VERSION. Standard gen_ai.* names are
        from the spec; gen_ai.maeah.* names are MAEAH-specific extensions.
        This dict can be serialised and emitted to any OTel collector.
        """
        if total_ms is None:
            total_ms = int((time.perf_counter() - self._start) * 1000)
        system = _PROFILE_TO_SYSTEM.get(self.profile, "llama_cpp")
        return {
            # Standard OTel GenAI SemConv 2026 attributes
            "gen_ai.system": system,
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": self.llm_model or "unknown",
            "gen_ai.response.model": self.llm_model or "unknown",
            "gen_ai.usage.input_tokens": self.tokens_in,
            "gen_ai.usage.output_tokens": self.tokens_out,
            "gen_ai.response.finish_reason": self.finish_reason,
            # MAEAH-specific extension attributes
            "gen_ai.maeah.trace_id": self.trace_id,
            "gen_ai.maeah.intent": self.intent,
            "gen_ai.maeah.profile": self.profile,
            "gen_ai.maeah.retrieval_hits": self.retrieval_hits,
            "gen_ai.maeah.retrieval_ms": self.retrieval_ms,
            "gen_ai.maeah.retrieval_collection_count": self.retrieval_collection_count,
            "gen_ai.maeah.rag_skipped": self.rag_skipped,
            "gen_ai.maeah.ttft_ms": self.llm_ms,
            "gen_ai.maeah.total_ms": total_ms,
            "gen_ai.maeah.semconv_version": _OTEL_SEMCONV_VERSION,
            "gen_ai.maeah.prompt_hash": self.prompt_hash,   # Phase 64.1
        }

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
            "finish_reason": self.finish_reason,
            "prompt_hash": self.prompt_hash,
            "otel_attributes": self.otel_span(total_ms),
            "trace_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal commit
    # ------------------------------------------------------------------

    async def _commit(self, total_ms: int) -> None:
        otel_attrs = self.otel_span(total_ms)
        if self._pg is not None:
            try:
                await self._pg.execute(
                    """
                    INSERT INTO query_traces
                        (trace_id, query_text, intent, profile,
                         retrieval_hits, retrieval_ms, rag_skipped,
                         llm_model, tokens_in, tokens_out, llm_ms, total_ms,
                         otel_attributes, prompt_hash, trace_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
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
                    json.dumps(otel_attrs),
                    self.prompt_hash or None,
                )
                logger.debug(
                    "trace_collector.commit trace_id=%s intent=%s total_ms=%d",
                    self.trace_id, self.intent, total_ms,
                )
            except Exception as exc:
                logger.debug("trace_collector.commit error: %s", exc)

        # Phase 54.5 — Observability Spine Metrics
        try:
            from metrics import QUERY_TRACES_COMMITTED, QUERY_TRACE_TOTAL_LATENCY
            QUERY_TRACES_COMMITTED.inc()
            QUERY_TRACE_TOTAL_LATENCY.observe(total_ms / 1000.0)
        except (ImportError, Exception):
            pass

        # Phase E — emit OTLP span if endpoint configured (fire-and-forget)
        if _OTEL_EXPORTER_URL:
            import asyncio
            asyncio.create_task(_emit_otlp_span(otel_attrs, self.trace_id))


# ---------------------------------------------------------------------------
# Phase E — OTLP HTTP/JSON span emitter
# ---------------------------------------------------------------------------

async def _emit_otlp_span(attrs: Dict[str, Any], trace_id: str) -> None:
    """Fire-and-forget OTLP/HTTP span export. Silently skips on any error."""
    if not _OTEL_EXPORTER_URL:
        return
    endpoint = _OTEL_EXPORTER_URL.rstrip("/") + "/v1/traces"
    # Minimal OTLP JSON envelope (protobuf-JSON encoding)
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "maeah-coordinator"}},
            ]},
            "scopeSpans": [{
                "scope": {"name": "trace_collector", "version": _OTEL_SEMCONV_VERSION},
                "spans": [{
                    "traceId": trace_id.replace("-", ""),
                    "spanId": trace_id.replace("-", "")[:16],
                    "name": f"gen_ai.{attrs.get('gen_ai.operation.name','chat')}",
                    "kind": 3,  # CLIENT
                    "startTimeUnixNano": str(int((time.time() - attrs.get("gen_ai.maeah.total_ms", 0) / 1000) * 1e9)),
                    "endTimeUnixNano": str(int(time.time() * 1e9)),
                    "attributes": [
                        {"key": k, "value": _otlp_value(v)}
                        for k, v in attrs.items()
                    ],
                    "status": {"code": 1},  # OK
                }],
            }],
        }],
    }
    try:
        import aiohttp
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=3.0)
        ) as session:
            await session.post(endpoint, json=payload)
    except Exception:
        pass  # OTLP export is best-effort, never block traces


def _otlp_value(v: Any) -> Dict[str, Any]:
    """Convert Python value to OTLP AnyValue JSON encoding."""
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": v}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}


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

        rows = await _pg.fetch_all(
            f"""
            SELECT trace_id, query_text, intent, profile,
                   retrieval_hits, retrieval_ms, rag_skipped,
                   llm_model, tokens_in, tokens_out, llm_ms, total_ms,
                   otel_attributes, prompt_hash, trace_at
            FROM query_traces
            {where_sql}
            ORDER BY trace_at DESC
            LIMIT %s
            """,
            *params,
        )
        traces = []
        for r in rows:
            otel = r.get("otel_attributes")
            if isinstance(otel, str):
                try:
                    otel = json.loads(otel)
                except Exception:
                    otel = None
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
                "otel_attributes": otel,
                "prompt_hash": r.get("prompt_hash"),   # Phase 64.1
                "trace_at": r["trace_at"].isoformat() if r["trace_at"] else None,
            })
        return web.json_response({"traces": traces, "count": len(traces)})
    except Exception as exc:
        logger.warning("handle_get_traces error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)
