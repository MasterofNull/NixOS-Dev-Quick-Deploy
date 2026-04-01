#!/usr/bin/env python3
"""Regression checks for hint-runtime batching improvements."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from hints_engine import Hint, HintsEngine  # noqa: E402

AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
AQ_REPORT_SPEC = importlib.util.spec_from_loader(
    "aq_report_synthetic_gap_alignment",
    SourceFileLoader("aq_report_synthetic_gap_alignment", str(AQ_REPORT_PATH)),
)
if AQ_REPORT_SPEC is None or AQ_REPORT_SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
aq_report = importlib.util.module_from_spec(AQ_REPORT_SPEC)
AQ_REPORT_SPEC.loader.exec_module(aq_report)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_runtime_reasoning_tail_hint(tmpdir: Path) -> None:
    report_path = tmpdir / "latest-aq-report.json"
    report_path.write_text(
        json.dumps(
            {
                "route_search_latency_decomposition": {
                    "available": True,
                    "breakdown": [
                        {"label": "local_lane:reasoning", "calls": 9, "p95_ms": 15399.0},
                        {"label": "synthesis_type:reasoning", "calls": 12, "p95_ms": 14920.0},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    engine = HintsEngine(report_json_path=report_path)
    hints = engine._hints_from_latest_report("optimize local reasoning route_search latency", [])
    hint_ids = [item.id for item in hints]
    assert_true("runtime_local_reasoning_tail" in hint_ids, "expected local reasoning tail hint")


def test_runtime_eval_regression_hint(tmpdir: Path) -> None:
    report_path = tmpdir / "latest-aq-report.json"
    report_path.write_text(
        json.dumps(
            {
                "eval_trend": {
                    "available": True,
                    "latest_pct": 30.0,
                    "mean_pct": 40.0,
                    "n_runs": 2,
                    "source": "tool_audit",
                    "trend": "falling",
                }
            }
        ),
        encoding="utf-8",
    )
    engine = HintsEngine(report_json_path=report_path)
    hints = engine._hints_from_latest_report("investigate eval score regression and prompt quality", [])
    hint_ids = [item.id for item in hints]
    assert_true("runtime_eval_regression_watch" in hint_ids, "expected eval regression hint")


def test_historical_hint_watchlist_runtime_hint(tmpdir: Path) -> None:
    report_path = tmpdir / "latest-aq-report.json"
    report_path.write_text(
        json.dumps(
            {
                "historical_hint_watchlist": {
                    "available": True,
                    "has_items": True,
                    "dominant_hint_id": "registry_eval_scorecard_analysis",
                    "dominant_share_pct": 100.0,
                    "total_injections": 4,
                    "alternative_hints": [
                        {"hint_id": "runtime_local_reasoning_tail", "count": 1},
                        {"hint_id": "runtime_memory_recall_underused", "count": 1},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    engine = HintsEngine(report_json_path=report_path)
    hints = engine._hints_from_latest_report("improve hint quality and steering diversity", [])
    hint_ids = [item.id for item in hints]
    assert_true("runtime_historical_hint_concentration" in hint_ids, "expected historical hint concentration hint")


def test_feedback_profile_runtime_hints() -> None:
    engine = HintsEngine()
    hints = engine._hints_from_feedback_profiles(
        "improve hint quality and reuse the most helpful guidance",
        ["improve", "hint", "quality", "reuse"],
        {
            "runtime_local_reasoning_tail": {
                "signal": 0.62,
                "event_count": 6,
                "helpful_count": 5,
                "unhelpful_count": 1,
                "confidence": 0.81,
                "dominant_tags": ["actionable", "relevance_high"],
            },
            "registry_eval_scorecard_analysis": {
                "signal": -0.41,
                "event_count": 5,
                "helpful_count": 1,
                "unhelpful_count": 4,
                "confidence": 0.74,
                "dominant_tags": ["relevance_low", "helpful_false"],
            },
        },
    )
    hint_ids = [item.id for item in hints]
    assert_true(any(item.startswith("runtime_feedback_positive_") for item in hint_ids), "expected positive feedback-profile hint")
    assert_true(any(item.startswith("runtime_feedback_negative_") for item in hint_ids), "expected negative feedback-profile hint")


def test_diversity_prefers_non_overused_candidates() -> None:
    engine = HintsEngine()
    deduped = [
        Hint("dominant_runtime", "runtime_signal", "Dominant runtime", 0.95, "A", "A", ["runtime"], {}),
        Hint("alt_runtime", "runtime_signal", "Alt runtime", 0.90, "B", "B", ["runtime"], {}),
        Hint("gap_hint", "gap_topic", "Gap", 0.80, "C", "C", ["gap"], {}),
        Hint("workflow_hint", "workflow_rule", "Workflow", 0.79, "D", "D", ["workflow"], {}),
        Hint("coach_hint", "prompt_coaching", "Coach", 0.78, "E", "E", ["coaching"], {}),
    ]
    selected = engine._select_with_diversity_policy(deduped, max_hints=4, overused_ids={"dominant_runtime"})
    selected_ids = [item.id for item in selected]
    assert_true("alt_runtime" in selected_ids, "expected non-overused runtime hint to satisfy quota")
    assert_true("dominant_runtime" not in selected_ids, "expected dominant overused hint to rotate out when alternatives exist")


def test_synthetic_gap_alignment() -> None:
    samples = [
        "read and summarize docs/operations/CONTEXT-LIMIT-HANDLING.md",
        "summarize the file nix/modules/core/base.nix",
        "analyze file dashboard/backend/api/routes/firewall.py",
    ]
    for sample in samples:
        assert_true(aq_report._is_synthetic_gap(sample), f"expected aq-report synthetic gap suppression for {sample}")
        assert_true(HintsEngine.__module__ and __import__("hints_engine")._is_synthetic_gap(sample), f"expected hints synthetic gap suppression for {sample}")


def test_curated_stale_gap_alignment() -> None:
    samples = [
        "show me the workflow start intent contract requirements for this repo",
        "explain qdrant hybrid routing configuration in the ai harness",
        "what are the progressive disclosure token discipline defaults",
        "continue agent mode still says message exceeds context limit",
    ]
    hints_module = __import__("hints_engine")
    for sample in samples:
        assert_true(aq_report._is_curated_stale_gap(sample), f"expected aq-report curated stale-gap suppression for {sample}")
        assert_true(hints_module._is_curated_stale_gap(sample), f"expected hints curated stale-gap suppression for {sample}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hints-runtime-batch-") as tmpdir:
        test_runtime_reasoning_tail_hint(Path(tmpdir))
    with tempfile.TemporaryDirectory(prefix="hints-runtime-eval-") as tmpdir:
        test_runtime_eval_regression_hint(Path(tmpdir))
    with tempfile.TemporaryDirectory(prefix="hints-runtime-history-") as tmpdir:
        test_historical_hint_watchlist_runtime_hint(Path(tmpdir))
    test_feedback_profile_runtime_hints()
    test_diversity_prefers_non_overused_candidates()
    test_synthetic_gap_alignment()
    test_curated_stale_gap_alignment()
    print("PASS: hint-runtime batching improvements stay aligned and anti-dominant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
