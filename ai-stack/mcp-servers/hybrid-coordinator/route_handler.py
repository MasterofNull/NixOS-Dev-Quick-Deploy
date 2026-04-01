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
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import capability_discovery
from config import Config
from metrics import (
    ROUTE_DECISIONS,
    ROUTE_ERRORS,
    LLM_BACKEND_SELECTIONS,
    LLM_BACKEND_LATENCY,
)
from search_router import looks_like_sql as _looks_like_sql, normalize_tokens as _normalize_tokens
from query_expansion import QueryExpander
from prompt_injection import PromptInjectionScanner, sanitize_query
import task_classifier

logger = logging.getLogger("hybrid-coordinator")
_injection_scanner = PromptInjectionScanner()
_LOW_SIGNAL_GAP_QUERIES = {
    "nix",
    "nixos",
    "test",
    "help",
    "docs",
}
_SYNTHETIC_GAP_PREFIXES = (
    "analysis only task ",
    "analysis only:",
    "analyze docs/",
    "summarize docs/",
    "fetch http://127.0.0.1",
    "fetch http://localhost",
    "curl http://127.0.0.1",
    "curl http://localhost",
)
_SYNTHETIC_GAP_SOURCE_MARKERS = {
    "gap-eval-pack",
    "manual_probe",
    "aq-qa",
    "smoke-focused-parity",
    "parity-smoke",
    "synthetic-test",
}

_CONTINUATION_QUERY_MARKERS = (
    "resume",
    "continue",
    "follow-up",
    "follow up",
    "prior context",
    "pick up where",
    "last agent",
    "ongoing",
    "left off",
    "remaining work",
    "current work",
)

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

# Batch 2.2: Route Search Optimization - Collection Latency Profiling
@dataclass
class CollectionLatencyMetrics:
    """Tracks per-collection search latency for optimization."""
    collection_latencies: Dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=50)))
    total_searches: int = 0
    simple_query_optimizations: int = 0  # Count of simplified collection fan-outs
    adaptive_timeout_applications: int = 0  # Count of adaptive timeout uses

_collection_metrics = CollectionLatencyMetrics()

# Phase 5.2 Optimization 2: Backend selection caching
@dataclass
class BackendSelectionCache:
    """LRU-style cache for backend selection decisions."""
    cache: Dict[str, str] = field(default_factory=dict)
    max_size: int = 1000
    access_count: int = 0
    hit_count: int = 0

_backend_selection_cache = BackendSelectionCache()


@lru_cache(maxsize=1000)
def _cached_backend_key(query_hash: str, score_str: str, prefer_local: bool) -> str:
    """Generate a deterministic cache key for backend selection."""
    return f"{query_hash[:16]}:{score_str}:{prefer_local}"


def _get_cached_backend_selection(query: str, score: float, prefer_local: bool) -> Optional[str]:
    """Check cache for previously computed backend selection."""
    global _backend_selection_cache
    _backend_selection_cache.access_count += 1

    query_hash = hashlib.sha256(query.encode()).hexdigest()
    score_str = f"{int(score*100)}"
    cache_key = _cached_backend_key(query_hash, score_str, prefer_local)

    if cache_key in _backend_selection_cache.cache:
        _backend_selection_cache.hit_count += 1
        return _backend_selection_cache.cache[cache_key]
    return None


def _cache_backend_selection(query: str, score: float, prefer_local: bool, backend: str) -> None:
    """Store backend selection decision in cache."""
    global _backend_selection_cache

    # Simple eviction: clear cache if it exceeds max_size
    if len(_backend_selection_cache.cache) >= _backend_selection_cache.max_size:
        _backend_selection_cache.cache.clear()

    query_hash = hashlib.sha256(query.encode()).hexdigest()
    score_str = f"{int(score*100)}"
    cache_key = _cached_backend_key(query_hash, score_str, prefer_local)
    _backend_selection_cache.cache[cache_key] = backend


def _should_track_query_gap(query: str, best_score: float, results_count: int, threshold: float) -> bool:
    """Reduce false-positive gap rows for low-signal short queries."""
    normalized = " ".join(_normalize_tokens(query))
    if not normalized:
        return False
    tokens = normalized.split()
    if normalized in _LOW_SIGNAL_GAP_QUERIES:
        return False
    # If retrieval returned anything for a tiny query, treat this as weak intent
    # rather than a true knowledge gap.
    if results_count > 0 and len(tokens) <= 2:
        return False
    return best_score < threshold


def _is_synthetic_gap_query(query: str) -> bool:
    normalized = " ".join(_normalize_tokens(query)).strip().lower()
    if not normalized:
        return True
    if normalized in _LOW_SIGNAL_GAP_QUERIES:
        return True
    if normalized.startswith(_SYNTHETIC_GAP_PREFIXES):
        return True
    if "127.0.0.1" in normalized or "localhost" in normalized:
        return True
    return False


def _context_requests_gap_skip(context: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(context, dict):
        return False
    if bool(context.get("skip_gap_tracking", False)):
        return True
    marker_fields = ("source", "intent", "origin", "task_type")
    for field in marker_fields:
        value = str(context.get(field, "")).strip().lower()
        if value in _SYNTHETIC_GAP_SOURCE_MARKERS:
            return True
    return False


def _runtime_context_blocks(context: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(context, dict):
        return []
    blocks: List[str] = []

    tool_hints = [
        str(item).strip()
        for item in (context.get("tool_hints") or [])
        if str(item).strip()
    ]
    if tool_hints:
        blocks.append("Workflow hints:\n" + "\n".join(f"- {item}" for item in tool_hints[:2]))

    tool_discovery = context.get("tool_discovery") or {}
    if isinstance(tool_discovery, dict):
        summary = str(tool_discovery.get("summary", "") or "").strip()
        capability_count = int(tool_discovery.get("capability_count", 0) or 0)
        if summary:
            blocks.append(
                f"Capability summary ({capability_count}): {summary[:260]}"
            )

    memory_recall = [
        str(item).strip()
        for item in (context.get("memory_recall") or [])
        if str(item).strip()
    ]
    if memory_recall:
        blocks.append("Relevant prior memory:\n" + "\n".join(f"- {item}" for item in memory_recall[:3]))

    return blocks


def _looks_like_continuation_query(query: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Detect continuation-style queries that should stay on the compact local path."""
    query_lower = str(query or "").lower()
    if any(token in query_lower for token in _CONTINUATION_QUERY_MARKERS):
        return True
    if isinstance(context, dict) and context.get("memory_recall"):
        return True
    has_previous_ref = any(token in query_lower for token in ("previous", "prior", "last"))
    has_resume_target = any(
        token in query_lower
        for token in ("context", "patch", "deploy", "troubleshooting", "debug", "loop", "work", "session")
    )
    return has_previous_ref and has_resume_target


def _non_memory_collections() -> List[str]:
    return [
        name for name in _COLLECTIONS.keys()
        if not str(name).startswith("agent-memory-")
    ]


def _select_route_collections(
    query: str,
    *,
    route: str,
    context: Optional[Dict[str, Any]],
    generate_response: bool,
) -> Dict[str, Any]:
    """Choose a bounded collection subset instead of fanning out across all stores."""
    ordered = _non_memory_collections()
    if not ordered:
        return {"profile": "all", "collections": list(_COLLECTIONS.keys())}

    q = str(query or "").strip().lower()
    ctx = context if isinstance(context, dict) else {}
    token_count = len(_normalize_tokens(query))
    has_memory = bool(ctx.get("memory_recall"))
    has_discovery = bool(ctx.get("tool_discovery"))
    continuation = _looks_like_continuation_query(query, ctx) or any(
        phrase in q
        for phrase in ("next patch", "last deploy", "last patch")
    )
    wants_history = (
        not has_memory
        and any(term in q for term in ("history", "previous", "earlier", "last run", "prior interaction"))
    )
    wants_error = any(term in q for term in ("error", "failure", "fail", "timeout", "latency", "problem", "bug"))
    wants_code = any(
        term in q
        for term in ("file", "module", "service", "nixos", "patch", "config", "flake", "option", "systemd", "repo", "code")
    )
    wants_patterns = has_discovery or any(
        term in q
        for term in ("pattern", "workflow", "best practice", "guide", "how", "approach", "strategy")
    )
    task_shape = task_classifier.classify(query, "", max_output_tokens=200).task_type

    selected: List[str] = []

    def add(name: str) -> None:
        if name in ordered and name not in selected:
            selected.append(name)

    if wants_code or task_shape == "code" or generate_response or route == "tree" or continuation:
        add("codebase-context")
    if wants_error or task_shape == "code" or route in {"tree", "hybrid"}:
        add("error-solutions")
    if task_shape in {"lookup", "reasoning", "synthesize"} or wants_patterns:
        add("best-practices")
    if wants_patterns or task_shape in {"reasoning", "synthesize"} or (generate_response and token_count >= 10):
        add("skills-patterns")
    if wants_history:
        add("interaction-history")

    if not selected:
        if task_shape == "lookup":
            for name in ("best-practices", "skills-patterns"):
                add(name)
        elif task_shape == "code":
            for name in ("codebase-context", "error-solutions", "skills-patterns"):
                add(name)
        elif task_shape == "reasoning":
            for name in ("best-practices", "skills-patterns", "codebase-context"):
                add(name)
        if not selected:
            selected = ordered[:3]

    if continuation and "interaction-history" in selected:
        selected.remove("interaction-history")

    max_collections = 3
    profile = "standard"
    if task_shape == "lookup":
        profile = "lookup-focused"
        max_collections = 2
    elif task_shape == "code" or wants_code:
        profile = "code-focused"
        max_collections = 3
    elif task_shape == "reasoning":
        profile = "reasoning-focused"
        max_collections = 3
    if route == "tree" or (generate_response and token_count >= 12 and task_shape not in {"lookup"}):
        max_collections = 4
        profile = "detailed" if profile == "standard" else f"{profile}-detailed"
    if wants_history:
        profile = "history-aware"
    elif continuation:
        profile = "continuation"
        max_collections = min(max_collections, 2)
    if continuation and (task_shape == "code" or wants_code or wants_error):
        profile = "continuation-code"
    elif continuation and task_shape == "reasoning":
        profile = "continuation-reasoning"
    if continuation and has_memory and not wants_history:
        max_collections = 1
        profile = f"{profile}-memory-first" if not profile.endswith("-memory-first") else profile
    elif continuation and not generate_response and not wants_history and token_count <= 14:
        max_collections = 1
        if not profile.endswith("-compact"):
            profile = f"{profile}-compact"

    # Favor lower fan-out for retrieval-only queries. These requests do not
    # need broad synthesis context, so cap the collection set more aggressively.
    if (
        not generate_response
        and not continuation
        and not wants_history
        and route in {"keyword", "semantic", "hybrid"}
        and token_count <= 12
    ):
        max_collections = min(max_collections, 2)
        if profile == "standard":
            profile = "latency-optimized"
        elif not profile.endswith("-compact") and not profile.endswith("-optimized"):
            profile = f"{profile}-compact"

    # Batch 2.2: Reduce fan-out for very simple queries (≤3 tokens)
    if token_count <= 3 and not continuation and not generate_response:
        max_collections = 1
        profile = "simple-query-optimized"
        global _collection_metrics
        _collection_metrics.simple_query_optimizations += 1

    return {
        "profile": profile,
        "collections": selected[:max_collections],
    }


def _select_keyword_pool(
    *,
    retrieval_profile: Dict[str, Any],
    keyword_limit: int,
    generate_response: bool,
) -> int:
    """Bound keyword scroll breadth using the active retrieval profile."""
    keyword_limit = max(0, int(keyword_limit))
    if keyword_limit <= 0:
        return 0

    profile = str((retrieval_profile or {}).get("profile", "") or "")
    collections = retrieval_profile.get("collections") if isinstance(retrieval_profile, dict) else []
    collection_count = len(collections) if isinstance(collections, list) else 0

    base_pool = max(keyword_limit, int(Config.AI_ROUTE_KEYWORD_POOL_DEFAULT))
    compact_pool = max(keyword_limit, int(Config.AI_ROUTE_KEYWORD_POOL_COMPACT))
    single_collection_pool = max(keyword_limit, int(Config.AI_ROUTE_KEYWORD_POOL_SINGLE_COLLECTION))

    if collection_count <= 1:
        return min(base_pool, single_collection_pool)

    if (
        not generate_response
        and (
            collection_count <= 2
            or profile.endswith("-compact")
            or profile.endswith("-memory-first")
            or profile in {"simple-query-optimized", "latency-optimized"}
        )
    ):
        return min(base_pool, compact_pool)

    if profile.startswith("lookup-focused") and collection_count <= 2:
        return min(base_pool, compact_pool)

    return base_pool


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
            elif Config.AI_TREE_SEARCH_ENABLED and token_count >= 8 and not _looks_like_continuation_query(query, context):
                route = "tree"
            else:
                route = "hybrid"

    # Batch 2.2: Calculate adaptive timeout based on query complexity
    token_count = len(_normalize_tokens(query))
    adaptive_timeout = calculate_adaptive_timeout(
        query,
        route,
        token_count,
        generate_response=generate_response,
    )

    # Phase 7.1.2 — LLM query expansion on semantic/hybrid routes
    _working_query = query
    _expansion_count = 1

    # Phase 5.2 Optimization 1: Parallelize LLM expansion and capability discovery
    # These are independent operations that can run concurrently
    expansion_task = None
    discovery_task = None

    if (
        Config.AI_LLM_EXPANSION_ENABLED
        and _query_expander is not None
        and route in ("semantic", "hybrid")
    ):
        try:
            # Batch 2.2: Use adaptive timeout instead of fixed config value
            expansion_task = asyncio.create_task(asyncio.wait_for(
                _query_expander.expand_with_llm(query, max_expansions=3),
                timeout=min(adaptive_timeout, Config.AI_LLM_EXPANSION_TIMEOUT_S),
            ))
        except Exception as _exp_err:
            logger.debug("llm_expansion_task_creation_failed", extra={"reason": str(_exp_err)})

    results: Dict[str, Any] = {}
    response_text = ""
    selected_backend = "none"
    backend_reason_class = "not_used"
    _cap_disc: Dict[str, Any] = {
        "decision": "skipped", "reason": "not-evaluated", "cache_hit": False,
        "intent_tags": [], "tools": [], "skills": [], "servers": [], "datasets": [],
    }

    try:
        retrieval_profile = _select_route_collections(
            query,
            route=route,
            context=context,
            generate_response=generate_response,
        )
        target_collections = retrieval_profile["collections"]
        keyword_pool = _select_keyword_pool(
            retrieval_profile=retrieval_profile,
            keyword_limit=keyword_limit,
            generate_response=generate_response,
        )

        # Retrieval-only requests do not use capability discovery in the response path,
        # so skip that extra fan-out unless the caller already provided discovery context.
        should_run_capability_discovery = (
            Config.AI_CAPABILITY_DISCOVERY_ON_QUERY
            and (generate_response or bool((context or {}).get("tool_discovery")))
        )

        # Phase 5.2 Optimization 1: Start capability discovery in parallel
        if should_run_capability_discovery:
            discovery_task = asyncio.create_task(capability_discovery.discover(query))

        # Phase 5.2 Optimization 1: Await both tasks concurrently instead of sequentially
        if expansion_task is not None:
            try:
                _expanded = await expansion_task
                if len(_expanded) > 1:
                    _working_query = _expanded[0]  # primary expansion for the main search
                    _expansion_count = len(_expanded)
                    logger.info("query_expansions", extra={"count": _expansion_count, "route": route})
            except (asyncio.TimeoutError, Exception) as _exp_err:
                logger.debug("llm_expansion_skipped", extra={"reason": str(_exp_err)})

        if discovery_task is not None:
            try:
                _cap_disc = await discovery_task
            except Exception as _disc_err:
                logger.debug("capability_discovery_failed", extra={"reason": str(_disc_err)})

        if route == "sql":
            response_text = (
                "SQL routing detected. Execution is disabled by default for safety. "
                "Set HYBRID_ALLOW_SQL_EXECUTION=true to enable read-only queries."
            )
        elif route == "keyword":
            # Phase 5.2 Optimization 3: Wrap search calls with adaptive timeout guards
            try:
                hybrid_results = await asyncio.wait_for(
                    _hybrid_search(
                        query=query, collections=target_collections,
                        limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
                        keyword_pool=keyword_pool,
                    ),
                    timeout=adaptive_timeout,
                )
                results = {"keyword_results": hybrid_results["keyword_results"]}
                response_text = _summarize(hybrid_results["keyword_results"])
            except asyncio.TimeoutError:
                logger.warning("search_timeout", route=route, timeout=adaptive_timeout, collections=target_collections)
                results = {"keyword_results": []}
                response_text = ""

        elif route == "semantic":
            try:
                hybrid_results = await asyncio.wait_for(
                    _hybrid_search(
                        query=_working_query, collections=target_collections,
                        limit=limit, keyword_limit=0, score_threshold=score_threshold,
                        keyword_pool=0,
                    ),
                    timeout=adaptive_timeout,
                )
                results = {"semantic_results": hybrid_results["semantic_results"]}
                response_text = _summarize(hybrid_results["semantic_results"])
            except asyncio.TimeoutError:
                logger.warning("search_timeout", route=route, timeout=adaptive_timeout, collections=target_collections)
                results = {"semantic_results": []}
                response_text = ""

        elif route == "tree":
            try:
                tree_results = await asyncio.wait_for(
                    _tree_search(
                        query=query, collections=target_collections,
                        limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
                    ),
                    timeout=adaptive_timeout,
                )
                results = tree_results
                response_text = _summarize(tree_results["combined_results"])
            except asyncio.TimeoutError:
                logger.warning("search_timeout", route=route, timeout=adaptive_timeout, collections=target_collections)
                results = {"combined_results": []}
                response_text = ""

        else:  # hybrid route
            try:
                hybrid_results = await asyncio.wait_for(
                    _hybrid_search(
                        query=_working_query, collections=target_collections,
                        limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
                        keyword_pool=keyword_pool,
                    ),
                    timeout=adaptive_timeout,
                )
                results = hybrid_results
                response_text = _summarize(hybrid_results["combined_results"])
            except asyncio.TimeoutError:
                logger.warning("search_timeout", route=route, timeout=adaptive_timeout, collections=target_collections)
                results = {"combined_results": []}
                response_text = ""

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
        skip_gap_tracking = _context_requests_gap_skip(context) or _is_synthetic_gap_query(query)
        if (not skip_gap_tracking
                and _should_track_query_gap(query, _best_score, len(_all_combined), _GAP_THRESHOLD)
                and postgres_client is not None):
            _query_hash = hashlib.sha256(query.encode()).hexdigest()[:64]
            _collections_hit = ",".join(sorted(set(
                r.get("collection", "") for r in _all_combined if isinstance(r, dict)
            ))) or "unknown"
            asyncio.create_task(_record_query_gap(
                query_hash=_query_hash, query_text=query[:500],
                score=_best_score, collection=_collections_hit,
            ))

        # Phase 5.2 Optimization 4: Only compute backend selection when actually needed
        # Skip expensive backend selection for retrieval-only queries
        if generate_response and route != "sql" and _select_backend is not None:
            try:
                # Phase 5.2 Optimization 2: Check backend selection cache first
                cached_backend = _get_cached_backend_selection(query, _best_score, prefer_local)
                if cached_backend is not None:
                    selected_backend = cached_backend
                    logger.debug("backend_selection_cache_hit")
                else:
                    selected_backend = await _select_backend(
                        query,
                        _best_score,
                        force_local=prefer_local,
                        force_remote=False,
                        requires_structured_output=False,
                    )
                    # Cache the result for future queries
                    _cache_backend_selection(query, _best_score, prefer_local, selected_backend)
            except Exception as exc:
                logger.debug("backend_selection_inference_failed error=%s", exc)

        prompt_prefix = Config.AI_PROMPT_CACHE_STATIC_PREFIX if Config.AI_PROMPT_CACHE_POLICY_ENABLED else ""
        prompt_prefix_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()[:16] if prompt_prefix else ""
        llama_cpp_client = _llama_cpp_client_ref()
        context_compressor = _context_compressor_ref()
        if generate_response and llama_cpp_client:
            discovery_context = capability_discovery.format_context(_cap_disc)
            runtime_context = "\n\n".join(_runtime_context_blocks(context))
            combined_context = "\n\n".join(
                part for part in (response_text, runtime_context, discovery_context) if part
            ).strip()
            compressed_context = combined_context
            compressed_tokens = 0
            local_max_tokens = max(1, int(Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS))
            remote_max_tokens = max(local_max_tokens, int(Config.AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS))
            classifier_context_chars = max(0, int(Config.AI_ROUTE_CLASSIFIER_CONTEXT_CHARS))
            response_max_tokens = remote_max_tokens
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
            task_complexity_summary = None
            classifier_context = compressed_context[:classifier_context_chars] if classifier_context_chars > 0 else ""
            if Config.AI_TASK_CLASSIFICATION_ENABLED:
                _complexity = task_classifier.classify(
                    query, classifier_context, max_output_tokens=local_max_tokens
                )
                task_complexity_summary = {
                    "type": _complexity.task_type,
                    "tokens": _complexity.token_estimate,
                    "local_suitable": bool(_complexity.local_suitable),
                    "remote_required": bool(_complexity.remote_required),
                    "reason": _complexity.reason,
                }
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
                        _inference_headers = {
                            "x-ai-route": "remote",
                            "x-ai-profile": "remote-reasoning",
                        }
                        response_max_tokens = remote_max_tokens
                        logger.info(
                            "task_complexity_remote type=%s tokens=%d → switchboard",
                            _complexity.task_type, _complexity.token_estimate,
                        )
                    else:
                        results["synthesis_skipped"] = True
                        results["task_complexity"] = task_complexity_summary
                        _skip_synthesis = True
                else:
                    _inference_client = llama_cpp_client
                    _inference_path = "/chat/completions"
                    _inference_headers = {}
                    response_max_tokens = local_max_tokens
            elif not _skip_synthesis:
                _inference_client = llama_cpp_client
                _inference_path = "/chat/completions"
                _inference_headers = {}
                response_max_tokens = local_max_tokens
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
                selected_backend = "remote" if _inference_headers.get("x-ai-route") == "remote" else "local"
                if _complexity and _complexity.remote_required:
                    backend_reason_class = "complexity_remote_required"
                elif _complexity:
                    backend_reason_class = "complexity_local_suitable"
                else:
                    backend_reason_class = "default_local"
                messages = []
                if selected_backend == "local":
                    local_system_prompt = Config.build_local_system_prompt()
                    if local_system_prompt:
                        messages.append({"role": "system", "content": local_system_prompt})
                messages.append({"role": "user", "content": prompt})
                _llm_start = time.perf_counter()
                try:
                    llm_resp = await _inference_client.post(
                        _inference_path,
                        headers=_inference_headers,
                        json={"messages": messages, "temperature": 0.2, "max_tokens": response_max_tokens},
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
                    LLM_BACKEND_SELECTIONS.labels(
                        backend=selected_backend,
                        reason_class=backend_reason_class,
                    ).inc()
                    LLM_BACKEND_LATENCY.labels(backend=selected_backend).observe(
                        max(0.0, time.perf_counter() - _llm_start)
                    )
                except Exception as exc:  # noqa: BLE001
                    response = getattr(exc, "response", None)
                    status_code = getattr(response, "status_code", None)
                    if (
                        selected_backend == "remote"
                        and llama_cpp_client is not None
                        and isinstance(status_code, int)
                        and 400 <= status_code < 500
                    ):
                        try:
                            fallback_messages = []
                            local_system_prompt = Config.build_local_system_prompt()
                            if local_system_prompt:
                                fallback_messages.append({"role": "system", "content": local_system_prompt})
                            fallback_messages.append({"role": "user", "content": prompt})
                            llm_resp = await llama_cpp_client.post(
                                "/chat/completions",
                                headers={},
                                json={"messages": fallback_messages, "temperature": 0.2, "max_tokens": local_max_tokens},
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
                            results["synthesis_fallback"] = {
                                "reason": "remote_4xx_local_fallback",
                                "status_code": status_code,
                                "original_backend": "remote",
                            }
                            selected_backend = "local"
                            backend_reason_class = "remote_4xx_local_fallback"
                            LLM_BACKEND_SELECTIONS.labels(
                                backend=selected_backend,
                                reason_class=backend_reason_class,
                            ).inc()
                            LLM_BACKEND_LATENCY.labels(backend=selected_backend).observe(
                                max(0.0, time.perf_counter() - _llm_start)
                            )
                            logger.info("route_search_remote_4xx_local_fallback status=%s", status_code)
                            exc = None
                        except Exception as fallback_exc:  # noqa: BLE001
                            exc = fallback_exc
                    if exc is not None:
                        _is_timeout = isinstance(exc, asyncio.TimeoutError) or "timeout" in type(exc).__name__.lower()
                        logger.warning("route_search_llm_failed error=%s timeout=%s", exc, _is_timeout)
                        LLM_BACKEND_SELECTIONS.labels(
                            backend=selected_backend,
                            reason_class="error",
                        ).inc()
                        LLM_BACKEND_LATENCY.labels(backend=selected_backend).observe(
                            max(0.0, time.perf_counter() - _llm_start)
                        )
                        if (
                            _is_timeout
                            and _record_query_gap is not None
                            and postgres_client is not None
                            and not (_context_requests_gap_skip(context) or _is_synthetic_gap_query(query))
                        ):
                            _t_hash = hashlib.sha256(query.encode()).hexdigest()[:64]
                            asyncio.create_task(_record_query_gap(
                                query_hash=_t_hash, query_text=query[:500], score=-1.0,
                                collection="inference_timeout",
                            ))

        if selected_backend in {"", "none", "unknown"} and not generate_response:
            selected_backend = "local"
            backend_reason_class = "retrieval_only_local"
            LLM_BACKEND_SELECTIONS.labels(
                backend=selected_backend,
                reason_class=backend_reason_class,
            ).inc()

        ROUTE_DECISIONS.labels(route=route).inc()
        _record_telemetry(
            "route_search",
            {
                "query": query[:200], "route": route, "prefer_local": prefer_local,
                "generate_response": bool(generate_response),
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
                "retrieval_profile": {
                    "profile": retrieval_profile.get("profile", "standard"),
                    "collection_count": len(target_collections),
                    "collections": target_collections,
                    "keyword_pool": keyword_pool,
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        ROUTE_ERRORS.labels(route=route).inc()
        logger.error("route_search_failed", extra={"route": route, "error": str(exc)})
        raise

    latency_ms = int((time.time() - start) * 1000)

    # Batch 2.2: Track collection search latency for profiling
    track_collection_search_latency(target_collections, latency_ms)

    return {
        "route": route, "backend": selected_backend, "response": response_text,
        "results": results, "latency_ms": latency_ms,
        "interaction_id": interaction_id,
        "backend_reason_class": backend_reason_class,
        "response_max_tokens": response_max_tokens if generate_response else None,
        "task_complexity": task_complexity_summary,
        "retrieval_profile": retrieval_profile,
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


# ---------------------------------------------------------------------------
# Batch 2.2: Route Search Optimization Metrics
# ---------------------------------------------------------------------------

def calculate_adaptive_timeout(
    query: str,
    route: str,
    token_count: int,
    generate_response: bool = True,
) -> float:
    """
    Calculate adaptive timeout based on query complexity.

    Simple queries (≤3 tokens, keyword route): 5s
    Medium queries (4-8 tokens, hybrid): 10s
    Complex queries (9+ tokens, tree/semantic): 15s

    Retrieval-only requests use tighter caps because they do not pay for
    downstream synthesis and should fail fast instead of inflating tail latency.

    Returns:
        Timeout in seconds
    """
    global _collection_metrics
    _collection_metrics.adaptive_timeout_applications += 1

    if token_count <= 3 and route == "keyword":
        base_timeout = 5.0
    elif token_count <= 8 and route in ("hybrid", "keyword"):
        base_timeout = 10.0
    elif route == "tree" or token_count > 8:
        base_timeout = 15.0
    else:
        base_timeout = 12.0  # Default for edge cases

    if generate_response:
        return base_timeout

    if token_count <= 3 and route == "keyword":
        return min(base_timeout, Config.AI_ROUTE_TIMEOUT_RETRIEVAL_KEYWORD_SECONDS)
    if route in ("semantic", "tree") or token_count > 8:
        return min(base_timeout, Config.AI_ROUTE_TIMEOUT_RETRIEVAL_COMPLEX_SECONDS)
    return min(base_timeout, Config.AI_ROUTE_TIMEOUT_RETRIEVAL_HYBRID_SECONDS)


def track_collection_search_latency(collections: List[str], latency_ms: float) -> None:
    """Track latency for a search across given collections."""
    global _collection_metrics
    _collection_metrics.total_searches += 1
    # Store latency for each collection searched
    for collection in collections:
        _collection_metrics.collection_latencies[collection].append(latency_ms)


def get_backend_selection_cache_stats() -> Dict[str, Any]:
    """Get backend selection cache performance statistics."""
    global _backend_selection_cache
    cache_size = len(_backend_selection_cache.cache)
    hit_rate = (
        (_backend_selection_cache.hit_count / _backend_selection_cache.access_count * 100)
        if _backend_selection_cache.access_count > 0
        else 0.0
    )
    return {
        "cache_size": cache_size,
        "max_size": _backend_selection_cache.max_size,
        "access_count": _backend_selection_cache.access_count,
        "hit_count": _backend_selection_cache.hit_count,
        "hit_rate_percent": round(hit_rate, 1),
    }


def get_route_search_metrics() -> Dict[str, Any]:
    """
    Get route search optimization metrics.

    Returns:
        Dictionary with collection latencies, optimization counts
    """
    metrics = _collection_metrics

    # Calculate per-collection averages
    collection_stats = {}
    for collection_name, latencies in metrics.collection_latencies.items():
        if latencies:
            latencies_list = list(latencies)
            avg_latency = sum(latencies_list) / len(latencies_list)
            # P95 calculation
            sorted_latencies = sorted(latencies_list)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0.0

            collection_stats[collection_name] = {
                "avg_latency_ms": round(avg_latency, 1),
                "p95_latency_ms": round(p95_latency, 1),
                "search_count": len(latencies_list),
            }

    backend_cache_stats = get_backend_selection_cache_stats()

    return {
        "total_searches": metrics.total_searches,
        "simple_query_optimizations": metrics.simple_query_optimizations,
        "adaptive_timeout_applications": metrics.adaptive_timeout_applications,
        "collection_stats": collection_stats,
        "backend_selection_cache": backend_cache_stats,
        "active": True,
    }
