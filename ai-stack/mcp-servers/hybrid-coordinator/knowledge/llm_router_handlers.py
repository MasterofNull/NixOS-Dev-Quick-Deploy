"""
LLM router and model coordination HTTP handlers.

Extracted from http_server.py (Phase 12.4 decomposition).

Covers:
  - /control/models/route  — classify and route task to model(s)
  - /control/models        — list available model profiles
  - /control/cache/warm    — proactive cache warming queue
  - /control/tools/suggestions — tool suggestions per domain
  - /control/llm/route     — tier-based cost routing
  - /control/llm/execute   — execute with advisor + auto-escalation
  - /control/llm/metrics   — LLM router metrics and cost savings
"""

import logging
from typing import Any, Callable, Dict, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None
_classify_and_route_task_fn: Optional[Callable[..., Any]] = None
_get_model_coordinator_fn: Optional[Callable[[], Any]] = None


def init(
    *,
    error_payload_fn: Callable[[str, Exception], Dict[str, Any]],
    classify_and_route_task_fn: Callable[..., Any],
    get_model_coordinator_fn: Callable[[], Any],
) -> None:
    global _error_payload, _classify_and_route_task_fn, _get_model_coordinator_fn
    _error_payload = error_payload_fn
    _classify_and_route_task_fn = classify_and_route_task_fn
    _get_model_coordinator_fn = get_model_coordinator_fn


async def handle_model_route(request: web.Request) -> web.Response:
    """
    POST /control/models/route — Classify and route a task to appropriate model(s).

    Phase 12.1/12.2: Model role classification and dual-model routing.
    Returns routing decision with primary/secondary model assignments.
    """
    try:
        data = await request.json()
        task = str(data.get("task") or data.get("query") or "").strip()
        if not task:
            return web.json_response({"error": "task required"}, status=400)

        context = data.get("context") if isinstance(data.get("context"), dict) else {}
        prefer_local = bool(data.get("prefer_local", True))

        result = _classify_and_route_task_fn(task, context, prefer_local=prefer_local)
        result["task"] = task

        return web.json_response(result)
    except Exception as exc:
        logger.error("handle_model_route error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_model_list(request: web.Request) -> web.Response:
    """GET /control/models — List available model profiles."""
    try:
        coordinator = _get_model_coordinator_fn()
        models = coordinator.list_available_models()
        stats = coordinator.get_routing_stats()
        return web.json_response({
            "models": models,
            "routing_stats": stats,
        })
    except Exception as exc:
        logger.error("handle_model_list error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_cache_warming_queue(request: web.Request) -> web.Response:
    """
    POST /control/cache/warm — Queue queries for proactive cache warming.
    GET /control/cache/warm — Get current warming queue batch.
    """
    try:
        coordinator = _get_model_coordinator_fn()
        if request.method == "POST":
            data = await request.json()
            queries = data.get("queries") if isinstance(data.get("queries"), list) else []
            if not queries:
                query = str(data.get("query") or "").strip()
                if query:
                    queries = [query]
            for q in queries:
                domain = data.get("domain")
                priority = int(data.get("priority", 1))
                coordinator.queue_cache_warming(q, domain, priority)
            return web.json_response({
                "status": "queued",
                "count": len(queries),
            })
        else:
            batch_size = int(request.rel_url.query.get("batch_size", "5"))
            batch = coordinator.get_cache_warming_batch(batch_size)
            return web.json_response({
                "batch": batch,
                "queue_depth": len(batch),
            })
    except Exception as exc:
        logger.error("handle_cache_warming_queue error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_tool_suggestions(request: web.Request) -> web.Response:
    """GET /control/tools/suggestions — Get tool suggestions for a domain."""
    try:
        domain = request.rel_url.query.get("domain", "ai-harness")
        task_type = request.rel_url.query.get("task_type", "")
        coordinator = _get_model_coordinator_fn()
        suggestions = coordinator.get_tool_suggestions(domain, task_type or None)
        return web.json_response({
            "domain": domain,
            "task_type": task_type or "general",
            "suggestions": suggestions,
        })
    except Exception as exc:
        logger.error("handle_tool_suggestions error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_llm_router_route(request: web.Request) -> web.Response:
    """
    POST /control/llm/route — Route task using tier-based cost optimization.

    Implements Local > Free > Paid routing strategy.
    Returns tier assignment and model selection.
    """
    try:
        from llm_router import get_router

        data = await request.json()
        task_description = str(data.get("task") or data.get("description") or "").strip()
        if not task_description:
            return web.json_response({"error": "task required"}, status=400)

        context = data.get("context") if isinstance(data.get("context"), dict) else {}

        router = get_router()
        tier, model = router.route_task(task_description, context)

        return web.json_response({
            "task": task_description,
            "tier": tier.value,
            "model": model,
            "routing_strategy": "tier-based cost optimization",
            "estimated_cost": router._estimate_cost(tier),
        })
    except ImportError:
        return web.json_response({
            "error": "llm_router not available",
            "fallback": "use /control/models/route instead"
        }, status=503)
    except Exception as exc:
        logger.error("handle_llm_router_route error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_llm_router_execute(request: web.Request) -> web.Response:
    """
    POST /control/llm/execute — Execute task with intelligent routing and auto-escalation.

    Executes task using tier-based routing with automatic escalation on failures.
    Returns result with tier, model, cost, and escalation information.
    """
    try:
        from llm_router import get_router

        data = await request.json()
        task = {
            "description": str(data.get("task") or data.get("description") or "").strip(),
            "context": data.get("context") if isinstance(data.get("context"), dict) else {},
            "type": data.get("type", "unknown"),
            "allow_escalation": bool(data.get("allow_escalation", True)),
            "allow_advisor": bool(data.get("allow_advisor", True)),
            "max_advisor_uses": int(data.get("max_advisor_uses", 3)),
        }

        if not task["description"]:
            return web.json_response({"error": "task required"}, status=400)

        router = get_router()
        result = await router.execute_with_advisor(task)

        return web.json_response(result)
    except ImportError:
        return web.json_response({
            "error": "llm_router not available",
            "fallback": "use /query or /control/models/route instead"
        }, status=503)
    except Exception as exc:
        logger.error("handle_llm_router_execute error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_llm_router_metrics(request: web.Request) -> web.Response:
    """
    GET /control/llm/metrics — Get LLM router metrics and cost savings.

    Returns tier distribution, cost estimates, escalation rates, and savings.
    """
    try:
        from llm_router import get_router

        router = get_router()
        metrics = router.get_metrics()

        return web.json_response({
            "metrics": metrics,
            "target_distribution": {
                "local": "80%",
                "free": "15%",
                "paid": "5%",
            },
            "cost_optimization_goal": "95% reduction ($600/mo → $30/mo)",
        })
    except ImportError:
        return web.json_response({
            "error": "llm_router not available",
            "message": "Tier-based routing not initialized"
        }, status=503)
    except Exception as exc:
        logger.error("handle_llm_router_metrics error=%s", exc)
        return web.json_response(_error_payload("internal_error", exc), status=500)


def register_routes(http_app: web.Application) -> None:
    # Model coordination
    http_app.router.add_post("/control/models/route", handle_model_route)
    http_app.router.add_get("/control/models", handle_model_list)
    http_app.router.add_post("/control/cache/warm", handle_cache_warming_queue)
    http_app.router.add_get("/control/cache/warm", handle_cache_warming_queue)
    http_app.router.add_get("/control/tools/suggestions", handle_tool_suggestions)
    # LLM router (tier-based cost optimization)
    http_app.router.add_post("/control/llm/route", handle_llm_router_route)
    http_app.router.add_post("/control/llm/execute", handle_llm_router_execute)
    http_app.router.add_get("/control/llm/metrics", handle_llm_router_metrics)
