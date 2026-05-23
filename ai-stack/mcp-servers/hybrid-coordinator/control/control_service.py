"""
control/control_service.py — ControlService for the hybrid-coordinator.

Phase R2.6 (Strangler Fig): route registration extracted from http_server.py.
Handles:
  GET /admin/v1/scheduler/status          — MLFQ scheduler status
  GET /admin/v1/policy/tool-deny-stats    — auth-profile tool denial counters (S2)
  GET /control/model-fleet/status         — model fleet status (model_fleet_manager)
  *   /control/runtimes/*                 — runtime registry (delegated to runtime_control_handlers)
  GET /control/fleet/summary              — fleet summary (delegated to runtime_control_handlers)
  GET /control/budget/*                   — budget policy (delegated to runtime_control_handlers)
  GET /control/reasoning/*                — reasoning profiles (delegated to runtime_control_handlers)

Standalone async handlers are written using direct module imports —
no configure() injection required; all dependencies are importable.

No handler logic beyond thin wrappers — delegates to existing modules.
"""

from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standalone handlers (converted from closures in http_server.run_http_mode)
# ---------------------------------------------------------------------------


async def handle_scheduler_status(request: web.Request) -> web.Response:
    """GET /admin/v1/scheduler/status — MLFQ scheduler queue snapshot."""
    from mlfq_scheduler import get_scheduler as _get_scheduler
    return web.json_response(await _get_scheduler().status())


async def handle_tool_deny_stats(request: web.Request) -> web.Response:
    """GET /admin/v1/policy/tool-deny-stats — auth-profile tool denial counts (S2)."""
    from middleware.auth import get_tool_denial_stats as _gds
    return web.json_response(_gds())


async def handle_fleet_status(request: web.Request) -> web.Response:
    """GET /control/model-fleet/status — model fleet health snapshot."""
    try:
        import model_fleet_manager as _mfm
        status = await _mfm.get_fleet_status()
        return web.json_response(status)
    except Exception as exc:
        logger.exception("handle_fleet_status error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all ControlService routes on the given aiohttp Application."""
    app.router.add_get("/admin/v1/scheduler/status", handle_scheduler_status)
    app.router.add_get("/admin/v1/policy/tool-deny-stats", handle_tool_deny_stats)
    app.router.add_get("/control/model-fleet/status", handle_fleet_status)

    # Runtime/budget/fleet/reasoning routes — already fully extracted
    import runtime_control_handlers as _rch
    _rch.register_routes(app)
