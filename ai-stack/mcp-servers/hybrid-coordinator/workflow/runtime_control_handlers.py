"""
Runtime control HTTP handlers.

Extracted from http_server.py (Phase 12.4 decomposition).

Owns the runtime register/list/get/status/deploy/rollback/schedule endpoints.
All registry mutations go through runtime_manager singletons.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from aiohttp import web

from agent_registry import (
    _active_lesson_refs,
    _agent_lessons_lock,
    _load_agent_lessons_registry,
)
from runtime_manager import (
    _enrich_runtime_record,
    _execute_runtime_service_action,
    _load_runtime_registry,
    _load_runtime_scheduler_policy,
    _normalize_tags,
    _runtime_registry_lock,
    _runtime_schedule_score,
    _runtime_scheduler_policy_path,
    _save_runtime_registry,
)

logger = __import__("logging").getLogger("hybrid-coordinator")

_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None


def init(*, error_payload_fn: Callable[[str, Exception], Dict[str, Any]]) -> None:
    global _error_payload
    _error_payload = error_payload_fn


async def handle_runtime_register(request: web.Request) -> web.Response:
    """Register or update an agent runtime in local control-plane state."""
    try:
        data = await request.json()
        runtime_id = str(data.get("runtime_id") or uuid4())
        now = int(time.time())
        record = {
            "runtime_id": runtime_id,
            "name": str(data.get("name", runtime_id)),
            "profile": str(data.get("profile", "default")),
            "status": str(data.get("status", "ready")),
            "runtime_class": str(data.get("runtime_class", "generic")),
            "transport": str(data.get("transport", "http")),
            "endpoint_env_var": str(data.get("endpoint_env_var", "")),
            "service_unit": str(data.get("service_unit", "")),
            "healthcheck_url": str(data.get("healthcheck_url", "")),
            "tags": data.get("tags", []) if isinstance(data.get("tags", []), list) else [],
            "updated_at": now,
            "source": str(data.get("source", "runtime-register") or "runtime-register"),
            "persistent": bool(data.get("persistent", False)),
        }
        record = _enrich_runtime_record(record)
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            existing = registry["runtimes"].get(runtime_id, {})
            record["created_at"] = int(existing.get("created_at", now))
            record["deployments"] = existing.get("deployments", [])
            registry["runtimes"][runtime_id] = record
            await _save_runtime_registry(registry)
        payload = dict(record)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_list(_request: web.Request) -> web.Response:
    try:
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
        items = [_enrich_runtime_record(item) for item in registry.get("runtimes", {}).values()]
        items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
        payload = {"runtimes": items, "count": len(items)}
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_get(request: web.Request) -> web.Response:
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
        if not runtime:
            return web.json_response({"error": "runtime not found"}, status=404)
        payload = _enrich_runtime_record(runtime)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_status(request: web.Request) -> web.Response:
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        data = await request.json()
        status = str(data.get("status", "ready"))
        note = str(data.get("note", "")).strip()
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
            if not runtime:
                return web.json_response({"error": "runtime not found"}, status=404)
            runtime["status"] = status
            runtime["updated_at"] = int(time.time())
            if note:
                runtime.setdefault("status_notes", []).append({"ts": int(time.time()), "text": note})
            registry["runtimes"][runtime_id] = runtime
            await _save_runtime_registry(registry)
        payload = _enrich_runtime_record(runtime)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_deploy(request: web.Request) -> web.Response:
    """Record deployment events and optionally execute bounded runtime activation."""
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        data = await request.json()
        execute = bool(data.get("execute", False))
        deployment = {
            "deployment_id": str(data.get("deployment_id") or uuid4()),
            "version": str(data.get("version", "")),
            "profile": str(data.get("profile", "default")),
            "target": str(data.get("target", "local")),
            "status": str(data.get("status", "deployed")),
            "created_at": int(time.time()),
            "note": str(data.get("note", "")),
        }
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
            if not runtime:
                return web.json_response({"error": "runtime not found"}, status=404)
            runtime = _enrich_runtime_record(runtime)
            action_result: Dict[str, Any] | None = None
            response_status = 200
            if execute:
                action_result, response_status = await _execute_runtime_service_action(runtime, action="deploy")
                deployment["execution"] = action_result
                deployment["status"] = "executed" if response_status == 200 else "activation_failed"
            runtime.setdefault("deployments", []).append(deployment)
            runtime["updated_at"] = int(time.time())
            if execute and action_result:
                runtime["status"] = "ready" if response_status == 200 else "degraded"
                runtime.setdefault("status_notes", []).append({
                    "ts": int(time.time()),
                    "text": f"runtime deploy execute={execute} status={deployment['status']}",
                })
            registry["runtimes"][runtime_id] = runtime
            await _save_runtime_registry(registry)
        payload = {"runtime_id": runtime_id, "deployment": deployment}
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload, status=response_status)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_rollback(request: web.Request) -> web.Response:
    """Record rollback requests and optionally execute bounded runtime rollback."""
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        data = await request.json()
        to_deployment_id = str(data.get("to_deployment_id", "")).strip()
        reason = str(data.get("reason", "")).strip()
        execute = bool(data.get("execute", False))
        if not to_deployment_id:
            return web.json_response({"error": "to_deployment_id required"}, status=400)
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
            if not runtime:
                return web.json_response({"error": "runtime not found"}, status=404)
            runtime = _enrich_runtime_record(runtime)
            rollback_entry = {
                "to_deployment_id": to_deployment_id,
                "reason": reason,
                "created_at": int(time.time()),
            }
            action_result: Dict[str, Any] | None = None
            response_status = 200
            if execute:
                action_result, response_status = await _execute_runtime_service_action(runtime, action="rollback")
                rollback_entry["execution"] = action_result
                rollback_entry["status"] = "executed" if response_status == 200 else "rollback_failed"
            runtime.setdefault("rollbacks", []).append(rollback_entry)
            runtime["updated_at"] = int(time.time())
            if execute and action_result:
                runtime["status"] = "ready" if response_status == 200 else "degraded"
                runtime.setdefault("status_notes", []).append({
                    "ts": int(time.time()),
                    "text": f"runtime rollback execute={execute} status={rollback_entry.get('status', 'recorded')}",
                })
            registry["runtimes"][runtime_id] = runtime
            await _save_runtime_registry(registry)
        payload = {"runtime_id": runtime_id, "to_deployment_id": to_deployment_id, "status": "recorded"}
        if execute:
            payload["execution"] = action_result
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload, status=response_status)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_schedule_policy(_request: web.Request) -> web.Response:
    """Return active runtime scheduler policy (declarative source + defaults)."""
    try:
        path = _runtime_scheduler_policy_path()
        policy = _load_runtime_scheduler_policy()
        payload = {
            "policy": policy,
            "source": str(path),
            "exists": path.exists(),
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_schedule(request: web.Request) -> web.Response:
    """Select the best runtime candidate for a task objective + requirements."""
    try:
        data = await request.json()
        objective = str(data.get("objective") or data.get("query") or "").strip()
        requirements = data.get("requirements", {}) if isinstance(data.get("requirements"), dict) else {}
        strategy = str(data.get("strategy", "weighted")).strip().lower()
        include_degraded = bool(data.get("include_degraded", False))
        policy = _load_runtime_scheduler_policy()
        selection = policy.get("selection", {}) if isinstance(policy, dict) else {}
        allowed_statuses = {
            str(s).strip().lower()
            for s in selection.get("allowed_statuses", ["ready"])
            if str(s).strip()
        }
        if include_degraded:
            allowed_statuses.add("degraded")
        require_all_tags = bool(selection.get("require_all_tags", False))
        max_candidates = max(1, int(selection.get("max_candidates", 5)))
        req_tags = _normalize_tags(requirements.get("tags", []))
        req_class = str(requirements.get("runtime_class", "")).strip().lower()
        req_transport = str(requirements.get("transport", "")).strip().lower()
        now = int(time.time())

        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtimes = list((registry.get("runtimes", {}) or {}).values())
            candidates: List[Dict[str, Any]] = []
            for runtime in runtimes:
                runtime_id = str(runtime.get("runtime_id", "")).strip()
                status = str(runtime.get("status", "unknown")).strip().lower()
                if not runtime_id:
                    continue
                if allowed_statuses and status not in allowed_statuses:
                    continue
                runtime_tags = _normalize_tags(runtime.get("tags", []))
                if req_tags:
                    overlap = set(req_tags) & set(runtime_tags)
                    if require_all_tags and not all(t in runtime_tags for t in req_tags):
                        continue
                    if not require_all_tags and not overlap:
                        continue
                if req_class and str(runtime.get("runtime_class", "")).strip().lower() != req_class:
                    continue
                if req_transport and str(runtime.get("transport", "")).strip().lower() != req_transport:
                    continue

                scored = _runtime_schedule_score(runtime, requirements, policy, now)
                candidates.append(
                    {
                        "runtime_id": runtime_id,
                        "name": runtime.get("name", runtime_id),
                        "status": runtime.get("status", "unknown"),
                        "runtime_class": runtime.get("runtime_class", "generic"),
                        "transport": runtime.get("transport", "http"),
                        "tags": _normalize_tags(runtime.get("tags", [])),
                        "updated_at": int(runtime.get("updated_at") or 0),
                        "score": scored["score"],
                        "score_components": scored["components"],
                    }
                )

            candidates.sort(key=lambda x: (float(x.get("score", 0.0)), int(x.get("updated_at", 0))), reverse=True)
            top_candidates = candidates[:max_candidates]
            if not top_candidates:
                return web.json_response(
                    {
                        "error": "no_runtime_candidate",
                        "objective": objective,
                        "requirements": {
                            "runtime_class": req_class,
                            "transport": req_transport,
                            "tags": req_tags,
                        },
                        "allowed_statuses": sorted(allowed_statuses),
                    },
                    status=404,
                )

            selected = top_candidates[0]
            selected_runtime = registry.get("runtimes", {}).get(selected["runtime_id"])
            if isinstance(selected_runtime, dict):
                selected_runtime.setdefault("schedule_events", []).append(
                    {
                        "ts": now,
                        "objective": objective[:500],
                        "strategy": strategy,
                        "score": selected.get("score", 0.0),
                        "requirements": {
                            "runtime_class": req_class,
                            "transport": req_transport,
                            "tags": req_tags,
                        },
                    }
                )
                selected_runtime["schedule_events"] = selected_runtime["schedule_events"][-50:]
                selected_runtime["updated_at"] = now
                registry["runtimes"][selected["runtime_id"]] = selected_runtime
                await _save_runtime_registry(registry)

        payload = {
            "objective": objective,
            "strategy": strategy,
            "selected": selected,
            "candidate_count": len(candidates),
            "candidates": top_candidates,
            "policy": {
                "allowed_statuses": sorted(allowed_statuses),
                "max_candidates": max_candidates,
                "require_all_tags": require_all_tags,
            },
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_deregister(request: web.Request) -> web.Response:
    """DELETE /control/runtimes/{runtime_id} — Phase 42: remove a runtime from the registry."""
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        if not runtime_id:
            return web.json_response({"error": "runtime_id required"}, status=400)
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            if runtime_id not in registry.get("runtimes", {}):
                return web.json_response({"error": "runtime not found"}, status=404)
            removed = registry["runtimes"].pop(runtime_id)
            await _save_runtime_registry(registry)
        return web.json_response({
            "runtime_id": runtime_id,
            "deregistered": True,
            "name": removed.get("name", runtime_id),
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_deployments_list(request: web.Request) -> web.Response:
    """GET /control/runtimes/{runtime_id}/deployments — Phase 42: deployment history."""
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        limit = min(int(request.rel_url.query.get("limit", "20") or "20"), 100)
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
        if not runtime:
            return web.json_response({"error": "runtime not found"}, status=404)
        deployments = list(runtime.get("deployments", []))
        rollbacks = list(runtime.get("rollbacks", []))
        # Merge and sort by created_at descending
        events: List[Dict[str, Any]] = []
        for d in deployments:
            events.append({"event_type": "deployment", **d})
        for r in rollbacks:
            events.append({"event_type": "rollback", **r})
        events.sort(key=lambda e: int(e.get("created_at") or 0), reverse=True)
        events = events[:limit]
        return web.json_response({
            "runtime_id": runtime_id,
            "count": len(events),
            "events": events,
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_fleet_summary(_request: web.Request) -> web.Response:
    """GET /control/fleet/summary — Phase 42: fleet-wide rollup by profile and status."""
    try:
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
        runtimes = list((registry.get("runtimes", {}) or {}).values())

        by_status: Dict[str, int] = {}
        by_profile: Dict[str, int] = {}
        recent_deployments: List[Dict[str, Any]] = []

        for rt in runtimes:
            status = str(rt.get("status", "unknown"))
            profile = str(rt.get("profile", "default"))
            by_status[status] = by_status.get(status, 0) + 1
            by_profile[profile] = by_profile.get(profile, 0) + 1
            # Collect most recent deployment per runtime
            deployments = rt.get("deployments", [])
            if deployments:
                latest = max(deployments, key=lambda d: int(d.get("created_at") or 0))
                recent_deployments.append({
                    "runtime_id": rt.get("runtime_id", ""),
                    "name": rt.get("name", ""),
                    "profile": profile,
                    "status": rt.get("status", "unknown"),
                    "last_deployment": latest,
                })

        recent_deployments.sort(
            key=lambda x: int((x.get("last_deployment") or {}).get("created_at") or 0),
            reverse=True,
        )

        return web.json_response({
            "total_runtimes": len(runtimes),
            "by_status": by_status,
            "by_profile": by_profile,
            "recent_deployments": recent_deployments[:10],
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_runtime_health(request: web.Request) -> web.Response:
    """GET /control/runtimes/{runtime_id}/health — Phase 42: live healthcheck probe."""
    try:
        runtime_id = request.match_info.get("runtime_id", "")
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = registry.get("runtimes", {}).get(runtime_id)
        if not runtime:
            return web.json_response({"error": "runtime not found"}, status=404)
        runtime = _enrich_runtime_record(runtime)
        healthcheck_url = str(runtime.get("healthcheck_url", "") or "").strip()
        if not healthcheck_url:
            return web.json_response({
                "runtime_id": runtime_id,
                "health": "unknown",
                "reason": "no healthcheck_url configured",
            }, status=200)
        probe_start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(healthcheck_url)
            latency_ms = round((time.monotonic() - probe_start) * 1000, 1)
            healthy = resp.status_code < 400
            return web.json_response({
                "runtime_id": runtime_id,
                "health": "healthy" if healthy else "unhealthy",
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "healthcheck_url": healthcheck_url,
            })
        except Exception as probe_err:
            latency_ms = round((time.monotonic() - probe_start) * 1000, 1)
            return web.json_response({
                "runtime_id": runtime_id,
                "health": "unreachable",
                "error": str(probe_err)[:200],
                "latency_ms": latency_ms,
                "healthcheck_url": healthcheck_url,
            }, status=200)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


# ── Budget / cost guardrail policy (Phase 45) ─────────────────────────────────

_BUDGET_POLICY_PATH = Path(
    os.getenv(
        "RUNTIME_BUDGET_POLICY_FILE",
        str(Path(__file__).parent.parent / "config" / "runtime-budget-policy.json"),
    )
)
_budget_policy_lock = asyncio.Lock()

_BUDGET_POLICY_SCHEMA = {
    "required_top": {"version", "default"},
    "default_fields": {"token_limit", "tool_call_limit", "time_limit_seconds", "fail_safe"},
    "valid_fail_safe": {"abort", "warn", "checkpoint"},
}


def _load_budget_policy_sync() -> Dict[str, Any]:
    if _BUDGET_POLICY_PATH.exists():
        try:
            return json.loads(_BUDGET_POLICY_PATH.read_text())
        except Exception:
            pass
    return {
        "version": "1.0",
        "default": {"token_limit": 8000, "tool_call_limit": 40,
                    "time_limit_seconds": 300, "fail_safe": "abort",
                    "warn_threshold_pct": 80},
        "per_mode": {},
        "enforcement": {"enabled": True, "scope": ["session", "workflow_run"],
                        "emit_telemetry": True},
    }


def check_budget_policy(usage: Dict[str, Any], mode: str = "") -> Dict[str, Any]:
    """Check usage against the active budget policy.  Returns {over_budget, field, limit, used, action}."""
    policy = _load_budget_policy_sync()
    limits = dict(policy.get("default", {}))
    per_mode = policy.get("per_mode", {})
    if mode and mode in per_mode:
        limits.update(per_mode[mode])
    token_limit = int(limits.get("token_limit") or 0)
    tool_limit = int(limits.get("tool_call_limit") or 0)
    tokens_used = int(usage.get("tokens_used") or 0)
    tools_used = int(usage.get("tool_calls_used") or 0)
    fail_safe = str(limits.get("fail_safe") or "abort")
    if token_limit and tokens_used >= token_limit:
        return {"over_budget": True, "field": "token_limit", "limit": token_limit,
                "used": tokens_used, "action": fail_safe}
    if tool_limit and tools_used >= tool_limit:
        return {"over_budget": True, "field": "tool_call_limit", "limit": tool_limit,
                "used": tools_used, "action": fail_safe}
    return {"over_budget": False}


async def handle_budget_policy_get(request: web.Request) -> web.Response:
    """GET /control/budget/policy — return active budget guardrail policy."""
    try:
        async with _budget_policy_lock:
            policy = _load_budget_policy_sync()
        return web.json_response({
            "policy": policy,
            "policy_file": str(_BUDGET_POLICY_PATH),
            "file_exists": _BUDGET_POLICY_PATH.exists(),
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_budget_policy_post(request: web.Request) -> web.Response:
    """POST /control/budget/policy — update budget guardrail policy at runtime."""
    try:
        data = await request.json()
        # Validate required structure
        if "default" not in data:
            return web.json_response(
                {"error": "missing required field 'default' in policy body"}, status=400
            )
        default_block = data["default"]
        fail_safe = str(default_block.get("fail_safe") or "abort")
        if fail_safe not in _BUDGET_POLICY_SCHEMA["valid_fail_safe"]:
            return web.json_response(
                {"error": f"invalid fail_safe '{fail_safe}'; must be one of: abort, warn, checkpoint"},
                status=400,
            )
        # Merge with existing (allow partial updates)
        async with _budget_policy_lock:
            existing = _load_budget_policy_sync()
            existing["default"].update(default_block)
            if "per_mode" in data:
                existing.setdefault("per_mode", {}).update(data["per_mode"])
            if "enforcement" in data:
                existing.setdefault("enforcement", {}).update(data["enforcement"])
            existing["version"] = str(data.get("version") or existing.get("version") or "1.0")
            existing["updated_at"] = int(time.time())
            try:
                _BUDGET_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
                _BUDGET_POLICY_PATH.write_text(json.dumps(existing, indent=2))
            except OSError as write_err:
                logger.warning("budget policy: could not persist to %s: %s",
                               _BUDGET_POLICY_PATH, write_err)
        logger.info("budget policy updated: token_limit=%s tool_call_limit=%s fail_safe=%s",
                    existing["default"].get("token_limit"),
                    existing["default"].get("tool_call_limit"),
                    existing["default"].get("fail_safe"))
        return web.json_response({"ok": True, "policy": existing})
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/control/runtimes/register", handle_runtime_register)
    http_app.router.add_get("/control/runtimes", handle_runtime_list)
    http_app.router.add_get("/control/runtimes/{runtime_id}", handle_runtime_get)
    http_app.router.add_delete("/control/runtimes/{runtime_id}", handle_runtime_deregister)
    http_app.router.add_post("/control/runtimes/{runtime_id}/status", handle_runtime_status)
    http_app.router.add_post("/control/runtimes/{runtime_id}/deployments", handle_runtime_deploy)
    http_app.router.add_get("/control/runtimes/{runtime_id}/deployments", handle_runtime_deployments_list)
    http_app.router.add_post("/control/runtimes/{runtime_id}/rollback", handle_runtime_rollback)
    http_app.router.add_get("/control/runtimes/{runtime_id}/health", handle_runtime_health)
    http_app.router.add_get("/control/fleet/summary", handle_fleet_summary)
    http_app.router.add_get("/control/runtimes/schedule/policy", handle_runtime_schedule_policy)
    http_app.router.add_post("/control/runtimes/schedule/select", handle_runtime_schedule)
    http_app.router.add_get("/control/budget/policy", handle_budget_policy_get)
    http_app.router.add_post("/control/budget/policy", handle_budget_policy_post)
