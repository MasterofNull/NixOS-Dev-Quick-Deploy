"""
telemetry/insights_service.py — InsightsService for the hybrid-coordinator.

Phase R2.6 (Strangler Fig): route registration extracted from http_server.py.
Handles:
  GET  /api/traces        — query trace explorer (trace_collector)
  POST /eval/run          — trigger continuous eval run (eval_runner)
  GET  /eval/trend        — eval trend history + RAGAS metric averages (eval_runner)
  POST /eval/score-query  — record per-query RAGAS metrics (eval_runner Phase 60.5)

All handler refs are direct module-level functions — no configure() injection
required; modules are importable without DI.

No handler logic in this file — thin wiring shim only.
"""

from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all InsightsService routes on the given aiohttp Application."""
    import trace_collector as _tc
    import eval_runner as _er
    from telemetry import health_spider_handlers as _hsh

    app.router.add_get("/api/traces", _tc.handle_get_traces)
    app.router.add_post("/eval/run", _er.handle_eval_run)
    app.router.add_get("/eval/trend", _er.handle_eval_trend)
    app.router.add_post("/eval/score-query", _er.handle_eval_score_query)
    app.router.add_get("/api/telemetry/anomalies", _hsh.handle_get_anomalies)
