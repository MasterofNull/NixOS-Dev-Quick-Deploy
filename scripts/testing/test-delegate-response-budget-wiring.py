#!/usr/bin/env python3
"""Static regression checks for delegated response budget wiring."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py"
HANDLERS = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py"
DELEGATION = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/delegation_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    coordinator_text = COORDINATOR.read_text(encoding="utf-8")
    handlers_text = HANDLERS.read_text(encoding="utf-8")
    delegation_text = DELEGATION.read_text(encoding="utf-8")

    assert_true(
        "def delegated_response_budget(" in coordinator_text,
        "expected ai_coordinator to define delegated response budget helper",
    )
    assert_true(
        "_STRICT_REPLY_ONLY_RE" in coordinator_text,
        "expected delegated response budget policy to special-case strict reply-only asks",
    )
    assert_true(
        "delegated_response_budget as _ai_coordinator_delegated_response_budget" in handlers_text,
        "expected delegate handler to import delegated response budget helper",
    )
    assert_true(
        "delegated_max_tokens = _ai_coordinator_delegated_response_budget(" in handlers_text,
        "expected delegate handler to compute a bounded delegated max_tokens value",
    )
    assert_true(
        'payload["max_tokens"] = delegated_max_tokens' in handlers_text,
        "expected delegate handler to inject bounded delegated max_tokens into the payload",
    )
    assert_true(
        "def _should_short_circuit_to_continue_local_http(" in handlers_text,
        "expected delegate handler to define a short-circuit helper for tiny local delegate asks",
    )
    assert_true(
        'selected_profile = "continue-local"' in handlers_text,
        "expected tiny local delegate asks to bypass subprocess spawn onto continue-local HTTP",
    )
    assert_true(
        "[local-fast-path:continue-local-http]" in handlers_text,
        "expected delegate routing rationale to record continue-local HTTP fast-path selection",
    )
    assert_true(
        "def _should_skip_progressive_context_for_tiny_local_reply(" in delegation_text,
        "expected delegation helpers to define a tiny-local-reply context skip helper",
    )
    assert_true(
        "skipped_for_tiny_local_reply" in delegation_text,
        "expected progressive-context helper to record tiny-local-reply skips",
    )
    assert_true(
        "_should_skip_progressive_context_for_tiny_local_reply(" in handlers_text,
        "expected delegate handler to consult the tiny-local-reply context skip helper",
    )
    assert_true(
        'progressive_context_meta = {"applied": False, "skipped_for_tiny_local_reply": True}' in handlers_text,
        "expected tiny local reply fast-path to bypass progressive context injection",
    )
    assert_true(
        'prompt_optimization = {"applied": False, "skipped_for_tiny_local_reply": True}' in handlers_text,
        "expected tiny local reply fast-path to bypass delegated prompt optimization",
    )

    print("PASS: delegated response budget is wired into coordinator dispatch")


if __name__ == "__main__":
    main()
