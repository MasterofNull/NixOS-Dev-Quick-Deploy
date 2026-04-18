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

import asyncio
import logging
import os
import re
import time
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import Config, RoutingConfig
from metrics import AUTONOMY_BUDGET_EXCEEDED, LLM_BACKEND_SELECTIONS, ROUTE_DECISIONS, ROUTE_ERRORS

logger = logging.getLogger("hybrid-coordinator")

_GENERIC_RESULT_LABELS = {
    "feature",
    "documentation",
    "docs",
    "update",
    "change",
    "result",
    "general",
    "unknown",
}
_CONVENTIONAL_COMMIT_PREFIX = re.compile(r"^(feat|fix|docs|chore|refactor|test|perf|ci|build)(\([^)]*\))?:", re.IGNORECASE)
_TECHNICAL_QUERY_TOKENS = {
    "route", "routing", "router", "query", "cache", "cached", "latency", "prompt",
    "context", "retrieval", "rag", "switchboard", "hybrid", "coordinator",
    "llm", "model", "local", "runtime", "http", "server", "search",
}
_TECHNICAL_PATH_TOKENS = {
    "route_handler", "search_router", "http_server", "switchboard", "hybrid-coordinator",
    "llm_client", "semantic_cache", "cache", "routing", "retrieval", "query",
}
_DOC_PATH_MARKERS = (".agent/", ".agents/", "docs/", "README.md", "primer", "workflow")
_VALIDATION_NOISE_TOKENS = (
    "py_compile",
    "pytest",
    "tier0-validation-gate",
    "repo-structure-lint",
    "nix-instantiate",
    "bash -n",
    "aq-qa",
    "validation gate",
    "pre-commit",
    "pre-deploy",
)


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


def _match_count(text: Any, tokens: List[str]) -> int:
    normalized = str(text or "").lower()
    if not normalized or not tokens:
        return 0
    return sum(1 for token in tokens if token in normalized)


def _is_generic_label(text: Any) -> bool:
    normalized = str(text or "").strip().lower()
    return not normalized or normalized in _GENERIC_RESULT_LABELS


def _joined_file_hints(payload: Dict[str, Any]) -> str:
    hints: List[str] = []
    for key in ("file_path", "relative_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            hints.append(value.strip())
    files_changed = payload.get("files_changed")
    if isinstance(files_changed, list):
        for entry in files_changed[:6]:
            if isinstance(entry, str) and entry.strip():
                hints.append(entry.strip())
    return " ".join(hints)


def _payload_content_text(item: Dict[str, Any], payload: Dict[str, Any]) -> str:
    return (
        item.get("content")
        or item.get("text")
        or payload.get("content")
        or payload.get("usage_pattern")
        or payload.get("diff_preview")
        or ""
    )


def _query_is_technical(tokens: List[str]) -> bool:
    return any(token in _TECHNICAL_QUERY_TOKENS for token in tokens)


def _path_category_counts(payload: Dict[str, Any]) -> Tuple[int, int]:
    code_paths = 0
    doc_paths = 0
    seen: List[str] = []
    direct = payload.get("file_path") or payload.get("relative_path")
    if isinstance(direct, str) and direct.strip():
        seen.append(direct.strip())
    files_changed = payload.get("files_changed")
    if isinstance(files_changed, list):
        seen.extend(str(entry).strip() for entry in files_changed[:8] if str(entry).strip())
    for path in seen:
        lowered = path.lower()
        if any(marker.lower() in lowered for marker in _DOC_PATH_MARKERS):
            doc_paths += 1
        elif lowered.endswith((".py", ".nix", ".sh", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml")):
            code_paths += 1
    return code_paths, doc_paths


def _preferred_file_hint(payload: Dict[str, Any]) -> str:
    candidates: List[str] = []
    direct = payload.get("file_path") or payload.get("relative_path")
    if isinstance(direct, str) and direct.strip():
        candidates.append(direct.strip())
    files_changed = payload.get("files_changed")
    if isinstance(files_changed, list):
        candidates.extend(str(entry).strip() for entry in files_changed[:8] if str(entry).strip())
    if not candidates:
        return ""
    for path in candidates:
        lowered = path.lower()
        if not any(marker.lower() in lowered for marker in _DOC_PATH_MARKERS):
            return path
    return candidates[0]


def _validation_noise_count(text: Any) -> int:
    normalized = str(text or "").lower()
    if not normalized:
        return 0
    return sum(1 for token in _VALIDATION_NOISE_TOKENS if token in normalized)


def keyword_match_score(query: str, item: Dict[str, Any]) -> Tuple[bool, float]:
    tokens = normalize_tokens(query)
    payload = item.get("payload") or {}
    if not tokens or not isinstance(payload, dict):
        return False, 0.0

    title_text = (
        payload.get("commit_subject")
        or payload.get("title")
        or payload.get("name")
        or payload.get("skill_name")
        or payload.get("error_type")
        or ""
    )
    path_text = _joined_file_hints(payload)
    preferred_path = _preferred_file_hint(payload).lower()
    summary_text = payload.get("summary") or payload.get("description") or payload.get("solution") or ""
    keyword_hint_text = " ".join(str(part) for part in (payload.get("keyword_hints") or []) if str(part).strip())
    content_text = _payload_content_text(item, payload)

    title_hits = _match_count(title_text, tokens)
    path_hits = _match_count(path_text, tokens)
    summary_hits = _match_count(summary_text, tokens)
    keyword_hint_hits = _match_count(keyword_hint_text, tokens)
    content_hits = _match_count(content_text, tokens)
    lexical_hits = title_hits + path_hits + summary_hits + keyword_hint_hits + content_hits
    if lexical_hits <= 0:
        return False, 0.0

    score = (
        1.2 * path_hits
        + 0.8 * title_hits
        + 0.45 * keyword_hint_hits
        + 0.25 * summary_hits
        + 0.08 * content_hits
    )

    code_paths, doc_paths = _path_category_counts(payload)
    if _query_is_technical(tokens):
        score += 0.35 * code_paths
        if doc_paths and code_paths == 0:
            score -= min(0.9, 0.3 * doc_paths)
        elif doc_paths > code_paths and code_paths > 0:
            score -= min(1.8, 0.55 * doc_paths)
        if any(token in path_text.lower() for token in _TECHNICAL_PATH_TOKENS):
            score += 0.3
        if preferred_path and any(token in preferred_path for token in _TECHNICAL_PATH_TOKENS):
            score += 0.35
        validation_noise = _validation_noise_count(title_text) + _validation_noise_count(summary_text) + _validation_noise_count(content_text)
        if validation_noise:
            score -= min(1.2, 0.3 * validation_noise)

    if _CONVENTIONAL_COMMIT_PREFIX.match(str(title_text or "")) and title_hits == 0 and path_hits == 0:
        score -= 0.12

    return True, max(score, 0.0)


def rerank_combined_results(query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply lightweight lexical+source-aware rerank over merged retrieval results."""
    tokens = normalize_tokens(query)
    reranked: List[Dict[str, Any]] = []
    for item in items:
        payload = item.get("payload") or {}
        title_text = (
            payload.get("commit_subject")
            or payload.get("title")
            or payload.get("name")
            or payload.get("skill_name")
            or payload.get("error_type")
            or ""
        )
        path_text = _joined_file_hints(payload)
        summary_text = payload.get("summary") or payload.get("description") or payload.get("solution") or ""
        content_text = _payload_content_text(item, payload)

        title_hits = _match_count(title_text, tokens)
        path_hits = _match_count(path_text, tokens)
        summary_hits = _match_count(summary_text, tokens)
        content_hits = _match_count(content_text, tokens)
        lexical_hits = title_hits + path_hits + summary_hits + content_hits
        source_bonus = len(item.get("sources", [])) * 0.1
        base_score = float(item.get("score", 0.0))
        field_bonus = (
            (0.32 * path_hits)
            + (0.22 * title_hits)
            + (0.10 * summary_hits)
            + (0.03 * content_hits)
        )
        keyword_bonus = 0.18 if item.get("source") == "keyword" or "keyword" in (item.get("sources") or []) else 0.0
        generic_penalty = 0.0
        if _CONVENTIONAL_COMMIT_PREFIX.match(str(title_text or "")) and title_hits == 0 and path_hits == 0:
            generic_penalty += 0.18
        if _is_generic_label(title_text) and path_hits == 0 and summary_hits == 0:
            generic_penalty += 0.12
        if lexical_hits == 0:
            generic_penalty += 0.10
        rerank_score = base_score + field_bonus + keyword_bonus + source_bonus - generic_penalty
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


async def _await_with_timeout(awaitable: Any, timeout_seconds: float) -> Any:
    """Await *awaitable* with a timeout only when the bound is positive."""
    if timeout_seconds <= 0:
        return await awaitable
    return await asyncio.wait_for(awaitable, timeout=timeout_seconds)


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

    async def _call_breaker_safe(self, name: str, fn: Callable[[], Any]) -> Any:
        """Support sync or async circuit-breaker wrappers."""
        result = self._call_breaker(name, fn)
        if inspect.isawaitable(result):
            return await result
        return result

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

        # Phase 5.1 Optimization: Parallelize collection searches for significant latency reduction
        # Previously sequential searches (~3-5s P95) now run concurrently (~1-2s P95)
        async def _search_collection(collection: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            """Search a single collection for both semantic and keyword results."""
            col_semantic: List[Dict[str, Any]] = []
            col_keyword: List[Dict[str, Any]] = []

            # Semantic search
            try:
                async def _query_points() -> Any:
                    return self._qdrant.query_points(
                        collection_name=collection,
                        query=query_embedding,
                        limit=limit,
                        score_threshold=score_threshold,
                    ).points
                points = await _await_with_timeout(
                    self._call_breaker_safe("qdrant", _query_points),
                    Config.AI_ROUTE_COLLECTION_SEMANTIC_TIMEOUT_SECONDS,
                )
                for point in points:
                    col_semantic.append({
                        "collection": collection,
                        "id": str(point.id),
                        "score": point.score,
                        "payload": point.payload,
                        "source": "semantic",
                    })
            except Exception as exc:
                logger.warning("semantic_search_failed collection=%s error=%s", collection, exc)

            # Keyword search
            if tokens:
                try:
                    async def _scroll_points() -> Any:
                        return self._qdrant.scroll(
                            collection_name=collection,
                            limit=keyword_pool,
                            with_payload=True,
                            with_vectors=False,
                        )
                    points, _ = await _await_with_timeout(
                        self._call_breaker_safe("qdrant", _scroll_points),
                        Config.AI_ROUTE_COLLECTION_KEYWORD_TIMEOUT_SECONDS,
                    )
                    for point in points:
                        matched, score = keyword_match_score(query, {"payload": point.payload or {}, "source": "keyword"})
                        if not matched:
                            continue
                        col_keyword.append({
                            "collection": collection,
                            "id": str(point.id),
                            "score": float(score),
                            "payload": point.payload,
                            "source": "keyword",
                        })
                except Exception as exc:
                    logger.warning("keyword_search_failed collection=%s error=%s", collection, exc)

            return col_semantic, col_keyword

        # Run all collection searches in parallel
        search_tasks = [_search_collection(col) for col in collections]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Aggregate results from parallel searches
        for result in search_results:
            if isinstance(result, Exception):
                logger.warning("parallel_search_failed error=%s", result)
                continue
            col_semantic, col_keyword = result
            semantic_results.extend(col_semantic)
            keyword_results.extend(col_keyword)

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

        ranked = rerank_combined_results(query, list(all_results.values()))
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
