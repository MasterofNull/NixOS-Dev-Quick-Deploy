"""
Workflow planning helpers: continuation detection, reasoning pattern selection,
workflow plan construction, tool security auditing, and AQ-report status loading.

Extracted from http_server.py (Phase 12.4 decomposition).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import Config
from tooling_manifest import workflow_tool_catalog
from pattern_integration import get_pattern_boost as _get_pattern_boost
from orchestration_utils import (
    _compact_prompt_coaching_metadata,
    _compact_workflow_tool_catalog,
    _compact_tool_security,
)

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_AQ_REPORT_LATEST_JSON = Path(
    os.getenv("AQ_REPORT_LATEST_JSON", "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
)

# Injected by http_server.run_http_mode() after the auditor is constructed.
_TOOL_SECURITY_AUDITOR: Optional[Any] = None


def set_tool_security_auditor(auditor: Any) -> None:
    """Late-bind the ToolSecurityAuditor instance created in run_http_mode."""
    global _TOOL_SECURITY_AUDITOR
    _TOOL_SECURITY_AUDITOR = auditor


# ---------------------------------------------------------------------------
# AQ-report status loader
# ---------------------------------------------------------------------------

def _load_aq_report_status_summary() -> Dict[str, Any]:
    try:
        if not _AQ_REPORT_LATEST_JSON.exists():
            return {"available": False, "source": str(_AQ_REPORT_LATEST_JSON)}
        payload = json.loads(_AQ_REPORT_LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "source": str(_AQ_REPORT_LATEST_JSON),
            "error": str(exc)[:180],
        }

    continue_editor = payload.get("continue_editor") or {}
    continue_windows = ((payload.get("continue_editor_windows") or {}).get("windows") or {})
    workflow_review = payload.get("intent_contract_compliance") or {}
    retrieval_windows = ((payload.get("route_retrieval_breadth_windows") or {}).get("windows") or {})
    routing_windows = ((payload.get("routing_windows") or {}).get("windows") or {})
    remote_windows = ((payload.get("remote_profile_utilization_windows") or {}).get("windows") or {})
    route_latency = payload.get("route_search_latency_decomposition") or {}
    rag_posture = payload.get("rag_posture") or {}
    delegation_windows = ((payload.get("delegated_prompt_failure_windows") or {}).get("windows") or {})
    delegation_trend = ((payload.get("delegated_prompt_failure_windows") or {}).get("trend") or {})
    recommendations = [
        str(item).strip()
        for item in (payload.get("recommendations") or [])
        if str(item).strip()
    ]
    structured_actions = payload.get("structured_actions") or []
    compact_actions = []
    for item in structured_actions[:3]:
        if not isinstance(item, dict):
            continue
        compact_actions.append(
            {
                "type": str(item.get("type", "") or "").strip(),
                "action": str(item.get("action", "") or "").strip(),
                "reason": str(item.get("reason", "") or "").strip()[:180],
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "safe": bool(item.get("safe", False)),
            }
        )

    def _trend_indicator(w1h: dict, w24h: dict, metric_key: str, higher_is_better: bool = True) -> str:
        """Return trend indicator: ↑ improving, ↓ worsening, → stable, ? unknown."""
        try:
            v1h = w1h.get(metric_key)
            v24h = w24h.get(metric_key)
            if v1h is None or v24h is None:
                return "?"
            v1h, v24h = float(v1h), float(v24h)
            if v24h == 0:
                return "→" if v1h == 0 else ("↑" if higher_is_better else "↓")
            ratio = v1h / v24h
            if ratio > 1.1:
                return "↑" if higher_is_better else "↓"
            elif ratio < 0.9:
                return "↓" if higher_is_better else "↑"
            return "→"
        except (TypeError, ValueError, ZeroDivisionError):
            return "?"

    routing_1h = routing_windows.get("1h", {})
    routing_24h = routing_windows.get("24h", {})
    retrieval_1h = retrieval_windows.get("1h", {})
    retrieval_24h = retrieval_windows.get("24h", {})
    delegation_1h = delegation_windows.get("1h", {})
    delegation_24h = delegation_windows.get("24h", {})

    return {
        "available": True,
        "source": str(_AQ_REPORT_LATEST_JSON),
        "generated_at": payload.get("generated_at", ""),
        "trend_summary": {
            "routing_local_pct": _trend_indicator(routing_1h, routing_24h, "local_pct", higher_is_better=True),
            "retrieval_rag_share": _trend_indicator(retrieval_1h, retrieval_24h, "rag_share_pct", higher_is_better=True),
            "delegation_failures": _trend_indicator(delegation_1h, delegation_24h, "total_failures", higher_is_better=False),
        },
        "continue_editor": {
            "healthy": bool(continue_editor.get("healthy", False)),
            "failed_n": int(continue_editor.get("failed_n", 0) or 0),
            "total_checks": int(continue_editor.get("total_checks", 0) or 0),
            "top_failure_category": continue_editor.get("top_failure_category"),
            "trend_1h": continue_windows.get("1h", {}),
            "trend_24h": continue_windows.get("24h", {}),
            "trend_7d": continue_windows.get("7d", {}),
        },
        "remote_profile_utilization": {
            "current": payload.get("remote_profile_utilization", {}),
            "trend_1h": remote_windows.get("1h", {}),
            "trend_24h": remote_windows.get("24h", {}),
            "trend_7d": remote_windows.get("7d", {}),
        },
        "routing": {
            "current": payload.get("routing", {}),
            "trend_1h": routing_1h,
            "trend_24h": routing_24h,
            "trend_7d": routing_windows.get("7d", {}),
            "latency": {
                "window": route_latency.get("window", ""),
                "overall_p95_ms": route_latency.get("overall_p95_ms"),
                "actionable_p95_ms": route_latency.get("actionable_p95_ms"),
                "backend_valid_p95_ms": route_latency.get("backend_valid_p95_ms"),
                "synthesis_p95_ms": route_latency.get("synthesis_p95_ms"),
                "retrieval_only_p95_ms": route_latency.get("retrieval_only_p95_ms"),
                "synthesis_calls": route_latency.get("synthesis_calls"),
                "client_error_count": route_latency.get("client_error_count"),
                "top_breakdown": (route_latency.get("breakdown") or [])[:3],
            },
        },
        "retrieval": {
            "current": payload.get("route_retrieval_breadth", {}),
            "trend_1h": retrieval_1h,
            "trend_24h": retrieval_24h,
            "trend_7d": retrieval_windows.get("7d", {}),
        },
        "rag_posture": {
            "available": bool(rag_posture.get("available", False)),
            "status": str(rag_posture.get("status", "unknown") or "unknown"),
            "recent_retrieval_calls": int(rag_posture.get("recent_retrieval_calls", 0) or 0),
            "cache_hit_pct": rag_posture.get("cache_hit_pct"),
            "memory_recall_share_pct": rag_posture.get("memory_recall_share_pct"),
            "memory_recall_attempts": int(rag_posture.get("memory_recall_attempts", 0) or 0),
            "memory_recall_miss_pct": rag_posture.get("memory_recall_miss_pct"),
            "memory_recall_diagnosis": str(rag_posture.get("memory_recall_diagnosis", "") or "").strip().lower(),
            "memory_recall_actions": [
                str(action).strip()
                for action in (rag_posture.get("memory_recall_actions") or [])
                if str(action).strip()
            ][:3],
            "prewarm_candidates": [
                {
                    "id": str(candidate.get("id", "")).strip(),
                    "reason": str(candidate.get("reason", "")).strip(),
                }
                for candidate in (rag_posture.get("prewarm_candidates") or [])[:3]
                if isinstance(candidate, dict) and str(candidate.get("id", "")).strip()
            ],
        },
        "delegation_failures": {
            "trend_status": delegation_trend.get("status", "unknown"),
            "trend_summary": delegation_trend.get("summary", ""),
            "trend_1h": delegation_1h,
            "trend_24h": delegation_24h,
            "trend_7d": delegation_windows.get("7d", {}),
        },
        "workflow_review": {
            "required_reviews": int(workflow_review.get("required_reviews", 0) or 0),
            "accepted_reviews": int(workflow_review.get("accepted_reviews", 0) or 0),
            "rejected_reviews": int(workflow_review.get("rejected_reviews", 0) or 0),
            "top_review_types": (workflow_review.get("top_review_types") or [])[:3],
            "accepted_task_classes": (workflow_review.get("accepted_task_classes") or [])[:5],
            "accepted_by_reviewed_profile": (workflow_review.get("accepted_by_reviewed_profile") or [])[:5],
        },
        "optimization_watch": {
            "available": bool(recommendations or compact_actions),
            "recommendation_count": len(recommendations),
            "structured_action_count": len(structured_actions),
            "top_recommendations": recommendations[:3],
            "top_actions": compact_actions,
        },
    }


# ---------------------------------------------------------------------------
# Tool security auditing
# ---------------------------------------------------------------------------

def _audit_planned_tools(query: str, tools: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Audit tools on first use and keep only approved/sanitized tool entries."""
    if not _TOOL_SECURITY_AUDITOR:
        return tools, {
            "enabled": False,
            "approved": [t.get("name", "") for t in tools],
            "blocked": [],
            "cache_hits": 0,
            "first_seen": 0,
        }

    approved: List[Dict[str, str]] = []
    blocked: List[str] = []
    cache_hits = 0
    first_seen = 0
    for tool in tools:
        tool_name = str(tool.get("name", "")).strip()
        if not tool_name:
            continue
        try:
            decision = _TOOL_SECURITY_AUDITOR.audit_tool(
                tool_name,
                {
                    "query": query[:400],
                    "endpoint": tool.get("endpoint"),
                    "reason": tool.get("reason"),
                    "manifest": {"name": tool_name, "endpoint": tool.get("endpoint")},
                },
            )
            if decision.get("cached"):
                cache_hits += 1
            if decision.get("first_seen"):
                first_seen += 1
            if decision.get("approved", True):
                approved.append(tool)
            else:
                blocked.append(tool_name)
        except PermissionError:
            blocked.append(tool_name)
    return approved, {
        "enabled": True,
        "approved": [t.get("name", "") for t in approved],
        "blocked": blocked,
        "cache_hits": cache_hits,
        "first_seen": first_seen,
    }


# ---------------------------------------------------------------------------
# Continuation / memory-recall detection
# ---------------------------------------------------------------------------

def _is_continuation_query(query: str) -> bool:
    query_lower = str(query or "").lower()
    direct_tokens = (
        "resume",
        "continue",
        "follow-up",
        "follow up",
        "prior context",
        "pick up where",
        "last agent",
        "ongoing",
    )
    if any(token in query_lower for token in direct_tokens):
        return True
    has_previous_ref = any(token in query_lower for token in ("previous", "prior", "last"))
    has_resume_target = any(
        token in query_lower
        for token in ("context", "patch", "deploy", "troubleshooting", "debug", "loop", "work")
    )
    return has_previous_ref and has_resume_target


def _should_prioritize_memory_recall(query: str) -> bool:
    """Return True when the query benefits from priming with recalled memory context.

    Phase 14.5: broaden heuristics to raise trigger rate from ~12% toward >=30%.
    Added phase/session context markers, agent-work vocabulary, status/progress
    signals, and a relaxed single-token path for high-signal terms.
    """
    if _is_continuation_query(query):
        return True
    query_lower = str(query or "").lower()

    # Explicit long-horizon markers — always recall
    long_horizon_markers = (
        "current work",
        "remaining work",
        "left off",
        "last run",
        "previous run",
        "earlier attempt",
        "ongoing task",
        "ongoing issue",
        # Phase 14.5 additions
        "next session",
        "last session",
        "from last",
        "where we left",
        "pick up",
        "continue from",
        "phase gate",
        "phase status",
        "hand off",
        "open items",
        "outstanding work",
        "unfinished",
        "in progress",
        "in-progress",
    )
    if any(marker in query_lower for marker in long_horizon_markers):
        return True

    # High-signal single tokens that strongly imply session context
    history_tokens = {
        "previous", "prior", "last", "earlier", "current", "ongoing",
        "remaining", "resume", "handoff", "unfinished", "incomplete",
        "pending", "blocked", "stalled", "next", "follow-up", "followup",
    }
    # Broad repo/work targets — anything that might need session grounding
    repo_target_tokens = {
        "patch", "deploy", "debug", "failure", "issue", "incident",
        "repo", "service", "system", "task", "work",
        # Phase 14.5 additions
        "fix", "bug", "error", "phase", "sprint", "ticket", "pr",
        "commit", "build", "test", "ci", "pipeline", "migration",
        "refactor", "release", "rollback", "plan", "roadmap",
        "agent", "session", "run", "step", "iteration",
    }
    has_history_ref = any(token in query_lower for token in history_tokens)
    has_repo_target = any(token in query_lower for token in repo_target_tokens)
    if has_history_ref and has_repo_target:
        return True

    # Phase 14.5: single-token fast path for high-signal standalone terms
    high_signal_standalone = {
        "handoff", "resume", "unfinished", "incomplete",
        "blocked", "stalled",
    }
    if any(token in query_lower for token in high_signal_standalone):
        return True

    return False


def _workflow_memory_first_strategy(
    query: str,
    memory_recall_priority: bool,
    aq_report_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Prefer memory-first plans for continuation work when live telemetry says it helps."""
    if not memory_recall_priority:
        return {"active": False, "mode": "standard", "reasons": [], "evidence": {}}

    retrieval = aq_report_summary.get("retrieval", {}) if isinstance(aq_report_summary, dict) else {}
    routing = aq_report_summary.get("routing", {}) if isinstance(aq_report_summary, dict) else {}
    rag_posture = aq_report_summary.get("rag_posture", {}) if isinstance(aq_report_summary, dict) else {}
    latency = routing.get("latency", {}) if isinstance(routing, dict) else {}

    memory_share = rag_posture.get("memory_recall_share_pct")
    memory_diagnosis = str(rag_posture.get("memory_recall_diagnosis", "") or "").strip().lower()
    synthesis_p95_ms = latency.get("synthesis_p95_ms")
    recent_retrieval_calls = int(rag_posture.get("recent_retrieval_calls", 0) or 0)
    retrieval_status = str(rag_posture.get("status", "unknown") or "unknown").strip().lower()

    reasons: List[str] = []
    try:
        if memory_diagnosis in {"unused", "weak"} and recent_retrieval_calls >= 8:
            reasons.append(f"memory_recall_{memory_diagnosis}")
    except Exception:
        pass
    try:
        if memory_share is not None and float(memory_share) <= 15.0 and recent_retrieval_calls >= 8:
            reasons.append("memory_recall_share_low")
    except (TypeError, ValueError):
        pass
    try:
        if synthesis_p95_ms is not None and float(synthesis_p95_ms) >= 20000.0:
            reasons.append("route_search_synthesis_hotspot")
    except (TypeError, ValueError):
        pass
    if retrieval_status == "low_sample":
        reasons.append("rag_cache_low_sample")

    # Explicit retrieval/search asks should still advertise route_search early.
    normalized = str(query or "").strip().lower()
    explicit_search = any(
        token in normalized
        for token in ("search", "find", "retrieve", "lookup", "grep", "rg ", "query")
    )
    active = bool(reasons) and not explicit_search
    return {
        "active": active,
        "mode": "memory-first" if active else "standard",
        "reasons": reasons,
        "evidence": {
            "memory_recall_share_pct": memory_share,
            "memory_recall_diagnosis": memory_diagnosis,
            "synthesis_p95_ms": synthesis_p95_ms,
            "recent_retrieval_calls": recent_retrieval_calls,
            "memory_actions": list(rag_posture.get("memory_recall_actions", []) or [])[:2],
        },
    }


# ---------------------------------------------------------------------------
# Workflow plan builder
# ---------------------------------------------------------------------------

def _build_workflow_plan(
    query: str,
    tools: Optional[List[Dict[str, str]]] = None,
    tool_security: Optional[Dict[str, Any]] = None,
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    memory_recall_priority = _should_prioritize_memory_recall(query)
    if tools is None or tool_security is None:
        tools, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query, memory_recall_priority=memory_recall_priority))
    prompt_coaching: Dict[str, Any] = {}
    try:
        from hints_engine import HintsEngine  # type: ignore[import]
        prompt_coaching = HintsEngine().prompt_coaching_as_dict(query, agent_type="codex")
    except Exception:
        prompt_coaching = {}
    tool_catalog = {str(t.get("name", "")).strip(): dict(t) for t in tools if str(t.get("name", "")).strip()}
    reasoning_pattern = _select_reasoning_pattern(query, prompt_coaching, memory_recall_priority)
    aq_report_summary = _load_aq_report_status_summary()
    retrieval_strategy = _workflow_memory_first_strategy(query, memory_recall_priority, aq_report_summary)

    def pick_tool_names(names: set[str]) -> List[str]:
        return [name for name in tool_catalog if name in names]

    discover_tools = (
        {"hints", "discovery", "memory_recall"}
        if retrieval_strategy["active"]
        else {"hints", "discovery", "route_search", "tree_search"}
        | ({"memory_recall"} if memory_recall_priority else set())
    )
    plan_tools = (
        {"hints", "discovery", "memory_recall"}
        if retrieval_strategy["active"]
        else {"hints", "discovery"} | ({"memory_recall"} if memory_recall_priority else set())
    )
    execute_tools = {
        "memory_recall",
        "route_search",
        "web_research_fetch",
        "browser_research_fetch",
        "curated_research_fetch",
        "feedback",
    }

    return {
        "objective": query,
        "workflow_version": "1.1",
        "phases": [
            {
                "id": "discover",
                "goal": "Collect high-signal context first.",
                "tools": pick_tool_names(discover_tools),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("discover", "react"),
                "exit_criteria": "Top risks identified.",
            },
            {
                "id": "plan",
                "goal": "Turn findings into verified steps.",
                "tools": pick_tool_names(plan_tools),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("plan", "react"),
                "exit_criteria": "Ordered task list exists.",
            },
            {
                "id": "execute",
                "goal": "Apply small reversible changes.",
                "tools": pick_tool_names(execute_tools),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("execute", "react"),
                "exit_criteria": "Primary objective implemented.",
            },
            {
                "id": "validate",
                "goal": "Run checks and confirm behavior.",
                "tools": pick_tool_names({"qa_check", "harness_eval", "health", "learning_stats"}),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("validate", "reflexion"),
                "exit_criteria": "Checks pass or failures are documented.",
            },
            {
                "id": "handoff",
                "goal": "Capture outcomes, risk, and rollback.",
                "tools": pick_tool_names({"feedback", "learning_stats"}),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("handoff", "reflexion"),
                "exit_criteria": "Handoff summary ready.",
            },
        ],
        "token_policy": {
            "approach": "progressive-disclosure",
            "rules": [
                {"id": "compact-first", "summary": "Start concise; load deeper context only when needed."},
                {"id": "retrieve-before-restating", "summary": "Prefer retrieval over prompt stuffing; escalate remote only when justified."},
                {"id": "cheap-probe-then-cache", "summary": "Use low-cost probing first and keep reusable prefixes compact for caching."},
            ],
        },
        "metadata": {
            "query_length": len(query),
            "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            "prompt_coaching": _compact_prompt_coaching_metadata(prompt_coaching),
            "tool_catalog": (
                tool_catalog
                if include_debug_metadata
                else _compact_workflow_tool_catalog(tool_catalog)
            ),
            "tool_security": (
                tool_security
                if include_debug_metadata
                else _compact_tool_security(tool_security or {})
            ),
            "created_epoch_s": int(time.time()),
            "memory_recall_priority": memory_recall_priority,
            "retrieval_strategy": retrieval_strategy,
            "reasoning_pattern": reasoning_pattern,
            "optimization_watch": aq_report_summary.get("optimization_watch", {"available": False}),
        },
    }


# ---------------------------------------------------------------------------
# Reasoning pattern selector
# ---------------------------------------------------------------------------

def _select_reasoning_pattern(
    query: str,
    prompt_coaching: Dict[str, Any],
    continuation_query: bool,
) -> Dict[str, Any]:
    """Select a live agentic reasoning pattern for workflow planning/runtime."""
    normalized = str(query or "").strip().lower()
    coaching_summary = _compact_prompt_coaching_metadata(prompt_coaching)
    missing_count = int(coaching_summary.get("missing_count", 0) or 0)
    complexity_tokens = {
        "architecture",
        "design",
        "tradeoff",
        "compare",
        "strategy",
        "complex",
        "multi-step",
        "reasoning",
    }
    reflexion_tokens = {
        "retry",
        "regression",
        "failure",
        "postmortem",
        "improve",
        "root cause",
        "stability",
        "freeze",
    }
    react_tokens = {
        "debug",
        "investigate",
        "diagnose",
        "fix",
        "deploy",
        "integration",
        "service",
        "workflow",
    }
    self_consistency_tokens = {
        "consistent",
        "consistency",
        "independent answers",
        "majority vote",
        "cross-check",
    }
    plan_and_solve_tokens = {
        "step-by-step plan",
        "break down",
        "implementation plan",
        "plan this",
        "sequence of steps",
    }
    verification_tokens = {
        "verify",
        "verification",
        "validate",
        "fact-check",
        "prove",
        "confirm",
    }
    debate_tokens = {
        "debate",
        "argue both sides",
        "counterargument",
        "pros and cons",
        "tradeoffs",
    }

    complexity_score = float(min(1.0, (len(normalized.split()) / 40.0) + (missing_count / 10.0)))
    selection_basis: List[str] = []
    if any(token in normalized for token in debate_tokens):
        primary = "debate"
        selection_basis.append("multi-perspective debate cues")
    elif any(token in normalized for token in verification_tokens):
        primary = "chain_of_verification"
        selection_basis.append("verification-first cues")
    elif any(token in normalized for token in self_consistency_tokens):
        primary = "self_consistency"
        selection_basis.append("consensus-checking cues")
    elif any(token in normalized for token in plan_and_solve_tokens):
        primary = "plan_and_solve"
        selection_basis.append("explicit planning cues")
    elif any(token in normalized for token in complexity_tokens):
        primary = "tree_of_thoughts"
        selection_basis.append("complex deliberation cues")
    elif continuation_query or any(token in normalized for token in reflexion_tokens):
        primary = "reflexion"
        selection_basis.append("iterative recovery cues")
    elif any(token in normalized for token in react_tokens):
        primary = "react"
        selection_basis.append("tool-using execution cues")
    elif complexity_score >= 0.65:
        primary = "tree_of_thoughts"
        selection_basis.append("elevated prompt complexity")
    else:
        primary = "react"
        selection_basis.append("default action-first workflow")

    phase_recommendations = {
        "discover": "react",
        "plan": "tree_of_thoughts" if primary in {"tree_of_thoughts", "reflexion"} else "react",
        "execute": "react",
        "validate": "reflexion",
        "handoff": "reflexion",
    }
    if primary == "tree_of_thoughts":
        phase_recommendations["plan"] = "tree_of_thoughts"
    elif primary == "plan_and_solve":
        phase_recommendations["plan"] = "plan_and_solve"
        phase_recommendations["execute"] = "plan_and_solve"
    elif primary == "self_consistency":
        phase_recommendations["validate"] = "self_consistency"
    elif primary == "chain_of_verification":
        phase_recommendations["validate"] = "chain_of_verification"
    elif primary == "debate":
        phase_recommendations["discover"] = "debate"
        phase_recommendations["plan"] = "debate"
    elif primary == "reflexion":
        phase_recommendations["validate"] = "reflexion"
        phase_recommendations["handoff"] = "reflexion"

    alternatives = [
        name
        for name in (
            "react",
            "tree_of_thoughts",
            "reflexion",
            "self_consistency",
            "plan_and_solve",
            "chain_of_verification",
            "debate",
        )
        if name != primary
    ]
    return {
        "selected_pattern": primary,
        "selection_basis": selection_basis,
        "complexity_score": round(complexity_score, 3),
        "boost_multiplier": round(float(_get_pattern_boost(primary)), 3),
        "phase_recommendations": phase_recommendations,
        "alternatives": alternatives,
        "constitutional_guardrails": True,
    }
