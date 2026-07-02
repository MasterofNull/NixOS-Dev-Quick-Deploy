#!/usr/bin/env python3
"""Unit tests for switchboard Phase B adaptive local output budget.

Verifies _adaptive_local_output_budget() decision logic in isolation (no live
service): non-reasoning unaffected, reasoning clamps under contention, idle allows
the fuller budget, and a caller-supplied smaller max_tokens is always respected.
"""
import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SB = _REPO / "ai-stack" / "switchboard" / "switchboard.py"


def _load_fn():
    # Load only the target function's source without importing the whole FastAPI app
    # (which pulls heavy deps). Extract and exec the pure helper.
    src = _SB.read_text()
    start = src.index("def _adaptive_local_output_budget(")
    end = src.index("def _apply_local_thinking_profile(")
    snippet = src[start:end]
    ns: dict = {}
    exec(compile(snippet, str(_SB), "exec"), ns)
    return ns["_adaptive_local_output_budget"]


def main() -> int:
    f = _load_fn()
    IDLE, BUSY = 1200, 400
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got}, want {want}")

    # Non-reasoning: always unchanged.
    check("nonreasoning_busy", f(False, True, 999, IDLE, BUSY), 999)
    check("nonreasoning_idle", f(False, False, 999, IDLE, BUSY), 999)
    check("nonreasoning_none", f(False, True, None, IDLE, BUSY), None)

    # Reasoning + busy -> clamp to busy ceiling.
    check("reasoning_busy_big", f(True, True, 5000, IDLE, BUSY), BUSY)
    check("reasoning_busy_none", f(True, True, None, IDLE, BUSY), BUSY)

    # Reasoning + idle -> allow up to idle ceiling.
    check("reasoning_idle_big", f(True, False, 5000, IDLE, BUSY), IDLE)
    check("reasoning_idle_none", f(True, False, None, IDLE, BUSY), IDLE)

    # Caller-supplied smaller value is always respected (never raised).
    check("reasoning_idle_small", f(True, False, 100, IDLE, BUSY), 100)
    check("reasoning_busy_small", f(True, True, 100, IDLE, BUSY), 100)

    if failures:
        print("FAIL: adaptive local budget")
        for x in failures:
            print("  " + x)
        return 1
    print("ok switchboard adaptive local output budget (9 cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
