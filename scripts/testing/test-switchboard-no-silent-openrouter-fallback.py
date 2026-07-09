#!/usr/bin/env python3
"""Regression: Gemini direct config must not silently reroute to OpenRouter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD = ROOT / "ai-stack" / "switchboard" / "switchboard.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SWITCHBOARD.read_text()
    mismatch_idx = text.find('REMOTE_API_KEY.startswith("sk-or-")')
    assert_true(mismatch_idx >= 0, "expected explicit OpenRouter-key/Gemini-endpoint mismatch guard")

    guard_block = text[mismatch_idx : mismatch_idx + 900]
    assert_true(
        "remote_key_endpoint_mismatch" in guard_block,
        "mismatch guard must return an explicit configuration error",
    )
    assert_true(
        "https://openrouter.ai/api" not in guard_block,
        "mismatch guard must not rewrite Gemini direct endpoint to OpenRouter",
    )
    assert_true(
        "meta-llama/llama-3.3-70b-instruct:free" not in guard_block,
        "mismatch guard must not rewrite Gemini models to OpenRouter fallback models",
    )
    assert_true(
        "Google AI Studio key" not in guard_block and "replace /run/secrets/remote_llm_api_key" not in guard_block,
        "mismatch guard must not recommend adding API keys for Antigravity fan-out",
    )

    print("PASS switchboard refuses silent OpenRouter fallback")


if __name__ == "__main__":
    main()
