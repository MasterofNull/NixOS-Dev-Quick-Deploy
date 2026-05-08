"""
Phase 28 — DELEGATE phase safety gate.

Evaluates session actions against the session's safety_mode before the
DELEGATE → VALIDATE transition is allowed.

Safety modes:
  open   — allow all (no-op, default — no regression for existing sessions)
  review — high → PRSI queue; critical → block (ABORTED)
  strict — medium+ → block (ABORTED); only low passes
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow.lifecycle_fsm import LifecycleSession

# Import classifier — tolerates missing module at startup so imports don't
# fail if the extensions package hasn't been loaded yet.
try:
    from extensions.blast_radius_classifier import classify, max_tier
except ImportError:  # pragma: no cover
    def classify(action: str) -> str:  # type: ignore[misc]
        return "medium"
    def max_tier(actions: list[str]) -> str:  # type: ignore[misc]
        return "medium"


_TIER_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class GateResult:
    allowed: bool
    blocked_actions: list[str] = field(default_factory=list)
    queued_actions: list[str] = field(default_factory=list)
    reason: str = ""
    tiers: dict[str, str] = field(default_factory=dict)   # action → tier


def evaluate(session: "LifecycleSession", actions: list[str] | None = None) -> GateResult:
    """Evaluate a list of actions against the session's safety_mode.

    args:
        session: LifecycleSession with a .safety_mode and .safety_gate_log
        actions: action strings to evaluate; if None, extracted from
                 session.context['delegation_actions'] (if present)

    Returns GateResult; also appends a log entry to session.safety_gate_log.
    """
    if actions is None:
        actions = list(session.context.get("delegation_actions") or [])

    mode = getattr(session, "safety_mode", "open")
    result = _apply_policy(mode, actions)

    log_entry: dict[str, Any] = {
        "ts": time.time(),
        "mode": mode,
        "allowed": result.allowed,
        "tiers": result.tiers,
        "blocked": result.blocked_actions,
        "queued": result.queued_actions,
        "reason": result.reason,
    }
    gate_log = getattr(session, "safety_gate_log", None)
    if gate_log is not None:
        gate_log.append(log_entry)

    return result


def _apply_policy(mode: str, actions: list[str]) -> GateResult:
    if not actions:
        return GateResult(allowed=True, reason="no actions to evaluate")

    tiers = {a: classify(a) for a in actions}

    if mode == "open":
        return GateResult(allowed=True, tiers=tiers, reason="open mode — all actions allowed")

    blocked: list[str] = []
    queued: list[str] = []

    if mode == "review":
        for action, tier in tiers.items():
            if tier == "critical":
                blocked.append(action)
            elif tier == "high":
                queued.append(action)
        if blocked:
            return GateResult(
                allowed=False,
                blocked_actions=blocked,
                queued_actions=queued,
                tiers=tiers,
                reason=f"review mode — {len(blocked)} critical action(s) blocked",
            )
        return GateResult(
            allowed=len(queued) == 0,
            queued_actions=queued,
            tiers=tiers,
            reason=f"review mode — {len(queued)} high action(s) queued for PRSI approval"
            if queued else "review mode — all actions within threshold",
        )

    if mode == "strict":
        threshold_order = _TIER_ORDER["medium"]  # medium and above blocked
        for action, tier in tiers.items():
            if _TIER_ORDER.get(tier, 2) <= threshold_order:
                blocked.append(action)
        if blocked:
            return GateResult(
                allowed=False,
                blocked_actions=blocked,
                tiers=tiers,
                reason=f"strict mode — {len(blocked)} medium+ action(s) blocked",
            )
        return GateResult(allowed=True, tiers=tiers, reason="strict mode — all actions are low risk")

    # Unknown mode — treat as open but log it
    return GateResult(allowed=True, tiers=tiers, reason=f"unknown mode '{mode}' — defaulting to open")
