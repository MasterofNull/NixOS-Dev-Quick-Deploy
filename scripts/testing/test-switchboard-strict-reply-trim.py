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
    assert_true(
        "def _skip_profile_card_for_messages(profile: str, messages: list) -> bool:" in text,
        "expected switchboard to define a helper for profile-card bypass on tiny local replies",
    )
    assert_true(
        "return _looks_like_strict_reply_only(messages)" in text,
        "expected strict reply-only local prompts to bypass profile-card injection",
    )
    assert_true(
        "if _skip_profile_card_for_messages(profile, messages):" in text,
        "expected switchboard profile-card injection to skip strict reply-only local prompts",
    )
    assert_true(
        "def _looks_like_compact_guidance_request(messages: list) -> bool:" in text,
        "expected switchboard to detect compact guidance requests on local editor lanes",
    )
    assert_true(
        "def _apply_compact_local_response_budget(payload: dict, profile: str) -> dict:" in text,
        "expected switchboard to define a compact local response budget helper",
    )
    assert_true(
        'payload["max_tokens"] = max(32, target)' in text,
        "expected compact local guidance requests to clamp max_tokens",
    )
    assert_true(
        "target = 48" in text,
        "expected compact local guidance requests to clamp output budgets to 48 tokens",
    )
    assert_true(
        "payload = _apply_compact_local_response_budget(payload, profile)" in text,
        "expected switchboard request shaping to apply compact local response budgets",
    )
    assert_true(
        'compact_guidance = profile in ("continue-local", "embedded-assist") and _looks_like_compact_guidance_request(messages)' in text,
        "expected switchboard trimming to classify compact local guidance prompts before applying the tighter budget",
    )
    assert_true(
        "max_tokens = min(max_tokens, 128)" in text,
        "expected compact local guidance prompts to use a tighter input token budget",
    )
    assert_true(
        text.count("max_messages = min(max_messages, 2)") >= 2,
        "expected compact local guidance prompts to keep only the minimal turn window",
    )
    assert_true(
        "min_truncate_tokens = 48 if compact_guidance else 128" in text,
        "expected compact local guidance prompts to allow a lower truncation floor than generic prompts",
    )

    print("PASS: switchboard trims strict reply-only local prompts more aggressively")


if __name__ == "__main__":
    main()
