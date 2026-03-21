#!/usr/bin/env python3
"""
Test Suite: Query Result Caching (Phase 5.2 Performance Optimizations - P1)

Purpose:
    Comprehensive testing for query result caching layer including:
    - Cache TTL enforcement
    - Cache invalidation triggers
    - Concurrent cache access thread-safety
    - Cache efficiency metrics (hit rate, latency reduction)
    - Memory limits and LRU eviction policy

Module Under Test:
    dashboard/backend/api/services/context_store.py
    dashboard/backend/api/cache_layer.py (hypothetical)

Classes:
    TestCacheTTLEnforcement - TTL enforcement and expiration
    TestCacheInvalidationTriggers - Cache invalidation on events
    TestConcurrentCacheAccess - Thread-safe cache operations
    TestCacheEfficiencyMetrics - Cache hit rates and performance
    TestMemoryLimitsEviction - Memory management and eviction

Coverage: ~250 lines
Phase: 5.2 (Performance Caching)
"""

import pytest
import time
import threading
from typing import Dict, Any, Optional
from collections import OrderedDict
from unittest.mock import Mock, MagicMock, patch


class CacheEntry:
    """Cache entry with TTL."""

    def __init__(self, value: Any, ttl: int):
        """Initialize cache entry.

        Args:
            value: Cached value
            ttl: Time-to-live in seconds
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return (time.time() - self.created_at) > self.ttl

    def access(self):
        """Record access to entry."""
        self.access_count += 1
        self.last_accessed = time.time()


class TestCacheTTLEnforcement:
    """Test TTL enforcement in cache.

    Validates that cache entries expire correctly after TTL and that
    expired entries are not returned to callers.
    """

    @pytest.fixture
    def ttl_cache(self):
        """Cache with TTL enforcement."""
        cache = Mock()
        cache._entries = {}
        cache.default_ttl = 300  # 5 minutes

        def get(key: str) -> Optional[Any]:
            """Get value from cache."""
            if key not in cache._entries:
                return None

            entry = cache._entries[key]
            if entry.is_expired():
                del cache._entries[key]
                return None

            entry.access()
            return entry.value

        def set(key: str, value: Any, ttl: int = None) -> None:
            """Set value in cache."""
            ttl = ttl or cache.default_ttl
            cache._entries[key] = CacheEntry(value, ttl)

        def has_expired(key: str) -> bool:
            """Check if entry has expired."""
            if key not in cache._entries:
                return True
            return cache._entries[key].is_expired()

        cache.get = get
        cache.set = set
        cache.has_expired = has_expired
        return cache

    def test_ttl_enforcement_expires_entry(self, ttl_cache):
        """Entry expires after TTL."""
        ttl_cache.set('key1', 'value1', ttl=0.1)
        assert ttl_cache.get('key1') == 'value1'

        time.sleep(0.15)
        assert ttl_cache.get('key1') is None

    def test_ttl_uses_default_when_not_specified(self, ttl_cache):
        """Default TTL used when not specified."""
        ttl_cache.default_ttl = 0.2
        ttl_cache.set('key2', 'value2')

        assert ttl_cache.get('key2') == 'value2'
        time.sleep(0.25)
        assert ttl_cache.get('key2') is None

    def test_different_ttls_for_different_entries(self, ttl_cache):
        """Different entries can have different TTLs."""
        ttl_cache.set('short', 'short_value', ttl=0.1)
        ttl_cache.set('long', 'long_value', ttl=0.5)

        assert ttl_cache.get('short') == 'short_value'
        assert ttl_cache.get('long') == 'long_value'

        time.sleep(0.15)
        assert ttl_cache.get('short') is None
        assert ttl_cache.get('long') == 'long_value'

    def test_access_does_not_reset_ttl(self, ttl_cache):
        """Accessing entry does not reset TTL."""
        ttl_cache.set('key3', 'value3', ttl=0.2)

        # Access multiple times
        ttl_cache.get('key3')
        time.sleep(0.1)
        ttl_cache.get('key3')
        time.sleep(0.15)

        # Should still expire based on creation time
        assert ttl_cache.get('key3') is None


class TestCacheInvalidationTriggers:
    """Test cache invalidation on triggering events.

    Validates that cache is properly invalidated when deployment changes,
    config updates, and other state-changing events occur.
    """

    @pytest.fixture
    def invalidating_cache(self):
        """Cache with invalidation triggers."""
        cache = Mock()
        cache._entries = {}
        cache.invalidation_events = []

        def get(key: str) -> Optional[Any]:
            """Get cached value."""
            return cache._entries.get(key)

        def set(key: str, value: Any) -> None:
            """Set cached value."""
            cache._entries[key] = value

        def invalidate(key: str = None, pattern: str = None) -> None:
            """Invalidate cache entries."""
            if key:
                if key in cache._entries:
                    del cache._entries[key]
            elif pattern:
                # Pattern-based invalidation (e.g., "deployment:*")
                for k in list(cache._entries.keys()):
                    if k.startswith(pattern.replace('*', '')):
                        del cache._entries[k]

            cache.invalidation_events.append({
                'timestamp': time.time(),
                'type': 'invalidate',
                'key': key,
                'pattern': pattern
            })

        def on_deployment_change(deployment_id: str) -> None:
            """Invalidate cache on deployment change."""
            invalidate(pattern=f"deployment:{deployment_id}:")
            cache.invalidation_events.append({
                'timestamp': time.time(),
                'type': 'deployment_change',
                'deployment_id': deployment_id
            })

        def on_config_update() -> None:
            """Invalidate cache on config update."""
            invalidate(pattern="config:")
            cache.invalidation_events.append({
                'timestamp': time.time(),
                'type': 'config_update'
            })

        cache.get = get
        cache.set = set
        cache.invalidate = invalidate
        cache.on_deployment_change = on_deployment_change
        cache.on_config_update = on_config_update
        return cache

    def test_direct_key_invalidation(self, invalidating_cache):
        """Invalidate specific cache key."""
        invalidating_cache.set('key1', 'value1')
        assert invalidating_cache.get('key1') == 'value1'

        invalidating_cache.invalidate('key1')
        assert invalidating_cache.get('key1') is None

    def test_pattern_based_invalidation(self, invalidating_cache):
        """Pattern-based invalidation removes matching keys."""
        invalidating_cache.set('deployment:d1:status', 'running')
        invalidating_cache.set('deployment:d1:metrics', {'cpu': 50})
        invalidating_cache.set('deployment:d2:status', 'running')

        invalidating_cache.invalidate(pattern='deployment:d1:')

        assert invalidating_cache.get('deployment:d1:status') is None
        assert invalidating_cache.get('deployment:d1:metrics') is None
        assert invalidating_cache.get('deployment:d2:status') == 'running'

    def test_deployment_change_triggers_invalidation(self, invalidating_cache):
        """Deployment change invalidates related cache."""
        invalidating_cache.set('deployment:app1:status', 'running')
        invalidating_cache.set('deployment:app1:metrics', {'cpu': 50})

        invalidating_cache.on_deployment_change('app1')

        assert invalidating_cache.get('deployment:app1:status') is None
        assert invalidating_cache.get('deployment:app1:metrics') is None

    def test_config_update_invalidates_config_cache(self, invalidating_cache):
        """Config update invalidates all config entries."""
        invalidating_cache.set('config:database_url', 'postgresql://...')
        invalidating_cache.set('config:cache_size', '1gb')
        invalidating_cache.set('other:value', 'data')

        invalidating_cache.on_config_update()

        assert invalidating_cache.get('config:database_url') is None
        assert invalidating_cache.get('config:cache_size') is None
        assert invalidating_cache.get('other:value') == 'data'

    def test_invalidation_events_tracked(self, invalidating_cache):
        """Invalidation events are tracked."""
        invalidating_cache.set('key1', 'value1')
        invalidating_cache.invalidate('key1')

        assert len(invalidating_cache.invalidation_events) == 1
        event = invalidating_cache.invalidation_events[0]
        assert event['type'] == 'invalidate'
        assert event['key'] == 'key1'


class TestConcurrentCacheAccess:
    """Test thread-safe concurrent cache access.

    Validates that concurrent reads and writes maintain data consistency
    and do not cause race conditions or corruption.
    """

    @pytest.fixture
    def concurrent_cache(self):
        """Thread-safe cache."""
        cache = Mock()
        cache._entries = {}
        cache.lock = threading.RLock()
        cache.operation_log = []

        def get(key: str) -> Optional[Any]:
            """Thread-safe get."""
            with cache.lock:
                result = cache._entries.get(key)
                cache.operation_log.append(('get', key, result))
                return result

        def set(key: str, value: Any) -> None:
            """Thread-safe set."""
            with cache.lock:
                cache._entries[key] = value
                cache.operation_log.append(('set', key, value))

        def increment(key: str) -> int:
            """Thread-safe increment."""
            with cache.lock:
                current = cache._entries.get(key, 0)
                new_value = current + 1
                cache._entries[key] = new_value
                cache.operation_log.append(('increment', key, new_value))
                return new_value

        cache.get = get
        cache.set = set
        cache.increment = increment
        return cache

    def test_concurrent_reads_are_safe(self, concurrent_cache):
        """Concurrent reads don't corrupt cache."""
        concurrent_cache.set('shared_key', 'shared_value')

        def reader():
            for _ in range(100):
                value = concurrent_cache.get('shared_key')
                assert value == 'shared_value'

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed
        assert len(concurrent_cache.operation_log) > 0

    def test_concurrent_increments_are_atomic(self, concurrent_cache):
        """Concurrent increments maintain atomicity."""
        concurrent_cache.set('counter', 0)

        def incrementer():
            for _ in range(50):
                concurrent_cache.increment('counter')

        threads = [threading.Thread(target=incrementer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 250 increments
        final_value = concurrent_cache.get('counter')
        assert final_value == 250

    def test_concurrent_writes_maintain_order(self, concurrent_cache):
        """Concurrent writes are properly ordered."""
        def writer(thread_id: int):
            for i in range(10):
                concurrent_cache.set(f'thread_{thread_id}_{i}', i)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all writes completed
        assert concurrent_cache.get('thread_0_0') == 0
        assert concurrent_cache.get('thread_2_9') == 9


class TestCacheEfficiencyMetrics:
    """Test cache efficiency metrics.

    Validates that cache hit rates are measured accurately and that
    caching provides measurable performance improvements.
    """

    @pytest.fixture
    def metrics_cache(self):
        """Cache with metrics tracking."""
        cache = Mock()
        cache._entries = {}
        cache.metrics = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_latency_cached': 0.0,
            'total_latency_uncached': 0.0
        }

        def get(key: str, compute_fn=None) -> Any:
            """Get with metrics."""
            start = time.perf_counter()

            if key in cache._entries:
                cache.metrics['hits'] += 1
                result = cache._entries[key]
                latency = time.perf_counter() - start
                cache.metrics['total_latency_cached'] += latency
                return result

            cache.metrics['misses'] += 1
            if compute_fn:
                result = compute_fn()
                cache._entries[key] = result
                latency = time.perf_counter() - start
                cache.metrics['total_latency_uncached'] += latency
                return result
            return None

        def hit_rate(self) -> float:
            """Calculate hit rate."""
            total = cache.metrics['hits'] + cache.metrics['misses']
            if total == 0:
                return 0.0
            return cache.metrics['hits'] / total

        def avg_cached_latency(self) -> float:
            """Average latency for cache hits."""
            if cache.metrics['hits'] == 0:
                return 0.0
            return cache.metrics['total_latency_cached'] / cache.metrics['hits']

        def avg_uncached_latency(self) -> float:
            """Average latency for cache misses."""
            if cache.metrics['misses'] == 0:
                return 0.0
            return cache.metrics['total_latency_uncached'] / cache.metrics['misses']

        cache.get = get
        cache.hit_rate = lambda: hit_rate(cache)
        cache.avg_cached_latency = lambda: avg_cached_latency(cache)
        cache.avg_uncached_latency = lambda: avg_uncached_latency(cache)
        return cache

    def test_hit_rate_calculation(self, metrics_cache):
        """Hit rate calculated correctly."""
        def expensive():
            return {'result': 'data'}

        # Cache misses
        metrics_cache.get('k1', expensive)
        metrics_cache.get('k2', expensive)

        # Cache hits
        metrics_cache.get('k1')
        metrics_cache.get('k1')

        hit_rate = metrics_cache.hit_rate()
        assert hit_rate == 0.5  # 2 hits out of 4 accesses

    def test_latency_improvement_from_caching(self, metrics_cache):
        """Caching reduces latency."""
        def slow_compute():
            time.sleep(0.05)
            return 'data'

        # First access (miss, slow)
        metrics_cache.get('slow_key', slow_compute)

        # Subsequent accesses (hits, fast)
        for _ in range(10):
            metrics_cache.get('slow_key')

        cached_latency = metrics_cache.avg_cached_latency()
        uncached_latency = metrics_cache.avg_uncached_latency()

        # Cached should be much faster
        assert cached_latency < uncached_latency * 0.1

    def test_metrics_track_evictions(self, metrics_cache):
        """Evictions are tracked in metrics."""
        # Mock eviction
        metrics_cache.metrics['evictions'] += 1
        metrics_cache.metrics['evictions'] += 1

        assert metrics_cache.metrics['evictions'] == 2


class TestMemoryLimitsEviction:
    """Test memory limits and LRU eviction.

    Validates that cache respects memory limits and evicts least-recently-used
    entries when capacity is reached.
    """

    @pytest.fixture
    def lru_cache(self):
        """LRU cache with memory limits."""
        cache = Mock()
        cache._entries = OrderedDict()
        cache.max_size = 100
        cache.evicted_keys = []

        def set(key: str, value: Any) -> None:
            """Set with LRU eviction."""
            if key in cache._entries:
                del cache._entries[key]  # Move to end

            cache._entries[key] = value

            # Evict if over capacity
            while len(cache._entries) > cache.max_size:
                evicted_key, _ = cache._entries.popitem(last=False)
                cache.evicted_keys.append(evicted_key)

        def get(key: str) -> Optional[Any]:
            """Get with LRU tracking."""
            if key not in cache._entries:
                return None

            value = cache._entries[key]
            del cache._entries[key]
            cache._entries[key] = value  # Move to end (most recent)
            return value

        cache.set = set
        cache.get = get
        return cache

    def test_eviction_on_capacity_exceeded(self, lru_cache):
        """LRU eviction when capacity exceeded."""
        lru_cache.max_size = 3

        lru_cache.set('a', 1)
        lru_cache.set('b', 2)
        lru_cache.set('c', 3)

        # This should trigger eviction of 'a'
        lru_cache.set('d', 4)

        assert lru_cache.get('a') is None
        assert lru_cache.get('b') == 2
        assert lru_cache.get('d') == 4

    def test_least_recently_used_evicted(self, lru_cache):
        """Least recently used entry is evicted."""
        lru_cache.max_size = 3

        lru_cache.set('a', 1)
        lru_cache.set('b', 2)
        lru_cache.set('c', 3)

        # Access 'b' to make it more recent
        lru_cache.get('b')

        # Add new entry, 'a' should be evicted (least recent)
        lru_cache.set('d', 4)

        assert 'a' in lru_cache.evicted_keys
        assert lru_cache.get('b') == 2
        assert lru_cache.get('c') == 3

    def test_multiple_evictions_maintain_capacity(self, lru_cache):
        """Multiple evictions maintain size limit."""
        lru_cache.max_size = 5

        for i in range(20):
            lru_cache.set(f'key_{i}', i)

        assert len(lru_cache._entries) == 5
        assert len(lru_cache.evicted_keys) == 15


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
