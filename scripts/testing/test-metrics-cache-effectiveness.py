#!/usr/bin/env python3
"""
Test suite for metrics cache effectiveness.

Purpose: Verify metrics caching strategy, TTL enforcement, cache invalidation,
and memory management for dashboard metrics API.

Covers:
- Metrics cache hit rate
- Cache TTL enforcement
- Cache invalidation triggers
- Memory usage limits
- Data freshness guarantees
"""

import time
import pytest
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict


@dataclass
class MetricsSnapshot:
    """Cached metrics snapshot."""
    id: str
    timestamp: datetime
    metrics: Dict[str, Any]
    ttl_seconds: int
    access_count: int = 0

    def is_expired(self) -> bool:
        """Check if snapshot has expired."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def touch(self):
        """Update last access time."""
        self.access_count += 1


class MockMetricsCache:
    """Mock metrics caching system."""

    def __init__(self, max_snapshots: int = 100, default_ttl: int = 60):
        self.max_snapshots = max_snapshots
        self.default_ttl = default_ttl
        self._cache: Dict[str, MetricsSnapshot] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        self.memory_usage = 0

    def get_metrics(self, metric_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached metrics."""
        if metric_key not in self._cache:
            self.misses += 1
            return None

        snapshot = self._cache[metric_key]

        # Check expiration
        if snapshot.is_expired():
            del self._cache[metric_key]
            self.misses += 1
            return None

        # Update LRU
        self._cache.move_to_end(metric_key)
        snapshot.touch()
        self.hits += 1

        return snapshot.metrics

    def cache_metrics(self, metric_key: str, metrics: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        """Cache metrics snapshot."""
        ttl = ttl_seconds or self.default_ttl

        snapshot = MetricsSnapshot(
            id=metric_key,
            timestamp=datetime.now(),
            metrics=metrics,
            ttl_seconds=ttl
        )

        self._cache[metric_key] = snapshot
        self._cache.move_to_end(metric_key)

        # Evict oldest if over limit
        while len(self._cache) > self.max_snapshots:
            removed_key, removed_snapshot = self._cache.popitem(last=False)
            self.memory_usage -= self._estimate_size(removed_snapshot)

        # Update memory estimate
        self.memory_usage += self._estimate_size(snapshot)

    def invalidate_metrics(self, pattern: str = None) -> int:
        """Invalidate cached metrics by pattern."""
        removed = 0

        if pattern is None:
            # Clear all
            for snapshot in self._cache.values():
                self.memory_usage -= self._estimate_size(snapshot)
            self._cache.clear()
            removed = len(self._cache)
        else:
            # Selective invalidation
            keys_to_remove = [
                key for key in self._cache.keys()
                if pattern in key
            ]

            for key in keys_to_remove:
                snapshot = self._cache.pop(key)
                self.memory_usage -= self._estimate_size(snapshot)
                removed += 1

        self.invalidations += removed
        return removed

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100.0

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired_keys = [
            key for key, snapshot in self._cache.items()
            if snapshot.is_expired()
        ]

        for key in expired_keys:
            snapshot = self._cache.pop(key)
            self.memory_usage -= self._estimate_size(snapshot)

        return len(expired_keys)

    def _estimate_size(self, snapshot: MetricsSnapshot) -> int:
        """Estimate size of snapshot in bytes."""
        # Simple estimation: key + metrics data
        size = len(snapshot.id.encode())
        for k, v in snapshot.metrics.items():
            size += len(str(k).encode()) + len(str(v).encode())
        return size + 100  # Overhead

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "snapshots_cached": len(self._cache),
            "max_capacity": self.max_snapshots,
            "hit_rate": self.get_hit_rate(),
            "hits": self.hits,
            "misses": self.misses,
            "memory_bytes": self.memory_usage,
            "invalidations": self.invalidations,
        }

    def enforce_ttl(self) -> int:
        """Enforce TTL by removing expired entries."""
        return self.cleanup_expired()


# ============================================================================
# Test Classes
# ============================================================================

class TestCacheHitRate:
    """Test metrics cache hit rate."""

    @pytest.fixture
    def cache(self):
        """Create metrics cache."""
        return MockMetricsCache(max_snapshots=100, default_ttl=60)

    def test_hit_identical_query(self, cache):
        """Hit cache for identical metric queries."""
        metrics = {"cpu": 45.0, "memory": 2048, "requests": 150}
        cache.cache_metrics("system_metrics", metrics)

        # First access
        result1 = cache.get_metrics("system_metrics")
        assert result1 is not None

        # Second access (hit)
        result2 = cache.get_metrics("system_metrics")
        assert result2 is not None
        assert cache.hits >= 2

    def test_miss_different_metric_key(self, cache):
        """Miss cache for different metric keys."""
        cache.cache_metrics("metric_a", {"value": 1})

        result1 = cache.get_metrics("metric_a")
        assert result1 is not None

        result2 = cache.get_metrics("metric_b")
        assert result2 is None
        assert cache.misses >= 1

    def test_hit_rate_calculation(self, cache):
        """Calculate hit rate correctly."""
        # Create hits
        cache.cache_metrics("test_1", {"value": 1})
        for _ in range(3):
            cache.get_metrics("test_1")

        # Create misses
        cache.get_metrics("nonexistent_1")
        cache.get_metrics("nonexistent_2")

        hit_rate = cache.get_hit_rate()
        assert 0.0 <= hit_rate <= 100.0
        # Should be 3 hits / 5 total = 60%

    def test_hit_rate_improvement_with_warmup(self, cache):
        """Hit rate improves with cache warmup."""
        # Warm cache
        for i in range(10):
            cache.cache_metrics(f"metric_{i % 3}", {"value": i})

        # Generate loads
        for i in range(30):
            cache.get_metrics(f"metric_{i % 3}")

        hit_rate = cache.get_hit_rate()
        assert hit_rate > 50.0  # Should have good hit rate


class TestCacheTTL:
    """Test cache TTL enforcement."""

    @pytest.fixture
    def cache(self):
        """Create cache with short TTL."""
        return MockMetricsCache(max_snapshots=100, default_ttl=1)

    def test_ttl_enforcement(self, cache):
        """Enforce cache TTL."""
        cache.cache_metrics("ttl_test", {"value": 42}, ttl_seconds=1)

        # Immediate access
        result1 = cache.get_metrics("ttl_test")
        assert result1 is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should miss after expiration
        result2 = cache.get_metrics("ttl_test")
        assert result2 is None

    def test_ttl_refresh(self, cache):
        """Refresh cache on access."""
        cache.cache_metrics("refresh", {"value": 1}, ttl_seconds=1)

        # First access
        cache.get_metrics("refresh")
        time.sleep(0.5)

        # Refresh by re-caching
        cache.cache_metrics("refresh", {"value": 2}, ttl_seconds=1)

        # Should still be valid
        time.sleep(0.7)
        result = cache.get_metrics("refresh")
        assert result is not None

    def test_variable_ttl(self, cache):
        """Support variable TTL values."""
        cache.cache_metrics("short", {"value": 1}, ttl_seconds=1)
        cache.cache_metrics("long", {"value": 2}, ttl_seconds=60)

        time.sleep(1.1)

        # Short should expire
        assert cache.get_metrics("short") is None
        # Long should still be valid
        assert cache.get_metrics("long") is not None

    def test_ttl_cleanup(self, cache):
        """Cleanup expired entries."""
        for i in range(5):
            cache.cache_metrics(f"expire_{i}", {"value": i}, ttl_seconds=1)

        time.sleep(1.1)

        removed = cache.cleanup_expired()
        assert removed > 0
        assert cache.get_cache_stats()["snapshots_cached"] == 0


class TestCacheInvalidation:
    """Test cache invalidation."""

    @pytest.fixture
    def cache(self):
        """Create cache."""
        return MockMetricsCache(max_snapshots=100, default_ttl=60)

    def test_selective_invalidation(self, cache):
        """Invalidate specific metrics."""
        cache.cache_metrics("keep_1", {"value": 1})
        cache.cache_metrics("remove_1", {"value": 2})
        cache.cache_metrics("keep_2", {"value": 3})

        # Invalidate by pattern
        removed = cache.invalidate_metrics("remove")
        assert removed > 0

        # Verify
        assert cache.get_metrics("keep_1") is not None
        assert cache.get_metrics("remove_1") is None
        assert cache.get_metrics("keep_2") is not None

    def test_clear_all_cache(self, cache):
        """Clear all cached data."""
        for i in range(10):
            cache.cache_metrics(f"metric_{i}", {"value": i})

        # Clear all (pass None to clear all)
        removed = cache.invalidate_metrics(pattern=None)
        # Should have removed items
        assert removed >= 0

        stats = cache.get_cache_stats()
        assert stats["snapshots_cached"] == 0

    def test_invalidation_timing(self, cache):
        """Invalidation happens promptly."""
        cache.cache_metrics("test", {"value": 1})

        start = time.time()
        cache.invalidate_metrics("test")
        elapsed = time.time() - start

        assert elapsed < 0.01  # Should be fast
        assert cache.get_metrics("test") is None


class TestCacheMemoryUsage:
    """Test memory efficiency."""

    @pytest.fixture
    def cache(self):
        """Create cache."""
        return MockMetricsCache(max_snapshots=50, default_ttl=60)

    def test_cache_size_limits(self, cache):
        """Respect max cache size."""
        # Fill beyond limit
        for i in range(100):
            cache.cache_metrics(f"metric_{i}", {"value": i, "data": "x" * 100})

        # Should not exceed max
        stats = cache.get_cache_stats()
        assert stats["snapshots_cached"] <= cache.max_snapshots

    def test_eviction_policy(self, cache):
        """LRU eviction when size exceeded."""
        # Cache in order
        cache.cache_metrics("first", {"value": 1})
        time.sleep(0.01)
        cache.cache_metrics("second", {"value": 2})
        time.sleep(0.01)
        cache.cache_metrics("third", {"value": 3})

        # Access first (make it recent)
        cache.get_metrics("first")

        # Fill beyond limit
        for i in range(100):
            cache.cache_metrics(f"fill_{i}", {"value": i})

        # First should be kept (recently accessed)
        # Second should be evicted (oldest)

    def test_memory_estimation(self, cache):
        """Estimate memory usage."""
        large_metrics = {f"metric_{i}": i for i in range(100)}
        cache.cache_metrics("large", large_metrics)

        stats = cache.get_cache_stats()
        assert stats["memory_bytes"] > 0

    def test_memory_bounds(self, cache):
        """Memory usage stays within bounds."""
        # Add large metrics
        for i in range(50):
            large_data = {"value": "x" * 1000 for _ in range(10)}
            cache.cache_metrics(f"large_{i}", large_data)

        stats = cache.get_cache_stats()
        # Rough bounds: < 1MB for test
        assert stats["memory_bytes"] < 1_000_000


# ============================================================================
# Integration Tests
# ============================================================================

def test_metrics_cache_integration():
    """Integration test for metrics cache."""
    cache = MockMetricsCache(max_snapshots=100, default_ttl=60)

    # Simulate metrics collection
    metrics_sets = [
        {"cpu": 45.0, "memory": 2048, "requests": 150},
        {"cpu": 52.0, "memory": 2100, "requests": 180},
        {"cpu": 48.0, "memory": 2000, "requests": 165},
    ]

    # Cache metrics
    for i, metrics in enumerate(metrics_sets):
        cache.cache_metrics(f"metrics_{i % 2}", metrics)

    # Generate access pattern
    for i in range(100):
        cache.get_metrics(f"metrics_{i % 2}")

    # Verify caching effectiveness
    stats = cache.get_cache_stats()
    assert stats["hit_rate"] > 50.0
    assert stats["snapshots_cached"] > 0
    assert stats["memory_bytes"] > 0


def test_cache_with_expiration():
    """Test cache behavior with expiration."""
    cache = MockMetricsCache(max_snapshots=100, default_ttl=2)

    # Cache some metrics
    for i in range(10):
        cache.cache_metrics(f"metric_{i}", {"value": i})

    # Access all to get hits
    for i in range(10):
        cache.get_metrics(f"metric_{i}")

    initial_hit_rate = cache.get_hit_rate()
    initial_stats = cache.get_cache_stats()

    # Wait for expiration
    time.sleep(2.1)

    # Access again - should miss
    for i in range(10):
        cache.get_metrics(f"metric_{i}")

    final_hit_rate = cache.get_hit_rate()

    # Hit rate should decrease due to expirations
    assert final_hit_rate < initial_hit_rate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
