#!/usr/bin/env python3
"""Static regression checks for delegated response budget wiring."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py"
HANDLERS = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    coordinator_text = COORDINATOR.read_text(encoding="utf-8")
    handlers_text = HANDLERS.read_text(encoding="utf-8")

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

    print("PASS: delegated response budget is wired into coordinator dispatch")


if __name__ == "__main__":
    main()
