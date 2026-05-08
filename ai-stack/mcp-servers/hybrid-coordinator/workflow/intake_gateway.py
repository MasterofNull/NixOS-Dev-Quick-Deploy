"""
Universal Agent Gateway (UAG) — Phase 26: Unified Agent Orchestration Gateway.

Single HTTP entry point for ALL user-initiated prompts regardless of client:
  Continue, Codex extension, Claude extension, raw API, future clients.

Routes:
  POST /agent/intake                       — submit a prompt, start lifecycle session
  GET  /agent/lifecycle                    — list recent sessions
  GET  /agent/lifecycle/{session_id}       — get session state
  POST /agent/lifecycle/{session_id}/advance — manually advance a phase
  POST /agent/lifecycle/{session_id}/abort — abort a session
  GET  /agent/registry                     — current agent capability registry
  GET  /agent/domains                      — domain router catalog

Caller normalization reads HTTP headers to identify the source client without
hardcoding any client names or subscription identifiers. New clients become
first-class participants by adding a recognizable X-AI-Profile or User-Agent.

Context pruning: at each phase boundary, only relevant structured outputs are
carried forward. Sub-agents receive a focused context slice, not raw tool history.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aiohttp import web

import agent_capability_registry
import domain_router
import lifecycle_fsm
from lifecycle_fsm import LifecyclePhase, detect_complexity

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module globals (injected via init())
# ---------------------------------------------------------------------------

_lifecycle_dir: Optional[Path] = None
_hints_url: str = "http://127.0.0.1:8003"
_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None


def init(
    *,
    lifecycle_dir: Path,
    switchboard_url: Optional[str] = None,
    cli_bridge_url: Optional[str] = None,
    hints_url: Optional[str] = None,
    error_payload_fn: Optional[Callable[[str, Exception], Dict[str, Any]]] = None,
) -> None:
    global _lifecycle_dir, _hints_url, _error_payload
    _lifecycle_dir = lifecycle_dir
    _hints_url = hints_url or os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")
    _error_payload = error_payload_fn

    lifecycle_fsm.init(lifecycle_dir)
    agent_capability_registry.init(
        switchboard_url=switchboard_url,
        cli_bridge_url=cli_bridge_url,
    )


# ---------------------------------------------------------------------------
# Caller normalization — no hardcoded client names
# ---------------------------------------------------------------------------

_PROFILE_SOURCE_MAP = [
    # (header_fragment, normalized_source)
    ("continue",           "continue"),
    ("codex",              "codex-ext"),
    ("claude",             "claude-ext"),
    ("local-agent",        "local-agent"),
    ("embedded-assist",    "embedded-assist"),
    ("remote-reasoning",   "remote-reasoning"),
    ("remote-coding",      "remote-coding"),
]

_USERAGENT_SOURCE_MAP = [
    ("continue",  "continue"),
    ("codex",     "codex-ext"),
    ("claude",    "claude-ext"),
    ("cursor",    "cursor"),
]


def _normalize_caller(request: web.Request) -> str:
    """Identify the calling client from request headers without hardcoding IDs.

    Priority order:
      1. X-Caller-Id header (explicit client identifier)
      2. X-AI-Profile header (switchboard profile name)
      3. User-Agent substring matching
      4. "raw-api" fallback
    """
    caller_id = request.headers.get("X-Caller-Id", "").strip().lower()
    if caller_id:
        return caller_id

    ai_profile = request.headers.get("X-AI-Profile", "").strip().lower()
    for fragment, source in _PROFILE_SOURCE_MAP:
        if fragment in ai_profile:
            return source
    if ai_profile:
        return f"profile:{ai_profile}"

    user_agent = request.headers.get("User-Agent", "").strip().lower()
    for fragment, source in _USERAGENT_SOURCE_MAP:
        if fragment in user_agent:
            return source

    return "raw-api"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_intake(request: web.Request) -> web.Response:
    """POST /agent/intake

    Body (JSON):
      prompt        — required, the user's task description
      complexity    — optional: simple|standard|complex (auto-detected if omitted)
      domain        — optional: nixos|python|security|trading|design|infra|general
      entry_phase   — optional: start at a specific lifecycle phase
      context       — optional: additional context dict (e.g., {file_path, selection})

    Returns:
      session_id, current_phase, sequence, next_action, routing_preview
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return web.json_response({"error": "prompt is required"}, status=400)

    caller = _normalize_caller(request)
    complexity = body.get("complexity") or detect_complexity(prompt)
    domain_hint = body.get("domain")
    entry_phase = body.get("entry_phase")
    extra_context = body.get("context") or {}

    # Auto-classify domain if not provided
    if not domain_hint:
        domain_hint = domain_router.classify_domain(prompt, context=extra_context)

    session = lifecycle_fsm.create_session(
        caller=caller,
        prompt=prompt,
        complexity=complexity,
        domain=domain_hint,
        entry_phase=entry_phase,
    )

    # Merge extra context (e.g., open file, selection) into the session
    if extra_context:
        session.context.update(extra_context)

    # Get routing preview for the classified domain
    routing = domain_router.route(prompt, context=session.context)

    # Refresh agent registry asynchronously (non-blocking)
    import asyncio
    asyncio.create_task(agent_capability_registry.refresh())

    return web.json_response({
        "session_id": session.session_id,
        "caller": caller,
        "current_phase": session.current_phase,
        "sequence": session.sequence,
        "complexity": complexity,
        "domain": domain_hint,
        "routing_preview": routing,
        "next_action": _next_action_guidance(session.current_phase, domain_hint),
        "pruned_context": session.pruned_context_for_current_phase(),
    })


async def handle_list_sessions(request: web.Request) -> web.Response:
    """GET /agent/lifecycle"""
    limit = int(request.rel_url.query.get("limit", "20"))
    sessions = lifecycle_fsm.list_sessions(limit=limit)
    return web.json_response({"sessions": sessions, "count": len(sessions)})


async def handle_get_session(request: web.Request) -> web.Response:
    """GET /agent/lifecycle/{session_id}"""
    session_id = request.match_info["session_id"]
    session = lifecycle_fsm.get_session(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    return web.json_response({
        "session_id": session.session_id,
        "caller": session.caller,
        "current_phase": session.current_phase,
        "sequence": session.sequence,
        "complexity": session.complexity,
        "domain": session.domain,
        "phases": session.phase_summary(),
        "is_terminal": lifecycle_fsm.is_terminal(session),
        "pruned_context": session.pruned_context_for_current_phase(),
        "delegations": session.delegations[-5:],  # last 5 only
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    })


async def handle_advance_phase(request: web.Request) -> web.Response:
    """POST /agent/lifecycle/{session_id}/advance

    Body (JSON):
      status            — passed | failed | skipped
      output_summary    — short summary of phase outcome (required, not raw tool output)
      tools_used        — list of tool names invoked
      context_updates   — structured key outputs ONLY (not full tool history)
      error             — error message if status=failed
    """
    session_id = request.match_info["session_id"]
    session = lifecycle_fsm.get_session(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    if lifecycle_fsm.is_terminal(session):
        return web.json_response({"error": "session is already in terminal state"}, status=400)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    status = body.get("status", "passed")
    output_summary = body.get("output_summary", "")
    tools_used = body.get("tools_used", [])
    context_updates = body.get("context_updates") or {}
    error = body.get("error")

    current_phase = session.current_phase
    session = lifecycle_fsm.complete_phase(
        session,
        current_phase,
        status=status,
        output_summary=output_summary,
        tools_used=tools_used,
        context_updates=context_updates,
        error=error,
    )

    return web.json_response({
        "session_id": session.session_id,
        "previous_phase": current_phase,
        "current_phase": session.current_phase,
        "is_terminal": lifecycle_fsm.is_terminal(session),
        "phases": session.phase_summary(),
        "pruned_context": session.pruned_context_for_current_phase(),
        "next_action": _next_action_guidance(session.current_phase, session.domain),
    })


async def handle_abort_session(request: web.Request) -> web.Response:
    """POST /agent/lifecycle/{session_id}/abort"""
    session_id = request.match_info["session_id"]
    session = lifecycle_fsm.get_session(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = body.get("reason", "user-cancelled")

    session = lifecycle_fsm.abort_session(session, reason)
    return web.json_response({
        "session_id": session.session_id,
        "current_phase": session.current_phase,
        "abort_reason": reason,
    })


async def handle_agent_registry(request: web.Request) -> web.Response:
    """GET /agent/registry — current agent capability registry."""
    force = request.rel_url.query.get("refresh") == "true"
    if force:
        import asyncio
        await agent_capability_registry.refresh(force=True)
    return web.json_response(agent_capability_registry.describe())


async def handle_domain_catalog(request: web.Request) -> web.Response:
    """GET /agent/domains — domain router catalog."""
    return web.json_response(domain_router.describe())


# ---------------------------------------------------------------------------
# Next-action guidance (no model names — just phase instructions)
# ---------------------------------------------------------------------------

_PHASE_GUIDANCE: Dict[str, str] = {
    "intake":   "Phase INTAKE complete. Proceed to system discovery: run `aq-qa 0` and search for existing plans.",
    "discover": "Phase DISCOVER complete. Summarize findings as codebase_summary and existing_plans, then advance.",
    "prd":      "Phase PRD complete. Confirm prd_scope and acceptance_checks are set, then advance to PLAN.",
    "plan":     "Phase PLAN complete. Review phases[] and tool_assignments, then advance to ASSIGN.",
    "assign":   "Phase ASSIGN complete. agent_assignments confirmed — begin domain-delegated execution in DELEGATE.",
    "delegate": "Phase DELEGATE complete. Record sub_agent_summaries and artifacts_created, then advance to VALIDATE.",
    "validate": "Phase VALIDATE complete. Run `aq-qa 0` and `scripts/governance/tier0-validation-gate.sh --pre-commit`.",
    "commit":   "Phase COMMIT complete. Record commit_sha and files_changed, then advance to DONE.",
    "done":     "Session DONE. All phases complete.",
    "aborted":  "Session ABORTED. Review abort_reason and restart if needed.",
}


def _next_action_guidance(phase: str, domain: Optional[str]) -> str:
    base = _PHASE_GUIDANCE.get(phase, f"Phase {phase}: proceed to next step.")
    if domain and phase == "assign":
        team = domain_router.get_team(domain)
        base += f" Domain={domain}: {team.workflow_hint}"
    return base


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/agent/intake",                           handle_intake)
    http_app.router.add_get("/agent/lifecycle",                         handle_list_sessions)
    http_app.router.add_get("/agent/lifecycle/{session_id}",            handle_get_session)
    http_app.router.add_post("/agent/lifecycle/{session_id}/advance",   handle_advance_phase)
    http_app.router.add_post("/agent/lifecycle/{session_id}/abort",     handle_abort_session)
    http_app.router.add_get("/agent/registry",                          handle_agent_registry)
    http_app.router.add_get("/agent/domains",                           handle_domain_catalog)
