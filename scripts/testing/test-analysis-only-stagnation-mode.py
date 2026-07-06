#!/usr/bin/env python3
"""Regression coverage for long-horizon analysis-only local-agent mode."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LIB = REPO / "scripts" / "ai" / "lib"
EXECUTOR = REPO / "ai-stack" / "local-agents" / "agent_executor.py"

sys.path.insert(0, str(LIB))


def assert_eq(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_agent_analysis_prompt_routes_to_research() -> None:
    dispatch = _load("dispatch", LIB / "dispatch.py")
    prompt = (
        "analysis only: read these local artifacts, produce a ranked_remaining_slices "
        "plan with dependency_order and validation_plan. Do not edit files."
    )
    assert_eq(dispatch.classify_task_type(prompt, "agent"), "research", "analysis prompt task_type")


def test_analysis_alias_normalizes_to_research() -> None:
    task_config = _load("task_config", LIB / "task_config.py")
    cfg = task_config.TaskConfig.from_args(
        mode="agent",
        role="architect",
        timeout_secs=300,
        max_tokens=None,
        llama_url="http://127.0.0.1:8080",
        hybrid_url="http://127.0.0.1:8003",
        ralph_url="http://127.0.0.1:8004",
        task_type="analysis_only",
    )
    assert_eq(cfg.task_type, "research", "analysis_only alias")


def test_executor_has_separate_analysis_guard() -> None:
    src = EXECUTOR.read_text()
    impl_hard = re.search(r"_IMPLEMENTATION_READS_HARD_LIMIT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
    analysis_hard = re.search(r"_ANALYSIS_READS_HARD_LIMIT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
    assert_true(impl_hard is not None, "implementation hard limit missing")
    assert_true(analysis_hard is not None, "analysis hard limit missing")
    assert_true(int(impl_hard.group(1)) == 12, "implementation hard limit must stay strict")
    assert_true(int(analysis_hard.group(1)) > 12, "analysis guard must allow long reads")
    assert_true("Analysis checkpoint stagnation" in src, "analysis checkpoint abort missing")
    assert_true('"store_memory"' in src and "_read_path_counts.clear()" in src, "checkpoint reset missing")
    assert_true("_REPEATED_READ_PATH_LIMIT" in src, "repeated-read guard missing")
    assert_true("STOP READING" in src and "exactly ONE edit" in src, "single-edit-first nudge missing")


if __name__ == "__main__":
    tests = [
        test_agent_analysis_prompt_routes_to_research,
        test_analysis_alias_normalizes_to_research,
        test_executor_has_separate_analysis_guard,
    ]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
