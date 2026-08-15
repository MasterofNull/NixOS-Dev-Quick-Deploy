"""
loop_state.py — Durable loop state management for aq-loop.

Writes/reads .agent/collaboration/LOOP_STATE.json so loop iteration
context survives between inner-loop executions and context compactions.

Schema:
  loop_id        unique identifier for this loop run
  intent         the original user intent / task description
  iteration      current iteration number (1-based)
  max_iterations maximum iterations before escalation
  phase          TRIAGE | GROUND | EXECUTE | VERIFY | COMPLETE | ESCALATED
  history        list of per-iteration evidence dicts
  started_at     ISO timestamp when loop started
  last_updated   ISO timestamp of last state write
"""

from __future__ import annotations

import json
import hashlib
import re
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_PATH = _REPO_ROOT / ".agent" / "collaboration" / "LOOP_STATE.json"
_PULSE_PATH = _REPO_ROOT / ".agent" / "collaboration" / "PULSE.log"
_RESUME_PATH = _REPO_ROOT / ".agent" / "collaboration" / "RESUME.json"
_ARCHIVE_DIR = _REPO_ROOT / ".agent" / "archive"

PHASES = ("TRIAGE", "GROUND", "EXECUTE", "VERIFY", "COMPLETE", "ESCALATED")


@dataclass
class LoopIteration:
    iteration: int
    phase_entered: str
    completed: bool
    result_preview: str
    incomplete_markers: list[str]
    tool_calls: int
    elapsed_s: float


@dataclass
class LoopState:
    loop_id: str
    intent: str
    iteration: int
    max_iterations: int
    phase: str
    history: list[dict] = field(default_factory=list)
    review_repair: dict = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: _now())
    last_updated: str = field(default_factory=lambda: _now())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["last_updated"] = _now()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LoopState":
        h = d.pop("history", [])
        obj = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        obj.history = h
        return obj


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_state(state: LoopState) -> None:
    state.last_updated = _now()
    _tmp = _STATE_PATH.with_suffix(".tmp")
    _tmp.write_text(json.dumps(state.to_dict(), indent=2))
    _tmp.rename(_STATE_PATH)


def read_state() -> LoopState | None:
    if not _STATE_PATH.exists():
        return None
    try:
        d = json.loads(_STATE_PATH.read_text())
        return LoopState.from_dict(d)
    except Exception:
        return None


def archive_state(state: LoopState) -> None:
    """Move completed loop state to archive/."""
    ts = time.strftime("%Y%m%d")
    slug = state.loop_id.replace(":", "-")
    dst = _ARCHIVE_DIR / f"{ts}-{slug}.json"
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if _STATE_PATH.exists():
        shutil.copy2(_STATE_PATH, dst)
        _STATE_PATH.unlink(missing_ok=True)


def append_pulse(loop_id: str, iteration: int, phase: str, status: str, detail: str = "") -> None:
    ts = _now()
    agent = "aq-loop"
    line = f"[{ts}] [{agent}] [{phase}]: loop/{loop_id}/iter{iteration} — {status}"
    if detail:
        line += f" | {detail[:120]}"
    try:
        with open(_PULSE_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def update_resume(objective: str, phase: str, status: str, loop_id: str = "") -> None:
    try:
        d: dict = {}
        if _RESUME_PATH.exists():
            d = json.loads(_RESUME_PATH.read_text())
        d["current_objective"] = objective
        d["phase"] = phase
        d["resume_hint"] = f"aq-loop {loop_id}: {status}"
        _tmp = _RESUME_PATH.with_suffix(".tmp")
        _tmp.write_text(json.dumps(d, indent=2))
        _tmp.rename(_RESUME_PATH)
    except Exception:
        pass


def extract_evidence(result: dict) -> dict:
    """Extract compact evidence from an aq-agent-loop JSON result."""
    return {
        "task_id": result.get("task_id", ""),
        "status": result.get("status", ""),
        "success": result.get("success", False),
        "incomplete_result": result.get("incomplete_result", False),
        "tool_calls": len(result.get("tool_calls", [])),
        "elapsed_s": result.get("elapsed_seconds", 0),
        "result_preview": (result.get("result") or "")[:300],
        "error": (result.get("error") or "")[:200],
    }


def is_completed(result: dict) -> bool:
    """True if the inner loop produced a genuine completion signal."""
    if not result.get("success"):
        return False
    if result.get("incomplete_result"):
        return False
    r = (result.get("result") or "").strip()
    r_lower = r.lower()
    # Check first 3 non-empty lines for COMPLETED: signal (tolerates leading whitespace)
    for line in r.splitlines()[:3]:
        if line.strip().lower().startswith("completed:"):
            return True
    # Secondary: status=completed and result contains action evidence
    if result.get("status") == "completed" and (
        "commit" in r_lower or "fixed" in r_lower or "done" in r_lower
    ):
        return True
    return False


_REVIEW_SCOPE = ("subject_hash", "baseline_hash", "criteria_hash", "roster_hash", "policy_hash")


def consume_review_result(state: LoopState, review: object) -> tuple[str, dict]:
    """Fail-closed review gate; returns approved, repair, or escalated.

    A scope is immutable for automatic repair. Each invariant gets one replay;
    all blockers in a completed result form one batch.
    """
    if not isinstance(review, dict) or set(review) != {"verdict", "scope", "blockers"}:
        return "escalated", {"reason": "malformed_review"}
    scope, blockers, verdict = review["scope"], review["blockers"], review["verdict"]
    hex64 = lambda value: isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
    if verdict not in {"APPROVED", "REJECTED"} or not isinstance(scope, dict) or set(scope) != set(_REVIEW_SCOPE) or any(not hex64(scope[k]) for k in _REVIEW_SCOPE) or not isinstance(blockers, list):
        return "escalated", {"reason": "unknown_or_concerns_review"}
    normalized = []
    for finding in blockers:
        if not isinstance(finding, dict) or set(finding) != {"invariant_id", "finding_hash"} or not isinstance(finding["invariant_id"], str) or not finding["invariant_id"] or not hex64(finding["finding_hash"]):
            return "escalated", {"reason": "malformed_finding"}
        normalized.append(finding)
    if verdict == "APPROVED":
        return ("approved", {}) if not normalized else ("escalated", {"reason": "approved_with_blockers"})
    if not normalized:
        return "escalated", {"reason": "rejected_without_blockers"}
    stored_scope = state.review_repair.get("scope")
    if stored_scope is not None and stored_scope != scope:
        return "escalated", {"reason": "scope_drift"}
    state.review_repair.setdefault("scope", scope)
    counters = state.review_repair.setdefault("replays", {})
    ids = sorted({item["invariant_id"] for item in normalized})
    repeated = [item for item in ids if counters.get(item, 0) >= 1]
    batch_hash = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if repeated:
        signals = state.review_repair.setdefault("issue_signals", [])
        signal = hashlib.sha256(("|".join(repeated) + batch_hash).encode()).hexdigest()
        if signal not in signals: signals.append(signal)
        return "escalated", {"reason": "invariant_recurrence", "invariants": repeated, "signal": signal}
    for invariant in ids: counters[invariant] = 1
    state.review_repair.setdefault("batches", []).append({"batch_hash": batch_hash, "findings": normalized})
    return "repair", {"batch_hash": batch_hash, "findings": normalized}
