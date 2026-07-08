#!/usr/bin/env python3
"""Pure model-tier routing matrix for local scheduler task classes.

Unknown task classes default to MID_RESIDENT: it is capable enough for bounded
work without spending the scarce 35B large-session slot on ambiguous requests.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


Residency = Literal["resident", "session"]


class Tier(StrEnum):
    """Model residency tiers from the ratified F2 routing matrix."""

    SMALL_RESIDENT = "SMALL_RESIDENT"
    MID_RESIDENT = "MID_RESIDENT"
    LARGE_SESSION = "LARGE_SESSION"


class TaskClass(StrEnum):
    """Validated task classes accepted by the F2 model-tier router."""

    CLASSIFICATION = "classification"
    JSON_REPAIR = "json_repair"
    TOOL_SCHEMA_VALIDATION = "tool_schema_validation"
    SHORT_CRITIQUE = "short_critique"
    PATH_GREP_SUMMARY = "path_grep_summary"
    BOUNDED_EDIT = "bounded_edit"
    DIFF_ANALYSIS = "diff_analysis"
    SINGLE_FILE_PLAN = "single_file_plan"
    TEST_ERROR_TRIAGE = "test_error_triage"
    ARCHITECTURE = "architecture"
    CONSENSUS_VOTE = "consensus_vote"
    MULTI_FILE_REFACTOR = "multi_file_refactor"
    DISSENT_REVIEW = "dissent_review"


class TierRoute(BaseModel):
    """Resolved routing attributes for a task class."""

    model_config = ConfigDict(frozen=True)

    tier: Tier
    concurrency_limit: int
    residency: Residency


TASK_CLASS_TIERS: dict[TaskClass, Tier] = {
    TaskClass.CLASSIFICATION: Tier.SMALL_RESIDENT,
    TaskClass.JSON_REPAIR: Tier.SMALL_RESIDENT,
    TaskClass.TOOL_SCHEMA_VALIDATION: Tier.SMALL_RESIDENT,
    TaskClass.SHORT_CRITIQUE: Tier.SMALL_RESIDENT,
    TaskClass.PATH_GREP_SUMMARY: Tier.SMALL_RESIDENT,
    TaskClass.BOUNDED_EDIT: Tier.MID_RESIDENT,
    TaskClass.DIFF_ANALYSIS: Tier.MID_RESIDENT,
    TaskClass.SINGLE_FILE_PLAN: Tier.MID_RESIDENT,
    TaskClass.TEST_ERROR_TRIAGE: Tier.MID_RESIDENT,
    TaskClass.ARCHITECTURE: Tier.LARGE_SESSION,
    TaskClass.CONSENSUS_VOTE: Tier.LARGE_SESSION,
    TaskClass.MULTI_FILE_REFACTOR: Tier.LARGE_SESSION,
    TaskClass.DISSENT_REVIEW: Tier.LARGE_SESSION,
}

TIER_ROUTES: dict[Tier, TierRoute] = {
    Tier.SMALL_RESIDENT: TierRoute(tier=Tier.SMALL_RESIDENT, concurrency_limit=3, residency="resident"),
    Tier.MID_RESIDENT: TierRoute(tier=Tier.MID_RESIDENT, concurrency_limit=1, residency="resident"),
    Tier.LARGE_SESSION: TierRoute(tier=Tier.LARGE_SESSION, concurrency_limit=1, residency="session"),
}

DEFAULT_TASK_CLASS_TIER = Tier.MID_RESIDENT


def route(task_class: TaskClass | str) -> TierRoute:
    """Return the conservative model-tier route for a task class."""

    normalized = _normalize_task_class(task_class)
    tier = TASK_CLASS_TIERS.get(normalized, DEFAULT_TASK_CLASS_TIER)
    return TIER_ROUTES[tier]


def _normalize_task_class(task_class: TaskClass | str) -> TaskClass | None:
    if isinstance(task_class, TaskClass):
        return task_class
    try:
        return TaskClass(task_class)
    except ValueError:
        return None
