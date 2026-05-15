"""
API key authentication middleware for the hybrid-coordinator HTTP server.

Extracted from http_server.py during Phase 12.4 decomposition.
Provides:
  - create_api_key_middleware() → aiohttp middleware coroutine
  - Public path list and loopback bypass logic are co-located here for
    easy auditing — all auth policy in one place.
"""

from aiohttp import web
from config import Config

# Endpoints always accessible without authentication (health, metrics, A2A discovery)
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
    # Phase 54: Agentic-First Architecture Elevation endpoints
    "/control/intent/",
    "/api/health/",
    "/api/traces",
    "/eval/run",
    "/eval/trend",
    # Phase 56: Harness Integration Loop
    "/api/agent-events",
    "/api/agent-ops/",
    "/api/memory/facts",
)


def _is_loopback_request(req: web.Request) -> bool:
    """Return True if the request originates from localhost."""
    remote = (req.remote or "").strip()
    if remote in {"127.0.0.1", "::1", "localhost"}:
        return True
    forwarded_for = (req.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded_for in {"127.0.0.1", "::1", "localhost"}


def _is_loopback_agent_request(req: web.Request) -> bool:
    """Return True if request is from localhost AND targets an agent-accessible endpoint."""
    if not _is_loopback_request(req):
        return False
    return any(req.path.startswith(pfx) for pfx in LOOPBACK_AGENT_PREFIXES)


def create_api_key_middleware():
    """Return the aiohttp middleware that enforces API key authentication."""

    async def api_key_middleware(request: web.Request, handler):
        if request.path in PUBLIC_PATHS:
            return await handler(request)
        if _is_loopback_agent_request(request):
            return await handler(request)
        if not Config.API_KEY:
            return await handler(request)
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
        if token != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    return api_key_middleware
