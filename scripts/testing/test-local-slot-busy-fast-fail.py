#!/usr/bin/env python3
"""Static regression checks for local-slot-busy fast-fail on the switchboard."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_PATH = REPO_ROOT / "ai-stack/switchboard/switchboard.py"
MCP_SERVERS_NIX = REPO_ROOT / "nix/modules/services/mcp-servers.nix"
RUNTIME_PATH = REPO_ROOT / "ai-stack/agents/runtimes/local_agent_runtime.py"
HANDLERS_PATH = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    swb_text = SWITCHBOARD_PATH.read_text(encoding="utf-8")
    mcp_servers_text = MCP_SERVERS_NIX.read_text(encoding="utf-8")
    runtime_text = RUNTIME_PATH.read_text(encoding="utf-8")
    handlers_text = HANDLERS_PATH.read_text(encoding="utf-8")

    # Switchboard: LOCAL_CONCURRENCY default must be 1 (matches --parallel 1)
    assert_true(
        'os.environ.get("SWB_LOCAL_CONCURRENCY", "1")' in swb_text,
        "expected LOCAL_CONCURRENCY default to be 1 (matches llama --parallel 1)",
    )

    # Switchboard: local runtime health uses semaphore value peek.
    assert_true(
        "local_slot_available = int(_local_sem._value)" in swb_text,
        "expected switchboard to surface local semaphore availability",
    )

    # Switchboard: local semaphore applies to chat/completions on local target.
    assert_true(
        'path == "chat/completions"' in swb_text
        and 'target_type == "local"' in swb_text
        and "_begin_local_active_request(path, profile, payload, is_stream)" in swb_text,
        "expected local active-request tracking to be scoped to chat/completions on local target",
    )

    # Runtime: detects 503 local_slot_busy before raise_for_status and waits for a slot.
    assert_true(
        'resp.status_code == 503' in runtime_text,
        "expected local agent runtime to check for 503 before raise_for_status",
    )
    assert_true(
        'await _wait_for_llama_slot(client, state=state)' in runtime_text
        and "continue" in runtime_text,
        "expected local agent runtime to wait and retry on named local_slot_busy error",
    )
    assert_true(
        'client.get(f"{LLAMA_CPP_URL}/slots"' in runtime_text
        and 'client.get(f"{LLAMA_CPP_URL}/health"' not in runtime_text,
        "expected local agent runtime to use /slots, not /health, for slot availability",
    )
    assert_true(
        '"waiting_for_slot"' in runtime_text
        and '"queue_wait_s"' in runtime_text
        and '"slot_wait_state"' in runtime_text,
        "expected local agent runtime to expose queue-wait state while waiting for a slot",
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

    # Coordinator: advances fallback chain to remote profiles on slot_busy,
    # but only when remote routing is actually configured.
    assert_true(
        "_slot_busy_next_profile" in handlers_text,
        "expected delegate handler to track slot_busy fallback profile",
    )
    assert_true(
        "_lb_err.get(\"error\") == \"local_slot_busy\"" in handlers_text,
        "expected delegate handler to detect local_slot_busy in spawn response",
    )
    assert_true(
        "_select_local_slot_busy_advance_target(" in handlers_text,
        "expected delegate handler to centralize slot_busy remote-advance selection",
    )
    assert_true(
        "if not remote_configured:" in handlers_text,
        "expected slot_busy remote advance to stop when remote routing is not configured",
    )
    assert_true(
        "if requested_profile in _LOCAL_PROFILE_NAMES:" in handlers_text,
        "expected explicit local profiles to avoid remote advance on local_slot_busy",
    )
    assert_true(
        "delegation_slot_busy_advance" in handlers_text,
        "expected delegate handler to log slot_busy advance event",
    )
    assert_true(
        "delegation_slot_busy_no_remote_advance" in handlers_text,
        "expected delegate handler to log when slot_busy cannot advance because remote routing is unavailable",
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
        'if response.status_code == 503 and _response_error_type(response) == "local_slot_busy":' in handlers_text,
        "expected HTTP delegate path to return local_slot_busy 503 to the bounded retry wrapper before raise_for_status",
    )
    assert_true(
        'retryable_local_profiles = {"default", "continue-local", "embedded-assist", "local-tool-calling"}' in handlers_text,
        "expected bounded local slot retry to cover all local HTTP profiles including local-tool-calling",
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

    print("PASS: local-slot-busy fast-fail is wired end-to-end with explicit-local remote advance guarded")


if __name__ == "__main__":
    main()
