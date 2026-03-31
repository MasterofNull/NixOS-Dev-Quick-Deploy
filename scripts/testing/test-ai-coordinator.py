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
    build_reasoning_finalization_messages,
    build_tool_call_finalization_messages,
    coerce_orchestration_context,
    default_runtime_id_for_profile,
    infer_profile,
    merge_runtime_defaults,
    prune_runtime_registry,
    route_by_complexity,
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

    continuation_route = route_by_complexity("continue the current work on the failing runtime slice", prefer_local=True)
    assert_true(continuation_route["recommended_profile"] == "default", "continuation routing should prefer local default lane")

    continuation_no_flag = route_by_complexity("resume the ongoing bounded repo task")
    assert_true(continuation_no_flag["recommended_profile"] == "default", "continuation routing should stay local-first by default")

    orchestration = coerce_orchestration_context({"agent_type": "continue", "role": "sub-agent"})
    assert_true(orchestration["requesting_agent"] == "continue", "orchestration should preserve requesting agent")
    assert_true(orchestration["requester_role"] == "sub-agent", "orchestration should preserve requester role")
    assert_true(orchestration["delegate_via_coordinator_only"] is True, "orchestration should enforce coordinator-only delegation")

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
        "Fix the bounded runtime cleanup regression in the coordinator slice.",
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
    assert_true("do not spawn, invoke, or route additional sub-agents" in messages[0]["content"].lower(), "system prompt should forbid nested sub-agent fan-out")
    assert_true("Expected artifact:" in messages[1]["content"], "user message should include artifact contract")
    assert_true("coordinator_handoff" in messages[1]["content"], "delegation contract should allow coordinator handoff instead of nested delegation")
    assert_true("Allowed repo paths:" in messages[1]["content"], "user message should include repo path allowlist")
    assert_true("Anti-goals:" in messages[1]["content"], "user message should include anti-goals when provided")
    assert_true("Completion rules:" in messages[1]["content"], "user message should include completion rules")
    assert_true("minimal patch sketch" in messages[1]["content"].lower(), "remote coding contract should stay patch-oriented")
    assert_true("root cause" in messages[1]["content"].lower(), "bugfix contract should request root-cause framing")
    assert_true("validation step" in messages[1]["content"].lower(), "bugfix contract should require concrete validation")

    reasoning_messages = build_messages(
        "Review the architecture risks in this coordinator slice.",
        context={"constraints": ["keep the output bounded to top risks and recommendation"]},
        profile="remote-reasoning",
    )
    assert_true("recommended direction first" in reasoning_messages[1]["content"].lower(), "remote reasoning contract should lead with decision guidance")
    assert_true("do not drift into patch design" in reasoning_messages[1]["content"].lower(), "remote reasoning contract should suppress patch drift")
    assert_true("residual risk" in reasoning_messages[1]["content"].lower(), "review contract should call out residual risk")

    free_messages = build_messages(
        "Summarize the most useful delegated findings.",
        context={"constraints": ["keep it short"]},
        profile="remote-free",
    )
    assert_true("main finding, evidence, and one next step" in free_messages[1]["content"].lower(), "remote free contract should stay compact")

    deploy_messages = build_messages(
        "Deploy this service safely and include rollback plus live verification.",
        context={"constraints": ["keep the deploy bounded to one service"]},
        profile="remote-free",
    )
    assert_true("live verification signal" in deploy_messages[1]["content"].lower(), "deploy contract should require live verification")
    assert_true("rollback path" in deploy_messages[1]["content"].lower(), "deploy contract should require rollback path")

    local_messages = build_messages(
        "Prepare a local tool-calling fallback contract.",
        context={"constraints": ["return explicit fallback if tools are unsupported"]},
        profile="local-tool-calling",
    )
    assert_true("local tool-calling prep sub-agent" in local_messages[0]["content"].lower(), "local tool-calling system prompt missing")
    assert_true("fallback" in local_messages[1]["content"].lower(), "local tool-calling artifact contract should mention fallback")
    assert_true("approved harness capabilities" in local_messages[1]["content"].lower(), "local tool-calling contract should stay bounded")

    remote_tool_messages = build_messages(
        "Produce a bounded tool-calling artifact.",
        context={"constraints": ["do not claim tool execution without evidence"]},
        profile="remote-tool-calling",
    )
    assert_true("tool-call-only output is insufficient" in remote_tool_messages[1]["content"].lower(), "remote tool-calling contract should forbid tool-call-only output")
    assert_true("do not claim any tool was executed" in remote_tool_messages[1]["content"].lower(), "remote tool-calling contract should forbid invented execution")

    research_messages = build_messages(
        "Research and summarize a bounded source dataset for native plants.",
        context={"constraints": ["keep it source-bounded"]},
        profile="remote-free",
    )
    assert_true("explicit sources" in research_messages[1]["content"].lower(), "research contract should require explicit sources")
    assert_true("extracted evidence" in research_messages[1]["content"].lower(), "research contract should separate evidence from summary")

    finalization_messages = build_tool_call_finalization_messages(
        "Summarize the next step after tool planning.",
        [{"name": "noop_status", "arguments": "{\"status\":\"TOOL_READY\"}"}],
        profile="remote-tool-calling",
    )
    assert_true(len(finalization_messages) == 2, "tool-call finalization should produce system and user messages")
    assert_true("bounded finalization pass" in finalization_messages[0]["content"].lower(), "finalization system prompt should explain remediation mode")
    assert_true("proposed tool-call plan" in finalization_messages[1]["content"].lower(), "finalization user prompt should summarize tool calls")

    reasoning_finalization_messages = build_reasoning_finalization_messages(
        "Review the main risk of overlong delegated prompt envelopes.",
        "Recommended direction: shorten the envelope and keep only one decision plus evidence.",
        profile="remote-reasoning",
    )
    assert_true(len(reasoning_finalization_messages) == 2, "reasoning finalization should produce system and user messages")
    assert_true("reasoning-only reply" in reasoning_finalization_messages[0]["content"].lower(), "reasoning finalization system prompt should explain remediation mode")
    assert_true("recovered reasoning draft" in reasoning_finalization_messages[1]["content"].lower(), "reasoning finalization user prompt should include recovered draft")

    print("PASS: ai-coordinator exposes default local/OpenRouter runtime lanes and profile inference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
