"""
Route search handler for hybrid-coordinator.

Provides route_search: routes queries to SQL/keyword/semantic/tree/hybrid
search strategies, optionally calls the local LLM for generation.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import route_handler
    route_handler.init(
        hybrid_search_fn=hybrid_search,
        tree_search_fn=tree_search,
        select_backend_fn=select_llm_backend,
        discover_fn=capability_discovery.discover,
        format_context_fn=capability_discovery.format_context,
        record_query_gap_fn=_record_query_gap,
        record_telemetry_fn=record_telemetry_event,
        summarize_fn=harness_eval._summarize_results,
        context_compressor_ref=lambda: context_compressor,
        llama_cpp_client_ref=lambda: llama_cpp_client,
        postgres_client_ref=lambda: postgres_client,
        collections=COLLECTIONS,
    )
    result = await route_handler.route_search(query="...", mode="auto")
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import capability_discovery
from config import Config
from metrics import ROUTE_DECISIONS, ROUTE_ERRORS
from search_router import looks_like_sql as _looks_like_sql, normalize_tokens as _normalize_tokens
from query_expansion import QueryExpander
from prompt_injection import PromptInjectionScanner, sanitize_query
import task_classifier

logger = logging.getLogger("hybrid-coordinator")
_injection_scanner = PromptInjectionScanner()

# ---------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------
_hybrid_search: Optional[Callable] = None
_tree_search: Optional[Callable] = None
_select_backend: Optional[Callable] = None
_record_query_gap: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_summarize: Optional[Callable] = None
_context_compressor_ref: Optional[Callable] = None
_llama_cpp_client_ref: Optional[Callable] = None
_switchboard_client_ref: Optional[Callable] = None
_postgres_client_ref: Optional[Callable] = None
_COLLECTIONS: Dict[str, Any] = {}
_query_expander: Optional["QueryExpander"] = None


def init(
    *,
    hybrid_search_fn: Callable,
    tree_search_fn: Callable,
    select_backend_fn: Callable,
    record_query_gap_fn: Callable,
    record_telemetry_fn: Callable,
    summarize_fn: Callable,
    context_compressor_ref: Callable,
    llama_cpp_client_ref: Callable,
    switchboard_client_ref: Callable,
    postgres_client_ref: Callable,
    collections: Dict[str, Any],
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _hybrid_search, _tree_search, _select_backend
    global _record_query_gap, _record_telemetry, _summarize
    global _context_compressor_ref, _llama_cpp_client_ref, _switchboard_client_ref, _postgres_client_ref, _COLLECTIONS
    global _query_expander
    _hybrid_search = hybrid_search_fn
    _tree_search = tree_search_fn
    _select_backend = select_backend_fn
    _record_query_gap = record_query_gap_fn
    _record_telemetry = record_telemetry_fn
    _summarize = summarize_fn
    _context_compressor_ref = context_compressor_ref
    _llama_cpp_client_ref = llama_cpp_client_ref
    _switchboard_client_ref = switchboard_client_ref
    _postgres_client_ref = postgres_client_ref
    _COLLECTIONS = collections
    _query_expander = QueryExpander(Config.LLAMA_CPP_URL)


async def route_search(
    query: str,
    mode: str = "auto",
    prefer_local: bool = True,
    context: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
    generate_response: bool = False,
) -> Dict[str, Any]:
    """Route query to SQL, semantic, keyword, tree, or hybrid search."""
    query = sanitize_query(query)
    start = time.time()
    interaction_id = str(uuid4())
    limit = max(1, min(int(limit), Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS))
    keyword_limit = max(0, min(int(keyword_limit), Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS))
    normalized_mode = (mode or "auto").lower()
    route = normalized_mode

    if normalized_mode == "auto":
        if _looks_like_sql(query):
            route = "sql"
        else:
            token_count = len(_normalize_tokens(query))
            if token_count <= 3:
                route = "keyword"
            elif Config.AI_TREE_SEARCH_ENABLED and token_count >= 8:
                route = "tree"
            else:
                route = "hybrid"

    # Phase 7.1.2 — LLM query expansion on semantic/hybrid routes
    _working_query = query
    _expansion_count = 1
    if (
        Config.AI_LLM_EXPANSION_ENABLED
        and _query_expander is not None
        and route in ("semantic", "hybrid")
    ):
        try:
            _expanded = await asyncio.wait_for(
                _query_expander.expand_with_llm(query, max_expansions=3),
                timeout=Config.AI_LLM_EXPANSION_TIMEOUT_S,
            )
            if len(_expanded) > 1:
                _working_query = _expanded[0]  # primary expansion for the main search
                _expansion_count = len(_expanded)
                logger.info("query_expansions", extra={"count": _expansion_count, "route": route})
        except (asyncio.TimeoutError, Exception) as _exp_err:
            logger.debug("llm_expansion_skipped", extra={"reason": str(_exp_err)})

    results: Dict[str, Any] = {}
    response_text = ""
    _cap_disc: Dict[str, Any] = {
        "decision": "skipped", "reason": "not-evaluated", "cache_hit": False,
        "intent_tags": [], "tools": [], "skills": [], "servers": [], "datasets": [],
    }

    try:
        if Config.AI_CAPABILITY_DISCOVERY_ON_QUERY:
            _cap_disc = await capability_discovery.discover(query)

        if route == "sql":
            response_text = (
                "SQL routing detected. Execution is disabled by default for safety. "
                "Set HYBRID_ALLOW_SQL_EXECUTION=true to enable read-only queries."
            )
        elif route == "keyword":
            hybrid_results = await _hybrid_search(
                query=query, collections=list(_COLLECTIONS.keys()),
                limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
            )
            results = {"keyword_results": hybrid_results["keyword_results"]}
            response_text = _summarize(hybrid_results["keyword_results"])
        elif route == "semantic":
            hybrid_results = await _hybrid_search(
                query=_working_query, collections=list(_COLLECTIONS.keys()),
                limit=limit, keyword_limit=0, score_threshold=score_threshold,
            )
            results = {"semantic_results": hybrid_results["semantic_results"]}
            response_text = _summarize(hybrid_results["semantic_results"])
        elif route == "tree":
            tree_results = await _tree_search(
                query=query, collections=list(_COLLECTIONS.keys()),
                limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
            )
            results = tree_results
            response_text = _summarize(tree_results["combined_results"])
        else:
            hybrid_results = await _hybrid_search(
                query=_working_query, collections=list(_COLLECTIONS.keys()),
                limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
            )
            results = hybrid_results
            response_text = _summarize(hybrid_results["combined_results"])

        # Task 15.1.2 — Prompt injection filtering on retrieved chunks
        _all_combined = (
            results.get("combined_results") or
            results.get("semantic_results") or
            results.get("keyword_results") or []
        )
        _all_combined, n_removed = _injection_scanner.filter_results(_all_combined, content_key="content")
        if n_removed:
            logger.warning("rag_injection_filtered", n_removed=n_removed)
        # Reflect filtered list back into results so downstream consumers see clean data
        if "combined_results" in results:
            results["combined_results"] = _all_combined
        elif "semantic_results" in results:
            results["semantic_results"] = _all_combined
        elif "keyword_results" in results:
            results["keyword_results"] = _all_combined

        # Phase 3.2.1 — Gap tracking
        _GAP_THRESHOLD = float(os.getenv("AI_GAP_SCORE_THRESHOLD", "0.4"))
        _best_score = max(
            (r.get("score", 0.0) for r in _all_combined if isinstance(r, dict)),
            default=0.0,
        )
        postgres_client = _postgres_client_ref()
        if _best_score < _GAP_THRESHOLD and postgres_client is not None:
            _query_hash = hashlib.sha256(query.encode()).hexdigest()[:64]
            _collections_hit = ",".join(sorted(set(
                r.get("collection", "") for r in _all_combined if isinstance(r, dict)
            ))) or "unknown"
            asyncio.create_task(_record_query_gap(
                query_hash=_query_hash, query_text=query[:500],
                score=_best_score, collection=_collections_hit,
            ))

        prompt_prefix = Config.AI_PROMPT_CACHE_STATIC_PREFIX if Config.AI_PROMPT_CACHE_POLICY_ENABLED else ""
        prompt_prefix_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()[:16] if prompt_prefix else ""
        llama_cpp_client = _llama_cpp_client_ref()
        context_compressor = _context_compressor_ref()
        if generate_response and llama_cpp_client:
            discovery_context = capability_discovery.format_context(_cap_disc)
            combined_context = f"{response_text}\n\n{discovery_context}".strip()
            compressed_context = combined_context
            compressed_tokens = 0
            if Config.AI_CONTEXT_COMPRESSION_ENABLED and context_compressor and combined_context:
                tokens_before = len(combined_context) // 4
                compressed_context, _, compressed_tokens = context_compressor.compress_to_budget(
                    contexts=[{"id": "route-results", "text": combined_context, "score": 1.0}],
                    max_tokens=Config.AI_CONTEXT_MAX_TOKENS,
                    strategy="hybrid",
                )
                logger.info(
                    "context_compression tokens_before=%d tokens_after=%d budget=%d",
                    tokens_before, compressed_tokens, Config.AI_CONTEXT_MAX_TOKENS,
                )
            # Task complexity classification — skip synthesis if remote-required,
            # use discrete bounded prompt if local-suitable.
            _complexity = None
            _skip_synthesis = False
            if Config.AI_TASK_CLASSIFICATION_ENABLED:
                _complexity = task_classifier.classify(
                    query, compressed_context, max_output_tokens=400
                )
                logger.info(
                    "task_complexity type=%s tokens=%d local=%s reason=%s",
                    _complexity.task_type,
                    _complexity.token_estimate,
                    _complexity.local_suitable,
                    _complexity.reason,
                )
                if _complexity.remote_required:
                    _swb = _switchboard_client_ref() if _switchboard_client_ref else None
                    if _swb and Config.SWITCHBOARD_URL:
                        _inference_client = _swb
                        _inference_path = "/v1/chat/completions"
                        _inference_headers = {"x-ai-route": "remote"}
                        logger.info(
                            "task_complexity_remote type=%s tokens=%d → switchboard",
                            _complexity.task_type, _complexity.token_estimate,
                        )
                    else:
                        results["synthesis_skipped"] = True
                        results["task_complexity"] = {
                            "type": _complexity.task_type,
                            "tokens": _complexity.token_estimate,
                            "reason": _complexity.reason,
                        }
                        _skip_synthesis = True
                else:
                    _inference_client = llama_cpp_client
                    _inference_path = "/chat/completions"
                    _inference_headers = {}
            elif not _skip_synthesis:
                _inference_client = llama_cpp_client
                _inference_path = "/chat/completions"
                _inference_headers = {}
            if not _skip_synthesis:
                if _complexity and _complexity.optimized_prompt:
                    prompt = _complexity.optimized_prompt
                else:
                    prompt = (
                        f"{prompt_prefix}\n\n"
                        f"User query: {query}\n\nContext:\n{compressed_context}\n\n"
                        "Provide a concise response using the context."
                    )
            if not _skip_synthesis:
                _all_results = (
                    results.get("combined_results") or results.get("semantic_results") or
                    results.get("keyword_results") or []
                )
                context_quality = max(
                    (r.get("score", 0.0) for r in _all_results if isinstance(r, dict)), default=0.5,
                )
                backend = "remote" if _inference_headers.get("x-ai-route") == "remote" else "local"
                try:
                    llm_resp = await _inference_client.post(
                        _inference_path,
                        headers=_inference_headers,
                        json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 400},
                        timeout=Config.LLAMA_CPP_INFERENCE_TIMEOUT,
                    )
                    llm_resp.raise_for_status()
                    llm_json = llm_resp.json()
                    response_text = llm_json["choices"][0]["message"]["content"]
                    usage = llm_json.get("usage", {}) if isinstance(llm_json, dict) else {}
                    cached_tokens = int(
                        usage.get("cached_tokens")
                        or (usage.get("prompt_tokens_details", {}) or {}).get("cached_tokens", 0)
                        or 0
                    )
                    results["prompt_cache"] = {
                        "policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                        "prefix_hash": prompt_prefix_hash,
                        "cached_tokens": cached_tokens,
                    }
                    if compressed_tokens:
                        results["context_compression"] = {
                            "enabled": True,
                            "token_budget": Config.AI_CONTEXT_MAX_TOKENS,
                            "compressed_tokens": compressed_tokens,
                        }
                except Exception as exc:  # noqa: BLE001
                    _is_timeout = isinstance(exc, asyncio.TimeoutError) or "timeout" in type(exc).__name__.lower()
                    logger.warning("route_search_llm_failed error=%s timeout=%s", exc, _is_timeout)
                    if _is_timeout and _record_query_gap is not None and postgres_client is not None:
                        _t_hash = hashlib.sha256(query.encode()).hexdigest()[:64]
                        asyncio.create_task(_record_query_gap(
                            query_hash=_t_hash, query_text=query[:500], score=-1.0,
                            collection="inference_timeout",
                        ))

        ROUTE_DECISIONS.labels(route=route).inc()
        _record_telemetry(
            "route_search",
            {
                "query": query[:200], "route": route, "prefer_local": prefer_local,
                "context_keys": list((context or {}).keys()),
                "prompt_cache_policy": {
                    "enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                    "prefix_hash": prompt_prefix_hash,
                },
                "inference_optimizations": {
                    "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
                    "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
                    "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
                },
                "capability_discovery": {
                    "decision": _cap_disc.get("decision", "unknown"),
                    "reason": _cap_disc.get("reason", "unknown"),
                    "cache_hit": bool(_cap_disc.get("cache_hit", False)),
                    "intent_tags": _cap_disc.get("intent_tags", []),
                    "tool_count": len(_cap_disc.get("tools", [])),
                    "skill_count": len(_cap_disc.get("skills", [])),
                    "server_count": len(_cap_disc.get("servers", [])),
                    "dataset_count": len(_cap_disc.get("datasets", [])),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        ROUTE_ERRORS.labels(route=route).inc()
        logger.error("route_search_failed route=%s error=%s", route, exc)
        raise

    latency_ms = int((time.time() - start) * 1000)
    return {
        "route": route, "backend": route, "response": response_text,
        "results": results, "latency_ms": latency_ms,
        "interaction_id": interaction_id,
        "capability_discovery": {
            "decision": _cap_disc.get("decision", "unknown"),
            "reason": _cap_disc.get("reason", "unknown"),
            "cache_hit": bool(_cap_disc.get("cache_hit", False)),
            "intent_tags": _cap_disc.get("intent_tags", []),
            "tools": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in _cap_disc.get("tools", [])
            ],
            "skills": [
                {"name": item.get("name", item.get("slug")), "description": item.get("description")}
                for item in _cap_disc.get("skills", [])
            ],
            "servers": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in _cap_disc.get("servers", [])
            ],
            "datasets": [
                {"title": item.get("title", item.get("relative_path")), "project": item.get("project")}
                for item in _cap_disc.get("datasets", [])
            ],
        },
    }
