#!/usr/bin/env python3
"""Regression coverage for Switchboard tool working-set selection."""

import importlib.util
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_PATH = REPO_ROOT / "ai-stack" / "switchboard" / "switchboard.py"


def load_switchboard():
    os.environ.setdefault("LLAMA_CTX_SIZE", "16384")
    spec = importlib.util.spec_from_file_location("switchboard_under_test", SWITCHBOARD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def names(tools):
    return {tool["function"]["name"] for tool in tools}


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    swb = load_switchboard()

    conversational = [{"role": "user", "content": "how are you today?"}]
    tools, allowed, meta = swb._normalize_local_tools(None, conversational)
    assert_true(tools == [], "conversational turns should hot-load zero local tools")
    assert_true(allowed == set(), "conversational allowed tool set should be empty")
    assert_true(meta["intent"] == "conversational", "expected conversational intent")
    assert_true(meta["active_schema_limit"] == swb.ACTIVE_TOOL_SCHEMA_LIMIT, "active schema limit metadata mismatch")
    assert_true(meta["evicted_count"] > 0, "expected unused tools to be evicted")

    git_prompt = [{"role": "user", "content": "what files changed in the last commit?"}]
    tools, allowed, meta = swb._normalize_local_tools(None, git_prompt)
    selected = names(tools)
    assert_true(meta["intent"] == "git", f"expected git intent, got {meta['intent']}")
    assert_true(len(tools) <= swb.ACTIVE_TOOL_SCHEMA_LIMIT, "automatic git lease exceeds active schema cap")
    assert_true({"git_status", "git_diff", "run_command"}.issubset(selected), "git bundle incomplete")
    assert_true("write_file" not in selected, "git query should not receive write_file")

    search_prompt = [{"role": "user", "content": "search the codebase for switchboard profiles"}]
    tools, allowed, meta = swb._normalize_local_tools(None, search_prompt)
    selected = names(tools)
    assert_true(meta["intent"] == "search", f"expected search intent, got {meta['intent']}")
    assert_true(len(tools) <= swb.ACTIVE_TOOL_SCHEMA_LIMIT, "automatic search lease exceeds active schema cap")
    assert_true({"search_files", "read_file"}.issubset(selected), "search bundle incomplete")
    assert_true("check_service" not in selected, "search query should not receive sys-ops tools")

    edit_prompt = [{"role": "user", "content": "fix and validate the switchboard local tool profile"}]
    tools, allowed, meta = swb._normalize_local_tools(None, edit_prompt)
    assert_true(meta["intent"] == "file_edit", f"expected file_edit intent, got {meta['intent']}")
    assert_true(len(tools) <= swb.ACTIVE_TOOL_SCHEMA_LIMIT, "automatic file-edit lease exceeds active schema cap")

    explicit_tools, explicit_allowed, explicit_meta = swb._normalize_local_tools(
        [{"type": "function", "function": {"name": "write_file"}}],
        conversational,
    )
    assert_true(names(explicit_tools) == {"write_file"}, "explicit tool selection must override intent GC")
    assert_true(explicit_allowed == {"write_file"}, "explicit allowed tools mismatch")
    assert_true(explicit_meta["explicit"] is True, "explicit selection should be marked explicit")

    full_tools, full_allowed, full_meta = swb._normalize_local_tools(["*"], conversational)
    assert_true(len(full_tools) == full_meta["available_count"], "tools=['*'] should lease full registry")
    assert_true(len(full_allowed) == full_meta["available_count"], "full registry allowed tools mismatch")
    assert_true(len(full_tools) > swb.ACTIVE_TOOL_SCHEMA_LIMIT, "explicit full registry lease should bypass active schema cap")

    remote_payload = {
        "messages": conversational,
        "tools": [
            {"type": "function", "function": {"name": "git_status"}},
            {"type": "function", "function": {"name": "read_file"}},
        ],
    }
    filtered, remote_meta = swb._filter_remote_tools_for_working_set(remote_payload, "remote-tool-calling")
    assert_true("tools" not in filtered, "remote conversational prompt should unload explicit tools")
    assert_true(filtered["tool_choice"] == "none", "remote conversational prompt should disable tool choice")
    assert_true(remote_meta["intent"] == "conversational", "remote intent metadata mismatch")

    health_text = SWITCHBOARD_PATH.read_text(encoding="utf-8")
    assert_true('"tool_working_set"' in health_text, "health endpoint should expose working-set telemetry")
    assert_true('"active_schema_limit"' in health_text, "health endpoint should expose active schema cap telemetry")
    assert_true("X-AI-Tool-Intent" in health_text, "responses should include tool intent telemetry")
    assert_true("runtime leases a small active tool set" in health_text, "local tool card should harden active lease behavior")
    assert_true("strongest 2-4 evidence points" in health_text, "local tool card should bound broad analysis evidence gathering")

    print("PASS: Switchboard hot-loads tool bundles and evicts unused schemas")


if __name__ == "__main__":
    main()
