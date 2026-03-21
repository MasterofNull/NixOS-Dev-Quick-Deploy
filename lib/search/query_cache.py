#!/usr/bin/env python3
"""
Multi-tier Query Result Caching System.

Implements in-memory + Redis caching with smart cache keys, TTL-based invalidation,
hit ratio tracking, partial result caching, cache warming, and LRU eviction.

Target Performance:
- Cache hit ratio > 60% for common queries
- Cache lookup < 5ms for in-memory, < 20ms for Redis
- Reduce query routing P95 from 2000ms to <500ms

Usage:
    from lib.search.query_cache import QueryCache

    cache = QueryCache(
        redis_url="redis://localhost:6379",
        config=config
    )
    await cache.initialize()

    # Check cache
    result = await cache.get("query text", mode="semantic")
    if result is None:
        # Execute query and cache
        result = await execute_query(...)
        await cache.set("query text", result, mode="semantic")
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Query cache configuration."""

    # In-memory cache
    memory_cache_size: int = 1000  # Number of entries
    memory_ttl_seconds: int = 300  # 5 minutes

    # Redis cache
    redis_cache_enabled: bool = True
    redis_ttl_seconds: int = 3600  # 1 hour
    redis_key_prefix: str = "query_cache:"

    # Partial result caching
    enable_partial_cache: bool = True
    partial_cache_min_size: int = 5  # Cache if at least this many results

    # Cache warming
    enable_warming: bool = True
    common_queries_file: Optional[str] = None

    # Eviction
    lru_eviction: bool = True


class InMemoryCache:
    """Fast in-memory LRU cache."""

    def __init__(self, max_size: int, ttl: int):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if available and not expired."""
        if key in self.cache:
            # Check TTL
            if time.time() - self.timestamps[key] < self.ttl:
                self.hits += 1
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            else:
                # Expired, remove
                del self.cache[key]
                del self.timestamps[key]

        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with LRU eviction."""
        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]

        self.cache[key] = value
        self.timestamps[key] = time.time()
        self.cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()
        self.timestamps.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
        }


class QueryCache:
    """
    Multi-tier query result caching system.

    Features:
    - L1 in-memory cache (fast, limited size)
    - L2 Redis cache (slower, larger capacity)
    - Smart cache key generation with normalization
    - TTL-based cache invalidation
    - Hit ratio tracking and metrics
    - Partial result caching
    - Cache warming for common queries
    - LRU eviction policy
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        config: Optional[CacheConfig] = None,
    ):
        self.redis_url = redis_url
        self.config = config or CacheConfig()
        self.redis: Optional[aioredis.Redis] = None

        # L1 in-memory cache
        self.memory_cache = InMemoryCache(
            max_size=self.config.memory_cache_size,
            ttl=self.config.memory_ttl_seconds,
        )

        # Metrics
        self.metrics = {
            "memory_hits": 0,
            "redis_hits": 0,
            "total_misses": 0,
            "sets": 0,
            "deletes": 0,
            "cache_warming_runs": 0,
        }

        logger.info(
            f"QueryCache initialized: memory_size={self.config.memory_cache_size}, "
            f"redis_enabled={self.config.redis_cache_enabled}"
        )

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if not self.config.redis_cache_enabled:
            logger.info("Redis cache disabled, using memory cache only")
            return

        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("Redis cache connection established")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis cache connection closed")

    def _normalize_query(self, query: str, mode: str) -> str:
        """
        Normalize query for consistent cache keys.

        - Lowercase
        - Strip whitespace
        - Remove punctuation
        - Sort tokens for order-independence
        """
        import re

        # Lowercase and strip
        normalized = query.lower().strip()

        # Remove punctuation except spaces
        normalized = re.sub(r"[^\w\s]", " ", normalized)

        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized)

        # Sort tokens for order-independence (optional, may not be desired)
        # tokens = sorted(normalized.split())
        # normalized = " ".join(tokens)

        return normalized

    def _make_cache_key(
        self,
        query: str,
        mode: str = "auto",
        collections: Optional[List[str]] = None,
        limit: int = 10,
    ) -> str:
        """
        Generate cache key from query parameters.

        Args:
            query: Query text
            mode: Search mode (auto, semantic, hybrid, etc.)
            collections: Target collections
            limit: Result limit

        Returns:
            Cache key string
        """
        # Normalize query
        normalized_query = self._normalize_query(query, mode)

        # Create stable representation of parameters
        params = {
            "query": normalized_query,
            "mode": mode,
            "collections": sorted(collections) if collections else [],
            "limit": limit,
        }

        # Hash parameters
        params_str = json.dumps(params, sort_keys=True)
        key_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]

        return f"{self.config.redis_key_prefix}{mode}:{key_hash}"

    async def get(
        self,
        query: str,
        mode: str = "auto",
        collections: Optional[List[str]] = None,
        limit: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached query result.

        Args:
            query: Query text
            mode: Search mode
            collections: Target collections
            limit: Result limit

        Returns:
            Cached result or None if not found
        """
        cache_key = self._make_cache_key(query, mode, collections, limit)

        # Try L1 memory cache first
        cached = self.memory_cache.get(cache_key)
        if cached is not None:
            self.metrics["memory_hits"] += 1
            logger.debug(f"Memory cache hit: {cache_key[:32]}...")
            return cached

        # Try L2 Redis cache
        if self.redis:
            try:
                cached_json = await self.redis.get(cache_key)
                if cached_json:
                    self.metrics["redis_hits"] += 1
                    cached = json.loads(cached_json)

                    # Promote to memory cache
                    self.memory_cache.set(cache_key, cached)

                    logger.debug(f"Redis cache hit: {cache_key[:32]}...")
                    return cached
            except Exception as e:
                logger.warning(f"Redis cache get error: {e}")

        # Cache miss
        self.metrics["total_misses"] += 1
        logger.debug(f"Cache miss: {cache_key[:32]}...")
        return None

    async def set(
        self,
        query: str,
        result: Dict[str, Any],
        mode: str = "auto",
        collections: Optional[List[str]] = None,
        limit: int = 10,
    ) -> None:
        """
        Cache query result.

        Args:
            query: Query text
            result: Query result to cache
            mode: Search mode
            collections: Target collections
            limit: Result limit
        """
        cache_key = self._make_cache_key(query, mode, collections, limit)

        # Check partial result caching
        if self.config.enable_partial_cache:
            result_count = len(result.get("combined_results", []))
            if result_count < self.config.partial_cache_min_size:
                logger.debug(
                    f"Skipping cache (result too small): {result_count} < "
                    f"{self.config.partial_cache_min_size}"
                )
                return

        # Set in memory cache
        self.memory_cache.set(cache_key, result)

        # Set in Redis cache
        if self.redis:
            try:
                result_json = json.dumps(result)
                await self.redis.setex(
                    cache_key,
                    self.config.redis_ttl_seconds,
                    result_json,
                )
                logger.debug(f"Cached result: {cache_key[:32]}...")
            except Exception as e:
                logger.warning(f"Redis cache set error: {e}")

        self.metrics["sets"] += 1

    async def delete(
        self,
        query: str,
        mode: str = "auto",
        collections: Optional[List[str]] = None,
        limit: int = 10,
    ) -> bool:
        """
        Delete cached query result.

        Args:
            query: Query text
            mode: Search mode
            collections: Target collections
            limit: Result limit

        Returns:
            True if deleted, False otherwise
        """
        cache_key = self._make_cache_key(query, mode, collections, limit)

        # Delete from memory cache
        deleted_memory = self.memory_cache.delete(cache_key)

        # Delete from Redis cache
        deleted_redis = False
        if self.redis:
            try:
                deleted_redis = bool(await self.redis.delete(cache_key))
            except Exception as e:
                logger.warning(f"Redis cache delete error: {e}")

        self.metrics["deletes"] += 1
        return deleted_memory or deleted_redis

    async def clear(self, pattern: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            pattern: Optional pattern to match keys (Redis only)

        Returns:
            Number of keys deleted
        """
        count = 0

        # Clear memory cache
        self.memory_cache.clear()
        count += len(self.memory_cache.cache)

        # Clear Redis cache
        if self.redis:
            try:
                if pattern:
                    # Delete matching keys
                    pattern_full = f"{self.config.redis_key_prefix}{pattern}"
                    keys = []
                    async for key in self.redis.scan_iter(match=pattern_full):
                        keys.append(key)
                    if keys:
                        count += await self.redis.delete(*keys)
                else:
                    # Delete all cache keys
                    pattern_full = f"{self.config.redis_key_prefix}*"
                    keys = []
                    async for key in self.redis.scan_iter(match=pattern_full):
                        keys.append(key)
                    if keys:
                        count += await self.redis.delete(*keys)
            except Exception as e:
                logger.error(f"Redis cache clear error: {e}")

        logger.info(f"Cleared {count} cache entries")
        return count

    async def warm_cache(
        self,
        queries: Optional[List[Dict[str, Any]]] = None,
        execute_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Warm cache with common queries.

        Args:
            queries: List of query dicts with 'query', 'mode', 'collections', 'limit'
            execute_fn: Async function to execute queries if not cached

        Returns:
            Warming statistics
        """
        if not self.config.enable_warming:
            logger.info("Cache warming disabled")
            return {"status": "disabled"}

        if not queries:
            # Load from default queries if configured
            if self.config.common_queries_file:
                # TODO: Load from file
                pass
            queries = []

        if not queries:
            logger.warning("No queries provided for cache warming")
            return {"status": "no_queries"}

        logger.info(f"Starting cache warming with {len(queries)} queries...")
        start_time = time.time()

        warmed = 0
        already_cached = 0
        errors = []

        for query_spec in queries:
            try:
                # Check if already cached
                cached = await self.get(
                    query=query_spec.get("query", ""),
                    mode=query_spec.get("mode", "auto"),
                    collections=query_spec.get("collections"),
                    limit=query_spec.get("limit", 10),
                )

                if cached:
                    already_cached += 1
                elif execute_fn:
                    # Execute and cache
                    result = await execute_fn(query_spec)
                    await self.set(
                        query=query_spec.get("query", ""),
                        result=result,
                        mode=query_spec.get("mode", "auto"),
                        collections=query_spec.get("collections"),
                        limit=query_spec.get("limit", 10),
                    )
                    warmed += 1
            except Exception as e:
                errors.append({
                    "query": query_spec.get("query", "")[:50],
                    "error": str(e),
                })
                logger.warning(f"Cache warming error for query: {e}")

        elapsed = time.time() - start_time
        self.metrics["cache_warming_runs"] += 1

        stats = {
            "status": "complete",
            "total_queries": len(queries),
            "warmed": warmed,
            "already_cached": already_cached,
            "errors": len(errors),
            "elapsed_seconds": elapsed,
        }

        logger.info(
            f"Cache warming complete: {warmed} warmed, {already_cached} already cached, "
            f"{len(errors)} errors in {elapsed:.1f}s"
        )

        return stats

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        memory_stats = self.memory_cache.get_stats()

        total_hits = self.metrics["memory_hits"] + self.metrics["redis_hits"]
        total_requests = total_hits + self.metrics["total_misses"]
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "memory_cache": memory_stats,
            "metrics": self.metrics,
            "overall_hit_rate": overall_hit_rate,
            "total_requests": total_requests,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.memory_cache.hits = 0
        self.memory_cache.misses = 0
        self.metrics = {
            "memory_hits": 0,
            "redis_hits": 0,
            "total_misses": 0,
            "sets": 0,
            "deletes": 0,
            "cache_warming_runs": 0,
        }
