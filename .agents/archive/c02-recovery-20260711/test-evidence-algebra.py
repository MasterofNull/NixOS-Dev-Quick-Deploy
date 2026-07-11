#!/usr/bin/env python3
"""Coverage for C0.2 Evidence Algebra and evaluate_gate in aq-report."""

from __future__ import annotations

import importlib.util
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


def test_empty_required_claims() -> None:
    mod = _load_aq_report()
    res = mod.evaluate_gate("test_gate", {})
    assert_true(res["outcome"] == "BLOCKED", f"Expected BLOCKED outcome, got {res['outcome']}")
    assert_true(res["evidence_condition"] == "INVALID", f"Expected INVALID, got {res['evidence_condition']}")
    assert_true(res["status"] == "no_data", f"Expected status no_data, got {res['status']}")
    assert_true(res["blocking_reasons"][0]["reason_code"] == "NO_REQUIRED_CLAIMS", "Expected NO_REQUIRED_CLAIMS")


def test_non_valid_required_evidence() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "MISSING",
            "assessment": "PASS",
            "remediation": "Provide claim_1",
            "source_id": "test_src",
            "reason_code": "MISSING_DATA",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["outcome"] == "BLOCKED", f"Expected BLOCKED outcome, got {res['outcome']}")
    assert_true(res["evidence_condition"] == "MISSING", f"Expected MISSING condition, got {res['evidence_condition']}")
    assert_true(res["status"] == "no_data", f"Expected legacy status no_data, got {res['status']}")
    assert_true(res["required_claims"]["claim_1"]["assessment"] == "UNKNOWN", "Non-VALID required evidence must yield UNKNOWN assessment")


def test_adverse_valid_measurement() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "VALID",
            "assessment": "FAIL",
            "remediation": "Fix claim_1",
            "source_id": "test_src",
            "reason_code": "CHECK_FAILED",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["outcome"] == "FAIL", f"Expected FAIL outcome, got {res['outcome']}")
    assert_true(res["status"] == "fail", f"Expected status fail, got {res['status']}")


def test_na_predicate_validation() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "VALID",
            "assessment": "NOT_APPLICABLE",
            "remediation": "",
            "source_id": "test_src",
            "reason_code": "NA",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["required_claims"]["claim_1"]["condition"] == "INVALID", "NA without predicate should be invalid")
    assert_true(res["required_claims"]["claim_1"]["assessment"] == "UNKNOWN", "NA without predicate should yield UNKNOWN assessment")


def test_conflicting_evidence() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "CONFLICTING",
            "assessment": "PASS",
            "remediation": "Resolve conflict",
            "source_id": "test_src",
            "reason_code": "CONFLICTING_VERSION",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["outcome"] == "BLOCKED", "Conflicting must yield BLOCKED")
    assert_true(res["evidence_condition"] == "CONFLICTING", "Expected CONFLICTING condition")
    assert_true(res["status"] == "fail", "Conflicting yields legacy status fail")


def test_unauthorized_producer() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "UNAUTHORIZED",
            "assessment": "PASS",
            "remediation": "Authorize producer",
            "source_id": "test_src",
            "reason_code": "UNAUTHORIZED",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["outcome"] == "BLOCKED", "Unauthorized must yield BLOCKED")
    assert_true(res["evidence_condition"] == "UNAUTHORIZED", "Expected UNAUTHORIZED condition")
    assert_true(res["status"] == "fail", "Unauthorized yields legacy status fail")


def test_insufficient_sample() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "INSUFFICIENT_SAMPLE",
            "assessment": "PASS",
            "remediation": "Run more tests",
            "source_id": "test_src",
            "reason_code": "LOW_SAMPLE",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["outcome"] == "BLOCKED", "Insufficient sample must yield BLOCKED")
    assert_true(res["evidence_condition"] == "INSUFFICIENT_SAMPLE", "Expected INSUFFICIENT_SAMPLE condition")
    assert_true(res["status"] == "no_data", "Insufficient sample yields legacy status no_data")


def test_proxy_metric_routing() -> None:
    mod = _load_aq_report()
    req = {
        "claim_1": {
            "condition": "VALID",
            "assessment": "PASS",
            "remediation": "Authorize proxy",
            "source_id": "test_src",
            "reason_code": "PROXY",
            "proxy_for": "target_metric",
            "proxy_authorized": False,
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    assert_true(res["required_claims"]["claim_1"]["condition"] == "UNAUTHORIZED", "Unauthorized proxy must yield UNAUTHORIZED condition")


def test_reason_sorting() -> None:
    mod = _load_aq_report()
    req = {
        "claim_b": {
            "condition": "VALID",
            "assessment": "FAIL",
            "remediation": "Fix B",
            "source_id": "src_y",
            "reason_code": "FAIL_B",
        },
        "claim_a": {
            "condition": "MISSING",
            "assessment": "UNKNOWN",
            "remediation": "Provide A",
            "source_id": "src_x",
            "reason_code": "MISSING_A",
        }
    }
    res = mod.evaluate_gate("test_gate", req)
    reasons = res["blocking_reasons"]
    assert_true(len(reasons) == 2, "Expected 2 blocking reasons")
    # sorted by claim_id first, so claim_a first, then claim_b
    assert_true(reasons[0]["claim_id"] == "claim_a", f"Expected claim_a first, got {reasons[0]['claim_id']}")
    assert_true(reasons[1]["claim_id"] == "claim_b", f"Expected claim_b second, got {reasons[1]['claim_id']}")


if __name__ == "__main__":
    tests = [
        ("empty required claims", test_empty_required_claims),
        ("non-valid required evidence", test_non_valid_required_evidence),
        ("adverse valid measurement", test_adverse_valid_measurement),
        ("NA predicate validation", test_na_predicate_validation),
        ("conflicting evidence", test_conflicting_evidence),
        ("unauthorized producer", test_unauthorized_producer),
        ("insufficient sample", test_insufficient_sample),
        ("proxy metric routing", test_proxy_metric_routing),
        ("reason sorting", test_reason_sorting),
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
