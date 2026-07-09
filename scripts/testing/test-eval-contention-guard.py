#!/usr/bin/env python3
"""Prompt-5: the eval loop must never poison itself with slot-contention noise.

Covers: (1) _slot_contended reads scheduler-state.json + /slots; (2) the
health-spider regression check excludes deferred/degraded_infra runs (pass_rate
None) and compares the last two REAL evals.

Run: python3 scripts/testing/test-eval-contention-guard.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def _load(script):
    loader = importlib.machinery.SourceFileLoader(script.replace("-", "_"), str(REPO / "scripts" / "ai" / script))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(m)
    return m


def test_slot_contended_running_job():
    tl = _load("aq-local-training-loop")
    with tempfile.TemporaryDirectory() as d:
        state = Path(d) / "scheduler-state.json"
        state.write_text(json.dumps({"running": {"id": "1234:job"}, "queue": []}))
        tl._SCHEDULER_STATE = state
        contended, why = tl._slot_contended()
        assert contended is True and "held by" in why, why
        print(f"PASS slot contended when a job holds the slot ({why[:40]}...)")


def test_slot_free_when_no_state_and_no_llama():
    tl = _load("aq-local-training-loop")
    with tempfile.TemporaryDirectory() as d:
        tl._SCHEDULER_STATE = Path(d) / "absent.json"
        # No llama at a bogus port -> probe fails -> fail-open (not contended).
        os.environ["LLAMA_CPP_BASE_URL"] = "http://127.0.0.1:59999"
        tl.LLAMA_BASE_URL = "http://127.0.0.1:59999"
        contended, why = tl._slot_contended()
        assert contended is False, f"must fail-open when surfaces absent: {why}"
        print("PASS fail-open (not contended) when state + llama absent")


def test_queue_depth_contention():
    tl = _load("aq-local-training-loop")
    with tempfile.TemporaryDirectory() as d:
        state = Path(d) / "s.json"
        state.write_text(json.dumps({"running": None, "queue": [{"id": "a"}, {"id": "b"}]}))
        tl._SCHEDULER_STATE = state
        tl.SLOT_CONTENTION_QUEUE_MAX = 0
        contended, why = tl._slot_contended()
        assert contended is True and "depth" in why, why
        print("PASS queue depth beyond threshold = contended")


def test_regression_excludes_infra_runs():
    hs = _load("aq-health-spider")
    # Two real evals with a big drop, but a deferred run interleaved last.
    results = [
        {"run_id": "r1", "pass_rate": 0.92, "status": "healthy"},
        {"run_id": "r2", "pass_rate": 0.30, "status": "eval_failed"},   # real regression
        {"run_id": "r3", "pass_rate": None, "status": "deferred"},       # infra noise (latest)
    ]
    reg = hs._loop_eval_regression(results)
    assert reg is not None, "should still detect the r1->r2 real regression despite trailing deferred"
    assert reg["previous_run"] == "r1" and reg["latest_run"] == "r2", reg
    print("PASS regression compares last two REAL evals, ignores trailing deferred")


def test_no_false_regression_from_contention_zero():
    hs = _load("aq-health-spider")
    # A healthy run then a degraded_infra run must NOT read as a collapse.
    results = [
        {"run_id": "r1", "pass_rate": 0.9, "status": "healthy"},
        {"run_id": "r2", "pass_rate": None, "status": "degraded_infra"},
    ]
    assert hs._loop_eval_regression(results) is None, "degraded_infra must not fake a regression"
    print("PASS degraded_infra run does not fake a regression")


if __name__ == "__main__":
    test_slot_contended_running_job()
    test_slot_free_when_no_state_and_no_llama()
    test_queue_depth_contention()
    test_regression_excludes_infra_runs()
    test_no_false_regression_from_contention_zero()
    print("ALL PASS")
