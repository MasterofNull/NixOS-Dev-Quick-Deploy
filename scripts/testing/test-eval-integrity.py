#!/usr/bin/env python3
"""Tests for R1.3 eval integrity gate — the gate must certify a trustworthy
scorer AND reject untrustworthy ones (RSI-Readiness R1).

The headline: a scorer that can't tell good from bad, or is noisy, or scores
infra-noise, or is gameable, must FAIL the gate. Otherwise the whole RSI loop
optimizes toward a corrupt signal.

Run: python3 scripts/testing/test-eval-integrity.py
"""

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import eval_integrity as EI  # noqa: E402

GOLDEN_DIR = REPO / "data" / "golden"
GOLDEN = json.loads((GOLDEN_DIR / "tasks.json").read_text())


def test_reference_scorer_is_trustworthy():
    res = EI.trustworthiness_gate(EI.exec_scorer, GOLDEN, str(GOLDEN_DIR))
    assert res.trustworthy, res.reason
    assert res.discrimination["ok"] and res.determinism["ok"]
    assert res.abstention["ok"] and res.isolation["ok"]
    print(f"PASS reference exec_scorer certified TRUSTWORTHY (min margin {res.discrimination['min_margin']})")


def test_gate_rejects_nondiscriminating_scorer():
    # A scorer that always returns 1.0 can't tell good from bad.
    flat = lambda resp, task: {"score": 1.0, "abstain": False}
    res = EI.trustworthiness_gate(flat, GOLDEN, str(GOLDEN_DIR))
    assert not res.trustworthy and not res.discrimination["ok"]
    print("PASS gate REJECTS a non-discriminating scorer (always-1.0)")


def test_gate_rejects_nondeterministic_scorer():
    noisy = lambda resp, task: {"score": random.random(), "abstain": False}
    res = EI.trustworthiness_gate(noisy, GOLDEN, str(GOLDEN_DIR))
    assert not res.trustworthy and not res.determinism["ok"]
    print(f"PASS gate REJECTS a non-deterministic scorer (stdev {res.determinism['max_stdev']})")


def test_gate_rejects_infra_noise_scorer():
    # A scorer that scores empty/timeout as 0 (a capability miss) instead of abstaining.
    def no_abstain(resp, task):
        return {"score": 0.0, "abstain": False}
    res = EI.trustworthiness_gate(no_abstain, GOLDEN, str(GOLDEN_DIR))
    assert not res.trustworthy and not res.abstention["ok"]
    print("PASS gate REJECTS a scorer that grades infra-noise as a capability miss")


def test_gate_rejects_unisolated_golden(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "tasks.json").write_text("[]")  # no .agent-no-read marker
        res = EI.isolation_check(d)
        assert not res["ok"] and "no-read" in res["reason"]
    print("PASS gate REFUSES to certify when golden set is agent-readable (anti-gaming)")


def test_exec_scorer_abstains_on_noise():
    for noise in ("", "Queued behind busy local inference slot: timeout", "[Error: disk full]"):
        r = EI.exec_scorer(noise, GOLDEN[0])
        assert r["abstain"], f"should abstain on: {noise!r}"
    print("PASS exec_scorer abstains on infra-noise (contention can't fake a regression)")


def test_exec_scorer_discriminates_per_type():
    for task in GOLDEN:
        sg = EI.exec_scorer(task["reference_good"], task)["score"]
        sb = EI.exec_scorer(task["reference_bad"], task)["score"]
        assert sg > sb, f"{task['id']}: good {sg} !> bad {sb}"
    print("PASS exec_scorer ranks good>bad across json_parse / py_compile / keyword")


if __name__ == "__main__":
    test_reference_scorer_is_trustworthy()
    test_gate_rejects_nondiscriminating_scorer()
    test_gate_rejects_nondeterministic_scorer()
    test_gate_rejects_infra_noise_scorer()
    test_gate_rejects_unisolated_golden()
    test_exec_scorer_abstains_on_noise()
    test_exec_scorer_discriminates_per_type()
    print("ALL PASS")
