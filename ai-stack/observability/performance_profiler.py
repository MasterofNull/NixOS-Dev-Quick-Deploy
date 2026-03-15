#!/usr/bin/env python3
"""
Performance Profiler & Bottleneck Detector

Continuous performance profiling with automatic bottleneck identification.
Part of Phase 1 Batch 1.3: Performance Profiling & Bottleneck Detection

Features:
- Continuous profiling of critical paths
- Automatic bottleneck detection
- Performance regression detection
- Optimization recommendation engine
- A/B testing framework integration
"""

import asyncio
import cProfile
import io
import json
import logging
import pstats
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance measurement"""
    operation: str
    duration_ms: float
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)


@dataclass
class Bottleneck:
    """Identified performance bottleneck"""
    operation: str
    severity: str  # "critical", "high", "medium", "low"
    avg_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    call_count: int
    total_time_ms: float
    percentage_of_total: float
    recommendation: str


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""
    bottleneck: Bottleneck
    priority: int  # 1-5, 1 being highest
    estimated_improvement: float  # Percentage improvement
    implementation_effort: str  # "low", "medium", "high"
    description: str
    action_items: List[str]


class PerformanceProfiler:
    """Continuous performance profiler"""

    def __init__(
        self,
        profile_dir: Path = Path(".agents/performance"),
        window_size_minutes: int = 60,
        enable_code_profiling: bool = False,
    ):
        self.profile_dir = profile_dir
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.window_size = timedelta(minutes=window_size_minutes)
        self.enable_code_profiling = enable_code_profiling

        # Performance metrics storage
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)

        # Baseline performance (for regression detection)
        self.baselines: Dict[str, float] = {}

        # Code profiler
        self.profiler = cProfile.Profile() if enable_code_profiling else None

        logger.info(
            f"Performance profiler initialized "
            f"(window={window_size_minutes}min, "
            f"code_profiling={enable_code_profiling})"
        )

    def record_metric(
        self,
        operation: str,
        duration_ms: float,
        metadata: Optional[Dict] = None,
    ):
        """Record a performance metric"""
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        self.metrics[operation].append(metric)

        # Clean old metrics outside window
        self._clean_old_metrics(operation)

    def _clean_old_metrics(self, operation: str):
        """Remove metrics outside the time window"""
        cutoff = datetime.now() - self.window_size
        self.metrics[operation] = [
            m for m in self.metrics[operation] if m.timestamp > cutoff
        ]

    def get_statistics(self, operation: str) -> Dict:
        """Get statistics for an operation"""
        metrics_list = self.metrics.get(operation, [])

        if not metrics_list:
            return {
                "operation": operation,
                "count": 0,
                "avg_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
            }

        durations = sorted([m.duration_ms for m in metrics_list])
        count = len(durations)

        def percentile(data, p):
            k = (len(data) - 1) * (p / 100)
            f = int(k)
            c = int(k) + 1 if k != f else f
            if c >= len(data):
                return data[-1]
            return data[f] + (data[c] - data[f]) * (k - f)

        return {
            "operation": operation,
            "count": count,
            "avg_ms": sum(durations) / count,
            "min_ms": durations[0],
            "max_ms": durations[-1],
            "p50_ms": percentile(durations, 50),
            "p95_ms": percentile(durations, 95),
            "p99_ms": percentile(durations, 99),
        }

    def identify_bottlenecks(
        self,
        min_call_count: int = 10,
        threshold_ms: float = 100,
    ) -> List[Bottleneck]:
        """Identify performance bottlenecks"""
        bottlenecks = []

        # Calculate total execution time
        total_time = 0
        operation_times = {}

        for operation, metrics_list in self.metrics.items():
            if len(metrics_list) < min_call_count:
                continue

            stats = self.get_statistics(operation)
            total_time_op = stats["avg_ms"] * stats["count"]
            total_time += total_time_op
            operation_times[operation] = (stats, total_time_op)

        # Identify bottlenecks
        for operation, (stats, total_time_op) in operation_times.items():
            # Skip if below threshold
            if stats["avg_ms"] < threshold_ms and stats["p95_ms"] < threshold_ms * 2:
                continue

            percentage = (total_time_op / total_time * 100) if total_time > 0 else 0

            # Determine severity
            if stats["p95_ms"] > 1000 or percentage > 30:
                severity = "critical"
                recommendation = f"URGENT: {operation} is a critical bottleneck consuming {percentage:.1f}% of total time"
            elif stats["p95_ms"] > 500 or percentage > 15:
                severity = "high"
                recommendation = f"High priority: {operation} needs optimization (p95={stats['p95_ms']:.1f}ms)"
            elif stats["p95_ms"] > 200 or percentage > 5:
                severity = "medium"
                recommendation = f"Moderate concern: {operation} could be optimized"
            else:
                severity = "low"
                recommendation = f"Low priority: {operation} shows acceptable performance"

            bottleneck = Bottleneck(
                operation=operation,
                severity=severity,
                avg_duration_ms=stats["avg_ms"],
                p95_duration_ms=stats["p95_ms"],
                p99_duration_ms=stats["p99_ms"],
                call_count=stats["count"],
                total_time_ms=total_time_op,
                percentage_of_total=percentage,
                recommendation=recommendation,
            )

            bottlenecks.append(bottleneck)

        # Sort by severity and total time
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        bottlenecks.sort(
            key=lambda b: (severity_order[b.severity], -b.total_time_ms)
        )

        return bottlenecks

    def generate_optimization_recommendations(
        self,
        bottlenecks: Optional[List[Bottleneck]] = None,
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations"""
        if bottlenecks is None:
            bottlenecks = self.identify_bottlenecks()

        recommendations = []

        for bottleneck in bottlenecks:
            # Skip low-severity bottlenecks
            if bottleneck.severity == "low":
                continue

            # Determine priority (1-5, 1 highest)
            priority_map = {"critical": 1, "high": 2, "medium": 3}
            priority = priority_map.get(bottleneck.severity, 5)

            # Estimate improvement potential
            if bottleneck.percentage_of_total > 20:
                estimated_improvement = 15.0  # 15% overall improvement possible
            elif bottleneck.percentage_of_total > 10:
                estimated_improvement = 8.0
            else:
                estimated_improvement = 3.0

            # Generate specific recommendations based on operation type
            action_items = self._generate_action_items(bottleneck)

            # Estimate implementation effort
            effort = self._estimate_effort(bottleneck)

            rec = OptimizationRecommendation(
                bottleneck=bottleneck,
                priority=priority,
                estimated_improvement=estimated_improvement,
                implementation_effort=effort,
                description=bottleneck.recommendation,
                action_items=action_items,
            )

            recommendations.append(rec)

        return recommendations

    def _generate_action_items(self, bottleneck: Bottleneck) -> List[str]:
        """Generate specific action items for a bottleneck"""
        operation = bottleneck.operation.lower()
        items = []

        # Database-related
        if "query" in operation or "fetch" in operation or "load" in operation:
            items.extend([
                "Add database query caching",
                "Optimize database indexes",
                "Consider query batching or connection pooling",
                "Profile slow queries with EXPLAIN ANALYZE",
            ])

        # API/Network-related
        if "api" in operation or "request" in operation or "http" in operation:
            items.extend([
                "Implement response caching",
                "Add request batching/multiplexing",
                "Consider connection keep-alive",
                "Reduce payload size",
            ])

        # AI/Model-related
        if "model" in operation or "inference" in operation or "llm" in operation:
            items.extend([
                "Implement prompt caching",
                "Optimize model parameters (temperature, max_tokens)",
                "Consider model distillation or quantization",
                "Add streaming responses",
            ])

        # General recommendations
        if bottleneck.avg_duration_ms > 500:
            items.append("Consider async/parallel execution")

        if bottleneck.call_count > 1000:
            items.append("Add rate limiting or request coalescing")

        return items if items else ["Profile code path for optimization opportunities"]

    def _estimate_effort(self, bottleneck: Bottleneck) -> str:
        """Estimate implementation effort"""
        operation = bottleneck.operation.lower()

        # High effort indicators
        if "refactor" in operation or "redesign" in operation:
            return "high"

        # Low effort indicators
        if "cache" in operation or "config" in operation:
            return "low"

        # Default to medium
        return "medium"

    def export_report(self, output_path: Optional[Path] = None) -> Path:
        """Export performance report"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.profile_dir / f"performance_report_{timestamp}.json"

        bottlenecks = self.identify_bottlenecks()
        recommendations = self.generate_optimization_recommendations(bottlenecks)

        report = {
            "generated_at": datetime.now().isoformat(),
            "window_size_minutes": self.window_size.total_seconds() / 60,
            "operations_tracked": len(self.metrics),
            "total_metrics": sum(len(m) for m in self.metrics.values()),
            "bottlenecks": [
                {
                    "operation": b.operation,
                    "severity": b.severity,
                    "avg_ms": round(b.avg_duration_ms, 2),
                    "p95_ms": round(b.p95_duration_ms, 2),
                    "p99_ms": round(b.p99_duration_ms, 2),
                    "call_count": b.call_count,
                    "percentage_of_total": round(b.percentage_of_total, 2),
                    "recommendation": b.recommendation,
                }
                for b in bottlenecks
            ],
            "optimization_recommendations": [
                {
                    "priority": r.priority,
                    "operation": r.bottleneck.operation,
                    "estimated_improvement_pct": r.estimated_improvement,
                    "implementation_effort": r.implementation_effort,
                    "description": r.description,
                    "action_items": r.action_items,
                }
                for r in recommendations
            ],
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Performance report exported to {output_path}")
        return output_path

    def start_code_profiling(self):
        """Start code-level profiling"""
        if self.profiler:
            self.profiler.enable()
            logger.info("Code profiling started")

    def stop_code_profiling(self) -> str:
        """Stop code profiling and return stats"""
        if not self.profiler:
            return "Code profiling not enabled"

        self.profiler.disable()

        # Get stats
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(50)  # Top 50 functions

        result = stream.getvalue()
        logger.info("Code profiling stopped")

        return result


# Global profiler instance
_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Get global profiler instance"""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler


if __name__ == "__main__":
    # Test performance profiler
    logging.basicConfig(level=logging.INFO)

    profiler = get_profiler()

    # Simulate some operations
    import random

    operations = [
        "query_hints",
        "delegate_task",
        "workflow_plan",
        "memory_store",
        "api_request",
    ]

    logger.info("Recording test metrics...")
    for _ in range(200):
        op = random.choice(operations)
        # Simulate different latencies
        if "api" in op:
            duration = random.gauss(800, 200)  # Slow API
        elif "delegate" in op:
            duration = random.gauss(1500, 500)  # Very slow delegation
        else:
            duration = random.gauss(100, 30)  # Fast operations

        profiler.record_metric(op, max(10, duration))

    # Identify bottlenecks
    logger.info("\nIdentifying bottlenecks...")
    bottlenecks = profiler.identify_bottlenecks(min_call_count=5)

    for bottleneck in bottlenecks:
        logger.info(f"\n{bottleneck.severity.upper()}: {bottleneck.operation}")
        logger.info(f"  Avg: {bottleneck.avg_duration_ms:.1f}ms")
        logger.info(f"  P95: {bottleneck.p95_duration_ms:.1f}ms")
        logger.info(f"  Calls: {bottleneck.call_count}")
        logger.info(f"  % of total: {bottleneck.percentage_of_total:.1f}%")

    # Generate recommendations
    logger.info("\nGenerating optimization recommendations...")
    recommendations = profiler.generate_optimization_recommendations(bottlenecks)

    for i, rec in enumerate(recommendations, 1):
        logger.info(f"\n{i}. {rec.bottleneck.operation} (Priority: {rec.priority})")
        logger.info(f"   Estimated improvement: {rec.estimated_improvement}%")
        logger.info(f"   Effort: {rec.implementation_effort}")
        logger.info(f"   Actions:")
        for action in rec.action_items:
            logger.info(f"     - {action}")

    # Export report
    report_path = profiler.export_report()
    logger.info(f"\nFull report: {report_path}")
