#!/usr/bin/env python3
"""Static regression checks for capability-gap integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COORDINATOR_ROOT = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
LEARNING_ENGINE = COORDINATOR_ROOT / "extensions" / "real_time_learning_engine.py"
DELEGATE_HANDLER = COORDINATOR_ROOT / "extensions" / "ai_coordinator_handlers.py"
STATUS_SERVICE = COORDINATOR_ROOT / "core" / "status_service.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    learning_text = LEARNING_ENGINE.read_text(encoding="utf-8")
    delegate_text = DELEGATE_HANDLER.read_text(encoding="utf-8")
    status_text = STATUS_SERVICE.read_text(encoding="utf-8")

    assert_true(
        "from gap_detection import GapDetector" in learning_text,
        "hybrid coordinator should import capability gap detection primitives",
    )
    assert_true(
        "from gap_remediation import RemediationPlan, RemediationResult, RemediationStatus, RemediationStrategy" in learning_text,
        "hybrid coordinator should import capability gap remediation primitives",
    )
    assert_true(
        "from remediation_learning import OutcomeTracker, PlaybookLibrary, StrategyOptimizer" in learning_text,
        "hybrid coordinator should import remediation learning primitives",
    )
    assert_true(
        'os.getenv("REMEDIATION_PLAYBOOKS_DIR", "/var/lib/ai-stack/hybrid/playbooks")' in learning_text,
        "hybrid coordinator should keep remediation playbooks in writable AI stack storage by default",
    )
    assert_true(
        "def _plan_capability_gap_remediation(" in learning_text,
        "hybrid coordinator should define remediation planning helper",
    )
    assert_true(
        "def _record_capability_gap_outcomes(" in learning_text,
        "hybrid coordinator should define remediation outcome recorder",
    )
    assert_true(
        '"capability_gap_automation": _capability_gap_status_snapshot()' in status_text,
        "status endpoint should expose capability-gap state",
    )
    assert_true(
        "capability_gaps = _GAP_DETECTOR.detect_from_failure(" in delegate_text,
        "delegate handler should detect capability gaps from delegated failures",
    )
    assert_true(
        '"capability_gaps": [' in delegate_text,
        "delegate response should expose detected capability gaps",
    )
    assert_true(
        '"remediation_plans": remediation_plans' in delegate_text,
        "delegate response should expose remediation plans",
    )

    print("PASS: capability gap detection, remediation, and learning are integrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
