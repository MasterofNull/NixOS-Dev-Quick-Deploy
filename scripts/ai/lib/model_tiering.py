#!/usr/bin/env python3
"""
model_tiering.py — Logic for Token Arbitrage and Complexity Estimation.

`get_recommended_model()` is health-aware: it never recommends a lane that
is flagged down or in an active cooldown. Health signals are read by
dynamically loading `scripts/ai/aq-role-route` and reusing its exact
filesystem-only lane-health probe (`_lane_health`, which checks
`.agents/delegation/.<lane>-down` flags and the codex quota-cooldown file)
rather than maintaining a second, independently-drifting copy of that
logic — see `scripts/ai/aq-role-route` for the source of truth on
availability signals.

Concrete model ids are resolved to real `config/model-coordinator.json`
`models` keys (the SSOT for lane -> model-id mapping); this module must
never hardcode a model id that is not an actual key there.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
_ROLE_ROUTE_PATH = REPO_ROOT / "scripts" / "ai" / "aq-role-route"
MODEL_COORDINATOR = REPO_ROOT / "config" / "model-coordinator.json"

# Fallback ladder, cheapest-eligible first, per DESIGN.md / aq-role-route's
# implementer eligibility order ("local -> codex -> claude"). Both L1 and L2
# walk the same ladder; only the concrete model id resolved at each lane
# differs by complexity (see _model_key_for_lane).
_LADDER: Tuple[str, ...] = ("local", "codex", "claude")

# Lane -> config/model-coordinator.json `models` key. These MUST be real
# keys in that file — verified against config/model-coordinator.json.
_LANE_MODEL_KEYS: Dict[str, str] = {
    "local": "llama-cpp-local",
    "codex": "codex",
}
# claude resolves to a different real key depending on complexity: L1
# (lightweight) -> claude-orchestrator, L2 (heavier reasoning) ->
# claude-reasoning. Both are real config/model-coordinator.json keys.
_CLAUDE_MODEL_FOR_COMPLEXITY: Dict[str, str] = {
    "L1": "claude-orchestrator",
    "L2": "claude-reasoning",
}
_DEFAULT_CLAUDE_MODEL = "claude-reasoning"


def _load_role_route():
    """Dynamically load aq-role-route (a script, not a package) so this
    module reuses its exact availability probe. Fails safe (returns None)
    if the script is missing/unparseable — callers then treat every lane
    as available rather than raising, matching aq-role-route's own
    fail-safe bias elsewhere (e.g. its lane-eligibility-registry fallback)."""
    try:
        loader = importlib.machinery.SourceFileLoader("aq_role_route", str(_ROLE_ROUTE_PATH))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        if spec is None:
            return None
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    except Exception:
        return None


_ROLE_ROUTE = _load_role_route()


def _lane_health(lane_id: str) -> Tuple[bool, Optional[str]]:
    """Return (available, unavailable_reason) for `lane_id`, reusing
    aq-role-route's `_lane_health` when it loaded successfully. If
    aq-role-route could not be loaded, fail safe by treating the lane as
    available (never crash the caller over a missing optional probe)."""
    if _ROLE_ROUTE is None:
        return True, None
    return _ROLE_ROUTE._lane_health(lane_id)


def estimate_task_complexity(query: str, tool_names: List[str] = []) -> str:
    """
    Estimate if a task is 'simple' (L1) or 'complex' (L2).

    Simple tasks (L1):
    - Triage (ls, grep, read_file)
    - File summaries
    - Status checks

    Complex tasks (L2):
    - Multi-file refactors
    - Planning
    - Architecture review
    """
    query_lower = query.lower()

    # Read-only or high-signal triage tools always route to L1
    l1_tools = {"ls", "grep", "read_file", "acat", "als", "agrep", "list_directory"}
    if any(tool in l1_tools for tool in tool_names):
        return "L1"

    # Keywords for L2 (Reasoning)
    l2_keywords = {"refactor", "plan", "design", "architecture", "implement", "fix", "debug"}
    if any(word in query_lower for word in l2_keywords):
        return "L2"

    # Default to L1 for short, simple queries
    if len(query.split()) < 15:
        return "L1"

    return "L2"


def _model_key_for_lane(lane: str, complexity: str) -> str:
    if lane == "claude":
        return _CLAUDE_MODEL_FOR_COMPLEXITY.get(complexity, _DEFAULT_CLAUDE_MODEL)
    return _LANE_MODEL_KEYS[lane]


def get_recommended_model_with_reason(complexity: str) -> Dict[str, Any]:
    """Health-aware complexity -> model-id resolution.

    Walks the `local -> codex -> claude` ladder and returns the first lane
    aq-role-route's health probe reports as available, recording a
    substitution reason when the preferred (first) lane is down. Never
    returns a lane the probe reports as unavailable while a healthy
    alternative exists on the ladder.
    """
    preferred = _LADDER[0]
    chosen_lane: Optional[str] = None
    reason: Optional[str] = None
    alternates: List[Dict[str, Any]] = []

    for lane in _LADDER:
        available, unavailable_reason = _lane_health(lane)
        if not available:
            alternates.append({"lane": lane, "unavailable_reason": unavailable_reason})
            continue
        if chosen_lane is None:
            chosen_lane = lane
            reason = (
                f"cheapest healthy lane for complexity={complexity}"
                if lane == preferred
                else (
                    f"preferred lane '{preferred}' unavailable; substituted '{lane}' "
                    "(next cheapest healthy lane on the local -> codex -> claude ladder)"
                )
            )

    if chosen_lane is None:
        # Fail closed rather than fabricate a healthy recommendation: every
        # ladder lane is down. Return the last-resort lane but say so
        # explicitly in `reason` so callers can detect and escalate.
        chosen_lane = _LADDER[-1]
        _, unavailable_reason = _lane_health(chosen_lane)
        reason = (
            f"all ladder lanes unavailable ({', '.join(a['lane'] for a in alternates)}); "
            f"last-resort '{chosen_lane}' returned ({unavailable_reason})"
        )

    model_id = _model_key_for_lane(chosen_lane, complexity)
    return {
        "model": model_id,
        "lane": chosen_lane,
        "complexity": complexity,
        "reason": reason,
        "alternates": alternates,
    }


def get_recommended_model(complexity: str) -> str:
    """Map complexity to a healthy, real config/model-coordinator.json
    model id. See `get_recommended_model_with_reason` for the full
    decision (lane, reason, alternates)."""
    return get_recommended_model_with_reason(complexity)["model"]
