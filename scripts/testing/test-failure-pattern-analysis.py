#!/usr/bin/env python3
"""Focused regression checks for failure pattern analysis primitives."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "capability-gap" / "failure_pattern_analysis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("failure_pattern_analysis", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_failure_categorization(module) -> None:
    categorizer = module.FailureCategorizer()
    assert_true(
        categorizer.categorize("ModuleNotFoundError: No module named torch", "ImportError") == module.FailureCategory.RESOURCE,
        "missing module errors should classify as resource failures",
    )
    assert_true(
        categorizer.categorize("Permission denied: /etc/hosts", "OSError") == module.FailureCategory.PERMISSION,
        "permission-denied errors should classify as permission failures",
    )
    assert_true(
        categorizer.categorize("Connection refused: localhost:5432", "NetworkError") == module.FailureCategory.NETWORK,
        "connection failures should classify as network failures",
    )


def test_feedback_analysis(module) -> None:
    analyzer = module.FeedbackAnalyzer()
    sentiment = analyzer.analyze_sentiment("I'm frustrated that the deployment keeps failing and nothing works.")
    issues = analyzer.extract_issues("Confused how to configure the database and missing documentation for Redis.")

    assert_true(sentiment == module.FeedbackSentiment.FRUSTRATED, "frustrated failure feedback should classify accordingly")
    assert_true(len(issues) >= 1, "feedback analyzer should extract issue phrases from operator feedback")


def test_pattern_discovery_and_gap_inference(module) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        analyzer = module.FailurePatternAnalyzer(output_dir=Path(tmpdir))

        repeated_failures = [
            ("ModuleNotFoundError: No module named torch", "ImportError", "Train model"),
            ("ModuleNotFoundError: No module named tensorflow", "ImportError", "Run inference"),
            ("command not found: nvidia-smi", "ShellError", "Check GPU"),
            ("Connection refused: localhost:5432", "NetworkError", "Connect to postgres"),
            ("Connection refused: localhost:6379", "NetworkError", "Connect to redis"),
            ("Connection refused: localhost:6333", "NetworkError", "Connect to qdrant"),
        ]

        for error_message, error_type, task_context in repeated_failures:
            analyzer.record_failure(error_message, error_type, task_context)

        analyzer.record_feedback("I'm frustrated that the database and GPU tools are still missing.")
        analyzer.record_feedback("Confused about the missing dependencies and service connection failures.")

        patterns = analyzer.discover_patterns()
        assert_true(len(patterns) >= 1, "pattern discovery should find repeated failure families")

        gaps = analyzer.infer_gaps()
        assert_true(len(gaps) >= 1, "gap inference should materialize remediable capability gaps")
        assert_true(
            any(gap.gap_type in {"tool", "knowledge"} for gap in gaps),
            "inferred gaps should classify likely tool or knowledge deficits",
        )
        assert_true(
            max(gap.priority_score for gap in gaps) > 0,
            "gap priority scoring should produce non-zero prioritization for active patterns",
        )

        report = analyzer.get_analysis_report()
        assert_true(report["summary"]["total_failures"] == len(repeated_failures), "analysis report should summarize recorded failures")
        assert_true(report["summary"]["gaps_identified"] == len(gaps), "analysis report should summarize inferred gaps")

        saved = analyzer.save_state()
        assert_true(saved.exists(), "analyzer should persist summarized state")
        stats = analyzer.get_stats()
        assert_true(stats["total_failures"] == len(repeated_failures), "stats should count all recorded failures")
        assert_true(stats["gaps_inferred"] == len(gaps), "stats should count inferred gaps")


def main() -> int:
    module = load_module()
    test_failure_categorization(module)
    test_feedback_analysis(module)
    test_pattern_discovery_and_gap_inference(module)
    print("PASS: failure pattern analysis primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
