#!/usr/bin/env python3
"""Tests for the pure local MLFQ scheduler core."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai" / "lib"))

from scheduler import (  # noqa: E402
    Band,
    Job,
    SchedulerConfig,
    SchedulerState,
    age,
    enqueue,
    next_job,
    no_starvation_invariant,
    preempt,
)


def job(job_id: str, band: Band, enqueued_at: float = 0.0) -> Job:
    return Job(id=job_id, band=band, enqueued_at=enqueued_at, task_class=None)


def drain_ids(state: SchedulerState, now: float) -> list[str]:
    seen: list[str] = []
    while True:
        selected, state = next_job(state, now)
        if selected is None:
            return seen
        seen.append(selected.id)


def test_next_job_orders_by_band_then_fifo_then_id() -> None:
    state = SchedulerState()
    state = enqueue(state, job("p3", Band.P3_BACKGROUND_BATCH, 1.0))
    state = enqueue(state, job("p1-b", Band.P1_INTERACTIVE, 2.0))
    state = enqueue(state, job("p2", Band.P2_CONSENSUS_VALIDATION, 0.5))
    state = enqueue(state, job("p1-a", Band.P1_INTERACTIVE, 2.0))

    assert drain_ids(state, now=2.0) == ["p1-a", "p1-b", "p2", "p3"]


def test_aging_promotes_p3_and_p2_after_configured_waits() -> None:
    config = SchedulerConfig(
        max_wait_s={
            Band.P1_INTERACTIVE: 999.0,
            Band.P2_CONSENSUS_VALIDATION: 20.0,
            Band.P3_BACKGROUND_BATCH: 10.0,
        },
        starvation_ceiling_s=90.0,
    )
    state = SchedulerState(
        config=config,
        queue=[
            job("p3", Band.P3_BACKGROUND_BATCH, 0.0),
            job("p2", Band.P2_CONSENSUS_VALIDATION, 0.0),
        ],
    )

    aged = age(state, now=21.0)

    by_id = {queued.id: queued.band for queued in aged.queue}
    assert by_id["p3"] == Band.P2_CONSENSUS_VALIDATION
    assert by_id["p2"] == Band.P1_INTERACTIVE


def test_starvation_bound_under_stream_of_p1_jobs() -> None:
    config = SchedulerConfig(starvation_ceiling_s=40.0)
    state = enqueue(SchedulerState(config=config), job("waiting-p3", Band.P3_BACKGROUND_BATCH, 0.0))

    for tick in range(0, 41, 5):
        state = enqueue(age(state, now=float(tick)), job(f"p1-{tick:02d}", Band.P1_INTERACTIVE, float(tick)))
        assert no_starvation_invariant(state, now=float(tick), ceiling=config.starvation_ceiling_s)

    aged = age(state, now=41.0)
    waiting = next(queued for queued in aged.queue if queued.id == "waiting-p3")
    assert waiting.band == Band.P1_INTERACTIVE
    assert no_starvation_invariant(aged, now=41.0, ceiling=config.starvation_ceiling_s)


def test_p1_preempts_running_p3_and_stashes_context() -> None:
    running = job("running-p3", Band.P3_BACKGROUND_BATCH, 0.0)
    state = SchedulerState(running=running)
    incoming = job("urgent", Band.P1_INTERACTIVE, 5.0)

    evicted, updated = preempt(state, incoming, now=5.0)
    selected, updated = next_job(updated, now=5.0)

    assert evicted is not None
    assert evicted.id == "running-p3"
    assert evicted.preempted_context == "preempted@5"
    assert selected is not None
    assert selected.id == "urgent"
    assert updated.running == selected


def test_p1_is_never_evicted_by_lower_bands() -> None:
    running = job("running-p1", Band.P1_INTERACTIVE, 0.0)
    state = SchedulerState(running=running)

    evicted_p2, after_p2 = preempt(state, job("p2", Band.P2_CONSENSUS_VALIDATION, 1.0), now=1.0)
    evicted_p3, after_p3 = preempt(after_p2, job("p3", Band.P3_BACKGROUND_BATCH, 2.0), now=2.0)

    assert evicted_p2 is None
    assert evicted_p3 is None
    assert after_p3.running == running
    assert [queued.id for queued in after_p3.queue] == ["p2", "p3"]


def test_p1_preempts_next_queued_p3_when_no_job_is_running() -> None:
    state = enqueue(SchedulerState(), job("queued-p3", Band.P3_BACKGROUND_BATCH, 0.0))

    evicted, updated = preempt(state, job("urgent", Band.P1_INTERACTIVE, 1.0), now=1.0)
    selected, _ = next_job(updated, now=1.0)

    assert evicted is not None
    assert evicted.id == "queued-p3"
    assert evicted.preempted_context == "preempted@1"
    assert selected is not None
    assert selected.id == "urgent"


def test_same_inputs_produce_same_schedule() -> None:
    def build_state() -> SchedulerState:
        state = SchedulerState()
        for queued in [
            job("c", Band.P3_BACKGROUND_BATCH, 0.0),
            job("a", Band.P1_INTERACTIVE, 1.0),
            job("b", Band.P2_CONSENSUS_VALIDATION, 0.5),
        ]:
            state = enqueue(state, queued)
        return state

    assert drain_ids(build_state(), now=2.0) == drain_ids(build_state(), now=2.0)
