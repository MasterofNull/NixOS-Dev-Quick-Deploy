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
