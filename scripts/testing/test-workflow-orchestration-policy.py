#!/usr/bin/env python3
"""Targeted checks for workflow orchestration role defaults."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from ai_coordinator import coerce_orchestration_context  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    default_ctx = coerce_orchestration_context({})
    assert_true(default_ctx["requester_role"] == "orchestrator", "default requester should be orchestrator")
    assert_true(default_ctx["top_level_orchestrator"] is True, "default requester should be top-level orchestrator")
    assert_true(default_ctx["subagents_may_spawn_subagents"] is False, "nested sub-agent spawning must stay disabled")
    assert_true(default_ctx["delegate_via_coordinator_only"] is True, "delegation must flow back through coordinator")

    sub_ctx = coerce_orchestration_context({"requesting_agent": "qwen", "requester_role": "sub-agent"})
    assert_true(sub_ctx["requested_by"] == "qwen", "requesting agent should be preserved")
    assert_true(sub_ctx["requester_role"] == "sub-agent", "sub-agent role should be preserved")
    assert_true(sub_ctx["top_level_orchestrator"] is False, "sub-agent must not be treated as top-level orchestrator")
    assert_true(sub_ctx["coordinator_delegate_path"] == "/control/ai-coordinator/delegate", "handoff path should be explicit")

    alias_ctx = coerce_orchestration_context({"agent": "continue", "role": "orchestrator"})
    assert_true(alias_ctx["requested_by"] == "continue", "legacy agent alias should normalize into requesting_agent")
    assert_true(alias_ctx["requester_role"] == "orchestrator", "legacy role alias should normalize into requester_role")

    print("PASS: workflow orchestration defaults keep top-level agents as orchestrators and sub-agents bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
