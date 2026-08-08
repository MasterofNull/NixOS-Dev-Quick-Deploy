#!/usr/bin/env python3
"""Pure, dependency-free workflow-deviation contract resolver."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "aq.workflow-deviation.v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9._-]{2,95}$")
_ROOT_KEY = re.compile(r"^[a-z][a-z0-9._-]{2,127}$")
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)

_CLASSIFICATION: dict[str, tuple[str, str, bool, bool]] = {
    "validation.environment": ("medium", "none", True, False),
    "review.request_revision": ("medium", "low", True, False),
    "delegation.unregistered": ("high", "low", True, False),
    "provider.capacity": ("medium", "none", True, False),
    "monitoring.receipt_missing": ("high", "low", True, False),
    "observation.failed": ("high", "low", True, False),
    "subject.drift": ("high", "medium", False, True),
    "authorization.invalid": ("critical", "high", False, True),
    "release.boundary": ("critical", "high", False, True),
    "security.policy": ("critical", "high", False, True),
    "deployment.runtime": ("critical", "high", False, True),
    "secret.exposure": ("critical", "high", False, True),
    "external.side_effect": ("critical", "high", False, True),
}

_TOP_KEYS = {
    "schema_version", "deviation_id", "occurred_at", "source",
    "reason_code", "summary", "severity", "mutation_risk", "retryable",
    "requires_owner", "automatic_eligible", "root_issue_key", "evidence",
    "disposition",
}
_SOURCE_KEYS = {"lane", "component", "phase", "workflow_id", "subject_digest"}
_EVIDENCE_KEYS = {"kind", "ref", "digest"}
_DISPOSITIONS = {
    "detected", "deduplicated", "issue_opened", "shadow_queued", "parked",
    "approval_required", "resolved", "rejected",
}


class DeviationContractError(ValueError):
    """The supplied deviation cannot enter the recursive-learning loop."""


def classify(reason_code: str) -> dict[str, Any]:
    """Return fail-closed derived policy for a stable reason code."""
    if not isinstance(reason_code, str) or not _REASON_CODE.fullmatch(reason_code):
        raise DeviationContractError("reason-code-invalid")
    severity, risk, retryable, owner = _CLASSIFICATION.get(
        reason_code, ("high", "medium", False, True)
    )
    return {
        "severity": severity,
        "mutation_risk": risk,
        "retryable": retryable,
        "requires_owner": owner,
        "automatic_eligible": risk in {"none", "low"} and not owner,
    }


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def deviation_id(record_without_id: Mapping[str, Any]) -> str:
    payload = b"aq.workflow-deviation.v1\0" + _canonical(record_without_id)
    return "wd_" + hashlib.sha256(payload).hexdigest()


def build(
    *,
    occurred_at: str,
    source: Mapping[str, str],
    reason_code: str,
    summary: str,
    root_issue_key: str,
    evidence: Sequence[Mapping[str, str]],
    disposition: str = "detected",
) -> dict[str, Any]:
    """Build and validate a closed deviation record without I/O or a clock."""
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "occurred_at": occurred_at,
        "source": dict(source),
        "reason_code": reason_code,
        "summary": summary,
        **classify(reason_code),
        "root_issue_key": root_issue_key,
        "evidence": [dict(item) for item in evidence],
        "disposition": disposition,
    }
    record["deviation_id"] = deviation_id(record)
    validate(record)
    return record


def validate(record: Mapping[str, Any]) -> None:
    """Validate closed shape and all derived fields; raise on ambiguity."""
    if not isinstance(record, Mapping) or set(record) != _TOP_KEYS:
        raise DeviationContractError("record-keys-invalid")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise DeviationContractError("schema-version-invalid")
    occurred_at = record.get("occurred_at")
    if not isinstance(occurred_at, str) or not _RFC3339.fullmatch(occurred_at):
        raise DeviationContractError("occurred-at-invalid")
    try:
        parsed_at = datetime.fromisoformat(
            occurred_at.replace("Z", "+00:00").replace("z", "+00:00")
        )
    except ValueError as exc:
        raise DeviationContractError("occurred-at-invalid") from exc
    if parsed_at.tzinfo is None:
        raise DeviationContractError("occurred-at-invalid")
    source = record.get("source")
    if not isinstance(source, Mapping) or not {"lane", "component", "phase"}.issubset(source):
        raise DeviationContractError("source-invalid")
    if not set(source).issubset(_SOURCE_KEYS):
        raise DeviationContractError("source-keys-invalid")
    source_limits = {"lane": 64, "component": 128, "phase": 64}
    for key, limit in source_limits.items():
        if not isinstance(source.get(key), str) or not (1 <= len(source[key]) <= limit):
            raise DeviationContractError("source-value-invalid")
    workflow_id = source.get("workflow_id")
    if workflow_id is not None and (
        not isinstance(workflow_id, str) or not (1 <= len(workflow_id) <= 128)
    ):
        raise DeviationContractError("workflow-id-invalid")
    digest = source.get("subject_digest")
    if digest is not None and (not isinstance(digest, str) or not _HEX64.fullmatch(digest)):
        raise DeviationContractError("subject-digest-invalid")
    if not isinstance(record.get("summary"), str) or not (1 <= len(record["summary"]) <= 300):
        raise DeviationContractError("summary-invalid")
    root_key = record.get("root_issue_key")
    if not isinstance(root_key, str) or not _ROOT_KEY.fullmatch(root_key):
        raise DeviationContractError("root-issue-key-invalid")
    if record.get("disposition") not in _DISPOSITIONS:
        raise DeviationContractError("disposition-invalid")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or len(evidence) > 16:
        raise DeviationContractError("evidence-invalid")
    for item in evidence:
        if not isinstance(item, Mapping) or set(item) != _EVIDENCE_KEYS:
            raise DeviationContractError("evidence-keys-invalid")
        if item.get("kind") not in {"artifact", "log", "receipt", "test", "review", "state"}:
            raise DeviationContractError("evidence-kind-invalid")
        if not isinstance(item.get("ref"), str) or not (1 <= len(item["ref"]) <= 256):
            raise DeviationContractError("evidence-ref-invalid")
        if not isinstance(item.get("digest"), str) or not _HEX64.fullmatch(item["digest"]):
            raise DeviationContractError("evidence-digest-invalid")
    expected_policy = classify(record["reason_code"])
    for key, value in expected_policy.items():
        if record.get(key) != value:
            raise DeviationContractError(f"derived-{key}-invalid")
    body = dict(record)
    supplied_id = body.pop("deviation_id", None)
    if supplied_id != deviation_id(body):
        raise DeviationContractError("deviation-id-invalid")


def learning_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    """Project a bounded PRSI candidate or an explicit approval-required result."""
    validate(record)
    if not record["automatic_eligible"]:
        return {
            "eligible": False,
            "disposition": "approval_required" if record["requires_owner"] else "parked",
            "root_issue_key": record["root_issue_key"],
            "deviation_id": record["deviation_id"],
        }
    return {
        "eligible": True,
        "type": "maintenance",
        "risk": record["mutation_risk"],
        "root_issue_key": record["root_issue_key"],
        "deviation_id": record["deviation_id"],
        "reason": record["reason_code"],
        "action": "diagnose-root-cause-and-prepare-shadow-repair",
    }
