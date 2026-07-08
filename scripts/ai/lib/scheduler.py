#!/usr/bin/env python3
"""Pure MLFQ slot scheduler with aging and preemption decisions."""

from __future__ import annotations

from enum import StrEnum
from math import inf

from pydantic import BaseModel, ConfigDict, Field


class Band(StrEnum):
    """Priority bands for local model-slot scheduling."""

    P1_INTERACTIVE = "P1_INTERACTIVE"
    P2_CONSENSUS_VALIDATION = "P2_CONSENSUS_VALIDATION"
    P3_BACKGROUND_BATCH = "P3_BACKGROUND_BATCH"


BAND_PRIORITY: dict[Band, int] = {
    Band.P1_INTERACTIVE: 1,
    Band.P2_CONSENSUS_VALIDATION: 2,
    Band.P3_BACKGROUND_BATCH: 3,
}

DEFAULT_MAX_SLOT_TIME_S: dict[Band, int] = {
    Band.P1_INTERACTIVE: 10,
    Band.P2_CONSENSUS_VALIDATION: 30,
    Band.P3_BACKGROUND_BATCH: 120,
}

DEFAULT_MAX_WAIT_S: dict[Band, float] = {
    Band.P1_INTERACTIVE: inf,
    Band.P2_CONSENSUS_VALIDATION: 30.0,
    Band.P3_BACKGROUND_BATCH: 30.0,
}

DEFAULT_STARVATION_CEILING_S = 90.0


class StrictModel(BaseModel):
    """Base model that rejects undeclared scheduler fields."""

    model_config = ConfigDict(extra="forbid")


class Job(StrictModel):
    """One caller-supplied unit of schedulable work."""

    id: str
    band: Band
    enqueued_at: float
    task_class: str | None
    preempted_context: str | None = None


class SchedulerConfig(StrictModel):
    """Scheduler tuning knobs with bounded starvation defaults."""

    max_slot_time_s: dict[Band, int] = Field(default_factory=lambda: DEFAULT_MAX_SLOT_TIME_S.copy())
    max_wait_s: dict[Band, float] = Field(default_factory=lambda: DEFAULT_MAX_WAIT_S.copy())
    starvation_ceiling_s: float = DEFAULT_STARVATION_CEILING_S


class SchedulerState(StrictModel):
    """In-memory scheduler state; callers own persistence if they need it."""

    queue: list[Job] = Field(default_factory=list)
    running: Job | None = None
    config: SchedulerConfig = Field(default_factory=SchedulerConfig)


def enqueue(state: SchedulerState, job: Job) -> SchedulerState:
    """Return a state with job appended to the queue."""

    return state.model_copy(update={"queue": [*state.queue, job]})


def next_job(state: SchedulerState, now: float) -> tuple[Job | None, SchedulerState]:
    """Pick and remove the highest-priority eligible job, FIFO within a band."""

    aged = age(state, now)
    if not aged.queue:
        return None, aged.model_copy(update={"running": None})

    selected = min(
        aged.queue,
        key=lambda job: (BAND_PRIORITY[job.band], job.enqueued_at, job.id),
    )
    remaining = [job for job in aged.queue if job != selected]
    return selected, aged.model_copy(update={"queue": remaining, "running": selected})


def age(state: SchedulerState, now: float) -> SchedulerState:
    """Promote waiting jobs by configured bounds without reading the clock."""

    return state.model_copy(
        update={
            "queue": [_aged_job(job, now, state.config) for job in state.queue],
            "running": _aged_job(state.running, now, state.config) if state.running else None,
        }
    )


def preempt(state: SchedulerState, incoming: Job, now: float) -> tuple[Job | None, SchedulerState]:
    """Return an evicted P3 job when an incoming P1 should take the slot."""

    aged = age(state, now)
    if incoming.band != Band.P1_INTERACTIVE:
        return None, enqueue(aged, incoming)

    if aged.running and aged.running.band == Band.P3_BACKGROUND_BATCH:
        evicted = _stash_preempted_context(aged.running, now)
        return evicted, aged.model_copy(update={"running": None, "queue": [*aged.queue, incoming]})

    if aged.running and aged.running.band == Band.P1_INTERACTIVE:
        return None, enqueue(aged, incoming)

    queued_p3 = _next_queued_p3(aged.queue)
    if queued_p3 is None:
        return None, enqueue(aged, incoming)

    evicted = _stash_preempted_context(queued_p3, now)
    remaining = [job for job in aged.queue if job != queued_p3]
    return evicted, aged.model_copy(update={"queue": [*remaining, incoming]})


def no_starvation_invariant(state: SchedulerState, now: float, ceiling: float) -> bool:
    """Return True iff no non-P1 job has waited beyond the starvation ceiling."""

    candidates = [*state.queue]
    if state.running is not None:
        candidates.append(state.running)
    return all(job.band == Band.P1_INTERACTIVE or now - job.enqueued_at <= ceiling for job in candidates)


def _aged_job(job: Job, now: float, config: SchedulerConfig) -> Job:
    wait_s = now - job.enqueued_at
    if wait_s > config.starvation_ceiling_s:
        return job.model_copy(update={"band": Band.P1_INTERACTIVE})
    if wait_s > config.max_wait_s.get(job.band, inf):
        return job.model_copy(update={"band": _promote(job.band)})
    return job


def _promote(band: Band) -> Band:
    if band == Band.P3_BACKGROUND_BATCH:
        return Band.P2_CONSENSUS_VALIDATION
    if band == Band.P2_CONSENSUS_VALIDATION:
        return Band.P1_INTERACTIVE
    return band


def _next_queued_p3(queue: list[Job]) -> Job | None:
    p3_jobs = [job for job in queue if job.band == Band.P3_BACKGROUND_BATCH]
    if not p3_jobs:
        return None
    return min(p3_jobs, key=lambda job: (job.enqueued_at, job.id))


def _stash_preempted_context(job: Job, now: float) -> Job:
    context = job.preempted_context or f"preempted@{now:g}"
    return job.model_copy(update={"preempted_context": context})
