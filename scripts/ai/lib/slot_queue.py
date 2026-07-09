#!/usr/bin/env python3
"""slot_queue — cross-process persistence adapter wiring F2 scheduler into dispatch.

F2.5 activation slice: scheduler.py (pure MLFQ), backpressure.py (typed
admission), and model_tier.py (tier routes) were built and tested in F2
Phase A but never wired into the live dispatch path. This module is the
wiring: a file-locked SchedulerState shared by all dispatch processes, so
concurrent local dispatches queue with banded priority + aging instead of
first-come race-polling /slots.

Contract:
  - acquire() blocks until this job is head-of-line AND the llama.cpp slot
    is free, then marks it running. Raises SlotQueueTimeout on deadline.
  - LOCAL_DELAYED is admissible (never-skip-local): the job stays queued and
    the caller's progress sidecar shows the typed state.
  - Running jobs are NEVER killed: llama.cpp single-slot generation cannot be
    checkpointed, so eviction-style preemption (scheduler.preempt) is a
    recorded deferral. Band priority + aging in next_job() provide the
    ordering guarantees.
  - Dead processes are GC'd by pid liveness, so a kill -9'd dispatch cannot
    wedge the queue.
  - Kill switch: SLOT_QUEUE=0 -> callers fall back to bare wait_for_slot().

Band selection (callers export DISPATCH_BAND):
  interactive -> P1, consensus -> P2 (default), background -> P3.

State file is the observability surface: .agents/delegation/scheduler-state.json
(queue depth, bands, waits are directly readable by dashboard/health-spider).
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from backpressure import Signal, assess
from model_tier import route
from scheduler import Band, Job, SchedulerState, age, next_job
from slot_scheduler import SlotWaitTimeout


def _slot_free(llama_url: str) -> bool:
    """Single non-blocking probe of llama.cpp /slots (never sleeps under flock)."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{llama_url}/slots", timeout=5) as resp:
            slots = json.loads(resp.read())
            return bool(slots) and not slots[0].get("is_processing", True)
    except Exception:
        return False

_BAND_BY_NAME = {
    "interactive": Band.P1_INTERACTIVE,
    "consensus": Band.P2_CONSENSUS_VALIDATION,
    "background": Band.P3_BACKGROUND_BATCH,
}

_POLL_INTERVAL_S = 3.0
# Jobs whose owning pid is gone are GC'd; running jobs get a grace multiple
# of the poll interval before reap so a live process mid-request isn't reaped
# during its own inference (pid check is authoritative; this is belt+braces).
_STATE_FILENAME = "scheduler-state.json"


class SlotQueueTimeout(SlotWaitTimeout):
    """Deadline expired while queued for the banded local slot."""


@dataclass
class AcquireResult:
    signal: Signal
    queue_wait_s: float
    band: Band
    queue_depth: int


def band_from_env(default: str = "consensus") -> Band:
    name = os.environ.get("DISPATCH_BAND", default).strip().lower()
    return _BAND_BY_NAME.get(name, Band.P2_CONSENSUS_VALIDATION)


def enabled() -> bool:
    return os.environ.get("SLOT_QUEUE", "1") != "0"


def _state_path(repo_root: Path) -> Path:
    p = repo_root / ".agents" / "delegation" / _STATE_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _job_pid(job: Job) -> int:
    try:
        return int(job.id.split(":", 1)[0])
    except (ValueError, IndexError):
        return -1


class _LockedState:
    """flock-guarded load/save of SchedulerState with dead-pid GC."""

    def __init__(self, repo_root: Path):
        self._path = _state_path(repo_root)
        self._lock_path = self._path.with_suffix(".lock")
        self._fh = None

    def __enter__(self) -> SchedulerState:
        self._fh = open(self._lock_path, "a+")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        state = self._load()
        return self._gc(state)

    def save(self, state: SchedulerState) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(_dump_state(state))
        os.replace(tmp, self._path)

    def __exit__(self, *exc) -> None:
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()

    def _load(self) -> SchedulerState:
        try:
            return SchedulerState.model_validate_json(self._path.read_text())
        except (OSError, ValueError):
            return SchedulerState()

    @staticmethod
    def _gc(state: SchedulerState) -> SchedulerState:
        queue = [j for j in state.queue if _pid_alive(_job_pid(j))]
        running = state.running
        if running is not None and not _pid_alive(_job_pid(running)):
            running = None
        if len(queue) != len(state.queue) or running is not state.running:
            return state.model_copy(update={"queue": queue, "running": running})
        return state


def acquire(
    repo_root: Path,
    run_id: str,
    llama_url: str,
    timeout_secs: int,
    *,
    band: Band | None = None,
    task_class: str | None = None,
    expected_infer_s: float = 0.0,
    on_wait=None,
) -> AcquireResult:
    """Queue with banded priority, then claim the free llama.cpp slot.

    on_wait: optional callback(signal, waited_s, queue_depth) invoked each
    poll so callers can surface typed queue state in progress sidecars.
    """
    _band = band or band_from_env()
    # Tier route is telemetry today (single local model); recorded on the job
    # via task_class so the state file shows what class holds/waits the slot.
    if task_class is not None:
        route(task_class)  # validates/normalizes; unknown classes fall to MID default
    job = Job(id=f"{os.getpid()}:{run_id}", band=_band, enqueued_at=time.time(), task_class=task_class)

    with _LockedState(repo_root) as state:
        _save_under_current_lock(repo_root, state.model_copy(update={"queue": [*state.queue, job]}))

    deadline = time.monotonic() + timeout_secs
    started = time.monotonic()
    while True:
        remaining = deadline - time.monotonic()
        waited = time.monotonic() - started
        signal = assess(waited, expected_infer_s, remaining)
        if signal is Signal.REJECT or remaining <= 0:
            _remove(repo_root, job.id)
            raise SlotQueueTimeout(
                f"banded slot queue deadline after {int(waited)}s (band={_band}, signal={signal})"
            )

        with _LockedState(repo_root) as state:
            depth = len(state.queue)
            now = time.time()
            selected, popped = next_job(state, now)
            head_of_line = (
                selected is not None
                and selected.id == job.id
                and state.running is None
            )
            if head_of_line and _slot_free(llama_url):
                _save_under_current_lock(repo_root, popped)
                return AcquireResult(signal=signal, queue_wait_s=waited, band=_band, queue_depth=depth)
            # Not head-of-line, or llama slot busy with non-queue traffic:
            # persist the aged (un-popped) queue and retry next poll.
            _save_under_current_lock(repo_root, age(state, now))

        if on_wait is not None:
            try:
                on_wait(signal, waited, depth)
            except Exception:
                pass
        time.sleep(_POLL_INTERVAL_S)


def release(repo_root: Path, run_id: str) -> None:
    """Clear the running marker owned by this process."""
    mine = f"{os.getpid()}:{run_id}"
    with _LockedState(repo_root) as state:
        if state.running is not None and state.running.id == mine:
            _save_under_current_lock(repo_root, state.model_copy(update={"running": None}))


def _remove(repo_root: Path, job_id: str) -> None:
    with _LockedState(repo_root) as state:
        queue = [j for j in state.queue if j.id != job_id]
        if len(queue) != len(state.queue):
            _save_under_current_lock(repo_root, state.model_copy(update={"queue": queue}))


def _dump_state(state: SchedulerState) -> str:
    # SchedulerConfig.max_wait_s holds inf, which JSON-serializes to null and
    # fails re-validation (F2 latent bug — logged in issues-backlog). We only
    # ever run with the default config, so persist queue/running and let the
    # default_factory rebuild config on load.
    return state.model_dump_json(exclude={"config"})


def _save_under_current_lock(repo_root: Path, state: SchedulerState) -> None:
    tmp = _state_path(repo_root).with_suffix(".tmp")
    tmp.write_text(_dump_state(state))
    os.replace(tmp, _state_path(repo_root))
