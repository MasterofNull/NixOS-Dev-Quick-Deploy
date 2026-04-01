#!/usr/bin/env python3
"""Static regression checks for delegated response quality integration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "from quality_assurance import QualityChecker, QualityThreshold, ResultCache, ResultRefiner, QualityTrendTracker" in text,
        "hybrid coordinator should import delegated quality assurance primitives",
    )
    assert_true(
        "_DELEGATED_QUALITY_CHECKER = QualityChecker(threshold=QualityThreshold.ACCEPTABLE)" in text,
        "hybrid coordinator should initialize a delegated quality checker",
    )
    assert_true(
        "def _assess_delegated_response_quality(" in text,
        "hybrid coordinator should define delegated quality assessment helper",
    )
    assert_true(
        '_DELEGATED_RESULT_CACHE.set(task, selected_text, quality_check.score)' in text,
        "delegated quality flow should cache passing responses",
    )
    assert_true(
        '_DELEGATED_QUALITY_TRACKER.record_quality(agent_id, quality_check.score.overall)' in text,
        "delegated quality flow should track per-agent quality trends",
    )
    assert_true(
        '"delegated_quality_assurance": _delegated_quality_status_snapshot()' in text,
        "status endpoint should expose delegated quality assurance state",
    )
    assert_true(
        'delegated_quality = await _assess_delegated_response_quality(' in text,
        "delegate handler should assess successful delegated responses",
    )
    assert_true(
        'body = _inject_delegated_response_text(body, updated_text)' in text,
        "delegate handler should inject refined or cached response text back into payloads",
    )
    assert_true(
        '"quality_assurance": delegated_quality' in text,
        "delegate response should surface quality assurance metadata",
    )

    print("PASS: delegated response quality assurance is integrated into routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
