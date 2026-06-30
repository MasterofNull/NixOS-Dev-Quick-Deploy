#!/usr/bin/env python3
"""Verify aq-agent-loop marks planning-only loops incomplete."""

from __future__ import annotations

import importlib.machinery
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOOP = ROOT / "scripts" / "ai" / "aq-agent-loop"


def load_module():
    loader = importlib.machinery.SourceFileLoader("aq_agent_loop_under_test", str(AGENT_LOOP))
    return loader.load_module()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_repeated_thought_loop_is_incomplete() -> None:
    module = load_module()
    repeated = "\n\n".join([
        "Thought: I need to gather comprehensive information before producing a ranking report.",
        "Thought: I need to gather comprehensive information before producing a ranking report.",
        "Thought: I need to gather comprehensive information before producing a ranking report.",
        "Thought: Let me start by getting system info and exploring the directory structure.",
    ])
    assert_true(module._is_incomplete_result(repeated), "repeated planning-only thought text must be incomplete")


def test_real_completion_is_not_incomplete() -> None:
    module = load_module()
    result = (
        "COMPLETED: ranked the top 10 integrations, recorded security gates, "
        "and identified the first safe repo-local implementation slice."
    )
    assert_true(not module._is_incomplete_result(result), "completed answer must not be incomplete")


def main() -> int:
    tests = [test_repeated_thought_loop_is_incomplete, test_real_completion_is_not_incomplete]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"FAIL {test.__name__}: {exc}")
            print(failures[-1])
    if failures:
        return 1
    print(f"PASS {len(tests)} agent loop result quality checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
