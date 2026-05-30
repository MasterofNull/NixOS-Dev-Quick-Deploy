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

# Optional profile request header. The server validates this against the
# authenticated request mode and records the effective profile in request state.
AUTH_PROFILE_HEADER = "X-Harness-Auth-Profile"
AUTH_CONTEXT_KEY = "auth_context"

AUTH_PROFILE_POLICY = {
    "public": {
        "default_profile": "readonly-strict",
        "allowed_profiles": ["readonly-strict"],
    },
    "loopback-agent": {
        "default_profile": "execute-guarded",
        "allowed_profiles": ["readonly-strict", "execute-guarded"],
    },
    "api-key": {
        "default_profile": "execute-guarded",
        "allowed_profiles": ["readonly-strict", "execute-guarded", "worktree-guarded"],
    },
    "no-api-key-configured": {
        "default_profile": "execute-guarded",
        "allowed_profiles": ["readonly-strict", "execute-guarded"],
    },
}

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
    "/qa/",                # Phase 84: QA check runner (loopback agents need eval access)
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


def _is_loopback_agent_path(path: str) -> bool:
    """Return True when a path is eligible for local-agent loopback access."""
    return any(path.startswith(pfx) for pfx in LOOPBACK_AGENT_PREFIXES)


def _extract_token(headers) -> str:
    token = headers.get(API_KEY_HEADER) or headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    return str(token).strip()


def _auth_context(mode: str, profile: str, authenticated: bool, reason: str) -> dict:
    return {
        "mode": mode,
        "profile": profile,
        "authenticated": authenticated,
        "reason": reason,
    }


def _profile_for_mode(mode: str, requested_profile: str = "") -> tuple[str, str]:
    policy = AUTH_PROFILE_POLICY.get(mode, AUTH_PROFILE_POLICY["public"])
    allowed = set(policy.get("allowed_profiles", []))
    profile = (requested_profile or "").strip() or str(policy.get("default_profile", "readonly-strict"))
    if profile not in allowed:
        return "", f"profile '{profile}' is not allowed for auth mode '{mode}'"
    return profile, ""


def resolve_auth_context(path: str, remote: str, headers, configured_api_key: str) -> tuple[dict, int]:
    """Resolve request auth mode and effective runtime profile.

    Returns ``(context, status)`` where status is 0 when the request may
    continue, 401 for authentication failure, and 403 for invalid profile
    requests. This pure helper keeps the runtime middleware testable without
    constructing aiohttp request transports.
    """
    requested_profile = str(headers.get(AUTH_PROFILE_HEADER, "")).strip()

    if path in PUBLIC_PATHS:
        profile, error = _profile_for_mode("public", requested_profile)
        if error:
            return {"error": error}, 403
        return _auth_context("public", profile, False, "public_path"), 0

    if remote in {"127.0.0.1", "::1", "localhost"} and _is_loopback_agent_path(path):
        profile, error = _profile_for_mode("loopback-agent", requested_profile)
        if error:
            return {"error": error}, 403
        return _auth_context("loopback-agent", profile, True, "loopback_agent_prefix"), 0

    if not configured_api_key:
        profile, error = _profile_for_mode("no-api-key-configured", requested_profile)
        if error:
            return {"error": error}, 403
        return _auth_context("no-api-key-configured", profile, True, "api_key_not_configured"), 0

    token = _extract_token(headers)
    if token != configured_api_key:
        return {"error": "unauthorized", "mode": "api-key"}, 401

    profile, error = _profile_for_mode("api-key", requested_profile)
    if error:
        return {"error": error}, 403
    return _auth_context("api-key", profile, True, "api_key_valid"), 0


# ---------------------------------------------------------------------------
# Tool-level access policy (S2: auth/profile enforcement at dispatch boundaries)
# ---------------------------------------------------------------------------

# MCP tools that mutate state and must be blocked for read-only profiles.
# Keys are harness auth profiles; values are sets of lower-cased tool names.
AUTH_PROFILE_TOOL_POLICY: dict = {
    "readonly-strict": {
        # Fine-tuning / training pipeline — writes dataset artifacts
        "generate_training_data",
        "capture_training_example",
        "flush_training_data",
        "start_finetuning_job",
        "run_distillation_pipeline",
        "generate_synthetic_training_data",
        # Memory writes
        "store_agent_memory",
        # Interaction / outcome writes
        "track_interaction",
        "update_outcome",
        "learning_feedback",
        "record_learning_signal",
        # Prompt mutation
        "optimize_prompt_template",
        "record_prompt_variant_outcome",
        # Model performance writes
        "record_model_performance",
        # Eval run (has side effects on eval store)
        "run_harness_eval",
    },
    # execute-guarded: all MCP tools permitted; restrict at higher layers (shell/git)
    "execute-guarded": set(),
    # worktree-guarded: unrestricted
    "worktree-guarded": set(),
}

# In-memory denial counter: {(tool_name, profile): count}
_tool_denial_counts: dict = {}


def check_tool_access(tool_name: str, auth_context: dict) -> tuple:
    """Return (allowed: bool, reason: str) for a given tool + auth context.

    Called at every MCP/tool dispatch boundary before executing the tool.
    ``auth_context`` is the dict stored at ``request[AUTH_CONTEXT_KEY]``.
    """
    profile = (auth_context or {}).get("profile") or "readonly-strict"
    blocked = AUTH_PROFILE_TOOL_POLICY.get(profile, AUTH_PROFILE_TOOL_POLICY["readonly-strict"])
    if tool_name.lower() in blocked:
        return False, f"tool '{tool_name}' blocked by auth profile '{profile}'"
    return True, ""


def record_tool_denial(tool_name: str, profile: str, reason: str) -> None:
    """Increment in-memory denial counter.  Cheap — no I/O on hot path."""
    key = (tool_name.lower(), profile)
    _tool_denial_counts[key] = _tool_denial_counts.get(key, 0) + 1


def get_tool_denial_stats() -> dict:
    """Return denial stats for the /admin/v1/policy/tool-deny-stats endpoint."""
    total = sum(_tool_denial_counts.values())
    by_tool: dict = {}
    by_profile: dict = {}
    breakdown = []
    for (tool, profile), count in sorted(_tool_denial_counts.items()):
        by_tool[tool] = by_tool.get(tool, 0) + count
        by_profile[profile] = by_profile.get(profile, 0) + count
        breakdown.append({"tool_name": tool, "profile": profile, "count": count})
    return {
        "total_denials": total,
        "by_tool": by_tool,
        "by_profile": by_profile,
        "breakdown": breakdown,
        "policy": {
            profile: sorted(blocked)
            for profile, blocked in AUTH_PROFILE_TOOL_POLICY.items()
        },
    }


def auth_profile_policy_summary() -> dict:
    """Return operator-facing policy metadata for dashboard/report surfaces."""
    return {
        "available": True,
        "profile_header": AUTH_PROFILE_HEADER,
        "context_key": AUTH_CONTEXT_KEY,
        "modes": AUTH_PROFILE_POLICY,
        "public_paths": sorted(PUBLIC_PATHS),
        "loopback_prefix_count": len(LOOPBACK_AGENT_PREFIXES),
        "tool_policy_profiles": sorted(AUTH_PROFILE_TOOL_POLICY.keys()),
    }


# ---------------------------------------------------------------------------
# Middleware factory
# ---------------------------------------------------------------------------


def create_api_key_middleware():
    """Return the aiohttp middleware that enforces API key authentication."""

    @web.middleware
    async def api_key_middleware(request: web.Request, handler):
        context, status = resolve_auth_context(
            request.path,
            (request.remote or "").strip(),
            request.headers,
            Config.API_KEY,
        )
        if status:
            return web.json_response(context, status=status)
        request[AUTH_CONTEXT_KEY] = context
        response = await handler(request)
        if isinstance(response, web.StreamResponse):
            response.headers.setdefault("X-Harness-Auth-Mode", context.get("mode", ""))
            response.headers.setdefault("X-Harness-Auth-Profile", context.get("profile", ""))
        return response

    return api_key_middleware
