#!/usr/bin/env python3
"""Static MAEAH security contract gates for Phase 1 parity controls.

This test intentionally validates repository policy/documentation surfaces rather
than live runtime behavior. Runtime sandbox enforcement lands in later Phase 62
slices; this gate keeps the contract from drifting while that work proceeds.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def check_runtime_safety_policy() -> None:
    policy = load_json("config/runtime-safety-policy.json")
    modes = policy.get("modes", {})
    assert_true({"plan-readonly", "execute-mutating", "strict"}.issubset(modes), "expected required safety modes")

    readonly = modes["plan-readonly"]
    assert_true(readonly.get("allowed_risk_classes") == ["safe"], "plan-readonly must allow only safe risk")
    readonly_blocked = set(readonly.get("blocked", []))
    assert_true(
        {"blocked", "mutating", "destructive"}.issubset(readonly_blocked),
        "plan-readonly must block blocked/mutating/destructive classes",
    )
    readonly_tools = set(readonly.get("tool_blocklist", []))
    for tool_name in ["write_file", "edit_file", "apply_patch", "git_commit", "git_push", "db_write", "http_post"]:
        assert_true(tool_name in readonly_tools, f"plan-readonly must block {tool_name}")

    execute = modes["execute-mutating"]
    execute_allowed = set(execute.get("allowed_risk_classes", []))
    assert_true({"safe", "review-required"}.issubset(execute_allowed), "execute-mutating must allow safe/review-required")
    execute_blocked = set(execute.get("blocked", []))
    assert_true("blocked" in execute_blocked, "execute-mutating must block blocked class")
    execute_tools = set(execute.get("tool_blocklist", []))
    for tool_name in ["delete_file", "git_push", "git_reset", "db_delete", "drop_table", "truncate_table"]:
        assert_true(tool_name in execute_tools, f"execute-mutating must block irreversible tool {tool_name}")

    strict = modes["strict"]
    assert_true(strict.get("allowed_risk_classes") == ["safe"], "strict must allow only safe risk")
    assert_true("high-risk" in set(strict.get("blocked", [])), "strict must block high-risk actions")


def check_runtime_isolation_profiles() -> None:
    policy = load_json("config/runtime-isolation-profiles.json")
    defaults = policy.get("default_profile_by_mode", {})
    profiles = policy.get("profiles", {})
    assert_true(defaults.get("plan-readonly") == "readonly-strict", "plan-readonly must default to readonly-strict")
    assert_true(defaults.get("execute-mutating") == "execute-guarded", "execute-mutating must default to execute-guarded")

    readonly = profiles.get("readonly-strict", {})
    assert_true(readonly.get("allow_workspace_write") is False, "readonly-strict must forbid workspace writes")
    assert_true(readonly.get("network_policy") == "none", "readonly-strict must forbid network")

    for profile_name, profile in profiles.items():
        network_policy = profile.get("network_policy")
        assert_true(network_policy in {"none", "loopback"}, f"{profile_name} must not allow unrestricted network")
        workspace_root = str(profile.get("workspace_root", ""))
        assert_true(
            workspace_root.startswith("/var/lib/nixos-ai-stack/mutable/program/"),
            f"{profile_name} workspace must stay under mutable program root",
        )


def check_review_gate_contract() -> None:
    text = (ROOT / "docs/architecture/gemini-review-gate.md").read_text(encoding="utf-8")
    required_phrases = [
        "Review-gate trigger categories",
        "Required artifact form",
        "Verdict protocol",
        "No-self-acceptance rule",
        "Qwen implementer work",
        "Validation evidence",
        "Acceptance criteria check",
        "Risk note",
    ]
    for phrase in required_phrases:
        assert_true(phrase in text, f"review gate contract missing phrase: {phrase}")


def check_parity_phase_mapping() -> None:
    text = (ROOT / ".agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md").read_text(encoding="utf-8")
    for item in ["PA-2", "PA-3", "PA-4", "Phase 1 — Security and governance contracts"]:
        assert_true(item in text, f"parity plan missing {item}")
    assert_true("Tool sandbox policy schema" in text, "parity plan must keep sandbox policy schema in Phase 1")
    assert_true("Agent identity/delegation contract" in text, "parity plan must keep identity/delegation contract in Phase 1")


def main() -> int:
    check_runtime_safety_policy()
    check_runtime_isolation_profiles()
    check_review_gate_contract()
    check_parity_phase_mapping()
    print("PASS: security contract gates are pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
