#!/usr/bin/env python3
"""
Agent Quality Profiling

Comprehensive quality profiling for remote agents with trend analysis,
quality-based routing, and performance benchmarking.
Part of Phase 6 Batch 6.2: Free Agent Pool Management

Key Features:
- Multi-dimensional quality scoring (latency, accuracy, consistency)
- Quality trend analysis and decay detection
- Automatic quality-based routing recommendations
- Performance benchmarking across agents
- Quality alerts and degradation detection
- Historical quality tracking and comparison

Reference: Load balancer quality scoring, SLA monitoring
"""

import asyncio
import hashlib
import json
import logging
import os
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Runtime writable state
QUALITY_PROFILER_STATE = Path(os.getenv(
    "QUALITY_PROFILER_STATE",
    "/var/lib/ai-stack/hybrid/quality-profiler"
))


class QualityDimension(Enum):
    """Quality measurement dimensions"""
    LATENCY = "latency"  # Response time
    ACCURACY = "accuracy"  # Correctness of responses
    CONSISTENCY = "consistency"  # Stability of quality over time
    THROUGHPUT = "throughput"  # Requests per time unit
    AVAILABILITY = "availability"  # Uptime and responsiveness
    COST_EFFICIENCY = "cost_efficiency"  # Quality per dollar


class QualityTrend(Enum):
    """Quality trend direction"""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class QualityGrade(Enum):
    """Quality grade levels"""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 75-90%
    ACCEPTABLE = "acceptable"  # 60-75%
    POOR = "poor"  # 40-60%
    FAILING = "failing"  # <40%


@dataclass
class QualityMeasurement:
    """A single quality measurement"""
    timestamp: datetime
    dimension: QualityDimension
    value: float  # 0-1 normalized score
    raw_value: float  # Original measurement
    metadata: Dict = field(default_factory=dict)


@dataclass
class QualityWindow:
    """Quality measurements within a time window"""
    agent_id: str
    window_start: datetime
    window_end: datetime
    measurements: List[QualityMeasurement] = field(default_factory=list)

    def add(self, measurement: QualityMeasurement):
        self.measurements.append(measurement)

    def get_dimension_scores(self, dimension: QualityDimension) -> List[float]:
        return [m.value for m in self.measurements if m.dimension == dimension]

    def average(self, dimension: QualityDimension) -> float:
        scores = self.get_dimension_scores(dimension)
        return statistics.mean(scores) if scores else 0.5


@dataclass
class AgentQualityProfile:
    """Complete quality profile for an agent"""
    agent_id: str
    agent_name: str
    tier: str

    # Current scores (0-1)
    latency_score: float = 0.5
    accuracy_score: float = 0.5
    consistency_score: float = 0.5
    throughput_score: float = 0.5
    availability_score: float = 0.5
    cost_efficiency_score: float = 0.5

    # Composite score
    overall_score: float = 0.5
    grade: QualityGrade = QualityGrade.ACCEPTABLE

    # Trends
    overall_trend: QualityTrend = QualityTrend.UNKNOWN
    dimension_trends: Dict[str, QualityTrend] = field(default_factory=dict)

    # Statistics
    total_measurements: int = 0
    measurement_window_hours: int = 24
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # History
    score_history: List[Tuple[datetime, float]] = field(default_factory=list)


@dataclass
class QualityBenchmark:
    """Benchmark results comparing agents"""
    benchmark_id: str
    timestamp: datetime
    task_type: str
    agent_results: Dict[str, Dict] = field(default_factory=dict)
    winner: Optional[str] = None
    summary: str = ""


class QualityScorer:
    """Calculate quality scores from raw measurements"""

    # Normalization thresholds
    LATENCY_THRESHOLDS = {
        "excellent": 100,  # ms
        "good": 300,
        "acceptable": 1000,
        "poor": 3000,
    }

    ACCURACY_THRESHOLDS = {
        "excellent": 0.95,
        "good": 0.85,
        "acceptable": 0.70,
        "poor": 0.50,
    }

    def __init__(self):
        logger.info("Quality Scorer initialized")

    def normalize_latency(self, latency_ms: float) -> float:
        """Normalize latency to 0-1 score (lower latency = higher score)"""
        if latency_ms <= self.LATENCY_THRESHOLDS["excellent"]:
            return 1.0
        elif latency_ms <= self.LATENCY_THRESHOLDS["good"]:
            return 0.9 - 0.1 * (latency_ms - 100) / 200
        elif latency_ms <= self.LATENCY_THRESHOLDS["acceptable"]:
            return 0.75 - 0.15 * (latency_ms - 300) / 700
        elif latency_ms <= self.LATENCY_THRESHOLDS["poor"]:
            return 0.5 - 0.2 * (latency_ms - 1000) / 2000
        else:
            return max(0.1, 0.3 - 0.1 * (latency_ms - 3000) / 5000)

    def normalize_accuracy(self, accuracy: float) -> float:
        """Normalize accuracy to 0-1 score"""
        if accuracy >= self.ACCURACY_THRESHOLDS["excellent"]:
            return 1.0
        elif accuracy >= self.ACCURACY_THRESHOLDS["good"]:
            return 0.85 + 0.15 * (accuracy - 0.85) / 0.10
        elif accuracy >= self.ACCURACY_THRESHOLDS["acceptable"]:
            return 0.65 + 0.20 * (accuracy - 0.70) / 0.15
        elif accuracy >= self.ACCURACY_THRESHOLDS["poor"]:
            return 0.40 + 0.25 * (accuracy - 0.50) / 0.20
        else:
            return max(0.1, accuracy / 0.50 * 0.40)

    def calculate_consistency(self, scores: List[float]) -> float:
        """Calculate consistency from variance in scores"""
        if len(scores) < 3:
            return 0.5  # Unknown with few samples

        try:
            std_dev = statistics.stdev(scores)
            # Low variance = high consistency
            # std_dev of 0 = perfect consistency (1.0)
            # std_dev of 0.2 = acceptable consistency (0.6)
            # std_dev of 0.4+ = poor consistency (0.2)
            return max(0.1, 1.0 - std_dev * 2)
        except statistics.StatisticsError:
            return 0.5

    def calculate_composite(
        self,
        scores: Dict[QualityDimension, float],
        weights: Optional[Dict[QualityDimension, float]] = None,
    ) -> float:
        """Calculate weighted composite score"""
        default_weights = {
            QualityDimension.LATENCY: 0.20,
            QualityDimension.ACCURACY: 0.30,
            QualityDimension.CONSISTENCY: 0.15,
            QualityDimension.THROUGHPUT: 0.10,
            QualityDimension.AVAILABILITY: 0.15,
            QualityDimension.COST_EFFICIENCY: 0.10,
        }

        weights = weights or default_weights

        total_weight = 0
        weighted_sum = 0

        for dimension, score in scores.items():
            weight = weights.get(dimension, 0.1)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def get_grade(self, score: float) -> QualityGrade:
        """Convert score to grade"""
        if score >= 0.90:
            return QualityGrade.EXCELLENT
        elif score >= 0.75:
            return QualityGrade.GOOD
        elif score >= 0.60:
            return QualityGrade.ACCEPTABLE
        elif score >= 0.40:
            return QualityGrade.POOR
        else:
            return QualityGrade.FAILING


class TrendAnalyzer:
    """Analyze quality trends over time"""

    def __init__(self, min_samples: int = 5):
        self.min_samples = min_samples
        logger.info("Trend Analyzer initialized")

    def analyze_trend(
        self,
        scores: List[Tuple[datetime, float]],
        window_hours: int = 24,
    ) -> QualityTrend:
        """Analyze trend from timestamped scores"""
        if len(scores) < self.min_samples:
            return QualityTrend.UNKNOWN

        # Sort by time
        sorted_scores = sorted(scores, key=lambda x: x[0])

        # Get recent window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        recent = [s for t, s in sorted_scores if t >= cutoff]

        if len(recent) < self.min_samples:
            return QualityTrend.UNKNOWN

        # Split into halves
        mid = len(recent) // 2
        first_half = recent[:mid]
        second_half = recent[mid:]

        first_avg = statistics.mean(first_half) if first_half else 0.5
        second_avg = statistics.mean(second_half) if second_half else 0.5

        # Calculate variance
        try:
            variance = statistics.variance(recent)
        except statistics.StatisticsError:
            variance = 0

        # Determine trend
        diff = second_avg - first_avg

        if variance > 0.04:  # High variance
            return QualityTrend.VOLATILE

        if diff > 0.05:
            return QualityTrend.IMPROVING
        elif diff < -0.05:
            return QualityTrend.DEGRADING
        else:
            return QualityTrend.STABLE

    def detect_degradation(
        self,
        current_score: float,
        historical_scores: List[float],
        threshold: float = 0.15,
    ) -> bool:
        """Detect if quality has degraded significantly"""
        if len(historical_scores) < 3:
            return False

        historical_avg = statistics.mean(historical_scores[-20:])  # Last 20
        return current_score < historical_avg - threshold


class AgentQualityProfiler:
    """
    Main quality profiling orchestrator.

    Tracks quality metrics across agents, analyzes trends,
    and provides routing recommendations.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        window_hours: int = 24,
    ):
        self.output_dir = output_dir or QUALITY_PROFILER_STATE
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.window_hours = window_hours
        self.scorer = QualityScorer()
        self.trend_analyzer = TrendAnalyzer()

        # Agent profiles
        self.profiles: Dict[str, AgentQualityProfile] = {}

        # Measurement windows (agent_id -> window)
        self.windows: Dict[str, QualityWindow] = {}

        # Benchmarks
        self.benchmarks: List[QualityBenchmark] = []

        # Alerts
        self.alerts: deque = deque(maxlen=100)

        logger.info(f"Quality Profiler initialized: {self.output_dir}")

    def ensure_profile(self, agent_id: str, agent_name: str = "", tier: str = "") -> AgentQualityProfile:
        """Ensure profile exists for agent"""
        if agent_id not in self.profiles:
            self.profiles[agent_id] = AgentQualityProfile(
                agent_id=agent_id,
                agent_name=agent_name or agent_id,
                tier=tier,
            )
            self.windows[agent_id] = QualityWindow(
                agent_id=agent_id,
                window_start=datetime.now(timezone.utc),
                window_end=datetime.now(timezone.utc) + timedelta(hours=self.window_hours),
            )

        return self.profiles[agent_id]

    def record_measurement(
        self,
        agent_id: str,
        dimension: QualityDimension,
        raw_value: float,
        metadata: Optional[Dict] = None,
        agent_name: str = "",
        tier: str = "",
    ):
        """Record a quality measurement"""
        profile = self.ensure_profile(agent_id, agent_name, tier)

        # Normalize value
        if dimension == QualityDimension.LATENCY:
            normalized = self.scorer.normalize_latency(raw_value)
        elif dimension == QualityDimension.ACCURACY:
            normalized = self.scorer.normalize_accuracy(raw_value)
        else:
            normalized = max(0, min(1, raw_value))  # Assume pre-normalized

        measurement = QualityMeasurement(
            timestamp=datetime.now(timezone.utc),
            dimension=dimension,
            value=normalized,
            raw_value=raw_value,
            metadata=metadata or {},
        )

        # Add to window
        window = self.windows.get(agent_id)
        if window:
            window.add(measurement)

        # Update profile scores
        self._update_profile_scores(agent_id)

        logger.debug(
            f"Recorded {dimension.value} for {agent_id}: "
            f"{raw_value:.2f} -> {normalized:.3f}"
        )

    def record_request(
        self,
        agent_id: str,
        success: bool,
        latency_ms: float,
        quality_score: float,
        agent_name: str = "",
        tier: str = "",
    ):
        """Convenience method to record all metrics from a request"""
        self.record_measurement(
            agent_id=agent_id,
            dimension=QualityDimension.LATENCY,
            raw_value=latency_ms,
            agent_name=agent_name,
            tier=tier,
        )

        self.record_measurement(
            agent_id=agent_id,
            dimension=QualityDimension.ACCURACY,
            raw_value=quality_score if success else 0.0,
            agent_name=agent_name,
            tier=tier,
        )

        self.record_measurement(
            agent_id=agent_id,
            dimension=QualityDimension.AVAILABILITY,
            raw_value=1.0 if success else 0.0,
            agent_name=agent_name,
            tier=tier,
        )

    def _update_profile_scores(self, agent_id: str):
        """Update profile scores from measurements"""
        profile = self.profiles.get(agent_id)
        window = self.windows.get(agent_id)

        if not profile or not window:
            return

        # Update dimension scores
        profile.latency_score = window.average(QualityDimension.LATENCY)
        profile.accuracy_score = window.average(QualityDimension.ACCURACY)
        profile.availability_score = window.average(QualityDimension.AVAILABILITY)
        profile.throughput_score = window.average(QualityDimension.THROUGHPUT) or 0.5
        profile.cost_efficiency_score = window.average(QualityDimension.COST_EFFICIENCY) or 0.5

        # Calculate consistency
        accuracy_scores = window.get_dimension_scores(QualityDimension.ACCURACY)
        profile.consistency_score = self.scorer.calculate_consistency(accuracy_scores)

        # Calculate composite score
        scores = {
            QualityDimension.LATENCY: profile.latency_score,
            QualityDimension.ACCURACY: profile.accuracy_score,
            QualityDimension.CONSISTENCY: profile.consistency_score,
            QualityDimension.THROUGHPUT: profile.throughput_score,
            QualityDimension.AVAILABILITY: profile.availability_score,
            QualityDimension.COST_EFFICIENCY: profile.cost_efficiency_score,
        }

        profile.overall_score = self.scorer.calculate_composite(scores)
        profile.grade = self.scorer.get_grade(profile.overall_score)

        # Update history
        profile.score_history.append((datetime.now(timezone.utc), profile.overall_score))
        profile.score_history = profile.score_history[-200:]  # Keep last 200

        # Analyze trends
        profile.overall_trend = self.trend_analyzer.analyze_trend(
            profile.score_history,
            self.window_hours,
        )

        profile.total_measurements = len(window.measurements)
        profile.last_updated = datetime.now(timezone.utc)

        # Check for degradation
        historical = [s for _, s in profile.score_history[:-10]]
        if historical and self.trend_analyzer.detect_degradation(
            profile.overall_score,
            historical,
        ):
            self._create_alert(
                agent_id,
                "quality_degradation",
                f"Agent {agent_id} quality degraded: {profile.overall_score:.2f}",
            )

    def _create_alert(self, agent_id: str, alert_type: str, message: str):
        """Create quality alert"""
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "type": alert_type,
            "message": message,
        }
        self.alerts.append(alert)
        logger.warning(f"Quality alert: {message}")

    def get_profile(self, agent_id: str) -> Optional[AgentQualityProfile]:
        """Get agent quality profile"""
        return self.profiles.get(agent_id)

    def get_all_profiles(self) -> List[AgentQualityProfile]:
        """Get all agent profiles"""
        return list(self.profiles.values())

    def get_routing_recommendation(
        self,
        agent_ids: List[str],
        prefer_quality: bool = True,
        min_grade: QualityGrade = QualityGrade.ACCEPTABLE,
    ) -> Optional[str]:
        """Get routing recommendation based on quality"""
        candidates = []

        for agent_id in agent_ids:
            profile = self.profiles.get(agent_id)
            if not profile:
                continue

            # Filter by minimum grade
            grade_order = {
                QualityGrade.EXCELLENT: 5,
                QualityGrade.GOOD: 4,
                QualityGrade.ACCEPTABLE: 3,
                QualityGrade.POOR: 2,
                QualityGrade.FAILING: 1,
            }

            if grade_order[profile.grade] < grade_order[min_grade]:
                continue

            # Avoid degrading agents
            if profile.overall_trend == QualityTrend.DEGRADING:
                continue

            candidates.append((agent_id, profile))

        if not candidates:
            return None

        # Sort by quality
        if prefer_quality:
            candidates.sort(key=lambda x: x[1].overall_score, reverse=True)
        else:
            # Sort by consistency for stable workloads
            candidates.sort(key=lambda x: x[1].consistency_score, reverse=True)

        return candidates[0][0]

    def compare_agents(
        self,
        agent_ids: List[str],
    ) -> Dict[str, Any]:
        """Compare quality across agents"""
        comparison = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": {},
            "rankings": {},
        }

        profiles = [(aid, self.profiles.get(aid)) for aid in agent_ids]
        profiles = [(aid, p) for aid, p in profiles if p is not None]

        if not profiles:
            return comparison

        for agent_id, profile in profiles:
            comparison["agents"][agent_id] = {
                "name": profile.agent_name,
                "overall_score": profile.overall_score,
                "grade": profile.grade.value,
                "trend": profile.overall_trend.value,
                "latency": profile.latency_score,
                "accuracy": profile.accuracy_score,
                "consistency": profile.consistency_score,
                "availability": profile.availability_score,
            }

        # Rankings
        for dimension in ["overall_score", "latency", "accuracy", "consistency"]:
            ranked = sorted(
                profiles,
                key=lambda x: getattr(x[1], dimension.replace("_score", "_score") if "score" in dimension else f"{dimension}_score"),
                reverse=True,
            )
            comparison["rankings"][dimension] = [aid for aid, _ in ranked]

        return comparison

    async def run_benchmark(
        self,
        agent_ids: List[str],
        task_type: str,
        request_fn: Callable,
        num_requests: int = 10,
    ) -> QualityBenchmark:
        """Run quality benchmark across agents"""
        benchmark_id = hashlib.sha256(
            f"{task_type}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        logger.info(f"Running benchmark {benchmark_id} ({task_type})")

        benchmark = QualityBenchmark(
            benchmark_id=benchmark_id,
            timestamp=datetime.now(timezone.utc),
            task_type=task_type,
        )

        for agent_id in agent_ids:
            latencies = []
            successes = 0
            quality_scores = []

            for i in range(num_requests):
                try:
                    start = datetime.now()
                    result = await request_fn(agent_id)
                    latency = (datetime.now() - start).total_seconds() * 1000

                    latencies.append(latency)
                    if result.get("success", False):
                        successes += 1
                        quality_scores.append(result.get("quality", 0.5))

                except Exception as e:
                    logger.warning(f"Benchmark request failed: {e}")

            if latencies:
                benchmark.agent_results[agent_id] = {
                    "avg_latency_ms": statistics.mean(latencies),
                    "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies),
                    "success_rate": successes / num_requests,
                    "avg_quality": statistics.mean(quality_scores) if quality_scores else 0,
                    "num_requests": num_requests,
                }

        # Determine winner
        if benchmark.agent_results:
            winner = max(
                benchmark.agent_results.items(),
                key=lambda x: x[1].get("success_rate", 0) * x[1].get("avg_quality", 0),
            )
            benchmark.winner = winner[0]
            benchmark.summary = (
                f"Winner: {winner[0]} with {winner[1]['success_rate']:.1%} success, "
                f"{winner[1]['avg_latency_ms']:.0f}ms avg latency"
            )

        self.benchmarks.append(benchmark)
        logger.info(f"Benchmark complete: {benchmark.summary}")

        return benchmark

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent quality alerts"""
        return list(self.alerts)[-limit:]

    def save_profiles(self) -> Path:
        """Save profiles to disk"""
        output_path = self.output_dir / "quality_profiles.json"

        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "profiles": {},
        }

        for agent_id, profile in self.profiles.items():
            data["profiles"][agent_id] = {
                "agent_name": profile.agent_name,
                "tier": profile.tier,
                "overall_score": profile.overall_score,
                "grade": profile.grade.value,
                "trend": profile.overall_trend.value,
                "latency_score": profile.latency_score,
                "accuracy_score": profile.accuracy_score,
                "consistency_score": profile.consistency_score,
                "availability_score": profile.availability_score,
                "total_measurements": profile.total_measurements,
                "last_updated": profile.last_updated.isoformat(),
            }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(self.profiles)} profiles to {output_path}")
        return output_path

    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics"""
        grades = defaultdict(int)
        trends = defaultdict(int)

        for profile in self.profiles.values():
            grades[profile.grade.value] += 1
            trends[profile.overall_trend.value] += 1

        return {
            "total_agents": len(self.profiles),
            "total_measurements": sum(p.total_measurements for p in self.profiles.values()),
            "grade_distribution": dict(grades),
            "trend_distribution": dict(trends),
            "recent_alerts": len(self.alerts),
            "benchmarks_run": len(self.benchmarks),
        }


async def main():
    """Test quality profiler"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Agent Quality Profiler Test")
    logger.info("=" * 60)

    # Initialize profiler
    profiler = AgentQualityProfiler()

    # Simulate measurements for multiple agents
    agents = [
        ("agent_1", "Qwen 32B", "free"),
        ("agent_2", "Mistral 7B", "free"),
        ("agent_3", "GPT-3.5", "paid"),
    ]

    import random

    for agent_id, name, tier in agents:
        # Simulate varying quality levels
        base_quality = random.uniform(0.6, 0.95)
        base_latency = random.uniform(100, 500)

        for _ in range(20):
            # Add some variance
            latency = base_latency * random.uniform(0.8, 1.5)
            quality = base_quality * random.uniform(0.9, 1.1)
            success = random.random() < base_quality

            profiler.record_request(
                agent_id=agent_id,
                success=success,
                latency_ms=latency,
                quality_score=quality if success else 0.0,
                agent_name=name,
                tier=tier,
            )

    # Show profiles
    logger.info("\nAgent Quality Profiles:")
    for profile in profiler.get_all_profiles():
        logger.info(f"\n{profile.agent_name} ({profile.tier}):")
        logger.info(f"  Overall: {profile.overall_score:.3f} ({profile.grade.value})")
        logger.info(f"  Trend: {profile.overall_trend.value}")
        logger.info(f"  Latency: {profile.latency_score:.3f}")
        logger.info(f"  Accuracy: {profile.accuracy_score:.3f}")
        logger.info(f"  Consistency: {profile.consistency_score:.3f}")

    # Test routing recommendation
    logger.info("\nRouting Recommendation:")
    recommended = profiler.get_routing_recommendation(
        [a[0] for a in agents],
        prefer_quality=True,
    )
    logger.info(f"  Recommended agent: {recommended}")

    # Compare agents
    logger.info("\nAgent Comparison:")
    comparison = profiler.compare_agents([a[0] for a in agents])
    logger.info(f"  Rankings by overall: {comparison['rankings']['overall_score']}")
    logger.info(f"  Rankings by latency: {comparison['rankings']['latency']}")

    # Show stats
    stats = profiler.get_stats()
    logger.info(f"\nStats:")
    logger.info(f"  Total agents: {stats['total_agents']}")
    logger.info(f"  Total measurements: {stats['total_measurements']}")
    logger.info(f"  Grade distribution: {stats['grade_distribution']}")

    # Save profiles
    profiler.save_profiles()


if __name__ == "__main__":
    asyncio.run(main())
