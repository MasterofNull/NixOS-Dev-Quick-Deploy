#!/usr/bin/env python3

import sys
from unittest.mock import MagicMock

sys.modules["config"] = MagicMock()
sys.modules["config"].Config = MagicMock(
    SWITCHBOARD_REMOTE_URL="https://openrouter.example/api",
    SWITCHBOARD_REMOTE_ALIAS_FREE="openrouter/free",
    SWITCHBOARD_REMOTE_ALIAS_CODING="openrouter/coding",
    SWITCHBOARD_REMOTE_ALIAS_REASONING="openrouter/reasoning",
    SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING="openrouter/tool-calling",
)

import ai_coordinator
from ai_coordinator import (
    build_messages,
    build_reasoning_finalization_messages,
    build_tool_call_finalization_messages,
    coerce_orchestration_context,
    default_runtime_id_for_profile,
    detect_query_complexity,
    extract_task_from_openai_messages,
    get_routing_stats,
    merge_runtime_defaults,
    prune_runtime_registry,
    route_by_complexity,
    route_openai_chat_payload,
    runtime_defaults,
)


def test_planning_defaults_to_lightweight_lane():
    decision = route_by_complexity(
        "Plan the next steps to stabilize the coordinator routing work and outline validation",
        prefer_local=False,
    )

    assert decision["task_archetype"] == "planning"
    assert decision["model_class"] == "lightweight"
    assert decision["recommended_profile"] == "remote-free"


def test_retrieval_prefers_local_when_requested():
    decision = route_by_complexity(
        "Search the docs and summarize the current switchboard model alias configuration",
        prefer_local=True,
    )

    assert decision["task_archetype"] == "retrieval"
    assert decision["model_class"] == "lightweight"
    assert decision["recommended_profile"] == "default"


def test_implementation_routes_to_coding_lane():
    decision = route_by_complexity(
        "Implement the coordinator patch to add model-aware task routing and update tests",
        prefer_local=False,
    )

    assert decision["task_archetype"] == "implementation"
    assert decision["model_class"] == "coding"
    assert decision["recommended_profile"] == "remote-coding"


def test_architecture_review_routes_to_reasoning_lane():
    decision = route_by_complexity(
        "Review the architecture tradeoffs for coordinator lane selection and security policy",
        prefer_local=False,
    )

    assert decision["task_archetype"] == "architecture-review"
    assert decision["model_class"] == "heavy-reasoning"
    assert decision["recommended_profile"] == "remote-reasoning"


def test_tool_calling_routes_to_tool_lane():
    decision = route_by_complexity(
        "Use MCP tool calling to inspect runtime status and return a bounded artifact",
        prefer_local=False,
    )

    assert decision["task_archetype"] == "tool-calling"
    assert decision["model_class"] == "tool-calling"
    assert decision["recommended_profile"] == "remote-tool-calling"


def test_detect_query_complexity_exposes_task_archetype():
    details = detect_query_complexity("Summarize the docs for the current coordinator routing flow")

    assert details["task_archetype"] == "retrieval"
    assert details["complexity"] == "simple"


def test_extract_task_from_openai_messages_prefers_recent_user_content():
    task = extract_task_from_openai_messages(
        [
            {"role": "system", "content": "Stay concise."},
            {"role": "user", "content": "Inspect the coordinator design."},
            {"role": "assistant", "content": "Working."},
            {"role": "user", "content": [{"type": "text", "text": "Plan the next implementation slice."}]},
        ]
    )

    assert "Inspect the coordinator design." in task
    assert "Plan the next implementation slice." in task


def test_route_openai_chat_payload_routes_tools_to_tool_calling_lane():
    decision = route_openai_chat_payload(
        {
            "messages": [{"role": "user", "content": "Use tools to inspect the repo and report the result."}],
            "tools": [{"type": "function", "function": {"name": "rg_search"}}],
        },
        prefer_local=False,
    )

    assert decision["recommended_profile"] == "remote-tool-calling"
    assert decision["tools_present"] is True


def test_route_openai_chat_payload_routes_continue_planning_to_lightweight_lane():
    decision = route_openai_chat_payload(
        {
            "messages": [{"role": "user", "content": "Plan the next steps for the Continue router migration."}],
        },
        prefer_local=True,
    )

    assert decision["recommended_profile"] == "default"
    assert decision["model_class"] == "lightweight"


def test_runtime_defaults_mark_remote_lanes_offline_without_remote_url():
    original_remote_url = ai_coordinator.Config.SWITCHBOARD_REMOTE_URL
    ai_coordinator.Config.SWITCHBOARD_REMOTE_URL = ""
    try:
        records = {item["runtime_id"]: item for item in runtime_defaults(now=123)}
    finally:
        ai_coordinator.Config.SWITCHBOARD_REMOTE_URL = original_remote_url

    assert records["local-hybrid"]["status"] == "ready"
    assert records["openrouter-free"]["status"] == "offline"
    assert records["openrouter-reasoning"]["status"] == "offline"


def test_merge_runtime_defaults_refreshes_default_records_but_keeps_custom_entries():
    merged = merge_runtime_defaults(
        {
            "runtimes": {
                "local-hybrid": {
                    "runtime_id": "local-hybrid",
                    "source": "ai-coordinator-default",
                    "created_at": 41,
                    "status": "offline",
                },
                "custom-runtime": {
                    "runtime_id": "custom-runtime",
                    "source": "user-managed",
                    "created_at": 77,
                    "status": "ready",
                },
            }
        },
        now=99,
    )

    local = merged["runtimes"]["local-hybrid"]
    custom = merged["runtimes"]["custom-runtime"]

    assert local["status"] == "ready"
    assert local["created_at"] == 41
    assert custom["status"] == "ready"
    assert custom["created_at"] == 77


def test_prune_runtime_registry_drops_only_stale_transient_records():
    registry = {
        "runtimes": {
            "smoke-runtime": {
                "runtime_id": "smoke-runtime",
                "source": "smoke",
                "created_at": 10,
                "updated_at": 10,
                "status": "ready",
            },
            "fresh-smoke": {
                "runtime_id": "fresh-smoke",
                "source": "smoke",
                "created_at": 990,
                "updated_at": 995,
                "status": "ready",
            },
            "persistent-runtime": {
                "runtime_id": "persistent-runtime",
                "source": "runtime-register",
                "persistent": True,
                "created_at": 10,
                "updated_at": 10,
                "status": "ready",
            },
        }
    }

    original_retention = getattr(ai_coordinator.Config, "AI_COORDINATOR_RUNTIME_RETENTION_SECONDS", "")
    ai_coordinator.Config.AI_COORDINATOR_RUNTIME_RETENTION_SECONDS = "300"
    try:
        pruned = prune_runtime_registry(registry, now=1000)
    finally:
        ai_coordinator.Config.AI_COORDINATOR_RUNTIME_RETENTION_SECONDS = original_retention

    runtimes = pruned["runtimes"]
    assert "smoke-runtime" not in runtimes
    assert "fresh-smoke" in runtimes
    assert "persistent-runtime" in runtimes
    assert "smoke-runtime" in pruned["meta"]["pruned_runtime_ids"]


def test_extract_task_from_openai_messages_falls_back_to_system_or_assistant_text():
    task = extract_task_from_openai_messages(
        [
            {"role": "assistant", "content": "Draft note."},
            {"role": "system", "content": {"text": "Fallback instructions."}},
        ]
    )

    assert task == "Fallback instructions."


def test_route_openai_chat_payload_uses_prompt_and_ignores_none_tool_choice():
    decision = route_openai_chat_payload(
        {
            "prompt": "Find the current deployment summary.",
            "tool_choice": "none",
        },
        prefer_local=False,
    )

    assert decision["task"] == "Find the current deployment summary."
    assert decision["recommended_profile"] == "remote-free"
    assert decision["tool_choice_requested"] is False


def test_default_runtime_id_for_profile_falls_back_to_remote_free():
    assert default_runtime_id_for_profile("unknown-profile") == "openrouter-free"


def test_get_routing_stats_rolls_up_recent_decisions():
    original_decisions = list(ai_coordinator._ROUTING_DECISIONS)
    ai_coordinator._ROUTING_DECISIONS = []
    try:
        route_by_complexity("Plan a bounded rollout validation", prefer_local=True)
        route_by_complexity("Implement the next patch set", prefer_local=False)
        stats = get_routing_stats()
    finally:
        ai_coordinator._ROUTING_DECISIONS = original_decisions

    assert stats["total_decisions"] == 2
    assert stats["complexity_breakdown"]["simple"] >= 1
    assert stats["profile_breakdown"]["default"] >= 1


def test_infer_profile_covers_requested_profile_and_task_fallbacks():
    assert ai_coordinator.infer_profile("ignored", requested_profile="continue-local") == "default"
    assert ai_coordinator.infer_profile("Need local tool call handling") == "local-tool-calling"
    assert ai_coordinator.infer_profile("Please call tools for this workflow") == "remote-tool-calling"
    assert ai_coordinator.infer_profile("Review the architecture tradeoff") == "remote-reasoning"
    assert ai_coordinator.infer_profile("Implement and debug the patch") == "remote-coding"
    assert ai_coordinator.infer_profile("Collect bounded research findings") == "remote-free"


def test_coerce_orchestration_context_normalizes_invalid_roles():
    normalized = coerce_orchestration_context({"requested_by": "continue", "role": "reviewer"})

    assert normalized["requesting_agent"] == "continue"
    assert normalized["requested_by"] == "continue"
    assert normalized["requester_role"] == "orchestrator"
    assert normalized["top_level_orchestrator"] is True
    assert normalized["delegate_via_coordinator_only"] is True


def test_build_messages_includes_contract_context_blocks():
    messages = build_messages(
        task="Deploy the ai-switchboard fix and verify rollback",
        context={
            "repo_paths": ["nix/modules/services/switchboard.nix"],
            "constraints": ["do not restart unrelated services"],
            "evidence_requirements": ["include systemctl status"],
            "anti_goals": ["no speculative refactors"],
            "extra_context": "The service failed with CHDIR before.",
        },
        profile="remote-coding",
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "implementation sub-agent" in messages[0]["content"]
    body = messages[1]["content"]
    assert "Allowed repo paths:" in body
    assert "- nix/modules/services/switchboard.nix" in body
    assert "Evidence requirements:" in body
    assert "Additional context:" in body


def test_build_tool_call_finalization_messages_handles_missing_and_present_calls():
    empty = build_tool_call_finalization_messages("Inspect tools", tool_calls=None)
    present = build_tool_call_finalization_messages(
        "Inspect tools",
        tool_calls=[{"name": "rg", "arguments": "{\"pattern\":\"TODO\"}"}, {"name": "jq"}],
    )

    assert "tool-call-only reply" in empty[0]["content"]
    assert "- no tool call details available" in empty[1]["content"]
    assert "- rg: {\"pattern\":\"TODO\"}" in present[1]["content"]
    assert "- jq" in present[1]["content"]


def test_build_reasoning_finalization_messages_truncates_excerpt_and_preserves_constraints():
    long_excerpt = "step " * 500
    messages = build_reasoning_finalization_messages("Review coordinator lane selection", long_excerpt)

    assert len(messages) == 2
    assert "reasoning-only reply" in messages[0]["content"]
    assert "Recovered reasoning draft:" in messages[1]["content"]
    assert "do not mention hidden reasoning" in messages[1]["content"]
    assert len(messages[1]["content"]) < 1600


def test_profile_completion_rules_cover_specialized_profiles():
    reasoning_rules = ai_coordinator._profile_completion_rules("remote-reasoning")
    free_rules = ai_coordinator._profile_completion_rules("remote-free")
    local_tool_rules = ai_coordinator._profile_completion_rules("local-tool-calling")
    remote_tool_rules = ai_coordinator._profile_completion_rules("remote-tool-calling")
    default_rules = ai_coordinator._profile_completion_rules("unknown")

    assert any("recommended direction" in rule for rule in reasoning_rules)
    assert any("main finding" in rule for rule in free_rules)
    assert any("OpenAI-compatible tool contract" in rule for rule in local_tool_rules)
    assert any("tool-call planning" in rule for rule in remote_tool_rules)
    assert any("assigned slice" in rule for rule in default_rules)


def test_task_shape_completion_rules_deduplicate_multi_shape_guidance():
    rules = ai_coordinator._task_shape_completion_rules(
        "Deploy fix and rollback switchboard failure review with retrieval source evidence",
        "remote-free",
    )

    assert any("verification signal" in rule for rule in rules)
    assert any("most likely root cause" in rule for rule in rules)
    assert any("recommended direction" in rule for rule in rules)
    assert any("explicit sources" in rule for rule in rules)
    assert len(rules) == len(set(rules))


def test_build_messages_adds_default_constraints_and_tool_completion_rules():
    messages = build_messages(
        task="Plan tool usage for the deploy review",
        context={"expected_artifact": "bounded tool plan"},
        profile="remote-tool-calling",
    )

    body = messages[1]["content"]
    assert "Expected artifact: bounded tool plan" in body
    assert "Constraints:" in body
    assert "- stay within the assigned slice" in body
    assert "Evidence requirements:" in body
    assert "- cite concrete files, commands, or runtime facts when available" in body
    assert "Tool-calling completion rules:" in body
