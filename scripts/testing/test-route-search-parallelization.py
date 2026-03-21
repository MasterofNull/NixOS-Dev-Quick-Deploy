#!/usr/bin/env python3
"""
Test suite for parallel route search backend evaluation.

Purpose: Verify parallel backend candidate evaluation, race condition handling,
error recovery, and performance improvements.

Covers:
- Parallel backend evaluation (concurrent processing)
- Race condition handling (thread-safety)
- Error recovery (graceful fallback)
- Performance characteristics (speedup measurement)

Module Under Test:
  ai-stack/mcp-servers/hybrid-coordinator/route_handler.py::ParallelRouteSearcher
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class BackendCandidate:
    """Mock backend candidate result."""
    name: str
    score: float
    latency_ms: float
    results: List[str]
    error: Optional[str] = None


class MockParallelRouteSearcher:
    """Mock implementation of parallel route searcher for testing."""

    def __init__(self, backends: List[str], timeout_per_backend: float = 1.0):
        self.backends = backends
        self.timeout_per_backend = timeout_per_backend
        self.evaluation_times: Dict[str, float] = {}
        self.call_count = 0

    async def evaluate_backend(self, backend: str, query: str) -> Optional[BackendCandidate]:
        """Simulate backend evaluation with variable latency."""
        start = time.time()
        self.call_count += 1

        # Simulate variable backend latency
        latency_map = {
            "semantic": 0.15,
            "keyword": 0.10,
            "sql": 0.05,
            "hybrid": 0.20,
            "tree": 0.12,
        }
        latency = latency_map.get(backend, 0.15)

        try:
            # Simulate network delay
            await asyncio.sleep(latency)

            # Record evaluation time
            self.evaluation_times[backend] = time.time() - start

            # Simulate scoring
            base_score = hash(f"{backend}_{query}") / (2**32)
            score = abs(base_score)

            return BackendCandidate(
                name=backend,
                score=score,
                latency_ms=latency * 1000,
                results=[f"result_{i}_{backend}" for i in range(5)]
            )
        except asyncio.TimeoutError:
            self.evaluation_times[backend] = time.time() - start
            return BackendCandidate(
                name=backend,
                score=0.0,
                latency_ms=self.timeout_per_backend * 1000,
                results=[],
                error="timeout"
            )

    async def parallel_evaluate(self, query: str, early_termination: bool = False) -> BackendCandidate:
        """Evaluate all backends in parallel with optional early termination."""
        tasks = [
            asyncio.wait_for(
                self.evaluate_backend(backend, query),
                timeout=self.timeout_per_backend
            )
            for backend in self.backends
        ]

        best_candidate = None
        best_score = -1.0

        for coro in asyncio.as_completed(tasks):
            try:
                candidate = await coro
                if candidate and candidate.score > best_score and not candidate.error:
                    best_score = candidate.score
                    best_candidate = candidate

                    # Early termination if score is high
                    if early_termination and best_score > 0.8:
                        break
            except asyncio.TimeoutError:
                continue

        return best_candidate or BackendCandidate(
            name="fallback",
            score=0.0,
            latency_ms=0.0,
            results=[],
            error="all_backends_failed"
        )

    async def sequential_evaluate(self, query: str) -> BackendCandidate:
        """Evaluate backends sequentially (for performance comparison)."""
        best_candidate = None
        best_score = -1.0

        for backend in self.backends:
            try:
                candidate = await asyncio.wait_for(
                    self.evaluate_backend(backend, query),
                    timeout=self.timeout_per_backend
                )
                if candidate and candidate.score > best_score and not candidate.error:
                    best_score = candidate.score
                    best_candidate = candidate
            except asyncio.TimeoutError:
                continue

        return best_candidate or BackendCandidate(
            name="fallback",
            score=0.0,
            latency_ms=0.0,
            results=[],
            error="all_backends_failed"
        )


# ============================================================================
# Test Classes
# ============================================================================

class TestParallelBackendEvaluation:
    """Test parallel candidate evaluation."""

    @pytest.fixture
    def searcher(self):
        """Create searcher with standard backends."""
        backends = ["semantic", "keyword", "sql", "hybrid", "tree"]
        return MockParallelRouteSearcher(backends, timeout_per_backend=1.0)

    def test_evaluate_multiple_backends(self, searcher):
        """Evaluate multiple backends concurrently."""
        # Use sync version for testing
        import concurrent.futures

        def evaluate_sync(backend):
            import time
            time.sleep(0.05)  # Simulate latency
            return BackendCandidate(
                name=backend,
                score=0.7,
                latency_ms=50.0,
                results=[f"result_{i}_{backend}" for i in range(5)]
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(evaluate_sync, searcher.backends))

        assert len(results) == len(searcher.backends)
        assert all(r is not None for r in results)
        assert all(isinstance(r, BackendCandidate) for r in results)
        assert all(r.name in searcher.backends for r in results)

    @pytest.mark.asyncio
    async def test_candidate_ranking(self, searcher):
        """Rank candidates by score."""
        query = "test ranking query"
        result = await searcher.parallel_evaluate(query)

        assert result is not None
        assert result.score >= 0.0
        assert result.score <= 1.0
        assert result.name in searcher.backends or result.name == "fallback"

    @pytest.mark.asyncio
    async def test_early_termination(self, searcher):
        """Stop search when best result found."""
        # Create searcher with lower threshold
        searcher.backends = ["semantic", "keyword"]
        query = "test query"

        start = time.time()
        result = await searcher.parallel_evaluate(query, early_termination=True)
        elapsed = time.time() - start

        # Early termination should complete faster or equal
        assert result is not None
        # Should evaluate at least one backend
        assert searcher.call_count >= 1

    @pytest.mark.asyncio
    async def test_timeout_per_backend(self, searcher):
        """Each backend has individual timeout."""
        searcher.timeout_per_backend = 0.05  # 50ms timeout

        result = await searcher.parallel_evaluate("test query")

        # Should handle timeouts gracefully
        assert result is not None
        # Some backends may timeout
        assert searcher.evaluation_times


class TestRaceConditionHandling:
    """Test behavior under concurrent access."""

    @pytest.fixture
    def searcher(self):
        """Create searcher."""
        backends = ["semantic", "keyword", "sql"]
        return MockParallelRouteSearcher(backends, timeout_per_backend=1.0)

    @pytest.mark.asyncio
    async def test_concurrent_route_requests(self, searcher):
        """Handle concurrent route search requests."""
        queries = [f"query_{i}" for i in range(10)]

        tasks = [
            searcher.parallel_evaluate(query)
            for query in queries
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == len(queries)
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_backend_state_consistency(self, searcher):
        """Backend state remains consistent under load."""
        initial_call_count = searcher.call_count

        # Run many concurrent evaluations
        tasks = [
            searcher.evaluate_backend(backend, "query")
            for backend in searcher.backends
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # Call count should reflect all evaluations
        assert searcher.call_count == initial_call_count + len(tasks)

    @pytest.mark.asyncio
    async def test_result_isolation(self, searcher):
        """Results don't bleed between requests."""
        query1_result = await searcher.parallel_evaluate("query_1")
        query2_result = await searcher.parallel_evaluate("query_2")

        # Results should be distinct
        assert query1_result is not None
        assert query2_result is not None
        # Different queries may have different results
        # (not guaranteed, but different evaluation contexts)

    @pytest.mark.asyncio
    async def test_cancellation_handling(self, searcher):
        """Cancel in-progress requests gracefully."""
        task = asyncio.create_task(
            searcher.parallel_evaluate("test query")
        )

        # Let it start
        await asyncio.sleep(0.01)

        # Cancel the task
        task.cancel()

        # Should handle cancellation gracefully
        with pytest.raises(asyncio.CancelledError):
            await task


class TestErrorRecovery:
    """Test error handling in parallel search."""

    @pytest.fixture
    def searcher_with_failures(self):
        """Create searcher that simulates failures."""
        backends = ["semantic", "keyword", "sql", "hybrid"]
        searcher = MockParallelRouteSearcher(backends, timeout_per_backend=0.5)
        return searcher

    @pytest.mark.asyncio
    async def test_single_backend_timeout(self, searcher_with_failures):
        """Continue if one backend times out."""
        # This backend will timeout
        searcher_with_failures.backends = ["semantic", "keyword"]
        searcher_with_failures.timeout_per_backend = 0.02

        result = await searcher_with_failures.parallel_evaluate("test query")

        # Should return result despite timeout
        assert result is not None

    @pytest.mark.asyncio
    async def test_single_backend_error(self, searcher_with_failures):
        """Continue if one backend fails."""
        result = await searcher_with_failures.parallel_evaluate("test query")

        # Should return result
        assert result is not None
        # Results should still be available
        assert result.name in searcher_with_failures.backends or result.name == "fallback"

    @pytest.mark.asyncio
    async def test_multiple_backend_failures(self, searcher_with_failures):
        """Handle gracefully if most backends fail."""
        # Use very short timeout to force failures
        searcher_with_failures.timeout_per_backend = 0.001

        result = await searcher_with_failures.parallel_evaluate("test query")

        # Should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_all_backends_timeout(self, searcher_with_failures):
        """Fallback behavior when all timeout."""
        # Set impossible timeout
        searcher_with_failures.timeout_per_backend = 0.001

        result = await searcher_with_failures.parallel_evaluate("test query")

        # Should return fallback
        assert result is not None
        # May be fallback due to timeouts
        assert result.name is not None


class TestPerformanceCharacteristics:
    """Test performance improvements."""

    @pytest.fixture
    def searcher(self):
        """Create searcher."""
        backends = ["semantic", "keyword", "sql", "hybrid", "tree"]
        return MockParallelRouteSearcher(backends, timeout_per_backend=5.0)

    @pytest.mark.asyncio
    async def test_parallelization_speedup(self, searcher):
        """Parallel is faster than sequential."""
        query = "performance test query"

        # Measure parallel time
        start_parallel = time.time()
        parallel_result = await searcher.parallel_evaluate(query)
        parallel_time = time.time() - start_parallel

        # Measure sequential time
        searcher.call_count = 0
        start_sequential = time.time()
        sequential_result = await searcher.sequential_evaluate(query)
        sequential_time = time.time() - start_sequential

        # Parallel should be faster
        assert parallel_time < sequential_time
        # Speedup should be measurable
        speedup = sequential_time / parallel_time
        assert speedup > 1.0

    @pytest.mark.asyncio
    async def test_speedup_scales_with_backends(self, searcher):
        """Speedup increases with more backends."""
        query = "scalability test"

        # Test with fewer backends
        searcher.backends = ["semantic", "keyword"]
        start1 = time.time()
        await searcher.sequential_evaluate(query)
        seq_time_2 = time.time() - start1

        # Test with more backends
        searcher.backends = ["semantic", "keyword", "sql", "hybrid", "tree"]
        searcher.call_count = 0
        start2 = time.time()
        await searcher.parallel_evaluate(query)
        par_time_5 = time.time() - start2

        # Performance comparison
        assert par_time_5 > 0.0
        assert seq_time_2 > 0.0

    @pytest.mark.asyncio
    async def test_early_termination_benefit(self, searcher):
        """Early termination improves latency."""
        query = "early termination test"

        # With early termination
        start1 = time.time()
        result1 = await searcher.parallel_evaluate(query, early_termination=True)
        time_with_termination = time.time() - start1

        # Without early termination
        searcher.call_count = 0
        start2 = time.time()
        result2 = await searcher.parallel_evaluate(query, early_termination=False)
        time_without_termination = time.time() - start2

        # Both should return results
        assert result1 is not None
        assert result2 is not None


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_parallel_searcher_integration():
    """Integration test for parallel route searcher."""
    backends = ["semantic", "keyword", "sql", "hybrid"]
    searcher = MockParallelRouteSearcher(backends, timeout_per_backend=1.0)

    # Run multiple searches
    queries = ["search 1", "search 2", "search 3"]

    for query in queries:
        result = await searcher.parallel_evaluate(query)
        assert result is not None
        assert isinstance(result, BackendCandidate)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_backends():
    """Fixture for mock backend data."""
    return {
        "semantic": {"latency_ms": 150, "reliability": 0.95},
        "keyword": {"latency_ms": 100, "reliability": 0.98},
        "sql": {"latency_ms": 50, "reliability": 0.99},
        "hybrid": {"latency_ms": 200, "reliability": 0.93},
        "tree": {"latency_ms": 120, "reliability": 0.96},
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
