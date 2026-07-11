#!/usr/bin/env python3
"""Round manifest schema, persistence, and state transitions for collaboration rounds."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CANONICAL_PROFILE = "aq-canonical-json-v1"
MAX_RECORD_BYTES = 1_048_576


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


class DecisionKind(StrEnum):
    direction = "direction"
    plan = "plan"
    implementation_authorization = "implementation_authorization"


class DecisionState(StrEnum):
    PENDING = "PENDING"
    RATIFIED = "RATIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CORRUPT = "CORRUPT"
    CANCELLED = "CANCELLED"


class AuthorizationState(StrEnum):
    BLOCKED = "BLOCKED"
    AUTHORIZED = "AUTHORIZED"
    CONSUMED = "CONSUMED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class DecisionRecord(StrictModel):
    schema_version: str = "2.0"
    decision_id: str
    kind: DecisionKind
    subject_hash: str
    state: DecisionState
    direction_hash: str | None = None
    package_hash: str | None = None
    reasons: list[str] = Field(default_factory=list, max_length=128)
    review_hashes: list[str] = Field(default_factory=list, max_length=64)


class ImplementationAuthorization(StrictModel):
    schema_version: str = "2.0"
    authorization_id: str
    state: AuthorizationState
    direction_hash: str
    plan_hash: str
    package_hash: str
    ownership_hash: str
    idempotency_key: str
    expires_at: str
    owner_principal: str
    consumed_by: str | None = None
    reasons: list[str] = Field(default_factory=list, max_length=64)


class AssignmentRecord(StrictModel):
    schema_version: str = "2.0"
    assignment_id: str
    authorization_id: str
    principal: str
    state: str = "ASSIGNED"
    subject_hash: str
    created_at: str
    effects_allowed: bool = True
    cancellation_pending: bool = False
    audit: list[str] = Field(default_factory=list, max_length=128)


class RecoveryRecord(StrictModel):
    schema_version: str = "2.0"
    corrupt_hash: str
    quarantine_hash: str
    reconstruction_hash: str
    dry_run_diff_hash: str
    actor: str
    decision: str
    reason: str
    new_revision: str


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
    predecessor_round_id: str | None = None


ALLOWED_TRANSITIONS: dict[RoundState, set[RoundState]] = {
    RoundState.CREATED: {RoundState.DISPATCHED, RoundState.ABORTED},
    RoundState.DISPATCHED: {RoundState.CONTRIBUTING, RoundState.ABORTED},
    RoundState.CONTRIBUTING: {RoundState.COLLECTED, RoundState.ABORTED},
    RoundState.COLLECTED: {
        RoundState.CONFLICTS_IDENTIFIED,
        RoundState.CONSENSUS_LOCKED,
        RoundState.ABORTED,
    },
    RoundState.CONFLICTS_IDENTIFIED: {RoundState.CONSENSUS_LOCKED, RoundState.ABORTED},
    RoundState.CONSENSUS_LOCKED: {RoundState.ASSIGNED, RoundState.AMEND, RoundState.ABORTED},
    RoundState.AMEND: {
        RoundState.CONSENSUS_LOCKED,
        RoundState.CONFLICTS_IDENTIFIED,
        RoundState.ABORTED,
    },
    RoundState.ASSIGNED: {RoundState.IMPLEMENTING, RoundState.ABORTED},
    RoundState.IMPLEMENTING: {RoundState.VALIDATING, RoundState.ABORTED},
    RoundState.VALIDATING: {RoundState.CLOSED, RoundState.IMPLEMENTING, RoundState.ABORTED},
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
        _fsync_directory(destination.parent)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def canonical_bytes(value: Any) -> bytes:
    """Encode a bounded value using aq-canonical-json-v1."""

    normalized = _canonical_normalize(value)
    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError("RECORD_TOO_LARGE")
    return encoded


def canonical_hash(value: Any) -> str:
    return "sha-256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_artifact_hash(data: bytes) -> str:
    return "sha-256:" + hashlib.sha256(data).hexdigest()


def commit_manifest_cas(value: Any, path: str | os.PathLike[str], expected_hash: str | None) -> str:
    """Commit canonical JSON under an exclusive lock and expected-prior-hash CAS."""

    import fcntl

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_name(destination.name + ".lock")
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("LOCK_CONFLICT") from exc
        prior = raw_artifact_hash(destination.read_bytes()) if destination.exists() else None
        if prior != expected_hash:
            raise RuntimeError("CAS_MISMATCH")
        data = canonical_bytes(value) + b"\n"
        tmp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
                tmp_name = tmp.name
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, destination)
            _fsync_directory(destination.parent)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return raw_artifact_hash(data)


def _canonical_normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_normalize(value.model_dump(mode="json"))
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise ValueError("FLOAT_FORBIDDEN")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_canonical_normalize(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str) or not key or not key.isascii() or not key[0].islower() or not all(
                char.islower() or char.isdigit() or char == "_" for char in key
            ):
                raise ValueError("INVALID_CANONICAL_KEY")
            result[key] = _canonical_normalize(value[key])
        return result
    raise ValueError("UNSUPPORTED_CANONICAL_TYPE")


def _fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def idempotency_hash(round_id: str, agent_role: str, task_prompt: str) -> str:
    """Return a stable idempotency hash for an agent lane dispatch."""

    payload = "\x1f".join([round_id, agent_role, task_prompt])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def export_json_schema() -> dict[str, Any]:
    """Export the manifest JSON Schema from the Pydantic SSOT."""

    return RoundManifest.model_json_schema()
