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
    assert_true(
        "Relevant context" in str(continuation_code.optimized_prompt or "")
        and len(str(continuation_code.optimized_prompt or "")) < 900,
        "expected continuation prompt shaping to keep context excerpts bounded",
    )

    continuation_reasoning = task_classifier.classify(
        "resume the architecture tradeoff analysis for the current work",
        context="Prior context already narrowed the choice to two local-first options.",
        max_output_tokens=350,
    )
    assert_true(continuation_reasoning.task_type == "reasoning", "expected continuation reasoning task classification")
    assert_true(continuation_reasoning.remote_required is False, "expected bounded continuation reasoning task to stay local")

    bounded_reasoning = task_classifier.classify(
        "analyze repeated query latency across cache hits and misses after local retrieval warming in this stack",
        context="Recent reports show cache hit rate above 70% and most repeated queries already stay on the local lane.",
        max_output_tokens=240,
    )
    assert_true(bounded_reasoning.task_type == "reasoning", "expected longer bounded reasoning task classification")
    assert_true(bounded_reasoning.remote_required is False, "expected longer bounded reasoning task to stay local")
    assert_true(
        bounded_reasoning.reason == "bounded_reasoning_within_local_capacity",
        "expected explicit bounded local reasoning reason",
    )
    assert_true(
        "Relevant context" in str(bounded_reasoning.optimized_prompt or "")
        and len(str(bounded_reasoning.optimized_prompt or "")) < 750,
        "expected bounded reasoning prompt shaping to keep context excerpts bounded",
    )

    short_explanation = task_classifier.classify(
        "explain how local routing and cache reuse reduce repeated query latency",
        context="Recent reports show cache hit rate above 70% and most repeated queries already stay on the local lane.",
        max_output_tokens=240,
    )
    assert_true(short_explanation.task_type == "synthesize", "expected short explanation task to downgrade to synthesize")
    assert_true(short_explanation.remote_required is False, "expected short explanation task to stay local")
    assert_true(
        short_explanation.reason == "within_local_capacity",
        "expected downgraded short explanation task to use the bounded synthesize path",
    )
    assert_true(
        "one short paragraph under 70 words" in str(short_explanation.optimized_prompt or "")
        and len(str(short_explanation.optimized_prompt or "")) < 700,
        "expected short explanation synthesize prompt to stay compact",
    )

    brief_reasoning = task_classifier.classify(
        "explain briefly how local routing and cache reuse reduce repeated query latency",
        context="Recent reports show cache hit rate above 70% and repeated lookups are already staying local.",
        max_output_tokens=160,
    )
    assert_true(brief_reasoning.task_type == "synthesize", "expected explicitly brief reasoning request to downgrade to synthesize")
    assert_true(brief_reasoning.remote_required is False, "expected explicitly brief reasoning request to stay local")
    assert_true(
        brief_reasoning.reason == "within_local_capacity",
        "expected downgraded brief reasoning request to use the bounded synthesize path",
    )

    architecture_reasoning = task_classifier.classify(
        "design the long-term architecture strategy for hybrid routing and delegation",
        context="The system has multiple local and remote lanes with policy tradeoffs.",
        max_output_tokens=240,
    )
    assert_true(architecture_reasoning.remote_required is True, "expected architecture-heavy reasoning to stay remote-required")

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
