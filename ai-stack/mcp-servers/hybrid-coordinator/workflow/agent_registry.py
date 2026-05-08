"""
Agent registry, lessons, evaluations, and intent contract utilities.

Extracted from http_server.py (Phase 12.4 decomposition).

Provides file-backed storage for agent lessons, evaluations, and review
events, plus intent contract validation/coercion helpers.
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Locks shared with the rest of the server (imported by http_server.py)
# ---------------------------------------------------------------------------

_agent_lessons_lock = asyncio.Lock()
_agent_evaluations_lock = asyncio.Lock()

_INTENT_DEPTH_EXPECTATIONS = {"minimum", "standard", "deep"}

# ---------------------------------------------------------------------------
# Registry and utility functions
# ---------------------------------------------------------------------------

def _agent_lessons_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-lessons.json"


def _agent_evaluations_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-evaluations.json"


def _workflow_blueprints_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("WORKFLOW_BLUEPRINTS_FILE", "config/workflow-blueprints.json")
        )
    )


def _hint_feedback_log_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("HINT_FEEDBACK_LOG_PATH", "/var/log/nixos-ai-stack/hint-feedback.jsonl")
        )
    )


def _default_agent_lessons_registry() -> Dict[str, Any]:
    return {
        "available": True,
        "path": str(_agent_lessons_registry_path()),
        "entries": [],
        "counts": {
            "total": 0,
            "pending_review": 0,
            "promoted": 0,
            "avoided": 0,
            "rejected": 0,
        },
        "active_lessons": [],
    }


def _default_agent_evaluations_registry() -> Dict[str, Any]:
    return {
        "available": True,
        "path": str(_agent_evaluations_registry_path()),
        "agents": {},
        "recent_events": [],
        "summary": {
            "agent_count": 0,
            "review_events": 0,
            "consensus_events": 0,
            "runtime_events": 0,
        },
    }


def _normalize_agent_role(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return normalized[:64] or "unknown"


def _default_agent_evaluation_row() -> Dict[str, Any]:
    return {
        "review_events": 0,
        "accepted_reviews": 0,
        "rejected_reviews": 0,
        "consensus_selected": 0,
        "runtime_events": 0,
        "successful_runtime_events": 0,
        "average_runtime_score": 0.0,
        "average_review_score": 0.0,
        "last_event_at": None,
    }


def _normalize_agent_lessons_registry(data: Any) -> Dict[str, Any]:
    registry = _default_agent_lessons_registry()
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            registry["entries"] = [item for item in entries if isinstance(item, dict)]
    counts = {
        "total": len(registry["entries"]),
        "pending_review": 0,
        "promoted": 0,
        "avoided": 0,
        "rejected": 0,
    }
    active_lessons: List[Dict[str, Any]] = []
    for item in registry["entries"]:
        state = str(item.get("state", "") or "").strip().lower()
        if state in counts:
            counts[state] += 1
        if state in {"promoted", "avoided"}:
            active_lessons.append(
                {
                    "lesson_key": item.get("lesson_key"),
                    "agent": item.get("agent"),
                    "hint_id": item.get("hint_id"),
                    "state": state,
                    "scope": item.get("scope"),
                    "materialization": item.get("materialization"),
                    "updated_at": item.get("updated_at"),
                }
            )
    active_lessons.sort(
        key=lambda item: (
            str(item.get("state") or ""),
            str(item.get("agent") or ""),
            str(item.get("hint_id") or ""),
        )
    )
    registry["counts"] = counts
    registry["active_lessons"] = active_lessons[:10]
    return registry


def _normalize_agent_evaluations_registry(data: Any) -> Dict[str, Any]:
    registry = _default_agent_evaluations_registry()
    if isinstance(data, dict):
        agents = data.get("agents")
        if isinstance(agents, dict):
            normalized_agents: Dict[str, Any] = {}
            for key, value in agents.items():
                agent_key = str(key or "").strip()
                if not agent_key or not isinstance(value, dict):
                    continue
                normalized_agents[agent_key] = {
                    "agent": agent_key,
                    "profiles": value.get("profiles", {}) if isinstance(value.get("profiles"), dict) else {},
                    "roles": value.get("roles", {}) if isinstance(value.get("roles"), dict) else {},
                    "totals": value.get("totals", {}) if isinstance(value.get("totals"), dict) else {},
                    "last_event_at": value.get("last_event_at"),
                }
            registry["agents"] = normalized_agents
        events = data.get("recent_events")
        if isinstance(events, list):
            registry["recent_events"] = [item for item in events if isinstance(item, dict)][-25:]

    review_events = 0
    consensus_events = 0
    runtime_events = 0
    for agent, payload in list(registry["agents"].items()):
        profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
        roles = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
        totals = {
            "review_events": 0,
            "accepted_reviews": 0,
            "rejected_reviews": 0,
            "consensus_selected": 0,
            "runtime_events": 0,
            "successful_runtime_events": 0,
            "average_runtime_score": 0.0,
            "average_review_score": 0.0,
        }
        weighted_scores = []
        total_score_events = 0
        weighted_runtime_scores = []
        total_runtime_score_events = 0
        normalized_profiles: Dict[str, Any] = {}
        normalized_roles: Dict[str, Any] = {}
        for profile_name, profile_payload in profiles.items():
            profile_key = str(profile_name or "").strip() or "unknown"
            if not isinstance(profile_payload, dict):
                continue
            review_count = int(profile_payload.get("review_events", 0) or 0)
            accepted = int(profile_payload.get("accepted_reviews", 0) or 0)
            rejected = int(profile_payload.get("rejected_reviews", 0) or 0)
            consensus_selected = int(profile_payload.get("consensus_selected", 0) or 0)
            runtime_count = int(profile_payload.get("runtime_events", 0) or 0)
            successful_runtime = int(profile_payload.get("successful_runtime_events", 0) or 0)
            avg_runtime_score = float(profile_payload.get("average_runtime_score", 0.0) or 0.0)
            avg_score = float(profile_payload.get("average_review_score", 0.0) or 0.0)
            normalized_profiles[profile_key] = {
                "review_events": review_count,
                "accepted_reviews": accepted,
                "rejected_reviews": rejected,
                "consensus_selected": consensus_selected,
                "runtime_events": runtime_count,
                "successful_runtime_events": successful_runtime,
                "average_runtime_score": round(avg_runtime_score, 4),
                "average_review_score": round(avg_score, 4),
                "last_event_at": profile_payload.get("last_event_at"),
            }
            totals["review_events"] += review_count
            totals["accepted_reviews"] += accepted
            totals["rejected_reviews"] += rejected
            totals["consensus_selected"] += consensus_selected
            totals["runtime_events"] += runtime_count
            totals["successful_runtime_events"] += successful_runtime
            if review_count > 0:
                weighted_scores.append(avg_score * review_count)
                total_score_events += review_count
            if runtime_count > 0:
                weighted_runtime_scores.append(avg_runtime_score * runtime_count)
                total_runtime_score_events += runtime_count
        for role_name, role_payload in roles.items():
            role_key = _normalize_agent_role(role_name)
            if not isinstance(role_payload, dict):
                continue
            normalized_roles[role_key] = {
                **_default_agent_evaluation_row(),
                "review_events": int(role_payload.get("review_events", 0) or 0),
                "accepted_reviews": int(role_payload.get("accepted_reviews", 0) or 0),
                "rejected_reviews": int(role_payload.get("rejected_reviews", 0) or 0),
                "consensus_selected": int(role_payload.get("consensus_selected", 0) or 0),
                "runtime_events": int(role_payload.get("runtime_events", 0) or 0),
                "successful_runtime_events": int(role_payload.get("successful_runtime_events", 0) or 0),
                "average_runtime_score": round(float(role_payload.get("average_runtime_score", 0.0) or 0.0), 4),
                "average_review_score": round(float(role_payload.get("average_review_score", 0.0) or 0.0), 4),
                "last_event_at": role_payload.get("last_event_at"),
            }
        totals["average_review_score"] = round(
            (sum(weighted_scores) / total_score_events) if total_score_events else 0.0,
            4,
        )
        totals["average_runtime_score"] = round(
            (sum(weighted_runtime_scores) / total_runtime_score_events) if total_runtime_score_events else 0.0,
            4,
        )
        payload["profiles"] = normalized_profiles
        payload["roles"] = normalized_roles
        payload["totals"] = totals
        review_events += totals["review_events"]
        consensus_events += totals["consensus_selected"]
        runtime_events += totals["runtime_events"]
    registry["summary"] = {
        "agent_count": len(registry["agents"]),
        "review_events": review_events,
        "consensus_events": consensus_events,
        "runtime_events": runtime_events,
    }
    return registry


def _load_agent_evaluations_registry_sync() -> Dict[str, Any]:
    path = _agent_evaluations_registry_path()
    if not path.exists():
        return _default_agent_evaluations_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_evaluations_registry()
    return _normalize_agent_evaluations_registry(data)


async def _load_agent_evaluations_registry() -> Dict[str, Any]:
    path = _agent_evaluations_registry_path()
    if not path.exists():
        return _default_agent_evaluations_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_evaluations_registry()
    return _normalize_agent_evaluations_registry(data)


async def _save_agent_evaluations_registry(data: Dict[str, Any]) -> None:
    path = _agent_evaluations_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_normalize_agent_evaluations_registry(data), indent=2) + "\n", encoding="utf-8")


def _record_agent_review_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    role: str,
    passed: bool,
    score: float,
    reviewer: str,
    review_type: str,
    task_class: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(profile or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    review_events = int(profile_row.get("review_events", 0) or 0) + 1
    running_total = float(profile_row.get("average_review_score", 0.0) or 0.0) * max(0, review_events - 1)
    profile_row["review_events"] = review_events
    profile_row["accepted_reviews"] = int(profile_row.get("accepted_reviews", 0) or 0) + (1 if passed else 0)
    profile_row["rejected_reviews"] = int(profile_row.get("rejected_reviews", 0) or 0) + (0 if passed else 1)
    profile_row["average_review_score"] = round((running_total + float(score)) / review_events, 4)
    profile_row["last_event_at"] = ts
    role_review_events = int(role_row.get("review_events", 0) or 0) + 1
    role_running_total = float(role_row.get("average_review_score", 0.0) or 0.0) * max(0, role_review_events - 1)
    role_row["review_events"] = role_review_events
    role_row["accepted_reviews"] = int(role_row.get("accepted_reviews", 0) or 0) + (1 if passed else 0)
    role_row["rejected_reviews"] = int(role_row.get("rejected_reviews", 0) or 0) + (0 if passed else 1)
    role_row["average_review_score"] = round((role_running_total + float(score)) / role_review_events, 4)
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "review",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "passed": bool(passed),
            "score": round(float(score), 4),
            "reviewer": reviewer,
            "review_type": review_type,
            "task_class": task_class,
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _record_agent_consensus_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    lane: str,
    role: str,
    selected_candidate_id: str,
    summary: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(lane or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    profile_row["consensus_selected"] = int(profile_row.get("consensus_selected", 0) or 0) + 1
    profile_row["last_event_at"] = ts
    role_row["consensus_selected"] = int(role_row.get("consensus_selected", 0) or 0) + 1
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "consensus",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "selected_candidate_id": selected_candidate_id,
            "summary": summary[:240],
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _runtime_event_score(event_type: str, risk_class: str, approved: bool) -> float:
    text = str(event_type or "").strip().lower()
    risk = str(risk_class or "").strip().lower()
    if text in {"failed", "failure", "error", "blocked", "rejected"} or risk == "blocked":
        return 0.0
    if text in {"completed", "complete", "success", "validation_pass", "phase_complete"}:
        return 1.0
    if risk == "review-required":
        return 0.8 if approved else 0.35
    return 0.7 if approved or risk == "safe" else 0.5


def _record_agent_runtime_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    role: str,
    event_type: str,
    risk_class: str,
    approved: bool,
    token_delta: int,
    tool_call_delta: int,
    detail: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(profile or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    runtime_events = int(profile_row.get("runtime_events", 0) or 0) + 1
    runtime_score = _runtime_event_score(event_type, risk_class, approved)
    running_total = float(profile_row.get("average_runtime_score", 0.0) or 0.0) * max(0, runtime_events - 1)
    profile_row["runtime_events"] = runtime_events
    profile_row["successful_runtime_events"] = int(profile_row.get("successful_runtime_events", 0) or 0) + (
        1 if runtime_score >= 0.8 else 0
    )
    profile_row["average_runtime_score"] = round((running_total + runtime_score) / runtime_events, 4)
    profile_row["last_event_at"] = ts
    role_runtime_events = int(role_row.get("runtime_events", 0) or 0) + 1
    role_running_total = float(role_row.get("average_runtime_score", 0.0) or 0.0) * max(0, role_runtime_events - 1)
    role_row["runtime_events"] = role_runtime_events
    role_row["successful_runtime_events"] = int(role_row.get("successful_runtime_events", 0) or 0) + (
        1 if runtime_score >= 0.8 else 0
    )
    role_row["average_runtime_score"] = round((role_running_total + runtime_score) / role_runtime_events, 4)
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "runtime",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "runtime_event_type": str(event_type or "").strip().lower(),
            "risk_class": str(risk_class or "").strip().lower(),
            "approved": bool(approved),
            "runtime_score": round(runtime_score, 4),
            "token_delta": max(0, int(token_delta or 0)),
            "tool_call_delta": max(0, int(tool_call_delta or 0)),
            "detail": str(detail or "").strip()[:240],
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _active_lesson_refs(registry: Dict[str, Any], limit: int = 2) -> List[Dict[str, Any]]:
    active_lessons = registry.get("active_lessons") if isinstance(registry, dict) else []
    if not isinstance(active_lessons, list):
        return []
    refs: List[Dict[str, Any]] = []
    for item in active_lessons[:max(0, limit)]:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "lesson_key": str(item.get("lesson_key", "") or "").strip(),
                "agent": str(item.get("agent", "") or "").strip(),
                "hint_id": str(item.get("hint_id", "") or "").strip(),
                "scope": str(item.get("scope", "") or "").strip(),
                "materialization": str(item.get("materialization", "") or "").strip(),
                "updated_at": str(item.get("updated_at", "") or "").strip(),
            }
        )
    return [item for item in refs if item.get("lesson_key")]


async def _load_active_lesson_refs(limit: int = 2) -> List[Dict[str, Any]]:
    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    return _active_lesson_refs(lesson_registry, limit=limit)


def _normalize_review_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text or "acceptance"


def _normalize_artifact_kind(value: Any, review_type: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text:
        return text
    if review_type == "patch_review":
        return "patch"
    if review_type == "plan_review":
        return "plan"
    if review_type == "artifact_review":
        return "artifact"
    return "response"


def _normalize_task_class(value: Any, session: Optional[Dict[str, Any]]) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text:
        return text
    if isinstance(session, dict):
        blueprint_id = str(session.get("blueprint_id", "") or "").strip().lower().replace("-", "_")
        if blueprint_id:
            return blueprint_id
    return "general"
async def _load_agent_lessons_registry() -> Dict[str, Any]:
    path = _agent_lessons_registry_path()
    if not path.exists():
        return _default_agent_lessons_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_lessons_registry()
    return _normalize_agent_lessons_registry(data)


async def _save_agent_lessons_registry(data: Dict[str, Any]) -> None:
    path = _agent_lessons_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_normalize_agent_lessons_registry(data), indent=2) + "\n", encoding="utf-8")


def _normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_orchestration_lane_list(value: Any) -> List[str]:
    values = _normalize_string_list(value)
    out: List[str] = []
    seen = set()
    for item in values:
        lane = str(item or "").strip().lower()
        if lane and lane not in seen:
            seen.add(lane)
            out.append(lane)
    return out


def _validate_intent_contract(contract: Any) -> Dict[str, Any]:
    """Validate required prompt-intent/spirit contract fields."""
    errors: List[str] = []
    if not isinstance(contract, dict):
        return {
            "ok": False,
            "errors": ["intent_contract must be an object"],
            "normalized": {},
        }

    user_intent = str(contract.get("user_intent", "") or "").strip()
    definition_of_done = str(contract.get("definition_of_done", "") or "").strip()
    depth_expectation = str(contract.get("depth_expectation", "") or "").strip().lower()
    spirit_constraints = _normalize_string_list(contract.get("spirit_constraints", []))
    no_early_exit_without = _normalize_string_list(contract.get("no_early_exit_without", []))
    anti_goals = _normalize_string_list(contract.get("anti_goals", []))

    if not user_intent:
        errors.append("intent_contract.user_intent is required")
    if not definition_of_done:
        errors.append("intent_contract.definition_of_done is required")
    if depth_expectation not in _INTENT_DEPTH_EXPECTATIONS:
        errors.append(
            "intent_contract.depth_expectation must be one of: minimum, standard, deep"
        )
    if not spirit_constraints:
        errors.append("intent_contract.spirit_constraints must contain at least one item")
    if not no_early_exit_without:
        errors.append("intent_contract.no_early_exit_without must contain at least one item")

    normalized = {
        "user_intent": user_intent,
        "definition_of_done": definition_of_done,
        "depth_expectation": depth_expectation if depth_expectation in _INTENT_DEPTH_EXPECTATIONS else "standard",
        "spirit_constraints": spirit_constraints,
        "no_early_exit_without": no_early_exit_without,
        "anti_goals": anti_goals,
    }
    return {"ok": len(errors) == 0, "errors": errors, "normalized": normalized}


def _default_intent_contract(query: str) -> Dict[str, Any]:
    objective = (query or "").strip()[:280] or "complete current workflow objective"
    return {
        "user_intent": objective,
        "definition_of_done": "deliver validated results that satisfy the objective",
        "depth_expectation": "minimum",
        "spirit_constraints": [
            "follow declarative-first policy",
            "capture validation evidence for major actions",
            "prefer harness retrieval, memory recall, and periodic compaction over resending long prompt history",
        ],
        "no_early_exit_without": [
            "all requested checks completed",
            "known blockers documented with remediation",
            "context strategy or blocker documented when the task is long-running",
        ],
        "anti_goals": [],
    }


def _coerce_intent_contract(query: str, incoming: Any) -> Dict[str, Any]:
    """
    Produce a valid intent contract even when callers omit/partially provide it.
    This keeps workflow telemetry contract coverage high without weakening fields.
    """
    base = _default_intent_contract(query)
    if not isinstance(incoming, dict):
        return base

    user_intent = str(incoming.get("user_intent", "") or "").strip()
    definition = str(incoming.get("definition_of_done", "") or "").strip()
    depth = str(incoming.get("depth_expectation", "") or "").strip().lower()
    spirit = _normalize_string_list(incoming.get("spirit_constraints", []))
    no_early = _normalize_string_list(incoming.get("no_early_exit_without", []))
    anti_goals = _normalize_string_list(incoming.get("anti_goals", []))

    if user_intent:
        base["user_intent"] = user_intent
    if definition:
        base["definition_of_done"] = definition
    if depth in _INTENT_DEPTH_EXPECTATIONS:
        base["depth_expectation"] = depth
    if spirit:
        base["spirit_constraints"] = spirit
    if no_early:
        base["no_early_exit_without"] = no_early
    if anti_goals:
        base["anti_goals"] = anti_goals
    return base


