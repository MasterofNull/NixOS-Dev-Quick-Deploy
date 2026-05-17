"""
Memory, harness, session, discovery, and proposal HTTP handlers.

Covers:
  - POST /memory/store, /memory/recall
  - POST /harness/eval, /qa/check
  - GET  /harness/stats, /harness/scorecard
  - POST /context/multi_turn
  - GET/DELETE /session/{session_id}
  - GET/POST /discovery/capabilities
  - POST /discovery/token_budget
  - POST /proposals/apply

Extracted from http_server.py (Phase 12.4 decomposition).
"""

import hashlib
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from aiohttp import web

import mcp_handlers
from agent_registry import (
    _active_lesson_refs,
    _agent_lessons_lock,
    _load_agent_lessons_registry,
)
from config import Config, OptimizationProposal, apply_proposal
from memory_manager import coerce_memory_summary, normalize_memory_type, validate_memory_content

# Phase 54.1: MemoryBroker integration
import memory_broker

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------
_store_memory: Optional[Callable] = None
_recall_memory: Optional[Callable] = None
_memory_broker: Optional[memory_broker.MemoryBroker] = None
...
def init(
    *,
    store_memory_fn: Callable,
    recall_memory_fn: Callable,
    run_harness_eval_fn: Callable,
    build_scorecard_fn: Callable,
    harness_stats: Dict[str, Any],
    performance_profiler: Any,
    multi_turn_manager: Any,
    progressive_disclosure: Any,
    error_payload_fn: Callable,
) -> None:
    """Inject runtime dependencies. Call once from http_server.py init()."""
    global _store_memory, _recall_memory, _run_harness_eval, _build_scorecard
    global _HARNESS_STATS, _PERFORMANCE_PROFILER, _multi_turn_manager
    global _progressive_disclosure, _error_payload, _memory_broker
    _store_memory = store_memory_fn
    _recall_memory = recall_memory_fn
    _run_harness_eval = run_harness_eval_fn
    _build_scorecard = build_scorecard_fn
    _HARNESS_STATS = harness_stats
    _PERFORMANCE_PROFILER = performance_profiler
    _multi_turn_manager = multi_turn_manager
    _progressive_disclosure = progressive_disclosure
    _error_payload = error_payload_fn
    try:
        _memory_broker = memory_broker.get_broker()
    except Exception:
        logger.warning("memory_context_handlers: memory_broker not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gap_query_fingerprint(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(query or "").strip().lower()).strip()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_memory_store(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        memory_type = normalize_memory_type(data.get("memory_type", ""))
        summary = coerce_memory_summary(data.get("summary"), data.get("content"))
        # Phase 12.3 — Reject poisoned/trivial payloads before any AIDB write
        validate_memory_content(summary, data.get("content"))
        
        # Phase 54.1 — Use MemoryBroker (Level 5)
        _mem_store_start = time.time()
        if _memory_broker:
            result = await _memory_broker.write(
                memory_type=memory_type,
                content=summary,
                context=data.get("metadata"),
                ttl_seconds=data.get("ttl_seconds"),
                source=data.get("source", "coordinator-api"),
            )
        else:
            # Fallback to direct store
            result = await _store_memory(
                memory_type=memory_type,
                summary=summary,
                content=data.get("content"),
                metadata=data.get("metadata"),
            )
        _mem_store_duration_ms = (time.time() - _mem_store_start) * 1000
        _PERFORMANCE_PROFILER.record_metric("memory_store", _mem_store_duration_ms, {"memory_type": memory_type})
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs and isinstance(result, dict):
            result["active_lesson_refs"] = lesson_refs
        return web.json_response(result)
    except ValueError as exc:
        return web.json_response({"error": "memory_store_invalid", "detail": str(exc)}, status=400)
    except Exception as exc:
        return web.json_response({"error": "memory_store_failed", "detail": str(exc)}, status=500)


async def handle_memory_recall(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        query = data.get("query") or data.get("prompt") or ""
        if not query:
            return web.json_response({"error": "query required"}, status=400)
        
        # Phase 54.1 — Use MemoryBroker (Level 5)
        _mem_recall_start = time.time()
        if _memory_broker:
            rows = await _memory_broker.read(
                memory_type=normalize_memory_type(data.get("memory_type", "semantic")),
                query=query,
                top_k=int(data.get("limit", 5)),
                include_expired=bool(data.get("include_expired", False)),
            )
            result = {"results": rows, "count": len(rows)}
        else:
            # Fallback to direct recall
            result = await _recall_memory(
                query=query,
                memory_types=data.get("memory_types"),
                limit=data.get("limit"),
                retrieval_mode=data.get("retrieval_mode", "hybrid"),
            )
        _mem_recall_duration_ms = (time.time() - _mem_recall_start) * 1000
        _PERFORMANCE_PROFILER.record_metric(
            "memory_recall", _mem_recall_duration_ms,
            {"query_len": len(query), "mode": data.get("retrieval_mode", "hybrid")},
        )
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs and isinstance(result, dict):
            result["active_lesson_refs"] = lesson_refs
        return web.json_response(result)
    except Exception as exc:
        return web.json_response({"error": "memory_recall_failed", "detail": str(exc)}, status=500)


async def handle_harness_eval(request: web.Request) -> web.Response:
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
        metrics = result.get("metrics") if isinstance(result, dict) else {}
        request["audit_metadata"] = {
            "harness_status": result.get("status") if isinstance(result, dict) else "",
            "harness_passed": bool(result.get("passed")) if isinstance(result, dict) else False,
            "harness_overall_score": metrics.get("overall_score") if isinstance(metrics, dict) else None,
            "harness_failure_category": result.get("failure_category") if isinstance(result, dict) else None,
            "harness_query_fingerprint": _gap_query_fingerprint(query),
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs and isinstance(result, dict):
            result["active_lesson_refs"] = lesson_refs
        return web.json_response(result)
    except Exception as exc:
        return web.json_response({"error": "harness_eval_failed", "detail": str(exc)}, status=500)


async def handle_qa_check(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        result = await mcp_handlers.run_qa_check_as_dict(data)
        qa_result = result.get("qa_result") if isinstance(result, dict) else {}
        request["audit_metadata"] = {
            "phase": result.get("phase"),
            "exit_code": result.get("exit_code"),
            "qa_passed": (qa_result or {}).get("passed") if isinstance(qa_result, dict) else None,
            "qa_failed": (qa_result or {}).get("failed") if isinstance(qa_result, dict) else None,
            "qa_skipped": (qa_result or {}).get("skipped") if isinstance(qa_result, dict) else None,
        }
        status = 200 if result.get("status") == "ok" else 500
        return web.json_response(result, status=status)
    except ValueError as exc:
        return web.json_response({"error": "qa_check_invalid", "detail": str(exc)}, status=400)
    except TimeoutError as exc:
        return web.json_response({"error": "qa_check_timeout", "detail": str(exc)}, status=504)
    except FileNotFoundError as exc:
        return web.json_response({"error": "qa_check_unavailable", "detail": str(exc)}, status=503)
    except Exception as exc:
        return web.json_response({"error": "qa_check_failed", "detail": str(exc)}, status=500)


async def handle_harness_stats(_request: web.Request) -> web.Response:
    payload = dict(_HARNESS_STATS)
    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_harness_scorecard(_request: web.Request) -> web.Response:
    payload = _build_scorecard()
    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
    if lesson_refs and isinstance(payload, dict):
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_multi_turn_context(request: web.Request) -> web.Response:
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
        payload = response.dict()
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_session_info(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        session_info = await _multi_turn_manager.get_session_info(session_id)
        if not session_info:
            return web.json_response({"error": "session not found"}, status=404)
        payload = dict(session_info)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_clear_session(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        await _multi_turn_manager.clear_session(session_id)
        payload: Dict[str, Any] = {"status": "cleared", "session_id": session_id}
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_discover_capabilities(request: web.Request) -> web.Response:
    try:
        data = await request.json() if request.method == "POST" else {}
        discovery_response = await _progressive_disclosure.discover(
            level=data.get("level", "overview"),
            categories=data.get("categories"),
            token_budget=data.get("token_budget", 500),
        )
        payload = discovery_response.dict()
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_token_budget_recommendations(request: web.Request) -> web.Response:
    try:
        data = await request.json() if request.method == "POST" else {}
        recommendations = await _progressive_disclosure.get_token_budget_recommendations(
            query_type=data.get("query_type", "quick_lookup"),
            context_level=data.get("context_level", "standard"),
        )
        payload = dict(recommendations)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
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
    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
    if lesson_refs and isinstance(result, dict):
        result["active_lesson_refs"] = lesson_refs
    return web.json_response(result)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/memory/store", handle_memory_store)
    http_app.router.add_post("/memory/recall", handle_memory_recall)
    http_app.router.add_post("/harness/eval", handle_harness_eval)
    http_app.router.add_post("/qa/check", handle_qa_check)
    http_app.router.add_get("/harness/stats", handle_harness_stats)
    http_app.router.add_get("/harness/scorecard", handle_harness_scorecard)
    http_app.router.add_post("/context/multi_turn", handle_multi_turn_context)
    http_app.router.add_get("/session/{session_id}", handle_session_info)
    http_app.router.add_delete("/session/{session_id}", handle_clear_session)
    http_app.router.add_post("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_get("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_post("/discovery/token_budget", handle_token_budget_recommendations)
    http_app.router.add_post("/proposals/apply", handle_apply_proposal)
