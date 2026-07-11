#!/usr/bin/env python3
"""Regression coverage for Phase 93.12 effectiveness scorecard in aq-report."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_aq_report():
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("aq_report", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_no_data_when_all_empty() -> None:
    mod = _load_aq_report()
    mod.production_store = None
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {}, [], None, None, None, None, None, None, None
    )
    assert_true("overall_status" in result, "overall_status key present")
    assert_true(result["overall_status"] == "blocked", f"required unknown → blocked, got {result['overall_status']}")
    assert_true("blocking_reasons" in result, "blocking_reasons key present")
    assert_true(len(result["blocking_reasons"]) > 0, "required unknown must include blocking reasons")


def test_pass_when_eval_rate_high() -> None:
    mod = _load_aq_report()
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {"recent_pass_rate": 0.95}, [], None, None, None, None, None, None, None
    )
    oc = result["outcome_correctness"]
    assert_true(oc["status"] == "pass", f"outcome_correctness should be pass, got {oc['status']}")
    assert_true(result["overall_status"] == "blocked", "missing required trace/review evidence must block")


def test_fail_when_eval_rate_low() -> None:
    mod = _load_aq_report()
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {"recent_pass_rate": 0.45}, [], None, None, None, None, None, None, None
    )
    oc = result["outcome_correctness"]
    assert_true(oc["status"] == "fail", f"outcome_correctness should be fail, got {oc['status']}")
    assert_true(result["overall_status"] == "fail", "overall_status must be fail when outcome_correctness fails")
    assert_true(len(result["blocking_reasons"]) > 0, "blocking_reasons must be non-empty when outcome fails")


def test_warn_when_validation_health_has_failures() -> None:
    mod = _load_aq_report()
    vh = {"available": True, "status": "fail", "checks_failed": 2, "checks_ran": 5}
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {}, [], None, None, None, None, None, vh, None
    )
    ot = result["operator_trust"]
    # no intent_coverage → no_data base, but checks_failed > 0 elevates to warn
    assert_true(ot["status"] in ("warn", "fail"), f"operator_trust should be warn/fail with failed checks, got {ot['status']}")
    assert_true(ot["validation_checks_failed"] == 2, "validation_checks_failed should be 2")


def test_scorecard_dimensions_all_present() -> None:
    mod = _load_aq_report()
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {}, [], None, None, None, None, None, None, None
    )
    for dim in ("outcome_correctness", "completion_reliability", "operator_trust",
                "regression_containment", "context_quality", "efficiency_inputs"):
        assert_true(dim in result, f"dimension '{dim}' must be present in scorecard")
    for dim_key in ("outcome_correctness", "completion_reliability", "operator_trust",
                    "regression_containment", "context_quality"):
        assert_true("status" in result[dim_key], f"{dim_key} must have a 'status' key")


def test_efficiency_inputs_never_blocks() -> None:
    mod = _load_aq_report()
    # Even with a high contention rate, efficiency_inputs should never cause blocking
    bad_contention = {"available": True, "status": "warn", "events_per_hour": 100.0, "exceeds_threshold": True}
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {}, [], None, None, None, None, None, None, bad_contention
    )
    # overall_status must not be 'fail' just because of contention
    assert_true(result["overall_status"] != "fail", "efficiency_inputs alone must never block to 'fail'")
    ei = result["efficiency_inputs"]
    assert_true(ei["lock_contention_events_per_hour"] == 100.0, "contention rate propagated to efficiency_inputs")


def test_scorecard_uses_activation_window_for_delegate_reliability() -> None:
    mod = _load_aq_report()
    recent_health = {
        "delegate_active_window_s": 3600,
        "delegate_active_window_rate": 0.95,
        "delegate_active_window_breakdown": {
            "total": 20,
            "ok": 19,
            "adjusted_rate": 0.95,
            "timeout": 1,
            "infra_startup_500": 0,
            "provider_error": 0,
        },
        "delegate_24h_rate": 0.33,
        "delegate_24h_breakdown": {
            "total": 40,
            "ok": 13,
            "adjusted_rate": 0.37,
            "timeout": 23,
            "infra_startup_500": 4,
            "provider_error": 0,
        },
    }
    result = mod.effectiveness_scorecard(
        {}, {}, {}, {}, [], None, None, None, recent_health, None, None, None
    )
    cr = result["completion_reliability"]
    assert_true(cr["status"] == "pass", f"active-window reliability should pass, got {cr['status']}")
    assert_true(cr["delegation_success_rate"] == 0.95, "active-window rate should drive current reliability")
    assert_true(cr["delegation_24h_success_rate"] == 0.33, "24h rate should remain visible as history")
    assert_true(cr["delegation_24h_timeout_failures"] == 23, "24h timeout history should remain visible")


def test_format_json_includes_effectiveness_scorecard() -> None:
    mod = _load_aq_report()
    dummy_scorecard = {"overall_status": "pass", "blocking_reasons": []}
    result_json = mod.format_json(
        "7d",
        {}, {}, {}, {}, {}, {}, {}, [], [], [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
        [],
        effectiveness_scorecard_summary=dummy_scorecard,
    )
    doc = json.loads(result_json)
    assert_true("effectiveness_scorecard" in doc, "effectiveness_scorecard key present in format_json output")
    assert_true(doc["effectiveness_scorecard"]["overall_status"] == "pass", "overall_status value preserved")


if __name__ == "__main__":
    tests = [
        ("no_data when all empty", test_no_data_when_all_empty),
        ("pass when eval rate high", test_pass_when_eval_rate_high),
        ("fail when eval rate low", test_fail_when_eval_rate_low),
        ("warn when validation health has failures", test_warn_when_validation_health_has_failures),
        ("all six scorecard dimensions present", test_scorecard_dimensions_all_present),
        ("efficiency_inputs never blocks overall", test_efficiency_inputs_never_blocks),
        ("scorecard uses activation window for delegate reliability", test_scorecard_uses_activation_window_for_delegate_reliability),
        ("format_json includes effectiveness_scorecard", test_format_json_includes_effectiveness_scorecard),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
