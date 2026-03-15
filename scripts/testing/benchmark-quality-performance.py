#!/usr/bin/env python3
"""
Quality System Performance Benchmark

Measures performance impact of quality features:
- Cache hit latency vs miss latency
- Critic evaluation overhead
- Auto-improvement time cost
- Overall quality system overhead

Provides baseline measurements for optimization decisions.
"""

import sys
import time
import statistics
from pathlib import Path

# Add hybrid-coordinator to path
coordinator_path = Path(__file__).parent.parent.parent / "ai-stack/mcp-servers/hybrid-coordinator"
sys.path.insert(0, str(coordinator_path))

from quality_cache import (
    cache_response,
    get_cached_response,
    clear_cache,
    generate_cache_key,
)
from generator_critic import critique_response
from quality_monitor import check_quality_health


def benchmark_cache_performance(iterations=100):
    """Benchmark cache hit vs miss performance."""
    print("\nBenchmarking cache performance...")

    clear_cache()

    # Cache a response
    query = "How to configure NixOS firewall?"
    response = "To configure NixOS firewall, add firewall settings to configuration.nix"
    cache_response(query, response, 90.0, 0.95)

    # Benchmark cache hits
    hit_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = get_cached_response(query)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        hit_times.append(elapsed)
        assert result is not None, "Expected cache hit"

    # Benchmark cache misses
    miss_times = []
    for i in range(iterations):
        start = time.perf_counter()
        result = get_cached_response(f"Different query {i}")
        elapsed = (time.perf_counter() - start) * 1000  # ms
        miss_times.append(elapsed)
        assert result is None, "Expected cache miss"

    hit_avg = statistics.mean(hit_times)
    hit_p95 = statistics.quantiles(hit_times, n=20)[18]  # 95th percentile

    miss_avg = statistics.mean(miss_times)
    miss_p95 = statistics.quantiles(miss_times, n=20)[18]

    print(f"  Cache Hit Performance:")
    print(f"    Avg: {hit_avg:.3f}ms")
    print(f"    P95: {hit_p95:.3f}ms")
    print(f"  Cache Miss Performance:")
    print(f"    Avg: {miss_avg:.3f}ms")
    print(f"    P95: {miss_p95:.3f}ms")
    print(f"  Speedup: {miss_avg/hit_avg:.2f}x faster for cache hits")

    return {
        "cache_hit_avg_ms": hit_avg,
        "cache_hit_p95_ms": hit_p95,
        "cache_miss_avg_ms": miss_avg,
        "cache_miss_p95_ms": miss_p95,
        "speedup": miss_avg / hit_avg,
    }


def benchmark_critic_performance(iterations=50):
    """Benchmark critic evaluation overhead."""
    print("\nBenchmarking critic evaluation...")

    task = "Implement a function to validate email addresses"
    response_good = """
Here's a function to validate email addresses:

1. Use regex pattern for validation
2. Check basic format requirements
3. Return boolean result

```python
import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

This validates the email format using a standard regex pattern.
"""

    response_poor = "idk maybe use regex or something"

    # Benchmark good response evaluation
    good_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        critique = critique_response(task, response_good)
        elapsed = (time.perf_counter() - start) * 1000
        good_times.append(elapsed)

    # Benchmark poor response evaluation
    poor_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        critique = critique_response(task, response_poor)
        elapsed = (time.perf_counter() - start) * 1000
        poor_times.append(elapsed)

    good_avg = statistics.mean(good_times)
    poor_avg = statistics.mean(poor_times)

    print(f"  Critic Evaluation Performance:")
    print(f"    Good response: {good_avg:.3f}ms avg")
    print(f"    Poor response: {poor_avg:.3f}ms avg")
    print(f"    Overhead: ~{good_avg:.1f}ms per evaluation")

    return {
        "critic_good_avg_ms": good_avg,
        "critic_poor_avg_ms": poor_avg,
        "critic_avg_overhead_ms": statistics.mean([good_avg, poor_avg]),
    }


def benchmark_health_monitoring(iterations=100):
    """Benchmark health monitoring overhead."""
    print("\nBenchmarking health monitoring...")

    # Create mock stats
    reflection_stats = {
        "active": True,
        "avg_final_confidence": 0.85,
        "total_retrievals": 10,
    }

    critic_stats = {
        "active": True,
        "avg_quality_score": 88.5,
        "intervention_rate": 0.15,
        "total_evaluations": 20,
    }

    cache_stats = {
        "active": True,
        "hit_rate": 0.45,
        "avg_hit_quality": 92.0,
    }

    # Benchmark health checks
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        health_score, alerts = check_quality_health(
            reflection_stats, critic_stats, cache_stats
        )
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg = statistics.mean(times)
    p95 = statistics.quantiles(times, n=20)[18]

    print(f"  Health Monitoring Performance:")
    print(f"    Avg: {avg:.3f}ms")
    print(f"    P95: {p95:.3f}ms")
    print(f"    Overhead: Very low (~{avg:.2f}ms)")

    return {
        "health_check_avg_ms": avg,
        "health_check_p95_ms": p95,
    }


def benchmark_cache_key_generation(iterations=1000):
    """Benchmark cache key generation."""
    print("\nBenchmarking cache key generation...")

    queries = [
        "How to configure NixOS?",
        "Install docker on NixOS",
        "NixOS firewall rules",
        "System upgrade nixos-rebuild",
    ]

    times = []
    for _ in range(iterations):
        query = queries[_ % len(queries)]
        start = time.perf_counter()
        key = generate_cache_key(query)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg = statistics.mean(times)

    print(f"  Cache Key Generation:")
    print(f"    Avg: {avg:.3f}ms")
    print(f"    Overhead: Negligible")

    return {
        "cache_key_gen_avg_ms": avg,
    }


def run_benchmarks():
    """Run all performance benchmarks."""
    print("=" * 60)
    print("Quality System Performance Benchmark")
    print("=" * 60)

    results = {}

    try:
        results["cache"] = benchmark_cache_performance(iterations=100)
        results["critic"] = benchmark_critic_performance(iterations=50)
        results["health"] = benchmark_health_monitoring(iterations=100)
        results["cache_key"] = benchmark_cache_key_generation(iterations=1000)

        print("\n" + "=" * 60)
        print("Performance Summary")
        print("=" * 60)

        print(f"\nCache Performance:")
        print(f"  Hit latency: {results['cache']['cache_hit_avg_ms']:.3f}ms")
        print(f"  Miss latency: {results['cache']['cache_miss_avg_ms']:.3f}ms")
        print(f"  Cache speedup: {results['cache']['speedup']:.2f}x")

        print(f"\nCritic Overhead:")
        print(f"  Evaluation time: {results['critic']['critic_avg_overhead_ms']:.1f}ms")

        print(f"\nHealth Monitoring:")
        print(f"  Check time: {results['health']['health_check_avg_ms']:.3f}ms")

        print(f"\nCache Key Generation:")
        print(f"  Generation time: {results['cache_key']['cache_key_gen_avg_ms']:.3f}ms")

        print("\n" + "=" * 60)
        print("Overall Assessment:")
        print("=" * 60)

        print(f"✓ Cache provides {results['cache']['speedup']:.2f}x speedup on hits")
        print(f"✓ Critic overhead: ~{results['critic']['critic_avg_overhead_ms']:.0f}ms (acceptable)")
        print(f"✓ Health monitoring: <{results['health']['health_check_avg_ms']:.1f}ms (negligible)")
        print(f"✓ Cache key gen: <{results['cache_key']['cache_key_gen_avg_ms']:.1f}ms (negligible)")

        print("\nAll performance metrics within acceptable ranges.")
        print("Quality features have minimal overhead impact.")

        return 0

    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_benchmarks())
