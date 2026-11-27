#!/usr/bin/env python3
"""Tests for R1.3 eval integrity gate — the gate must certify a trustworthy
scorer AND reject untrustworthy ones (RSI-Readiness R1).

The headline: a scorer that can't tell good from bad, or is noisy, or scores
infra-noise, or is gameable, must FAIL the gate. Otherwise the whole RSI loop
optimizes toward a corrupt signal.

Run: python3 scripts/testing/test-eval-integrity.py
"""

import hashlib
import json
import math
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


def _outcomes(prefix: str = "selection", n: int = 100, errors: int = 50,
              wins: int = 20, losses: int = 2) -> tuple[dict[str, str], dict[str, str]]:
    base = {f"{prefix}-{i}": "fail" if i < errors else "pass" for i in range(n)}
    candidate = dict(base)
    for i in range(wins):
        candidate[f"{prefix}-{i}"] = "pass"
    for i in range(errors, errors + losses):
        candidate[f"{prefix}-{i}"] = "fail"
    return base, candidate


def test_baseline_cache_key():
    params = {"temperature": 0.0, "nested": {"b": 2, "a": 1}}
    key = EI.baseline_cache_key("model", "quant", "sha", params)
    reordered = {"nested": {"a": 1, "b": 2}, "temperature": 0.0}
    assert key == EI.baseline_cache_key("model", "quant", "sha", reordered)
    assert len(key) == 64 and all(c in "0123456789abcdef" for c in key)
    canonical = json.dumps({"model_id": "model", "quant": "quant", "dataset_sha": "sha",
                            "decode_params": params}, sort_keys=True, separators=(",", ":"))
    assert key == hashlib.sha256(canonical.encode()).hexdigest()
    for args in (("other", "quant", "sha", params), ("model", "other", "sha", params),
                 ("model", "quant", "other", params), ("model", "quant", "sha", {"temperature": 1})):
        assert key != EI.baseline_cache_key(*args)
    for index in range(3):
        for empty in ("", "  ", "\t\n"):
            fields = ["model", "quant", "sha"]
            fields[index] = empty
            try:
                EI.baseline_cache_key(*fields, params)
            except ValueError:
                pass
            else:
                raise AssertionError("empty cache identity accepted")
    print("PASS baseline cache canonical SHA-256, order invariance, sensitivity and empty rejection")


def test_promotion_rejects_invalid_pairs():
    base, candidate = _outcomes()
    for invalid_base, invalid_candidate in (
        ({}, {}), (base, {"different": "pass"}),
        ({**base, "selection-0": "unknown"}, candidate),
        (base, {**candidate, "selection-0": "unknown"}),
    ):
        result = EI.promotion_gate(invalid_base, invalid_candidate, require_holdout=False)
        assert not result.promoted and not result.checks["selection_inputs"]
        assert "selection_inputs" in result.reason
    print("PASS promotion rejects empty, unpaired and unknown-label selection data")


def test_promotion_rejects_saturation_and_crashes():
    for errors in (1, 19):
        base, candidate = _outcomes(errors=errors, wins=errors, losses=0)
        result = EI.promotion_gate(base, candidate, require_holdout=False)
        assert not result.promoted and not result.checks["selection_headroom"]
        if errors == 1:
            assert result.selection["base_acc"] == 0.99
            assert not result.checks["selection_saturation"]
    for crash_base in (False, True):
        base, candidate = _outcomes()
        target = base if crash_base else candidate
        for i in range(42):
            target[f"selection-{i}"] = "crash"
        result = EI.promotion_gate(base, candidate, require_holdout=False)
        assert not result.promoted and not result.checks["selection_crash_rate"]
        field = "base_crash_rate" if crash_base else "candidate_crash_rate"
        assert result.selection[field] == 0.42
    print("PASS promotion rejects 99% saturation, fewer than 20 errors and 42% crashes on either side")


def test_promotion_rejects_small_sample_noise():
    base, candidate = _outcomes(n=39, errors=20, wins=20, losses=0)
    result = EI.promotion_gate(base, candidate, require_holdout=False)
    assert not result.promoted and not result.checks["selection_min_n"]
    for wins, losses in ((3, 1), (0, 0), (1, 3), (3, 3)):
        base, candidate = _outcomes(n=40, errors=20, wins=wins, losses=losses)
        result = EI.promotion_gate(base, candidate, require_holdout=False)
        assert not result.promoted and not result.checks["selection_significance"]
        if (wins, losses) == (3, 1):
            assert result.selection["z_score"] == 0.5
        if wins == losses:
            assert result.selection["z_score"] == 0.0
        if wins <= losses:
            assert not result.checks["selection_improvement"]
    print("PASS promotion rejects undersized samples, small-N noise, zero gains and non-improvements")


def test_promotion_holdout_and_significant_gain():
    base, candidate = _outcomes()
    holdout_base, holdout_candidate = _outcomes("holdout")
    for hb, hc in ((None, None), (holdout_base, None), (None, holdout_candidate), ({}, {})):
        result = EI.promotion_gate(base, candidate, hb, hc)
        assert not result.promoted and not result.checks["holdout_inputs"]
    leaked = EI.promotion_gate(base, candidate, base, candidate)
    assert not leaked.promoted and not leaked.checks["holdout_disjoint"]
    flat = EI.promotion_gate(base, candidate, holdout_base, holdout_base)
    assert not flat.promoted and not flat.checks["holdout_significance"]
    for hb, hc in ((holdout_base, {"wrong": "pass"}),
                   (holdout_base, {**holdout_candidate, "holdout-0": "invalid"})):
        invalid = EI.promotion_gate(base, candidate, hb, hc)
        assert not invalid.promoted and not invalid.checks["holdout_inputs"]
    for crash_base in (False, True):
        hb, hc = _outcomes("holdout")
        target = hb if crash_base else hc
        for i in range(42):
            target[f"holdout-{i}"] = "crash"
        crashed = EI.promotion_gate(base, candidate, hb, hc)
        assert not crashed.promoted and not crashed.checks["holdout_crash_rate"]
    result = EI.promotion_gate(base, candidate, holdout_base, holdout_candidate)
    assert result.promoted, result.reason
    assert all(result.checks.values())
    assert result.holdout is not None
    for summary in (result.selection, result.holdout):
        assert summary["w_to_c"] == 20 and summary["c_to_w"] == 2
        assert math.isclose(summary["z_score"], 17 / math.sqrt(22))
    print(f"PASS disjoint selection/holdout gain: w_to_c=20 c_to_w=2 z_score={result.selection['z_score']}")
    print("PASS promotion rejects missing, leaked, invalid, flat and crash-heavy holdouts")


def test_promotion_thresholds_and_crash_exclusion():
    base, candidate = _outcomes(n=40, errors=20, wins=3, losses=1)
    result = EI.promotion_gate(base, candidate, require_holdout=False, min_z=0.5)
    assert result.promoted and result.holdout is None
    assert not EI.promotion_gate(base, candidate, require_holdout=False, min_n=41).promoted
    assert not EI.promotion_gate(base, candidate, require_holdout=False, max_base_acc=0.49).promoted
    assert not EI.promotion_gate(base, candidate, require_holdout=False, min_error_headroom=21).promoted
    base, candidate = _outcomes()
    for i in range(10):
        candidate[f"selection-{i}"] = "crash"
        base[f"selection-{90 + i}"] = "crash"
    result = EI.promotion_gate(base, candidate, require_holdout=False)
    assert result.promoted and result.selection["w_to_c"] == 10
    assert result.selection["c_to_w"] == 2
    assert math.isclose(result.selection["base_acc"], 40 / 90)
    assert not EI.promotion_gate(base, candidate, require_holdout=False, max_crash_rate=0.09).promoted
    for kwargs in ({"min_z": float("nan")}, {"max_crash_rate": float("nan")},
                   {"max_base_acc": 1.1}, {"min_n": 0}, {"min_error_headroom": -1}):
        try:
            EI.promotion_gate(base, candidate, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid threshold accepted: {kwargs}")
    print("PASS configurable thresholds, exact boundaries, non-crash accuracy and crash pair exclusion")


def test_futility_breaker():
    assert not EI.futility_breaker([]).halt
    assert not EI.futility_breaker([{"promoted": False}]).halt
    failed = [{"promoted": False}, {"promoted": False}]
    result = EI.futility_breaker(failed)
    assert result.halt and result.consecutive_non_promoted == 2
    assert "consecutive" in result.reason and result.latest_crash_rate == 0.0
    reset = EI.futility_breaker([*failed, {"promoted": True}])
    assert not reset.halt and reset.consecutive_non_promoted == 0
    assert not EI.futility_breaker([*failed, {"promoted": True}, {"promoted": False}]).halt
    crashed = EI.futility_breaker([{"promoted": True, "crash_rate": 0.42}])
    assert crashed.halt and crashed.latest_crash_rate == 0.42 and "crash" in crashed.reason
    assert not EI.futility_breaker([{"promoted": True, "crash_rate": 0.10}]).halt
    assert not EI.futility_breaker(failed, max_consecutive_non_promoted=3).halt
    assert not EI.futility_breaker([{"promoted": True, "crash_rate": 0.42}], max_crash_rate=0.5).halt
    for history in ([{}], [{"promoted": "False"}], [{"promoted": False, "crash_rate": float("nan")}]):
        try:
            EI.futility_breaker(history)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed history accepted")
    print("PASS futility stops repeated failures/high crashes and resets after promotion")


if __name__ == "__main__":
    test_reference_scorer_is_trustworthy()
    test_gate_rejects_nondiscriminating_scorer()
    test_gate_rejects_nondeterministic_scorer()
    test_gate_rejects_infra_noise_scorer()
    test_gate_rejects_unisolated_golden()
    test_exec_scorer_abstains_on_noise()
    test_exec_scorer_discriminates_per_type()
    test_baseline_cache_key()
    test_promotion_rejects_invalid_pairs()
    test_promotion_rejects_saturation_and_crashes()
    test_promotion_rejects_small_sample_noise()
    test_promotion_holdout_and_significant_gain()
    test_promotion_thresholds_and_crash_exclusion()
    test_futility_breaker()
    print("ALL PASS")
