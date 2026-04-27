"""
Workflow session handlers for the hybrid-coordinator HTTP server.

Extracted from http_server.py during Phase 11.3 decomposition. This module
owns workflow session persistence and the workflow-oriented HTTP endpoints,
while core planner/runtime helpers remain in http_server.py and are injected
via init().
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

_build_workflow_plan: Optional[Callable[..., Dict[str, Any]]] = None
_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None
_audit_planned_tools: Optional[Callable[..., Any]] = None
_phase_tool_names: Optional[Callable[[Dict[str, Any]], List[str]]] = None
_load_lesson_refs: Optional[Callable[..., Any]] = None
_ralph_request_headers: Optional[Callable[[], Dict[str, str]]] = None
_workflow_sessions_lock: Optional[Any] = None
_normalize_safety_mode: Optional[Callable[[str], str]] = None
_default_budget: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
_default_usage: Optional[Callable[[], Dict[str, Any]]] = None
_ensure_session_runtime_fields: Optional[Callable[[Dict[str, Any]], None]] = None
_session_lineage: Optional[Callable[[Dict[str, Any], str], List[str]]] = None
_budget_exceeded: Optional[Callable[[Dict[str, Any]], str]] = None
_load_runtime_safety_policy: Optional[Callable[[], Dict[str, Any]]] = None
_check_isolation_constraints: Optional[Callable[[Dict[str, Any], Dict[str, Any]], str]] = None
_resolve_isolation_profile: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
_load_and_validate_workflow_blueprints: Optional[Callable[[], Dict[str, Any]]] = None
_coerce_orchestration_context: Optional[Callable[[Any], Dict[str, Any]]] = None
_build_workflow_run_session: Optional[Callable[..., Dict[str, Any]]] = None
_apply_consensus_update: Optional[Callable[..., Dict[str, Any]]] = None
_apply_arbiter_update: Optional[Callable[..., Dict[str, Any]]] = None
_build_orchestration_team: Optional[Callable[..., Dict[str, Any]]] = None
_agent_evaluations_lock: Optional[Any] = None
_load_agent_evaluations_registry: Optional[Callable[[], Any]] = None
_save_agent_evaluations_registry: Optional[Callable[[Dict[str, Any]], Any]] = None
_record_agent_consensus_event: Optional[Callable[..., Dict[str, Any]]] = None
_record_agent_runtime_event: Optional[Callable[..., Dict[str, Any]]] = None
_performance_profiler: Optional[Any] = None
_build_tooling_manifest: Optional[Callable[..., Dict[str, Any]]] = None
_workflow_tool_catalog: Optional[Callable[..., List[Dict[str, str]]]] = None
_default_intent_contract: Optional[Callable[[str], Dict[str, Any]]] = None
_ralph_wiggum_url: str = ""


def init(
    *,
    build_workflow_plan_fn: Callable[..., Dict[str, Any]],
    error_payload_fn: Callable[[str, Exception], Dict[str, Any]],
    audit_planned_tools_fn: Callable[..., Any],
    phase_tool_names_fn: Callable[[Dict[str, Any]], List[str]],
    load_lesson_refs_fn: Callable[..., Any],
    ralph_request_headers_fn: Callable[[], Dict[str, str]],
    workflow_sessions_lock: Any,
    normalize_safety_mode_fn: Callable[[str], str],
    default_budget_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    default_usage_fn: Callable[[], Dict[str, Any]],
    ensure_session_runtime_fields_fn: Callable[[Dict[str, Any]], None],
    session_lineage_fn: Callable[[Dict[str, Any], str], List[str]],
    budget_exceeded_fn: Callable[[Dict[str, Any]], str],
    load_runtime_safety_policy_fn: Callable[[], Dict[str, Any]],
    check_isolation_constraints_fn: Callable[[Dict[str, Any], Dict[str, Any]], str],
    resolve_isolation_profile_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    load_and_validate_workflow_blueprints_fn: Callable[[], Dict[str, Any]],
    coerce_orchestration_context_fn: Callable[[Any], Dict[str, Any]],
    build_workflow_run_session_fn: Callable[..., Dict[str, Any]],
    apply_consensus_update_fn: Callable[..., Dict[str, Any]],
    apply_arbiter_update_fn: Callable[..., Dict[str, Any]],
    build_orchestration_team_fn: Callable[..., Dict[str, Any]],
    agent_evaluations_lock: Any,
    load_agent_evaluations_registry_fn: Callable[[], Any],
    save_agent_evaluations_registry_fn: Callable[[Dict[str, Any]], Any],
    record_agent_consensus_event_fn: Callable[..., Dict[str, Any]],
    record_agent_runtime_event_fn: Callable[..., Dict[str, Any]],
    performance_profiler: Any,
    build_tooling_manifest_fn: Callable[..., Dict[str, Any]],
    workflow_tool_catalog_fn: Callable[..., List[Dict[str, str]]],
    default_intent_contract_fn: Callable[[str], Dict[str, Any]],
    ralph_wiggum_url: str,
) -> None:
    global _build_workflow_plan, _error_payload, _audit_planned_tools, _phase_tool_names
    global _load_lesson_refs, _ralph_request_headers, _workflow_sessions_lock
    global _normalize_safety_mode, _default_budget, _default_usage
    global _ensure_session_runtime_fields, _session_lineage, _budget_exceeded
    global _load_runtime_safety_policy, _check_isolation_constraints, _resolve_isolation_profile
    global _load_and_validate_workflow_blueprints, _coerce_orchestration_context
    global _build_workflow_run_session, _apply_consensus_update, _apply_arbiter_update
    global _build_orchestration_team, _agent_evaluations_lock
    global _load_agent_evaluations_registry, _save_agent_evaluations_registry
    global _record_agent_consensus_event, _record_agent_runtime_event
    global _performance_profiler, _build_tooling_manifest, _workflow_tool_catalog
    global _default_intent_contract, _ralph_wiggum_url

    _build_workflow_plan = build_workflow_plan_fn
    _error_payload = error_payload_fn
    _audit_planned_tools = audit_planned_tools_fn
    _phase_tool_names = phase_tool_names_fn
    _load_lesson_refs = load_lesson_refs_fn
    _ralph_request_headers = ralph_request_headers_fn
    _workflow_sessions_lock = workflow_sessions_lock
    _normalize_safety_mode = normalize_safety_mode_fn
    _default_budget = default_budget_fn
    _default_usage = default_usage_fn
    _ensure_session_runtime_fields = ensure_session_runtime_fields_fn
    _session_lineage = session_lineage_fn
    _budget_exceeded = budget_exceeded_fn
    _load_runtime_safety_policy = load_runtime_safety_policy_fn
    _check_isolation_constraints = check_isolation_constraints_fn
    _resolve_isolation_profile = resolve_isolation_profile_fn
    _load_and_validate_workflow_blueprints = load_and_validate_workflow_blueprints_fn
    _coerce_orchestration_context = coerce_orchestration_context_fn
    _build_workflow_run_session = build_workflow_run_session_fn
    _apply_consensus_update = apply_consensus_update_fn
    _apply_arbiter_update = apply_arbiter_update_fn
    _build_orchestration_team = build_orchestration_team_fn
    _agent_evaluations_lock = agent_evaluations_lock
    _load_agent_evaluations_registry = load_agent_evaluations_registry_fn
    _save_agent_evaluations_registry = save_agent_evaluations_registry_fn
    _record_agent_consensus_event = record_agent_consensus_event_fn
    _record_agent_runtime_event = record_agent_runtime_event_fn
    _performance_profiler = performance_profiler
    _build_tooling_manifest = build_tooling_manifest_fn
    _workflow_tool_catalog = workflow_tool_catalog_fn
    _default_intent_contract = default_intent_contract_fn
    _ralph_wiggum_url = ralph_wiggum_url


def _workflow_sessions_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "workflow-sessions.json"


async def _active_lesson_refs(limit: int = 2) -> List[Dict[str, Any]]:
    refs = await _load_lesson_refs(limit=limit)
    return refs if isinstance(refs, list) else []


def _internal_error(exc: Exception) -> web.Response:
    return web.json_response(_error_payload("internal_error", exc), status=500)


async def _load_workflow_sessions() -> Dict[str, Any]:
    path = _workflow_sessions_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        backfill_count = 0
        for session in data.values():
            if not isinstance(session, dict):
                continue
            ic = session.get("intent_contract")
            if not isinstance(ic, dict) or not ic:
                objective = str(session.get("objective", "") or "").strip()
                session["intent_contract"] = _default_intent_contract(objective)
                backfill_count += 1
        if backfill_count:
            await _save_workflow_sessions(data)
        return data
    except Exception:
        return {}


async def _save_workflow_sessions(data: Dict[str, Any]) -> None:
    path = _workflow_sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


async def handle_workflow_plan(request: web.Request) -> web.Response:
    try:
        if request.method == "POST":
            data = await request.json()
            query = (data.get("query") or data.get("prompt") or "").strip()
            include_debug_metadata = bool(data.get("include_debug_metadata") or data.get("debug"))
        else:
            data = {}
            query = (request.rel_url.query.get("q") or "").strip()
            include_debug_metadata = request.rel_url.query.get("debug", "0").strip().lower() in {"1", "true", "yes"}
        if not query:
            return web.json_response({"error": "query required"}, status=400)
        plan_start = time.time()
        result = _build_workflow_plan(query, include_debug_metadata=include_debug_metadata)
        plan_duration_ms = (time.time() - plan_start) * 1000
        _performance_profiler.record_metric("workflow_plan_build", plan_duration_ms, {"query_len": len(query)})
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            result["active_lesson_refs"] = lesson_refs
            metadata = result.get("metadata")
            if isinstance(metadata, dict):
                metadata["active_lesson_refs"] = lesson_refs
        return web.json_response(result)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_tooling_manifest(request: web.Request) -> web.Response:
    try:
        if request.method == "POST":
            data = await request.json()
            query = (data.get("query") or data.get("prompt") or "").strip()
        else:
            data = {}
            query = (request.rel_url.query.get("q") or "").strip()
        if not query:
            return web.json_response({"error": "query required"}, status=400)
        tools, tool_security = _audit_planned_tools(query, _workflow_tool_catalog(query))
        plan = _build_workflow_plan(query, tools=tools, tool_security=tool_security)
        result = _build_tooling_manifest(
            query,
            tools,
            runtime=str(data.get("runtime") or request.rel_url.query.get("runtime") or "python"),
            max_tools=data.get("max_tools"),
            max_result_chars=data.get("max_result_chars"),
            phases=[
                {"id": str(phase.get("id", "")).strip(), "tools": _phase_tool_names(phase)}
                for phase in plan.get("phases", [])
                if isinstance(phase, dict)
            ],
            tool_security=tool_security,
        )
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            result["active_lesson_refs"] = lesson_refs
            metadata = result.get("metadata")
            if isinstance(metadata, dict):
                metadata["active_lesson_refs"] = lesson_refs
        return web.json_response(result)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_orchestrate(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        prompt = (data.get("prompt") or data.get("query") or "").strip()
        if not prompt:
            return web.json_response({"error": "prompt required"}, status=400)
        payload = {"prompt": prompt}
        for key in ("backend", "max_iterations", "require_approval", "context"):
            if key in data:
                payload[key] = data[key]
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{_ralph_wiggum_url.rstrip('/')}/tasks",
                headers=_ralph_request_headers(),
                json=payload,
            )
        response_payload = response.json()
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs and isinstance(response_payload, dict):
            response_payload["active_lesson_refs"] = lesson_refs
        return web.json_response(response_payload, status=response.status_code)
    except httpx.HTTPError as exc:
        return web.json_response(_error_payload("ralph_unavailable", exc), status=502)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_orchestrate_status(request: web.Request) -> web.Response:
    try:
        task_id = str(request.match_info.get("task_id", "")).strip()
        if not task_id:
            return web.json_response({"error": "task_id required"}, status=400)
        include_result = str(request.rel_url.query.get("include_result", "false")).strip().lower() in {"1", "true", "yes", "on"}
        upstream_path = "/result" if include_result else ""
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{_ralph_wiggum_url.rstrip('/')}/tasks/{task_id}{upstream_path}",
                headers=_ralph_request_headers(),
            )
        response_payload = response.json()
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs and isinstance(response_payload, dict):
            response_payload["active_lesson_refs"] = lesson_refs
        return web.json_response(response_payload, status=response.status_code)
    except httpx.HTTPError as exc:
        return web.json_response(_error_payload("ralph_unavailable", exc), status=502)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_session_start(request: web.Request) -> web.Response:
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
            "safety_mode": _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly"))),
            "budget": _default_budget(data),
            "usage": _default_usage(),
            "isolation": {
                "profile": str(data.get("isolation_profile", "")).strip(),
                "workspace_root": str(data.get("workspace_root", "")).strip(),
                "network_policy": str(data.get("network_policy", "")).strip(),
            },
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "trajectory": [{
                "ts": int(time.time()),
                "event_type": "session_start",
                "phase_id": "discover",
                "detail": "workflow session created",
            }],
        }
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            session["active_lesson_refs"] = lesson_refs
        return web.json_response(session)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_session_get(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        include_lineage = request.rel_url.query.get("lineage", "").lower() in {"1", "true", "yes"}
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        payload = dict(session)
        if include_lineage:
            payload["lineage"] = _session_lineage(sessions, session_id)
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_sessions_list(_request: web.Request) -> web.Response:
    try:
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
        items = []
        for sid, sess in sessions.items():
            phase_state = sess.get("phase_state", [])
            current_idx = int(sess.get("current_phase_index", 0))
            current_phase = None
            reasoning_pattern = sess.get("reasoning_pattern", {})
            if 0 <= current_idx < len(phase_state):
                current_phase = phase_state[current_idx].get("id")
            _ensure_session_runtime_fields(sess)
            items.append({
                "session_id": sid,
                "status": sess.get("status", "unknown"),
                "objective": sess.get("objective", ""),
                "current_phase": current_phase,
                "current_phase_index": current_idx,
                "safety_mode": sess.get("safety_mode", "plan-readonly"),
                "budget": sess.get("budget", {}),
                "usage": sess.get("usage", {}),
                "reasoning_pattern": {
                    "selected_pattern": reasoning_pattern.get("selected_pattern", ""),
                    "boost_multiplier": reasoning_pattern.get("boost_multiplier", 1.0),
                },
                "orchestration_runtime": sess.get("orchestration_runtime", {}),
                "created_at": sess.get("created_at"),
                "updated_at": sess.get("updated_at"),
            })
        items.sort(key=lambda item: int(item.get("updated_at") or 0), reverse=True)
        payload = {"sessions": items, "count": len(items)}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_tree(request: web.Request) -> web.Response:
    try:
        include_completed = request.rel_url.query.get("include_completed", "true").lower() in {"1", "true", "yes"}
        include_failed = request.rel_url.query.get("include_failed", "true").lower() in {"1", "true", "yes"}
        include_objective = request.rel_url.query.get("include_objective", "true").lower() in {"1", "true", "yes"}
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
            parent_id = sess.get("fork", {}).get("from_session_id")
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
            node["children_count"] = int(children_count.get(node["session_id"], 0))
        roots = [node["session_id"] for node in nodes if node.get("parent_session_id") is None]
        nodes.sort(key=lambda node: int(node.get("updated_at") or 0), reverse=True)
        payload = {"nodes": nodes, "edges": edges, "roots": roots, "count": len(nodes)}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_session_fork(request: web.Request) -> web.Response:
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
            forked["fork"] = {"from_session_id": session_id, "note": note, "forked_at": now}
            sessions[new_id] = forked
            await _save_workflow_sessions(sessions)
        payload = {"session_id": new_id, "forked_from": session_id, "status": "created"}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_session_advance(request: web.Request) -> web.Response:
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
            _ensure_session_runtime_fields(session)

            idx = int(session.get("current_phase_index", 0))
            phases = session.get("phase_state", [])
            if not phases or idx >= len(phases):
                session["status"] = "completed"
                session["updated_at"] = int(time.time())
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
                payload = dict(session)
                lesson_refs = await _active_lesson_refs(limit=2)
                if lesson_refs:
                    payload["active_lesson_refs"] = lesson_refs
                return web.json_response(payload)

            phase = phases[idx]
            if note:
                phase.setdefault("notes", []).append({"ts": int(time.time()), "text": note})
            phase_id = str(phase.get("id", f"phase-{idx}"))
            if session.get("safety_mode") == "plan-readonly":
                mutating_note = any(x in note.lower() for x in ("write", "apply", "edit", "delete", "execute"))
                if mutating_note and action == "note":
                    return web.json_response(
                        {"error": "plan-readonly mode blocks mutating action notes; switch to execute-mutating", "safety_mode": "plan-readonly"},
                        status=403,
                    )

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

            session["trajectory"].append({
                "ts": int(time.time()),
                "event_type": "phase_advance",
                "phase_id": phase_id,
                "action": action,
                "note": note,
            })

            budget_error = _budget_exceeded(session)
            if budget_error:
                session["status"] = "failed"
                session["trajectory"].append({"ts": int(time.time()), "event_type": "budget_violation", "detail": budget_error})

            session["phase_state"] = phases
            session["updated_at"] = int(time.time())
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
        payload = dict(session)
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_start(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        query = (data.get("query") or data.get("prompt") or "").strip()
        if not query:
            return web.json_response({"error": "query required"}, status=400)
        blueprints_data = _load_and_validate_workflow_blueprints()
        blueprint_id = str(data.get("blueprint_id", "") or "").strip()
        selected_blueprint = blueprints_data.get("blueprint_by_id", {}).get(blueprint_id) if blueprint_id else None
        orchestration = _coerce_orchestration_context(data)
        lesson_refs = await _active_lesson_refs(limit=2)
        session = _build_workflow_run_session(
            query=query,
            data=data,
            selected_blueprint=selected_blueprint,
            orchestration=orchestration,
            lesson_refs=lesson_refs,
        )
        session_id = session["session_id"]
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
        return web.json_response(session)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_get(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        include_replay = request.rel_url.query.get("replay", "false").lower() in {"1", "true", "yes"}
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        payload = dict(session)
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        if not include_replay:
            payload["trajectory_count"] = len(session.get("trajectory", []))
            payload.pop("trajectory", None)
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_consensus(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        data = await request.json()
        selected_candidate_id = str(data.get("selected_candidate_id", "") or "").strip()
        summary = str(data.get("summary", "") or "").strip()[:400]
        decisions = data.get("decisions")
        if not selected_candidate_id:
            return web.json_response({"error": "selected_candidate_id required"}, status=400)
        if not isinstance(decisions, list) or not decisions:
            return web.json_response({"error": "decisions must be a non-empty list"}, status=400)
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            try:
                consensus = _apply_consensus_update(
                    session,
                    selected_candidate_id=selected_candidate_id,
                    decisions=decisions,
                    summary=summary,
                )
            except ValueError as exc:
                return web.json_response({"error": str(exc)}, status=400)
            session["team"] = _build_orchestration_team(
                session.get("orchestration_policy", {}) if isinstance(session.get("orchestration_policy"), dict) else {},
                session.get("orchestration", {}) if isinstance(session.get("orchestration"), dict) else {},
                consensus,
            )
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
            async with _agent_evaluations_lock:
                evaluation_registry = await _load_agent_evaluations_registry()
                evaluation_registry = _record_agent_consensus_event(
                    evaluation_registry,
                    agent=str(consensus.get("selected_agent", "") or "unknown"),
                    lane=str(consensus.get("selected_lane", "") or "unknown"),
                    role=str(consensus.get("selected_role", "") or "unknown"),
                    selected_candidate_id=selected_candidate_id,
                    summary=summary,
                    ts=int(session.get("updated_at") or time.time()),
                )
                await _save_agent_evaluations_registry(evaluation_registry)
        return web.json_response({"status": "ok", "session_id": session_id, "consensus": consensus})
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_arbiter(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        data = await request.json()
        selected_candidate_id = str(data.get("selected_candidate_id", "") or "").strip()
        arbiter = str(data.get("arbiter", "") or "").strip()
        verdict = str(data.get("verdict", "") or "").strip().lower()
        rationale = str(data.get("rationale", "") or "").strip()[:400]
        summary = str(data.get("summary", "") or "").strip()[:400]
        supporting_decisions = data.get("supporting_decisions")
        if not selected_candidate_id:
            return web.json_response({"error": "selected_candidate_id required"}, status=400)
        if not arbiter:
            return web.json_response({"error": "arbiter required"}, status=400)
        if verdict not in {"accept", "reject", "prefer"}:
            return web.json_response({"error": "verdict must be one of: accept, reject, prefer"}, status=400)
        if not rationale:
            return web.json_response({"error": "rationale required"}, status=400)
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            try:
                consensus = _apply_arbiter_update(
                    session,
                    selected_candidate_id=selected_candidate_id,
                    arbiter=arbiter,
                    verdict=verdict,
                    rationale=rationale,
                    summary=summary,
                    supporting_decisions=supporting_decisions if isinstance(supporting_decisions, list) else [],
                )
            except ValueError as exc:
                return web.json_response({"error": str(exc)}, status=400)
            session["team"] = _build_orchestration_team(
                session.get("orchestration_policy", {}) if isinstance(session.get("orchestration_policy"), dict) else {},
                session.get("orchestration", {}) if isinstance(session.get("orchestration"), dict) else {},
                consensus,
            )
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
            if verdict in {"accept", "prefer"}:
                async with _agent_evaluations_lock:
                    evaluation_registry = await _load_agent_evaluations_registry()
                    evaluation_registry = _record_agent_consensus_event(
                        evaluation_registry,
                        agent=str(consensus.get("selected_agent", "") or "unknown"),
                        lane=str(consensus.get("selected_lane", "") or "unknown"),
                        role=str(consensus.get("selected_role", "") or "unknown"),
                        selected_candidate_id=selected_candidate_id,
                        summary=summary or rationale,
                        ts=int(session.get("updated_at") or time.time()),
                    )
                    await _save_agent_evaluations_registry(evaluation_registry)
        return web.json_response({"status": "ok", "session_id": session_id, "consensus": consensus})
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_team(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        return web.json_response({
            "session_id": session_id,
            "team": session.get("team", {}),
            "consensus_mode": ((session.get("consensus") or {}) if isinstance(session.get("consensus"), dict) else {}).get("consensus_mode", ""),
        })
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_team_detailed(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        consensus = session.get("consensus", {})
        team = session.get("team", {})
        phase_state = session.get("phase_state", [])
        current_idx = int(session.get("current_phase_index", 0))
        current_phase = None
        if 0 <= current_idx < len(phase_state):
            current_phase = phase_state[current_idx].get("id")
        team_details = {
            "session_id": session_id,
            "objective": session.get("objective", ""),
            "status": session.get("status", "unknown"),
            "current_phase": current_phase,
            "current_phase_index": current_idx,
            "safety_mode": session.get("safety_mode", "plan-readonly"),
            "budget": session.get("budget", {}),
            "usage": session.get("usage", {}),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "reasoning_pattern": session.get("reasoning_pattern", {}),
            "consensus_mode": consensus.get("consensus_mode", ""),
            "selection_strategy": team.get("selection_strategy", ""),
            "team_members": team.get("members", []),
            "active_slots": team.get("active_slots", []),
            "required_slots": team.get("required_slots", []),
            "optional_slot_capacity": team.get("optional_slot_capacity", 0),
            "deferred_slots": team.get("deferred_slots", []),
            "deferred_members": team.get("deferred_members", []),
            "orchestration_runtime": session.get("orchestration_runtime", {}),
            "candidates": consensus.get("candidates", []),
            "selected_candidate_id": consensus.get("selected_candidate_id", ""),
            "formation_mode": team.get("formation_mode", ""),
        }
        return web.json_response(team_details)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_arbiter_history(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        limit = max(1, min(50, int(request.rel_url.query.get("limit", "10"))))
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        consensus = session.get("consensus", {})
        arbiter_state = consensus.get("arbiter", {})
        if consensus.get("consensus_mode") != "arbiter-review":
            return web.json_response({"session_id": session_id, "arbiter_active": False, "history": [], "message": "arbiter mode not active"})
        history = arbiter_state.get("history", [])[-limit:]
        return web.json_response({
            "session_id": session_id,
            "arbiter_active": True,
            "arbiter": arbiter_state.get("arbiter", ""),
            "current_status": arbiter_state.get("status", ""),
            "history": history,
            "history_count": len(arbiter_state.get("history", [])),
        })
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_mode(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        data = await request.json()
        target_mode = _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly")))
        confirm = bool(data.get("confirm", False))
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            if target_mode == "execute-mutating" and not confirm:
                return web.json_response({"error": "confirm=true required to switch to execute-mutating"}, status=400)
            session["safety_mode"] = target_mode
            session["updated_at"] = int(time.time())
            session["trajectory"].append({
                "ts": int(time.time()),
                "event_type": "mode_change",
                "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
                "detail": f"safety_mode -> {target_mode}",
            })
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
        payload = {"session_id": session_id, "safety_mode": target_mode}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_isolation_get(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        payload = {
            "session_id": session_id,
            "isolation": session.get("isolation", {}),
            "resolved_profile": _resolve_isolation_profile(session),
        }
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_isolation_set(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        data = await request.json()
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            iso = dict(session.get("isolation", {}))
            if "profile" in data:
                iso["profile"] = str(data.get("profile", "")).strip()
            if "workspace_root" in data:
                iso["workspace_root"] = str(data.get("workspace_root", "")).strip()
            if "network_policy" in data:
                iso["network_policy"] = str(data.get("network_policy", "")).strip()
            session["isolation"] = iso
            session["updated_at"] = int(time.time())
            session["trajectory"].append({
                "ts": int(time.time()),
                "event_type": "isolation_update",
                "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
                "detail": f"isolation -> {iso}",
            })
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
        payload = {
            "session_id": session_id,
            "isolation": session.get("isolation", {}),
            "resolved_profile": _resolve_isolation_profile(session),
        }
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_event(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        data = await request.json()
        event_type = str(data.get("event_type", "event")).strip().lower()
        risk_class = str(data.get("risk_class", "safe")).strip().lower()
        approved = bool(data.get("approved", False))
        token_delta = int(data.get("token_delta", 0))
        tool_call_delta = int(data.get("tool_call_delta", 0))
        detail = str(data.get("detail", "")).strip()

        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            mode = str(session.get("safety_mode", "plan-readonly"))
            policy = _load_runtime_safety_policy()
            mode_policy = (policy.get("modes", {}) or {}).get(mode, {})
            allowed = set(mode_policy.get("allowed_risk_classes", ["safe"]))
            requires_approval = set(mode_policy.get("requires_approval", ["review-required"]))
            blocked = set(mode_policy.get("blocked", ["blocked"]))
            if risk_class in blocked:
                return web.json_response({"error": "blocked risk_class cannot be executed"}, status=403)
            if risk_class in requires_approval and not approved:
                return web.json_response({"error": "review-required event must include approved=true"}, status=403)
            if risk_class not in allowed and risk_class not in requires_approval:
                return web.json_response({"error": "risk_class not allowed by runtime safety policy", "risk_class": risk_class, "safety_mode": mode}, status=403)

            isolation_error = _check_isolation_constraints(session, data)
            if isolation_error:
                return web.json_response({
                    "error": isolation_error,
                    "isolation": session.get("isolation", {}),
                    "resolved_profile": _resolve_isolation_profile(session),
                }, status=403)

            usage = session.get("usage", {})
            usage["tokens_used"] = int(usage.get("tokens_used", 0)) + max(0, token_delta)
            usage["tool_calls_used"] = int(usage.get("tool_calls_used", 0)) + max(0, tool_call_delta)
            session["usage"] = usage
            budget_error = _budget_exceeded(session)
            if budget_error:
                return web.json_response({"error": budget_error, "usage": usage, "budget": session.get("budget", {})}, status=429)

            current_idx = int(session.get("current_phase_index", 0))
            phase_id = f"phase-{current_idx}"
            phases = session.get("phase_state", [])
            if 0 <= current_idx < len(phases):
                phase_id = str(phases[current_idx].get("id", phase_id))

            event_ts = int(time.time())
            session["trajectory"].append({
                "ts": event_ts,
                "event_type": event_type,
                "phase_id": phase_id,
                "risk_class": risk_class,
                "approved": approved,
                "token_delta": token_delta,
                "tool_call_delta": tool_call_delta,
                "detail": detail,
            })
            session["updated_at"] = event_ts
            sessions[session_id] = session
            await _save_workflow_sessions(sessions)
            consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
            runtime_agent = str(consensus.get("selected_agent", "") or "").strip()
            runtime_profile = str(consensus.get("selected_lane", "") or "").strip()
            runtime_role = str(consensus.get("selected_role", "") or "").strip()
            if runtime_agent and runtime_profile:
                async with _agent_evaluations_lock:
                    evaluation_registry = await _load_agent_evaluations_registry()
                    evaluation_registry = _record_agent_runtime_event(
                        evaluation_registry,
                        agent=runtime_agent,
                        profile=runtime_profile,
                        role=runtime_role,
                        event_type=event_type,
                        risk_class=risk_class,
                        approved=approved,
                        token_delta=token_delta,
                        tool_call_delta=tool_call_delta,
                        detail=detail,
                        ts=event_ts,
                    )
                    await _save_agent_evaluations_registry(evaluation_registry)
        payload = {
            "session_id": session_id,
            "usage": session.get("usage", {}),
            "budget": session.get("budget", {}),
            "trajectory_count": len(session.get("trajectory", [])),
        }
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_run_replay(request: web.Request) -> web.Response:
    try:
        session_id = request.match_info.get("session_id", "")
        phase = str(request.rel_url.query.get("phase", "")).strip()
        event_type = str(request.rel_url.query.get("event_type", "")).strip().lower()
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        events = list(session.get("trajectory", []))
        if phase:
            events = [event for event in events if str(event.get("phase_id", "")) == phase]
        if event_type:
            events = [event for event in events if str(event.get("event_type", "")).lower() == event_type]
        payload = {
            "session_id": session_id,
            "count": len(events),
            "events": events,
            "usage": session.get("usage", {}),
            "budget": session.get("budget", {}),
        }
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


async def handle_workflow_blueprints(_request: web.Request) -> web.Response:
    try:
        parsed = _load_and_validate_workflow_blueprints()
        items = parsed.get("blueprints", [])
        errors = parsed.get("errors", [])
        payload = {"blueprints": items, "count": len(items), "source": parsed.get("source", ""), "valid": len(errors) == 0, "errors": errors}
        lesson_refs = await _active_lesson_refs(limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)
    except Exception as exc:
        return _internal_error(exc)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/workflow/plan", handle_workflow_plan)
    http_app.router.add_get("/workflow/plan", handle_workflow_plan)
    http_app.router.add_post("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_get("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_post("/workflow/orchestrate", handle_workflow_orchestrate)
    http_app.router.add_get("/workflow/orchestrate/{task_id}", handle_workflow_orchestrate_status)
    http_app.router.add_post("/workflow/session/start", handle_workflow_session_start)
    http_app.router.add_get("/workflow/sessions", handle_workflow_sessions_list)
    http_app.router.add_get("/workflow/tree", handle_workflow_tree)
    http_app.router.add_get("/workflow/session/{session_id}", handle_workflow_session_get)
    http_app.router.add_post("/workflow/session/{session_id}/fork", handle_workflow_session_fork)
    http_app.router.add_post("/workflow/session/{session_id}/advance", handle_workflow_session_advance)
    http_app.router.add_post("/workflow/run/start", handle_workflow_run_start)
    http_app.router.add_get("/workflow/run/{session_id}", handle_workflow_run_get)
    http_app.router.add_get("/workflow/run/{session_id}/team", handle_workflow_run_team)
    http_app.router.add_get("/workflow/run/{session_id}/team/detailed", handle_workflow_run_team_detailed)
    http_app.router.add_get("/workflow/run/{session_id}/arbiter/history", handle_workflow_run_arbiter_history)
    http_app.router.add_post("/workflow/run/{session_id}/consensus", handle_workflow_run_consensus)
    http_app.router.add_post("/workflow/run/{session_id}/arbiter", handle_workflow_run_arbiter)
    http_app.router.add_post("/workflow/run/{session_id}/mode", handle_workflow_run_mode)
    http_app.router.add_get("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_get)
    http_app.router.add_post("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_set)
    http_app.router.add_post("/workflow/run/{session_id}/event", handle_workflow_run_event)
    http_app.router.add_get("/workflow/run/{session_id}/replay", handle_workflow_run_replay)
    http_app.router.add_get("/workflow/blueprints", handle_workflow_blueprints)
