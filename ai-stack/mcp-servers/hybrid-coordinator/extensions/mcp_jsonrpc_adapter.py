"""
Phase 68.2-68.3: MCP JSON-RPC 2.0 adapter for hybrid-coordinator.

Thin shim wrapping existing dispatch_tool() in JSON-RPC 2.0 envelope (MCP 2025-11-05).
Mounts at POST /mcp/v2 (tools/call, tools/list) and GET /mcp/v2/tools.
Zero changes to existing tool handler signatures.

Security (Gemini Phase 68 review):
  - Non-loopback callers require X-API-Key header.
  - tools/list is auth-required; NOT publicly enumerable.
  - Inherits S2 tool-level auth via dispatch_tool() → AUTH_PROFILE_TOOL_POLICY.

JSON-RPC 2.0 error codes (RFC 4627 + MCP spec):
  -32700  ParseError     — malformed JSON body
  -32600  InvalidRequest — missing jsonrpc/method fields
  -32601  MethodNotFound — unknown method
  -32602  InvalidParams  — params missing or wrong type
  -32603  InternalError  — tool execution error
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Auth helper (mirrors http_server_impl._is_loopback_agent_request logic)
# ---------------------------------------------------------------------------

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_loopback(request: web.Request) -> bool:
    """Return True if the request originates from loopback."""
    peer = request.transport and request.transport.get_extra_info("peername")
    host = peer[0] if peer else ""
    return host in _LOOPBACK_HOSTS


def _check_auth(request: web.Request, config_api_key: str) -> bool:
    """Return True if caller is authorized (loopback OR valid X-API-Key)."""
    if _is_loopback(request):
        return True
    provided = request.headers.get("X-API-Key", "")
    return bool(provided and provided == config_api_key)


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_mcp_v2_call(request: web.Request) -> web.Response:
    """POST /mcp/v2 — JSON-RPC 2.0 dispatcher (tools/call + tools/list)."""
    config = request.app.get("_config", {})
    api_key = config.get("api_key", "")

    if not _check_auth(request, api_key):
        return web.json_response(
            _err(None, -32600, "Unauthorized"),
            status=401,
        )

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return web.json_response(_err(None, -32700, "ParseError — body is not valid JSON"), status=400)

    req_id  = body.get("id")
    jsonrpc = body.get("jsonrpc")
    method  = body.get("method", "")
    params  = body.get("params") or {}

    if jsonrpc != "2.0" or not method:
        return web.json_response(_err(req_id, -32600, "InvalidRequest — jsonrpc='2.0' and method required"), status=400)

    # ── tools/list ────────────────────────────────────────────────────────────
    if method == "tools/list":
        try:
            from extensions import mcp_handlers
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in mcp_handlers.TOOL_DEFINITIONS
            ]
            return web.json_response(_ok(req_id, {"tools": tools}))
        except Exception as exc:
            logger.exception("mcp/v2 tools/list error")
            return web.json_response(_err(req_id, -32603, "InternalError", str(exc)), status=500)

    # ── tools/call ────────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name")
        arguments  = params.get("arguments") or {}
        if not tool_name:
            return web.json_response(_err(req_id, -32602, "InvalidParams — params.name required"), status=400)
        try:
            from extensions import mcp_handlers
            # Validate tool exists
            known = {t.name for t in mcp_handlers.TOOL_DEFINITIONS}
            if tool_name not in known:
                return web.json_response(_err(req_id, -32601, f"MethodNotFound — unknown tool '{tool_name}'"), status=404)
            results = await mcp_handlers.dispatch_tool(tool_name, arguments)
            content = [{"type": r.type, "text": r.text} for r in (results or [])]
            return web.json_response(_ok(req_id, {"content": content, "isError": False}))
        except Exception as exc:
            logger.exception("mcp/v2 tools/call error tool=%s", tool_name)
            return web.json_response(_err(req_id, -32603, "InternalError", str(exc)), status=500)

    # Unknown method
    return web.json_response(_err(req_id, -32601, f"MethodNotFound — unknown method '{method}'"), status=404)


async def handle_mcp_v2_tools(request: web.Request) -> web.Response:
    """GET /mcp/v2/tools — convenience REST endpoint; returns tools/list result.

    Auth-required per Gemini review: NOT publicly enumerable without X-API-Key.
    """
    config  = request.app.get("_config", {})
    api_key = config.get("api_key", "")
    if not _check_auth(request, api_key):
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        from extensions import mcp_handlers
        tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in mcp_handlers.TOOL_DEFINITIONS
        ]
        return web.json_response({
            "jsonrpc": "2.0",
            "id": None,
            "result": {"tools": tools},
            "meta": {
                "spec_version": "2025-11-05",
                "tool_count": len(tools),
                "endpoint": "/mcp/v2",
            },
        })
    except Exception as exc:
        logger.exception("mcp/v2/tools GET error")
        return web.json_response({"error": str(exc)}, status=500)


def register_routes(app: web.Application) -> None:
    """Phase 68.2-68.3: Register MCP JSON-RPC 2.0 routes."""
    app.router.add_post("/mcp/v2",       handle_mcp_v2_call)
    app.router.add_get("/mcp/v2/tools",  handle_mcp_v2_tools)
    logger.info("mcp_jsonrpc_adapter: /mcp/v2 (JSON-RPC 2.0) routes registered")
