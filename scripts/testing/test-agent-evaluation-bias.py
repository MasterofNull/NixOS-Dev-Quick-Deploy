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
    assert_true(
        '"collaborator_lanes": []' in text,
        "orchestration policy should default collaborator_lanes to an empty list",
    )
    assert_true(
        'normalized["collaborator_lanes"] = _normalize_orchestration_lane_list(policy.get("collaborator_lanes", []))' in text,
        "orchestration policy should normalize collaborator lanes explicitly",
    )
    assert_true(
        'if allow_parallel and collaborator_candidates:' in text,
        "team formation should activate collaborator candidates when parallel subagents are enabled",
    )
    assert_true(
        'f"collaborator-{idx}"' in text,
        "candidate seeding should create bounded collaborator candidate ids",
    )
    assert_true(
        'deferred_members = optional_members[optional_budget:]' in text,
        "team formation should retain deferred collaborator members when capacity is exhausted",
    )
    assert_true(
        '"optional_slot_capacity": optional_budget' in text,
        "team metadata should expose the optional collaborator capacity budget",
    )
    assert_true(
        '"deferred_slots": deferred_slots' in text,
        "team metadata should expose deferred collaborator slot names",
    )
    assert_true(
        '"deferred_members": team.get("deferred_members", [])' in text,
        "detailed team inspection should include deferred collaborator members",
    )
    assert_true(
        '"objective": session.get("objective", "")' in text,
        "detailed team inspection should expose workflow objective context",
    )
    assert_true(
        '"status": session.get("status", "unknown")' in text,
        "detailed team inspection should expose workflow runtime status",
    )
    assert_true(
        '"current_phase": current_phase' in text,
        "detailed team inspection should expose the current workflow phase",
    )
    assert_true(
        '"safety_mode": session.get("safety_mode", "plan-readonly")' in text,
        "detailed team inspection should expose workflow safety mode",
    )
    assert_true(
        '"usage": session.get("usage", {})' in text,
        "detailed team inspection should expose workflow usage counters",
    )

    print("PASS: role-aware agent evaluation biasing is wired into orchestration scoring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
