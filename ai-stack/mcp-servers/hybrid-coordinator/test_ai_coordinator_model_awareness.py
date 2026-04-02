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

from ai_coordinator import detect_query_complexity, route_by_complexity


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
