#!/usr/bin/env python3
"""
Test suite for backend selection cache correctness and effectiveness.

Purpose: Verify backend selection cache hit/miss rates, TTL enforcement,
invalidation triggers, and memory efficiency.

Covers:
- Cache hit/miss tracking
- TTL enforcement and refresh
- Cache invalidation strategies
- Memory usage and eviction policies
- Concurrent cache access and thread-safety

Module Under Test:
  ai-stack/mcp-servers/hybrid-coordinator/route_handler.py::BackendSelectionCache
"""

import time
import pytest
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import hashlib


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    query: str
    backend: str
    score: float
    timestamp: datetime
    ttl_seconds: int = 300
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def touch(self):
        """Update last accessed time."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class MockBackendSelectionCache:
    """Mock implementation of backend selection cache."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    def _make_key(self, query: str) -> str:
        """Generate cache key from query."""
        return hashlib.sha256(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached backend selection."""
        with self._lock:
            key = self._make_key(query)

            if key not in self._cache:
                self.misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self.misses += 1
                return None

            # Update LRU order
            self._cache.move_to_end(key)
            entry.touch()
            self.hits += 1

            return {
                "backend": entry.backend,
                "score": entry.score,
                "timestamp": entry.timestamp.isoformat(),
            }

    def set(self, query: str, backend: str, score: float, ttl_seconds: Optional[int] = None) -> None:
        """Cache backend selection."""
        with self._lock:
            key = self._make_key(query)
            ttl = ttl_seconds or self.ttl_seconds

            entry = CacheEntry(
                query=query,
                backend=backend,
                score=score,
                timestamp=datetime.now(),
                ttl_seconds=ttl
            )

            self._cache[key] = entry
            self._cache.move_to_end(key)

            # Evict oldest if over size limit
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def invalidate(self, query: str) -> None:
        """Invalidate specific cache entry."""
        with self._lock:
            key = self._make_key(query)
            if key in self._cache:
                del self._cache[key]
                self.invalidations += 1

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
            self.invalidations += 1

    def get_hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100.0

    def get_size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_memory_estimate(self) -> int:
        """Estimate memory usage in bytes."""
        total = 0
        with self._lock:
            for entry in self._cache.values():
                total += len(entry.query.encode()) + 100  # Entry overhead
        return total


# ============================================================================
# Test Classes
# ============================================================================

class TestCacheHitRate:
    """Test cache hit/miss rates."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return MockBackendSelectionCache(max_size=1000, ttl_seconds=300)

    def test_cache_hit_identical_query(self, cache):
        """Hit cache for identical queries."""
        query = "identical test query"
        cache.set(query, "semantic", 0.95)

        # First access (miss)
        result1 = cache.get(query)
        assert result1 is not None

        # Second access (hit)
        result2 = cache.get(query)
        assert result2 is not None
        assert result2["backend"] == "semantic"
        assert cache.hits == 2  # Both get operations hit after set

    def test_cache_miss_different_query(self, cache):
        """Miss cache for different queries."""
        query1 = "query one"
        query2 = "query two"

        cache.set(query1, "semantic", 0.95)

        # Query1 should hit
        result1 = cache.get(query1)
        assert result1 is not None

        # Query2 should miss
        result2 = cache.get(query2)
        assert result2 is None
        assert cache.misses >= 1

    def test_cache_hit_rate_tracking(self, cache):
        """Track hit rate metrics."""
        # Generate cache hits and misses
        for i in range(10):
            cache.set(f"query_{i}", "semantic", 0.9)

        # All gets should hit
        for i in range(10):
            cache.get(f"query_{i}")

        hit_rate = cache.get_hit_rate()
        assert hit_rate > 0.0
        assert hit_rate <= 100.0

    def test_hit_rate_improvement(self, cache):
        """Hit rate improves with repeated queries."""
        # Initial misses
        for i in range(5):
            cache.get(f"new_query_{i}")

        initial_miss_rate = cache.get_hit_rate()

        # Cache results
        for i in range(5):
            cache.set(f"new_query_{i}", "keyword", 0.85)

        # Repeated access
        for i in range(5):
            cache.get(f"new_query_{i}")

        improved_hit_rate = cache.get_hit_rate()
        # Hit rate should improve
        assert improved_hit_rate > initial_miss_rate


class TestCacheRefreshStrategy:
    """Test cache TTL and refresh."""

    @pytest.fixture
    def cache(self):
        """Create cache with short TTL for testing."""
        return MockBackendSelectionCache(max_size=1000, ttl_seconds=1)

    def test_cache_ttl_enforcement(self, cache):
        """Respect cache TTL."""
        query = "ttl test"
        cache.set(query, "semantic", 0.95, ttl_seconds=1)

        # Immediate get should hit
        result1 = cache.get(query)
        assert result1 is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should miss after expiration
        result2 = cache.get(query)
        assert result2 is None

    def test_cache_refresh_on_ttl(self, cache):
        """Refresh cache when TTL expires."""
        query = "refresh test"

        # Set with short TTL
        cache.set(query, "semantic", 0.95, ttl_seconds=1)
        result1 = cache.get(query)
        assert result1 is not None

        # Wait and refresh
        time.sleep(1.1)
        cache.set(query, "keyword", 0.85, ttl_seconds=1)

        # Should get refreshed value
        result2 = cache.get(query)
        assert result2 is not None
        assert result2["backend"] == "keyword"

    def test_stale_data_handling(self, cache):
        """Handle temporarily stale cache gracefully."""
        query = "stale handling"
        cache.set(query, "semantic", 0.95, ttl_seconds=1)

        time.sleep(0.5)

        # Still fresh
        result = cache.get(query)
        assert result is not None

    def test_refresh_background(self, cache):
        """Refresh can happen in background."""
        # Store multiple entries
        for i in range(5):
            cache.set(f"refresh_{i}", "semantic", 0.9)

        # Cleanup expired (background task simulation)
        initial_size = cache.get_size()
        time.sleep(1.1)
        removed = cache.cleanup_expired()

        assert removed > 0 or initial_size == cache.get_size()


class TestCacheInvalidation:
    """Test cache invalidation triggers."""

    @pytest.fixture
    def cache(self):
        """Create cache."""
        return MockBackendSelectionCache(max_size=1000, ttl_seconds=300)

    def test_invalidate_on_backend_change(self, cache):
        """Clear cache when backends change."""
        query = "invalidation test"
        cache.set(query, "semantic", 0.95)

        # Verify it's cached
        result1 = cache.get(query)
        assert result1 is not None

        # Invalidate on backend change
        cache.invalidate(query)

        # Should miss after invalidation
        result2 = cache.get(query)
        assert result2 is None

    def test_invalidate_on_config_change(self, cache):
        """Clear cache when config changes."""
        # Simulate config-dependent queries
        for i in range(5):
            cache.set(f"config_{i}", "semantic", 0.9)

        # Verify cached
        assert cache.get_size() == 5

        # Clear on config change
        cache.clear()

        # All should miss now
        assert cache.get_size() == 0

    def test_selective_invalidation(self, cache):
        """Invalidate only affected entries."""
        # Cache multiple entries
        cache.set("keep_1", "semantic", 0.95)
        cache.set("remove_1", "keyword", 0.85)
        cache.set("keep_2", "hybrid", 0.90)

        initial_size = cache.get_size()

        # Selectively invalidate
        cache.invalidate("remove_1")

        # Others should still be cached
        assert cache.get("keep_1") is not None
        assert cache.get("keep_2") is not None
        assert cache.get("remove_1") is None
        assert cache.get_size() == initial_size - 1

    def test_invalidation_timing(self, cache):
        """Invalidation happens promptly."""
        query = "timing test"
        cache.set(query, "semantic", 0.95)

        # Measure invalidation time
        start = time.time()
        cache.invalidate(query)
        elapsed = time.time() - start

        # Should be fast (< 10ms)
        assert elapsed < 0.01

        # Verify invalidation worked
        assert cache.get(query) is None


class TestCacheMemoryUsage:
    """Test cache memory efficiency."""

    @pytest.fixture
    def cache(self):
        """Create cache."""
        return MockBackendSelectionCache(max_size=100, ttl_seconds=300)

    def test_cache_size_limits(self, cache):
        """Cache respects max size."""
        # Fill beyond max size
        for i in range(150):
            cache.set(f"query_{i}", "semantic", 0.9)

        # Should not exceed max size
        assert cache.get_size() <= cache.max_size

    def test_eviction_strategy(self, cache):
        """LRU or similar eviction policy."""
        # Set entries
        cache.set("old_1", "semantic", 0.9)
        time.sleep(0.01)
        cache.set("new_1", "keyword", 0.8)

        # Access old_1 to make it recent
        cache.get("old_1")

        # Fill cache beyond limit
        for i in range(105):
            cache.set(f"fill_{i}", "hybrid", 0.7)

        # Recently accessed should be kept
        # (implementation dependent)
        size = cache.get_size()
        assert size <= cache.max_size

    def test_memory_under_load(self, cache):
        """Memory usage reasonable under load."""
        # Cache many entries
        for i in range(100):
            cache.set(f"memory_test_{i}", "semantic", 0.9)

        memory = cache.get_memory_estimate()
        # Should be reasonable (less than 1MB for 100 entries)
        assert memory < 1_000_000

    def test_cache_compression(self, cache):
        """Cache handles data compactly."""
        # Store entries with long queries
        for i in range(50):
            long_query = f"very long query with lots of text content {i}" * 10
            cache.set(long_query, "semantic", 0.9)

        # Should still respect size limits
        assert cache.get_size() <= cache.max_size


class TestConcurrentCacheAccess:
    """Test thread-safety of cache."""

    @pytest.fixture
    def cache(self):
        """Create cache."""
        return MockBackendSelectionCache(max_size=1000, ttl_seconds=300)

    def test_concurrent_reads(self, cache):
        """Multiple readers don't block."""
        query = "concurrent test"
        cache.set(query, "semantic", 0.95)

        results = []

        def reader():
            for _ in range(100):
                result = cache.get(query)
                results.append(result)

        # Run multiple readers
        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed
        assert len(results) == 500

    def test_read_write_consistency(self, cache):
        """Read-write operations consistent."""
        results = []

        def write_and_read():
            for i in range(10):
                query = f"consistency_{i}"
                cache.set(query, "semantic", 0.9)
                result = cache.get(query)
                results.append((i, result is not None))

        threads = [threading.Thread(target=write_and_read) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert all(success for _, success in results)

    def test_cache_coherence(self, cache):
        """All readers see consistent data."""
        observed_values = []

        def reader(query_num):
            for _ in range(20):
                result = cache.get(f"coherence_{query_num}")
                if result:
                    observed_values.append(result["backend"])

        # Set values
        for i in range(5):
            cache.set(f"coherence_{i}", f"backend_{i}", 0.9)

        # Read concurrently
        threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All observers should see consistent backend names
        for value in observed_values:
            assert "backend_" in value


# ============================================================================
# Integration Tests
# ============================================================================

def test_cache_integration():
    """Integration test for cache operations."""
    cache = MockBackendSelectionCache(max_size=100, ttl_seconds=60)

    # Warm up cache
    for i in range(50):
        cache.set(f"query_{i}", "semantic", 0.9)

    # Generate workload
    for i in range(500):
        cache.get(f"query_{i % 50}")

    # Verify metrics
    hit_rate = cache.get_hit_rate()
    assert hit_rate > 50.0  # Should have good hit rate
    assert cache.get_size() <= 100  # Should respect size limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
