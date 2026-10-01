#!/usr/bin/env python3
"""delegate-to-local launch verification: fail on a dead child, never on slow registration.

History: wave 1 (2b654d8b) added registry polling to stop false launch acks, but its
loop counted 0.1s ticks as seconds (0.3s window) and failed live tasks whose
registration lags launch by ~35s (ctx-freshness + worktree setup), so aq-collab-round
recorded a running local lane as an error. These cases run the real function.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "delegate-to-local"


def _verify(pid_expr: str, registry_text: str | None) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as d:
        reg = Path(d) / "registry.jsonl"
        if registry_text is not None:
            reg.write_text(registry_text)
        script = (f"source {SCRIPT!s} >/dev/null 2>&1; {pid_expr}; "
                  f"verify_launch_success \"$P\" task-x {reg!s}; rc=$?; kill $P 2>/dev/null || true; exit $rc")
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)


def test_dead_unregistered_child_fails():
    r = _verify("true & P=$!; wait $P", None)
    assert r.returncode == 1 and "exited before registering" in r.stderr, r


def test_alive_unregistered_child_succeeds_with_warning():
    r = _verify("sleep 20 & P=$!", "")
    assert r.returncode == 0 and "not yet registered" in r.stderr, r


def test_alive_registered_child_succeeds_quietly():
    r = _verify("sleep 20 & P=$!", '{"id": "task-x"}\n')
    assert r.returncode == 0 and "WARN" not in r.stderr, r


def test_fast_finished_registered_child_succeeds():
    r = _verify("true & P=$!; wait $P", '{"id": "task-x"}\n')
    assert r.returncode == 0, r


def test_caller_aborts_on_failure():
    content = SCRIPT.read_text()
    assert 'if ! verify_launch_success "$BG_PID" "$ID"; then' in content


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if fails else 0)
