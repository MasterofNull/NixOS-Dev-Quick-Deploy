#!/usr/bin/env python3
"""Phase 156: verify delegation_feedback contract detection accuracy."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2]
        / "ai-stack"
        / "mcp-servers"
        / "hybrid-coordinator"
        / "workflow"
    ),
)
from delegation_feedback import delegation_prompt_contract_signals


def test_json_contract_no_system_prompt_contamination() -> None:
    """Task 1: system prompt containing 'json' + 'only' must NOT set expects_json
    when the task itself does not ask for JSON."""
    task = "Reply with only the word PONG"
    messages = [{"role": "system", "content": "Output valid JSON only"}]
    signals = delegation_prompt_contract_signals(task, messages)
    assert signals["expects_json"] is False, (
        f"FAIL: expects_json should be False when task doesn't ask for JSON "
        f"(system prompt contamination), got: {signals}"
    )


def test_json_contract_explicit_in_task() -> None:
    """Task 2: task explicitly requesting JSON must set expects_json=True."""
    task = "Return a JSON object with fields: name, score"
    messages: list = []
    signals = delegation_prompt_contract_signals(task, messages)
    assert signals["expects_json"] is True, (
        f"FAIL: expects_json should be True when task explicitly requests JSON, got: {signals}"
    )


def test_exact_output_explicit_in_task() -> None:
    """Task 3: task asking for exact output must set expects_short_exact=True."""
    task = "Reply exactly: DONE and nothing else"
    messages: list = []
    signals = delegation_prompt_contract_signals(task, messages)
    assert signals["expects_short_exact"] is True, (
        f"FAIL: expects_short_exact should be True when task asks for exact output, got: {signals}"
    )


def test_exact_output_no_system_prompt_contamination() -> None:
    """Task 4: system prompt containing 'exactly' must NOT set expects_short_exact
    when the task itself does not ask for exact output."""
    task = "Summarize this code"
    messages = [{"role": "system", "content": "Respond exactly with structured output"}]
    signals = delegation_prompt_contract_signals(task, messages)
    assert signals["expects_short_exact"] is False, (
        f"FAIL: expects_short_exact should be False when task doesn't ask for exact output "
        f"(system prompt contamination), got: {signals}"
    )


def main() -> None:
    tests = [
        test_json_contract_no_system_prompt_contamination,
        test_json_contract_explicit_in_task,
        test_exact_output_explicit_in_task,
        test_exact_output_no_system_prompt_contamination,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"  ERROR {t.__name__}: {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
