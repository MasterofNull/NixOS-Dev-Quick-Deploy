#!/usr/bin/env python3
"""Fast tests for the pure F2 model-tier routing matrix."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai" / "lib"))

import model_tier  # noqa: E402


EXPECTED_ROUTES = {
    model_tier.TaskClass.CLASSIFICATION: (model_tier.Tier.SMALL_RESIDENT, 3, "resident"),
    model_tier.TaskClass.JSON_REPAIR: (model_tier.Tier.SMALL_RESIDENT, 3, "resident"),
    model_tier.TaskClass.TOOL_SCHEMA_VALIDATION: (model_tier.Tier.SMALL_RESIDENT, 3, "resident"),
    model_tier.TaskClass.SHORT_CRITIQUE: (model_tier.Tier.SMALL_RESIDENT, 3, "resident"),
    model_tier.TaskClass.PATH_GREP_SUMMARY: (model_tier.Tier.SMALL_RESIDENT, 3, "resident"),
    model_tier.TaskClass.BOUNDED_EDIT: (model_tier.Tier.MID_RESIDENT, 1, "resident"),
    model_tier.TaskClass.DIFF_ANALYSIS: (model_tier.Tier.MID_RESIDENT, 1, "resident"),
    model_tier.TaskClass.SINGLE_FILE_PLAN: (model_tier.Tier.MID_RESIDENT, 1, "resident"),
    model_tier.TaskClass.TEST_ERROR_TRIAGE: (model_tier.Tier.MID_RESIDENT, 1, "resident"),
    model_tier.TaskClass.ARCHITECTURE: (model_tier.Tier.LARGE_SESSION, 1, "session"),
    model_tier.TaskClass.CONSENSUS_VOTE: (model_tier.Tier.LARGE_SESSION, 1, "session"),
    model_tier.TaskClass.MULTI_FILE_REFACTOR: (model_tier.Tier.LARGE_SESSION, 1, "session"),
    model_tier.TaskClass.DISSENT_REVIEW: (model_tier.Tier.LARGE_SESSION, 1, "session"),
}


def assert_route(task_class: model_tier.TaskClass | str, tier: model_tier.Tier, limit: int, residency: str) -> None:
    resolved = model_tier.route(task_class)

    assert resolved.tier == tier
    assert resolved.concurrency_limit == limit
    assert resolved.residency == residency


def test_every_ratified_task_class_routes_to_expected_tier_attrs() -> None:
    for task_class, expected in EXPECTED_ROUTES.items():
        assert_route(task_class, *expected)
        assert_route(task_class.value, *expected)


def test_unknown_string_defaults_to_mid_resident_not_large_session() -> None:
    resolved = model_tier.route("unknown_task_class")

    assert resolved.tier == model_tier.Tier.MID_RESIDENT
    assert resolved.tier != model_tier.Tier.LARGE_SESSION
    assert resolved.concurrency_limit == 1
    assert resolved.residency == "resident"


def test_mapping_table_is_complete_for_task_class_enum() -> None:
    assert set(model_tier.TASK_CLASS_TIERS) == set(model_tier.TaskClass)


def test_mapping_table_is_internally_consistent() -> None:
    assert set(model_tier.TASK_CLASS_TIERS.values()) <= set(model_tier.Tier)
    assert set(model_tier.TIER_ROUTES) == set(model_tier.Tier)
    for tier in model_tier.Tier:
        assert tier in set(model_tier.TASK_CLASS_TIERS.values())
        assert model_tier.TIER_ROUTES[tier].tier == tier


def test_route_is_deterministic() -> None:
    first = model_tier.route(model_tier.TaskClass.DIFF_ANALYSIS)
    second = model_tier.route(model_tier.TaskClass.DIFF_ANALYSIS)
    unknown_first = model_tier.route("not_in_matrix")
    unknown_second = model_tier.route("not_in_matrix")

    assert first == second
    assert unknown_first == unknown_second
