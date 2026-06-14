"""
router.py — Thin aiohttp Application factory for the hybrid-coordinator.

Phase R2 Strangler Fig migration:
  - R2.1 (this file): Skeleton with full middleware pipeline; http_server.py
    still handles all routes via its own web.Application.
  - R2.2+: Domain services wired in here one by one; each service's routes
    are registered here and removed from http_server.py per slice.
  - R2.8: http_server.py reduced to ≤100-line compatibility shim that calls
    create_app() and registers legacy routes only.

Public API:
    from router import create_app
    app = create_app()
    web.run_app(app, port=port)

Design invariants:
  - No inline handler logic in this file — handlers live in domain service modules.
  - All middleware logic extracted into named factory functions for testability.
  - Each R2.x slice adds one `_register_<service>_routes(app)` call here.
  - Rollback = revert the `_register_*` call + the domain service module.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, List, Optional
from uuid import uuid4

from aiohttp import web
from opentelemetry import trace

from config import Config
from middleware.auth import create_api_key_middleware
from metrics import REQUEST_COUNT, REQUEST_ERRORS, REQUEST_LATENCY
from shared.rate_limiter import create_rate_limiter_middleware, RateLimiterConfig

_SERVICE_NAME = "hybrid-coordinator"
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Middleware factory functions
# ---------------------------------------------------------------------------


def _make_tracing_middleware() -> web.middleware:  # type: ignore[type-arg]
    """OTel tracing middleware — wraps each request in a span."""
    @web.middleware
    async def tracing_middleware(request: web.Request, handler):
        tracer = trace.get_tracer(_SERVICE_NAME)
        span_name = f"{request.method} {request.path}"
        with tracer.start_as_current_span(
            span_name,
            attributes={
                "http.method": request.method,
                "http.target": request.path,
            },
        ) as span:
            response = await handler(request)
            span.set_attribute("http.status_code", response.status)
            return response

    return tracing_middleware


def _make_request_id_middleware(
    audit_request_fn: Optional[Callable] = None,
) -> web.middleware:  # type: ignore[type-arg]
    """
    Request-ID + latency/error metrics middleware.

    Assigns X-Request-ID (from header or generated), records Prometheus
    latency/count/error metrics, and mirrors the ID back in the response header.

    Args:
        audit_request_fn: Optional audit hook (signature: fn(request, status_int, latency_ms)).
            Injected from http_server.py during the Strangler Fig migration; will be
            replaced by a standalone audit module in R2.7.
    """
    import time as _time

    @web.middleware
    async def request_id_middleware(request: web.Request, handler):
        from structlog.contextvars import bind_contextvars, clear_contextvars

        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request["request_id"] = request_id
        bind_contextvars(request_id=request_id)
        start = _time.perf_counter()
        response: Optional[web.Response] = None
        try:
            response = await handler(request)
            return response
        except Exception:  # noqa: BLE001
            REQUEST_ERRORS.labels(request.path, request.method).inc()
            raise
        finally:
            duration = _time.perf_counter() - start
            status = str(response.status) if response is not None else "500"
            REQUEST_LATENCY.labels(request.path, request.method).observe(duration)
            REQUEST_COUNT.labels(request.path, status).inc()
            if audit_request_fn is not None:
                try:
                    audit_request_fn(request, int(status), duration * 1000.0)
                except Exception:  # noqa: BLE001
                    pass  # audit must not crash the request pipeline
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            clear_contextvars()

    return request_id_middleware


def _make_rate_limit_config() -> RateLimiterConfig:
    """Build rate-limiter config from env vars (mirrors http_server.py defaults)."""
    return RateLimiterConfig(
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        default_rpm=int(os.getenv("RATE_LIMIT_DEFAULT_RPM", "100")),
        default_rph=int(os.getenv("RATE_LIMIT_DEFAULT_RPH", "3000")),
        burst_multiplier=float(os.getenv("RATE_LIMIT_BURST_MULTIPLIER", "1.5")),
        endpoint_limits={
            "/": int(os.getenv("RATE_LIMIT_ROOT_RPM", "300")),
            "/query": int(os.getenv("RATE_LIMIT_QUERY_RPM", "30")),
            "/search/tree": int(os.getenv("RATE_LIMIT_TREE_RPM", "20")),
            "/hints": int(os.getenv("RATE_LIMIT_HINTS_RPM", "60")),
            "/harness/eval": int(os.getenv("RATE_LIMIT_EVAL_RPM", "20")),
            "/workflow": int(os.getenv("RATE_LIMIT_WORKFLOW_RPM", "30")),
            "/a2a": int(os.getenv("RATE_LIMIT_A2A_RPM", "300")),
            "/control/ai-coordinator/delegate": int(os.getenv("RATE_LIMIT_DELEGATE_RPM", "10")),
            "/research/web/fetch": int(os.getenv("RATE_LIMIT_RESEARCH_RPM", "20")),
        },
        exempt_paths={"/health", "/metrics", "/health/detailed", "/health/aggregate"},
    )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def _register_insights_routes(app: web.Application) -> None:
    """R2.6: Register InsightsService routes (/api/traces, /eval/run, /eval/trend)."""
    from telemetry import insights_service as _is
    _is.register_routes(app)


def _register_control_routes(app: web.Application) -> None:
    """R2.6: Register ControlService routes (/admin/v1/*, /control/*)."""
    from control import control_service as _cs
    _cs.register_routes(app)


def _register_agent_routes(app: web.Application) -> None:
    """R2.6: Register AgentService routes (/api/agent-*, /a2a/*)."""
    from agent import agent_service as _as
    _as.register_routes(app)


def _register_orchestration_routes(app: web.Application) -> None:
    """R2.5: Register OrchestrationService routes (/v1/orchestrate, /search/tree, /workflow/graph/*)."""
    from workflow import orchestration_service as _os
    _os.register_routes(app)


def _register_query_routes(app: web.Application) -> None:
    """R2.4: Register QueryService routes (/query, /api/query, /augment_query)."""
    from query import query_service as _qs
    _qs.register_routes(app)


def _register_memory_routes(app: web.Application) -> None:
    """R2.3: Register MemoryService routes (/api/memory/facts, /memory/journal, supersede, crystallizer)."""
    from memory import memory_service as _ms
    _ms.register_routes(app)


def _register_status_routes(app: web.Application) -> None:
    """R2.2: Register StatusService routes (/status, /api/hardware/state, /stats/delegate)."""
    from core import status_service as _ss
    _ss.register_routes(app)


def create_app(
    extra_middlewares: Optional[List] = None,
    audit_request_fn: Optional[Callable] = None,
) -> web.Application:
    """
    Create the aiohttp Application with the standard middleware stack.

    Middleware order (same as http_server.py):
        1. tracing_middleware   — OTel span per request
        2. request_id_middleware — X-Request-ID + Prometheus metrics
        3. rate_limit_middleware — sliding-window rate limiting
        4. api_key_middleware   — API key authentication

    R2.1: Routing table is EMPTY — http_server.py handles all routes via its
    own web.Application instance. Starting from R2.2, domain service routes
    are registered here and the corresponding handlers removed from http_server.py.

    Args:
        extra_middlewares: Optional list of additional middlewares appended
            after the standard stack (useful for test overrides).

    Returns:
        Configured web.Application ready for route registration.
    """
    rate_limiter_config = _make_rate_limit_config()
    _rate_limiter, rate_limit_middleware = create_rate_limiter_middleware(rate_limiter_config)
    logger.info(
        "router.create_app rate_limit enabled=%s default_rpm=%s",
        rate_limiter_config.enabled,
        rate_limiter_config.default_rpm,
    )

    middlewares: List = [
        _make_tracing_middleware(),
        _make_request_id_middleware(audit_request_fn=audit_request_fn),
        rate_limit_middleware,
        create_api_key_middleware(),
    ]
    if extra_middlewares:
        middlewares.extend(extra_middlewares)

    app = web.Application(middlewares=middlewares)
    app["rate_limiter"] = _rate_limiter

    # -----------------------------------------------------------------------
    # Route registration — one block per R2.x slice.
    # R2.1: no routes yet — all handled by http_server.py.
    # Uncomment each block as its slice is implemented and tested.
    # -----------------------------------------------------------------------

    # R2.2: StatusService (/status, /api/hardware/state, /stats/delegate)
    _register_status_routes(app)

    # R2.3: MemoryService (/api/memory/facts, /memory/journal, /memory/supersede)
    _register_memory_routes(app)

    # R2.4: QueryService (/query, /api/query, /augment_query)
    _register_query_routes(app)

    # R2.5: OrchestrationService (/v1/orchestrate, /search/tree, /workflow/graph/run)
    _register_orchestration_routes(app)

    # R2.6: InsightsService + ControlService + AgentService
    _register_insights_routes(app)
    _register_control_routes(app)
    _register_agent_routes(app)

    # Phase 61: ContextLifecycleManager (/context/lifecycle/*)
    _register_clm_routes(app)

    # Phase 63: GraphRAG knowledge search (/api/knowledge/graph/search)
    _register_graph_search_routes(app)

    # Phase 68.2-68.3: MCP JSON-RPC 2.0 adapter (/mcp/v2, /mcp/v2/tools)
    _register_mcp_jsonrpc_routes(app)

    # Phase 69.3: Temporal Knowledge Graph (/knowledge/graph/fact-chain)
    _register_temporal_graph_routes(app)

    # Phase 70.1: Reputation-weighted consensus engine (/workflow/consensus/vote)
    _register_consensus_routes(app)

    return app


def _register_clm_routes(app: web.Application) -> None:
    """Phase 61: Register CLM routes (/context/lifecycle/status, /context/lifecycle/evict/{id})."""
    from knowledge import context_lifecycle_manager as _clm
    _clm.register_routes(app)


def _register_graph_search_routes(app: web.Application) -> None:
    """Phase 63: Register GraphRAG search route (/api/knowledge/graph/search)."""
    try:
        from knowledge import graph_search as _gs
        _gs.register_routes(app)
    except Exception as exc:
        import logging
        logging.getLogger("hybrid-coordinator").warning("GraphRAG route registration skipped: %s", exc)


def _register_mcp_jsonrpc_routes(app: web.Application) -> None:
    """Phase 68.2-68.3: Register MCP JSON-RPC 2.0 adapter routes (/mcp/v2, /mcp/v2/tools)."""
    try:
        from extensions import mcp_jsonrpc_adapter as _mcp_rpc
        _mcp_rpc.register_routes(app)
    except Exception as exc:
        import logging
        logging.getLogger("hybrid-coordinator").warning("MCP JSON-RPC 2.0 route registration skipped: %s", exc)


def _register_temporal_graph_routes(app: web.Application) -> None:
    """Phase 69.3: Register Temporal Knowledge Graph routes (/knowledge/graph/fact-chain)."""
    try:
        from knowledge import temporal_graph as _tg
        _tg.register_routes(app)
    except Exception as exc:
        import logging
        logging.getLogger("hybrid-coordinator").warning("Temporal graph route registration skipped: %s", exc)


def _register_consensus_routes(app: web.Application) -> None:
    """Phase 70.1: Register reputation-weighted consensus routes (/workflow/consensus/*)."""
    try:
        from workflow import consensus_engine as _ce
        _ce.register_routes(app)
    except Exception as exc:
        import logging
        logging.getLogger("hybrid-coordinator").warning("Consensus engine route registration skipped: %s", exc)
