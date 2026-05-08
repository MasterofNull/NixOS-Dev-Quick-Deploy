"""
Lifecycle FSM for the Unified Agent Orchestration Gateway (Phase 26).

8 deterministic phases drive every user-initiated task:
  INTAKE → DISCOVER → PRD → PLAN → ASSIGN → DELEGATE → VALIDATE → COMMIT → DONE

Sessions are persisted as JSONL under DATA_DIR/lifecycle/.
Context pruning is applied at each phase boundary so sub-agents only receive
relevant information — never the full search history or unrelated tool output.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Phase registry
# ---------------------------------------------------------------------------

class LifecyclePhase(str, Enum):
    INTAKE   = "intake"    # Normalize caller + prompt; detect complexity + domain
    DISCOVER = "discover"  # Codebase scan, health check, existing plans
    PRD      = "prd"       # Generate/locate PRD; scope the work
    PLAN     = "plan"      # Phased execution plan + tool assignments
    ASSIGN   = "assign"    # Match agents/teams to each plan phase
    DELEGATE = "delegate"  # Execute via delegated agents/teams
    VALIDATE = "validate"  # aq-qa, syntax checks, test gates
    COMMIT   = "commit"    # Guided commit + tier0-validation-gate
    DONE     = "done"      # Terminal: all phases complete
    ABORTED  = "aborted"   # Terminal: user cancelled or safety block


# Ordered sequence for a full lifecycle run
FULL_SEQUENCE: List[LifecyclePhase] = [
    LifecyclePhase.INTAKE,
    LifecyclePhase.DISCOVER,
    LifecyclePhase.PRD,
    LifecyclePhase.PLAN,
    LifecyclePhase.ASSIGN,
    LifecyclePhase.DELEGATE,
    LifecyclePhase.VALIDATE,
    LifecyclePhase.COMMIT,
    LifecyclePhase.DONE,
]

# Simple tasks skip DISCOVER + PRD (no codebase search needed)
SIMPLE_SEQUENCE: List[LifecyclePhase] = [
    LifecyclePhase.INTAKE,
    LifecyclePhase.PLAN,
    LifecyclePhase.ASSIGN,
    LifecyclePhase.DELEGATE,
    LifecyclePhase.VALIDATE,
    LifecyclePhase.COMMIT,
    LifecyclePhase.DONE,
]

# Domain-delegated tasks enter after planning (called by domain_router)
DOMAIN_SEQUENCE: List[LifecyclePhase] = [
    LifecyclePhase.ASSIGN,
    LifecyclePhase.DELEGATE,
    LifecyclePhase.VALIDATE,
    LifecyclePhase.COMMIT,
    LifecyclePhase.DONE,
]

TERMINAL_PHASES = {LifecyclePhase.DONE, LifecyclePhase.ABORTED}

# ---------------------------------------------------------------------------
# Context pruning: per-phase relevance filters
# ---------------------------------------------------------------------------

# Keys whose values are carried forward into every subsequent phase
_ALWAYS_FORWARD = {"session_id", "caller", "prompt", "complexity", "domain"}

# Per-phase: which context keys produced in that phase to carry into the next
_PHASE_OUTPUT_KEYS: Dict[str, List[str]] = {
    "intake":   ["complexity", "domain", "caller_profile", "intent_summary"],
    "discover": ["codebase_summary", "existing_plans", "health_status", "relevant_files"],
    "prd":      ["prd_title", "prd_scope", "acceptance_checks", "out_of_scope"],
    "plan":     ["phases", "tool_assignments", "domain_hints", "estimated_complexity"],
    "assign":   ["agent_assignments", "team_routing", "capability_map"],
    "delegate": ["delegation_results", "artifacts_created", "sub_agent_summaries"],
    "validate": ["validation_passed", "validation_errors", "qa_score"],
    "commit":   ["commit_sha", "files_changed", "commit_message"],
}


def prune_context_for_phase(
    full_context: Dict[str, Any], target_phase: str
) -> Dict[str, Any]:
    """Return only context keys relevant for the given target phase.

    Sub-agents receive this pruned dict, not the full accumulated context.
    This prevents irrelevant search results, unrelated tool outputs, and
    previous-phase noise from inflating the prompt context.
    """
    pruned: Dict[str, Any] = {}

    # Always include session identity
    for k in _ALWAYS_FORWARD:
        if k in full_context:
            pruned[k] = full_context[k]

    # Determine which phases have completed and include their output keys
    phase_order = [p.value for p in FULL_SEQUENCE]
    try:
        target_idx = phase_order.index(target_phase)
    except ValueError:
        target_idx = len(phase_order)

    for phase_name, output_keys in _PHASE_OUTPUT_KEYS.items():
        try:
            phase_idx = phase_order.index(phase_name)
        except ValueError:
            continue
        if phase_idx < target_idx:
            for k in output_keys:
                if k in full_context:
                    pruned[k] = full_context[k]

    return pruned


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PhaseRecord:
    phase: str
    status: str                      # pending | running | passed | failed | skipped
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    agent: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    output_summary: Optional[str] = None
    error: Optional[str] = None
    context_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleSession:
    session_id: str
    caller: str               # continue | codex-ext | claude-ext | raw-api | ...
    prompt: str
    complexity: str           # simple | standard | complex
    domain: Optional[str]     # nixos | python | security | trading | design | infra | general
    sequence: List[str]       # ordered phase names for this session
    current_phase: str
    created_at: float
    updated_at: float
    phases: List[PhaseRecord] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    delegations: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    # Phase 28 — guarded execution
    safety_mode: str = "open"            # open | review | strict
    safety_gate_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LifecycleSession":
        phases_raw = data.pop("phases", [])
        # Backward compat: sessions persisted before Phase 28 lack these fields
        data.setdefault("safety_mode", "open")
        data.setdefault("safety_gate_log", [])
        inst = cls(**data)
        inst.phases = [PhaseRecord(**p) for p in phases_raw]
        return inst

    def current_phase_record(self) -> Optional[PhaseRecord]:
        for p in self.phases:
            if p.phase == self.current_phase:
                return p
        return None

    def pruned_context_for_current_phase(self) -> Dict[str, Any]:
        return prune_context_for_phase(self.context, self.current_phase)

    def next_phase(self) -> Optional[str]:
        """Return the next phase in this session's sequence, or None if at terminal."""
        try:
            idx = self.sequence.index(self.current_phase)
            if idx + 1 < len(self.sequence):
                return self.sequence[idx + 1]
        except ValueError:
            pass
        return None

    def phase_summary(self) -> List[Dict[str, Any]]:
        """Compact list of phase status for display."""
        records = {p.phase: p for p in self.phases}
        result = []
        for phase_name in self.sequence:
            rec = records.get(phase_name)
            result.append({
                "phase": phase_name,
                "status": rec.status if rec else "pending",
                "agent": rec.agent if rec else None,
                "output_summary": rec.output_summary if rec else None,
            })
        return result


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

_lifecycle_dir: Optional[Path] = None


def init(lifecycle_dir: Path) -> None:
    global _lifecycle_dir
    _lifecycle_dir = lifecycle_dir
    lifecycle_dir.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    assert _lifecycle_dir is not None, "lifecycle_fsm.init() not called"
    return _lifecycle_dir / f"{session_id}.json"


def _write_session(session: LifecycleSession) -> None:
    session.updated_at = time.time()
    path = _session_path(session.session_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(session.to_dict(), indent=2))
    tmp.rename(path)


def _read_session(session_id: str) -> Optional[LifecycleSession]:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return LifecycleSession.from_dict(data)
    except Exception as exc:
        logger.warning("lifecycle_fsm: failed to read session %s: %s", session_id, exc)
        return None


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

def _select_sequence(complexity: str) -> List[str]:
    if complexity == "simple":
        return [p.value for p in SIMPLE_SEQUENCE]
    return [p.value for p in FULL_SEQUENCE]


def create_session(
    *,
    caller: str,
    prompt: str,
    complexity: str = "standard",
    domain: Optional[str] = None,
    entry_phase: Optional[str] = None,
) -> LifecycleSession:
    """Create and persist a new lifecycle session."""
    sequence = _select_sequence(complexity)
    start_phase = entry_phase or sequence[0]

    session = LifecycleSession(
        session_id=str(uuid.uuid4()),
        caller=caller,
        prompt=prompt,
        complexity=complexity,
        domain=domain,
        sequence=sequence,
        current_phase=start_phase,
        created_at=time.time(),
        updated_at=time.time(),
        phases=[PhaseRecord(phase=p, status="pending") for p in sequence],
        context={"caller": caller, "prompt": prompt, "complexity": complexity, "domain": domain},
    )
    _write_session(session)
    logger.info("lifecycle_fsm: created session %s caller=%s complexity=%s phase=%s",
                session.session_id, caller, complexity, start_phase)
    return session


def get_session(session_id: str) -> Optional[LifecycleSession]:
    return _read_session(session_id)


def list_sessions(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent sessions sorted by updated_at descending."""
    if _lifecycle_dir is None:
        return []
    sessions = []
    for path in sorted(_lifecycle_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text())
            sessions.append({
                "session_id": data.get("session_id"),
                "caller": data.get("caller"),
                "current_phase": data.get("current_phase"),
                "complexity": data.get("complexity"),
                "domain": data.get("domain"),
                "updated_at": data.get("updated_at"),
                "prompt_preview": (data.get("prompt", "") or "")[:80],
            })
        except Exception:
            continue
    return sessions


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------

def start_phase(session: LifecycleSession, phase: str, agent: Optional[str] = None) -> LifecycleSession:
    """Mark a phase as running and record which agent is handling it."""
    for rec in session.phases:
        if rec.phase == phase:
            rec.status = "running"
            rec.started_at = time.time()
            rec.agent = agent
            # Snapshot only the relevant context for this phase
            rec.context_snapshot = session.pruned_context_for_current_phase()
            break
    session.current_phase = phase
    _write_session(session)
    return session


def complete_phase(
    session: LifecycleSession,
    phase: str,
    *,
    status: str = "passed",
    output_summary: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
    context_updates: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> LifecycleSession:
    """Complete a phase and advance to the next one.

    context_updates contains only the KEY OUTPUTS from this phase — not the
    full tool output. Callers must extract the relevant summary before calling.
    """
    for rec in session.phases:
        if rec.phase == phase:
            rec.status = status
            rec.completed_at = time.time()
            rec.output_summary = output_summary
            rec.tools_used = tools_used or []
            rec.error = error
            break

    # Merge only the structured outputs into session context
    if context_updates:
        session.context.update(context_updates)

    # Advance to next phase
    next_p = session.next_phase()
    if next_p and status == "passed":
        session.current_phase = next_p
    elif status == "failed" and error:
        session.current_phase = LifecyclePhase.ABORTED.value
    elif next_p is None and status == "passed":
        session.current_phase = LifecyclePhase.DONE.value

    _write_session(session)
    logger.info("lifecycle_fsm: session %s phase=%s→%s status=%s",
                session.session_id, phase, session.current_phase, status)
    return session


def skip_phase(session: LifecycleSession, phase: str, reason: str) -> LifecycleSession:
    """Skip a phase (e.g., DISCOVER for simple tasks)."""
    return complete_phase(session, phase, status="skipped", output_summary=reason)


def abort_session(session: LifecycleSession, reason: str) -> LifecycleSession:
    """Abort the session (user cancel or safety block)."""
    session.current_phase = LifecyclePhase.ABORTED.value
    session.context["abort_reason"] = reason
    _write_session(session)
    return session


def is_terminal(session: LifecycleSession) -> bool:
    return session.current_phase in (LifecyclePhase.DONE.value, LifecyclePhase.ABORTED.value)


# ---------------------------------------------------------------------------
# Complexity detection heuristic
# ---------------------------------------------------------------------------

_SIMPLE_PATTERNS = [
    "fix typo", "add comment", "rename", "update version", "bump version",
    "fix spelling", "format", "whitespace", "trailing comma",
]

_COMPLEX_PATTERNS = [
    "refactor", "migrate", "architecture", "overhaul", "redesign", "revamp",
    "phase ", "multi-agent", "new service", "new module", "new system",
]


def detect_complexity(prompt: str) -> str:
    """Heuristic complexity classification: simple | standard | complex."""
    lower = prompt.lower()
    for pat in _COMPLEX_PATTERNS:
        if pat in lower:
            return "complex"
    for pat in _SIMPLE_PATTERNS:
        if pat in lower:
            return "simple"
    word_count = len(prompt.split())
    if word_count < 10:
        return "simple"
    if word_count > 100:
        return "complex"
    return "standard"
