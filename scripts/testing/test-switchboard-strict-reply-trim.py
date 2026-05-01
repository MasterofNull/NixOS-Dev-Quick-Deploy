#!/usr/bin/env python3
"""Static regression for strict reply-only trimming on local switchboard lanes."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_NIX = REPO_ROOT / "nix/modules/services/switchboard.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SWITCHBOARD_NIX.read_text(encoding="utf-8")

    assert_true(
        "def _looks_like_strict_reply_only(messages: list) -> bool:" in text,
        "expected switchboard to define strict reply-only detection helper",
    )
    assert_true(
        'if profile in ("continue-local", "embedded-assist") and _looks_like_strict_reply_only(messages):' in text,
        "expected switchboard trimming to special-case strict reply-only local prompts",
    )
    assert_true(
        "max_tokens = min(max_tokens, 256)" in text,
        "expected strict reply-only local prompts to use a tighter token budget",
    )
    assert_true(
        "max_messages = min(max_messages, 2)" in text,
        "expected strict reply-only local prompts to keep only the minimal turn window",
    )

    print("PASS: switchboard trims strict reply-only local prompts more aggressively")


if __name__ == "__main__":
    main()
