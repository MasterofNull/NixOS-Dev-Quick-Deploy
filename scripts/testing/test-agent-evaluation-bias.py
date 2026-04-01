#!/usr/bin/env python3
"""Static regression checks for recency-aware agent evaluation biasing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "def _recent_agent_event_bias()" in text,
        "evaluation bias should include a recent-event helper",
    )
    assert_true(
        'events[-12:]' in text,
        "evaluation bias should inspect a bounded recent event window",
    )
    assert_true(
        'totals = agent_row.get("totals")' in text,
        "evaluation bias should blend whole-agent totals, not only one profile row",
    )
    assert_true(
        'recent_bias = _recent_agent_event_bias()' in text,
        "evaluation bias should include recent-event signals in scoring",
    )
    assert_true(
        '(0.55 * _weighted_component(avg_review_score, review_events, 5.0))' in text,
        "evaluation bias should weight direct profile review history explicitly",
    )
    assert_true(
        '(0.25 * _weighted_component(total_avg_review_score, total_review_events, 12.0))' in text,
        "evaluation bias should include longer whole-agent review history",
    )
    assert_true(
        '(0.20 * recent_bias["runtime_score"])' in text,
        "evaluation bias should include recent runtime quality",
    )

    print("PASS: recency-aware agent evaluation biasing is wired into orchestration scoring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
