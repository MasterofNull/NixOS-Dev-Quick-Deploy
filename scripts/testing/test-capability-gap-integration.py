#!/usr/bin/env python3
"""Static regression checks for capability-gap integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "from gap_detection import GapDetector, GapType" in text,
        "hybrid coordinator should import capability gap detection primitives",
    )
    assert_true(
        "from gap_remediation import RemediationPlan, RemediationResult, RemediationStatus, RemediationStrategy" in text,
        "hybrid coordinator should import capability gap remediation primitives",
    )
    assert_true(
        "from remediation_learning import OutcomeTracker, PlaybookLibrary, StrategyOptimizer" in text,
        "hybrid coordinator should import remediation learning primitives",
    )
    assert_true(
        "def _plan_capability_gap_remediation(" in text,
        "hybrid coordinator should define remediation planning helper",
    )
    assert_true(
        "def _record_capability_gap_outcomes(" in text,
        "hybrid coordinator should define remediation outcome recorder",
    )
    assert_true(
        '"capability_gap_automation": _capability_gap_status_snapshot()' in text,
        "status endpoint should expose capability-gap state",
    )
    assert_true(
        "capability_gaps = _GAP_DETECTOR.detect_from_failure(" in text,
        "delegate handler should detect capability gaps from delegated failures",
    )
    assert_true(
        '"capability_gaps": [' in text,
        "delegate response should expose detected capability gaps",
    )
    assert_true(
        '"remediation_plans": remediation_plans' in text,
        "delegate response should expose remediation plans",
    )

    print("PASS: capability gap detection, remediation, and learning are integrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
