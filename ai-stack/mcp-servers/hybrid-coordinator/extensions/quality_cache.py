"""
quality_cache.py — Quality-Aware Response Caching

Implements intelligent caching that leverages:
- Critic evaluation scores (only cache high-quality responses)
- Reflection confidence (skip cache for low-confidence queries)
- Response metadata for cache invalidation

Benefits:
- Reduces redundant work for common high-quality queries
- Improves response latency for cached results
- Maintains quality standards via critic gates
- Auto-invalidates low-confidence or outdated caches
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache Configuration
# ---------------------------------------------------------------------------

CACHE_QUALITY_THRESHOLD = 85.0  # Minimum critic score to cache
CACHE_CONFIDENCE_THRESHOLD = 0.8  # Minimum reflection confidence to use cache
CACHE_TTL_SECONDS = 3600  # 1 hour default TTL
CACHE_MAX_SIZE = 1000  # Maximum cached responses


# ---------------------------------------------------------------------------
# Cache Entry
# ---------------------------------------------------------------------------

@dataclass
class CachedResponse:
    """A cached response with quality metadata."""
    query_hash: str
    response: str
    quality_score: float
    confidence: float
    timestamp: str
    ttl_seconds: int
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        cached_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        age_seconds = (datetime.now(tz=timezone.utc) - cached_time).total_seconds()
        return age_seconds > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query_hash": self.query_hash,
            "response": self.response,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "hit_count": self.hit_count,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Cache Metrics
# ---------------------------------------------------------------------------

@dataclass
class CacheMetrics:
    """Tracks cache performance metrics."""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_skips: int = 0  # Low confidence or quality
    cache_writes: int = 0
    cache_evictions: int = 0
    avg_hit_quality: float = 0.0
    avg_cached_confidence: float = 0.0

    # Rolling windows
    recent_hits: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_qualities: deque = field(default_factory=lambda: deque(maxlen=100))


_cache_metrics = CacheMetrics()
_response_cache: Dict[str, CachedResponse] = {}


def get_cache_stats() -> Dict[str, Any]:
    """Get current cache statistics."""
    metrics = _cache_metrics

    if metrics.total_queries > 0:
        hit_rate = metrics.cache_hits / metrics.total_queries
        skip_rate = metrics.cache_skips / metrics.total_queries
    else:
        hit_rate = 0.0
        skip_rate = 0.0

    recent_hit_rate = (
        sum(metrics.recent_hits) / len(metrics.recent_hits)
        if metrics.recent_hits
        else 0.0
    )

    return {
        "total_queries": metrics.total_queries,
        "cache_hits": metrics.cache_hits,
        "cache_misses": metrics.cache_misses,
        "cache_skips": metrics.cache_skips,
        "cache_writes": metrics.cache_writes,
        "cache_evictions": metrics.cache_evictions,
        "hit_rate": round(hit_rate, 3),
        "skip_rate": round(skip_rate, 3),
        "recent_hit_rate": round(recent_hit_rate, 3),
        "avg_hit_quality": round(metrics.avg_hit_quality, 1),
        "avg_cached_confidence": round(metrics.avg_cached_confidence, 3),
        "cache_size": len(_response_cache),
        "cache_max_size": CACHE_MAX_SIZE,
        "active": True,
    }


# ---------------------------------------------------------------------------
# Cache Key Generation
# ---------------------------------------------------------------------------

def generate_cache_key(query: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a cache key for a query.

    Args:
        query: The user query
        context: Optional context that affects response (agent, task_type, etc.)

    Returns:
        SHA256 hash of normalized query + context
    """
    # Normalize query
    normalized = query.lower().strip()

    # Include relevant context in key
    context_str = ""
    if context:
        relevant_context = {
            "agent": context.get("agent"),
            "task_type": context.get("task_type"),
            "format": context.get("expected_format"),
        }
        context_str = json.dumps(relevant_context, sort_keys=True)

    key_material = f"{normalized}::{context_str}"
    return hashlib.sha256(key_material.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Cache Operations
# ---------------------------------------------------------------------------

def should_use_cache(
    query: str,
    reflection_confidence: Optional[float] = None,
) -> bool:
    """
    Determine if cache should be used for this query.

    Args:
        query: The user query
        reflection_confidence: Confidence score from reflection loop

    Returns:
        True if cache should be used, False to skip cache
    """
    global _cache_metrics

    # Skip cache for very short queries (likely simple lookups)
    if len(query.split()) < 3:
        return False

    # Skip cache if reflection confidence is too low
    if reflection_confidence is not None and reflection_confidence < CACHE_CONFIDENCE_THRESHOLD:
        logger.debug(
            f"Skipping cache: low reflection confidence {reflection_confidence:.2f} < {CACHE_CONFIDENCE_THRESHOLD}"
        )
        _cache_metrics.cache_skips += 1
        return False

    return True


def get_cached_response(
    query: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Retrieve a cached response if available and valid.

    Args:
        query: The user query
        context: Optional context

    Returns:
        (response, metadata) if cache hit, None if miss
    """
    global _cache_metrics, _response_cache

    _cache_metrics.total_queries += 1

    cache_key = generate_cache_key(query, context)

    if cache_key not in _response_cache:
        _cache_metrics.cache_misses += 1
        _cache_metrics.recent_hits.append(0)
        return None

    entry = _response_cache[cache_key]

    # Check if expired
    if entry.is_expired():
        logger.debug(f"Cache entry expired for key {cache_key}")
        del _response_cache[cache_key]
        _cache_metrics.cache_misses += 1
        _cache_metrics.cache_evictions += 1
        _cache_metrics.recent_hits.append(0)
        return None

    # Cache hit
    entry.hit_count += 1
    _cache_metrics.cache_hits += 1
    _cache_metrics.recent_hits.append(1)

    # Update running averages
    n = _cache_metrics.cache_hits
    _cache_metrics.avg_hit_quality = (
        (_cache_metrics.avg_hit_quality * (n - 1) + entry.quality_score) / n
    )
    _cache_metrics.avg_cached_confidence = (
        (_cache_metrics.avg_cached_confidence * (n - 1) + entry.confidence) / n
    )

    metadata = {
        "cache_hit": True,
        "quality_score": entry.quality_score,
        "confidence": entry.confidence,
        "cached_at": entry.timestamp,
        "hit_count": entry.hit_count,
    }

    logger.info(
        f"Cache hit for key {cache_key}, quality={entry.quality_score:.1f}, "
        f"hits={entry.hit_count}"
    )

    return (entry.response, metadata)


def cache_response(
    query: str,
    response: str,
    quality_score: float,
    confidence: float,
    context: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> bool:
    """
    Cache a response if it meets quality thresholds.

    Args:
        query: The user query
        response: The response to cache
        quality_score: Critic quality score (0-100)
        confidence: Reflection confidence (0.0-1.0)
        context: Optional context
        ttl_seconds: Time-to-live in seconds

    Returns:
        True if cached, False if skipped
    """
    global _cache_metrics, _response_cache

    # Only cache high-quality responses
    if quality_score < CACHE_QUALITY_THRESHOLD:
        logger.debug(
            f"Skipping cache: low quality {quality_score:.1f} < {CACHE_QUALITY_THRESHOLD}"
        )
        return False

    # Don't cache if we're at max size (evict LRU first)
    if len(_response_cache) >= CACHE_MAX_SIZE:
        _evict_lru()

    cache_key = generate_cache_key(query, context)

    entry = CachedResponse(
        query_hash=cache_key,
        response=response,
        quality_score=quality_score,
        confidence=confidence,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ttl_seconds=ttl_seconds,
        metadata=context or {},
    )

    _response_cache[cache_key] = entry
    _cache_metrics.cache_writes += 1
    _cache_metrics.recent_qualities.append(quality_score)

    logger.info(
        f"Cached response for key {cache_key}, quality={quality_score:.1f}, "
        f"confidence={confidence:.2f}"
    )

    return True


def _evict_lru() -> None:
    """Evict least-recently-used cache entry."""
    global _response_cache, _cache_metrics

    if not _response_cache:
        return

    # Find entry with lowest hit_count (LRU proxy)
    lru_key = min(_response_cache.keys(), key=lambda k: _response_cache[k].hit_count)

    logger.debug(f"Evicting LRU cache entry: {lru_key}")
    del _response_cache[lru_key]
    _cache_metrics.cache_evictions += 1


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

def clear_cache() -> int:
    """
    Clear all cached responses.

    Returns:
        Number of entries cleared
    """
    global _response_cache

    count = len(_response_cache)
    _response_cache.clear()
    logger.info(f"Cleared {count} cache entries")
    return count


def get_all_cached_entries() -> List[Dict[str, Any]]:
    """Get all cached entries for inspection."""
    return [entry.to_dict() for entry in _response_cache.values()]
