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
_LEASE_RESERVATION_DIRNAME = "scheduler-lease-reservations"

DENY_SCHEDULER_CONTEXT = "scheduler-context-denied"
DENY_EPOCH_AUTHORITY = "epoch-authority-unavailable"
DENY_RESERVATION_REPLAY = "scheduler-context-replay"
DENY_RESERVATION_LEDGER = "scheduler-reservation-ledger-unavailable"
DENY_RESERVATION_REVOKED = "revoked-before-execution"

_ACTIVE_RESERVATIONS: dict[str, tuple[Path, dict]] = {}


class SlotQueueTimeout(SlotWaitTimeout):
    """Deadline expired while queued for the banded local slot."""


class SlotQueueLeaseDenied(Exception):
    """Stable typed denial from the flag-gated C6 scheduler lease fence."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


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


def _lease_gate_enabled() -> bool:
    return os.environ.get("CAPABILITY_SCHEDULER_LEASE_GATE", "0") == "1"


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
    scheduler_context=None,
    signer_keys_json=None,
    now=None,
) -> AcquireResult:
    """Queue with banded priority, then claim the free llama.cpp slot.

    on_wait: optional callback(signal, waited_s, queue_depth) invoked each
    poll so callers can surface typed queue state in progress sidecars.
    """
    if _lease_gate_enabled():
        return _acquire_with_lease_gate(
            repo_root,
            run_id,
            llama_url,
            timeout_secs,
            band=band,
            task_class=task_class,
            expected_infer_s=expected_infer_s,
            on_wait=on_wait,
            scheduler_context=scheduler_context,
            signer_keys_json=signer_keys_json,
            now=now,
        )
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
    if _lease_gate_enabled():
        active = _ACTIVE_RESERVATIONS.pop(mine, None)
        if active is not None:
            _set_reservation_state(active[0], active[1], "released")


def _verify_scheduler_reservation(candidate, signer_keys_json, now=None) -> tuple[dict, int]:
    """Resolve the authority epoch first, then invoke the existing ingress verifier."""
    try:
        import revocation_epoch

        current_epoch = revocation_epoch.resolve_current_epoch()
    except Exception as exc:  # noqa: BLE001 — every authority failure is a typed deny
        reason = getattr(exc, "reason", DENY_EPOCH_AUTHORITY)
        raise SlotQueueLeaseDenied(DENY_EPOCH_AUTHORITY, str(reason)) from exc

    try:
        import dispatch

        verdict = dispatch.verify_ingress_scheduler_context(
            candidate,
            signer_keys_json=signer_keys_json,
            current_epoch=current_epoch,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 — verifier/import failure denies
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, exc.__class__.__name__) from exc
    if not isinstance(verdict, dict) or verdict.get("ok") is not True:
        reason = verdict.get("reason") if isinstance(verdict, dict) else "malformed-verdict"
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, str(reason))

    verified = verdict.get("context")
    if not isinstance(verified, dict):
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, "missing-verified-context")
    stamped_epoch = verified.get("revocation_epoch")
    if isinstance(stamped_epoch, bool) or not isinstance(stamped_epoch, int):
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, "malformed-revocation-epoch")
    if stamped_epoch != current_epoch:
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, "context-epoch-mismatch")
    return dict(verified), current_epoch


def _reservation_digest(context: dict) -> str:
    import hashlib

    payload = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reservation_dir(repo_root: Path) -> Path:
    path = repo_root / ".agents" / "delegation" / _LEASE_RESERVATION_DIRNAME
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _record_reservation(repo_root: Path, context: dict) -> tuple[Path, dict]:
    import hashlib

    context_digest = _reservation_digest(context)
    lease_id = context.get("lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        raise SlotQueueLeaseDenied(DENY_SCHEDULER_CONTEXT, "missing-lease-id")
    record = {
        "context_digest": context_digest,
        "lease_id_digest": hashlib.sha256(lease_id.encode("utf-8")).hexdigest(),
        "revocation_epoch": context["revocation_epoch"],
        "reservation_state": "queued",
        "receipt_id": context_digest[:32],
    }
    directory = _reservation_dir(repo_root)
    path = directory / f"{context_digest}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise SlotQueueLeaseDenied(DENY_RESERVATION_REPLAY) from exc
    except OSError as exc:
        raise SlotQueueLeaseDenied(DENY_RESERVATION_LEDGER, exc.__class__.__name__) from exc
    try:
        os.write(fd, (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        os.fsync(fd)
    except OSError as exc:
        raise SlotQueueLeaseDenied(DENY_RESERVATION_LEDGER, exc.__class__.__name__) from exc
    finally:
        os.close(fd)
    dir_fd = os.open(directory, os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return path, record


def _set_reservation_state(path: Path, record: dict, state: str) -> None:
    import tempfile

    updated = dict(record)
    updated["reservation_state"] = state
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (json.dumps(updated, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    dir_fd = os.open(path.parent, os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    record.clear()
    record.update(updated)


def _drop_reservation(repo_root: Path, job_id: str, path: Path, record: dict, state: str) -> None:
    with _LockedState(repo_root) as scheduler_state:
        queue = [queued for queued in scheduler_state.queue if queued.id != job_id]
        running = scheduler_state.running
        if running is not None and running.id == job_id:
            running = None
        if len(queue) != len(scheduler_state.queue) or running is not scheduler_state.running:
            _save_under_current_lock(
                repo_root,
                scheduler_state.model_copy(update={"queue": queue, "running": running}),
            )
    _set_reservation_state(path, record, state)
    _ACTIVE_RESERVATIONS.pop(job_id, None)


def _acquire_with_lease_gate(
    repo_root: Path,
    run_id: str,
    llama_url: str,
    timeout_secs: int,
    *,
    band: Band | None,
    task_class: str | None,
    expected_infer_s: float,
    on_wait,
    scheduler_context,
    signer_keys_json,
    now,
) -> AcquireResult:
    verified_context, _ = _verify_scheduler_reservation(scheduler_context, signer_keys_json, now=now)
    _band = band or band_from_env()
    if task_class is not None:
        route(task_class)
    job = Job(id=f"{os.getpid()}:{run_id}", band=_band, enqueued_at=time.time(), task_class=task_class)
    reservation_path, reservation = _record_reservation(repo_root, verified_context)
    _ACTIVE_RESERVATIONS[job.id] = (reservation_path, reservation)

    with _LockedState(repo_root) as state:
        _save_under_current_lock(repo_root, state.model_copy(update={"queue": [*state.queue, job]}))

    deadline = time.monotonic() + timeout_secs
    started = time.monotonic()
    while True:
        try:
            _verify_scheduler_reservation(verified_context, signer_keys_json, now=now)
        except SlotQueueLeaseDenied as exc:
            drop_state = (
                DENY_RESERVATION_REVOKED
                if "epoch" in exc.detail
                else "denied-before-execution"
            )
            _drop_reservation(repo_root, job.id, reservation_path, reservation, drop_state)
            raise

        remaining = deadline - time.monotonic()
        waited = time.monotonic() - started
        signal = assess(waited, expected_infer_s, remaining)
        if signal is Signal.REJECT or remaining <= 0:
            _drop_reservation(repo_root, job.id, reservation_path, reservation, "timed-out")
            raise SlotQueueTimeout(
                f"banded slot queue deadline after {int(waited)}s (band={_band}, signal={signal})"
            )

        claimed = False
        with _LockedState(repo_root) as state:
            depth = len(state.queue)
            current_time = time.time()
            selected, popped = next_job(state, current_time)
            head_of_line = selected is not None and selected.id == job.id and state.running is None
            if head_of_line and _slot_free(llama_url):
                _save_under_current_lock(repo_root, popped)
                _set_reservation_state(reservation_path, reservation, "held")
                claimed = True
            else:
                _save_under_current_lock(repo_root, age(state, current_time))

        if claimed:
            try:
                _verify_scheduler_reservation(verified_context, signer_keys_json, now=now)
            except SlotQueueLeaseDenied:
                _drop_reservation(
                    repo_root,
                    job.id,
                    reservation_path,
                    reservation,
                    DENY_RESERVATION_REVOKED,
                )
                raise
            return AcquireResult(signal=signal, queue_wait_s=waited, band=_band, queue_depth=depth)

        if on_wait is not None:
            try:
                on_wait(signal, waited, depth)
            except Exception:
                pass
        time.sleep(_POLL_INTERVAL_S)


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
