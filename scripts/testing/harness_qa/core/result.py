"""CheckResult dataclass and helpers for building pass/fail/skip results."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


# 4.5: sole closed details serializer. Self-contained (no external schema-file read, no
# jsonschema dependency) so this module keeps its existing zero-external-dependency
# footprint; the accepted policy order/provider/profile pairing and the
# ``qa.provider-probe-result.v1`` field/enum contract are mirrored here explicitly.
_PROVIDER_ORDER = ("codex", "qwen", "claude", "pi")
_PROFILE_BY_PROVIDER = {
    "codex": "codex_help",
    "qwen": "qwen_help",
    "claude": "claude_help",
    "pi": "pi_help",
}
_FAILURE_CLASSES = frozenset(
    {
        "none",
        "executable_missing",
        "spawn_failed",
        "exit_nonzero",
        "provider_reported_failure",
        "machine_output_missing",
        "machine_output_invalid",
        "deadline_exceeded",
        "output_limit_exceeded",
        "cleanup_failed",
        "interrupted",
        "probe_busy",
        "contract_invalid",
    }
)
_TERMINATION_ACTIONS = frozenset({"sigcont", "sigterm", "sigkill", "quiescence", "reap"})
_ACTION_OUTCOMES = frozenset({"sent", "not_needed", "esrch_verified", "complete", "failed"})
_DISPOSITION_CLASSES = frozenset({"default_terminating", "ignored", "custom"})
_REQUIRED_RECORD_KEYS = frozenset(
    {
        "schema_version", "invocation_id", "provider_id", "profile_id", "lifecycle_state",
        "started_monotonic_ms", "ended_monotonic_ms", "duration_ms", "deadline_ms",
        "exit_code", "result", "failure_class", "termination_actions",
        "stdout_truncated", "stderr_truncated", "stderr_summary", "disposition",
        "evidence_digest",
    }
)


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _valid_record(record: Any, *, provider_id: str, invocation_id: str) -> bool:
    if not isinstance(record, dict) or set(record) != _REQUIRED_RECORD_KEYS:
        return False
    if record["schema_version"] != "qa.provider-probe-result.v1":
        return False
    if record["invocation_id"] != invocation_id:
        return False
    if record["provider_id"] != provider_id or record["profile_id"] != _PROFILE_BY_PROVIDER[provider_id]:
        return False
    if record["lifecycle_state"] != "terminal":
        return False
    started, ended = record["started_monotonic_ms"], record["ended_monotonic_ms"]
    if not isinstance(started, int) or isinstance(started, bool) or started < 0:
        return False
    if not isinstance(ended, int) or isinstance(ended, bool) or ended < 0:
        return False
    duration = record["duration_ms"]
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 <= duration <= 300000:
        return False
    if record["deadline_ms"] != 45000:
        return False
    exit_code = record["exit_code"]
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or not -255 <= exit_code <= 255
    ):
        return False
    result, failure_class = record["result"], record["failure_class"]
    if result not in ("pass", "fail") or failure_class not in _FAILURE_CLASSES:
        return False
    if (result == "pass") != (failure_class == "none"):
        return False
    actions = record["termination_actions"]
    if not isinstance(actions, list) or len(actions) > 8:
        return False
    for entry in actions:
        if not isinstance(entry, dict) or set(entry) != {"action", "outcome", "at_ms"}:
            return False
        if entry["action"] not in _TERMINATION_ACTIONS or entry["outcome"] not in _ACTION_OUTCOMES:
            return False
        at_ms = entry["at_ms"]
        if not isinstance(at_ms, int) or isinstance(at_ms, bool) or not 0 <= at_ms <= 50000:
            return False
    if not isinstance(record["stdout_truncated"], bool) or not isinstance(record["stderr_truncated"], bool):
        return False
    stderr_summary = record["stderr_summary"]
    if not isinstance(stderr_summary, str) or len(stderr_summary) > 4096:
        return False
    disposition = record["disposition"]
    if not isinstance(disposition, dict) or set(disposition) != {"class", "redelivered", "coalesced_signals"}:
        return False
    disposition_class = disposition["class"]
    redelivered = disposition["redelivered"]
    coalesced = disposition["coalesced_signals"]
    if disposition_class is not None and disposition_class not in _DISPOSITION_CLASSES:
        return False
    if not isinstance(redelivered, bool):
        return False
    if not isinstance(coalesced, int) or isinstance(coalesced, bool) or not 0 <= coalesced <= 1000000:
        return False
    if disposition_class is None and redelivered:
        return False
    if redelivered and not isinstance(disposition_class, str):
        return False
    digest = record["evidence_digest"]
    if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
        return False
    if any(ch not in "0123456789abcdef" for ch in digest[7:]):
        return False
    return True


def _valid_details(details: Any) -> bool:
    """Accept only ``None`` or exactly four closed records in accepted policy order."""
    if details is None:
        return True
    if not isinstance(details, list) or len(details) != 4:
        return False
    first = details[0]
    if not isinstance(first, dict):
        return False
    invocation_id = first.get("invocation_id")
    if not _valid_uuid(invocation_id):
        return False
    for provider_id, record in zip(_PROVIDER_ORDER, details):
        if not _valid_record(record, provider_id=provider_id, invocation_id=invocation_id):
            return False
    return True


@dataclass
class CheckResult:
    status: Status
    layer: int
    id: str
    description: str
    reason: str = ""
    duration_ms: float = 0.0
    phase: str = "0"
    details: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict:
        d = {
            "layer": self.layer,
            "id": self.id,
            "status": self.status.value,
            "description": self.description,
        }
        if self.reason:
            d["description"] = f"{self.description} ({self.reason})"
        if self.details is not None:
            if not _valid_details(self.details):
                raise ValueError(
                    "CheckResult.details failed closed qa.provider-probe-result.v1 validation"
                )
            d["details"] = self.details
        return d


def passed(layer: int, id: str, description: str, phase: str = "0") -> CheckResult:
    return CheckResult(Status.PASS, layer, id, description, phase=phase)


def failed(layer: int, id: str, description: str, reason: str = "", phase: str = "0") -> CheckResult:
    return CheckResult(Status.FAIL, layer, id, description, reason=reason, phase=phase)


def skipped(layer: int, id: str, description: str, reason: str = "", phase: str = "0") -> CheckResult:
    return CheckResult(Status.SKIP, layer, id, description, reason=reason, phase=phase)


@dataclass
class ResultSet:
    phase: str
    results: list[CheckResult] = field(default_factory=list)
    duration_s: int = 0
    layer_filter: int = 0
    causality_mode: bool = False

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == Status.SKIP)

    @property
    def degraded_confidence(self) -> bool:
        if not (self.causality_mode and self.layer_filter > 0):
            return False
        layers: dict[int, list[CheckResult]] = {}
        for r in self.results:
            layers.setdefault(r.layer, []).append(r)
        return any(
            any(r.status == Status.FAIL for r in layers[l])
            for l in layers
            if l < self.layer_filter
        )
