#!/usr/bin/env python3
"""Targeted checks for ai-coordinator default runtime lanes."""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from ai_coordinator import (  # noqa: E402
    build_messages,
    build_tool_call_finalization_messages,
    default_runtime_id_for_profile,
    infer_profile,
    merge_runtime_defaults,
    prune_runtime_registry,
)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    merged = merge_runtime_defaults({"runtimes": {}})
    runtime_ids = set((merged.get("runtimes", {}) or {}).keys())
    assert_true("local-hybrid" in runtime_ids, "local-hybrid default missing")
    assert_true("local-tool-calling" in runtime_ids, "local-tool-calling default missing")
    assert_true("openrouter-free" in runtime_ids, "openrouter-free default missing")
    assert_true("openrouter-coding" in runtime_ids, "openrouter-coding default missing")
    assert_true("openrouter-reasoning" in runtime_ids, "openrouter-reasoning default missing")
    assert_true("openrouter-tool-calling" in runtime_ids, "openrouter-tool-calling default missing")

    assert_true(infer_profile("review architecture tradeoffs") == "remote-reasoning", "reasoning profile inference failed")
    assert_true(infer_profile("implement patch for service failure") == "remote-coding", "coding profile inference failed")
    assert_true(infer_profile("gather quick external context") == "remote-free", "free profile inference failed")
    assert_true(infer_profile("prepare a local tool call for a future model") == "local-tool-calling", "local tool-calling profile inference failed")
    assert_true(infer_profile("use a tool call against the remote lane") == "remote-tool-calling", "remote tool-calling profile inference failed")
    assert_true(infer_profile("use the local lane", "continue-local") == "default", "continue-local should map to default lane")

    refreshed = merge_runtime_defaults(
        {
            "runtimes": {
                "local-hybrid": {
                    "runtime_id": "local-hybrid",
                    "name": "stale-name",
                    "source": "ai-coordinator-default",
                    "created_at": 123,
                }
            }
        }
    )
    local_runtime = refreshed["runtimes"]["local-hybrid"]
    assert_true(local_runtime["name"] == "Local Hybrid Coordinator", "default runtime record did not refresh")
    assert_true(local_runtime["created_at"] == 123, "refresh should preserve created_at")

    assert_true(default_runtime_id_for_profile("remote-free") == "openrouter-free", "free runtime mapping failed")
    assert_true(default_runtime_id_for_profile("remote-coding") == "openrouter-coding", "coding runtime mapping failed")
    assert_true(default_runtime_id_for_profile("remote-reasoning") == "openrouter-reasoning", "reasoning runtime mapping failed")
    assert_true(default_runtime_id_for_profile("remote-tool-calling") == "openrouter-tool-calling", "tool-calling runtime mapping failed")
    assert_true(default_runtime_id_for_profile("continue-local") == "local-hybrid", "continue-local runtime mapping failed")
    assert_true(default_runtime_id_for_profile("local-tool-calling") == "local-tool-calling", "local tool-calling runtime mapping failed")

    pruned = prune_runtime_registry(
        {
            "runtimes": {
                "smoke-1": {
                    "runtime_id": "smoke-1",
                    "name": "smoke-runtime",
                    "runtime_class": "sandboxed",
                    "tags": ["smoke"],
                    "updated_at": 1,
                },
                "gemini": {
                    "runtime_id": "gemini",
                    "name": "gemini",
                    "runtime_class": "remote-llm",
                    "tags": ["delegation", "remote", "gemini"],
                    "updated_at": 1,
                    "source": "runtime-register",
                    "persistent": True,
                },
            }
        },
        now=60 * 60 * 24,
    )
    pruned_ids = set((pruned.get("meta", {}) or {}).get("pruned_runtime_ids", []) or [])
    pruned_runtimes = set((pruned.get("runtimes", {}) or {}).keys())
    assert_true("smoke-1" in pruned_ids, "stale transient smoke runtime should be pruned")
    assert_true("smoke-1" not in pruned_runtimes, "pruned smoke runtime should not remain")
    assert_true("gemini" in pruned_runtimes, "persistent runtime registration should remain")
    assert_true("local-hybrid" in pruned_runtimes, "default runtime should be restored during prune merge")

    messages = build_messages(
        "Implement the bounded runtime cleanup slice.",
        context={
            "repo_paths": ["ai-stack/mcp-servers/hybrid-coordinator/http_server.py"],
            "constraints": ["do not invent extra files"],
            "evidence_requirements": ["cite concrete file paths"],
            "anti_goals": ["do not claim validation you did not run"],
        },
        profile="remote-coding",
    )
    assert_true(len(messages) == 2, "delegation envelope should produce system and user messages")
    assert_true("not the orchestrator" in messages[0]["content"].lower(), "system prompt should enforce sub-agent role")
    assert_true("Expected artifact:" in messages[1]["content"], "user message should include artifact contract")
    assert_true("Allowed repo paths:" in messages[1]["content"], "user message should include repo path allowlist")
    assert_true("Anti-goals:" in messages[1]["content"], "user message should include anti-goals when provided")

    local_messages = build_messages(
        "Prepare a local tool-calling fallback contract.",
        context={"constraints": ["return explicit fallback if tools are unsupported"]},
        profile="local-tool-calling",
    )
    assert_true("local tool-calling prep sub-agent" in local_messages[0]["content"].lower(), "local tool-calling system prompt missing")
    assert_true("fallback" in local_messages[1]["content"].lower(), "local tool-calling artifact contract should mention fallback")

    remote_tool_messages = build_messages(
        "Produce a bounded tool-calling artifact.",
        context={"constraints": ["do not claim tool execution without evidence"]},
        profile="remote-tool-calling",
    )
    assert_true("tool-call-only output is insufficient" in remote_tool_messages[1]["content"].lower(), "remote tool-calling contract should forbid tool-call-only output")
    assert_true("do not claim any tool was executed" in remote_tool_messages[1]["content"].lower(), "remote tool-calling contract should forbid invented execution")

    finalization_messages = build_tool_call_finalization_messages(
        "Summarize the next step after tool planning.",
        [{"name": "noop_status", "arguments": "{\"status\":\"TOOL_READY\"}"}],
        profile="remote-tool-calling",
    )
    assert_true(len(finalization_messages) == 2, "tool-call finalization should produce system and user messages")
    assert_true("bounded finalization pass" in finalization_messages[0]["content"].lower(), "finalization system prompt should explain remediation mode")
    assert_true("proposed tool-call plan" in finalization_messages[1]["content"].lower(), "finalization user prompt should summarize tool calls")

    print("PASS: ai-coordinator exposes default local/OpenRouter runtime lanes and profile inference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
