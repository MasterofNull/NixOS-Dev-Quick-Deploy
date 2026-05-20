"""
middleware/auth.py — Canonical authentication middleware for the hybrid-coordinator.

Phase R2.7 (Strangler Fig): consolidated from two divergent copies:
  - core/auth_middleware.py (Phase 12.4 extraction)
  - http_server.py:_is_loopback_request / _is_loopback_agent_request (inline copy)

Changes vs prior state:
  - LOOPBACK_AGENT_PREFIXES is the union of both copies (5 prefixes were missing
    from core/auth_middleware.py: /control/safety/, /agent/lifecycle/,
    /control/reasoning/, /control/budget/, /control/fleet/)
  - _is_loopback_request uses only req.remote (does NOT trust X-Forwarded-For —
    it is trivially spoofable by any remote client)
  - API_KEY_HEADER constant replaces all "X-API-Key" string literals

core/auth_middleware.py is kept as a re-export shim for backwards compatibility.
"""

from aiohttp import web
from config import Config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The header name used for API key authentication.
API_KEY_HEADER = "X-API-Key"

# Endpoints always accessible without authentication (health, metrics, discovery).
PUBLIC_PATHS = frozenset({
    "/health",
    "/metrics",
    "/.well-known/mcp.json",
    "/.well-known/agent.json",
    "/.well-known/agent-card.json",
    "/health/detailed",
    "/health/aggregate",
})

# Endpoint prefixes reachable from localhost without an API key.
# Local agents (Qwen, Claude Code, Aider, etc.) running on the same machine
# should be able to use the harness without manual API key configuration.
# Remote requests still require full auth.
#
# This is the canonical union of:
#   - core/auth_middleware.py LOOPBACK_AGENT_PREFIXES (Phase 12.4)
#   - http_server.py agent_prefixes (Phase 54, 56)
LOOPBACK_AGENT_PREFIXES = (
    "/hints",
    "/workflow/",
    "/query",
    "/v1/orchestrate",
    "/v1/",
    "/review/",
    "/discovery/",
    "/control/ai-coordinator/",
    "/control/llm/",
    "/control/agents/",
    "/control/agents",
    "/control/review/",
    "/control/runtimes",
    "/control/runtimes/",
    "/memory/",
    "/memory/crystalline/",
    "/learning/",
    "/cache/",
    "/harness/",
    "/parity/",
    "/feedback",
    "/status",
    "/alerts",
    "/stats",
    "/learning/stats",
    "/control/safety/",    # Phase 28: local agents set session safety mode
    "/agent/lifecycle/",   # Phase 37: UAG lifecycle replay (aq-qa probe)
    "/control/reasoning/", # Phase 51: ablation/reasoning profile pack
    "/control/budget/",    # Phase 45: budget policy read
    "/control/fleet/",     # Phase 42: fleet summary
    "/control/intent/",    # Phase 54: intent classification map + reload
    "/api/health/",        # Phase 54: RAG health gate (L6)
    "/api/traces",         # Phase 54: query trace explorer
    "/eval/run",           # Phase 54: trigger eval run
    "/eval/trend",         # Phase 54: eval trend history
    "/api/agent-events",   # Phase 56: agent event bus
    "/api/agent-ops/",     # Phase 56: agent ops status
    "/api/memory/facts",   # Phase 56: commit fact ingest
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _is_loopback_request(req: web.Request) -> bool:
    """Return True when the request originates from localhost.

    NOTE: X-Forwarded-For is intentionally NOT trusted — it is trivially spoofable
    by any remote client. Only the aiohttp transport-level peer address is used.
    """
    remote = (req.remote or "").strip()
    return remote in {"127.0.0.1", "::1", "localhost"}


def _is_loopback_agent_request(req: web.Request) -> bool:
    """Return True if request is from localhost AND targets an agent-accessible endpoint."""
    if not _is_loopback_request(req):
        return False
    return any(req.path.startswith(pfx) for pfx in LOOPBACK_AGENT_PREFIXES)


# ---------------------------------------------------------------------------
# Middleware factory
# ---------------------------------------------------------------------------


def create_api_key_middleware():
    """Return the aiohttp middleware that enforces API key authentication."""

    async def api_key_middleware(request: web.Request, handler):
        if request.path in PUBLIC_PATHS:
            return await handler(request)
        if _is_loopback_agent_request(request):
            return await handler(request)
        if not Config.API_KEY:
            return await handler(request)
        token = (
            request.headers.get(API_KEY_HEADER)
            or request.headers.get("Authorization", "")
        )
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
        if token != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    return api_key_middleware
