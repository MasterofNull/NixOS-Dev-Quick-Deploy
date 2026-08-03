#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C, C3b R7 durable reservation store.

Exercises `scripts/ai/lib/durable_reservation.DurableReservationSet` per
`.agents/plans/aqos-foundation-c/R7-PROVISIONING-DESIGN-20260803.md` §4
(FROZEN rev2): the same `try_reserve`/`commit`/`fail`/`state_of` contract
as `execution_grant.ReplayReservationSet`, but persistent (crash recovery
across a fresh instance on the same backing file) and thread-safe
(concurrent `try_reserve` on one `grant_id` has exactly one winner).

Also asserts the R7 §3 env-format parity fix directly against
`ai-stack/switchboard/execution_cell_runner.build_config_from_env`: the
`AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS` env MUST be JSON
(`{"primary": "<mirror>"}`) — a `key=value` string throws `ValueError` in
`json.loads`, silently collapsing to `mirrors={}` and denying every grant
`unknown-trusted-repo`.

Fully offline/hermetic: everything runs against temp-dir-backed JSON
files, no network, no systemd, no real runner process.

Run directly: `python3 scripts/testing/test-durable-reservation.py`
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "ai" / "lib")
_SWITCHBOARD_DIR = str(Path(__file__).resolve().parents[1].parent / "ai-stack" / "switchboard")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
if _SWITCHBOARD_DIR not in sys.path:
    sys.path.insert(0, _SWITCHBOARD_DIR)

from durable_reservation import DurableReservationSet  # noqa: E402
from execution_grant import (  # noqa: E402
    RESERVATION_COMMITTED,
    RESERVATION_FAILED,
    RESERVATION_RESERVED,
)


def _store_path(tmp_path: str, name: str = "grant.json") -> str:
    return os.path.join(tmp_path, "reservations", name)


def test_reserve_then_commit():
    with tempfile.TemporaryDirectory() as tmp:
        path = _store_path(tmp)
        store = DurableReservationSet(path)
        assert store.try_reserve("g1") is True
        assert store.state_of("g1") == RESERVATION_RESERVED
        assert store.commit("g1") is True
        assert store.state_of("g1") == RESERVATION_COMMITTED
        assert os.path.isfile(path)


def test_reserve_then_fail():
    with tempfile.TemporaryDirectory() as tmp:
        store = DurableReservationSet(_store_path(tmp))
        assert store.try_reserve("g2") is True
        assert store.fail("g2") is True
        assert store.state_of("g2") == RESERVATION_FAILED


def test_double_reserve_denied():
    with tempfile.TemporaryDirectory() as tmp:
        store = DurableReservationSet(_store_path(tmp))
        assert store.try_reserve("g3") is True
        assert store.try_reserve("g3") is False
        assert "g3" in store
        # A second reserve attempt must not clobber the first reservation's
        # state (still reserved, not silently re-armed).
        assert store.state_of("g3") == RESERVATION_RESERVED


def test_commit_without_reserve_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        store = DurableReservationSet(_store_path(tmp))
        assert store.commit("never-reserved") is False
        assert store.state_of("never-reserved") is None
        # Same fail-closed guard for `fail()`.
        assert store.fail("never-reserved") is False
        # And a terminal state cannot be re-committed/re-failed.
        store.try_reserve("g4")
        store.commit("g4")
        assert store.commit("g4") is False
        assert store.fail("g4") is False
        assert store.state_of("g4") == RESERVATION_COMMITTED


def test_persistence_across_fresh_instance_same_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = _store_path(tmp)
        first = DurableReservationSet(path)
        assert first.try_reserve("g5") is True
        assert first.commit("g5") is True

        # A crash-recovery scenario: a brand-new instance on the SAME file
        # must see the durably-persisted state, not start empty.
        second = DurableReservationSet(path)
        assert second.state_of("g5") == RESERVATION_COMMITTED
        assert "g5" in second
        # A grant that crashed mid-flight (reserved, never committed/failed)
        # must also survive as non-replayable "reserved" — never silently
        # promoted or dropped.
        first.try_reserve("g6")
        third = DurableReservationSet(path)
        assert third.state_of("g6") == RESERVATION_RESERVED
        assert third.try_reserve("g6") is False


def test_concurrent_try_reserve_exactly_one_winner():
    with tempfile.TemporaryDirectory() as tmp:
        store = DurableReservationSet(_store_path(tmp))
        results: list[bool] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(2)

        def race() -> None:
            barrier.wait()
            outcome = store.try_reserve("contested")
            with results_lock:
                results.append(outcome)

        threads = [threading.Thread(target=race) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 2
        assert sorted(results) == [False, True]
        assert store.state_of("contested") == RESERVATION_RESERVED


def test_trusted_repo_mirrors_env_json_parity():
    """R7 §3 parity test: run the actual env string through
    `build_config_from_env` and assert the mirror survives — this catches
    both a future id/key rename AND a regression back to a `key=value`
    (non-JSON) env format, which `json.loads` would reject and silently
    collapse to `mirrors={}` (`unknown-trusted-repo` for every grant)."""
    import execution_cell_runner as runner  # noqa: E402  (local import: keeps the module-load side effects out of collection time)

    config = runner.build_config_from_env(
        {"AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS": '{"primary":"/tmp/x.git"}'}
    )
    assert "primary" in config.trusted_repo_mirrors
    assert config.trusted_repo_mirrors["primary"] == "/tmp/x.git"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
