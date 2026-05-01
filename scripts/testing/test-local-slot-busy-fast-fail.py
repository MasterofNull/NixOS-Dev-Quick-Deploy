#!/usr/bin/env python3
"""Static regression checks for local-slot-busy fast-fail on the switchboard."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_NIX = REPO_ROOT / "nix/modules/services/switchboard.nix"
MCP_SERVERS_NIX = REPO_ROOT / "nix/modules/services/mcp-servers.nix"
RUNTIME_PATH = REPO_ROOT / "ai-stack/agents/runtimes/local_agent_runtime.py"
HANDLERS_PATH = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    swb_text = SWITCHBOARD_NIX.read_text(encoding="utf-8")
    mcp_servers_text = MCP_SERVERS_NIX.read_text(encoding="utf-8")
    runtime_text = RUNTIME_PATH.read_text(encoding="utf-8")
    handlers_text = HANDLERS_PATH.read_text(encoding="utf-8")

    # Switchboard: LOCAL_CONCURRENCY default must be 1 (matches --parallel 1)
    assert_true(
        'os.environ.get("SWB_LOCAL_CONCURRENCY", "1")' in swb_text,
        "expected LOCAL_CONCURRENCY default to be 1 (matches llama --parallel 1)",
    )

    # Switchboard: fast-fail check uses semaphore value peek
    assert_true(
        "_local_sem._value <= 0" in swb_text,
        "expected switchboard to fast-fail when local semaphore is exhausted",
    )

    # Switchboard: fast-fail returns a named local_slot_busy error type
    assert_true(
        '"type": "local_slot_busy"' in swb_text,
        "expected switchboard fast-fail to emit local_slot_busy error type",
    )

    # Switchboard: fast-fail only applies to chat/completions on local target
    assert_true(
        'path == "chat/completions"' in swb_text
        and 'target_type == "local"' in swb_text,
        "expected fast-fail gate to be scoped to chat/completions on local target",
    )

    # Runtime: detects 503 local_slot_busy before raise_for_status
    assert_true(
        'resp.status_code == 503' in runtime_text,
        "expected local agent runtime to check for 503 before raise_for_status",
    )
    assert_true(
        'raise RuntimeError("local_slot_busy")' in runtime_text,
        "expected local agent runtime to raise named local_slot_busy error",
    )

    # Coordinator: translates local_slot_busy into a 503 response (not 500)
    assert_true(
        'parsed_error.get("error") == "local_slot_busy"' in handlers_text,
        "expected delegate handler to detect local_slot_busy from agent stderr",
    )
    assert_true(
        '"error": "local_slot_busy"' in handlers_text
        and "status=503" in handlers_text,
        "expected delegate handler to return HTTP 503 for local_slot_busy",
    )

    # Coordinator: advances fallback chain to remote profiles on slot_busy
    assert_true(
        "_slot_busy_next_profile" in handlers_text,
        "expected delegate handler to track slot_busy fallback profile",
    )
    assert_true(
        "_lb_err.get(\"error\") == \"local_slot_busy\"" in handlers_text,
        "expected delegate handler to detect local_slot_busy in spawn response",
    )
    assert_true(
        "_is_remote_profile(c[\"profile\"])" in handlers_text,
        "expected delegate handler to filter fallback chain to remote-only on slot_busy",
    )
    assert_true(
        "delegation_slot_busy_advance" in handlers_text,
        "expected delegate handler to log slot_busy advance event",
    )
    assert_true(
        "_slot_busy_next_profile or selected_profile" in handlers_text,
        "expected HTTP delegate path to pick up slot_busy advance profile",
    )

    # Coordinator: lightweight local HTTP profiles get a bounded retry before
    # surfacing slot-busy back to the caller.
    assert_true(
        "_post_delegate_with_local_slot_retry" in handlers_text,
        "expected delegate handler to wrap HTTP delegate calls with local slot retry",
    )
    assert_true(
        'retryable_local_profiles = {"default", "continue-local", "embedded-assist"}' in handlers_text,
        "expected bounded local slot retry to target lightweight local profiles",
    )
    assert_true(
        'AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES' in handlers_text
        and 'AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_DELAY_S' in handlers_text,
        "expected local slot retry to be env-tunable",
    )
    assert_true(
        "delegation_local_slot_busy_retry" in handlers_text,
        "expected retry attempts to emit a dedicated log event",
    )
    assert_true(
        '"AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES=4"' in mcp_servers_text
        and '"AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_DELAY_S=15.0"' in mcp_servers_text
        and '"AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_BUDGET_FLOOR_S=5.0"' in mcp_servers_text,
        "expected deployed hybrid coordinator env to tune local slot retry behavior",
    )

    print("PASS: local-slot-busy fast-fail is wired end-to-end (switchboard → runtime → coordinator → remote advance)")


if __name__ == "__main__":
    main()
