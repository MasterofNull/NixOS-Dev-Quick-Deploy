#!/usr/bin/env python3
"""Hermetic checks for bounded local-agent skill projection."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))

from local_skill_projection import SkillProjection, select_local_skills  # noqa: E402
from agent_executor import AgentType, LocalAgentExecutor  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _fake_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    selector = root / "scripts" / "ai" / "aq-skill-auto"
    selector.parent.mkdir(parents=True)
    selector.write_text("#!/bin/sh\n", encoding="utf-8")
    for name, content in {
        "testing-patterns": "TESTING INSTRUCTION\n" + "x" * 1_200,
        "aq-workflow": "WORKFLOW INSTRUCTION\n" + "y" * 1_200,
    }.items():
        target = root / ".agent" / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_selection_and_prompt_reachability() -> None:
    root = _fake_repo()

    def runner(command, **kwargs):
        require(command[0] == str(root / "scripts" / "ai" / "aq-skill-auto"), "must use existing selector")
        require(command[-2:] == ["--json", "--test"], "selector must validate selected skills")
        require(kwargs["timeout"] <= 8 and kwargs["capture_output"] is True,
                "selector execution must be bounded/read-only")
        return subprocess.CompletedProcess(command, 0, '{"status":"ok","reference_skills":["testing-patterns","aq-workflow"]}', "")

    projection = select_local_skills("test a bounded local task", repo_root=root, runner=runner)
    require(projection.status == "selected", f"unexpected projection: {projection}")
    require(projection.skill_names == ("testing-patterns", "aq-workflow"), "selected names must survive projection")
    require(len(projection.prompt) <= 2_000, "prompt projection must remain bounded")
    require("TESTING INSTRUCTION" in projection.prompt and "WORKFLOW INSTRUCTION" in projection.prompt,
            "only selected instructions must be present")
    prompt = LocalAgentExecutor(fallback_endpoint="")._get_system_prompt(
        AgentType.AGENT, [], "test a bounded local task", projection.prompt,
    )
    require(projection.prompt in prompt, "selected instructions must reach the local system prompt")


def test_selector_failure_is_visible_and_safe() -> None:
    root = _fake_repo()

    def failing_runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("aq-skill-auto", 8)

    projection = select_local_skills("task", repo_root=root, runner=failing_runner)
    require(projection.status == "degraded" and projection.reason == "selector-unreadable",
            f"selector failure must be typed degraded, got {projection}")
    require(not projection.skill_names and "unavailable" in projection.prompt,
            "selector failure must be visible without catalog fallback")
    over_budget = LocalAgentExecutor(fallback_endpoint="")._get_system_prompt(
        AgentType.AGENT, [], "task", "x" * 2_001,
    )
    require("x" * 100 not in over_budget, "oversized projection must be rejected at the prompt boundary")


def test_invalid_selector_output_fails_closed_and_loop_is_wired() -> None:
    root = _fake_repo()
    projection = select_local_skills(
        "task", repo_root=root,
        runner=lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, '{"status":"ok","reference_skills":["a","b","c"]}', "",
        ),
    )
    require(projection.status == "degraded" and projection.reason == "selector-invalid-skill-count",
            "more than two selected skills must fail closed")
    loop_source = (ROOT / "scripts" / "ai" / "aq-agent-loop").read_text(encoding="utf-8")
    require("select_local_skills(task_text, repo_root=_REPO_ROOT)" in loop_source,
            "aq-agent-loop must select skills before constructing its Task")
    require('"_local_skill_projection": skill_projection.prompt' in loop_source,
            "aq-agent-loop must pass bounded projection to the executor context")


def main() -> int:
    test_selection_and_prompt_reachability()
    test_selector_failure_is_visible_and_safe()
    test_invalid_selector_output_fails_closed_and_loop_is_wired()
    print("PASS: local skill projection is bounded, visible on degradation, and reaches system prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
