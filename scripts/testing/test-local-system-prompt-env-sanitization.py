#!/usr/bin/env python3
"""Static regression checks for local system prompt env injection."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVERS_NIX = REPO_ROOT / "nix/modules/services/mcp-servers.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = MCP_SERVERS_NIX.read_text(encoding="utf-8")

    assert_true(
        'singleLineValue = value:' in text,
        "expected mcp-servers module to define single-line value normalization helper",
    )
    assert_true(
        'lib.replaceStrings ["\\r" "\\n"] [" " " "] value' in text,
        "expected single-line value helper to strip carriage returns and newlines",
    )
    assert_true(
        "AI_LOCAL_SYSTEM_PROMPT_IDENTITY=${singleLineValue ai.aiHarness.runtime.localSystemPrompt.identity}" in text,
        "expected local system prompt identity env injection to use single-line normalization",
    )

    print("PASS: local system prompt env injection is normalized to a single line")


if __name__ == "__main__":
    main()
