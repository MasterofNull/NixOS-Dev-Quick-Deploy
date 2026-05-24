#!/usr/bin/env python3
"""Static regression for local tool-budget finalization in Switchboard."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD = REPO_ROOT / "ai-stack" / "switchboard" / "switchboard.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SWITCHBOARD.read_text(encoding="utf-8")

    assert_true(
        "async def _finalize_after_local_tool_limit" in text,
        "expected Switchboard to define a forced finalization pass after local tool budget exhaustion",
    )
    assert_true(
        '"tools", "tool_choice", "max_tool_calls"' in text,
        "expected finalization payload to remove tool schemas and max_tool_calls",
    )
    assert_true(
        "Stop calling tools. Produce the best final answer now from the completed tool outputs." in text,
        "expected finalization prompt to force a tool-free final answer",
    )
    assert_true(
        "local_tool_finalization" in text and "forced_tool_free" in text,
        "expected final response metadata to distinguish forced finalization from fallback",
    )
    assert_true(
        "local_tool_call_limit_exhausted" in text,
        "expected skipped pending tool calls to receive explicit budget-exhausted tool observations",
    )
    assert_true(
        "raise RuntimeError(f\"local tool-call limit exceeded" not in text,
        "tool budget exhaustion must not surface as a 502 RuntimeError",
    )

    print("PASS: Switchboard finalizes local tool-budget exhaustion instead of returning a 502")


if __name__ == "__main__":
    main()
