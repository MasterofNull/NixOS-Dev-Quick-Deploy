#!/usr/bin/env python3
"""Regression checks for aq-report runtime recommendations and structured actions."""

from __future__ import annotations

import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_aq_report():
    os.environ.setdefault("AI_STRICT_ENV", "false")
    spec = importlib.util.spec_from_loader(
        "aq_report_runtime_actions",
        SourceFileLoader("aq_report_runtime_actions", str(AQ_REPORT_PATH)),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load aq-report")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    aq_report = load_aq_report()

    route = {"available": True, "local_pct": 100.0}
    cache = {"available": True, "hit_pct": 70.1}
    eval_trend = {
        "available": True,
        "trend": "falling",
        "latest_pct": 30.0,
        "mean_pct": 40.0,
        "n_runs": 2,
        "source": "tool_audit",
    }
    route_latency = {
        "available": True,
        "overall_p95_ms": 11065.0,
        "actionable_p95_ms": 11065.0,
        "backend_valid_p95_ms": 11065.0,
        "client_error_count": 0,
        "backend_unclassified_count": 0,
        "total_calls": 71,
        "breakdown": [
            {"label": "local_lane:reasoning", "calls": 6, "p95_ms": 15267.3},
            {"label": "synthesis_type:reasoning", "calls": 6, "p95_ms": 15267.3},
            {"label": "local_lane:default", "calls": 3, "p95_ms": 4820.0},
        ],
    }

    recommendations = aq_report.build_recommendations(
        {},
        route,
        cache,
        eval_trend,
        [],
        route_latency_decomposition=route_latency,
        feedback_acceleration={
            "available": True,
            "status": "watch",
            "promotable_lessons": 2,
        },
        gap_remediation={
            "available": True,
            "candidate_count": 2,
            "top_strategies": [("extract_pattern", 1), ("import_knowledge", 1)],
        },
    )
    joined = "\n".join(recommendations)
    assert_true("eval-regression-check" in joined, "expected tagged eval recommendation")
    assert_true("Local reasoning synthesis remains the route_search tail" in joined, "expected reasoning-lane recommendation")
    assert_true("Dedicated local reasoning is materially slower than the default local lane" in joined, "expected default-vs-reasoning lane recommendation")
    assert_true("promotable lesson candidate" in joined, "expected feedback acceleration recommendation")
    assert_true("Recurring capability gaps remain actionable" in joined, "expected gap remediation recommendation")
    workflow_context = aq_report.build_recommendations(
        {
            "workflow_run_start": {
                "calls": 4,
                "success_pct": 50.0,
                "error_count": 2,
                "client_error_count": 0,
                "p95_ms": 90.0,
            }
        },
        route,
        cache,
        {"available": False},
        [],
        intent_compliance={"available": True, "accepted_reviews": 2, "rejected_reviews": 0, "pending_reviews": 0},
        recent_tool_stats={
            "workflow_run_start": {
                "calls": 4,
                "success_pct": 50.0,
                "error_count": 2,
                "client_error_count": 0,
                "p95_ms": 90.0,
            }
        },
    )
    assert_true(
        "reviewer-gated workflow runs are completing cleanly" in "\n".join(workflow_context),
        "expected workflow reliability contextualization for reviewer-gated starts",
    )

    actions = aq_report.build_structured_actions(
        {},
        route,
        cache,
        eval_trend,
        [],
        None,
        None,
        route_latency,
        {
            "available": True,
            "has_items": True,
            "dominant_hint_id": "registry_eval_scorecard_analysis",
            "dominant_share_pct": 100.0,
            "alternative_hints": [
                {"hint_id": "runtime_local_reasoning_tail", "count": 1},
            ],
        },
        {
            "available": True,
            "candidates": [
                {
                    "topic": "home-manager git credential helper conflict",
                    "occurrences": 4,
                    "strategy": "extract_pattern",
                    "reason": "operational_remediation_pattern_gap",
                    "estimated_effort": "low",
                    "requires_approval": False,
                },
            ],
        },
    )
    action_names = [item.get("action") for item in actions]
    assert_true("run_targeted_eval" in action_names, "expected targeted eval structured action")
    assert_true("tune_local_reasoning_lane" in action_names, "expected reasoning lane structured action")
    assert_true("rotate_hint_alternates" in action_names, "expected historical hint alternate structured action")
    assert_true("remediate_gap" in action_names, "expected gap remediation structured action")
    eval_action = next(item for item in actions if item.get("action") == "run_targeted_eval")
    assert_true(eval_action.get("script_args") == ["--full", "--strategy", "eval-regression-check"], "expected tagged eval script args")
    rotate_action = next(item for item in actions if item.get("action") == "rotate_hint_alternates")
    assert_true(rotate_action.get("alternate_hint_ids") == ["runtime_local_reasoning_tail"], "expected alternate hint ids in structured action")
    gap_action = next(item for item in actions if item.get("action") == "remediate_gap")
    assert_true(gap_action.get("type") == "gap_remediation", "expected gap remediation action type")
    assert_true(gap_action.get("strategy") == "extract_pattern", "expected classified gap remediation strategy")

    diversity = aq_report.hint_diversity(
        {
            "available": True,
            "total": 1,
            "unique_hints": 1,
            "dominant_hint_id": "registry_eval_scorecard_analysis",
            "dominant_share_pct": 100.0,
            "normalized_entropy_pct": 0.0,
            "effective_hints": 1.0,
        }
    )
    assert_true(diversity.get("status") == "low_sample", "expected low-sample hint diversity status")
    context = aq_report._hint_diversity_recent_context({"available": True, "window": "1h", "total_injections": 1, "status": "low_sample"})
    assert_true("low sample" in context.lower(), "expected low-sample hint diversity context")

    print("PASS: aq-report runtime recommendations and structured actions stay actionable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
