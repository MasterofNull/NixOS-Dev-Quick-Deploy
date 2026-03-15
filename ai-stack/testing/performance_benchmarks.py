#!/usr/bin/env python3
"""
Performance Benchmarking Framework

Automated performance benchmarks for AI stack components.
Part of Phase 3 Batch 3.2: Automated Testing & Validation

Benchmarks:
- Hint query latency
- Delegation throughput
- Memory store operations
- Workflow execution
- API endpoint response times
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Single benchmark result"""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float
    metadata: Dict = field(default_factory=dict)


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark runs"""
    name: str
    baseline_avg_ms: float
    current_avg_ms: float
    change_pct: float
    is_regression: bool
    recommendation: str


class PerformanceBenchmark:
    """Performance benchmark runner"""

    def __init__(self, warmup_iterations: int = 10):
        self.warmup_iterations = warmup_iterations
        self.results: List[BenchmarkResult] = []

        logger.info(f"Performance Benchmark initialized (warmup={warmup_iterations})")

    async def benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        args: tuple = (),
        kwargs: dict = None,
    ) -> BenchmarkResult:
        """Run a benchmark"""
        kwargs = kwargs or {}

        logger.info(f"Benchmarking: {name} ({iterations} iterations)")

        # Warmup
        logger.info(f"  Warmup: {self.warmup_iterations} iterations...")
        for _ in range(self.warmup_iterations):
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

        # Actual benchmark
        logger.info(f"  Running benchmark...")
        times = []
        start_total = time.perf_counter()

        for _ in range(iterations):
            start = time.perf_counter()

            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

        end_total = time.perf_counter()
        total_time_ms = (end_total - start_total) * 1000

        # Calculate statistics
        times_sorted = sorted(times)

        def percentile(data, p):
            k = (len(data) - 1) * (p / 100)
            f = int(k)
            c = f + 1 if k != f else f
            if c >= len(data):
                return data[-1]
            return data[f] + (data[c] - data[f]) * (k - f)

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total_time_ms,
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=percentile(times_sorted, 50),
            p95_ms=percentile(times_sorted, 95),
            p99_ms=percentile(times_sorted, 99),
            throughput_per_sec=(iterations / total_time_ms) * 1000,
        )

        self.results.append(result)

        logger.info(f"  Results: avg={result.avg_time_ms:.2f}ms, p95={result.p95_ms:.2f}ms")

        return result

    def compare_with_baseline(
        self,
        baseline_path: Path,
        regression_threshold_pct: float = 10.0,
    ) -> List[BenchmarkComparison]:
        """Compare results with baseline"""
        if not baseline_path.exists():
            logger.warning(f"No baseline found at {baseline_path}")
            return []

        with open(baseline_path) as f:
            baseline_data = json.load(f)

        baseline_results = {r["name"]: r for r in baseline_data["results"]}
        comparisons = []

        for result in self.results:
            baseline = baseline_results.get(result.name)
            if not baseline:
                continue

            baseline_avg = baseline["avg_time_ms"]
            change_pct = ((result.avg_time_ms - baseline_avg) / baseline_avg) * 100
            is_regression = change_pct > regression_threshold_pct

            comparison = BenchmarkComparison(
                name=result.name,
                baseline_avg_ms=baseline_avg,
                current_avg_ms=result.avg_time_ms,
                change_pct=change_pct,
                is_regression=is_regression,
                recommendation=self._generate_comparison_recommendation(
                    result.name, change_pct, is_regression
                ),
            )

            comparisons.append(comparison)

        return comparisons

    def _generate_comparison_recommendation(
        self,
        name: str,
        change_pct: float,
        is_regression: bool,
    ) -> str:
        """Generate recommendation from comparison"""
        if is_regression:
            return f"{name} regressed by {change_pct:.1f}% - investigate and optimize"
        elif change_pct < -10:
            return f"{name} improved by {abs(change_pct):.1f}% - good!"
        else:
            return f"{name} performance stable ({change_pct:+.1f}%)"

    def export_results(self, output_path: Path):
        """Export benchmark results"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_benchmarks": len(self.results),
            "results": [
                {
                    "name": r.name,
                    "iterations": r.iterations,
                    "avg_time_ms": round(r.avg_time_ms, 3),
                    "min_time_ms": round(r.min_time_ms, 3),
                    "max_time_ms": round(r.max_time_ms, 3),
                    "p50_ms": round(r.p50_ms, 3),
                    "p95_ms": round(r.p95_ms, 3),
                    "p99_ms": round(r.p99_ms, 3),
                    "throughput_per_sec": round(r.throughput_per_sec, 2),
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Benchmark results exported: {output_path}")


# Example benchmarks
async def example_async_operation():
    """Example async operation to benchmark"""
    await asyncio.sleep(0.01)  # Simulate 10ms operation


def example_sync_operation():
    """Example sync operation to benchmark"""
    time.sleep(0.001)  # Simulate 1ms operation


async def benchmark_hint_system():
    """Benchmark hint system operations"""
    benchmark = PerformanceBenchmark(warmup_iterations=5)

    # Benchmark hint query
    await benchmark.benchmark(
        name="hint_query_simple",
        func=example_async_operation,  # Would be actual hint query
        iterations=50,
    )

    # Benchmark hint deduplication
    await benchmark.benchmark(
        name="hint_deduplication",
        func=example_sync_operation,  # Would be actual deduplication
        iterations=100,
    )

    return benchmark


async def benchmark_delegation_system():
    """Benchmark delegation system"""
    benchmark = PerformanceBenchmark(warmup_iterations=5)

    # Benchmark task delegation
    await benchmark.benchmark(
        name="delegate_task_simple",
        func=example_async_operation,
        iterations=20,
    )

    return benchmark


async def benchmark_memory_store():
    """Benchmark memory store operations"""
    benchmark = PerformanceBenchmark(warmup_iterations=10)

    # Benchmark store operation
    await benchmark.benchmark(
        name="memory_store_write",
        func=example_sync_operation,
        iterations=100,
    )

    # Benchmark retrieve operation
    await benchmark.benchmark(
        name="memory_store_read",
        func=example_sync_operation,
        iterations=100,
    )

    return benchmark


async def main():
    """Run performance benchmarks"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Performance Benchmarking Framework")
    logger.info("=" * 60)

    # Run all benchmarks
    benchmarks = []

    logger.info("\nHint System Benchmarks:")
    hint_bench = await benchmark_hint_system()
    benchmarks.append(hint_bench)

    logger.info("\nDelegation System Benchmarks:")
    delegation_bench = await benchmark_delegation_system()
    benchmarks.append(delegation_bench)

    logger.info("\nMemory Store Benchmarks:")
    memory_bench = await benchmark_memory_store()
    benchmarks.append(memory_bench)

    # Combine all results
    all_results = PerformanceBenchmark()
    for bench in benchmarks:
        all_results.results.extend(bench.results)

    # Export results
    results_path = Path(".agents/benchmarks/performance_results.json")
    all_results.export_results(results_path)

    # Compare with baseline if available
    baseline_path = Path(".agents/benchmarks/baseline.json")
    if baseline_path.exists():
        logger.info("\nComparing with baseline...")
        comparisons = all_results.compare_with_baseline(baseline_path)

        for comp in comparisons:
            status = "REGRESSION" if comp.is_regression else "OK"
            logger.info(
                f"  [{status}] {comp.name}: {comp.change_pct:+.1f}% "
                f"({comp.baseline_avg_ms:.2f}ms -> {comp.current_avg_ms:.2f}ms)"
            )
    else:
        logger.info("\nNo baseline found - this will be the new baseline")
        # Copy results to baseline
        import shutil
        shutil.copy(results_path, baseline_path)

    logger.info(f"\nResults: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
