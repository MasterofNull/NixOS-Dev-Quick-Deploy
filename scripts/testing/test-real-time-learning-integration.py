#!/usr/bin/env python3
"""Static regression checks for real-time learning integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "from online_learning import IncrementalLearner, LearningExample, UpdateStrategy, HintQualityAdjuster, LivePatternMiner" in text,
        "hybrid coordinator should import online learning primitives",
    )
    assert_true(
        "from feedback_acceleration import ImmediateFeedbackProcessor, SuccessFailureDetector" in text,
        "hybrid coordinator should import feedback acceleration primitives",
    )
    assert_true(
        "async def _apply_real_time_learning(" in text,
        "hybrid coordinator should define real-time learning helper",
    )
    assert_true(
        '"real_time_learning": _real_time_learning_status_snapshot()' in text,
        "status endpoint should expose real-time learning state",
    )
    assert_true(
        "real_time_learning = await _apply_real_time_learning(" in text,
        "delegate handler should apply real-time learning to successful outcomes",
    )
    assert_true(
        '"real_time_learning": real_time_learning' in text,
        "delegate response should expose real-time learning metadata",
    )

    print("PASS: delegated routing integrates real-time learning and feedback acceleration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
