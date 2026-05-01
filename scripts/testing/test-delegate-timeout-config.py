#!/usr/bin/env python3
"""Static regression checks for delegated timeout layering configuration."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OPTIONS_PATH = REPO_ROOT / "nix/modules/core/options.nix"
MCP_SERVERS_PATH = REPO_ROOT / "nix/modules/services/mcp-servers.nix"
HANDLERS_PATH = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    options_text = OPTIONS_PATH.read_text(encoding="utf-8")
    service_text = MCP_SERVERS_PATH.read_text(encoding="utf-8")
    handlers_text = HANDLERS_PATH.read_text(encoding="utf-8")

    assert_true(
        "delegateTimeoutSeconds = lib.mkOption" in options_text,
        "expected declarative delegate timeout option in core options",
    )
    assert_true(
        "delegateInnerSlackSeconds = lib.mkOption" in options_text,
        "expected declarative delegate timeout slack option in core options",
    )
    assert_true(
        '"AI_DELEGATE_TIMEOUT_S=${toString ai.aiHarness.runtime.delegateTimeoutSeconds}"' in service_text,
        "expected hybrid coordinator service to inject AI_DELEGATE_TIMEOUT_S",
    )
    assert_true(
        '"AI_DELEGATE_TIMEOUT_SLACK_S=${toString ai.aiHarness.runtime.delegateInnerSlackSeconds}"' in service_text,
        "expected hybrid coordinator service to inject AI_DELEGATE_TIMEOUT_SLACK_S",
    )
    assert_true(
        'delegate_timeout_slack_s = float(os.getenv("AI_DELEGATE_TIMEOUT_SLACK_S", "30"))' in handlers_text,
        "expected delegate handler to read timeout slack from env",
    )
    assert_true(
        "local_agent_timeout_s = max(1.0, timeout_s - min(delegate_timeout_slack_s, max(1.0, timeout_s * 0.125)))" in handlers_text,
        "expected delegate handler to reserve inner timeout slack",
    )
    assert_true(
        '"AGENT_TIMEOUT": str(agent_timeout_sec if agent_timeout_sec is not None else timeout_sec)' in handlers_text,
        "expected local agent spawn path to use split inner timeout",
    )
    assert_true(
        "agent_timeout_sec=local_agent_timeout_s," in handlers_text,
        "expected delegate handler to pass inner timeout budget into local agent spawns",
    )
    assert_true(
        'parsed_error.get("error") == "local_agent_timeout"' in handlers_text,
        "expected delegate handler to translate named local agent timeouts into 504 responses",
    )

    print("PASS: delegated timeout layering stays declarative and split across outer/inner budgets")


if __name__ == "__main__":
    main()
