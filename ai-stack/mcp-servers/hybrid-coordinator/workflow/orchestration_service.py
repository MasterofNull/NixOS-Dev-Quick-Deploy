"""
workflow/orchestration_service.py — OrchestrationService for the hybrid-coordinator.

Phase R2.5 (Strangler Fig): route registration extracted from http_server.py.
Handles:
  POST /v1/orchestrate   — unified front-door routing (handle_orchestrate facade)
  POST /search/tree      — multi-collection tree search (handle_tree_search)
  *    /workflow/graph/* — orchestration graph runner (delegated to orchestration_graph_runner)

handle_orchestrate and handle_tree_search are closures in http_server.run_http_mode().
configure() stores their refs; register_routes() uses them when wiring the router.

No handler logic in this file — thin wiring shim only.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Injected runtime refs (set by configure(), called from http_server.run_http_mode())
# ---------------------------------------------------------------------------

_handle_orchestrate: Optional[Callable] = None
_handle_tree_search: Optional[Callable] = None


def configure(
    handle_orchestrate_fn: Callable,
    handle_tree_search_fn: Callable,
) -> None:
    """Inject closure refs from http_server.run_http_mode(). Call before create_app()."""
    global _handle_orchestrate, _handle_tree_search
    _handle_orchestrate = handle_orchestrate_fn
    _handle_tree_search = handle_tree_search_fn
    logger.debug("orchestration_service.configure: refs injected")


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all OrchestrationService routes on the given aiohttp Application."""
    if _handle_orchestrate is None or _handle_tree_search is None:
        raise RuntimeError(
            "orchestration_service.configure() must be called before register_routes()"
        )
    app.router.add_post("/v1/orchestrate", _handle_orchestrate)
    app.router.add_post("/search/tree", _handle_tree_search)

    # Orchestration graph runner already extracted to workflow/orchestration_graph_runner.py
    import orchestration_graph_runner as _ogr
    _ogr.register_routes(app)
