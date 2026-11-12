#!/usr/bin/env python3
"""Static regression checks for agent-pool integration in delegated routing."""

from pathlib import Path

from _coordinator_src import read


ROOT = Path(__file__).resolve().parents[2]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    # http_server.py is gone: the manager and status snapshot live in http_server_impl.py /
    # core/status_service.py, pool selection in workflow/delegation_handlers.py, the delegate
    # route in extensions/ai_coordinator_handlers.py.
    text = read(
        "http_server_impl.py",
        "core/status_service.py",
        "workflow/delegation_handlers.py",
        "extensions/ai_coordinator_handlers.py",
    )

    assert_true(
        "from agent_pool_manager import AgentPoolManager, RemoteAgent" in text,  # AgentTier dropped as dead in 80d2fd4a3
        "hybrid coordinator should import the offloading agent pool manager",
    )
    assert_true(
        "_AGENT_POOL_MANAGER = AgentPoolManager()" in text,
        "hybrid coordinator should initialize a shared agent pool manager",
    )
    assert_true(
        '\"agent_pool\": _agent_pool_status_snapshot()' in text,
        "status endpoint should expose agent-pool state",
    )
    assert_true(
        "def _select_agent_pool_candidate(" in text,
        "hybrid coordinator should define a pool selection helper",
    )
    assert_true(
        'if "model" not in payload and _remote_profile_uses_agent_pool(selected_profile):' in text,
        "remote-free delegation should select a pool-backed model when no explicit model is pinned",
    )
    assert_true(
        '_AGENT_POOL_MANAGER.mark_rate_limited(pool_agent.agent_id)' in text,
        "rate-limited delegated models should feed back into pool availability tracking",
    )
    assert_true(
        '"agent_pool_agent_id": pool_agent.agent_id if pool_agent else ""' in text,
        "delegate audit metadata should retain selected pool agent id",
    )
    assert_true(
        '"agent_pool": (' in text,
        "delegate response should expose pool selection details",
    )

    print("PASS: delegated routing is integrated with the remote agent pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
