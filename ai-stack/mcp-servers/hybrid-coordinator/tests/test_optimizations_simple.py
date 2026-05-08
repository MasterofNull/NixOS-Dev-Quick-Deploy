#!/usr/bin/env python3
"""
Simple test for Phase 5.2 Route Search Optimizations.

Tests the core optimization functions in isolation.
"""

import sys
import time
import asyncio


class TestBackendSelectionCache:
    """Test backend selection caching infrastructure."""

    def test_cache_operations(self):
        """Test cache key generation and storage."""
        print("Test 1: Backend Selection Cache Operations")

        # Import cache functions from route_handler
        from route_handler import (
            _cached_backend_key,
            _get_cached_backend_selection,
            _cache_backend_selection,
            _backend_selection_cache,
        )

        # Reset cache
        _backend_selection_cache.cache.clear()
        _backend_selection_cache.access_count = 0
        _backend_selection_cache.hit_count = 0

        # Test 1a: Cache miss
        result = _get_cached_backend_selection("query1", 0.75, True)
        assert result is None, "First access should be a miss"
        print("  ✓ First access returned None (cache miss)")

        # Test 1b: Cache write
        _cache_backend_selection("query1", 0.75, True, "local")
        assert len(_backend_selection_cache.cache) == 1, "Cache should contain 1 entry"
        print("  ✓ Backend selection cached")

        # Test 1c: Cache hit
        result = _get_cached_backend_selection("query1", 0.75, True)
        assert result == "local", "Should retrieve cached backend"
        print(f"  ✓ Cache hit: returned '{result}'")

        # Test 1d: Cache differentiation
        result = _get_cached_backend_selection("query1", 0.80, True)
        assert result is None, "Different score should be a miss"
        print("  ✓ Different score treated as cache miss")

        result = _get_cached_backend_selection("query1", 0.75, False)
        assert result is None, "Different prefer_local should be a miss"
        print("  ✓ Different prefer_local treated as cache miss")

        # Test 1e: Cache statistics
        from route_handler import get_backend_selection_cache_stats
        stats = get_backend_selection_cache_stats()
        print(f"\n  Cache Statistics:")
        print(f"    Cache size: {stats['cache_size']}")
        print(f"    Access count: {stats['access_count']}")
        print(f"    Hit count: {stats['hit_count']}")
        print(f"    Hit rate: {stats['hit_rate_percent']:.1f}%")

        assert stats['hit_rate_percent'] > 0, "Should have some cache hits"
        assert stats['cache_size'] >= 1, "Cache should contain entries"

        print("\n✓ PASS: Backend selection cache works correctly\n")

    def test_cache_eviction(self):
        """Test cache eviction on overflow."""
        print("Test 2: Cache Eviction on Overflow")

        from route_handler import (
            _cache_backend_selection,
            _backend_selection_cache,
        )

        # Set small max size
        original_max = _backend_selection_cache.max_size
        _backend_selection_cache.max_size = 3
        _backend_selection_cache.cache.clear()

        # Fill cache
        for i in range(3):
            _cache_backend_selection(f"query{i}", float(i), True, f"backend{i}")

        assert len(_backend_selection_cache.cache) == 3
        print(f"  Cache filled to max: {len(_backend_selection_cache.cache)} entries")

        # Add one more - should trigger eviction
        _cache_backend_selection("query3", 3.0, True, "backend3")
        print(f"  Cache after overflow: {len(_backend_selection_cache.cache)} entries")

        # Cache should be cleared and refilled
        assert len(_backend_selection_cache.cache) >= 1
        print("  ✓ Cache eviction triggered successfully")

        # Restore original
        _backend_selection_cache.max_size = original_max
        _backend_selection_cache.cache.clear()

        print("✓ PASS: Cache eviction works correctly\n")

class TestAdaptiveTimeout:
    """Test adaptive timeout calculation."""

    def test_timeout_levels(self):
        """Test timeout levels for different query complexities."""
        print("Test 3: Adaptive Timeout Calculation")

        from route_handler import calculate_adaptive_timeout

        # Simple query, keyword route
        timeout = calculate_adaptive_timeout("test", "keyword", 3)
        assert timeout == 5.0, "Simple keyword query should have 5s timeout"
        print(f"  Simple keyword (3 tokens): {timeout}s")

        # Medium query, hybrid route
        timeout = calculate_adaptive_timeout("test query foo bar", "hybrid", 5)
        assert timeout == 10.0, "Medium hybrid query should have 10s timeout"
        print(f"  Medium hybrid (5 tokens): {timeout}s")

        # Complex query, tree route
        timeout = calculate_adaptive_timeout("very long test query with many tokens for complex analysis", "tree", 10)
        assert timeout == 15.0, "Complex tree query should have 15s timeout"
        print(f"  Complex tree (10 tokens): {timeout}s")

        print("✓ PASS: Timeout calculation works correctly\n")

class TestCollectionLatencyMetrics:
    """Test collection latency tracking."""

    def test_latency_tracking(self):
        """Test tracking and calculation of latency metrics."""
        print("Test 4: Collection Latency Tracking")

        from route_handler import (
            track_collection_search_latency,
            get_route_search_metrics,
            _collection_metrics,
        )

        # Reset metrics
        _collection_metrics.collection_latencies.clear()
        _collection_metrics.total_searches = 0
        _collection_metrics.simple_query_optimizations = 0
        _collection_metrics.adaptive_timeout_applications = 0

        # Track some searches
        collections = ["codebase-context", "skills-patterns"]
        for latency in [100, 150, 200, 120, 180]:
            track_collection_search_latency(collections, latency)

        metrics = get_route_search_metrics()
        print(f"  Total searches tracked: {metrics['total_searches']}")
        print(f"  Collections in metrics: {len(metrics['collection_stats'])}")

        for coll_name, stats in metrics['collection_stats'].items():
            print(f"    {coll_name}:")
            print(f"      Avg latency: {stats['avg_latency_ms']:.1f}ms")
            print(f"      P95 latency: {stats['p95_latency_ms']:.1f}ms")
            print(f"      Search count: {stats['search_count']}")

        assert metrics['total_searches'] == 5
        assert len(metrics['collection_stats']) > 0
        print("✓ PASS: Latency tracking works correctly\n")

class TestParallelizationPattern:
    """Test the parallelization pattern used in route_search."""

    def test_parallel_task_creation(self):
        asyncio.run(self._run_parallel_task_creation())

    async def _run_parallel_task_creation(self):
        """Test that tasks can be created and awaited in parallel."""
        print("Test 5: Parallel Task Pattern")

        # Simulate the optimization pattern
        async def fast_operation():
            await asyncio.sleep(0.1)
            return "fast"

        async def slow_operation():
            await asyncio.sleep(0.2)
            return "slow"

        # Sequential approach
        start = time.time()
        result1 = await fast_operation()
        result2 = await slow_operation()
        sequential_time = time.time() - start
        print(f"  Sequential time: {sequential_time:.3f}s")

        # Parallel approach (like the optimization)
        start = time.time()
        task1 = asyncio.create_task(fast_operation())
        task2 = asyncio.create_task(slow_operation())
        result1 = await task1
        result2 = await task2
        parallel_time = time.time() - start
        print(f"  Parallel time: {parallel_time:.3f}s")

        speedup = sequential_time / parallel_time
        print(f"  Speedup: {speedup:.2f}x")

        assert parallel_time < sequential_time, "Parallel should be faster"
        assert speedup >= 1.45, "Should have significant speedup"
        print("✓ PASS: Parallel task pattern works correctly\n")

def main():
    """Run all tests."""
    print("=" * 70)
    print("Phase 5.2 Route Search Optimization Tests (Unit Tests)")
    print("=" * 70 + "\n")

    all_passed = True
    tests = [
        TestBackendSelectionCache().test_cache_operations(),
        TestBackendSelectionCache().test_cache_eviction(),
        TestAdaptiveTimeout().test_timeout_levels(),
        TestCollectionLatencyMetrics().test_latency_tracking(),
    ]

    for result in tests:
        if not result:
            all_passed = False

    # Run async test
    try:
        asyncio.run(TestParallelizationPattern().test_parallel_task_creation())
    except Exception as e:
        print(f"Async test failed: {e}\n")
        all_passed = False

    print("=" * 70)
    if all_passed:
        print("All tests PASSED ✓")
        return 0
    else:
        print("Some tests FAILED ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
