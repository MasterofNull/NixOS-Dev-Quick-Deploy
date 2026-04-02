#!/usr/bin/env python3
"""Focused regression checks for the agent quality profiler slice."""

from __future__ import annotations

import importlib.util
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "offloading" / "agent_quality_profiler.py"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_quality_profiler", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_quality_scorer_normalization(module) -> None:
    scorer = module.QualityScorer()
    assert_true(scorer.normalize_latency(80) == 1.0, "excellent latency should normalize to 1.0")
    assert_true(scorer.normalize_latency(5000) < 0.3, "very slow latency should normalize to a low score")
    assert_true(scorer.normalize_accuracy(0.97) == 1.0, "excellent accuracy should normalize to 1.0")
    assert_true(0.39 < scorer.normalize_accuracy(0.50) < 0.41, "0.50 accuracy should land in the poor band")


def test_trend_analysis_and_degradation_detection(module) -> None:
    analyzer = module.TrendAnalyzer(min_samples=4)
    now = datetime.now(timezone.utc)

    improving = [(now - timedelta(hours=4 - idx), score) for idx, score in enumerate([0.45, 0.50, 0.62, 0.71])]
    degrading = [(now - timedelta(hours=4 - idx), score) for idx, score in enumerate([0.82, 0.78, 0.63, 0.55])]
    volatile = [(now - timedelta(hours=4 - idx), score) for idx, score in enumerate([0.30, 0.88, 0.31, 0.86])]

    assert_true(
        analyzer.analyze_trend(improving, window_hours=8) == module.QualityTrend.IMPROVING,
        "trend analyzer should classify upward movement as improving",
    )
    assert_true(
        analyzer.analyze_trend(degrading, window_hours=8) == module.QualityTrend.DEGRADING,
        "trend analyzer should classify downward movement as degrading",
    )
    assert_true(
        analyzer.analyze_trend(volatile, window_hours=8) == module.QualityTrend.VOLATILE,
        "high-variance windows should be marked volatile",
    )
    assert_true(
        analyzer.detect_degradation(0.48, [0.70, 0.72, 0.74, 0.73], threshold=0.15),
        "degradation detection should fire when the current score falls materially below historical mean",
    )


def test_profiler_records_profiles_and_recommendations(module) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        profiler = module.AgentQualityProfiler(output_dir=Path(tmpdir), window_hours=48)

        for _ in range(8):
            profiler.record_request(
                agent_id="fast_stable",
                success=True,
                latency_ms=110,
                quality_score=0.94,
                agent_name="Fast Stable",
                tier="free",
            )
            profiler.record_request(
                agent_id="slower_ok",
                success=True,
                latency_ms=420,
                quality_score=0.72,
                agent_name="Slower OK",
                tier="free",
            )

        fast = profiler.get_profile("fast_stable")
        slower = profiler.get_profile("slower_ok")
        assert_true(fast is not None and slower is not None, "profiler should materialize profiles for recorded agents")
        assert_true(fast.overall_score > slower.overall_score, "higher-quality agent should have a stronger composite score")
        assert_true(fast.grade in (module.QualityGrade.GOOD, module.QualityGrade.EXCELLENT), "good agent should grade well")

        recommended = profiler.get_routing_recommendation(["fast_stable", "slower_ok"])
        assert_true(recommended == "fast_stable", "routing recommendation should prefer the stronger non-degrading agent")

        comparison = profiler.compare_agents(["fast_stable", "slower_ok"])
        assert_true(
            comparison["rankings"]["overall_score"][0] == "fast_stable",
            "overall ranking should place the stronger agent first",
        )
        assert_true(
            comparison["agents"]["fast_stable"]["grade"] in ("good", "excellent"),
            "comparison output should serialize grade values for operator-facing consumers",
        )

        saved = profiler.save_profiles()
        assert_true(saved.exists(), "profiler should persist profiles to disk")
        stats = profiler.get_stats()
        assert_true(stats["total_agents"] == 2, "stats should track total profiled agents")
        assert_true(stats["total_measurements"] == 48, "stats should count all recorded measurements")


def main() -> int:
    module = load_module()
    test_quality_scorer_normalization(module)
    test_trend_analysis_and_degradation_detection(module)
    test_profiler_records_profiles_and_recommendations(module)
    print("PASS: agent quality profiler primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
