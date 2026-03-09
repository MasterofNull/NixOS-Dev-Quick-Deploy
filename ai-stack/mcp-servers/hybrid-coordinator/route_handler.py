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
    continuation = has_memory or any(
        phrase in q
        for phrase in ("continue", "resume", "previous", "prior", "next patch", "last deploy", "last patch")
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

    selected: List[str] = []

    def add(name: str) -> None:
        if name in ordered and name not in selected:
            selected.append(name)

    add("best-practices")
    if wants_error or route in {"tree", "hybrid"}:
        add("error-solutions")
    if wants_code or generate_response or route == "tree" or continuation:
        add("codebase-context")
    if wants_patterns or (generate_response and token_count >= 10):
        add("skills-patterns")
    if wants_history:
        add("interaction-history")

    if not selected:
        selected = ordered[:3]

    if continuation and "interaction-history" in selected:
        selected.remove("interaction-history")

    max_collections = 3
    profile = "standard"
    if route == "tree" or (generate_response and token_count >= 12):
        max_collections = 4
        profile = "detailed"
    if wants_history:
        profile = "history-aware"
    elif continuation:
        profile = "continuation"

    return {
        "profile": profile,
        "collections": selected[:max_collections],
    }


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
        if Config.AI_CAPABILITY_DISCOVERY_ON_QUERY:
            _cap_disc = await capability_discovery.discover(query)

        if route == "sql":
            response_text = (
                "SQL routing detected. Execution is disabled by default for safety. "
                "Set HYBRID_ALLOW_SQL_EXECUTION=true to enable read-only queries."
            )
        elif route == "keyword":
            hybrid_results = await _hybrid_search(
                query=query, collections=target_collections,
                limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
            )
            results = {"keyword_results": hybrid_results["keyword_results"]}
            response_text = _summarize(hybrid_results["keyword_results"])
        elif route == "semantic":
            hybrid_results = await _hybrid_search(
                query=_working_query, collections=target_collections,
                limit=limit, keyword_limit=0, score_threshold=score_threshold,
            )
            results = {"semantic_results": hybrid_results["semantic_results"]}
            response_text = _summarize(hybrid_results["semantic_results"])
        elif route == "tree":
            tree_results = await _tree_search(
                query=query, collections=target_collections,
                limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
            )
            results = tree_results
            response_text = _summarize(tree_results["combined_results"])
        else:
            hybrid_results = await _hybrid_search(
                query=_working_query, collections=target_collections,
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

        # Emit backend-selection decisions even when callers request retrieval-only
        # mode (generate_response=false), so routing split telemetry stays useful.
        if not generate_response and route != "sql" and _select_backend is not None:
            try:
                selected_backend = await _select_backend(
                    query,
                    _best_score,
                    force_local=prefer_local,
                    force_remote=False,
                    requires_structured_output=False,
                )
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
                        _inference_headers = {
                            "x-ai-route": "remote",
                            "x-ai-profile": "remote-reasoning",
                        }
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
                        json={"messages": messages, "temperature": 0.2, "max_tokens": 400},
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
                                json={"messages": fallback_messages, "temperature": 0.2, "max_tokens": 400},
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
                "retrieval_profile": {
                    "profile": retrieval_profile.get("profile", "standard"),
                    "collection_count": len(target_collections),
                    "collections": target_collections,
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        ROUTE_ERRORS.labels(route=route).inc()
        logger.error("route_search_failed route=%s error=%s", route, exc)
        raise

    latency_ms = int((time.time() - start) * 1000)
    return {
        "route": route, "backend": selected_backend, "response": response_text,
        "results": results, "latency_ms": latency_ms,
        "interaction_id": interaction_id,
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
