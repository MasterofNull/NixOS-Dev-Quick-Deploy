"""
core/status_service.py — StatusService for the hybrid-coordinator.

Phase R2.2 (Strangler Fig): extracted from http_server.py:run_http_mode() closures.
Handles: /status, /api/hardware/state, /stats/delegate

Dependencies injected via configure() (called from http_server.init()):
  - local_llm_healthy_ref: Callable[[], bool]
  - queue_depth_ref: Callable[[], int]
  - queue_max_ref: Callable[[], int]

All other dependencies imported directly from their origin modules (no http_server import).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Optional

import httpx
from aiohttp import web

from agent_registry import (
    _active_lesson_refs,
    _agent_lessons_lock,
    _load_agent_lessons_registry,
)
from ai_coordinator import get_routing_stats as _ai_coordinator_get_routing_stats
from auto_quality_improver import get_improvement_summary as _get_auto_improvement_summary
from config import Config, routing_config
from delegation_handlers import (
    _agent_pool_status_snapshot,
    _delegated_quality_status_snapshot,
)
from generator_critic import get_critic_stats as _get_generator_critic_stats
from inference_param_manager import get_ipm
from lesson_effectiveness_tracker import get_lesson_effectiveness_stats as _get_lesson_effectiveness_stats
from memory_manager import get_memory_latency_metrics
from model_coordinator import get_model_coordinator as _get_model_coordinator
from pattern_integration import (
    get_pattern_effectiveness as _get_pattern_effectiveness,
    get_pattern_stats as _get_pattern_stats,
)
from quality_cache import get_cache_stats as _get_quality_cache_stats
from quality_monitor import (
    get_health_summary as _get_quality_health_summary,
    get_monitor_stats as _get_quality_monitor_stats,
)
from rag_reflection import get_reflection_stats as _get_rag_reflection_stats
from real_time_learning_engine import (
    _capability_gap_status_snapshot,
    _meta_learning_status_snapshot,
    _real_time_learning_status_snapshot,
)
from remediation_tracker import get_remediation_success_rate as _get_remediation_success_rate
from route_handler import get_route_search_metrics as _get_route_search_metrics
from skill_usage_tracker import get_skill_usage_stats as _get_skill_usage_stats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Injected runtime refs (set by configure(), called from http_server.init())
# ---------------------------------------------------------------------------

_local_llm_healthy_ref: Optional[Callable[[], bool]] = None
_queue_depth_ref: Optional[Callable[[], int]] = None
_queue_max_ref: Optional[Callable[[], int]] = None


def configure(
    local_llm_healthy_ref: Callable[[], bool],
    queue_depth_ref: Callable[[], int],
    queue_max_ref: Callable[[], int],
) -> None:
    """Inject runtime dependency refs. Call from http_server.init()."""
    global _local_llm_healthy_ref, _queue_depth_ref, _queue_max_ref
    _local_llm_healthy_ref = local_llm_healthy_ref
    _queue_depth_ref = queue_depth_ref
    _queue_max_ref = queue_max_ref


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def handle_status(request: web.Request) -> web.Response:
    """GET /status — model loading status and health snapshot."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as hc:
            resp = await hc.get(f"{Config.LLAMA_CPP_URL}/health")
            llama_data = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            llama_status = llama_data.get("status", "unknown")
            loading = llama_status == "loading"
    except Exception as exc:
        llama_status = "unreachable"
        loading = False
        logger.debug("handle_status llama.cpp probe failed: %s", exc)

    threshold = await routing_config.get_threshold()

    healthy = _local_llm_healthy_ref() if _local_llm_healthy_ref is not None else False
    q_depth = _queue_depth_ref() if _queue_depth_ref is not None else 0
    q_max = _queue_max_ref() if _queue_max_ref is not None else 0

    payload: dict[str, Any] = {
        "service": "hybrid-coordinator",
        "local_llm": {
            "url": Config.LLAMA_CPP_URL,
            "status": llama_status,
            "loading": loading,
            "healthy": healthy,
            "model_name": os.getenv("LLAMA_MODEL_NAME", "unknown"),
            "queue_depth": q_depth,
            "queue_max": q_max,
        },
        "routing": {
            "threshold": threshold,
            "local_supports_json": (
                os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true"
            ),
            "complexity_routing": _ai_coordinator_get_routing_stats(),
        },
        "model_coordination": _get_model_coordinator().get_routing_stats(),
        "rag_reflection_stats": _get_rag_reflection_stats(),
        "generator_critic_stats": _get_generator_critic_stats(),
        "quality_cache_stats": _get_quality_cache_stats(),
        "quality_health": _get_quality_health_summary(
            reflection_stats=_get_rag_reflection_stats(),
            critic_stats=_get_generator_critic_stats(),
            cache_stats=_get_quality_cache_stats(),
        ),
        "quality_monitor": _get_quality_monitor_stats(),
        "auto_quality_improvement": _get_auto_improvement_summary(),
        "agent_pool": _agent_pool_status_snapshot(),
        "delegated_quality_assurance": _delegated_quality_status_snapshot(),
        "capability_gap_automation": _capability_gap_status_snapshot(),
        "real_time_learning": _real_time_learning_status_snapshot(),
        "meta_learning": _meta_learning_status_snapshot(),
        "skill_usage_stats": _get_skill_usage_stats(),
        "pattern_stats": _get_pattern_stats(),
        "pattern_effectiveness": _get_pattern_effectiveness(),
        "remediation_success_rate": _get_remediation_success_rate(),
        "memory_latency_metrics": get_memory_latency_metrics(),
        "route_search_metrics": _get_route_search_metrics(),
        "lesson_effectiveness_stats": _get_lesson_effectiveness_stats(),
    }

    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs

    return web.json_response(payload)


async def handle_hardware_state(request: web.Request) -> web.Response:
    """GET /api/hardware/state — current thermal and RAM metrics."""
    from dataclasses import asdict
    state = await get_ipm().hardware_state()
    return web.json_response(asdict(state))


async def handle_delegate_stats(request: web.Request) -> web.Response:
    """GET /stats/delegate — delegation success rate from audit log.

    Reads the ai-audit-sidecar JSONL log under the coordinator's own
    process credentials (ai-hybrid:ai-stack), so callers like aq-qa
    do not need direct file-system group membership to get the rate.

    Query params:
      window_s  — lookback window in seconds (default 86400 = 24h)

    Response:
      {total, ok, success_rate, window_s, skipped_probes}
    """
    try:
        window_s = int(request.rel_url.query.get("window_s", "86400"))
    except (TypeError, ValueError):
        window_s = 86400

    audit_log = os.getenv(
        "TOOL_AUDIT_LOG_PATH",
        "/var/log/ai-audit-sidecar/tool-audit.jsonl",
    )
    now = time.time()
    total = 0
    ok = 0
    skipped_probes = 0
    error_msg = None
    try:
        with open(audit_log, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except Exception:
                    continue
                if entry.get("tool_name") != "ai_coordinator_delegate":
                    continue
                ts_str = entry.get("timestamp", "")
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if now - ts > window_s:
                    continue
                latency_ms = float(entry.get("latency_ms") or 0)
                err_msg_e = entry.get("error_message") or ""
                is_probe = (
                    (
                        entry.get("outcome") == "error"
                        and err_msg_e == "http_status_504"
                        and latency_ms < 15000
                    )
                    or err_msg_e.startswith("blocked_endpoint_pattern:")
                )
                if is_probe:
                    skipped_probes += 1
                    continue
                outcome = entry.get("outcome", "")
                _TERMINAL_OUTCOMES = {"success", "error", "timeout", "failed"}
                if outcome not in _TERMINAL_OUTCOMES:
                    continue
                total += 1
                if outcome == "success":
                    ok += 1
    except OSError as exc:
        error_msg = str(exc)
    except Exception as exc:
        error_msg = str(exc)

    if error_msg:
        return web.json_response(
            {"error": error_msg, "total": 0, "ok": 0, "window_s": window_s},
            status=503,
        )
    success_rate = round(ok / total, 3) if total > 0 else None
    return web.json_response({
        "total": total,
        "ok": ok,
        "success_rate": success_rate,
        "window_s": window_s,
        "skipped_probes": skipped_probes,
    })


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all StatusService routes on the given aiohttp Application."""
    app.router.add_get("/status", handle_status)
    app.router.add_get("/api/hardware/state", handle_hardware_state)
    app.router.add_get("/stats/delegate", handle_delegate_stats)
