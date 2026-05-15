"""
learning_lifecycle.py - continuous-learning promotion contract.

Continuous-learning artifacts are not runtime authority until they have moved
through validation and promotion. This module keeps that rule small, testable,
and reusable across hints, query retrieval, playbooks, and dashboard surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Tuple


class LearningLifecycleStatus(str, Enum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    CRYSTALLIZED = "crystallized"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


LIFECYCLE_ORDER: Tuple[LearningLifecycleStatus, ...] = (
    LearningLifecycleStatus.OBSERVED,
    LearningLifecycleStatus.CANDIDATE,
    LearningLifecycleStatus.VALIDATED,
    LearningLifecycleStatus.PROMOTED,
    LearningLifecycleStatus.CRYSTALLIZED,
    LearningLifecycleStatus.SUPERSEDED,
    LearningLifecycleStatus.ARCHIVED,
)

REQUIRED_LEARNING_FIELDS: Tuple[str, ...] = (
    "source_event_id",
    "evidence",
    "scope",
    "confidence",
    "last_validated_at",
    "promotion_status",
    "supersedes",
    "expires_at",
)

DEFAULT_RUNTIME_ACTIVE_STATUSES = {
    LearningLifecycleStatus.PROMOTED,
    LearningLifecycleStatus.CRYSTALLIZED,
}


@dataclass(frozen=True)
class LearningRecordValidation:
    valid: bool
    missing_fields: Tuple[str, ...]
    promotion_status: LearningLifecycleStatus
    runtime_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_fields": list(self.missing_fields),
            "promotion_status": self.promotion_status.value,
            "runtime_active": self.runtime_active,
        }


def normalize_promotion_status(value: Any) -> LearningLifecycleStatus:
    if isinstance(value, LearningLifecycleStatus):
        return value
    normalized = str(value or "").strip().lower()
    for status in LearningLifecycleStatus:
        if status.value == normalized:
            return status
    return LearningLifecycleStatus.CANDIDATE


def is_default_runtime_active(status: Any) -> bool:
    return normalize_promotion_status(status) in DEFAULT_RUNTIME_ACTIVE_STATUSES


def is_retired(status: Any) -> bool:
    return normalize_promotion_status(status) in {
        LearningLifecycleStatus.SUPERSEDED,
        LearningLifecycleStatus.ARCHIVED,
    }


def lifecycle_rank(status: Any) -> int:
    normalized = normalize_promotion_status(status)
    return LIFECYCLE_ORDER.index(normalized)


def strongest_status(statuses: Iterable[Any]) -> LearningLifecycleStatus:
    return max((normalize_promotion_status(item) for item in statuses), key=lifecycle_rank, default=LearningLifecycleStatus.CANDIDATE)


def validate_learning_record(record: Mapping[str, Any]) -> LearningRecordValidation:
    missing = tuple(field for field in REQUIRED_LEARNING_FIELDS if field not in record)
    status = normalize_promotion_status(record.get("promotion_status"))
    return LearningRecordValidation(
        valid=not missing,
        missing_fields=missing,
        promotion_status=status,
        runtime_active=is_default_runtime_active(status),
    )


def filter_runtime_active_records(records: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return [
        record
        for record in records
        if is_default_runtime_active(record.get("promotion_status"))
        and not is_retired(record.get("promotion_status"))
    ]
