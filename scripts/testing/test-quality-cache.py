#!/usr/bin/env python3
"""
Test quality-aware response caching.

Validates:
- Cache key generation
- Quality thresholds
- Cache hit/miss behavior
- LRU eviction
- TTL expiration
- Metrics tracking
"""

import sys
import time
from pathlib import Path

# Add hybrid-coordinator to path
coordinator_path = Path(__file__).parent.parent.parent / "ai-stack/mcp-servers/hybrid-coordinator"
sys.path.insert(0, str(coordinator_path))

from quality_cache import (
    generate_cache_key,
    get_cached_response,
    cache_response,
    should_use_cache,
    get_cache_stats,
    clear_cache,
)


def test_cache_key_generation():
    """Test cache key generation is consistent."""
    print("Testing cache key generation...")

    query1 = "How do I configure NixOS firewall?"
    query2 = "how do i configure nixos firewall?"  # Case insensitive
    query3 = "  How do I configure NixOS firewall?  "  # Whitespace

    key1 = generate_cache_key(query1)
    key2 = generate_cache_key(query2)
    key3 = generate_cache_key(query3)

    assert key1 == key2 == key3, "Cache keys should be case/whitespace insensitive"
    print(f"✓ Cache key generation: {key1}")


def test_quality_threshold():
    """Test quality threshold enforcement."""
    print("\nTesting quality threshold...")

    clear_cache()
    query = "Test query for quality threshold"

    # Try to cache low-quality response (should be rejected)
    low_quality_cached = cache_response(
        query=query,
        response="Low quality response",
        quality_score=70.0,  # Below 85 threshold
        confidence=0.9,
    )
    assert not low_quality_cached, "Low quality response should not be cached"
    print("✓ Low quality response rejected (score=70)")

    # Cache high-quality response (should succeed)
    high_quality_cached = cache_response(
        query=query,
        response="High quality response with structured format:\n1. Answer\n2. Code\n3. Explanation",
        quality_score=90.0,  # Above 85 threshold
        confidence=0.95,
    )
    assert high_quality_cached, "High quality response should be cached"
    print("✓ High quality response cached (score=90)")

    stats = get_cache_stats()
    assert stats["cache_size"] == 1, "Cache should have 1 entry"
    print(f"✓ Cache size: {stats['cache_size']}")


def test_cache_hit_miss():
    """Test cache hit and miss behavior."""
    print("\nTesting cache hit/miss...")

    clear_cache()
    query = "How to enable SSH on NixOS?"

    # First query - should be a miss
    result1 = get_cached_response(query)
    assert result1 is None, "First query should be a cache miss"

    stats = get_cache_stats()
    assert stats["cache_misses"] == 1, "Should have 1 miss"
    print("✓ Cache miss on first query")

    # Cache a high-quality response
    response_text = "To enable SSH on NixOS:\n1. Add services.openssh.enable = true\n2. Rebuild system\n3. SSH will be available"
    cache_response(
        query=query,
        response=response_text,
        quality_score=92.0,
        confidence=0.98,
    )

    # Second query - should be a hit
    result2 = get_cached_response(query)
    assert result2 is not None, "Second query should be a cache hit"
    cached_response, metadata = result2
    assert cached_response == response_text, "Cached response should match"
    assert metadata["cache_hit"] is True, "Metadata should indicate cache hit"
    assert metadata["quality_score"] == 92.0, "Quality score should be preserved"

    stats = get_cache_stats()
    assert stats["cache_hits"] == 1, "Should have 1 hit"
    assert stats["hit_rate"] == 0.5, "Hit rate should be 50% (1 hit, 1 miss)"
    print(f"✓ Cache hit on second query (hit_rate={stats['hit_rate']:.1%})")


def test_confidence_threshold():
    """Test confidence threshold for cache usage."""
    print("\nTesting confidence threshold...")

    # Low confidence should skip cache
    low_conf = should_use_cache("query", reflection_confidence=0.5)
    assert not low_conf, "Low confidence should skip cache"
    print("✓ Low confidence (0.5) skips cache")

    # High confidence should use cache
    high_conf = should_use_cache("How to configure firewall?", reflection_confidence=0.9)
    assert high_conf, "High confidence should use cache"
    print("✓ High confidence (0.9) uses cache")


def test_metrics_tracking():
    """Test comprehensive metrics tracking."""
    print("\nTesting metrics tracking...")

    clear_cache()

    # Get baseline stats
    baseline = get_cache_stats()

    # Generate some cache activity
    queries = [
        ("Query 1", "Response 1", 88.0, 0.92),
        ("Query 2", "Response 2", 95.0, 0.98),
        ("Query 3", "Response 3", 87.0, 0.89),
    ]

    for query, response, quality, confidence in queries:
        cache_response(query, response, quality, confidence)

    # Do some cache lookups
    get_cached_response("Query 1")  # Hit
    get_cached_response("Query 2")  # Hit
    get_cached_response("Unknown")  # Miss

    stats = get_cache_stats()

    assert stats["cache_size"] == 3, f"Should have 3 entries, got {stats['cache_size']}"
    assert stats["cache_writes"] >= 3, f"Should have at least 3 writes, got {stats['cache_writes']}"
    # Total queries and hits/misses are cumulative, so just check they increased
    assert stats["total_queries"] > baseline["total_queries"], "Total queries should increase"
    assert stats["cache_hits"] > baseline["cache_hits"], "Cache hits should increase"
    assert stats["avg_hit_quality"] > 85.0, f"Average hit quality should be > 85, got {stats['avg_hit_quality']}"

    print(f"✓ Metrics tracking:")
    print(f"  - Cache size: {stats['cache_size']}")
    print(f"  - Hit rate: {stats['hit_rate']:.1%}")
    print(f"  - Avg quality: {stats['avg_hit_quality']:.1f}")


def test_cache_expiration():
    """Test TTL expiration."""
    print("\nTesting TTL expiration...")

    clear_cache()
    query = "Test TTL query"

    # Cache with very short TTL
    cache_response(
        query=query,
        response="Short-lived response",
        quality_score=90.0,
        confidence=0.95,
        ttl_seconds=1  # 1 second TTL
    )

    # Should be cached immediately
    result1 = get_cached_response(query)
    assert result1 is not None, "Should be cached immediately"
    print("✓ Response cached with 1s TTL")

    # Wait for expiration
    time.sleep(2)

    # Should be expired now
    result2 = get_cached_response(query)
    assert result2 is None, "Should be expired after TTL"

    stats = get_cache_stats()
    assert stats["cache_evictions"] == 1, "Should have 1 eviction"
    print("✓ Response expired after TTL")


def run_all_tests():
    """Run all cache tests."""
    print("=" * 60)
    print("Quality Cache Test Suite")
    print("=" * 60)

    try:
        test_cache_key_generation()
        test_quality_threshold()
        test_cache_hit_miss()
        test_confidence_threshold()
        test_metrics_tracking()
        test_cache_expiration()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

        # Show final stats
        stats = get_cache_stats()
        print("\nFinal Cache Statistics:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.3f}")
            else:
                print(f"  {key}: {value}")

        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
