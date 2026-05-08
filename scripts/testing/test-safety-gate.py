#!/usr/bin/env python3
"""Phase 28 — unit tests for safety_gate.py + LifecycleSession.safety_mode"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))
from workflow.safety_gate import evaluate, GateResult
from extensions.blast_radius_classifier import classify

PASS = 0
FAIL = 0


def check(label: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


# Minimal LifecycleSession stub — only the fields safety_gate uses
@dataclass
class _StubSession:
    session_id: str = "test-session"
    safety_mode: str = "open"
    safety_gate_log: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


print("=== safety_gate evaluate() ===\n")

# ─── open mode ─────────────────────────────────────────────────────────────
print("[open mode — allow all]")
s = _StubSession(safety_mode="open")
r = evaluate(s, ["rm -rf /", "git push --force", "cat README.md"])
check("open: allowed=True even with critical",  r.allowed is True)
check("open: blocked_actions empty",            r.blocked_actions == [])
check("open: queued_actions empty",             r.queued_actions == [])
check("open: gate_log entry appended",          len(s.safety_gate_log) == 1)
check("open: gate_log mode=open",               s.safety_gate_log[0]["mode"] == "open")

# ─── open mode with no actions ─────────────────────────────────────────────
print("\n[open mode — empty actions]")
s2 = _StubSession(safety_mode="open")
r2 = evaluate(s2, [])
check("empty: allowed=True",                   r2.allowed is True)

# ─── open mode from session.context ────────────────────────────────────────
print("\n[open mode — actions from session.context]")
s3 = _StubSession(safety_mode="open", context={"delegation_actions": ["git status"]})
r3 = evaluate(s3)   # no explicit actions arg
check("context actions: allowed=True",         r3.allowed is True)
check("context actions: tiers has git status", "git status" in r3.tiers)

# ─── review mode ───────────────────────────────────────────────────────────
print("\n[review mode — high queued, critical blocked]")
s4 = _StubSession(safety_mode="review")
r4 = evaluate(s4, ["git push origin main", "cat README.md"])
check("review: high queued",                   "git push origin main" in r4.queued_actions)
check("review: low not queued",                "cat README.md" not in r4.queued_actions)
check("review: allowed=False (queued items)",  r4.allowed is False)

s5 = _StubSession(safety_mode="review")
r5 = evaluate(s5, ["nixos-rebuild switch", "git push"])
check("review: critical blocked",              "nixos-rebuild switch" in r5.blocked_actions)
check("review: allowed=False (critical)",      r5.allowed is False)

s6 = _StubSession(safety_mode="review")
r6 = evaluate(s6, ["cat README.md", "ls -la", "git status"])
check("review: all low → allowed=True",        r6.allowed is True)
check("review: all low → no queued",           r6.queued_actions == [])

# ─── strict mode ───────────────────────────────────────────────────────────
print("\n[strict mode — medium+ blocked, only low passes]")
s7 = _StubSession(safety_mode="strict")
r7 = evaluate(s7, ["git commit -m 'fix'", "cat README.md"])
check("strict: medium blocked",                "git commit -m 'fix'" in r7.blocked_actions)
check("strict: allowed=False (medium)",        r7.allowed is False)

s8 = _StubSession(safety_mode="strict")
r8 = evaluate(s8, ["nixos-rebuild switch"])
check("strict: critical blocked",              "nixos-rebuild switch" in r8.blocked_actions)
check("strict: allowed=False (critical)",      r8.allowed is False)

s9 = _StubSession(safety_mode="strict")
r9 = evaluate(s9, ["cat README.md", "ls -la", "aq-qa 0", "git status"])
check("strict: all low → allowed=True",        r9.allowed is True)
check("strict: all low → no blocked",          r9.blocked_actions == [])

# ─── GateResult tiers populated ────────────────────────────────────────────
print("\n[GateResult.tiers populated]")
s10 = _StubSession(safety_mode="open")
r10 = evaluate(s10, ["git push", "cat f"])
check("tiers: git push → high",               r10.tiers.get("git push") == "high")
check("tiers: cat f → low",                   r10.tiers.get("cat f") == "low")

# ─── gate_log accumulation ─────────────────────────────────────────────────
print("\n[gate_log accumulates across calls]")
s11 = _StubSession(safety_mode="review")
evaluate(s11, ["git push"])
evaluate(s11, ["cat f"])
check("gate_log: 2 entries after 2 calls",    len(s11.safety_gate_log) == 2)
check("gate_log: ts is float",                isinstance(s11.safety_gate_log[0]["ts"], float))

# ─── unknown mode defaults to open ─────────────────────────────────────────
print("\n[unknown mode defaults to open]")
s12 = _StubSession(safety_mode="guardian")
r12 = evaluate(s12, ["rm -rf /"])
check("unknown mode: allowed=True",            r12.allowed is True)

# ─── LifecycleSession backward compat fields ───────────────────────────────
print("\n[LifecycleSession backward compat]")
from workflow.lifecycle_fsm import LifecycleSession
ls = LifecycleSession.from_dict({
    "session_id": "old-session",
    "caller": "test",
    "prompt": "test prompt",
    "complexity": "simple",
    "domain": "python",
    "sequence": ["intake", "delegate", "validate", "done"],
    "current_phase": "intake",
    "created_at": 1000.0,
    "updated_at": 1000.0,
    # safety_mode and safety_gate_log intentionally absent
})
check("from_dict: safety_mode defaults to open",   ls.safety_mode == "open")
check("from_dict: safety_gate_log defaults empty", ls.safety_gate_log == [])

print(f"\n{'='*40}")
print(f"Result: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
