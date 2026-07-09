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


if __name__ == "__main__":
    test_dead_pid_gc()
    test_release_idempotent_and_signal()
    test_local_delayed_signal()
    test_kill_switch()
    test_timeout_reject()
    test_band_ordering()
    print("ALL PASS")
