#!/usr/bin/env python3
"""Static regression for aq-optimizer lesson-review action support."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_OPTIMIZER = ROOT / "scripts" / "ai" / "aq-optimizer"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = AQ_OPTIMIZER.read_text(encoding="utf-8")

    assert_true(
        'def apply_lesson_review(action: dict, dry_run: bool) -> dict:' in text,
        "aq-optimizer should implement lesson review application",
    )
    assert_true(
        'elif atype == "lesson" and aname == "review_agent_lesson":' in text,
        "aq-optimizer should handle structured lesson review actions",
    )
    assert_true(
        '/control/ai-coordinator/lessons/review' in text,
        "lesson review support should use the existing coordinator review endpoint",
    )

    print("PASS: aq-optimizer supports structured lesson review actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
