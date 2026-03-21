"""
Search Performance API Routes.

Provides endpoints for query performance metrics, cache statistics,
profiling data, and performance optimization controls.

Endpoints:
- GET  /api/search/performance/metrics - Get performance metrics
- GET  /api/search/performance/slow-queries - List slow queries
- GET  /api/search/cache/stats - Cache hit ratios and stats
- POST /api/search/cache/warm - Trigger cache warming
- POST /api/search/cache/clear - Clear cache (admin)
- GET  /api/search/performance/profile - Query profiling data
- GET  /api/search/performance/recommendations - Optimization suggestions
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search-performance"])


# Global instances (initialized by main app)
vector_optimizer = None
query_cache = None
query_batcher = None
embedding_optimizer = None
query_profiler = None


class CacheWarmRequest(BaseModel):
    """Request to warm cache with specific queries."""

    queries: Optional[List[Dict[str, Any]]] = None
    use_common_queries: bool = True


class CacheClearRequest(BaseModel):
    """Request to clear cache."""

    pattern: Optional[str] = None
    confirm: bool = False


@router.get("/performance/metrics")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get comprehensive performance metrics.

    Returns:
        Performance metrics from all optimization components
    """
    metrics = {
        "status": "ok",
        "timestamp": None,  # Add timestamp
    }

    if vector_optimizer:
        metrics["vector_search"] = vector_optimizer.get_metrics()

    if query_cache:
        metrics["cache"] = query_cache.get_stats()

    if query_batcher:
        metrics["batching"] = query_batcher.get_metrics()

    if embedding_optimizer:
        metrics["embeddings"] = embedding_optimizer.get_metrics()

    if query_profiler:
        metrics["profiler"] = query_profiler.get_metrics()

    return metrics


@router.get("/performance/slow-queries")
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """
    Get recent slow queries for analysis.

    Args:
        limit: Maximum number of slow queries to return

    Returns:
        List of slow queries with timing breakdowns
    """
    if not query_profiler:
        raise HTTPException(status_code=503, detail="Query profiler not available")

    slow_queries = query_profiler.get_slow_queries(limit=limit)

    return {
        "slow_queries": slow_queries,
        "count": len(slow_queries),
        "threshold_ms": query_profiler.config.slow_query_threshold_ms,
    }


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache hit ratios and statistics.

    Returns:
        Detailed cache statistics
    """
    if not query_cache:
        raise HTTPException(status_code=503, detail="Query cache not available")

    stats = query_cache.get_stats()

    # Add vector cache stats if available
    if vector_optimizer and vector_optimizer.query_cache:
        stats["vector_cache"] = vector_optimizer.query_cache.get_stats()

    # Add embedding cache stats if available
    if embedding_optimizer and embedding_optimizer.cache:
        stats["embedding_cache_size"] = len(embedding_optimizer.cache)

    return stats


@router.post("/cache/warm")
async def warm_cache(request: CacheWarmRequest) -> Dict[str, Any]:
    """
    Trigger cache warming with common queries.

    Args:
        request: Cache warming request with optional queries

    Returns:
        Warming statistics
    """
    if not query_cache:
        raise HTTPException(status_code=503, detail="Query cache not available")

    # Use provided queries or default common queries
    queries = request.queries

    # Warm cache
    stats = await query_cache.warm_cache(queries=queries)

    return {
        "status": "complete",
        "stats": stats,
    }


@router.post("/cache/clear")
async def clear_cache(request: CacheClearRequest) -> Dict[str, Any]:
    """
    Clear cache entries (admin operation).

    Args:
        request: Cache clear request with optional pattern

    Returns:
        Number of entries cleared
    """
    if not query_cache:
        raise HTTPException(status_code=503, detail="Query cache not available")

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Cache clear requires confirmation (set confirm=true)",
        )

    count = await query_cache.clear(pattern=request.pattern)

    return {
        "status": "cleared",
        "entries_cleared": count,
        "pattern": request.pattern,
    }


@router.get("/performance/profile")
async def get_profiling_data(
    include_slow_queries: bool = Query(True),
) -> Dict[str, Any]:
    """
    Get detailed query profiling data.

    Args:
        include_slow_queries: Whether to include slow query details

    Returns:
        Profiling data with component breakdowns
    """
    if not query_profiler:
        raise HTTPException(status_code=503, detail="Query profiler not available")

    data = {
        "metrics": query_profiler.get_metrics(),
        "percentiles": query_profiler.get_percentiles(),
    }

    if include_slow_queries:
        data["slow_queries"] = query_profiler.get_slow_queries(limit=20)

    # Add component baselines
    data["component_baselines"] = {
        component: {
            "count": len(durations),
            "avg_ms": sum(durations) / len(durations) if durations else 0.0,
            "min_ms": min(durations) if durations else 0.0,
            "max_ms": max(durations) if durations else 0.0,
        }
        for component, durations in query_profiler.component_baselines.items()
    }

    return data


@router.get("/performance/recommendations")
async def get_optimization_recommendations() -> Dict[str, Any]:
    """
    Get AI-powered optimization recommendations.

    Returns:
        List of actionable optimization recommendations
    """
    recommendations = []

    # Analyze cache performance
    if query_cache:
        cache_stats = query_cache.get_stats()
        hit_rate = cache_stats.get("overall_hit_rate", 0.0)

        if hit_rate < 0.4:
            recommendations.append({
                "component": "cache",
                "severity": "high",
                "issue": f"Low cache hit rate: {hit_rate:.1%}",
                "recommendation": "Consider increasing cache size or TTL, or review query patterns",
                "action": "increase_cache_size",
            })
        elif hit_rate < 0.6:
            recommendations.append({
                "component": "cache",
                "severity": "medium",
                "issue": f"Moderate cache hit rate: {hit_rate:.1%}",
                "recommendation": "Cache hit rate could be improved with cache warming",
                "action": "enable_cache_warming",
            })

    # Analyze query profiler
    if query_profiler:
        metrics = query_profiler.get_metrics()
        percentiles = query_profiler.get_percentiles()

        if percentiles.get("p95", 0) > 500:
            recommendations.append({
                "component": "query_performance",
                "severity": "high",
                "issue": f"High P95 latency: {percentiles['p95']:.1f}ms",
                "recommendation": "Review slow queries and consider optimizing HNSW parameters",
                "action": "optimize_hnsw_config",
            })

        if metrics.get("regressions_detected", 0) > 5:
            recommendations.append({
                "component": "performance",
                "severity": "medium",
                "issue": f"{metrics['regressions_detected']} regressions detected",
                "recommendation": "Investigate recent changes that may have degraded performance",
                "action": "review_recent_changes",
            })

    # Analyze batching efficiency
    if query_batcher:
        batch_metrics = query_batcher.get_metrics()
        efficiency = batch_metrics.get("avg_efficiency", 0.0)

        if efficiency < 0.6:
            recommendations.append({
                "component": "batching",
                "severity": "medium",
                "issue": f"Low batch efficiency: {efficiency:.1%}",
                "recommendation": "Consider adjusting batch size or wait times",
                "action": "tune_batch_params",
            })

    return {
        "recommendations": recommendations,
        "count": len(recommendations),
        "high_severity": len([r for r in recommendations if r["severity"] == "high"]),
        "medium_severity": len([r for r in recommendations if r["severity"] == "medium"]),
    }


def init_search_performance(
    vector_opt=None,
    query_c=None,
    query_b=None,
    embedding_opt=None,
    query_prof=None,
) -> None:
    """
    Initialize search performance components.

    Args:
        vector_opt: VectorSearchOptimizer instance
        query_c: QueryCache instance
        query_b: QueryBatcher instance
        embedding_opt: EmbeddingOptimizer instance
        query_prof: QueryProfiler instance
    """
    global vector_optimizer, query_cache, query_batcher, embedding_optimizer, query_profiler

    vector_optimizer = vector_opt
    query_cache = query_c
    query_batcher = query_b
    embedding_optimizer = embedding_opt
    query_profiler = query_prof

    logger.info("Search performance API routes initialized")
