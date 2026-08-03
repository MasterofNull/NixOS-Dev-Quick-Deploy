"""Durable reservation store — Foundation C, C3b R7 (§4 of
`.agents/plans/aqos-foundation-c/R7-PROVISIONING-DESIGN-20260803.md`,
FROZEN rev2).

Replaces the `#8` shadow stopgap (`execution_grant.ReplayReservationSet`,
in-memory, not durable, not safe across processes) with a persistent,
thread-safe store behind the SAME duck-typed contract (`__contains__`,
`add`, `try_reserve`, `commit`, `fail`, `state_of`) so `reserve_replay()`
and every existing caller are unchanged.

Durability is built on the LANDED `_fsync_write_json` primitive
(`execution_cell_clone.py:188`: temp-same-dir write + file fsync + atomic
`os.replace` + directory fsync) — every mutating transition is a single
all-or-nothing atomic write; a crash mid-write leaves the last durably
committed state on disk (the temp file is never observed), never a torn
read. A grant crashed after `reserved` but before `committed`/`failed`
stays `reserved` on restart (non-replayable, fail-closed) — design §4
"Crash recovery" is intentional, not a bug.

Thread safety: the runner serves each connection on its own thread
(`execution_cell_runner.py:1063`) and calls `try_reserve` from
`verify_grant` BEFORE the concurrency semaphore — `flock` alone gives
cross-process but NOT intra-process safety (threads sharing one process
share the open-file description). Every mutating op here holds a single
`threading.Lock` around the whole read-modify-persist, so two threads
racing the same `grant_id` can never both win.

This module opens NO socket, invokes NO bwrap/git, and does NO network
I/O — it is a private per-file JSON ledger under a caller-supplied path
(the runner's own `state_root`, design §4)."""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from typing import Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from execution_grant import (  # noqa: E402
    RESERVATION_COMMITTED,
    RESERVATION_FAILED,
    RESERVATION_RESERVED,
)


def _fsync_write_json(path: str, obj: dict) -> None:
    """Durable JSON write: temp-same-dir write, fsync the file, atomic
    `os.replace`, then fsync the containing directory. Mirrors
    `execution_cell_clone._fsync_write_json` exactly (R2's landed
    primitive) so both durable stores share the identical on-disk
    durability guarantee. Raises OSError on failure — callers wrap this in
    their own fail-closed handling; it is NOT itself total."""
    data = json.dumps(obj, sort_keys=True, indent=2, default=str).encode("utf-8") + b"\n"
    tmp_path = f"{path}.tmp-{uuid.uuid4().hex}"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    dir_fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


class DurableReservationSet:
    """Persistent, thread-safe reservation store behind the SAME contract
    as `execution_grant.ReplayReservationSet` (`__contains__`, `add`,
    `try_reserve`, `commit`, `fail`, `state_of`), so it is a drop-in for
    `reserve_replay()` and any caller written against the in-memory
    reference implementation.

    Backing store is a single JSON file at `path`: `{grant_id: status}`.
    Loaded once at construction (crash recovery — an existing file's state
    is honored, never rebuilt from scratch); every subsequent mutating
    call re-persists the FULL state atomically via `_fsync_write_json`
    under `self._lock`, so concurrent threads in this process never
    interleave a read-modify-write."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._state: dict[str, str] = {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._state = {str(k): str(v) for k, v in loaded.items()}
        except FileNotFoundError:
            self._state = {}
        except (OSError, ValueError):
            # Corrupt/unreadable ledger: start EMPTY (availability-favoring) rather
            # than raise — never crash the runner at construction time; the next
            # successful persist heals the file. NOTE this is fail-*OPEN* for replay
            # (a grant that was actually reserved becomes re-reservable → a spurious
            # admission), NOT fail-closed. Acceptable ONLY because R7 is the
            # deny-closed, non-authoritative SHADOW (a replayed grant re-runs a cell
            # in the sandbox with no real effect). Before the shadow becomes
            # authoritative (R8), a corrupt ledger MUST fail-CLOSED (treat the store
            # as unreliable → deny, per execution_grant.reserve_replay's contract).
            self._state = {}

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        _fsync_write_json(self._path, self._state)

    def __contains__(self, grant_id: str) -> bool:
        with self._lock:
            return grant_id in self._state

    def add(self, grant_id: str) -> None:
        """Duck-typed MutableSet.add(), used by `reserve_replay`'s
        set-fallback branch. Equivalent to a bare try_reserve with no
        distinct later commit/fail transition."""
        with self._lock:
            if grant_id in self._state:
                return
            self._state[grant_id] = RESERVATION_RESERVED
            self._persist()

    def try_reserve(self, grant_id: str) -> bool:
        """Atomic (within this process, via `self._lock`; durable, via
        `_fsync_write_json`) try-reserve: True iff this call is the first
        to reserve `grant_id`."""
        with self._lock:
            if grant_id in self._state:
                return False
            self._state[grant_id] = RESERVATION_RESERVED
            self._persist()
            return True

    def commit(self, grant_id: str) -> bool:
        """reserved -> committed. False (no-op) if `grant_id` was never
        reserved, or is already in a terminal state — fail-closed: a
        caller cannot commit what it never reserved, nor double-transition
        a terminal reservation."""
        with self._lock:
            if self._state.get(grant_id) != RESERVATION_RESERVED:
                return False
            self._state[grant_id] = RESERVATION_COMMITTED
            self._persist()
            return True

    def fail(self, grant_id: str) -> bool:
        """reserved -> failed. Same guard as `commit`."""
        with self._lock:
            if self._state.get(grant_id) != RESERVATION_RESERVED:
                return False
            self._state[grant_id] = RESERVATION_FAILED
            self._persist()
            return True

    def state_of(self, grant_id: str) -> Optional[str]:
        with self._lock:
            return self._state.get(grant_id)
