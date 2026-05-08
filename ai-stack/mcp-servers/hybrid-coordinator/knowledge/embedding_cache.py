#!/usr/bin/env python3
"""
Embedding Cache with Redis
Caches embeddings to avoid redundant API calls
"""

import hashlib
import json
import logging
from typing import List, Optional

import redis.asyncio as aioredis

from metrics import EMBEDDING_CACHE_HITS, EMBEDDING_CACHE_MISSES

logger = logging.getLogger("embedding-cache")


class EmbeddingCache:
    """
    Redis-based cache for embeddings

    Features:
    - Cache embeddings by text hash
    - TTL-based expiration (default: 7 days)
    - Batch get/set operations
    - Hit rate tracking
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl_seconds: int = 604800,  # 7 days
        key_prefix: str = "embedding:",
        model_name: str = "",
        cache_epoch: int = 1,
    ):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.model_name = model_name
        self.cache_epoch = cache_epoch

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0
        }

    async def initialize(self, flush_on_model_change: bool = False):
        """Initialize Redis connection"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False  # We'll handle encoding ourselves
            )
            await self.redis.ping()
            logger.info("✓ Embedding cache initialized")

            # Flush legacy keys that lack the model slug in their key format.
            # These were written by an older version of _text_to_key and carry
            # vectors from an unknown embedding space.
            if flush_on_model_change:
                # Legacy keys match the bare prefix with no "m<slug>:" segment.
                # They look like  "embedding:<64-hex-chars>"  (no 'm' after prefix).
                legacy_pattern = f"{self.key_prefix}[^m]*"
                keys = []
                async for key in self.redis.scan_iter(match=legacy_pattern):
                    # Exclude keys that already carry the new model-slug format.
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    suffix = key_str[len(self.key_prefix):]
                    if not suffix.startswith("m"):
                        keys.append(key)
                count = 0
                if keys:
                    count = await self.redis.delete(*keys)
                logger.info("embedding_cache_legacy_keys_flushed count=%d", count)

        except Exception as e:
            logger.error(f"Failed to initialize embedding cache: {e}")
            self.redis = None

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    def _text_to_key(self, text: str, variant_tag: str = "A") -> str:
        """
        Convert text to cache key using hash.

        Key format: <prefix>e<epoch>:m<model_slug>:v<variant>:<text_hash>

        - epoch:      incrementing CACHE_EPOCH invalidates all old entries atomically
        - model_slug: ensures vectors from different embedding models never collide
        - variant:    A/B test tag so variants never share cache entries
        """
        model_slug = hashlib.sha256(self.model_name.encode()).hexdigest()[:16]
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return f"{self.key_prefix}e{self.cache_epoch}:m{model_slug}:v{variant_tag}:{text_hash}"

    async def get(self, text: str, variant_tag: str = "A") -> Optional[List[float]]:
        """
        Get embedding from cache

        Args:
            text: Text to get embedding for
            variant_tag: A/B test variant (default "A")

        Returns:
            Embedding vector or None if not cached
        """
        if not self.redis:
            return None

        try:
            key = self._text_to_key(text, variant_tag)
            cached = await self.redis.get(key)

            if cached:
                self.stats["hits"] += 1
                EMBEDDING_CACHE_HITS.inc()
                # Parse JSON-encoded embedding
                embedding = json.loads(cached)
                logger.debug(f"Cache hit for text (len={len(text)})")
                return embedding
            else:
                self.stats["misses"] += 1
                EMBEDDING_CACHE_MISSES.inc()
                logger.debug(f"Cache miss for text (len={len(text)})")
                return None

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error getting embedding from cache: {e}")
            return None

    async def set(self, text: str, embedding: List[float], variant_tag: str = "A") -> bool:
        """
        Set embedding in cache

        Args:
            text: Text that was embedded
            embedding: Embedding vector
            variant_tag: A/B test variant (default "A")

        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            return False

        try:
            key = self._text_to_key(text, variant_tag)
            # Store as JSON
            value = json.dumps(embedding)
            await self.redis.setex(key, self.ttl_seconds, value)
            self.stats["sets"] += 1
            logger.debug(f"Cached embedding for text (len={len(text)})")
            return True

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error setting embedding in cache: {e}")
            return False

    async def get_many(self, texts: List[str], variant_tag: str = "A") -> List[Optional[List[float]]]:
        """
        Get multiple embeddings from cache

        Args:
            texts: List of texts to get embeddings for
            variant_tag: A/B test variant (default "A")

        Returns:
            List of embeddings (None for cache misses)
        """
        if not self.redis:
            return [None] * len(texts)

        try:
            keys = [self._text_to_key(text, variant_tag) for text in texts]
            cached_values = await self.redis.mget(keys)

            embeddings = []
            for value in cached_values:
                if value:
                    self.stats["hits"] += 1
                    EMBEDDING_CACHE_HITS.inc()
                    embeddings.append(json.loads(value))
                else:
                    self.stats["misses"] += 1
                    EMBEDDING_CACHE_MISSES.inc()
                    embeddings.append(None)

            return embeddings

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error getting multiple embeddings from cache: {e}")
            return [None] * len(texts)

    async def set_many(self, texts: List[str], embeddings: List[List[float]], variant_tag: str = "A") -> int:
        """
        Set multiple embeddings in cache

        Args:
            texts: List of texts
            embeddings: List of embeddings
            variant_tag: A/B test variant (default "A")

        Returns:
            Number of successfully cached embeddings
        """
        if not self.redis or len(texts) != len(embeddings):
            return 0

        try:
            # Use pipeline for efficiency
            pipeline = self.redis.pipeline()

            for text, embedding in zip(texts, embeddings):
                key = self._text_to_key(text, variant_tag)
                value = json.dumps(embedding)
                pipeline.setex(key, self.ttl_seconds, value)

            await pipeline.execute()
            self.stats["sets"] += len(texts)
            logger.debug(f"Cached {len(texts)} embeddings")
            return len(texts)

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error setting multiple embeddings in cache: {e}")
            return 0

    async def delete(self, text: str) -> bool:
        """
        Delete embedding from cache

        Args:
            text: Text to delete embedding for

        Returns:
            True if deleted, False otherwise
        """
        if not self.redis:
            return False

        try:
            key = self._text_to_key(text)
            await self.redis.delete(key)
            return True

        except Exception as e:
            logger.error(f"Error deleting embedding from cache: {e}")
            return False

    async def clear_all(self) -> int:
        """
        Clear all embeddings from cache

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            # Find all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = []

            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} embeddings from cache")
                return deleted
            else:
                return 0

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with hits, misses, hit_rate, sets, errors
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate
        }

    async def get_cache_size(self) -> int:
        """
        Get number of cached embeddings

        Returns:
            Number of keys in cache
        """
        if not self.redis:
            return 0

        try:
            pattern = f"{self.key_prefix}*"
            count = 0

            async for _ in self.redis.scan_iter(match=pattern):
                count += 1

            return count

        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0
