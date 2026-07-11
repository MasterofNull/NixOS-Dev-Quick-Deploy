#!/usr/bin/env python3
"""Frozen C0.2 evidence algebra fixtures against aq-report's canonical calculator."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("aq_report_c02", str(ROOT / "scripts" / "ai" / "aq-report"))
spec = importlib.util.spec_from_loader(loader.name, loader)
report = importlib.util.module_from_spec(spec)
loader.exec_module(report)


def claim(claim_id: str, condition: str = "VALID", assessment: str = "PASS", **kwargs):
    return report.evaluate_evidence_claim(
        claim_id, required=kwargs.pop("required", True), evidence_condition=condition,
        assessment=assessment, reason_code=kwargs.pop("reason_code", "TEST"),
        source_id=kwargs.pop("source_id", "fixture"), remediation="rerun evidence", **kwargs,
    )


def test_missing_and_na_abuse_block() -> None:
    missing = claim("trace_complete", "MISSING", "PASS")
    abused_na = claim("review_outcome", "MISSING", "NOT_APPLICABLE", applicability_predicate="v1")
    gate = report.evaluate_evidence_gate("effectiveness", [missing, abused_na])
    assert missing["assessment"] == abused_na["assessment"] == "UNKNOWN"
    assert gate["outcome"] == "BLOCKED" and not gate["automation_allowed"]


def test_zero_required_and_optional_only_block() -> None:
    assert report.evaluate_evidence_gate("empty", [])["blocking_reasons"][0]["reason_code"] == "NO_REQUIRED_CLAIMS"
    optional = claim("cache_efficiency", required=False)
    assert report.evaluate_evidence_gate("optional", [optional])["outcome"] == "BLOCKED"


def test_unknown_producer_sample_proxy_and_stale_policy() -> None:
    unauthorized = claim("artifact_usefulness", producer_authorized=False)
    low_sample = claim("review_outcome", sample_size=2, sample_minimum=5)
    proxy = claim("task_outcome", proxy_for="task_outcome_denominator_valid")
    gate = report.evaluate_evidence_gate("effectiveness", [unauthorized, low_sample, proxy])
    assert {unauthorized["evidence_condition"], low_sample["evidence_condition"]} == {"UNAUTHORIZED", "INSUFFICIENT_SAMPLE"}
    assert gate["outcome"] == "BLOCKED"
    passing = report.evaluate_evidence_gate("effectiveness", [claim("trace")], policy_current=False)
    assert passing["outcome"] == "PASS" and not passing["automation_allowed"]


def test_known_adverse_fails_and_zero_denominator_unknown() -> None:
    adverse = claim("artifact_usefulness", "VALID", "FAIL")
    zero = claim("task_outcome_denominator_valid", "INVALID", "PASS")
    assert report.evaluate_evidence_gate("effectiveness", [adverse, zero])["outcome"] == "FAIL"
    assert zero["assessment"] == "UNKNOWN"


def test_deterministic_reason_order_and_recovery() -> None:
    claims = [claim("z", "MISSING", "PASS", source_id="b"), claim("a", "STALE", "PASS", source_id="a")]
    blocked = report.evaluate_evidence_gate("effectiveness", claims)
    assert [item["claim_id"] for item in blocked["blocking_reasons"]] == ["a", "z"]
    recovered = report.evaluate_evidence_gate("effectiveness", [claim("a"), claim("z")])
    assert recovered["outcome"] == "PASS" and recovered["automation_allowed"]


def test_conflicting_candidates_never_select_newest() -> None:
    conflict = claim("artifact_hash_valid", "CONFLICTING", "PASS")
    gate = report.evaluate_evidence_gate("qa_certification", [conflict])
    assert gate["outcome"] == "BLOCKED" and gate["evidence_condition"] == "CONFLICTING"


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
