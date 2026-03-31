#!/usr/bin/env python3
"""Regression checks for local continuation routing in task_classifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "task_classifier.py"
SPEC = importlib.util.spec_from_file_location("task_classifier_test_mod", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load task_classifier module")
task_classifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task_classifier)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    continuation_code = task_classifier.classify(
        "continue fixing the deployment bug from the last agent run",
        context="The previous change tightened the service dependency ordering and updated the failing module path.",
        max_output_tokens=300,
    )
    assert_true(continuation_code.task_type == "code", "expected continuation code task classification")
    assert_true(continuation_code.remote_required is False, "expected bounded continuation code task to stay local")
    assert_true(continuation_code.local_suitable is True, "expected bounded continuation code task to be local suitable")
    assert_true(
        continuation_code.reason == "continuation_within_local_capacity",
        "expected explicit continuation-local reason",
    )

    continuation_reasoning = task_classifier.classify(
        "resume the architecture tradeoff analysis for the current work",
        context="Prior context already narrowed the choice to two local-first options.",
        max_output_tokens=350,
    )
    assert_true(continuation_reasoning.task_type == "reasoning", "expected continuation reasoning task classification")
    assert_true(continuation_reasoning.remote_required is False, "expected bounded continuation reasoning task to stay local")

    large_reasoning = task_classifier.classify(
        "continue the architecture analysis for the current work",
        context="x" * 5000,
        max_output_tokens=500,
    )
    assert_true(large_reasoning.remote_required is True, "expected oversized continuation task to stay remote-required")

    print("PASS: task_classifier keeps bounded continuation work on local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
