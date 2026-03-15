# Quality Cache Integration Guide

## Overview

The quality cache (`quality_cache.py`) is implemented and ready for integration. It provides intelligent caching with quality gates based on critic evaluation and reflection confidence.

## Current Status

**✓ Implemented:**
- Core caching logic (`quality_cache.py` - 367 lines)
- Quality gates (critic score ≥ 85, confidence ≥ 0.8)
- LRU eviction, TTL management
- Comprehensive metrics tracking
- `/status` endpoint integration

**⚠ Pending:**
- Integration into response generation paths
- Active usage in query/delegation flows

## Integration Points

### 1. Query Response Caching (`handle_query` - line 2087)

**Location:** `http_server.py:2285` - after `_route_search` call

**Pattern:**
```python
from quality_cache import get_cached_response, cache_response, should_use_cache

# Before _route_search call:
if should_use_cache(query, reflection_confidence=None):
    cached = get_cached_response(query, context=request_context)
    if cached:
        response, cache_metadata = cached
        result = {"response": response, "cached": True, **cache_metadata}
        return web.json_response(result)

# After _route_search call (if generate_response=True):
result = await _route_search(...)
if result.get("response") and result.get("quality_score"):
    cache_response(
        query=query,
        response=result["response"],
        quality_score=result["quality_score"],
        confidence=result.get("confidence", 1.0),
        context=request_context
    )
```

### 2. Delegation Responses (`delegation_feedback.py`)

**Location:** After critic evaluation in delegation flow

**Pattern:**
```python
from quality_cache import cache_response
from generator_critic import critique_response

# After generating delegated response:
critique = critique_response(task, response_text, task_type="code")
if critique.passed:
    cache_response(
        query=task,
        response=response_text,
        quality_score=critique.quality_score,
        confidence=0.95,  # High confidence for passed evaluations
        context={"task_type": task_type, "agent": agent}
    )
```

### 3. Hint Delivery (Optional - for frequently-requested hints)

**Location:** `handle_hints` - line 3070

**Note:** Hints are pre-computed rankings, not generated responses. Cache integration here is optional and would cache the entire hint result set for identical queries.

## Cache Configuration

Current defaults in `quality_cache.py`:
```python
CACHE_QUALITY_THRESHOLD = 85.0   # Minimum critic score
CACHE_CONFIDENCE_THRESHOLD = 0.8  # Minimum reflection confidence
CACHE_TTL_SECONDS = 3600          # 1 hour
CACHE_MAX_SIZE = 1000             # Max entries
```

## Monitoring

Cache stats available via `/status` endpoint with API key:
```bash
curl -H "X-API-Key: Model1" http://localhost:8003/status | jq '.quality_cache_stats'
```

**Metrics tracked:**
- `total_queries`, `cache_hits`, `cache_misses`, `cache_skips`
- `hit_rate`, `skip_rate`, `recent_hit_rate`
- `avg_hit_quality`, `avg_cached_confidence`
- `cache_size`, `cache_evictions`

## Testing Plan

1. **Unit Test:** Add `scripts/testing/test-quality-cache.py`
   - Test cache key generation
   - Test quality thresholds
   - Test LRU eviction
   - Test TTL expiration

2. **Integration Test:** Add cache to one endpoint (e.g., `/query`)
   - Run query twice with same input
   - Verify second query is cache hit
   - Check quality metrics in `/status`

3. **Load Test:** Monitor cache performance
   - Track hit rate over 100 queries
   - Verify quality threshold enforcement
   - Validate cache size limits

## Next Steps

1. Choose integration point (recommended: `handle_query` for `/query` endpoint)
2. Add cache check before expensive operations
3. Add cache write after quality validation
4. Run integration tests
5. Monitor cache metrics
6. Tune thresholds based on production data

## Notes

- Cache is currently passive (not integrated into flow)
- All infrastructure is in place and monitoring-ready
- Integration is straightforward with provided patterns
- Expected benefits: 20-40% latency reduction for cache hits
