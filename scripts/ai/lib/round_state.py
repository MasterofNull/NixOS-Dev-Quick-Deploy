#!/usr/bin/env python3
"""Round manifest schema, persistence, and state transitions for collaboration rounds."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoundState(StrEnum):
    """Durable lifecycle states for a collaboration round."""

    CREATED = "CREATED"
    DISPATCHED = "DISPATCHED"
    CONTRIBUTING = "CONTRIBUTING"
    COLLECTED = "COLLECTED"
    CONFLICTS_IDENTIFIED = "CONFLICTS_IDENTIFIED"
    CONSENSUS_LOCKED = "CONSENSUS_LOCKED"
    AMEND = "AMEND"
    ASSIGNED = "ASSIGNED"
    IMPLEMENTING = "IMPLEMENTING"
    VALIDATING = "VALIDATING"
    CLOSED = "CLOSED"
    ABORTED = "ABORTED"


class LaneStatus(StrEnum):
    """Per-lane dispatch and contribution status."""

    pending = "pending"
    dispatching = "dispatching"
    running = "running"
    submitted = "submitted"
    failed = "failed"
    timed_out = "timed_out"
    amended = "amended"


class IllegalTransition(ValueError):
    """Raised when a requested round state transition is not allowed."""


class StrictModel(BaseModel):
    """Base model that rejects undeclared manifest fields."""

    model_config = ConfigDict(extra="forbid")


class Lane(StrictModel):
    """One agent lane participating in a round."""

    agent: str
    dispatch_id: str | None
    idempotency_hash: str
    status: LaneStatus
    landed_at: str | None


class QuorumPolicy(StrictModel):
    """Round quorum and timeout policy."""

    min_lanes: int
    required_agents: list[str]
    late_local_admissible: bool = True
    timeout_seconds: int | None
    deadline: str | None
    timeout_action: str = "lock_with_present"


class Conflict(StrictModel):
    """A detected conflict among lane contributions."""

    file_path: str
    line_range: str | None
    description: str
    competing: list[str]


class RoundTask(StrictModel):
    """User task metadata attached to a round."""

    prompt: str
    target: str
    scope_files: list[str]


class HistoryEntry(StrictModel):
    """Durable state transition audit entry."""

    transition: str
    timestamp: str
    actor: str


class RoundManifest(StrictModel):
    """Pydantic SSOT for round.json."""

    schema_version: str = "1.0"
    round_id: str
    state: RoundState
    task: RoundTask
    opened_at: str
    quorum_policy: QuorumPolicy
    lanes: list[Lane]
    contributions: dict[str, str] = Field(default_factory=dict)
    conflicts: list[Conflict] = Field(default_factory=list)
    consensus_hash: str | None
    aggregate_path: str | None
    aggregate_hash: str | None
    locked_at: str | None
    history: list[HistoryEntry] = Field(default_factory=list)


ALLOWED_TRANSITIONS: dict[RoundState, set[RoundState]] = {
    RoundState.CREATED: {RoundState.DISPATCHED, RoundState.ABORTED},
    RoundState.DISPATCHED: {RoundState.CONTRIBUTING, RoundState.ABORTED},
    RoundState.CONTRIBUTING: {RoundState.COLLECTED, RoundState.ABORTED},
    RoundState.COLLECTED: {
        RoundState.CONFLICTS_IDENTIFIED,
        RoundState.CONSENSUS_LOCKED,
    },
    RoundState.CONFLICTS_IDENTIFIED: {RoundState.CONSENSUS_LOCKED},
    RoundState.CONSENSUS_LOCKED: {RoundState.ASSIGNED, RoundState.AMEND},
    RoundState.AMEND: {
        RoundState.CONSENSUS_LOCKED,
        RoundState.CONFLICTS_IDENTIFIED,
    },
    RoundState.ASSIGNED: {RoundState.IMPLEMENTING},
    RoundState.IMPLEMENTING: {RoundState.VALIDATING},
    RoundState.VALIDATING: {RoundState.CLOSED, RoundState.IMPLEMENTING},
    RoundState.CLOSED: set(),
    RoundState.ABORTED: set(),
}


def utc_iso() -> str:
    """Return a second-granularity UTC ISO 8601 timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def transition(manifest: RoundManifest, to_state: RoundState, actor: str) -> RoundManifest:
    """Return a new manifest after applying a legal durable state transition."""

    if to_state not in ALLOWED_TRANSITIONS[manifest.state]:
        raise IllegalTransition(f"{manifest.state.value}->{to_state.value} is not allowed")

    entry = HistoryEntry(
        transition=f"{manifest.state.value}->{to_state.value}",
        timestamp=utc_iso(),
        actor=actor,
    )
    return manifest.model_copy(update={"state": to_state, "history": [*manifest.history, entry]})


def load(path: str | os.PathLike[str]) -> RoundManifest:
    """Load and validate a round manifest from disk."""

    return RoundManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save(manifest: RoundManifest, path: str | os.PathLike[str]) -> None:
    """Atomically write a round manifest as formatted JSON."""

    destination = Path(path)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(manifest.model_dump_json(indent=2))
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, destination)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def idempotency_hash(round_id: str, agent_role: str, task_prompt: str) -> str:
    """Return a stable idempotency hash for an agent lane dispatch."""

    payload = "\x1f".join([round_id, agent_role, task_prompt])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def export_json_schema() -> dict[str, Any]:
    """Export the manifest JSON Schema from the Pydantic SSOT."""

    return RoundManifest.model_json_schema()
