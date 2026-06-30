"""Replayable agent-run event envelopes for Pi-style observability.

This module is intentionally small and dependency-free. It gives scripts and
services one canonical shape for future single-agent replay, swimlane views,
race comparisons, useful-token metrics, and human-control audit events.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "maeah.agent-run-event.v1"

EVENT_TYPES = {
    "prompt_load",
    "spec_variant",
    "system_prompt",
    "memory_recall",
    "skill_load",
    "model_call",
    "tool_call",
    "tool_result",
    "token_usage",
    "artifact",
    "validation",
    "review",
    "human_control",
    "thought",
    "planning",
    "final_outcome",
}

STATUSES = {
    "started",
    "running",
    "succeeded",
    "failed",
    "blocked",
    "skipped",
    "no_data",
}

SPEC_VARIANTS = {"markdown", "html", "visual_html"}
SECRET_KEY_FRAGMENTS = ("secret", "token", "password", "passwd", "api_key", "apikey", "credential", "authorization")
SAFE_TELEMETRY_KEYS = {"tokens_in", "tokens_out", "max_tokens", "token_count", "total_tokens"}
SERVICE_EVENT_PATH = Path("/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl")


def now_iso() -> str:
    """Return an RFC3339 UTC timestamp with Z suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: str, *, length: int = 16) -> str:
    """Return a stable short digest for prompt/tool payload references."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def redact_payload(payload: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Redact likely secret-bearing keys recursively.

    The event stream is meant for operator debugging. It should expose enough
    context to understand behavior while avoiding raw secrets in replay UIs.
    """
    if not payload:
        return {}, []

    secret_fields: list[str] = []

    def scrub(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, nested in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                lowered = str(key).lower()
                if lowered not in SAFE_TELEMETRY_KEYS and any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
                    secret_fields.append(child_path)
                    redacted[str(key)] = "[REDACTED]"
                else:
                    redacted[str(key)] = scrub(nested, child_path)
            return redacted
        if isinstance(value, list):
            return [scrub(item, f"{path}[]") for item in value]
        return value

    return scrub(payload, ""), secret_fields


def make_event(
    event_type: str,
    *,
    source: str,
    run_id: str,
    status: str = "succeeded",
    timestamp: str | None = None,
    payload: dict[str, Any] | None = None,
    experiment_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    slice_id: str | None = None,
    agent_id: str | None = None,
    role: str | None = None,
    autonomy_boundary: str | None = None,
    lane_id: str | None = None,
    parent_event_id: str | None = None,
    trace_id: str | None = None,
    duration_ms: float | None = None,
    route_profile: str | None = None,
    model: str | None = None,
    tool_name: str | None = None,
    spec: dict[str, Any] | None = None,
    tokens: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
    no_data_reason: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Build and validate one agent-run event envelope."""
    clean_payload, secret_fields = redact_payload(payload)
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": timestamp or now_iso(),
        "source": source,
        "run_id": run_id,
        "experiment_id": experiment_id,
        "session_id": session_id,
        "task_id": task_id,
        "slice_id": slice_id,
        "agent_id": agent_id,
        "role": role,
        "autonomy_boundary": autonomy_boundary,
        "lane_id": lane_id,
        "parent_event_id": parent_event_id,
        "trace_id": trace_id,
        "duration_ms": duration_ms,
        "status": status,
        "route_profile": route_profile,
        "model": model,
        "tool_name": tool_name,
        "spec": _normalize_spec(spec),
        "tokens": _normalize_tokens(tokens),
        "cost": _normalize_cost(cost),
        "artifact": _normalize_artifact(artifact),
        "redaction": {
            "payload_redacted": bool(secret_fields),
            "secret_fields": secret_fields,
        },
        "payload": clean_payload,
        "no_data_reason": no_data_reason,
    }
    validate_event(event)
    return event


def _normalize_spec(spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = dict(spec or {})
    return {
        "variant": spec.get("variant"),
        "canonical_path": spec.get("canonical_path"),
        "derived_path": spec.get("derived_path"),
        "source_hash": spec.get("source_hash"),
        "generator": spec.get("generator"),
    }


def _normalize_tokens(tokens: dict[str, Any] | None) -> dict[str, Any]:
    tokens = dict(tokens or {})
    total = tokens.get("total")
    if total is None:
        parts = [tokens.get("input"), tokens.get("output"), tokens.get("tool_output")]
        if any(isinstance(part, int) for part in parts):
            total = sum(part for part in parts if isinstance(part, int))
    useful_ratio = tokens.get("useful_ratio")
    accepted = tokens.get("accepted_artifact")
    if useful_ratio is None and isinstance(accepted, int) and isinstance(total, int) and total > 0:
        useful_ratio = round(min(max(accepted / total, 0), 1), 4)
    return {
        "input": tokens.get("input"),
        "output": tokens.get("output"),
        "context": tokens.get("context"),
        "tool_output": tokens.get("tool_output"),
        "accepted_artifact": accepted,
        "rework": tokens.get("rework"),
        "total": total,
        "useful_ratio": useful_ratio,
    }


def _normalize_cost(cost: dict[str, Any] | None) -> dict[str, Any]:
    cost = dict(cost or {})
    return {
        "amount": cost.get("amount"),
        "currency": cost.get("currency"),
    }


def _normalize_artifact(artifact: dict[str, Any] | None) -> dict[str, Any]:
    artifact = dict(artifact or {})
    return {
        "path": artifact.get("path"),
        "kind": artifact.get("kind"),
        "hash": artifact.get("hash"),
        "accepted": artifact.get("accepted"),
    }


def validate_event(event: dict[str, Any]) -> None:
    """Validate the subset of schema rules required by runtime code/tests."""
    required = ("schema_version", "event_id", "event_type", "timestamp", "source", "run_id", "status", "redaction")
    missing = [key for key in required if key not in event]
    if missing:
        raise ValueError(f"agent-run event missing required fields: {', '.join(missing)}")
    if event["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"invalid schema_version: {event['schema_version']}")
    if event["event_type"] not in EVENT_TYPES:
        raise ValueError(f"invalid event_type: {event['event_type']}")
    if event["status"] not in STATUSES:
        raise ValueError(f"invalid status: {event['status']}")
    if not event["source"]:
        raise ValueError("source must not be empty")
    if not event["run_id"]:
        raise ValueError("run_id must not be empty")
    if event.get("duration_ms") is not None and event["duration_ms"] < 0:
        raise ValueError("duration_ms must be non-negative")
    spec = event.get("spec") or {}
    variant = spec.get("variant")
    if variant is not None and variant not in SPEC_VARIANTS:
        raise ValueError(f"invalid spec.variant: {variant}")
    tokens = event.get("tokens") or {}
    for key in ("input", "output", "context", "tool_output", "accepted_artifact", "rework", "total"):
        value = tokens.get(key)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValueError(f"tokens.{key} must be a non-negative integer or null")
    useful_ratio = tokens.get("useful_ratio")
    if useful_ratio is not None and not (0 <= useful_ratio <= 1):
        raise ValueError("tokens.useful_ratio must be between 0 and 1")
    redaction = event.get("redaction") or {}
    if not isinstance(redaction.get("payload_redacted"), bool):
        raise ValueError("redaction.payload_redacted must be a boolean")
    if not isinstance(redaction.get("secret_fields"), list):
        raise ValueError("redaction.secret_fields must be a list")


def reconstruct_timeline(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and sort events into replay order."""
    timeline = list(events)
    for event in timeline:
        validate_event(event)
    return sorted(timeline, key=lambda item: (item["timestamp"], item["event_id"]))


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    """Append a validated event to a JSONL file."""
    validate_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def repo_root() -> Path:
    """Resolve the repository root for user-writable observability spools."""
    env_root = os.getenv("REPO_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[3]


def repo_event_path(root: Path | None = None) -> Path:
    """Return the repo-local canonical agent-run event spool."""
    return (root or repo_root()) / ".agents" / "telemetry" / "agent-run-events.jsonl"


def default_event_path(root: Path | None = None) -> Path:
    """Return the canonical write path for agent-run events.

    Service processes can set AQ_AGENT_RUN_EVENTS_PATH or write to the service
    telemetry path. User-space CLIs fall back to a repo-local spool with the
    same schema so dashboard readers can merge both streams.
    """
    env_path = os.getenv("AQ_AGENT_RUN_EVENTS_PATH")
    if env_path:
        return Path(env_path)
    if SERVICE_EVENT_PATH.parent.exists() and os.access(str(SERVICE_EVENT_PATH.parent), os.W_OK):
        return SERVICE_EVENT_PATH
    return repo_event_path(root)


def _safe_run_id(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_id).strip("._")
    return (safe or stable_digest(run_id))[:160]


def latest_projection_path(run_id: str, root: Path | None = None) -> Path:
    """Return the repo-local latest-state projection path for one run."""
    return (root or repo_root()) / ".agents" / "observability" / "latest" / f"{_safe_run_id(run_id)}.json"


def write_latest_projection(event: dict[str, Any], root: Path | None = None) -> Path:
    """Atomically write the latest observed state for a run.

    This is a projection of agent-run-events.jsonl, not a second source of
    truth. Existing dashboards and CLIs can read it for low-latency status.
    """
    validate_event(event)
    path = latest_projection_path(str(event["run_id"]), root)
    projection = {
        "schema_version": f"{SCHEMA_VERSION}.latest",
        "run_id": event["run_id"],
        "updated_at": now_iso(),
        "latest_event": event,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(projection, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def emit_event(
    event_type: str,
    *,
    root: Path | None = None,
    event_path: Path | None = None,
    write_latest: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create, append, and project one canonical agent-run event."""
    event = make_event(event_type, **kwargs)
    append_jsonl(event_path or default_event_path(root), event)
    if write_latest:
        write_latest_projection(event, root)
    return event


def load_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Load and validate agent-run events from JSONL."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
    if limit is not None:
        records = records[-limit:]
    return reconstruct_timeline(records)
