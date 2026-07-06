#!/usr/bin/env python3
"""Unit tests for aq-sequential-edit orchestration (pure logic, mocked dispatch).

Verifies the decomposer sequences single-edit sub-tasks, validates between steps,
retries within budget, and stops on unrecoverable failure — without any LLM call.
"""
import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_path = ROOT / "scripts" / "ai" / "aq-sequential-edit"
_loader = SourceFileLoader("aq_sequential_edit", str(_path))
_spec = importlib.util.spec_from_loader("aq_sequential_edit", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def test_all_steps_pass():
    calls = []
    manifest = {"target": "f.py", "steps": [{"name": "a", "prompt": "x"}, {"name": "b", "prompt": "y"}]}
    r = mod.run_manifest(
        manifest,
        dispatch=lambda p, t: calls.append(p) or {"ok": True},
        validate=lambda tgt: True,
        log=lambda *_: None,
    )
    if not r["success"] or r["completed"] != 2:
        _fail(f"expected 2/2 success, got {r}")
    if len(calls) != 2:
        _fail(f"expected 2 dispatches, got {len(calls)}")
    # Each prompt must be scoped to ONE edit (the decomposition contract).
    if not all("exactly ONE edit" in c for c in calls):
        _fail("sub-prompts not single-edit scoped")
    print("PASS  all steps pass -> success 2/2, single-edit scoped")


def test_retry_then_succeed():
    attempts = {"n": 0}
    def dispatch(p, t):
        attempts["n"] += 1
        return {"ok": attempts["n"] >= 2}  # fail first, pass second
    r = mod.run_manifest(
        {"target": "f.py", "steps": [{"name": "a", "prompt": "x"}]},
        dispatch=dispatch, validate=lambda tgt: True, retries=2, log=lambda *_: None,
    )
    if not r["success"] or attempts["n"] != 2:
        _fail(f"expected success after 1 retry, got success={r['success']} attempts={attempts['n']}")
    print("PASS  retry-then-succeed within budget")


def test_stop_on_persistent_failure():
    attempts = {"n": 0}
    def dispatch(p, t):
        attempts["n"] += 1
        return {"ok": False}
    r = mod.run_manifest(
        {"target": "f.py", "steps": [{"name": "a", "prompt": "x"}, {"name": "b", "prompt": "y"}]},
        dispatch=dispatch, validate=lambda tgt: True, retries=2, log=lambda *_: None,
    )
    if r["success"]:
        _fail("should have failed on persistent step failure")
    if r["completed"] != 0:
        _fail(f"should stop at step 1 (completed=0), got {r['completed']}")
    if attempts["n"] != 3:  # 1 + 2 retries, then stop (never dispatch step b)
        _fail(f"expected 3 attempts then stop, got {attempts['n']}")
    print("PASS  stop-on-failure: step 2 never dispatched after step 1 exhausts retries")


def test_validation_gate_blocks_bad_edit():
    # dispatch says ok, but validation (compile) fails -> step must not pass.
    r = mod.run_manifest(
        {"target": "f.py", "steps": [{"name": "a", "prompt": "x"}]},
        dispatch=lambda p, t: {"ok": True}, validate=lambda tgt: False, retries=1,
        log=lambda *_: None,
    )
    if r["success"]:
        _fail("validation failure should block step success")
    print("PASS  validation gate blocks a bad edit even when dispatch reports ok")


if __name__ == "__main__":
    test_all_steps_pass()
    test_retry_then_succeed()
    test_stop_on_persistent_failure()
    test_validation_gate_blocks_bad_edit()
    print("\n4/4 orchestration tests passed")
