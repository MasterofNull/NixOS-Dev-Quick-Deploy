#!/usr/bin/env python3
"""Targeted checks for required workflow blueprint coverage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "config" / "workflow-blueprints.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    payload = json.loads(BLUEPRINTS_PATH.read_text(encoding="utf-8"))
    items = payload.get("blueprints") or []
    ids = {item.get("id") for item in items if isinstance(item, dict)}
    required = {
        "coding-bugfix-safe",
        "repo-refactor-guarded",
        "deploy-rollback-safe-ops",
        "continue-editor-rescue",
        "bounded-research-review",
        "remote-reasoning-escalation",
        "prsi-pessimistic-recursive-improvement",
        "long-running-context-offload",
    }
    missing = sorted(required - ids)
    assert_true(not missing, f"missing required workflow blueprints: {', '.join(missing)}")
    for item in items:
        policy = item.get("orchestration_policy") or {}
        assert_true(isinstance(policy, dict), f"blueprint {item.get('id')} missing orchestration_policy")
        assert_true(bool(policy.get("primary_lane")), f"blueprint {item.get('id')} missing primary_lane")
        assert_true(bool(policy.get("reviewer_lane")), f"blueprint {item.get('id')} missing reviewer_lane")
        assert_true(bool(policy.get("escalation_lane")), f"blueprint {item.get('id')} missing escalation_lane")
        assert_true(bool(policy.get("consensus_mode")), f"blueprint {item.get('id')} missing consensus_mode")
        if policy.get("allow_parallel_subagents"):
            collaborator_lanes = policy.get("collaborator_lanes") or []
            assert_true(
                isinstance(collaborator_lanes, list) and len(collaborator_lanes) >= 1,
                f"blueprint {item.get('id')} must declare collaborator_lanes when parallel subagents are enabled",
            )
            assert_true(
                int(policy.get("max_parallel_subagents") or 0) >= 2,
                f"blueprint {item.get('id')} must reserve at least one optional collaborator slot",
            )
    offload = next((item for item in items if item.get("id") == "long-running-context-offload"), None)
    assert_true(offload is not None, "long-running-context-offload blueprint must exist")
    contract = offload.get("intent_contract") or {}
    spirit_constraints = contract.get("spirit_constraints") or []
    assert_true(
        any("memory recall" in str(entry).lower() for entry in spirit_constraints),
        "long-running-context-offload blueprint must steer runs toward harness memory recall",
    )
    assert_true(
        any("compact" in str(entry).lower() for entry in spirit_constraints),
        "long-running-context-offload blueprint must require frequent compaction",
    )
    print("PASS: workflow blueprints cover the required harness task families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
