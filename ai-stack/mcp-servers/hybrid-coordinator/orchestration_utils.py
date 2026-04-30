"""
Orchestration utilities: response compaction, evaluation seeding, team building,
and consensus/arbiter update logic.

Extracted from http_server.py (Phase 12.4 decomposition).

Contains compact response formatters, evaluation history bias calculation,
orchestration lane routing, agent team building, and consensus/arbiter updates.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Set


from agent_registry import _load_agent_evaluations_registry_sync, _normalize_orchestration_lane_list, _normalize_orchestration_lane_list

logger = logging.getLogger("hybrid-coordinator")

_ORCHESTRATION_ESCALATION_LANES: Set[str] = {"remote-reasoning", "flagship-remote", "none"}

def _compact_prompt_coaching_metadata(prompt_coaching: Dict[str, Any]) -> Dict[str, Any]:
    """Avoid repeating the full coaching payload inside metadata."""
    if not isinstance(prompt_coaching, dict) or not prompt_coaching:
        return {}
    missing_fields = [
        str(item).strip() for item in (prompt_coaching.get("missing_fields", []) or []) if str(item).strip()
    ]
    token_discipline = prompt_coaching.get("token_discipline", {})
    if not isinstance(token_discipline, dict):
        token_discipline = {}
    return {
        "score": float(prompt_coaching.get("score", 0.0) or 0.0),
        "recommended_agent": str(prompt_coaching.get("recommended_agent", "codex") or "codex"),
        "missing_fields": missing_fields[:3],
        "missing_count": len(missing_fields),
        "token_plan": {
            "spend_tier": str(token_discipline.get("spend_tier", "lean") or "lean"),
            "recommended_input_budget": int(token_discipline.get("recommended_input_budget", 0) or 0),
        },
    }


def _query_prompt_coaching_response(
    prompt_coaching: Dict[str, Any],
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    """Return compact prompt coaching by default and preserve deep detail only on opt-in."""
    compact = _compact_prompt_coaching_metadata(prompt_coaching)
    if not include_debug_metadata:
        suggested_prompt = str(prompt_coaching.get("suggested_prompt", "") or "").strip()
        if suggested_prompt:
            compact["suggested_prompt"] = suggested_prompt
        return compact
    enriched = dict(prompt_coaching)
    enriched["summary"] = compact
    return enriched


def _compact_tooling_layer_response(
    tooling_layer: Dict[str, Any],
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    """Keep normal query tooling metadata compact and operational."""
    planned_tools = list(tooling_layer.get("planned_tools", []) or [])
    executed_tools = list(tooling_layer.get("executed", []) or [])
    hints = list(tooling_layer.get("hints", []) or [])
    tool_security = tooling_layer.get("tool_security", {})
    if not isinstance(tool_security, dict):
        tool_security = {}
    compact = {
        "enabled": bool(tooling_layer.get("enabled", False)),
        "planned_tools": planned_tools[:3],
        "planned_count": len(planned_tools),
        "planned_more": max(0, len(planned_tools) - 3),
        "executed": executed_tools[:3],
        "executed_count": len(executed_tools),
        "executed_more": max(0, len(executed_tools) - 3),
        "hints_count": len(hints),
        "tool_security": {
            "blocked_count": len(tool_security.get("blocked", []) or []),
            "cache_hits": int(tool_security.get("cache_hits", 0) or 0),
            "first_seen": int(tool_security.get("first_seen", 0) or 0),
        },
    }
    if include_debug_metadata:
        enriched = dict(tooling_layer)
        enriched["summary"] = compact
        return enriched
    return compact


def _compact_tool_security(tool_security: Dict[str, Any]) -> Dict[str, Any]:
    """Keep tool-security state compact on default metadata surfaces."""
    if not isinstance(tool_security, dict):
        tool_security = {}
    return {
        "enabled": bool(tool_security.get("enabled", False)),
        "approved_count": len(tool_security.get("approved", []) or []),
        "blocked_count": len(tool_security.get("blocked", []) or []),
        "cache_hits": int(tool_security.get("cache_hits", 0) or 0),
        "first_seen": int(tool_security.get("first_seen", 0) or 0),
    }


def _compact_workflow_tool_catalog(tool_catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Keep workflow-plan tool metadata compact by default."""
    compact: Dict[str, Any] = {}
    if not isinstance(tool_catalog, dict):
        return compact
    for name, payload in tool_catalog.items():
        if not isinstance(payload, dict):
            continue
        tool_name = str(payload.get("name", "") or name).strip()
        if not tool_name:
            continue
        compact[tool_name] = {
            "endpoint": str(payload.get("endpoint", "") or "").strip(),
        }
    return compact


def _phase_tool_names(phase: Dict[str, Any]) -> List[str]:
    """Accept compact plan tool names and legacy tool dicts."""
    names: List[str] = []
    for tool in phase.get("tools", []):
        if isinstance(tool, str):
            name = tool.strip()
        elif isinstance(tool, dict):
            name = str(tool.get("name", "")).strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _session_lineage(sessions: Dict[str, Any], session_id: str) -> List[str]:
    """Return root->...->session lineage for a session id."""
    lineage: List[str] = []
    seen = set()
    current = session_id
    while current and current not in seen and current in sessions:
        seen.add(current)
        lineage.append(current)
        parent = (
            sessions.get(current, {})
            .get("fork", {})
            .get("from_session_id")
        )
        current = parent if isinstance(parent, str) else ""
    lineage.reverse()
    return lineage


def _normalize_safety_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"plan-readonly", "plan_readonly", "readonly"}:
        return "plan-readonly"
    if mode in {"execute-mutating", "execute_mutating", "execute"}:
        return "execute-mutating"
    return "plan-readonly"


def _default_budget(data: Dict[str, Any]) -> Dict[str, int]:
    env_token_limit = int(os.getenv("AI_RUN_DEFAULT_TOKEN_LIMIT", "8000"))
    env_tool_call_limit = int(os.getenv("AI_RUN_DEFAULT_TOOL_CALL_LIMIT", "40"))
    token_limit_raw = data.get("token_limit", env_token_limit)
    tool_call_limit_raw = data.get("tool_call_limit", env_tool_call_limit)
    return {
        "token_limit": int(env_token_limit if token_limit_raw in (None, "") else token_limit_raw),
        "tool_call_limit": int(env_tool_call_limit if tool_call_limit_raw in (None, "") else tool_call_limit_raw),
    }


def _default_usage() -> Dict[str, int]:
    return {"tokens_used": 0, "tool_calls_used": 0}


def _evaluation_history_bias(registry: Dict[str, Any], agent: str, profile: str, role: str) -> Dict[str, float]:
    agents = registry.get("agents") if isinstance(registry, dict) else {}
    if not isinstance(agents, dict):
        return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
    agent_row = agents.get(str(agent or "").strip())
    if not isinstance(agent_row, dict):
        return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
    profiles = agent_row.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    profile_row = profiles.get(str(profile or "").strip())
    if not isinstance(profile_row, dict):
        profile_row = {}
    roles = agent_row.get("roles")
    if not isinstance(roles, dict):
        roles = {}
    role_row = roles.get(_normalize_agent_role(role))
    if not isinstance(role_row, dict):
        role_row = {}

    def _bounded_score(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0

    def _bounded_count(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _weighted_component(avg_score: float, count: int, divisor: float) -> float:
        weight = min(1.0, count / divisor) if divisor > 0 else 0.0
        return avg_score * weight

    def _recent_agent_event_bias() -> Dict[str, float]:
        events = registry.get("recent_events") if isinstance(registry, dict) else []
        if not isinstance(events, list):
            return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
        agent_key = str(agent or "").strip()
        profile_key = str(profile or "").strip()
        role_key = _normalize_agent_role(role)
        review_scores: List[float] = []
        runtime_scores: List[float] = []
        selection_events = 0
        scoped_events = 0
        agent_events = 0
        for item in events[-18:]:
            if not isinstance(item, dict):
                continue
            if str(item.get("agent", "") or "").strip() != agent_key:
                continue
            agent_events += 1
            profile_match = str(item.get("profile", "") or "").strip() == profile_key
            role_match = _normalize_agent_role(item.get("role")) == role_key
            if not profile_match and not role_match:
                continue
            scoped_events += 1
            event_type = str(item.get("event_type", "") or "").strip().lower()
            if event_type == "review":
                review_scores.append(_bounded_score(item.get("score", 0.0)))
            elif event_type == "runtime":
                runtime_scores.append(_bounded_score(item.get("runtime_score", 0.0)))
            elif event_type == "consensus":
                selection_events += 1
        recency_weight = min(1.0, scoped_events / 5.0) if scoped_events > 0 else min(0.5, agent_events / 10.0)
        review_score = (sum(review_scores) / len(review_scores)) if review_scores else 0.0
        runtime_score = (sum(runtime_scores) / len(runtime_scores)) if runtime_scores else 0.0
        selection_score = min(1.0, selection_events / 3.0)
        return {
            "review_score": round(review_score * recency_weight, 4),
            "selection_score": round(selection_score * recency_weight, 4),
            "runtime_score": round(runtime_score * recency_weight, 4),
        }

    review_events = _bounded_count(profile_row.get("review_events", 0))
    avg_review_score = _bounded_score(profile_row.get("average_review_score", 0.0))
    consensus_selected = _bounded_count(profile_row.get("consensus_selected", 0))
    runtime_events = _bounded_count(profile_row.get("runtime_events", 0))
    avg_runtime_score = _bounded_score(profile_row.get("average_runtime_score", 0.0))
    role_review_events = _bounded_count(role_row.get("review_events", 0))
    role_avg_review_score = _bounded_score(role_row.get("average_review_score", 0.0))
    role_consensus_selected = _bounded_count(role_row.get("consensus_selected", 0))
    role_runtime_events = _bounded_count(role_row.get("runtime_events", 0))
    role_avg_runtime_score = _bounded_score(role_row.get("average_runtime_score", 0.0))

    totals = agent_row.get("totals") if isinstance(agent_row.get("totals"), dict) else {}
    total_review_events = _bounded_count(totals.get("review_events", 0))
    total_runtime_events = _bounded_count(totals.get("runtime_events", 0))
    total_consensus_selected = _bounded_count(totals.get("consensus_selected", 0))
    total_avg_review_score = _bounded_score(totals.get("average_review_score", 0.0))
    total_avg_runtime_score = _bounded_score(totals.get("average_runtime_score", 0.0))
    recent_bias = _recent_agent_event_bias()

    review_component = (
        (0.40 * _weighted_component(avg_review_score, review_events, 5.0))
        + (0.20 * _weighted_component(role_avg_review_score, role_review_events, 8.0))
        + (0.20 * _weighted_component(total_avg_review_score, total_review_events, 12.0))
        + (0.20 * recent_bias["review_score"])
    )
    selection_component = (
        (0.45 * min(1.0, consensus_selected / 5.0))
        + (0.20 * min(1.0, role_consensus_selected / 6.0))
        + (0.15 * min(1.0, total_consensus_selected / 8.0))
        + (0.20 * recent_bias["selection_score"])
    )
    runtime_component = (
        (0.40 * _weighted_component(avg_runtime_score, runtime_events, 6.0))
        + (0.25 * _weighted_component(role_avg_runtime_score, role_runtime_events, 8.0))
        + (0.15 * _weighted_component(total_avg_runtime_score, total_runtime_events, 12.0))
        + (0.20 * recent_bias["runtime_score"])
    )
    return {
        "review_score": round(review_component, 4),
        "selection_score": round(selection_component, 4),
        "runtime_score": round(runtime_component, 4),
    }


def _agent_for_orchestration_lane(lane: str, requested_by: str, role: str) -> str:
    normalized_lane = str(lane or "").strip().lower()
    normalized_role = _normalize_agent_role(role)
    if normalized_role == "reviewer":
        return "codex"
    if normalized_lane == "research":
        return "gemini"
    if normalized_lane == "reasoning" or normalized_lane in _ORCHESTRATION_ESCALATION_LANES:
        return "remote"
    return requested_by


def _profile_for_orchestration_lane(lane: str, role: str, objective: str) -> str:
    normalized_lane = str(lane or "").strip().lower()
    normalized_role = _normalize_agent_role(role)
    local_handoff = _orchestration_prefers_local_handoff(objective)
    if normalized_lane == "research":
        return "remote-gemini"
    if normalized_lane == "reasoning" or normalized_lane in _ORCHESTRATION_ESCALATION_LANES:
        return "remote-reasoning"
    if normalized_lane == "diagnostics":
        return "local-tool-calling" if local_handoff or normalized_role == "collaborator" else "default"
    if normalized_lane in {"implementation", "hardening", "operations", "self-improvement"}:
        if local_handoff and normalized_role == "collaborator":
            return "local-tool-calling"
        return "remote-coding" if normalized_role == "orchestrator" else "default"
    return "default"


def _seed_agent_evaluation(policy: Dict[str, Any], orchestration: Dict[str, Any]) -> Dict[str, Any]:
    strategy = str(policy.get("selection_strategy", "orchestrator-first") or "orchestrator-first").strip()
    consensus_mode = str(policy.get("consensus_mode", "reviewer-gate") or "reviewer-gate").strip()
    requested_by = str(orchestration.get("requested_by", "human") or "human").strip() or "human"
    requester_role = str(orchestration.get("requester_role", "orchestrator") or "orchestrator").strip() or "orchestrator"
    objective = str(orchestration.get("objective") or orchestration.get("query") or "").strip()
    evaluation_registry = _load_agent_evaluations_registry_sync()

    candidates: List[Dict[str, Any]] = []

    def _add_candidate(candidate_id: str, lane: str, agent: str, role: str, components: Dict[str, float], basis: str) -> None:
        profile = _profile_for_orchestration_lane(lane, role, objective)
        history = _evaluation_history_bias(evaluation_registry, agent, profile, role)
        components = dict(components)
        components["historical_review"] = history["review_score"]
        components["historical_selection"] = history["selection_score"]
        components["historical_runtime_quality"] = history["runtime_score"]
        score = round(sum(float(value) for value in components.values()), 4)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "lane": lane,
                "agent": agent,
                "role": role,
                "profile": profile,
                "runtime_id": _ai_coordinator_default_runtime_id_for_profile(profile),
                "basis": basis,
                "score": score,
                "score_components": {key: round(float(value), 4) for key, value in components.items()},
                "history_bias": history,
            }
        )

    primary_lane = str(policy.get("primary_lane", "implementation") or "implementation").strip()
    reviewer_lane = str(policy.get("reviewer_lane", "codex-review") or "codex-review").strip()
    escalation_lane = str(policy.get("escalation_lane", "remote-reasoning") or "remote-reasoning").strip()
    collaborator_lanes = _normalize_orchestration_lane_list(policy.get("collaborator_lanes", []))

    base_requester_score = 0.4 if requester_role == "orchestrator" else 0.25
    _add_candidate(
        "primary",
        primary_lane,
        _agent_for_orchestration_lane(primary_lane, requested_by, requester_role),
        requester_role,
        {
            "strategy_fit": 0.4,
            "locality": 0.25 if strategy in {"local-first", "orchestrator-first"} else 0.15,
            "review_alignment": 0.15 if consensus_mode == "reviewer-gate" else 0.1,
            "requester_bias": base_requester_score,
        },
        "session requester aligned to primary lane",
    )
    _add_candidate(
        "reviewer",
        reviewer_lane,
        _agent_for_orchestration_lane(reviewer_lane, requested_by, "reviewer"),
        "reviewer",
        {
            "strategy_fit": 0.2,
            "locality": 0.2,
            "review_alignment": 0.45,
            "requester_bias": 0.05,
        },
        "reviewer gate candidate",
    )
    if escalation_lane != "none":
        remote_weight = 0.45 if strategy == "escalate-on-complexity" else 0.2
        _add_candidate(
            "escalation",
            escalation_lane,
            _agent_for_orchestration_lane(escalation_lane, requested_by, "escalation"),
            "escalation",
            {
                "strategy_fit": remote_weight,
                "locality": 0.05,
                "review_alignment": 0.15 if consensus_mode == "arbiter-review" else 0.1,
                "requester_bias": 0.05,
            },
            "escalation lane candidate",
        )
    for idx, lane in enumerate(collaborator_lanes, start=1):
        collaborator_agent = _agent_for_orchestration_lane(lane, requested_by, "collaborator")
        collaborator_locality = 0.05 if lane in _ORCHESTRATION_ESCALATION_LANES else 0.2
        collaborator_strategy_fit = 0.25 if strategy in {"evidence-first", "escalate-on-complexity"} else 0.18
        _add_candidate(
            f"collaborator-{idx}",
            lane,
            collaborator_agent,
            "collaborator",
            {
                "strategy_fit": collaborator_strategy_fit,
                "locality": collaborator_locality,
                "review_alignment": 0.12,
                "requester_bias": 0.04,
            },
            f"parallel collaborator lane candidate ({lane})",
        )

    candidates.sort(key=lambda item: (float(item.get("score", 0.0)), item.get("candidate_id", "")), reverse=True)
    selected = candidates[0] if candidates else {}
    arbiter_candidate = next((item for item in candidates if item.get("candidate_id") == "reviewer"), selected)
    arbiter_state: Dict[str, Any] = {}
    if consensus_mode == "arbiter-review":
        arbiter_state = {
            "required": True,
            "status": "pending",
            "arbiter": str((arbiter_candidate or {}).get("agent", "") or "codex"),
            "arbiter_lane": str((arbiter_candidate or {}).get("lane", "") or "codex-review"),
            "selected_candidate_id": None,
            "selected_lane": None,
            "selected_agent": None,
            "last_decision": None,
            "history": [],
        }
    return {
        "selection_strategy": strategy,
        "consensus_mode": consensus_mode,
        "status": "pending",
        "selected_candidate_id": selected.get("candidate_id"),
        "selected_lane": selected.get("lane"),
        "selected_agent": selected.get("agent"),
        "selected_role": selected.get("role"),
        "selected_profile": selected.get("profile"),
        "selected_runtime_id": selected.get("runtime_id"),
        "candidates": candidates,
        "history": [],
        "arbiter": arbiter_state,
    }


def _build_orchestration_team(
    policy: Dict[str, Any],
    orchestration: Dict[str, Any],
    consensus: Dict[str, Any],
) -> Dict[str, Any]:
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    selected_candidate_id = str(consensus.get("selected_candidate_id", "") or "").strip()
    primary_candidate = by_id.get(selected_candidate_id) or next(iter(by_id.values()), {})
    reviewer_candidate = by_id.get("reviewer") or {}
    escalation_candidate = by_id.get("escalation") or {}
    collaborator_candidates = [
        candidate
        for candidate_id, candidate in by_id.items()
        if candidate_id.startswith("collaborator-")
    ]
    requested_by = str(orchestration.get("requested_by", "human") or "human").strip() or "human"
    requester_role = str(orchestration.get("requester_role", "orchestrator") or "orchestrator").strip() or "orchestrator"
    allow_parallel = bool(policy.get("allow_parallel_subagents", False))
    max_parallel = max(1, int(policy.get("max_parallel_subagents", 1) or 1))
    selection_strategy = str(policy.get("selection_strategy", "orchestrator-first") or "orchestrator-first").strip()
    consensus_mode = str(consensus.get("consensus_mode", policy.get("consensus_mode", "reviewer-gate")) or "reviewer-gate").strip()

    team_members: List[Dict[str, Any]] = []

    def _append_member(candidate: Dict[str, Any], slot: str, required: bool, activation_reason: str) -> None:
        if not candidate:
            return
        team_members.append(
            {
                "slot": slot,
                "candidate_id": str(candidate.get("candidate_id", "") or "").strip(),
                "lane": str(candidate.get("lane", "") or "").strip(),
                "agent": str(candidate.get("agent", "") or "").strip(),
                "role": str(candidate.get("role", "") or "").strip(),
                "profile": str(candidate.get("profile", "") or "").strip(),
                "runtime_id": str(candidate.get("runtime_id", "") or "").strip(),
                "score": round(float(candidate.get("score", 0.0) or 0.0), 4),
                "required": required,
                "activation_reason": activation_reason,
            }
        )

    _append_member(primary_candidate, "primary", True, "highest-ranked primary execution candidate")
    _append_member(reviewer_candidate, "reviewer", True, "reviewer gate coverage")

    if escalation_candidate and (
        allow_parallel or selection_strategy == "escalate-on-complexity" or consensus_mode == "arbiter-review"
    ):
        _append_member(
            escalation_candidate,
            "escalation",
            consensus_mode == "arbiter-review" or selection_strategy == "escalate-on-complexity",
            "escalation lane reserved for complex or arbitrated tasks",
        )
    if allow_parallel and collaborator_candidates:
        for candidate in collaborator_candidates:
            lane = str(candidate.get("lane", "") or "").strip() or "unknown"
            _append_member(
                candidate,
                f"collaborator:{lane}",
                False,
                f"parallel collaborator lane activated for {lane}",
            )

    # Keep deterministic bounded team size while allowing limited multi-role composition.
    unique_members: List[Dict[str, Any]] = []
    seen_slots = set()
    for member in team_members:
        slot = str(member.get("slot", "") or "")
        if not slot or slot in seen_slots:
            continue
        seen_slots.add(slot)
        unique_members.append(member)
    required_members = [member for member in unique_members if bool(member.get("required"))]
    optional_members = [member for member in unique_members if not bool(member.get("required"))]
    optional_budget = max(0, max_parallel - 1)
    active_members = required_members + optional_members[:optional_budget]
    deferred_members = optional_members[optional_budget:]
    active_slots = [str(member.get("slot", "") or "") for member in active_members]
    deferred_slots = [str(member.get("slot", "") or "") for member in deferred_members]
    required_slots = [str(member.get("slot", "") or "") for member in required_members]
    return {
        "requested_by": requested_by,
        "requester_role": requester_role,
        "formation_mode": "dynamic-role-assignment",
        "selection_strategy": selection_strategy,
        "consensus_mode": consensus_mode,
        "allow_parallel_subagents": allow_parallel,
        "max_parallel_subagents": max_parallel,
        "required_slots": required_slots,
        "optional_slot_capacity": optional_budget,
        "active_slots": active_slots,
        "deferred_slots": deferred_slots,
        "members": active_members,
        "deferred_members": deferred_members,
    }


def _normalize_consensus_decisions(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "") or "").strip()
        reviewer = str(item.get("reviewer", "") or "").strip()[:64]
        verdict = str(item.get("verdict", "") or "").strip().lower()
        rationale = str(item.get("rationale", "") or "").strip()[:400]
        if not candidate_id or not reviewer or verdict not in {"accept", "reject", "prefer"}:
            continue
        normalized.append(
            {
                "candidate_id": candidate_id,
                "reviewer": reviewer,
                "verdict": verdict,
                "rationale": rationale,
            }
        )
    return normalized


def _apply_consensus_update(
    session: Dict[str, Any],
    *,
    selected_candidate_id: str,
    decisions: List[Dict[str, Any]],
    summary: str,
) -> Dict[str, Any]:
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    if selected_candidate_id not in by_id:
        raise ValueError("selected_candidate_id must match an existing consensus candidate")

    normalized_decisions = _normalize_consensus_decisions(decisions)
    if not normalized_decisions:
        raise ValueError("decisions must contain at least one valid reviewer decision")

    now = int(time.time())
    selected_candidate = by_id[selected_candidate_id]
    accept_count = len([item for item in normalized_decisions if item.get("verdict") in {"accept", "prefer"}])
    reject_count = len([item for item in normalized_decisions if item.get("verdict") == "reject"])
    consensus["status"] = "accepted" if accept_count >= reject_count else "rejected"
    consensus["selected_candidate_id"] = selected_candidate_id
    consensus["selected_lane"] = selected_candidate.get("lane")
    consensus["selected_agent"] = selected_candidate.get("agent")
    consensus["selected_role"] = selected_candidate.get("role")
    consensus["selected_profile"] = selected_candidate.get("profile")
    consensus["selected_runtime_id"] = selected_candidate.get("runtime_id")
    history = consensus.get("history") if isinstance(consensus.get("history"), list) else []
    history.append(
        {
            "ts": now,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "summary": summary,
            "decisions": normalized_decisions,
        }
    )
    consensus["history"] = history[-10:]
    session["consensus"] = consensus
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    trajectory.append(
        {
            "ts": now,
            "event_type": "consensus_update",
            "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
            "detail": f"consensus -> {consensus['status']} ({selected_candidate_id})",
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "decision_count": len(normalized_decisions),
        }
    )
    session["trajectory"] = trajectory
    session["updated_at"] = now
    return consensus


def _apply_arbiter_update(
    session: Dict[str, Any],
    *,
    selected_candidate_id: str,
    arbiter: str,
    verdict: str,
    rationale: str,
    summary: str,
    supporting_decisions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    if str(consensus.get("consensus_mode", "") or "").strip() != "arbiter-review":
        raise ValueError("arbiter decisions require consensus_mode=arbiter-review")
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    if selected_candidate_id not in by_id:
        raise ValueError("selected_candidate_id must match an existing consensus candidate")
    normalized_verdict = str(verdict or "").strip().lower()
    if normalized_verdict not in {"accept", "reject", "prefer"}:
        raise ValueError("verdict must be one of: accept, reject, prefer")
    normalized_arbiter = str(arbiter or "").strip()[:64]
    if not normalized_arbiter:
        raise ValueError("arbiter required")
    normalized_rationale = str(rationale or "").strip()[:400]
    if not normalized_rationale:
        raise ValueError("rationale required")
    normalized_summary = str(summary or "").strip()[:400] or normalized_rationale
    normalized_support = _normalize_consensus_decisions(supporting_decisions or [])

    now = int(time.time())
    selected_candidate = by_id[selected_candidate_id]
    arbiter_state = consensus.get("arbiter") if isinstance(consensus.get("arbiter"), dict) else {}
    history = arbiter_state.get("history") if isinstance(arbiter_state.get("history"), list) else []
    decision = {
        "ts": now,
        "arbiter": normalized_arbiter,
        "verdict": normalized_verdict,
        "selected_candidate_id": selected_candidate_id,
        "selected_lane": selected_candidate.get("lane"),
        "selected_agent": selected_candidate.get("agent"),
        "selected_role": selected_candidate.get("role"),
        "rationale": normalized_rationale,
        "summary": normalized_summary,
        "supporting_decisions": normalized_support,
    }
    history.append(decision)
    arbiter_state.update(
        {
            "required": True,
            "status": "resolved",
            "arbiter": normalized_arbiter,
            "arbiter_lane": str(arbiter_state.get("arbiter_lane", "") or "codex-review"),
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "selected_profile": selected_candidate.get("profile"),
            "selected_runtime_id": selected_candidate.get("runtime_id"),
            "last_decision": decision,
            "history": history[-10:],
        }
    )
    consensus["arbiter"] = arbiter_state
    consensus["status"] = "accepted" if normalized_verdict in {"accept", "prefer"} else "rejected"
    consensus["selected_candidate_id"] = selected_candidate_id
    consensus["selected_lane"] = selected_candidate.get("lane")
    consensus["selected_agent"] = selected_candidate.get("agent")
    consensus["selected_role"] = selected_candidate.get("role")
    consensus["selected_profile"] = selected_candidate.get("profile")
    consensus["selected_runtime_id"] = selected_candidate.get("runtime_id")
    consensus_history = consensus.get("history") if isinstance(consensus.get("history"), list) else []
    consensus_history.append(
        {
            "ts": now,
            "source": "arbiter",
            "arbiter": normalized_arbiter,
            "verdict": normalized_verdict,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "summary": normalized_summary,
            "decisions": normalized_support,
        }
    )
    consensus["history"] = consensus_history[-10:]
    session["consensus"] = consensus
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    trajectory.append(
        {
            "ts": now,
            "event_type": "arbiter_decision",
            "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
            "detail": f"arbiter -> {consensus['status']} ({selected_candidate_id})",
            "arbiter": normalized_arbiter,
            "verdict": normalized_verdict,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "supporting_decision_count": len(normalized_support),
        }
    )
    session["trajectory"] = trajectory
    session["updated_at"] = now
    return consensus
