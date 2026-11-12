#!/usr/bin/env python3
"""F2.5 wiring tests: banded cross-process slot queue (scripts/ai/lib/slot_queue.py).

Covers: band ordering (P1 beats earlier P3), typed backpressure surfacing,
dead-pid GC, release idempotence, kill switch, and timeout rejection.
Run: python3 scripts/testing/test-slot-queue-wiring.py
"""

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import slot_queue  # noqa: E402
from scheduler import Band, Job, SchedulerState  # noqa: E402
from backpressure import Signal  # noqa: E402


def _fresh_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="slotq-test-"))


def test_band_ordering():
    """P1 enqueued after P3 must acquire first when both wait."""
    root = _fresh_root()
    slot_queue._slot_free = lambda url: True  # llama always free
    order = []

    def worker(run_id, band, delay, hold):
        time.sleep(delay)
        slot_queue.acquire(root, run_id, "http://x", 60, band=band)
        order.append(run_id)
        time.sleep(hold)
        slot_queue.release(root, run_id)

    # P3 takes the slot and holds it until BOTH later jobs are queued, so the
    # shared next_job selection (not poll order) decides who goes next.
    t1 = threading.Thread(target=worker, args=("p3-first", Band.P3_BACKGROUND_BATCH, 0, 2.5))
    t2 = threading.Thread(target=worker, args=("p3-second", Band.P3_BACKGROUND_BATCH, 0.5, 0.2))
    t3 = threading.Thread(target=worker, args=("p1-late", Band.P1_INTERACTIVE, 1.0, 0.2))
    for t in (t1, t2, t3):
        t.start()
    for t in (t1, t2, t3):
        t.join(timeout=90)
    assert order[0] == "p3-first", order
    assert order.index("p1-late") < order.index("p3-second"), (
        f"P1 must preempt queued P3 ordering: {order}")
    print(f"PASS band ordering: {order}")


def test_dead_pid_gc():
    """Jobs owned by dead pids are GC'd so the queue cannot wedge."""
    root = _fresh_root()
    dead = Job(id="999999999:ghost", band=Band.P1_INTERACTIVE,
               enqueued_at=time.time(), task_class=None)
    state = SchedulerState(queue=[dead], running=dead.model_copy(update={"id": "999999998:ghost2"}))
    slot_queue._save_under_current_lock(root, state)
    with slot_queue._LockedState(root) as gc_state:
        assert gc_state.queue == [], "dead queued job not GC'd"
        assert gc_state.running is None, "dead running job not GC'd"
    print("PASS dead-pid GC")


def test_release_idempotent_and_signal():
    root = _fresh_root()
    slot_queue._slot_free = lambda url: True
    res = slot_queue.acquire(root, "solo", "http://x", 30,
                             band=Band.P2_CONSENSUS_VALIDATION, expected_infer_s=5.0)
    assert res.signal in (Signal.OK, Signal.LOCAL_DELAYED)
    slot_queue.release(root, "solo")
    slot_queue.release(root, "solo")  # second release is a no-op
    with slot_queue._LockedState(root) as state:
        assert state.running is None and state.queue == []
    print(f"PASS release + signal ({res.signal})")


def test_local_delayed_signal():
    """expected_infer_s beyond deadline yields admissible LOCAL_DELAYED, not reject."""
    root = _fresh_root()
    slot_queue._slot_free = lambda url: True
    res = slot_queue.acquire(root, "slow", "http://x", 30,
                             band=Band.P3_BACKGROUND_BATCH, expected_infer_s=10_000.0)
    assert res.signal is Signal.LOCAL_DELAYED, res.signal
    slot_queue.release(root, "slow")
    print("PASS LOCAL_DELAYED admissible (never-skip-local)")


def test_timeout_reject():
    root = _fresh_root()
    slot_queue._slot_free = lambda url: False  # slot never frees
    t0 = time.monotonic()
    try:
        slot_queue.acquire(root, "doomed", "http://x", 4, band=Band.P3_BACKGROUND_BATCH)
    except slot_queue.SlotQueueTimeout as exc:
        with slot_queue._LockedState(root) as state:
            assert state.queue == [], "timed-out job must be dequeued"
        print(f"PASS timeout reject after {time.monotonic()-t0:.0f}s: {exc}")
    else:
        raise AssertionError("expected SlotQueueTimeout")


def test_kill_switch():
    os.environ["SLOT_QUEUE"] = "0"
    assert not slot_queue.enabled()
    os.environ.pop("SLOT_QUEUE")
    assert slot_queue.enabled()
    print("PASS kill switch")


_HOLDER = """
import sys, time
sys.path.insert(0, sys.argv[1] + "/scripts/ai/lib")
import slot_queue
from scheduler import Band
slot_queue._slot_free = lambda url: True
root, rid, hold, mark = sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
from pathlib import Path
slot_queue.acquire(Path(root), rid, "http://x", 60, band=Band.P3_BACKGROUND_BATCH)
open(mark, "a").write(f"{rid} acquired {time.time()}\\n")
time.sleep(hold)
open(mark, "a").write(f"{rid} released {time.time()}\\n")
slot_queue.release(Path(root), rid)
"""


def test_unit_and_shell_processes_exclude_each_other():
    """One shared lock/state: a unit-style process (AQ_DELEGATION_DIR elsewhere, read-only-ish env) and a shell-style
    process contend for the one slot; the second acquires only after the first releases."""
    import subprocess
    root = _fresh_root()
    mark = root / "marks.txt"
    other = _fresh_root()
    unit_env = {**os.environ, "AQ_DELEGATION_DIR": str(other / "prsi" / "delegation")}
    shell_env = {k: v for k, v in os.environ.items() if k != "AQ_DELEGATION_DIR"}
    first = subprocess.Popen([sys.executable, "-c", _HOLDER, str(REPO), str(root), "unit", "3", str(mark)], env=unit_env)
    deadline = time.time() + 20
    while time.time() < deadline and not (mark.exists() and "unit acquired" in mark.read_text()):
        time.sleep(0.1)
    second = subprocess.Popen([sys.executable, "-c", _HOLDER, str(REPO), str(root), "shell", "0.1", str(mark)], env=shell_env)
    assert first.wait(30) == 0 and second.wait(30) == 0
    ev = {(l.split()[0], l.split()[1]): float(l.split()[2]) for l in mark.read_text().splitlines()}
    assert ev[("shell", "acquired")] >= ev[("unit", "released")], ev
    assert (root / ".agents/delegation/scheduler/scheduler-state.lock").exists()
    assert not list(other.rglob("scheduler-state*")), "AQ_DELEGATION_DIR must not split the state"
    print("PASS unit-style and shell-style processes exclude each other on one lock")


def test_legacy_state_migrates_once():
    import json
    root = _fresh_root()
    old = root / ".agents/delegation/scheduler-state.json"
    old.parent.mkdir(parents=True)
    st = SchedulerState(queue=[Job(id=f"{os.getpid()}:legacy", band=Band.P3_BACKGROUND_BATCH, task_class="x", enqueued_at=time.time())])
    old.write_text(slot_queue._dump_state(st))
    new = root / ".agents/delegation/scheduler/scheduler-state.json"
    import scheduler_paths
    assert scheduler_paths.read_path(root) == old, "readers fall back to the old file until migrated"
    with slot_queue._LockedState(root) as state:
        assert [j.id for j in state.queue] == [f"{os.getpid()}:legacy"], state
    assert new.exists() and scheduler_paths.read_path(root) == new
    new.write_text(slot_queue._dump_state(SchedulerState()))
    with slot_queue._LockedState(root):
        pass
    assert json.loads(new.read_text())["queue"] == [], "migration must not overwrite an existing new file"
    print("PASS legacy scheduler-state.json migrates once")


def test_all_readers_and_writers_agree_on_the_path():
    import scheduler_paths
    root = _fresh_root()
    want = root / ".agents/delegation/scheduler/scheduler-state.json"
    assert slot_queue._state_path(root) == want == scheduler_paths.state_file(root)
    # a linked worktree resolves to the main checkout's directory
    wt = _fresh_root()
    (wt / ".git").write_text(f"gitdir: {root}/.git/worktrees/w\n")
    assert scheduler_paths.state_file(wt) == want
    # the dashboard route and the training loop use the same module, not their own path rule
    dash = (REPO / "dashboard/backend/api/routes/aistack.py").read_text()
    loop = (REPO / "scripts/ai/aq-local-training-loop").read_text()
    assert "scheduler_paths.read_path(" in dash and "scheduler_paths.state_file(" in loop
    assert "AQ_DELEGATION_DIR" not in (REPO / "scripts/ai/lib/slot_queue.py").read_text()
    print("PASS readers and writers resolve one path")


def test_nix_unit_gets_only_the_scheduler_dir():
    nix = (REPO / "nix/modules/roles/ai-stack.nix").read_text()
    i = nix.index("systemd.services.ai-prsi-rsi-dispatch = {")
    unit = nix[i:nix.index("systemd.paths.ai-prsi-rsi-dispatch", i)]
    assert '"${cfg.mcpServers.repoPath}/.agents/delegation/scheduler"' in unit
    assert '"${cfg.mcpServers.repoPath}/.agents/delegation"' not in unit
    assert 'd ${cfg.mcpServers.repoPath}/.agents/delegation/scheduler ' in nix, "tmpfiles rule must create it before the namespace is built"
    print("PASS unit ReadWritePaths is exactly the scheduler dir, created by tmpfiles")


if __name__ == "__main__":
    test_unit_and_shell_processes_exclude_each_other()
    test_legacy_state_migrates_once()
    test_all_readers_and_writers_agree_on_the_path()
    test_nix_unit_gets_only_the_scheduler_dir()
    test_dead_pid_gc()
    test_release_idempotent_and_signal()
    test_local_delayed_signal()
    test_kill_switch()
    test_timeout_reject()
    test_band_ordering()
    print("ALL PASS")
