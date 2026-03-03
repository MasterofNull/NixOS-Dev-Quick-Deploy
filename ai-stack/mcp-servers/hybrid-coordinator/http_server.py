"""
HTTP server module for the hybrid-coordinator.

Provides run_http_mode(): creates the aiohttp web application with all route
handlers, registers routes, and runs the server.

Extracted from server.py main() (Phase 6.1 decomposition).

Usage:
    import http_server
    http_server.init(
        augment_query_fn=augment_query_with_context,
        route_search_fn=route_search,
        ...
    )
    await http_server.run_http_mode(port=port, access_log_format=..., ...)
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from aiohttp import web
import httpx
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import Config, OptimizationProposal, apply_proposal, routing_config
from metrics import PROCESS_MEMORY_BYTES, REQUEST_COUNT, REQUEST_ERRORS, REQUEST_LATENCY

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state — populated by init()
# ---------------------------------------------------------------------------
_augment_query: Optional[Callable] = None
_route_search: Optional[Callable] = None
_tree_search: Optional[Callable] = None
_store_memory: Optional[Callable] = None
_recall_memory: Optional[Callable] = None
_run_harness_eval: Optional[Callable] = None
_build_scorecard: Optional[Callable] = None
_record_learning_feedback: Optional[Callable] = None
_record_simple_feedback: Optional[Callable] = None
_update_outcome: Optional[Callable] = None
_get_variant_stats: Optional[Callable] = None
_generate_dataset: Optional[Callable] = None
_get_process_memory: Optional[Callable] = None
_snapshot_stats: Optional[Callable] = None
_error_payload: Optional[Callable] = None
_wait_for_model: Optional[Callable] = None

_multi_turn_manager: Optional[Any] = None
_progressive_disclosure: Optional[Any] = None
_feedback_api: Optional[Any] = None
_learning_pipeline: Optional[Any] = None

_COLLECTIONS: Dict[str, Any] = {}
_HYBRID_STATS: Dict[str, Any] = {}
_HARNESS_STATS: Dict[str, Any] = {}
_CIRCUIT_BREAKERS: Optional[Any] = None
_SERVICE_NAME: str = "hybrid-coordinator"

_local_llm_healthy_ref: Optional[Callable] = None   # lambda: _local_llm_healthy
_local_llm_loading_ref: Optional[Callable] = None   # lambda: _local_llm_loading
_queue_depth_ref: Optional[Callable] = None          # lambda: _model_loading_queue_depth
_queue_max_ref: Optional[Callable] = None            # lambda: _MODEL_QUEUE_MAX
_workflow_sessions_lock = asyncio.Lock()


def _workflow_tool_catalog(query: str) -> List[Dict[str, str]]:
    """Heuristic tool assignment for a structured execution plan."""
    q = (query or "").lower()
    tools: List[Dict[str, str]] = []
    seen = set()

    def add(name: str, endpoint: str, reason: str) -> None:
        if name in seen:
            return
        seen.add(name)
        tools.append({"name": name, "endpoint": endpoint, "reason": reason})

    add("hints", "/hints", "Ranked workflow hints and known pitfalls for the query.")
    add("discovery", "/discovery/capabilities", "Progressive disclosure of available stack capabilities.")

    if any(k in q for k in ("find", "search", "retrieve", "context", "rag", "semantic", "lexical")):
        add("route_search", "/query", "Hybrid retrieval path (semantic + lexical + routing).")
        add("memory_recall", "/memory/recall", "Recall prior procedural/semantic memory for similar tasks.")

    if any(k in q for k in ("nixos", "service", "systemd", "deploy", "boot", "shutdown")):
        add("route_search", "/query", "Search indexed NixOS docs/rules and prior fixes.")
        add("tree_search", "/search/tree", "Broader branch-and-aggregate retrieval for infra issues.")

    if any(k in q for k in ("test", "validate", "verify", "smoke", "check")):
        add("harness_eval", "/harness/eval", "Deterministic eval scorecard for acceptance checks.")
        add("health", "/health", "Runtime stack health and capability flags.")

    if any(k in q for k in ("feedback", "learn", "improve", "regression", "quality")):
        add("feedback", "/feedback", "Capture outcome and correction data.")
        add("learning_stats", "/learning/stats", "Inspect learning pipeline health and backlog.")

    if "route_search" not in seen:
        add("route_search", "/query", "Default execution path for response generation with retrieval.")

    return tools


def _workflow_sessions_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "workflow-sessions.json"


def _build_workflow_plan(query: str) -> Dict[str, Any]:
    tools = _workflow_tool_catalog(query)
    return {
        "objective": query,
        "workflow_version": "1.1",
        "phases": [
            {
                "id": "discover",
                "goal": "Collect only high-signal context first.",
                "tools": [t for t in tools if t["name"] in {"hints", "discovery", "route_search", "tree_search"}],
                "exit_criteria": "Top risks and likely root causes identified.",
            },
            {
                "id": "plan",
                "goal": "Convert findings into discrete steps with verification points.",
                "tools": [t for t in tools if t["name"] in {"hints", "discovery"}],
                "exit_criteria": "Ordered task list with acceptance checks exists.",
            },
            {
                "id": "execute",
                "goal": "Apply changes in small reversible increments.",
                "tools": [t for t in tools if t["name"] in {"route_search", "memory_recall", "feedback"}],
                "exit_criteria": "Primary objective implemented.",
            },
            {
                "id": "validate",
                "goal": "Run smoke/eval checks and confirm expected behavior.",
                "tools": [t for t in tools if t["name"] in {"harness_eval", "health", "learning_stats"}],
                "exit_criteria": "All mandatory checks pass or failures are documented.",
            },
            {
                "id": "handoff",
                "goal": "Capture outcomes, residual risk, and rollback path.",
                "tools": [t for t in tools if t["name"] in {"feedback", "learning_stats"}],
                "exit_criteria": "Actionable handoff summary ready.",
            },
        ],
        "token_policy": {
            "approach": "progressive-disclosure",
            "rules": [
                "Start with concise hints/capability summaries.",
                "Load deeper context only when a phase requires it.",
                "Prefer retrieval over full-policy prompt stuffing.",
            ],
        },
        "metadata": {
            "query_length": len(query),
            "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            "created_epoch_s": int(time.time()),
        },
    }


def _session_lineage(sessions: Dict[str, Any], session_id: str) -> List[str]:
    """Return root->...->session lineage for a session id."""
    lineage: List[str] = []
    seen = set()
    current = session_id
    while current and current not in seen and current in sessions:
        seen.add(current)
        lineage.append(current)
        parent = (
            sessions.get(current, {})
            .get("fork", {})
            .get("from_session_id")
        )
        current = parent if isinstance(parent, str) else ""
    lineage.reverse()
    return lineage


async def _load_workflow_sessions() -> Dict[str, Any]:
    path = _workflow_sessions_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def _save_workflow_sessions(data: Dict[str, Any]) -> None:
    path = _workflow_sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def init(
    *,
    augment_query_fn: Callable,
    route_search_fn: Callable,
    tree_search_fn: Callable,
    store_memory_fn: Callable,
    recall_memory_fn: Callable,
    run_harness_eval_fn: Callable,
    build_scorecard_fn: Callable,
    record_learning_feedback_fn: Callable,
    record_simple_feedback_fn: Callable,
    update_outcome_fn: Callable,
    get_variant_stats_fn: Callable,
    generate_dataset_fn: Callable,
    get_process_memory_fn: Callable,
    snapshot_stats_fn: Callable,
    error_payload_fn: Callable,
    wait_for_model_fn: Callable,
    multi_turn_manager: Any,
    progressive_disclosure: Any,
    feedback_api: Optional[Any],
    learning_pipeline: Optional[Any],
    collections: Dict[str, Any],
    hybrid_stats: Dict[str, Any],
    harness_stats: Dict[str, Any],
    circuit_breakers: Any,
    service_name: str,
    local_llm_healthy_ref: Callable,
    local_llm_loading_ref: Callable,
    queue_depth_ref: Callable,
    queue_max_ref: Callable,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _augment_query, _route_search, _tree_search, _store_memory, _recall_memory
    global _run_harness_eval, _build_scorecard, _record_learning_feedback
    global _record_simple_feedback, _update_outcome, _get_variant_stats, _generate_dataset
    global _get_process_memory, _snapshot_stats, _error_payload, _wait_for_model
    global _multi_turn_manager, _progressive_disclosure, _feedback_api, _learning_pipeline
    global _COLLECTIONS, _HYBRID_STATS, _HARNESS_STATS, _CIRCUIT_BREAKERS, _SERVICE_NAME
    global _local_llm_healthy_ref, _local_llm_loading_ref, _queue_depth_ref, _queue_max_ref

    _augment_query = augment_query_fn
    _route_search = route_search_fn
    _tree_search = tree_search_fn
    _store_memory = store_memory_fn
    _recall_memory = recall_memory_fn
    _run_harness_eval = run_harness_eval_fn
    _build_scorecard = build_scorecard_fn
    _record_learning_feedback = record_learning_feedback_fn
    _record_simple_feedback = record_simple_feedback_fn
    _update_outcome = update_outcome_fn
    _get_variant_stats = get_variant_stats_fn
    _generate_dataset = generate_dataset_fn
    _get_process_memory = get_process_memory_fn
    _snapshot_stats = snapshot_stats_fn
    _error_payload = error_payload_fn
    _wait_for_model = wait_for_model_fn
    _multi_turn_manager = multi_turn_manager
    _progressive_disclosure = progressive_disclosure
    _feedback_api = feedback_api
    _learning_pipeline = learning_pipeline
    _COLLECTIONS = collections
    _HYBRID_STATS = hybrid_stats
    _HARNESS_STATS = harness_stats
    _CIRCUIT_BREAKERS = circuit_breakers
    _SERVICE_NAME = service_name
    _local_llm_healthy_ref = local_llm_healthy_ref
    _local_llm_loading_ref = local_llm_loading_ref
    _queue_depth_ref = queue_depth_ref
    _queue_max_ref = queue_max_ref


async def run_http_mode(port: int) -> None:
    """Build and run the aiohttp HTTP server."""

    access_log_format = (
        '{"remote":"%a","request":"%r","status":%s,'
        '"bytes":"%b","agent":"%{User-Agent}i","time":"%t"}'
    )
    access_logger = logging.getLogger("aiohttp.access")
    access_logger.handlers.clear()
    access_handler = logging.StreamHandler()
    access_handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    @web.middleware
    async def tracing_middleware(request, handler):
        tracer = trace.get_tracer(_SERVICE_NAME)
        span_name = f"{request.method} {request.path}"
        with tracer.start_as_current_span(
            span_name,
            attributes={"http.method": request.method, "http.target": request.path},
        ) as span:
            response = await handler(request)
            span.set_attribute("http.status_code", response.status)
            return response

    @web.middleware
    async def request_id_middleware(request, handler):
        from structlog.contextvars import bind_contextvars, clear_contextvars
        import time
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request["request_id"] = request_id
        bind_contextvars(request_id=request_id)
        start = time.time()
        response = None
        try:
            response = await handler(request)
            return response
        except Exception:  # noqa: BLE001
            REQUEST_ERRORS.labels(request.path, request.method).inc()
            raise
        finally:
            duration = time.time() - start
            status = str(response.status) if response else "500"
            REQUEST_LATENCY.labels(request.path, request.method).observe(duration)
            REQUEST_COUNT.labels(request.path, status).inc()
            if response:
                response.headers["X-Request-ID"] = request_id
            clear_contextvars()

    @web.middleware
    async def api_key_middleware(request, handler):
        if request.path in ("/health", "/metrics"):
            return await handler(request)
        if not Config.API_KEY:
            return await handler(request)
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
        if token != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def handle_status(request):
        """Phase 2.4.2 — Model loading status endpoint."""
        import time as _time
        try:
            async with httpx.AsyncClient(timeout=2.0) as hc:
                resp = await hc.get(f"{Config.LLAMA_CPP_URL}/health")
                llama_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                llama_status = llama_data.get("status", "unknown")
                loading = llama_status == "loading"
        except Exception as exc:
            llama_status = "unreachable"
            loading = False
            logger.debug("handle_status llama.cpp probe failed: %s", exc)

        threshold = await routing_config.get_threshold()
        return web.json_response({
            "service": "hybrid-coordinator",
            "local_llm": {
                "url": Config.LLAMA_CPP_URL,
                "status": llama_status,
                "loading": loading,
                "healthy": _local_llm_healthy_ref(),
                "model_name": os.getenv("LLAMA_MODEL_NAME", "unknown"),
                "queue_depth": _queue_depth_ref(),
                "queue_max": _queue_max_ref(),
            },
            "routing": {
                "threshold": threshold,
                "local_supports_json": os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true",
            },
        })

    async def handle_health(request):
        """Health check endpoint with circuit breakers."""
        try:
            from continuous_learning import learning_pipeline
            if learning_pipeline and hasattr(learning_pipeline, "circuit_breakers"):
                breakers = {name: breaker.state.name for name, breaker in learning_pipeline.circuit_breakers._breakers.items()}
            else:
                breakers = {}
        except (ImportError, AttributeError) as exc:
            logger.debug("Circuit breaker state unavailable: %s", exc)
            breakers = {}

        return web.json_response({
            "status": "healthy",
            "service": "hybrid-coordinator",
            "collections": list(_COLLECTIONS.keys()),
            "ai_harness": {
                "enabled": Config.AI_HARNESS_ENABLED,
                "memory_enabled": Config.AI_MEMORY_ENABLED,
                "tree_search_enabled": Config.AI_TREE_SEARCH_ENABLED,
                "eval_enabled": Config.AI_HARNESS_EVAL_ENABLED,
                "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
                "capability_discovery_ttl_seconds": Config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS,
                "capability_discovery_on_query": Config.AI_CAPABILITY_DISCOVERY_ON_QUERY,
                "autonomy_max_external_calls": Config.AI_AUTONOMY_MAX_EXTERNAL_CALLS,
                "autonomy_max_retrieval_results": Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS,
                "prompt_cache_policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
                "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
                "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            },
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            "circuit_breakers": breakers or (_CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {}),
        })

    async def handle_stats(request):
        return web.json_response({
            "status": "ok",
            "service": "hybrid-coordinator",
            "stats": _snapshot_stats(),
            "collections": list(_COLLECTIONS.keys()),
            "harness_stats": _HARNESS_STATS,
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            "circuit_breakers": _CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {},
        })

    async def handle_augment_query(request):
        try:
            data = await request.json()
            result = await _augment_query(data.get("query", ""), data.get("agent_type", "remote"))
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "augment_query_failed", "detail": str(exc)}, status=500)

    async def handle_query(request):
        """HTTP endpoint for query routing."""
        try:
            data = await request.json()
            query = data.get("prompt") or data.get("query") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            prefer_local = bool(data.get("prefer_local", True))
            if prefer_local and _local_llm_loading_ref():
                ready = await _wait_for_model(timeout=30.0)
                if not ready:
                    return web.json_response(
                        {
                            "error": "model_loading",
                            "detail": "Local model is loading and the queue is full or timed out. Retry or set prefer_local=false.",
                            "queue_depth": _queue_depth_ref(),
                            "queue_max": _queue_max_ref(),
                        },
                        status=503,
                    )
            result = await _route_search(
                query=query,
                mode=data.get("mode", "auto"),
                prefer_local=prefer_local,
                context=data.get("context"),
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", 0.7)),
                generate_response=bool(data.get("generate_response", False)),
            )
            iid = result.get("interaction_id", "")
            if iid:
                try:
                    _last_id_path = os.path.expanduser("~/.local/share/nixos-ai-stack/last-interaction")
                    os.makedirs(os.path.dirname(_last_id_path), exist_ok=True)
                    with open(_last_id_path, "w") as _f:
                        _f.write(iid)
                except OSError:
                    pass
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "route_search_failed", "detail": str(exc)}, status=500)

    async def handle_tree_search(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _tree_search(
                query=query,
                collections=data.get("collections"),
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", 0.7)),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "tree_search_failed", "detail": str(exc)}, status=500)

    async def handle_memory_store(request):
        try:
            data = await request.json()
            result = await _store_memory(
                memory_type=data.get("memory_type", ""),
                summary=data.get("summary", ""),
                content=data.get("content"),
                metadata=data.get("metadata"),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "memory_store_failed", "detail": str(exc)}, status=500)

    async def handle_memory_recall(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _recall_memory(
                query=query,
                memory_types=data.get("memory_types"),
                limit=data.get("limit"),
                retrieval_mode=data.get("retrieval_mode", "hybrid"),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "memory_recall_failed", "detail": str(exc)}, status=500)

    async def handle_harness_eval(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _run_harness_eval(
                query=query,
                expected_keywords=data.get("expected_keywords"),
                mode=data.get("mode", "auto"),
                max_latency_ms=data.get("max_latency_ms"),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "harness_eval_failed", "detail": str(exc)}, status=500)

    async def handle_harness_stats(_request):
        return web.json_response(_HARNESS_STATS)

    async def handle_harness_scorecard(_request):
        return web.json_response(_build_scorecard())

    async def handle_multi_turn_context(request):
        try:
            data = await request.json()
            session_id = data.get("session_id") or str(uuid4())
            response = await _multi_turn_manager.get_context(
                session_id=session_id,
                query=data.get("query", ""),
                context_level=data.get("context_level", "standard"),
                previous_context_ids=data.get("previous_context_ids", []),
                max_tokens=data.get("max_tokens", 2000),
                metadata=data.get("metadata"),
            )
            return web.json_response(response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback(request):
        try:
            data = await request.json()
            interaction_id = data.get("interaction_id")
            outcome = data.get("outcome")
            user_feedback = data.get("user_feedback", 0)
            correction = data.get("correction")
            if correction:
                feedback_id = await _record_learning_feedback(
                    query=data.get("query", ""),
                    correction=correction,
                    original_response=data.get("original_response"),
                    interaction_id=interaction_id,
                    rating=data.get("rating"),
                    tags=data.get("tags"),
                    model=data.get("model"),
                    variant=data.get("variant"),
                )
                return web.json_response({"status": "recorded", "feedback_id": feedback_id})
            if interaction_id and outcome:
                await _update_outcome(interaction_id=interaction_id, outcome=outcome, user_feedback=user_feedback)
                return web.json_response({"status": "updated"})
            return web.json_response({"error": "missing_feedback_fields"}, status=400)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_simple_feedback(request):
        """Phase 3.1.1 — POST /feedback/{interaction_id}"""
        try:
            interaction_id = request.match_info.get("interaction_id", "")
            if not interaction_id:
                return web.json_response({"error": "interaction_id required in path"}, status=400)
            data = await request.json()
            rating = data.get("rating")
            if rating not in (1, -1):
                return web.json_response({"error": "rating must be 1 (good) or -1 (bad)"}, status=400)
            feedback_id = await _record_simple_feedback(
                interaction_id=interaction_id,
                rating=rating,
                note=str(data.get("note", ""))[:1000],
                query=str(data.get("query", ""))[:500],
            )
            return web.json_response({"status": "recorded", "feedback_id": feedback_id})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback_evaluate(request):
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            feedback_response = await _feedback_api.evaluate_response(
                session_id=session_id,
                response=data.get("response", ""),
                confidence=data.get("confidence", 0.5),
                gaps=data.get("gaps", []),
                metadata=data.get("metadata"),
            )
            return web.json_response(feedback_response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_session_info(request):
        try:
            session_id = request.match_info.get("session_id")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            session_info = await _multi_turn_manager.get_session_info(session_id)
            if not session_info:
                return web.json_response({"error": "session not found"}, status=404)
            return web.json_response(session_info)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_clear_session(request):
        try:
            session_id = request.match_info.get("session_id")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            await _multi_turn_manager.clear_session(session_id)
            return web.json_response({"status": "cleared", "session_id": session_id})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_discover_capabilities(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            discovery_response = await _progressive_disclosure.discover(
                level=data.get("level", "overview"),
                categories=data.get("categories"),
                token_budget=data.get("token_budget", 500),
            )
            return web.json_response(discovery_response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_token_budget_recommendations(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            recommendations = await _progressive_disclosure.get_token_budget_recommendations(
                query_type=data.get("query_type", "quick_lookup"),
                context_level=data.get("context_level", "standard"),
            )
            return web.json_response(recommendations)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_apply_proposal(request: web.Request) -> web.Response:
        """Apply a validated OptimizationProposal. Requires API key."""
        key = request.headers.get("X-API-Key", "")
        if Config.API_KEY and key != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            body = await request.json()
            proposal = OptimizationProposal(**body)
        except Exception as exc:
            return web.json_response({"error": "invalid_proposal", "detail": str(exc)}, status=400)
        result = await apply_proposal(proposal)
        return web.json_response(result)

    async def handle_metrics(_request):
        PROCESS_MEMORY_BYTES.set(_get_process_memory())
        return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def handle_learning_stats(_request):
        try:
            stats_path = Path(
                os.path.expanduser(
                    os.getenv(
                        "CONTINUOUS_LEARNING_STATS_PATH",
                        os.path.join(
                            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid"),
                            "telemetry",
                            "continuous_learning_stats.json",
                        ),
                    )
                )
            )
            if stats_path.exists():
                import json
                with open(stats_path, "r") as f:
                    return web.json_response(json.load(f))
            if _learning_pipeline:
                stats = await _learning_pipeline.get_statistics()
                return web.json_response(stats)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        return web.json_response({
            "checkpoints": {"total": 0, "last_checkpoint": None},
            "backpressure": {"unprocessed_mb": 0, "paused": False},
            "backpressure_threshold_mb": 100,
            "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0},
        })

    async def handle_learning_process(_request):
        if not _learning_pipeline:
            return web.json_response({"status": "disabled"}, status=503)
        try:
            patterns = await _learning_pipeline.process_telemetry_batch()
            examples_count = 0
            if patterns:
                examples = await _learning_pipeline.generate_finetuning_examples(patterns)
                examples_count = len(examples)
                await _learning_pipeline._save_finetuning_examples(examples)
                await _learning_pipeline._index_patterns(patterns)
            await _learning_pipeline._write_stats_snapshot()
            return web.json_response({"status": "ok", "patterns": len(patterns), "examples": examples_count})
        except Exception as exc:
            return web.json_response({"status": "error", "detail": str(exc)}, status=500)

    async def handle_learning_export(_request):
        try:
            dataset_path = ""
            if _learning_pipeline:
                dataset_path = await _learning_pipeline.export_dataset_for_training()
            else:
                dataset_path = await _generate_dataset()
            count = 0
            if dataset_path and Path(dataset_path).exists():
                with open(dataset_path, "r") as f:
                    count = sum(1 for _ in f)
            return web.json_response({"status": "ok", "dataset_path": dataset_path, "examples": count})
        except Exception as exc:
            return web.json_response({"status": "error", "detail": str(exc)}, status=500)

    async def handle_learning_ab_compare(request):
        try:
            data = await request.json()
            tag_prefix = data.get("tag_prefix", "variant:")
            tag_a = data.get("tag_a")
            tag_b = data.get("tag_b")
            variant_a = data.get("variant_a")
            variant_b = data.get("variant_b")
            days = data.get("days")
            if not tag_a and variant_a:
                tag_a = f"{tag_prefix}{variant_a}"
            if not tag_b and variant_b:
                tag_b = f"{tag_prefix}{variant_b}"
            if not tag_a or not tag_b:
                return web.json_response({"error": "variant_a/variant_b or tag_a/tag_b required"}, status=400)
            stats_a = await _get_variant_stats(tag_a, days)
            stats_b = await _get_variant_stats(tag_b, days)
            avg_a = stats_a.get("avg_rating")
            avg_b = stats_b.get("avg_rating")
            delta = (float(avg_a) - float(avg_b)) if avg_a is not None and avg_b is not None else None
            return web.json_response({
                "status": "ok",
                "variant_a": stats_a,
                "variant_b": stats_b,
                "delta": {"avg_rating": delta},
            })
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=503)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    _RELOAD_ALLOWLIST = {
        "llama-cpp": "llama-cpp.service",
        "ai-embeddings": "ai-embeddings.service",
    }

    async def handle_reload_model(request: web.Request) -> web.Response:
        """POST /reload-model — restart a whitelisted systemd service."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        service = body.get("service", "llama-cpp")
        if service not in _RELOAD_ALLOWLIST:
            return web.json_response({"error": "service not in allowlist"}, status=400)
        service_unit = _RELOAD_ALLOWLIST[service]
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "restart", service_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return web.json_response({
            "status": "restarting",
            "service": service_unit,
            "note": "service will be unavailable briefly",
        })

    # ------------------------------------------------------------------
    # Phase 19.2.1/19.2.2 — /hints endpoint (agent-agnostic hint API)
    # ------------------------------------------------------------------

    async def handle_hints(request: web.Request) -> web.Response:
        """POST /hints or GET /hints?q= — return ranked workflow hints for any agent.

        Phase 19.3.2: When format=continue (GET param) or body contains 'fullInput'
        (Continue.dev HTTP context provider), returns [{"name","description","content"}].
        """
        try:
            if request.method == "POST":
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                # Continue.dev HTTP context provider sends {"query":..., "fullInput":...}
                is_continue = "fullInput" in body or body.get("format") == "continue"
                query = body.get("query", "") or body.get("fullInput", "")
                ctx = body.get("context", {})
                file_ext = ctx.get("file_ext", "") if isinstance(ctx, dict) else str(ctx)
                max_hints = int(body.get("max_hints", 5))
                agent_type = ctx.get("agent_type", "remote") if isinstance(ctx, dict) else "remote"
            else:
                is_continue = request.rel_url.query.get("format") == "continue"
                query = request.rel_url.query.get("q", "")
                file_ext = request.rel_url.query.get("context", "")
                max_hints = int(request.rel_url.query.get("max", "5"))
                agent_type = request.rel_url.query.get("agent", "remote")

            try:
                import sys as _sys
                from pathlib import Path as _Path
                _hints_dir = _Path(__file__).parent
                if str(_hints_dir) not in _sys.path:
                    _sys.path.insert(0, str(_hints_dir))
                from hints_engine import HintsEngine  # type: ignore[import]
                engine = HintsEngine()
                result = engine.rank_as_dict(query, context=file_ext, max_hints=max_hints)
            except Exception as exc:
                logger.warning("hints_engine_unavailable error=%s", exc)
                result = {
                    "hints": [],
                    "generated_at": "",
                    "query": query,
                    "error": f"hints_engine unavailable: {exc}",
                }

            # Phase 19.3.2 — Continue.dev HTTP context provider format
            if is_continue:
                hints = result.get("hints", [])
                content_lines = [f"# AI Stack Hints\n\n"]
                for i, h in enumerate(hints, 1):
                    score_pct = f"{h.get('score', 0):.0%}"
                    content_lines.append(
                        f"{i}. [{h.get('type', 'hint')}] {h.get('title', '')} ({score_pct})\n"
                        f"   {h.get('snippet', '')[:120]}\n"
                        f"   Reason: {h.get('reason', '')}\n\n"
                    )
                return web.json_response([{
                    "name": "aq-hints",
                    "description": f"AI Stack workflow hints" + (f" for: {query[:60]}" if query else ""),
                    "content": "".join(content_lines) or "No hints available — run aq-prompt-eval to score registry prompts.",
                }])

            # Agent-type-specific augmentation
            if result.get("hints") and agent_type in ("claude", "codex", "qwen", "aider"):
                top = result["hints"][0]
                result["inject_prefix"] = top.get("snippet", "")[:150]

            return web.json_response(result)
        except Exception as exc:
            logger.error("handle_hints error=%s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_workflow_plan(request: web.Request) -> web.Response:
        """Build a structured phase plan with explicit tool assignments."""
        try:
            if request.method == "POST":
                data = await request.json()
                query = (data.get("query") or data.get("prompt") or "").strip()
            else:
                data = {}
                query = (request.rel_url.query.get("q") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            return web.json_response(_build_workflow_plan(query))
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_start(request: web.Request) -> web.Response:
        """Start a persisted workflow session from a query."""
        try:
            data = await request.json()
            query = (data.get("query") or data.get("prompt") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            session_id = str(uuid4())
            plan = _build_workflow_plan(query)
            phases = []
            for idx, phase in enumerate(plan.get("phases", [])):
                phases.append({
                    "id": phase.get("id", f"phase-{idx}"),
                    "status": "in_progress" if idx == 0 else "pending",
                    "started_at": int(time.time()) if idx == 0 else None,
                    "completed_at": None,
                    "notes": [],
                })
            session = {
                "session_id": session_id,
                "objective": query,
                "plan": plan,
                "phase_state": phases,
                "current_phase_index": 0,
                "status": "in_progress",
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
            }
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_get(request: web.Request) -> web.Response:
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            include_lineage = (
                request.rel_url.query.get("lineage", "").lower() in {"1", "true", "yes"}
            )
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            if include_lineage:
                payload = dict(session)
                payload["lineage"] = _session_lineage(sessions, session_id)
                return web.json_response(payload)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_sessions_list(_request: web.Request) -> web.Response:
        """List persisted workflow sessions with compact metadata."""
        try:
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
            items = []
            for sid, sess in sessions.items():
                phase_state = sess.get("phase_state", [])
                current_idx = int(sess.get("current_phase_index", 0))
                current_phase = None
                if 0 <= current_idx < len(phase_state):
                    current_phase = phase_state[current_idx].get("id")
                items.append({
                    "session_id": sid,
                    "status": sess.get("status", "unknown"),
                    "objective": sess.get("objective", ""),
                    "current_phase": current_phase,
                    "current_phase_index": current_idx,
                    "created_at": sess.get("created_at"),
                    "updated_at": sess.get("updated_at"),
                })
            items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
            return web.json_response({"sessions": items, "count": len(items)})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_tree(request: web.Request) -> web.Response:
        """Return workflow session tree with parent/child relationships."""
        try:
            include_completed = (
                request.rel_url.query.get("include_completed", "true").lower() in {"1", "true", "yes"}
            )
            include_failed = (
                request.rel_url.query.get("include_failed", "true").lower() in {"1", "true", "yes"}
            )
            include_objective = (
                request.rel_url.query.get("include_objective", "true").lower() in {"1", "true", "yes"}
            )

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()

            nodes = []
            edges = []
            children_count: Dict[str, int] = {}

            for sid, sess in sessions.items():
                status = str(sess.get("status", "unknown"))
                if status == "completed" and not include_completed:
                    continue
                if status == "failed" and not include_failed:
                    continue

                parent_id = (
                    sess.get("fork", {})
                    .get("from_session_id")
                )
                if isinstance(parent_id, str) and parent_id:
                    edges.append({"from": parent_id, "to": sid, "type": "fork"})
                    children_count[parent_id] = int(children_count.get(parent_id, 0)) + 1

                node = {
                    "session_id": sid,
                    "status": status,
                    "current_phase_index": int(sess.get("current_phase_index", 0)),
                    "created_at": sess.get("created_at"),
                    "updated_at": sess.get("updated_at"),
                    "parent_session_id": parent_id if isinstance(parent_id, str) and parent_id else None,
                }
                if include_objective:
                    node["objective"] = sess.get("objective", "")
                nodes.append(node)

            for node in nodes:
                sid = node["session_id"]
                node["children_count"] = int(children_count.get(sid, 0))

            roots = [n["session_id"] for n in nodes if n.get("parent_session_id") is None]
            nodes.sort(key=lambda n: int(n.get("updated_at") or 0), reverse=True)

            return web.json_response({
                "nodes": nodes,
                "edges": edges,
                "roots": roots,
                "count": len(nodes),
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_fork(request: web.Request) -> web.Response:
        """Fork a workflow session to create a branch from current state."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json() if request.can_read_body else {}
            note = str(data.get("note", "forked session")).strip()
            new_id = str(uuid4())
            now = int(time.time())
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                source = sessions.get(session_id)
                if not source:
                    return web.json_response({"error": "session not found"}, status=404)
                forked = json.loads(json.dumps(source))
                forked["session_id"] = new_id
                forked["status"] = "in_progress"
                forked["created_at"] = now
                forked["updated_at"] = now
                forked.setdefault("fork", {})
                forked["fork"] = {
                    "from_session_id": session_id,
                    "note": note,
                    "forked_at": now,
                }
                sessions[new_id] = forked
                await _save_workflow_sessions(sessions)
            return web.json_response({"session_id": new_id, "forked_from": session_id, "status": "created"})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_advance(request: web.Request) -> web.Response:
        """Advance workflow state using actions: pass|fail|skip|note."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json()
            action = str(data.get("action", "note")).strip().lower()
            note = str(data.get("note", "")).strip()
            if action not in {"pass", "fail", "skip", "note"}:
                return web.json_response({"error": "action must be one of pass|fail|skip|note"}, status=400)

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)

                idx = int(session.get("current_phase_index", 0))
                phases = session.get("phase_state", [])
                if not phases or idx >= len(phases):
                    session["status"] = "completed"
                    session["updated_at"] = int(time.time())
                    sessions[session_id] = session
                    await _save_workflow_sessions(sessions)
                    return web.json_response(session)

                phase = phases[idx]
                if note:
                    phase.setdefault("notes", []).append({"ts": int(time.time()), "text": note})

                if action in {"pass", "skip"}:
                    phase["status"] = "completed"
                    phase["completed_at"] = int(time.time())
                    idx += 1
                    if idx < len(phases):
                        phases[idx]["status"] = "in_progress"
                        if not phases[idx].get("started_at"):
                            phases[idx]["started_at"] = int(time.time())
                        session["current_phase_index"] = idx
                        session["status"] = "in_progress"
                    else:
                        session["status"] = "completed"
                        session["current_phase_index"] = len(phases)
                elif action == "fail":
                    phase["status"] = "failed"
                    phase["completed_at"] = int(time.time())
                    session["status"] = "failed"
                else:
                    if phase.get("status") == "pending":
                        phase["status"] = "in_progress"
                        phase["started_at"] = int(time.time())

                session["phase_state"] = phases
                session["updated_at"] = int(time.time())
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_review_acceptance(request: web.Request) -> web.Response:
        """Deterministic reviewer gate: criteria + keyword coverage scoring."""
        try:
            data = await request.json()
            response_text = str(data.get("response", "") or "")
            query = str(data.get("query", "") or "")
            criteria = data.get("criteria", []) or []
            expected_keywords = data.get("expected_keywords", []) or []
            min_criteria_ratio = float(data.get("min_criteria_ratio", 0.7))
            min_keyword_ratio = float(data.get("min_keyword_ratio", 0.6))
            run_eval = bool(data.get("run_harness_eval", False))

            if not response_text:
                return web.json_response({"error": "response required"}, status=400)

            text = response_text.lower()
            criteria_hits = []
            for criterion in criteria:
                crit = str(criterion).strip()
                if not crit:
                    continue
                hit = crit.lower() in text
                criteria_hits.append({"criterion": crit, "hit": hit})
            criteria_total = len(criteria_hits)
            criteria_hit_count = len([c for c in criteria_hits if c["hit"]])
            criteria_ratio = (criteria_hit_count / criteria_total) if criteria_total else 1.0

            keyword_hits = []
            for kw in expected_keywords:
                item = str(kw).strip().lower()
                if not item:
                    continue
                keyword_hits.append({"keyword": item, "hit": item in text})
            keyword_total = len(keyword_hits)
            keyword_hit_count = len([k for k in keyword_hits if k["hit"]])
            keyword_ratio = (keyword_hit_count / keyword_total) if keyword_total else 1.0

            harness_eval = None
            if run_eval and query and expected_keywords and _run_harness_eval is not None:
                try:
                    harness_eval = await _run_harness_eval(
                        query=query,
                        expected_keywords=[str(k) for k in expected_keywords],
                        mode="auto",
                        max_latency_ms=None,
                    )
                except Exception as exc:
                    harness_eval = {"error": str(exc)}

            passed = criteria_ratio >= min_criteria_ratio and keyword_ratio >= min_keyword_ratio
            if isinstance(harness_eval, dict) and harness_eval.get("passed") is False:
                passed = False

            return web.json_response({
                "passed": passed,
                "score": round((criteria_ratio + keyword_ratio) / 2.0, 4),
                "criteria": {
                    "hits": criteria_hits,
                    "hit_count": criteria_hit_count,
                    "total": criteria_total,
                    "ratio": round(criteria_ratio, 4),
                    "threshold": min_criteria_ratio,
                },
                "keywords": {
                    "hits": keyword_hits,
                    "hit_count": keyword_hit_count,
                    "total": keyword_total,
                    "ratio": round(keyword_ratio, 4),
                    "threshold": min_keyword_ratio,
                },
                "harness_eval": harness_eval,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    # ------------------------------------------------------------------
    # App assembly and startup
    # ------------------------------------------------------------------

    http_app = web.Application(
        middlewares=[tracing_middleware, request_id_middleware, api_key_middleware]
    )
    http_app.router.add_get("/health", handle_health)
    http_app.router.add_get("/status", handle_status)
    http_app.router.add_get("/stats", handle_stats)
    http_app.router.add_post("/augment_query", handle_augment_query)
    http_app.router.add_post("/query", handle_query)
    http_app.router.add_post("/search/tree", handle_tree_search)
    http_app.router.add_post("/memory/store", handle_memory_store)
    http_app.router.add_post("/memory/recall", handle_memory_recall)
    http_app.router.add_post("/harness/eval", handle_harness_eval)
    http_app.router.add_get("/harness/stats", handle_harness_stats)
    http_app.router.add_get("/harness/scorecard", handle_harness_scorecard)
    http_app.router.add_post("/feedback", handle_feedback)
    http_app.router.add_post("/feedback/{interaction_id}", handle_simple_feedback)
    http_app.router.add_post("/proposals/apply", handle_apply_proposal)
    http_app.router.add_post("/context/multi_turn", handle_multi_turn_context)
    http_app.router.add_post("/feedback/evaluate", handle_feedback_evaluate)
    http_app.router.add_get("/session/{session_id}", handle_session_info)
    http_app.router.add_delete("/session/{session_id}", handle_clear_session)
    http_app.router.add_post("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_get("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_post("/discovery/token_budget", handle_token_budget_recommendations)
    http_app.router.add_get("/metrics", handle_metrics)
    http_app.router.add_get("/learning/stats", handle_learning_stats)
    http_app.router.add_post("/learning/process", handle_learning_process)
    http_app.router.add_post("/learning/export", handle_learning_export)
    http_app.router.add_post("/learning/ab_compare", handle_learning_ab_compare)
    http_app.router.add_post("/reload-model", handle_reload_model)
    http_app.router.add_post("/hints", handle_hints)           # Phase 19.2.1
    http_app.router.add_get("/hints", handle_hints)            # Phase 19.2.2
    http_app.router.add_post("/workflow/plan", handle_workflow_plan)
    http_app.router.add_get("/workflow/plan", handle_workflow_plan)
    http_app.router.add_post("/workflow/session/start", handle_workflow_session_start)
    http_app.router.add_get("/workflow/sessions", handle_workflow_sessions_list)
    http_app.router.add_get("/workflow/tree", handle_workflow_tree)
    http_app.router.add_get("/workflow/session/{session_id}", handle_workflow_session_get)
    http_app.router.add_post("/workflow/session/{session_id}/fork", handle_workflow_session_fork)
    http_app.router.add_post("/workflow/session/{session_id}/advance", handle_workflow_session_advance)
    http_app.router.add_post("/review/acceptance", handle_review_acceptance)

    runner = web.AppRunner(
        http_app,
        access_log=access_logger,
        access_log_format=access_log_format,
    )
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("✓ Hybrid Coordinator HTTP server running on http://0.0.0.0:%d", port)

    # Keep server running
    await asyncio.Event().wait()
