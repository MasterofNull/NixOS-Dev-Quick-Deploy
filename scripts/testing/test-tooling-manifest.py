#!/usr/bin/env python3
"""Targeted checks for harness tooling-manifest loop orchestration exposure."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from tooling_manifest import build_tooling_manifest, workflow_tool_catalog  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    agentic_query = "orchestrate a long-running multi-agent workflow to implement and verify a repo change"
    agentic_tools = workflow_tool_catalog(agentic_query)
    agentic_tool_names = [tool["name"] for tool in agentic_tools]
    assert_true("ai_coordinator_delegate" in agentic_tool_names, "ai_coordinator_delegate missing for agentic query")
    assert_true("loop_orchestrate" in agentic_tool_names, "loop_orchestrate missing for agentic query")
    assert_true("loop_status" in agentic_tool_names, "loop_status missing for agentic query")

    manifest = build_tooling_manifest(agentic_query, agentic_tools)
    manifest_tool_names = [tool["name"] for tool in manifest["tools"]]
    assert_true("ai_coordinator_delegate" in manifest_tool_names, "manifest omits ai_coordinator_delegate")
    assert_true("loop_orchestrate" in manifest_tool_names, "manifest omits loop_orchestrate")
    assert_true(any(phase["id"] == "execute" and "ai_coordinator_delegate" in phase["tools"] for phase in manifest["phases"]),
                "execute phase does not expose ai_coordinator_delegate")
    assert_true(any(phase["id"] == "execute" and "loop_orchestrate" in phase["tools"] for phase in manifest["phases"]),
                "execute phase does not expose loop_orchestrate")
    assert_true(any(phase["id"] == "validate" and "loop_status" in phase["tools"] for phase in manifest["phases"]),
                "validate phase does not expose loop_status")

    simple_query = "find the relevant nixos option for openssh"
    simple_tools = workflow_tool_catalog(simple_query)
    simple_tool_names = [tool["name"] for tool in simple_tools]
    assert_true("loop_orchestrate" not in simple_tool_names, "simple query should not default to loop_orchestrate")

    research_query = "scrape a public native plant database page and extract the relevant sections"
    research_tools = workflow_tool_catalog(research_query)
    research_tool_names = [tool["name"] for tool in research_tools]
    assert_true("web_research_fetch" in research_tool_names, "web research query missing web_research_fetch")
    assert_true("curated_research_fetch" in research_tool_names, "web research query missing curated_research_fetch")
    research_manifest = build_tooling_manifest(research_query, research_tools)
    assert_true(
        any(tool["name"] == "web_research_fetch" for tool in research_manifest["tools"]),
        "manifest omits web_research_fetch",
    )
    assert_true(
        any(tool["name"] == "curated_research_fetch" for tool in research_manifest["tools"]),
        "manifest omits curated_research_fetch",
    )
    assert_true(
        any(phase["id"] == "execute" and "web_research_fetch" in phase["tools"] for phase in research_manifest["phases"]),
        "execute phase does not expose web_research_fetch",
    )
    assert_true(
        any(phase["id"] == "execute" and "curated_research_fetch" in phase["tools"] for phase in research_manifest["phases"]),
        "execute phase does not expose curated_research_fetch",
    )

    skill_query = "find a shared skill from agentskill and show the approved catalog"
    skill_tools = workflow_tool_catalog(skill_query)
    skill_tool_names = [tool["name"] for tool in skill_tools]
    assert_true("shared_skill_registry" in skill_tool_names, "skill query missing shared_skill_registry")
    skill_manifest = build_tooling_manifest(skill_query, skill_tools)
    assert_true(
        any(tool["name"] == "shared_skill_registry" for tool in skill_manifest["tools"]),
        "manifest omits shared_skill_registry",
    )
    assert_true(
        any(phase["id"] == "discover" and "shared_skill_registry" in phase["tools"] for phase in skill_manifest["phases"]),
        "discover phase does not expose shared_skill_registry",
    )

    print("PASS: tooling manifest exposes Ralph loop orchestration only when agentic workflow intent is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
