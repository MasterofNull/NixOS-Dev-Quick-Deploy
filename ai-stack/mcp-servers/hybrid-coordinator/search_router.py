"""
Search routing module for the hybrid-coordinator.

Provides SearchRouter: unified entry-point for keyword/semantic/hybrid/tree/SQL
search strategies, LLM backend selection, and result reranking.

Extracted from server.py (Phase 6.1 decomposition).

Usage:
    from search_router import SearchRouter
    router = SearchRouter(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        call_breaker_fn=_call_with_breaker,
        check_local_health_fn=_check_local_llm_health,
        wait_for_model_fn=_wait_for_local_model,
        get_local_loading_fn=lambda: _local_llm_loading,
        routing_config=routing_config,
        record_telemetry_fn=record_telemetry_event,
        collections=COLLECTIONS,
    )
    result = await router.route(query, mode="auto")
"""

import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import Config, RoutingConfig
from metrics import AUTONOMY_BUDGET_EXCEEDED, LLM_BACKEND_SELECTIONS, ROUTE_DECISIONS, ROUTE_ERRORS

logger = logging.getLogger("hybrid-coordinator")


# ============================================================================
# Stand-alone utility functions (no server-global dependencies)
# ============================================================================

def looks_like_sql(query: str) -> bool:
    """Return True if *query* looks like a SQL statement."""
    normalized = query.strip().lower()
    if not normalized:
        return False
    sql_start = ("select", "with", "insert", "update", "delete")
    if normalized.startswith(sql_start):
        return True
    if ";" in normalized and (" from " in normalized or " where " in normalized):
        return True
    return False


def normalize_tokens(query: str) -> List[str]:
    """Tokenize *query* and remove stopwords."""
    tokens = re.findall(r"[a-zA-Z0-9_\-]{2,}", query.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "http", "https",
        "you", "your", "are", "was", "were", "can", "could", "should", "would",
    }
    return [t for t in tokens if t not in stopwords]


def payload_matches_tokens(payload: Dict[str, Any], tokens: List[str]) -> Tuple[bool, int]:
    """Return (matched, count) of *tokens* found in *payload* values."""
    if not tokens or not payload:
        return False, 0
    haystacks: List[str] = []
    for value in payload.values():
        if isinstance(value, str):
            haystacks.append(value.lower())
        elif isinstance(value, list):
            haystacks.extend([str(item).lower() for item in value if isinstance(item, (str, int))])
    combined = " ".join(haystacks)
    matches = sum(1 for token in tokens if token in combined)
    return matches > 0, matches


def rerank_combined_results(query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply lightweight lexical+source-aware rerank over merged retrieval results."""
    tokens = normalize_tokens(query)
    reranked: List[Dict[str, Any]] = []
    for item in items:
        payload = item.get("payload") or {}
        text = " ".join(
            str(payload.get(key, ""))
            for key in ("title", "description", "content", "solution", "usage_pattern", "summary")
        ).lower()
        lexical_hits = sum(1 for token in tokens if token in text)
        source_bonus = len(item.get("sources", [])) * 0.1
        base_score = float(item.get("score", 0.0))
        rerank_score = base_score + (0.05 * lexical_hits) + source_bonus
        reranked.append({**item, "rerank_score": round(rerank_score, 4)})
    reranked.sort(key=lambda row: float(row.get("rerank_score", 0.0)), reverse=True)
    return reranked


def tree_expand_queries(query: str, branch_factor: int) -> List[str]:
    """Expand *query* into *branch_factor* variations for tree search."""
    tokens = normalize_tokens(query)
    if not tokens:
        return [query]
    expansions: List[str] = [query]
    top = tokens[: max(1, branch_factor)]
    expansions.extend([f"{query} {token}" for token in top])
    expansions.extend([" ".join(top[:idx + 1]) for idx in range(min(len(top), branch_factor))])
    deduped: List[str] = []
    for item in expansions:
        if item not in deduped:
            deduped.append(item)
    return deduped[: max(1, branch_factor)]


# ============================================================================
# SearchRouter
# ============================================================================

class SearchRouter:
    """Unified search entry-point: keyword / semantic / hybrid / tree / SQL."""

    def __init__(
        self,
        *,
        qdrant_client: Any,
        embed_fn: Callable,
        call_breaker_fn: Callable,
        check_local_health_fn: Callable,
        wait_for_model_fn: Callable,
        get_local_loading_fn: Callable,
        routing_config: RoutingConfig,
        record_telemetry_fn: Callable,
        collections: Dict[str, Any],
    ) -> None:
        self._qdrant = qdrant_client
        self._embed = embed_fn
        self._call_breaker = call_breaker_fn
        self._check_health = check_local_health_fn
        self._wait_for_model = wait_for_model_fn
        self._get_loading = get_local_loading_fn
        self._routing_config = routing_config
        self._record_telemetry = record_telemetry_fn
        self._collections = collections

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    async def select_backend(
        self,
        prompt: str,
        context_quality: float,
        *,
        force_local: bool = False,
        force_remote: bool = False,
        requires_structured_output: bool = False,
    ) -> str:
        """Return 'local' or 'remote' based on confidence, liveness, and overrides."""
        _local_supports_json = os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true"

        if force_local:
            backend, reason, reason_class = "local", "force_local_override", "override"
        elif force_remote:
            backend, reason, reason_class = "remote", "force_remote_override", "override"
        elif requires_structured_output and not _local_supports_json:
            backend, reason, reason_class = "remote", "structured_output_required", "capability"
            logger.info("routing_override reason=structured_output_required local_supports_json=false")
        elif not await self._check_health():
            backend, reason, reason_class = "remote", "local_unhealthy", "health"
        elif self._get_loading():
            ready = await self._wait_for_model(timeout=30.0)
            if ready:
                backend, reason, reason_class = "local", "waited_for_model_load", "loading_queue"
            else:
                backend, reason, reason_class = "remote", "model_loading_queue_full_or_timeout", "loading_queue"
        else:
            threshold = await self._routing_config.get_threshold()
            if context_quality >= threshold:
                backend = "local"
                reason = f"context_quality_above_threshold_{threshold:.3f}"
                reason_class = "confidence"
            else:
                backend = "remote"
                reason = f"context_quality_below_threshold_{threshold:.3f}"
                reason_class = "confidence"

        logger.info(
            "llm_backend_selected backend=%s reason=%s local_confidence_score=%.3f",
            backend, reason, context_quality,
        )
        LLM_BACKEND_SELECTIONS.labels(backend=backend, reason_class=reason_class).inc()
        return backend

    # ------------------------------------------------------------------
    # Hybrid search
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit: int = 5,
        keyword_limit: int = 5,
        score_threshold: float = 0.7,
        keyword_pool: int = 60,
    ) -> Dict[str, Any]:
        """Hybrid search combining vector similarity and keyword matching."""
        collections = collections or list(self._collections.keys())
        query_embedding = await self._embed(query)
        tokens = normalize_tokens(query)

        semantic_results: List[Dict[str, Any]] = []
        keyword_results: List[Dict[str, Any]] = []

        for collection in collections:
            try:
                points = self._call_breaker(
                    "qdrant",
                    lambda col=collection: self._qdrant.query_points(
                        collection_name=col,
                        query=query_embedding,
                        limit=limit,
                        score_threshold=score_threshold,
                    ).points,
                )
                for point in points:
                    semantic_results.append({
                        "collection": collection,
                        "id": str(point.id),
                        "score": point.score,
                        "payload": point.payload,
                        "source": "semantic",
                    })
            except Exception as exc:
                logger.warning("semantic_search_failed collection=%s error=%s", collection, exc)

            if tokens:
                try:
                    points, _ = self._call_breaker(
                        "qdrant",
                        lambda col=collection: self._qdrant.scroll(
                            collection_name=col,
                            limit=keyword_pool,
                            with_payload=True,
                            with_vectors=False,
                        ),
                    )
                    for point in points:
                        matched, score = payload_matches_tokens(point.payload or {}, tokens)
                        if not matched:
                            continue
                        keyword_results.append({
                            "collection": collection,
                            "id": str(point.id),
                            "score": float(score),
                            "payload": point.payload,
                            "source": "keyword",
                        })
                except Exception as exc:
                    logger.warning("keyword_search_failed collection=%s error=%s", collection, exc)

        keyword_results.sort(key=lambda item: item["score"], reverse=True)
        keyword_results = keyword_results[:keyword_limit]

        combined: Dict[str, Dict[str, Any]] = {}
        for item in semantic_results + keyword_results:
            key = f"{item['collection']}:{item['id']}"
            if key not in combined:
                combined[key] = {**item, "sources": {item["source"]}}
            else:
                combined[key]["sources"].add(item["source"])
                combined[key]["score"] = max(combined[key]["score"], item["score"])

        combined_results = []
        for item in combined.values():
            item["sources"] = sorted(item["sources"])
            combined_results.append(item)
        combined_results = rerank_combined_results(query, combined_results)
        max_results = max(1, Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS)
        if len(combined_results) > max_results:
            AUTONOMY_BUDGET_EXCEEDED.labels(budget="retrieval_results").inc()
            combined_results = combined_results[:max_results]

        self._record_telemetry(
            "hybrid_search",
            {"query": query[:200], "collections": collections,
             "semantic_results": len(semantic_results), "keyword_results": len(keyword_results)},
        )
        return {
            "query": query,
            "collections": collections,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
            "combined_results": combined_results,
            "tokens": tokens,
        }

    # ------------------------------------------------------------------
    # Tree search
    # ------------------------------------------------------------------

    async def tree_search(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit: int = 5,
        keyword_limit: int = 5,
        score_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """Branch-and-aggregate retrieval over query expansions."""
        collections = collections or list(self._collections.keys())
        max_depth = max(1, Config.AI_TREE_SEARCH_MAX_DEPTH)
        branch_factor = max(1, Config.AI_TREE_SEARCH_BRANCH_FACTOR)

        branches = [query]
        all_results: Dict[str, Dict[str, Any]] = {}
        branch_runs: List[Dict[str, Any]] = []

        for depth in range(max_depth):
            next_branches: List[str] = []
            for branch_query in branches[:branch_factor]:
                result = await self.hybrid_search(
                    query=branch_query, collections=collections,
                    limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
                )
                branch_runs.append({
                    "depth": depth, "query": branch_query,
                    "semantic_results": len(result.get("semantic_results", [])),
                    "keyword_results": len(result.get("keyword_results", [])),
                })
                for item in result.get("combined_results", []):
                    key = f"{item.get('collection')}:{item.get('id')}"
                    current = all_results.get(key)
                    if current is None or float(item.get("score", 0.0)) > float(current.get("score", 0.0)):
                        all_results[key] = item
                next_branches.extend(tree_expand_queries(branch_query, branch_factor))
            branches = next_branches

        ranked = sorted(all_results.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)
        ranked = ranked[: max(limit, keyword_limit, Config.AI_MEMORY_MAX_RECALL_ITEMS)]
        return {
            "query": query, "search_mode": "tree",
            "depth": max_depth, "branch_factor": branch_factor,
            "combined_results": ranked, "branches": branch_runs,
        }

    # ------------------------------------------------------------------
    # Public unified entry point
    # ------------------------------------------------------------------

    async def route(
        self,
        query: str,
        mode: str = "auto",
        collections: Optional[List[str]] = None,
        limit: int = 5,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Route query to the appropriate search strategy based on *mode*."""
        if mode == "tree" or (mode == "auto" and Config.AI_TREE_SEARCH_ENABLED and len(query) > 20):
            return await self.tree_search(query, collections=collections, limit=limit)
        return await self.hybrid_search(query, collections=collections, limit=limit, **kwargs)
