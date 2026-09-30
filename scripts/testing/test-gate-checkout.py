#!/usr/bin/env python3
"""Test suite for aq-gate-checkout.

Verifies:
1. Basic acquire and release lifecycle.
2. Re-entrant/idempotent acquisition by same PID.
3. Mutual exclusion between distinct processes.
4. Wait timeout when gate is held.
5. Dead-PID auto-reclaim when previous holder crashed.
6. Context runner (aq-gate-checkout run) cleans up on exit.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKOUT_CLI = REPO_ROOT / "scripts" / "ai" / "aq-gate-checkout"
CHECKOUTS_DIR = REPO_ROOT / ".agent" / "collaboration" / "gate-checkouts"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKOUT_CLI), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_basic_acquire_release() -> None:
    gate = "test-gate-basic"
    # Ensure clean start
    run_cli("release", "--gate", gate, "--force")

    # Acquire
    res = run_cli("acquire", "--gate", gate, "--agent", "test-agent", "--task", "test-task")
    assert res.returncode == 0, f"Acquire failed: {res.stderr}"

    # Status
    res_status = run_cli("status", "--gate", gate, "--json")
    assert res_status.returncode == 0
    status_data = json.loads(res_status.stdout)
    assert status_data["status"] == "CHECKED_OUT"
    assert status_data["holder_agent"] == "test-agent"
    assert status_data["holder_task"] == "test-task"

    # Release
    res_rel = run_cli("release", "--gate", gate)
    assert res_rel.returncode == 0, f"Release failed: {res_rel.stderr}"

    # Status should be AVAILABLE
    res_avail = run_cli("status", "--gate", gate, "--json")
    status_avail = json.loads(res_avail.stdout)
    assert status_avail["status"] == "AVAILABLE"
    print("PASS: test_basic_acquire_release")


def test_idempotent_acquire() -> None:
    gate = "test-gate-idempotent"
    run_cli("release", "--gate", gate, "--force")

    res1 = run_cli("acquire", "--gate", gate, "--agent", "agent-a")
    assert res1.returncode == 0

    # Same process acquires again
    res2 = run_cli("acquire", "--gate", gate, "--agent", "agent-a")
    assert res2.returncode == 0

    run_cli("release", "--gate", gate)
    print("PASS: test_idempotent_acquire")


def test_contention_and_timeout() -> None:
    gate = "test-gate-contention"
    run_cli("release", "--gate", gate, "--force")

    # Acquire with an external PID (e.g. current PID)
    res_acq = run_cli("acquire", "--gate", gate, "--agent", "holder-agent", "--pid", str(os.getpid()))
    assert res_acq.returncode == 0

    # Try to acquire from simulated different PID with short wait
    res_block = run_cli(
        "acquire",
        "--gate", gate,
        "--agent", "blocked-agent",
        "--pid", "999999",  # Will try as PID 999999
        "--wait", "1",
    )
    # Should timeout because current PID is still alive and holding it
    assert res_block.returncode == 2, f"Expected returncode 2 on timeout, got {res_block.returncode}: {res_block.stderr}"
    assert "TIMEOUT" in res_block.stderr or "held by" in res_block.stderr

    # Release
    run_cli("release", "--gate", gate, "--pid", str(os.getpid()))
    print("PASS: test_contention_and_timeout")


def test_dead_pid_reclaim() -> None:
    gate = "test-gate-dead-pid"
    run_cli("release", "--gate", gate, "--force")

    # Manually craft a lease with a non-existent PID
    CHECKOUTS_DIR.mkdir(parents=True, exist_ok=True)
    lease_file = CHECKOUTS_DIR / f"{gate}.json"
    dead_pid = 9999999
    while True:
        try:
            os.kill(dead_pid, 0)
            dead_pid += 1
        except OSError:
            break

    lease_data = {
        "gate": gate,
        "holder_agent": "crashed-agent",
        "holder_pid": dead_pid,
        "holder_task": "dead task",
        "claimed_at": "2026-01-01T00:00:00Z",
        "claimed_at_epoch": time.time(),
        "ttl_seconds": 900,
        "hostname": "localhost",
    }
    with open(lease_file, "w") as f:
        json.dump(lease_data, f)

    # Acquire should detect dead PID and reclaim immediately without waiting
    t0 = time.time()
    res = run_cli("acquire", "--gate", gate, "--agent", "survivor-agent")
    t1 = time.time()

    assert res.returncode == 0, f"Dead PID reclaim failed: {res.stderr}"
    assert (t1 - t0) < 3.0, f"Dead PID reclaim took too long ({t1 - t0:.2f}s)"

    # Verify survivor holds it
    res_status = run_cli("status", "--gate", gate, "--json")
    status_data = json.loads(res_status.stdout)
    assert status_data["holder_agent"] == "survivor-agent"

    run_cli("release", "--gate", gate)
    print("PASS: test_dead_pid_reclaim")


def test_run_command_wrapper() -> None:
    gate = "test-gate-run"
    run_cli("release", "--gate", gate, "--force")

    # Execute a simple echo command via run
    res = run_cli(
        "run",
        "--gate", gate,
        "--agent", "runner-agent",
        "--",
        sys.executable, "-c", "import sys; sys.exit(0)",
    )
    assert res.returncode == 0, f"Run command failed: {res.stderr}"

    # Verify released automatically
    res_avail = run_cli("status", "--gate", gate, "--json")
    status_avail = json.loads(res_avail.stdout)
    assert status_avail["status"] == "AVAILABLE"
    print("PASS: test_run_command_wrapper")


def test_nested_checkout_rejected() -> None:
    gate = "test-gate-nested"
    cli = str(REPO_ROOT / "scripts/ai/aq-gate-checkout")
    child = (
        "import os, subprocess, sys; "
        "r = subprocess.run([sys.executable, sys.argv[1], 'acquire', "
        "'--gate', sys.argv[2], '--pid', str(os.getpid()), '--wait', '30'], "
        "capture_output=True, text=True, timeout=5); "
        "print(r.stderr); sys.exit(r.returncode)"
    )
    result = run_cli("run", "--gate", gate, "--agent", "test", "--",
                     sys.executable, "-c", child, cli, gate)
    assert result.returncode == 2, result.stderr
    assert "Nested checkout rejected" in result.stdout, result.stdout
    status = json.loads(run_cli("status", "--gate", gate, "--json").stdout)
    assert status["status"] == "AVAILABLE"
    print("PASS: test_nested_checkout_rejected")


def main() -> None:
    test_basic_acquire_release()
    test_idempotent_acquire()
    test_contention_and_timeout()
    test_dead_pid_reclaim()
    test_run_command_wrapper()
    test_nested_checkout_rejected()
    print("ALL GATE CHECKOUT TESTS PASSED!")


if __name__ == "__main__":
    main()
