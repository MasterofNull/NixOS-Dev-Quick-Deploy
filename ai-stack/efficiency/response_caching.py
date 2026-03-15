#!/usr/bin/env python3
"""
Response Caching & Deduplication Framework

Semantic caching and deduplication to minimize redundant LLM calls.
Part of Phase 7 Batch 7.3: Response Caching & Deduplication

Key Features:
- Semantic caching for similar queries
- Response deduplication
- Cache warming based on usage patterns
- Smart cache invalidation policies
- Cache hit rate optimization

Reference: GPTCache (https://github.com/zilliztech/GPTCache)
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CachePolicy(Enum):
    """Cache invalidation policies"""
    TTL = "time_to_live"  # Time-based expiration
    LRU = "least_recently_used"  # Evict least recently used
    LFU = "least_frequently_used"  # Evict least frequently used
    ADAPTIVE = "adaptive"  # Combine TTL + LRU


@dataclass
class CacheEntry:
    """Single cache entry"""
    key: str
    query: str
    response: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    tokens_saved: int = 0
    ttl_seconds: int = 3600
    metadata: Dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry is expired"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def access(self):
        """Record cache access"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_saved: int = 0
    avg_hit_rate: float = 0.0
    avg_latency_ms: float = 0.0


class SemanticCache:
    """Semantic caching with similarity matching"""

    def __init__(
        self,
        max_size: int = 1000,
        policy: CachePolicy = CachePolicy.ADAPTIVE,
        similarity_threshold: float = 0.85,
    ):
        self.max_size = max_size
        self.policy = policy
        self.similarity_threshold = similarity_threshold

        self.cache: Dict[str, CacheEntry] = {}
        self.query_embeddings: Dict[str, List[float]] = {}  # Simplified embeddings

        self.stats = CacheStats()

        logger.info(
            f"Semantic Cache initialized: "
            f"max_size={max_size}, policy={policy.value}, "
            f"similarity_threshold={similarity_threshold}"
        )

    def get(
        self,
        query: str,
        exact_match: bool = False,
    ) -> Optional[Any]:
        """Get cached response for query"""
        self.stats.total_requests += 1
        start_time = time.time()

        # Try exact match first
        query_hash = self._hash_query(query)
        if query_hash in self.cache:
            entry = self.cache[query_hash]

            if not entry.is_expired():
                entry.access()
                self.stats.cache_hits += 1
                self.stats.tokens_saved += entry.tokens_saved

                logger.debug(f"Cache hit (exact): {query_hash}")
                return entry.response

            # Remove expired entry
            del self.cache[query_hash]

        # Try semantic similarity match (if not exact-only)
        if not exact_match:
            similar_entry = self._find_similar(query)
            if similar_entry:
                similar_entry.access()
                self.stats.cache_hits += 1
                self.stats.tokens_saved += similar_entry.tokens_saved

                logger.debug(f"Cache hit (semantic): {similar_entry.key}")
                return similar_entry.response

        # Cache miss
        self.stats.cache_misses += 1
        logger.debug(f"Cache miss: {query_hash}")

        # Update latency stats
        latency_ms = (time.time() - start_time) * 1000
        self._update_latency(latency_ms)

        return None

    def set(
        self,
        query: str,
        response: Any,
        tokens_saved: int = 0,
        ttl_seconds: int = 3600,
    ):
        """Cache response for query"""
        query_hash = self._hash_query(query)

        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self._evict()

        # Create cache entry
        entry = CacheEntry(
            key=query_hash,
            query=query,
            response=response,
            tokens_saved=tokens_saved,
            ttl_seconds=ttl_seconds,
        )

        self.cache[query_hash] = entry

        # Store query embedding (simplified)
        self.query_embeddings[query_hash] = self._create_embedding(query)

        logger.debug(f"Cached response: {query_hash}")

    def _hash_query(self, query: str) -> str:
        """Hash query for exact matching"""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _create_embedding(self, text: str) -> List[float]:
        """Create simple text embedding (bag-of-words representation)"""
        # Very simplified: term frequency vector
        terms = text.lower().split()
        vocab = sorted(set(terms))

        # Create frequency vector
        embedding = []
        for term in vocab[:100]:  # Limit to top 100 terms
            freq = terms.count(term) / len(terms)
            embedding.append(freq)

        # Pad to fixed size
        while len(embedding) < 100:
            embedding.append(0.0)

        return embedding[:100]

    def _find_similar(self, query: str) -> Optional[CacheEntry]:
        """Find semantically similar cached query"""
        query_embedding = self._create_embedding(query)

        best_similarity = 0.0
        best_entry = None

        for key, cached_embedding in self.query_embeddings.items():
            entry = self.cache.get(key)
            if not entry or entry.is_expired():
                continue

            # Calculate cosine similarity (simplified)
            similarity = self._cosine_similarity(query_embedding, cached_embedding)

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_entry = entry

        return best_entry

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity"""
        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def _evict(self):
        """Evict cache entry based on policy"""
        if not self.cache:
            return

        if self.policy == CachePolicy.TTL:
            # Remove oldest entry
            oldest_key = min(self.cache.items(), key=lambda x: x[1].created_at)[0]
            del self.cache[oldest_key]
            if oldest_key in self.query_embeddings:
                del self.query_embeddings[oldest_key]

        elif self.policy == CachePolicy.LRU:
            # Remove least recently used
            lru_key = min(self.cache.items(), key=lambda x: x[1].last_accessed)[0]
            del self.cache[lru_key]
            if lru_key in self.query_embeddings:
                del self.query_embeddings[lru_key]

        elif self.policy == CachePolicy.LFU:
            # Remove least frequently used
            lfu_key = min(self.cache.items(), key=lambda x: x[1].access_count)[0]
            del self.cache[lfu_key]
            if lfu_key in self.query_embeddings:
                del self.query_embeddings[lfu_key]

        else:  # ADAPTIVE
            # Combine recency and frequency
            scores = {}
            for key, entry in self.cache.items():
                age = (datetime.now() - entry.last_accessed).total_seconds()
                score = entry.access_count / (age + 1)  # Higher is better
                scores[key] = score

            worst_key = min(scores.items(), key=lambda x: x[1])[0]
            del self.cache[worst_key]
            if worst_key in self.query_embeddings:
                del self.query_embeddings[worst_key]

        logger.debug(f"Evicted cache entry (policy={self.policy.value})")

    def _update_latency(self, latency_ms: float):
        """Update average latency"""
        # Exponential moving average
        if self.stats.avg_latency_ms == 0:
            self.stats.avg_latency_ms = latency_ms
        else:
            self.stats.avg_latency_ms = 0.9 * self.stats.avg_latency_ms + 0.1 * latency_ms

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        if self.stats.total_requests > 0:
            self.stats.avg_hit_rate = self.stats.cache_hits / self.stats.total_requests

        return self.stats

    def clear_expired(self):
        """Clear all expired entries"""
        expired = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]

        for key in expired:
            del self.cache[key]
            if key in self.query_embeddings:
                del self.query_embeddings[key]

        if expired:
            logger.info(f"Cleared {len(expired)} expired cache entries")


class ResponseDeduplicator:
    """Deduplicate responses"""

    def __init__(self):
        self.response_hashes: Dict[str, List[str]] = defaultdict(list)
        logger.info("Response Deduplicator initialized")

    def is_duplicate(self, response: str) -> bool:
        """Check if response is duplicate"""
        response_hash = self._hash_response(response)

        # Check for exact duplicate
        if response_hash in self.response_hashes:
            logger.debug(f"Duplicate response detected: {response_hash}")
            return True

        # Check for near-duplicate (simplified)
        response_words = set(response.lower().split())

        for existing_hash, existing_words in self.response_hashes.items():
            # Calculate Jaccard similarity
            if isinstance(existing_words, list) and existing_words:
                existing_set = set(existing_words[0].lower().split())
                similarity = len(response_words & existing_set) / len(response_words | existing_set)

                if similarity > 0.9:  # 90% similarity threshold
                    logger.debug(f"Near-duplicate response detected: {similarity:.2%}")
                    return True

        # Not a duplicate - record it
        self.response_hashes[response_hash] = [response]
        return False

    def _hash_response(self, response: str) -> str:
        """Hash response"""
        normalized = response.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class CacheWarmer:
    """Proactive cache warming based on usage patterns"""

    def __init__(self, cache: SemanticCache):
        self.cache = cache
        self.query_patterns: Dict[str, int] = defaultdict(int)
        logger.info("Cache Warmer initialized")

    def record_query(self, query: str):
        """Record query for pattern analysis"""
        # Extract query pattern (simplified)
        pattern = self._extract_pattern(query)
        self.query_patterns[pattern] += 1

    def _extract_pattern(self, query: str) -> str:
        """Extract query pattern"""
        # Remove specific values, keep structure
        pattern = query.lower()

        # Replace numbers with placeholder
        pattern = re.sub(r'\d+', '<NUM>', pattern)

        # Replace file paths
        pattern = re.sub(r'/[\w/.-]+', '<PATH>', pattern)

        # Replace quoted strings
        pattern = re.sub(r'"[^"]+"', '<STR>', pattern)

        return pattern

    def identify_popular_patterns(self, min_count: int = 5) -> List[Tuple[str, int]]:
        """Identify popular query patterns"""
        popular = [
            (pattern, count)
            for pattern, count in self.query_patterns.items()
            if count >= min_count
        ]

        popular.sort(reverse=True, key=lambda x: x[1])

        logger.info(f"Identified {len(popular)} popular query patterns")
        return popular

    async def warm_cache(
        self,
        query_generator: Callable[[str], str],
        llm_client: Any,
    ):
        """Warm cache with popular patterns"""
        popular = self.identify_popular_patterns()

        if not popular:
            logger.info("No patterns to warm")
            return

        warmed_count = 0

        for pattern, count in popular[:10]:  # Top 10 patterns
            # Generate representative query
            query = query_generator(pattern)

            # Check if already cached
            if self.cache.get(query, exact_match=False):
                continue

            # Query LLM and cache
            try:
                # In production, would call actual LLM
                response = f"Warmed response for pattern: {pattern}"
                self.cache.set(query, response, tokens_saved=100)
                warmed_count += 1

                await asyncio.sleep(0.1)  # Rate limiting

            except Exception as e:
                logger.error(f"Cache warming failed for pattern {pattern}: {e}")

        logger.info(f"Warmed cache with {warmed_count} entries")


class CacheOptimizer:
    """Optimize cache performance"""

    def __init__(self, cache: SemanticCache):
        self.cache = cache
        logger.info("Cache Optimizer initialized")

    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze cache performance"""
        stats = self.cache.get_stats()

        analysis = {
            "hit_rate": stats.avg_hit_rate,
            "total_requests": stats.total_requests,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
            "tokens_saved": stats.tokens_saved,
            "avg_latency_ms": stats.avg_latency_ms,
            "cache_size": len(self.cache.cache),
            "recommendations": [],
        }

        # Generate recommendations
        if stats.avg_hit_rate < 0.3:
            analysis["recommendations"].append(
                "Low hit rate (<30%). Consider increasing cache size or lowering similarity threshold."
            )

        if stats.avg_hit_rate > 0.8:
            analysis["recommendations"].append(
                "High hit rate (>80%). Cache is performing well!"
            )

        if len(self.cache.cache) >= self.cache.max_size * 0.9:
            analysis["recommendations"].append(
                "Cache nearly full (>90%). Consider increasing max_size or adjusting eviction policy."
            )

        if stats.avg_latency_ms > 10:
            analysis["recommendations"].append(
                f"High cache lookup latency ({stats.avg_latency_ms:.1f}ms). Consider optimizing similarity search."
            )

        return analysis

    def suggest_policy(self) -> CachePolicy:
        """Suggest optimal cache policy"""
        stats = self.cache.get_stats()

        # Analyze access patterns
        if not self.cache.cache:
            return CachePolicy.ADAPTIVE

        # Calculate recency vs frequency
        avg_access_count = sum(e.access_count for e in self.cache.cache.values()) / len(self.cache.cache)

        if avg_access_count > 5:
            # High reuse - LFU is good
            return CachePolicy.LFU
        elif avg_access_count < 2:
            # Low reuse - LRU is better
            return CachePolicy.LRU
        else:
            # Mixed - ADAPTIVE is best
            return CachePolicy.ADAPTIVE


async def main():
    """Test response caching framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Response Caching & Deduplication Test")
    logger.info("=" * 60)

    # Test 1: Semantic Cache
    logger.info("\n1. Semantic Cache Test:")
    cache = SemanticCache(max_size=10, similarity_threshold=0.8)

    # Cache some responses
    cache.set("how to fix SQL injection", "Use parameterized queries", tokens_saved=50)
    cache.set("best practices for security", "Use mTLS and encryption", tokens_saved=60)
    cache.set("implement rate limiting", "Use token bucket algorithm", tokens_saved=55)

    # Try to retrieve
    queries = [
        "how to fix SQL injection",  # Exact match
        "fix SQL injection vulnerability",  # Similar
        "what is quantum computing",  # No match
    ]

    for query in queries:
        result = cache.get(query)
        logger.info(f"  Query: '{query}' -> {'HIT' if result else 'MISS'}")

    # Test 2: Cache Stats
    logger.info("\n2. Cache Statistics:")
    stats = cache.get_stats()
    logger.info(f"  Hit rate: {stats.avg_hit_rate:.1%}")
    logger.info(f"  Total requests: {stats.total_requests}")
    logger.info(f"  Tokens saved: {stats.tokens_saved}")
    logger.info(f"  Avg latency: {stats.avg_latency_ms:.2f}ms")

    # Test 3: Response Deduplication
    logger.info("\n3. Response Deduplication Test:")
    deduplicator = ResponseDeduplicator()

    responses = [
        "Use parameterized queries to prevent SQL injection",
        "Use parameterized queries to prevent SQL injection",  # Exact duplicate
        "Parameterized queries prevent SQL injection",  # Near duplicate
        "Enable HTTPS for secure communication",  # Different
    ]

    for i, response in enumerate(responses):
        is_dup = deduplicator.is_duplicate(response)
        logger.info(f"  Response {i+1}: {'DUPLICATE' if is_dup else 'UNIQUE'}")

    # Test 4: Cache Warming
    logger.info("\n4. Cache Warming Test:")
    warmer = CacheWarmer(cache)

    # Record some queries
    for _ in range(10):
        warmer.record_query("analyze code in <PATH>")
    for _ in range(7):
        warmer.record_query("fix bug in <PATH>")

    popular = warmer.identify_popular_patterns(min_count=5)
    logger.info(f"  Popular patterns:")
    for pattern, count in popular:
        logger.info(f"    {pattern}: {count} occurrences")

    # Test 5: Cache Optimization
    logger.info("\n5. Cache Optimization:")
    optimizer = CacheOptimizer(cache)

    analysis = optimizer.analyze_performance()
    logger.info(f"  Hit rate: {analysis['hit_rate']:.1%}")
    logger.info(f"  Cache size: {analysis['cache_size']}/{cache.max_size}")
    logger.info(f"  Recommendations:")
    for rec in analysis["recommendations"]:
        logger.info(f"    - {rec}")

    suggested_policy = optimizer.suggest_policy()
    logger.info(f"  Suggested policy: {suggested_policy.value}")


if __name__ == "__main__":
    asyncio.run(main())
