#!/usr/bin/env python3
"""Static regression checks for role-aware agent evaluation biasing."""

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
        "def _normalize_agent_role(value: Any) -> str:" in text,
        "evaluation bias should normalize agent roles for cross-lane aggregation",
    )
    assert_true(
        "import re" in text,
        "role normalization should import re for regex-based cleanup",
    )
    assert_true(
        '"roles": value.get("roles", {}) if isinstance(value.get("roles"), dict) else {}' in text,
        "agent evaluation registry should preserve role summaries",
    )
    assert_true(
        "role_row = roles.get(_normalize_agent_role(role))" in text,
        "evaluation bias should read the role-specific history row",
    )
    assert_true(
        'events[-18:]' in text,
        "evaluation bias should inspect an expanded bounded recent event window",
    )
    assert_true(
        'if not profile_match and not role_match:' in text,
        "recent-event bias should consider either matching profile or matching role",
    )
    assert_true(
        '(0.20 * _weighted_component(role_avg_review_score, role_review_events, 8.0))' in text,
        "evaluation bias should include role-specific review history",
    )
    assert_true(
        '(0.25 * _weighted_component(role_avg_runtime_score, role_runtime_events, 8.0))' in text,
        "evaluation bias should include role-specific runtime quality history",
    )
    assert_true(
        '(0.20 * min(1.0, role_consensus_selected / 6.0))' in text,
        "evaluation bias should include role-specific consensus history",
    )
    assert_true(
        'components["historical_runtime_quality"] = history["runtime_score"]' in text,
        "seeded candidates should still receive runtime history bias",
    )
    assert_true(
        '"selected_role": selected.get("role")' in text,
        "seeded consensus state should preserve the selected role",
    )
    assert_true(
        '"role_count": len(roles)' in text,
        "evaluation trends should surface tracked role counts",
    )
    assert_true(
        '"roles": {' in text,
        "evaluation trends should expose per-role aggregates",
    )

    print("PASS: role-aware agent evaluation biasing is wired into orchestration scoring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
