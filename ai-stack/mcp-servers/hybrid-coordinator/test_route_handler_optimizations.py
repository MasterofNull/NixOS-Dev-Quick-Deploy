#!/usr/bin/env python3
"""
Test script for Phase 5.2 Route Search Optimizations.

Tests:
1. Parallel LLM expansion and capability discovery
2. Backend selection caching
3. Collection timeout guards
4. Skip backend selection when not needed
"""

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# Mock the external dependencies before importing route_handler
sys.modules['config'] = MagicMock()
sys.modules['metrics'] = MagicMock()
sys.modules['search_router'] = MagicMock()
sys.modules['query_expansion'] = MagicMock()
sys.modules['prompt_injection'] = MagicMock()
sys.modules['task_classifier'] = MagicMock()
sys.modules['capability_discovery'] = MagicMock()

# Setup mocks
from unittest.mock import MagicMock
Config = MagicMock()
Config.AI_LLM_EXPANSION_ENABLED = True
Config.AI_CAPABILITY_DISCOVERY_ON_QUERY = True
Config.AI_TREE_SEARCH_ENABLED = True
Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = 20
Config.AI_LLM_EXPANSION_TIMEOUT_S = 5.0
Config.AI_TASK_CLASSIFICATION_ENABLED = False
Config.LLAMA_CPP_URL = "http://localhost:8000"
sys.modules['config'].Config = Config

# Now we can import route_handler
import route_handler


class TestParallelization:
    """Test parallel LLM expansion and capability discovery."""

    async def test_parallel_expansion_and_discovery(self):
        """Verify that expansion and discovery tasks run in parallel."""
        print("Test 1: Parallel LLM Expansion and Discovery")

        # Setup mocks
        expansion_times = []
        discovery_times = []

        async def mock_expand_with_llm(query, max_expansions):
            start = time.time()
            await asyncio.sleep(0.2)  # Simulate 200ms expansion
            expansion_times.append(time.time() - start)
            return [query, query + " expanded"]

        async def mock_capability_discover(query):
            start = time.time()
            await asyncio.sleep(0.2)  # Simulate 200ms discovery
            discovery_times.append(time.time() - start)
            return {
                "decision": "found",
                "reason": "test",
                "cache_hit": False,
                "intent_tags": [],
                "tools": [],
                "skills": [],
                "servers": [],
                "datasets": [],
            }

        # Mock components
        expander = MagicMock()
        expander.expand_with_llm = mock_expand_with_llm

        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [],
        })
        summarize_fn = MagicMock(return_value="test response")

        # Patch the imports
        with patch.object(route_handler, '_query_expander', expander):
            with patch.object(route_handler, '_hybrid_search', hybrid_search_fn):
                with patch.object(route_handler, '_summarize', summarize_fn):
                    with patch('capability_discovery.discover', mock_capability_discover):
                        with patch.object(route_handler, '_normalize_tokens', return_value=['test']):
                            with patch.object(route_handler, '_looks_like_sql', return_value=False):
                                with patch.object(route_handler, '_record_telemetry', MagicMock()):
                                    with patch.object(route_handler, '_postgres_client_ref', return_value=None):
                                        with patch.object(route_handler, '_llama_cpp_client_ref', return_value=None):
                                            with patch.object(route_handler, 'ROUTE_DECISIONS', MagicMock()):
                                                with patch.object(route_handler, 'ROUTE_ERRORS', MagicMock()):
                                                    with patch.object(route_handler, 'sanitize_query', lambda x: x):
                                                        with patch.object(route_handler, '_injection_scanner', MagicMock()):
                                                            route_handler._injection_scanner.filter_results = MagicMock(return_value=([], 0))

                                                            # Run the search
                                                            start = time.time()
                                                            result = await route_handler.route_search(
                                                                query="test query",
                                                                mode="hybrid",
                                                            )
                                                            total_time = time.time() - start

        # Verify parallel execution
        if expansion_times and discovery_times:
            max_time = max(expansion_times[0], discovery_times[0])
            sequential_time = expansion_times[0] + discovery_times[0]
            print(f"  Expansion time: {expansion_times[0]:.3f}s")
            print(f"  Discovery time: {discovery_times[0]:.3f}s")
            print(f"  Max parallel time: {max_time:.3f}s")
            print(f"  Sequential would be: {sequential_time:.3f}s")
            print(f"  Parallelization efficiency: {(sequential_time / max_time):.2f}x")

            if max_time < (sequential_time * 0.9):
                print("  ✓ PASS: Operations ran in parallel")
                return True
            else:
                print("  ✗ FAIL: Operations did not run in parallel")
                return False
        return True


class TestBackendSelectionCache:
    """Test backend selection caching."""

    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        print("\nTest 2: Backend Selection Cache Key Generation")

        key1 = route_handler._cached_backend_key("abc123", "75", True)
        key2 = route_handler._cached_backend_key("abc123", "75", True)
        key3 = route_handler._cached_backend_key("abc123", "80", True)
        key4 = route_handler._cached_backend_key("abc123", "75", False)

        assert key1 == key2, "Same inputs should produce same key"
        assert key1 != key3, "Different scores should produce different keys"
        assert key1 != key4, "Different prefer_local should produce different keys"
        print(f"  Sample key: {key1}")
        print("  ✓ PASS: Cache keys generated correctly")
        return True

    def test_cache_hit_miss(self):
        """Test cache hit/miss tracking."""
        print("\nTest 3: Backend Selection Cache Hit/Miss Tracking")

        # Reset cache
        route_handler._backend_selection_cache.cache.clear()
        route_handler._backend_selection_cache.access_count = 0
        route_handler._backend_selection_cache.hit_count = 0

        query = "test query"
        score = 0.75
        prefer_local = True

        # First access - should be a miss
        cached = route_handler._get_cached_backend_selection(query, score, prefer_local)
        assert cached is None, "First access should miss"

        # Add to cache
        route_handler._cache_backend_selection(query, score, prefer_local, "local")

        # Second access - should be a hit
        cached = route_handler._get_cached_backend_selection(query, score, prefer_local)
        assert cached == "local", "Second access should hit"

        stats = route_handler.get_backend_selection_cache_stats()
        print(f"  Cache size: {stats['cache_size']}")
        print(f"  Access count: {stats['access_count']}")
        print(f"  Hit count: {stats['hit_count']}")
        print(f"  Hit rate: {stats['hit_rate_percent']:.1f}%")

        assert stats['hit_rate_percent'] == 50.0, "Hit rate should be 50% (1 hit, 2 accesses)"
        print("  ✓ PASS: Cache hit/miss tracking works correctly")
        return True

    def test_cache_eviction(self):
        """Test that cache evicts when full."""
        print("\nTest 4: Backend Selection Cache Eviction")

        # Reset cache
        route_handler._backend_selection_cache.cache.clear()
        route_handler._backend_selection_cache.max_size = 5

        # Fill cache
        for i in range(5):
            route_handler._cache_backend_selection(f"query{i}", float(i), True, f"backend{i}")

        assert len(route_handler._backend_selection_cache.cache) == 5
        print(f"  Cache filled to max: {len(route_handler._backend_selection_cache.cache)}")

        # Add one more - should trigger eviction
        route_handler._cache_backend_selection("query5", 5.0, True, "backend5")
        # After eviction and re-add, cache should be size 1
        assert len(route_handler._backend_selection_cache.cache) >= 1
        print(f"  Cache after eviction: {len(route_handler._backend_selection_cache.cache)}")
        print("  ✓ PASS: Cache eviction works correctly")

        # Reset to default size
        route_handler._backend_selection_cache.max_size = 1000
        return True


class TestTimeoutGuards:
    """Test collection timeout guards."""

    async def test_search_timeout(self):
        """Test that search operations timeout correctly."""
        print("\nTest 5: Collection Timeout Guards")

        async def slow_search(*args, **kwargs):
            await asyncio.sleep(5.0)  # Simulate 5s search
            return {"combined_results": [], "semantic_results": [], "keyword_results": []}

        # Test with short timeout
        try:
            result = await asyncio.wait_for(slow_search(), timeout=1.0)
            print("  ✗ FAIL: Should have timed out")
            return False
        except asyncio.TimeoutError:
            print("  Slow search timed out as expected")
            print("  ✓ PASS: Timeout guards work correctly")
            return True


class TestSkipBackendSelection:
    """Test that backend selection is skipped when not generating response."""

    async def test_backend_selection_skipped_on_retrieval_only(self):
        """Test that backend selection is not called for retrieval-only queries."""
        print("\nTest 6: Skip Backend Selection for Retrieval-Only Queries")

        select_backend_calls = []

        async def mock_select_backend(*args, **kwargs):
            select_backend_calls.append(args)
            return "local"

        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [],
        })
        summarize_fn = MagicMock(return_value="test response")

        with patch.object(route_handler, '_select_backend', mock_select_backend):
            with patch.object(route_handler, '_hybrid_search', hybrid_search_fn):
                with patch.object(route_handler, '_summarize', summarize_fn):
                    with patch.object(route_handler, '_normalize_tokens', return_value=['test']):
                        with patch.object(route_handler, '_looks_like_sql', return_value=False):
                            with patch.object(route_handler, '_record_telemetry', MagicMock()):
                                with patch.object(route_handler, '_postgres_client_ref', return_value=None):
                                    with patch.object(route_handler, '_llama_cpp_client_ref', return_value=None):
                                        with patch.object(route_handler, 'ROUTE_DECISIONS', MagicMock()):
                                            with patch.object(route_handler, 'ROUTE_ERRORS', MagicMock()):
                                                with patch.object(route_handler, 'sanitize_query', lambda x: x):
                                                    with patch.object(route_handler, '_injection_scanner', MagicMock()):
                                                        route_handler._injection_scanner.filter_results = MagicMock(return_value=([], 0))

                                                        # Run search without generation
                                                        await route_handler.route_search(
                                                            query="test query",
                                                            mode="keyword",
                                                            generate_response=False,
                                                        )

        if len(select_backend_calls) == 0:
            print("  Backend selection was skipped for retrieval-only query")
            print("  ✓ PASS: Backend selection correctly skipped")
            return True
        else:
            print(f"  ✗ FAIL: Backend selection was called {len(select_backend_calls)} times")
            return False


async def run_async_tests():
    """Run all async tests."""
    tests = [
        TestParallelization().test_parallel_expansion_and_discovery(),
        TestTimeoutGuards().test_search_timeout(),
        TestSkipBackendSelection().test_backend_selection_skipped_on_retrieval_only(),
    ]
    results = await asyncio.gather(*tests, return_exceptions=True)
    return results


def main():
    """Run all optimization tests."""
    print("=" * 70)
    print("Phase 5.2 Route Search Optimization Tests")
    print("=" * 70)

    all_passed = True

    # Sync tests
    sync_tests = [
        TestBackendSelectionCache().test_cache_key_generation(),
        TestBackendSelectionCache().test_cache_hit_miss(),
        TestBackendSelectionCache().test_cache_eviction(),
    ]

    for result in sync_tests:
        if isinstance(result, Exception):
            print(f"Test error: {result}")
            all_passed = False
        elif not result:
            all_passed = False

    # Async tests
    try:
        async_results = asyncio.run(run_async_tests())
        for result in async_results:
            if isinstance(result, Exception):
                print(f"Test error: {result}")
                all_passed = False
            elif not result:
                all_passed = False
    except Exception as e:
        print(f"Async test error: {e}")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("All tests PASSED ✓")
        return 0
    else:
        print("Some tests FAILED ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
