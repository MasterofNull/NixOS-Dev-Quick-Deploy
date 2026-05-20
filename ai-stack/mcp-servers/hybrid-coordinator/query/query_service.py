"""
query/query_service.py — QueryService for the hybrid-coordinator.

Phase R2.4 (Strangler Fig): route registration extracted from http_server.py.
Handles:
  POST /query        — public query routing (handle_query_http facade)
  POST /api/query    — alias of /query
  POST /augment_query — context augmentation for agent queries

The actual handler logic lives in http_server.py as closures (heavy DI chain).
configure() is called from run_http_mode() after closures are defined; it
stores references that register_routes() uses when wiring the aiohttp router.

No handler logic in this file — a thin wiring shim only.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Injected runtime refs (set by configure(), called from http_server.run_http_mode())
# ---------------------------------------------------------------------------

_handle_query_http: Optional[Callable] = None
_handle_augment_query: Optional[Callable] = None


def configure(
    handle_query_fn: Callable,
    handle_query_http_fn: Callable,
    handle_augment_query_fn: Callable,
) -> None:
    """Inject closure refs from http_server.run_http_mode(). Call before create_app()."""
    global _handle_query_http, _handle_augment_query
    # handle_query_fn is the MCP/internal entry point; the HTTP facade is
    # handle_query_http_fn — both /query and /api/query use the facade.
    _ = handle_query_fn  # reserved for R2.5+ internal wiring
    _handle_query_http = handle_query_http_fn
    _handle_augment_query = handle_augment_query_fn
    logger.debug("query_service.configure: refs injected")


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all QueryService routes on the given aiohttp Application."""
    if _handle_query_http is None or _handle_augment_query is None:
        raise RuntimeError(
            "query_service.configure() must be called before register_routes()"
        )
    app.router.add_post("/query", _handle_query_http)
    app.router.add_post("/api/query", _handle_query_http)
    app.router.add_post("/augment_query", _handle_augment_query)
