"""
Operational HTTP handlers for the hybrid-coordinator server.

Extracted from http_server.py during Phase 11.5 decomposition. This module
owns health, alerts, feedback, metrics, cache, learning, and model-control
surfaces while relying on injected coordinator state and helpers.
"""

import asyncio
import json
import logging
import os
import re
import socket
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from alert_engine import AlertSeverity
from metrics import (
    ORCHESTRATION_ACTIVE_SESSIONS,
    ORCHESTRATION_PENDING_DELEGATIONS,
    ORCHESTRATION_REGISTERED_AGENTS,
    ORCHESTRATION_TOOL_PENDING_APPROVALS,
    ORCHESTRATION_WORKSPACES_BY_MODE,
    PROCESS_MEMORY_BYTES,
)

logger = logging.getLogger("hybrid-coordinator")

_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None
_load_lesson_refs: Optional[Callable[..., Any]] = None
_snapshot_stats: Optional[Callable[[], Dict[str, Any]]] = None
_queue_depth_ref: Optional[Callable[[], Any]] = None
_queue_max_ref: Optional[Callable[[], Any]] = None
_get_alert_engine: Optional[Callable[[], Any]] = None
_record_learning_feedback: Optional[Callable[..., Any]] = None
_record_simple_feedback: Optional[Callable[..., Any]] = None
_update_outcome: Optional[Callable[..., Any]] = None
_get_variant_stats: Optional[Callable[..., Any]] = None
_generate_dataset: Optional[Callable[[], Any]] = None
_get_process_memory: Optional[Callable[[], float]] = None

_feedback_api: Optional[Any] = None
_embedding_cache_ref: Optional[Callable[[], Any]] = None
_learning_pipeline: Optional[Any] = None
_agent_hq: Optional[Any] = None
_delegation_api: Optional[Any] = None
_workspace_manager: Optional[Any] = None
_mcp_tool_invoker: Optional[Any] = None
_performance_profiler: Optional[Any] = None
_config: Optional[Any] = None
_collections: Dict[str, Any] = {}
_hybrid_stats: Dict[str, Any] = {}
_harness_stats: Dict[str, Any] = {}
_circuit_breakers: Optional[Any] = None

_HEALTH_HISTORY: deque = deque(maxlen=60)
_RELOAD_ALLOWLIST = {
    "llama-cpp": "llama-cpp.service",
    "llama-cpp-embed": "llama-cpp-embed.service",
    "ai-embeddings": "ai-embeddings.service",
}


def init(
    *,
    error_payload_fn: Callable[[str, Exception], Dict[str, Any]],
    load_lesson_refs_fn: Callable[..., Any],
    snapshot_stats_fn: Callable[[], Dict[str, Any]],
    queue_depth_ref: Callable[[], Any],
    queue_max_ref: Callable[[], Any],
    get_alert_engine_fn: Callable[[], Any],
    record_learning_feedback_fn: Callable[..., Any],
    record_simple_feedback_fn: Callable[..., Any],
    update_outcome_fn: Callable[..., Any],
    get_variant_stats_fn: Callable[..., Any],
    generate_dataset_fn: Callable[[], Any],
    get_process_memory_fn: Callable[[], float],
    feedback_api: Any,
    embedding_cache_ref: Callable[[], Any],
    learning_pipeline: Any,
    agent_hq: Any,
    delegation_api: Any,
    workspace_manager: Any,
    mcp_tool_invoker: Any,
    performance_profiler: Any,
    config: Any,
    collections: Dict[str, Any],
    hybrid_stats: Dict[str, Any],
    harness_stats: Dict[str, Any],
    circuit_breakers: Any,
) -> None:
    global _error_payload, _load_lesson_refs, _snapshot_stats, _queue_depth_ref, _queue_max_ref
    global _get_alert_engine, _record_learning_feedback, _record_simple_feedback, _update_outcome
    global _get_variant_stats, _generate_dataset, _get_process_memory, _feedback_api
    global _embedding_cache_ref, _learning_pipeline, _agent_hq, _delegation_api
    global _workspace_manager, _mcp_tool_invoker, _performance_profiler, _config
    global _collections, _hybrid_stats, _harness_stats, _circuit_breakers

    _error_payload = error_payload_fn
    _load_lesson_refs = load_lesson_refs_fn
    _snapshot_stats = snapshot_stats_fn
    _queue_depth_ref = queue_depth_ref
    _queue_max_ref = queue_max_ref
    _get_alert_engine = get_alert_engine_fn
    _record_learning_feedback = record_learning_feedback_fn
    _record_simple_feedback = record_simple_feedback_fn
    _update_outcome = update_outcome_fn
    _get_variant_stats = get_variant_stats_fn
    _generate_dataset = generate_dataset_fn
    _get_process_memory = get_process_memory_fn
    _feedback_api = feedback_api
    _embedding_cache_ref = embedding_cache_ref
    _learning_pipeline = learning_pipeline
    _agent_hq = agent_hq
    _delegation_api = delegation_api
    _workspace_manager = workspace_manager
    _mcp_tool_invoker = mcp_tool_invoker
    _performance_profiler = performance_profiler
    _config = config
    _collections = collections
    _hybrid_stats = hybrid_stats
    _harness_stats = harness_stats
    _circuit_breakers = circuit_breakers


async def _active_lesson_refs(limit: int = 2) -> List[Dict[str, Any]]:
    refs = await _load_lesson_refs(limit=limit)
    return refs if isinstance(refs, list) else []


def _internal_error(exc: Exception) -> web.Response:
    return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_health(_request: web.Request) -> web.Response:
    try:
        from continuous_learning import learning_pipeline

        if learning_pipeline and hasattr(learning_pipeline, "circuit_breakers"):
            breakers = {
                name: breaker.state.name
                for name, breaker in learning_pipeline.circuit_breakers._breakers.items()
            }
        else:
            breakers = {}
    except (ImportError, AttributeError) as exc:
        logger.debug("Circuit breaker state unavailable: %s", exc)
        breakers = {}

    payload = {
        "status": "healthy",
        "service": "hybrid-coordinator",
        "collections": list(_collections.keys()),
        "ai_harness": {
            "enabled": _config.AI_HARNESS_ENABLED,
            "memory_enabled": _config.AI_MEMORY_ENABLED,
            "tree_search_enabled": _config.AI_TREE_SEARCH_ENABLED,
            "eval_enabled": _config.AI_HARNESS_EVAL_ENABLED,
            "capability_discovery_enabled": _config.AI_CAPABILITY_DISCOVERY_ENABLED,
            "capability_discovery_ttl_seconds": _config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS,
            "capability_discovery_on_query": _config.AI_CAPABILITY_DISCOVERY_ON_QUERY,
            "autonomy_max_external_calls": _config.AI_AUTONOMY_MAX_EXTERNAL_CALLS,
            "autonomy_max_retrieval_results": _config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS,
            "prompt_cache_policy_enabled": _config.AI_PROMPT_CACHE_POLICY_ENABLED,
            "speculative_decoding_enabled": _config.AI_SPECULATIVE_DECODING_ENABLED,
            "speculative_decoding_mode": _config.AI_SPECULATIVE_DECODING_MODE,
            "context_compression_enabled": _config.AI_CONTEXT_COMPRESSION_ENABLED,
        },
        "capability_discovery": _hybrid_stats.get("capability_discovery", {}),
        "circuit_breakers": breakers or (_circuit_breakers.get_all_stats() if _circuit_breakers else {}),
    }
    lesson_refs = await _active_lesson_refs(limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_health_detailed(_request: web.Request) -> web.Response:
    deps: Dict[str, Any] = {}

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip()
    aidb_url = os.getenv("AIDB_URL", "http://127.0.0.1:8002").strip()
    llama_url = os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080").strip()
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()
    postgres_host = os.getenv("POSTGRES_HOST", "127.0.0.1").strip()
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432") or 5432)

    async with httpx.AsyncClient(timeout=2.5) as hc:
        try:
            r = await hc.get(f"{qdrant_url.rstrip('/')}/collections")
            deps["qdrant"] = {"status": "ok" if r.status_code < 500 else "error", "http_status": r.status_code}
        except Exception as exc:  # noqa: BLE001
            deps["qdrant"] = {"status": "unavailable", "error": str(exc)[:180]}

        try:
            r = await hc.get(f"{aidb_url.rstrip('/')}/health/fast")
            body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            deps["aidb"] = {
                "status": "ok" if r.status_code < 500 else "error",
                "http_status": r.status_code,
                "reported_status": body.get("status"),
            }
        except Exception as exc:  # noqa: BLE001
            deps["aidb"] = {"status": "unavailable", "error": str(exc)[:180]}

        try:
            r = await hc.get(f"{llama_url.rstrip('/')}/health")
            body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            deps["llama_cpp"] = {
                "status": "ok" if r.status_code < 500 else "error",
                "http_status": r.status_code,
                "reported_status": body.get("status"),
            }
        except Exception as exc:  # noqa: BLE001
            deps["llama_cpp"] = {"status": "unavailable", "error": str(exc)[:180]}

    redis_host_port = redis_url.split("://", 1)[-1].split("/", 1)[0]
    redis_host, redis_port = (redis_host_port.split(":", 1) + ["6379"])[:2]
    try:
        with socket.create_connection((redis_host, int(redis_port)), timeout=2.0):
            deps["redis"] = {"status": "ok", "host": redis_host, "port": int(redis_port)}
    except Exception as exc:  # noqa: BLE001
        deps["redis"] = {"status": "unavailable", "error": str(exc)[:180]}

    try:
        with socket.create_connection((postgres_host, postgres_port), timeout=2.0):
            deps["postgres"] = {"status": "ok", "host": postgres_host, "port": postgres_port}
    except Exception as exc:  # noqa: BLE001
        deps["postgres"] = {"status": "unavailable", "error": str(exc)[:180]}

    stats = _snapshot_stats() if _snapshot_stats else {}
    total_queries = int(stats.get("total_queries", 0) or 0)
    context_hits = int(stats.get("context_hits", 0) or 0)
    context_hit_rate = round((100.0 * context_hits / total_queries), 1) if total_queries > 0 else None
    perf = {
        "total_queries": total_queries,
        "context_hits": context_hits,
        "context_hit_rate_pct": context_hit_rate,
        "model_loading_queue_depth": _queue_depth_ref() if _queue_depth_ref else None,
        "model_loading_queue_max": _queue_max_ref() if _queue_max_ref else None,
    }
    dependency_unhealthy = any(d.get("status") != "ok" for d in deps.values())
    service_status = "degraded" if dependency_unhealthy else "healthy"
    payload = {
        "status": service_status,
        "service": "hybrid-coordinator",
        "dependencies": deps,
        "performance": perf,
        "circuit_breakers": _circuit_breakers.get_all_stats() if _circuit_breakers else {},
        "capability_discovery": _hybrid_stats.get("capability_discovery", {}),
    }
    lesson_refs = await _active_lesson_refs(limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload, status=200 if service_status in ("healthy", "degraded") else 503)


async def handle_health_aggregate(_request: web.Request) -> web.Response:
    servers = {
        "hybrid-coordinator": {"url": "http://127.0.0.1:8003", "endpoint": "/health"},
        "aidb": {"url": os.getenv("AIDB_URL", "http://127.0.0.1:8002").strip(), "endpoint": "/health"},
        "ralph-wiggum": {"url": _config.RALPH_WIGGUM_URL.rstrip("/"), "endpoint": "/health"},
        "llama-cpp": {"url": os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080").strip(), "endpoint": "/health"},
        "qdrant": {"url": os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip(), "endpoint": "/collections"},
    }

    results: Dict[str, Any] = {}
    aggregate_start = datetime.now(timezone.utc).timestamp()

    async def ping_server(name: str, info: Dict[str, str]) -> Dict[str, Any]:
        url = f"{info['url']}{info['endpoint']}"
        start = datetime.now(timezone.utc).timestamp()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                latency_ms = round((datetime.now(timezone.utc).timestamp() - start) * 1000, 1)
                body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                status = "healthy" if resp.status_code < 400 else "degraded" if resp.status_code < 500 else "unhealthy"
                return {
                    "status": status,
                    "http_status": resp.status_code,
                    "latency_ms": latency_ms,
                    "reported_status": body.get("status"),
                }
        except Exception as exc:
            latency_ms = round((datetime.now(timezone.utc).timestamp() - start) * 1000, 1)
            return {"status": "unreachable", "latency_ms": latency_ms, "error": str(exc)[:120]}

    tasks = {name: ping_server(name, info) for name, info in servers.items()}
    for name, task in tasks.items():
        results[name] = await task

    aggregate_latency_ms = round((datetime.now(timezone.utc).timestamp() - aggregate_start) * 1000, 1)
    statuses = [r.get("status", "unknown") for r in results.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s in ("unhealthy", "unreachable") for s in statuses):
        overall = "degraded"
    else:
        overall = "partially_healthy"

    snapshot = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall": overall,
        "servers": {k: v.get("status") for k, v in results.items()},
        "latencies": {k: v.get("latency_ms") for k, v in results.items()},
    }
    _HEALTH_HISTORY.append(snapshot)

    trend = None
    if len(_HEALTH_HISTORY) >= 3:
        recent = list(_HEALTH_HISTORY)[-10:]
        healthy_count = sum(1 for h in recent if h.get("overall") == "healthy")
        if healthy_count >= 8:
            trend = "stable"
        elif healthy_count >= 5:
            trend = "fluctuating"
        else:
            trend = "degrading"

    payload = {
        "status": overall,
        "aggregate_latency_ms": aggregate_latency_ms,
        "servers": results,
        "trend": trend,
        "history_depth": len(_HEALTH_HISTORY),
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
    return web.json_response(payload, status=200 if overall == "healthy" else 207)


async def handle_stats(_request: web.Request) -> web.Response:
    payload = {
        "status": "ok",
        "service": "hybrid-coordinator",
        "stats": _snapshot_stats(),
        "collections": list(_collections.keys()),
        "harness_stats": _harness_stats,
        "capability_discovery": _hybrid_stats.get("capability_discovery", {}),
        "circuit_breakers": _circuit_breakers.get_all_stats() if _circuit_breakers else {},
    }
    lesson_refs = await _active_lesson_refs(limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_feedback(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        lesson_refs = await _active_lesson_refs(limit=2)
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
            payload = {"status": "recorded", "feedback_id": feedback_id}
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        if interaction_id and outcome:
            await _update_outcome(
                interaction_id=interaction_id,
                outcome=outcome,
                user_feedback=user_feedback,
            )
            payload = {"status": "updated"}
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        return web.json_response({"error": "missing_feedback_fields"}, status=400)
    except Exception as exc:
        return _internal_error(exc)


async def handle_simple_feedback(request: web.Request) -> web.Response:
    try:
        interaction_id = request.match_info.get("interaction_id", "")
        if not interaction_id:
            return web.json_response({"error": "interaction_id required in path"}, status=400)
        lesson_refs = await _active_lesson_refs(limit=2)
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
        payload = {"status": "recorded", "feedback_id": feedback_id}
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_feedback_evaluate(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        lesson_refs = await _active_lesson_refs(limit=2)
        feedback_response = await _feedback_api.evaluate_response(
            session_id=session_id,
            response=data.get("response", ""),
            confidence=data.get("confidence", 0.5),
            gaps=data.get("gaps", []),
            metadata=data.get("metadata"),
        )
        payload = feedback_response.dict()
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_metrics(_request: web.Request) -> web.Response:
    PROCESS_MEMORY_BYTES.set(_get_process_memory())
    if _embedding_cache_ref:
        try:
            cache = _embedding_cache_ref()
            if cache:
                from metrics import EMBEDDING_CACHE_SIZE

                size = await cache.get_cache_size()
                EMBEDDING_CACHE_SIZE.set(size)
        except Exception:
            pass
    try:
        ORCHESTRATION_ACTIVE_SESSIONS.set(len(_agent_hq.sessions))
        ORCHESTRATION_REGISTERED_AGENTS.set(len(_agent_hq.global_agents))
        from metrics import ORCHESTRATION_SESSIONS_BY_STATE

        state_counts: Dict[str, int] = {}
        for session in _agent_hq.sessions.values():
            state_name = session.state.name if hasattr(session.state, "name") else str(session.state)
            state_counts[state_name] = state_counts.get(state_name, 0) + 1
        for state_name, count in state_counts.items():
            ORCHESTRATION_SESSIONS_BY_STATE.labels(state=state_name).set(count)

        queue_status = _delegation_api.get_queue_status()
        ORCHESTRATION_PENDING_DELEGATIONS.set(queue_status.get("pending_requests", 0))
        from metrics import ORCHESTRATION_WORKSPACE_DISK_BYTES

        total_disk = 0
        mode_counts: Dict[str, int] = {}
        for ws in _workspace_manager.workspaces.values():
            mode_name = ws.mode.name if hasattr(ws.mode, "name") else str(ws.mode)
            mode_counts[mode_name] = mode_counts.get(mode_name, 0) + 1
            if ws.path.exists():
                try:
                    total_disk += sum(f.stat().st_size for f in ws.path.rglob("*") if f.is_file())
                except (OSError, PermissionError):
                    pass
        for mode_name, count in mode_counts.items():
            ORCHESTRATION_WORKSPACES_BY_MODE.labels(mode=mode_name).set(count)
        ORCHESTRATION_WORKSPACE_DISK_BYTES.set(total_disk)

        tool_report = _mcp_tool_invoker.get_usage_report()
        from metrics import ORCHESTRATION_TOOLS_RATE_LIMITED

        ORCHESTRATION_TOOLS_RATE_LIMITED.set(tool_report.get("rate_limited_tools", 0))
        ORCHESTRATION_TOOL_PENDING_APPROVALS.set(tool_report.get("pending_approvals", 0))
        from metrics import (
            BOTTLENECK_AVG_DURATION_MS,
            BOTTLENECK_COUNT,
            BOTTLENECK_P95_DURATION_MS,
            OPTIMIZATION_RECOMMENDATIONS_PENDING,
        )

        bottlenecks = _performance_profiler.identify_bottlenecks(min_call_count=5, threshold_ms=50)
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for bottleneck in bottlenecks:
            severity_counts[bottleneck.severity] += 1
            BOTTLENECK_AVG_DURATION_MS.labels(operation=bottleneck.operation).set(bottleneck.avg_duration_ms)
            BOTTLENECK_P95_DURATION_MS.labels(operation=bottleneck.operation).set(bottleneck.p95_duration_ms)
        for severity, count in severity_counts.items():
            BOTTLENECK_COUNT.labels(severity=severity).set(count)
        recommendations = _performance_profiler.generate_optimization_recommendations(bottlenecks)
        rec_by_priority: Dict[int, int] = {}
        for recommendation in recommendations:
            rec_by_priority[recommendation.priority] = rec_by_priority.get(recommendation.priority, 0) + 1
        for priority, count in rec_by_priority.items():
            OPTIMIZATION_RECOMMENDATIONS_PENDING.labels(priority=str(priority)).set(count)
    except Exception:
        pass
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


async def handle_cache_invalidate(request: web.Request) -> web.Response:
    if not _embedding_cache_ref:
        return web.json_response({"error": "cache not initialized"}, status=503)

    try:
        cache = _embedding_cache_ref()
        if not cache:
            return web.json_response({"error": "cache not available"}, status=503)

        data = await request.json()
        trigger = data.get("trigger", "manual")
        scope = data.get("scope", "all")

        from metrics import EMBEDDING_CACHE_INVALIDATIONS

        EMBEDDING_CACHE_INVALIDATIONS.labels(trigger=trigger).inc()
        lesson_refs = await _active_lesson_refs(limit=2)

        if scope == "all":
            deleted = await cache.clear_all()
            logger.info("cache_invalidation trigger=%s scope=all deleted=%d", trigger, deleted)
            payload = {"status": "ok", "keys_deleted": deleted}
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        return web.json_response({"error": "unsupported scope"}, status=400)
    except Exception as exc:
        logger.error("cache_invalidation_error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def handle_cache_stats(_request: web.Request) -> web.Response:
    if not _embedding_cache_ref:
        return web.json_response({"error": "cache not initialized"}, status=503)

    try:
        cache = _embedding_cache_ref()
        if not cache:
            return web.json_response({"error": "cache not available"}, status=503)

        stats = cache.get_stats()
        size = await cache.get_cache_size()
        stats["current_size"] = size
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            stats["active_lesson_refs"] = lesson_refs
        return web.json_response(stats)
    except Exception as exc:
        logger.error("cache_stats_error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def handle_learning_stats(_request: web.Request) -> web.Response:
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
            payload = json.loads(stats_path.read_text(encoding="utf-8"))
            lesson_refs = await _active_lesson_refs(limit=2)
            if lesson_refs and isinstance(payload, dict):
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        if _learning_pipeline:
            stats = await _learning_pipeline.get_statistics()
            lesson_refs = await _active_lesson_refs(limit=2)
            if lesson_refs and isinstance(stats, dict):
                stats["active_lesson_refs"] = lesson_refs
            return web.json_response(stats)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)

    payload = {
        "checkpoints": {"total": 0, "last_checkpoint": None},
        "backpressure": {"unprocessed_mb": 0, "paused": False},
        "backpressure_threshold_mb": 100,
        "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0},
    }
    lesson_refs = await _active_lesson_refs(limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_learning_process(_request: web.Request) -> web.Response:
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
        payload = {"status": "ok", "patterns": len(patterns), "examples": examples_count}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response({"status": "error", "detail": str(exc)}, status=500)


async def handle_learning_export(_request: web.Request) -> web.Response:
    try:
        dataset_path = await _learning_pipeline.export_dataset_for_training() if _learning_pipeline else await _generate_dataset()
        dataset_path_str = str(dataset_path) if dataset_path else ""
        count = 0
        if dataset_path_str and Path(dataset_path_str).exists():
            with open(dataset_path_str, "r", encoding="utf-8") as handle:
                count = sum(1 for _ in handle)
        payload = {"status": "ok", "dataset_path": dataset_path_str, "examples": count}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response({"status": "error", "detail": str(exc)}, status=500)


async def handle_learning_ab_compare(request: web.Request) -> web.Response:
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
        payload = {"status": "ok", "variant_a": stats_a, "variant_b": stats_b, "delta": {"avg_rating": delta}}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except RuntimeError as exc:
        return web.json_response({"error": str(exc)}, status=503)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_reload_model(request: web.Request) -> web.Response:
    from metrics import MODEL_RELOADS, MODEL_RELOAD_DURATION
    import time as _time

    try:
        body = await request.json()
    except Exception:
        body = {}
    service = body.get("service", "llama-cpp")
    if service not in _RELOAD_ALLOWLIST:
        MODEL_RELOADS.labels(service=service, status="failure").inc()
        return web.json_response({"error": "service not in allowlist"}, status=400)

    service_unit = _RELOAD_ALLOWLIST[service]
    start = _time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        "systemctl",
        "restart",
        service_unit,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await proc.communicate()
    duration = _time.monotonic() - start
    MODEL_RELOAD_DURATION.labels(service=service).observe(duration)
    lesson_refs = await _active_lesson_refs(limit=2)
    if proc.returncode == 0:
        MODEL_RELOADS.labels(service=service, status="success").inc()
        payload = {"status": "restarted", "service": service_unit, "duration_seconds": round(duration, 2)}
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

    MODEL_RELOADS.labels(service=service, status="failure").inc()
    payload = {
        "status": "failed",
        "service": service_unit,
        "error": stderr.decode("utf-8", errors="replace")[:500],
    }
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload, status=500)


async def handle_model_status(_request: web.Request) -> web.Response:
    from metrics import MODEL_ACTIVE_INFO
    import re

    results = {}
    for name, unit in _RELOAD_ALLOWLIST.items():
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "is-active",
            unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        status = stdout.decode().strip()
        model_path = "unknown"
        if name in ("llama-cpp", "llama-cpp-embed"):
            env_proc = await asyncio.create_subprocess_exec(
                "systemctl",
                "show",
                unit,
                "--property=ExecStart",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            env_out, _ = await env_proc.communicate()
            env_str = env_out.decode()
            model_match = re.search(r"--model\s+([^\s;]+)", env_str)
            if model_match:
                model_path = model_match.group(1)
        MODEL_ACTIVE_INFO.labels(service=name, model_path=model_path).set(1 if status == "active" else 0)
        results[name] = {"unit": unit, "status": status, "model_path": model_path}
    payload = {"services": results}
    lesson_refs = await _active_lesson_refs(limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_alerts_list(request: web.Request) -> web.Response:
    try:
        alert_engine = _get_alert_engine()
        severity = str(request.query.get("severity", "") or "").strip().lower()
        component = str(request.query.get("component", "") or "").strip()
        severity_filter = None
        if severity:
            try:
                severity_filter = AlertSeverity(severity)
            except ValueError:
                return web.json_response({"error": "invalid severity"}, status=400)
        alerts = alert_engine.get_active_alerts(severity=severity_filter, component=component or None)
        return web.json_response(
            {
                "alerts": [alert.to_dict() for alert in alerts],
                "count": len(alerts),
                "severity_counts": {
                    level.value: sum(1 for alert in alerts if alert.severity == level)
                    for level in AlertSeverity
                },
                "stats": alert_engine.get_stats(),
            }
        )
    except Exception as exc:
        return _internal_error(exc)


async def handle_alert_acknowledge(request: web.Request) -> web.Response:
    try:
        alert_id = str(request.match_info.get("alert_id", "") or "").strip()
        if not alert_id:
            return web.json_response({"error": "alert_id required"}, status=400)
        acknowledged = await _get_alert_engine().acknowledge_alert(alert_id)
        return web.json_response(
            {
                "alert_id": alert_id,
                "acknowledged": acknowledged,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=200 if acknowledged else 404,
        )
    except Exception as exc:
        return _internal_error(exc)


async def handle_alert_resolve(request: web.Request) -> web.Response:
    try:
        alert_id = str(request.match_info.get("alert_id", "") or "").strip()
        if not alert_id:
            return web.json_response({"error": "alert_id required"}, status=400)
        resolved = await _get_alert_engine().resolve_alert(alert_id)
        return web.json_response(
            {
                "alert_id": alert_id,
                "resolved": resolved,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status=200 if resolved else 404,
        )
    except Exception as exc:
        return _internal_error(exc)


async def handle_alert_test_create(request: web.Request) -> web.Response:
    try:
        data = await request.json() if request.can_read_body else {}
        severity_raw = str(data.get("severity", "warning") or "warning").strip().lower()
        try:
            severity = AlertSeverity(severity_raw)
        except ValueError:
            return web.json_response({"error": "invalid severity"}, status=400)
        title = str(data.get("title") or "Phase 4.1 validation alert").strip()[:120] or "Phase 4.1 validation alert"
        message = str(data.get("message") or "Synthetic deployment-monitoring-alerting validation alert").strip()[:500]
        source = str(data.get("source") or "phase-4-1-smoke").strip()[:64] or "phase-4-1-smoke"
        component = str(data.get("component") or "deployment-monitoring").strip()[:64] or "deployment-monitoring"
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        alert = await _get_alert_engine().create_alert(
            title=title,
            message=message,
            severity=severity,
            source=source,
            component=component,
            metadata=metadata,
        )
        return web.json_response({"status": "created", "alert": alert.to_dict()}, status=201)
    except Exception as exc:
        return _internal_error(exc)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/health", handle_health)
    http_app.router.add_get("/health/detailed", handle_health_detailed)
    http_app.router.add_get("/health/aggregate", handle_health_aggregate)
    http_app.router.add_get("/alerts", handle_alerts_list)
    http_app.router.add_post("/alerts/test", handle_alert_test_create)
    http_app.router.add_post("/alerts/{alert_id}/acknowledge", handle_alert_acknowledge)
    http_app.router.add_post("/alerts/{alert_id}/resolve", handle_alert_resolve)
    http_app.router.add_get("/stats", handle_stats)
    http_app.router.add_post("/feedback", handle_feedback)
    http_app.router.add_post("/feedback/{interaction_id}", handle_simple_feedback)
    http_app.router.add_post("/feedback/evaluate", handle_feedback_evaluate)
    http_app.router.add_get("/metrics", handle_metrics)
    http_app.router.add_post("/cache/invalidate", handle_cache_invalidate)
    http_app.router.add_get("/cache/stats", handle_cache_stats)
    http_app.router.add_get("/learning/stats", handle_learning_stats)
    http_app.router.add_post("/learning/process", handle_learning_process)
    http_app.router.add_post("/learning/export", handle_learning_export)
    http_app.router.add_post("/learning/ab_compare", handle_learning_ab_compare)
    http_app.router.add_post("/reload-model", handle_reload_model)
    http_app.router.add_get("/model/status", handle_model_status)
