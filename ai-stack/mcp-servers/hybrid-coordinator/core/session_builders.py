"""
Workflow session builder helpers: session field defaults, runtime-contract
construction, isolation profile resolution, and constraint checking.

Extracted from http_server.py (Phase 12.4 decomposition).
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from orchestration import IsolationMode, ToolStatus
from tooling_manifest import workflow_tool_catalog
from orchestration_utils import (
    _normalize_safety_mode,
    _default_budget,
    _default_usage,
    _seed_agent_evaluation,
    _build_orchestration_team,
)
from agent_registry import (
    _normalize_agent_role,
    _validate_intent_contract,
    _coerce_intent_contract,
)
from runtime_manager import (
    _validate_orchestration_policy,
    _load_runtime_isolation_profiles,
)
from workflow_planning import _build_workflow_plan

# ---------------------------------------------------------------------------
# Injectable singletons (set by http_server.session_builders_init())
# ---------------------------------------------------------------------------

_AGENT_HQ: Optional[Any] = None
_DELEGATION_API: Optional[Any] = None
_WORKSPACE_MANAGER: Optional[Any] = None
_MCP_TOOL_INVOKER: Optional[Any] = None


def init(
    *,
    agent_hq: Any,
    delegation_api: Any,
    workspace_manager: Any,
    mcp_tool_invoker: Any,
) -> None:
    """Inject live orchestration-framework singletons. Call once from http_server.init()."""
    global _AGENT_HQ, _DELEGATION_API, _WORKSPACE_MANAGER, _MCP_TOOL_INVOKER
    _AGENT_HQ = agent_hq
    _DELEGATION_API = delegation_api
    _WORKSPACE_MANAGER = workspace_manager
    _MCP_TOOL_INVOKER = mcp_tool_invoker


# ---------------------------------------------------------------------------
# Session field defaults
# ---------------------------------------------------------------------------

def _ensure_session_runtime_fields(session: Dict[str, Any]) -> None:
    default_mode = _normalize_safety_mode(os.getenv("AI_RUN_DEFAULT_SAFETY_MODE", "plan-readonly"))
    default_token_limit = int(os.getenv("AI_RUN_DEFAULT_TOKEN_LIMIT", "8000"))
    default_tool_call_limit = int(os.getenv("AI_RUN_DEFAULT_TOOL_CALL_LIMIT", "40"))
    session.setdefault("safety_mode", default_mode)
    session.setdefault("budget", {"token_limit": default_token_limit, "tool_call_limit": default_tool_call_limit})
    session.setdefault("usage", {"tokens_used": 0, "tool_calls_used": 0})
    session.setdefault("trajectory", [])
    session.setdefault(
        "isolation",
        {
            "profile": "",
            "workspace_root": "",
            "network_policy": "",
        },
    )
    session.setdefault(
        "reviewer_gate",
        {
            "required": False,
            "last_review": None,
            "history": [],
            "status": "not_required",
        },
    )
    policy = session.get("orchestration_policy") if isinstance(session.get("orchestration_policy"), dict) else {}
    orchestration = session.get("orchestration") if isinstance(session.get("orchestration"), dict) else {}
    session.setdefault("consensus", _seed_agent_evaluation(policy, orchestration))
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    if isinstance(consensus, dict) and not str(consensus.get("selected_role", "") or "").strip():
        selected_candidate_id = str(consensus.get("selected_candidate_id", "") or "").strip()
        candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
        selected_candidate = next(
            (
                item
                for item in candidates
                if isinstance(item, dict) and str(item.get("candidate_id", "") or "").strip() == selected_candidate_id
            ),
            {},
        )
        if selected_candidate:
            consensus["selected_role"] = str(selected_candidate.get("role", "") or "").strip()
            consensus["selected_profile"] = str(selected_candidate.get("profile", "") or "").strip()
            consensus["selected_runtime_id"] = str(selected_candidate.get("runtime_id", "") or "").strip()
            session["consensus"] = consensus
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    if not team:
        session["team"] = _build_orchestration_team(policy, orchestration, session["consensus"])
    session["orchestration_runtime"] = _build_orchestration_runtime_contract(session)


# ---------------------------------------------------------------------------
# Workflow run session builder
# ---------------------------------------------------------------------------

def _build_workflow_run_session(
    query: str,
    data: Dict[str, Any],
    selected_blueprint: Optional[Dict[str, Any]],
    orchestration: Dict[str, Any],
    lesson_refs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    incoming_contract = data.get("intent_contract")
    if incoming_contract is None and selected_blueprint:
        incoming_contract = selected_blueprint.get("intent_contract", {})
    blueprint_selection = data.get("blueprint_selection") if isinstance(data.get("blueprint_selection"), dict) else {}
    validation = _validate_intent_contract(_coerce_intent_contract(query, incoming_contract))
    orchestration_payload = dict(orchestration)
    orchestration_payload.setdefault("query", query)
    orchestration_payload.setdefault("objective", query)
    incoming_policy = data.get("orchestration_policy")
    effective_policy: Optional[Dict[str, Any]] = None
    if isinstance(selected_blueprint, dict) and isinstance(selected_blueprint.get("orchestration_policy"), dict):
        effective_policy = dict(selected_blueprint.get("orchestration_policy", {}))
    if isinstance(incoming_policy, dict):
        if effective_policy is None:
            effective_policy = {}
        effective_policy.update(incoming_policy)
    policy_validation = _validate_orchestration_policy(
        effective_policy,
        query=query,
    )
    session_id = str(uuid4())
    plan = _build_workflow_plan(query)
    now = time.time()
    phases = []
    for idx, phase in enumerate(plan.get("phases", [])):
        phases.append(
            {
                "id": phase.get("id", f"phase-{idx}"),
                "status": "in_progress" if idx == 0 else "pending",
                "started_at": now if idx == 0 else None,
                "completed_at": None,
                "notes": [],
            }
        )

    seeded_consensus = _seed_agent_evaluation(policy_validation["normalized"], orchestration_payload)
    seeded_team = _build_orchestration_team(policy_validation["normalized"], orchestration_payload, seeded_consensus)
    reasoning_pattern = (
        ((plan.get("metadata") or {}) if isinstance(plan.get("metadata"), dict) else {}).get("reasoning_pattern", {})
    )
    remote_task_contract = data.get("remote_task_contract") if isinstance(data.get("remote_task_contract"), dict) else None
    session = {
        "session_id": session_id,
        "objective": query,
        "plan": plan,
        "phase_state": phases,
        "current_phase_index": 0,
        "status": "in_progress",
        "safety_mode": _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly"))),
        "budget": _default_budget(data),
        "usage": _default_usage(),
        "blueprint_id": str(data.get("blueprint_id", "") or "").strip() or None,
        "blueprint_title": (
            str(selected_blueprint.get("title", "")).strip()
            if isinstance(selected_blueprint, dict)
            else ""
        ) or None,
        "blueprint_selection": blueprint_selection or None,
        "intent_contract": validation["normalized"],
        "remote_task_contract": remote_task_contract,
        "orchestration": orchestration_payload,
        "orchestration_policy": policy_validation["normalized"],
        "consensus": seeded_consensus,
        "team": seeded_team,
        "reasoning_pattern": reasoning_pattern,
        "reviewer_gate": {
            "required": _blueprint_requires_reviewer_gate(selected_blueprint),
            "last_review": None,
            "history": [],
            "status": "pending_review" if _blueprint_requires_reviewer_gate(selected_blueprint) else "not_required",
        },
        "isolation": {
            "profile": str(data.get("isolation_profile", "")).strip(),
            "workspace_root": str(data.get("workspace_root", "")).strip(),
            "network_policy": str(data.get("network_policy", "")).strip(),
        },
        "created_at": now,
        "updated_at": now,
        "trajectory": [
            {
                "ts": now,
                "event_type": "run_start",
                "phase_id": "discover",
                "detail": "workflow run started",
                "intent_contract_present": True,
                "requester_role": orchestration["requester_role"],
                "requested_by": orchestration["requested_by"],
                "delegate_via_coordinator_only": True,
                "reviewer_gate_required": _blueprint_requires_reviewer_gate(selected_blueprint),
                "primary_lane": policy_validation["normalized"]["primary_lane"],
                "consensus_mode": policy_validation["normalized"]["consensus_mode"],
                "arbiter_required": policy_validation["normalized"]["consensus_mode"] == "arbiter-review",
                "selected_candidate_id": seeded_consensus.get("selected_candidate_id"),
                "team_slots": seeded_team.get("active_slots", []),
                "reasoning_pattern": reasoning_pattern.get("selected_pattern", ""),
                "reasoning_pattern_boost": reasoning_pattern.get("boost_multiplier", 1.0),
                "blueprint_id": str(data.get("blueprint_id", "") or "").strip() or None,
                "blueprint_selection_mode": str(blueprint_selection.get("mode", "") or "").strip() or "unspecified",
            }
        ],
    }
    if lesson_refs:
        session["active_lesson_refs"] = lesson_refs
    return session


# ---------------------------------------------------------------------------
# History role resolver
# ---------------------------------------------------------------------------

def _resolve_history_role(
    session: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    review_type: str = "",
) -> str:
    agent_key = str(agent or "").strip()
    profile_key = str(profile or "").strip()
    if not agent_key:
        return "unknown"

    roles = set()
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    for member in team.get("members", []) if isinstance(team.get("members"), list) else []:
        if not isinstance(member, dict):
            continue
        if str(member.get("agent", "") or "").strip() == agent_key:
            role = _normalize_agent_role(member.get("slot") or member.get("role"))
            if role != "unknown":
                roles.add(role)

    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    for candidate in consensus.get("candidates", []) if isinstance(consensus.get("candidates"), list) else []:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("agent", "") or "").strip() != agent_key:
            continue
        candidate_role = _normalize_agent_role(candidate.get("role"))
        candidate_lane = str(candidate.get("lane", "") or "").strip()
        if profile_key and candidate_lane == profile_key and candidate_role != "unknown":
            return candidate_role
        if candidate_role != "unknown":
            roles.add(candidate_role)

    if len(roles) == 1:
        return next(iter(roles))

    normalized_review_type = str(review_type or "").strip().lower()
    if normalized_review_type == "plan_review" or profile_key == "remote-reasoning":
        return "escalation"
    if normalized_review_type in {"artifact_review", "patch_review", "acceptance"}:
        return "primary"
    return "unknown"


# ---------------------------------------------------------------------------
# Reviewer gate / budget helpers
# ---------------------------------------------------------------------------

def _blueprint_requires_reviewer_gate(blueprint: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(blueprint, dict):
        return False
    phases = blueprint.get("phases", [])
    if not isinstance(phases, list):
        return False
    return any(bool(item.get("requires_approval")) for item in phases if isinstance(item, dict))


def _budget_exceeded(session: Dict[str, Any]) -> Optional[str]:
    budget = session.get("budget", {})
    usage = session.get("usage", {})
    token_limit = int(budget.get("token_limit", 0))
    tool_call_limit = int(budget.get("tool_call_limit", 0))
    tokens_used = int(usage.get("tokens_used", 0))
    tool_calls_used = int(usage.get("tool_calls_used", 0))
    if token_limit > 0 and tokens_used > token_limit:
        return f"token budget exceeded: {tokens_used}>{token_limit}"
    if tool_call_limit > 0 and tool_calls_used > tool_call_limit:
        return f"tool-call budget exceeded: {tool_calls_used}>{tool_call_limit}"
    return None


# ---------------------------------------------------------------------------
# Isolation profile resolution
# ---------------------------------------------------------------------------

def _resolve_isolation_profile(session: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load_runtime_isolation_profiles()
    profiles = cfg.get("profiles", {}) if isinstance(cfg, dict) else {}
    isolation = session.get("isolation", {}) if isinstance(session.get("isolation"), dict) else {}
    profile_name = str(isolation.get("profile", "")).strip()
    if not profile_name:
        by_mode = cfg.get("default_profile_by_mode", {}) if isinstance(cfg, dict) else {}
        profile_name = str(by_mode.get(session.get("safety_mode", "plan-readonly"), "readonly-strict"))
    profile = profiles.get(profile_name, profiles.get("readonly-strict", {}))
    workspace_root = str(isolation.get("workspace_root", "")).strip() or str(profile.get("workspace_root", "/tmp/agent-runs"))
    network_policy = str(isolation.get("network_policy", "")).strip() or str(profile.get("network_policy", "none"))
    return {
        "profile_name": profile_name,
        "workspace_root": workspace_root,
        "network_policy": network_policy,
        "allow_workspace_write": bool(profile.get("allow_workspace_write", False)),
        "allowed_processes": list(profile.get("allowed_processes", [])),
    }


def _resolve_orchestration_workspace_mode(session: Dict[str, Any]) -> str:
    """Map workflow isolation state onto orchestration workspace modes."""
    isolation = _resolve_isolation_profile(session)
    workspace_root = str(isolation.get("workspace_root", "") or "").strip().lower()
    safety_mode = str(session.get("safety_mode", "plan-readonly") or "plan-readonly").strip().lower()

    if "/worktree" in workspace_root or workspace_root.endswith("/worktrees"):
        return IsolationMode.GIT_WORKTREE.value
    if safety_mode == "execute-mutating":
        return IsolationMode.COPY.value
    return IsolationMode.TEMP_DIR.value


# ---------------------------------------------------------------------------
# Orchestration runtime contract builder
# ---------------------------------------------------------------------------

def _build_orchestration_runtime_contract(session: Dict[str, Any]) -> Dict[str, Any]:
    """Expose the integrated orchestration-framework view for a workflow session."""
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    reasoning_pattern = session.get("reasoning_pattern") if isinstance(session.get("reasoning_pattern"), dict) else {}
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    resolved_profile = _resolve_isolation_profile(session)
    members = team.get("members") if isinstance(team.get("members"), list) else []
    deferred_members = team.get("deferred_members") if isinstance(team.get("deferred_members"), list) else []

    session_id = str(session.get("session_id", "") or "").strip()
    hq_session = _AGENT_HQ.get_session(session_id) if _AGENT_HQ else None
    hq_status = _AGENT_HQ.get_session_status(session_id) if (_AGENT_HQ and hq_session) else None
    delegation_status = _DELEGATION_API.get_queue_status() if _DELEGATION_API else {}
    workspace_list = _WORKSPACE_MANAGER.list_workspaces(session_id=session_id) if _WORKSPACE_MANAGER else []
    tool_report = _MCP_TOOL_INVOKER.get_usage_report() if _MCP_TOOL_INVOKER else {}

    return {
        "framework": "multi-agent-orchestration-foundation",
        "framework_status": "live",
        "agent_hq": {
            "enabled": True,
            "session_id": session_id,
            "state": hq_session.state.value if hq_session else str(session.get("status", "unknown") or "unknown").strip(),
            "checkpointing": True,
            "timeline_events": len(trajectory),
            "live_session": hq_session is not None,
            "registered_agents": len(_AGENT_HQ.global_agents) if _AGENT_HQ else 0,
            "active_sessions": len(_AGENT_HQ.sessions) if _AGENT_HQ else 0,
            "checkpoint_count": len(hq_session.checkpoints) if hq_session else 0,
            "task_summary": hq_status.get("tasks", {}) if hq_status else {},
        },
        "delegation": {
            "enabled": True,
            "selection_strategy": str(team.get("selection_strategy", "") or "").strip(),
            "consensus_mode": str(consensus.get("consensus_mode", "") or "").strip(),
            "selected_agent": str(consensus.get("selected_agent", "") or "").strip(),
            "selected_lane": str(consensus.get("selected_lane", "") or "").strip(),
            "selected_profile": str(consensus.get("selected_profile", "") or "").strip(),
            "selected_runtime_id": str(consensus.get("selected_runtime_id", "") or "").strip(),
            "active_member_count": len(members),
            "deferred_member_count": len(deferred_members),
            "queue_size": delegation_status.get("queue_size", 0),
            "pending_delegations": delegation_status.get("pending_count", 0),
            "completed_delegations": delegation_status.get("completed_count", 0),
            "registered_targets": len(delegation_status.get("agents", {})),
        },
        "workspace": {
            "enabled": True,
            "mode": _resolve_orchestration_workspace_mode(session),
            "resolved_profile": resolved_profile,
            "network_policy": str(resolved_profile.get("network_policy", "") or "").strip(),
            "active_workspaces": len(workspace_list),
            "total_workspaces": len(_WORKSPACE_MANAGER.workspaces) if _WORKSPACE_MANAGER else 0,
        },
        "tool_invocation": {
            "enabled": True,
            "catalog_size": len(workflow_tool_catalog("") or []),
            "status": ToolStatus.AVAILABLE.value,
            "cache_enabled": True,
            "reasoning_pattern": str(reasoning_pattern.get("selected_pattern", "") or "").strip(),
            "registered_tools": tool_report.get("tools_registered", 0),
            "total_invocations": tool_report.get("analytics", {}).get("total_invocations", 0),
            "pending_approvals": tool_report.get("pending_approvals", 0),
        },
    }


# ---------------------------------------------------------------------------
# Isolation constraint checker
# ---------------------------------------------------------------------------

def _check_isolation_constraints(session: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
    isolation = _resolve_isolation_profile(session)
    exec_meta = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    workspace_path = str(exec_meta.get("workspace_path", "")).strip()
    process_exec = str(exec_meta.get("process_exec", "")).strip()
    requested_network = str(exec_meta.get("network_access", "")).strip().lower()

    if workspace_path:
        root = os.path.abspath(isolation["workspace_root"])
        wp = os.path.abspath(workspace_path)
        if not (wp == root or wp.startswith(root.rstrip("/") + "/")):
            return f"workspace path outside isolation root: {workspace_path}"

    if process_exec:
        exe_name = os.path.basename(process_exec)
        allowed = set(isolation.get("allowed_processes", []))
        if allowed and exe_name not in allowed:
            return f"process not allowed by isolation profile: {exe_name}"

    if requested_network:
        policy = isolation.get("network_policy", "none")
        order = {"none": 0, "loopback": 1, "egress": 2}
        if order.get(requested_network, 99) > order.get(policy, 0):
            return f"network access '{requested_network}' exceeds policy '{policy}'"

    return None
