"""
Multi-agent orchestration, bottleneck detection, and review acceptance HTTP handlers.

Extracted from http_server.py (Phase 12.4 decomposition).

Covers:
  - /control/orchestration/* — Phase 4.2 multi-agent framework
  - /control/bottleneck/*    — Phase 1.3 live bottleneck detection
  - /review/acceptance       — deterministic reviewer gate (criteria + keyword scoring)
"""

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aiohttp import web


# Phase 12.4 fix: IsolationMode and SessionState were extracted from
# ai-stack/orchestration/ which is not in sys.path at import time (sys.path
# additions in http_server.py happen after this module is imported at line 130).
# Define the minimal enum values inline — same pattern used for all Phase 12.4
# missing-import fixes (see commit d32efbf2).
class IsolationMode(str, Enum):
    TEMP_DIR = "temp_dir"
    GIT_WORKTREE = "worktree"
    OVERLAY = "overlay"
    COPY = "copy"


class SessionState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"

logger = __import__("logging").getLogger("hybrid-coordinator")

_AGENT_HQ: Optional[Any] = None
_DELEGATION_API: Optional[Any] = None
_WORKSPACE_MANAGER: Optional[Any] = None
_MCP_TOOL_INVOKER: Optional[Any] = None
_PERFORMANCE_PROFILER: Optional[Any] = None
_orchestration_persistence_dir: Optional[Path] = None
_workspace_base_dir: Optional[Path] = None
_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None
_run_harness_eval: Optional[Callable] = None


def init(
    *,
    agent_hq: Any,
    delegation_api: Any,
    workspace_manager: Any,
    mcp_tool_invoker: Any,
    performance_profiler: Any,
    orchestration_persistence_dir: Path,
    workspace_base_dir: Path,
    error_payload_fn: Callable[[str, Exception], Dict[str, Any]],
    run_harness_eval_fn: Optional[Callable] = None,
) -> None:
    global _AGENT_HQ, _DELEGATION_API, _WORKSPACE_MANAGER, _MCP_TOOL_INVOKER
    global _PERFORMANCE_PROFILER, _orchestration_persistence_dir, _workspace_base_dir
    global _error_payload, _run_harness_eval
    _AGENT_HQ = agent_hq
    _DELEGATION_API = delegation_api
    _WORKSPACE_MANAGER = workspace_manager
    _MCP_TOOL_INVOKER = mcp_tool_invoker
    _PERFORMANCE_PROFILER = performance_profiler
    _orchestration_persistence_dir = orchestration_persistence_dir
    _workspace_base_dir = workspace_base_dir
    _error_payload = error_payload_fn
    _run_harness_eval = run_harness_eval_fn


# ---------------------------------------------------------------------------
# Orchestration endpoints
# ---------------------------------------------------------------------------

async def handle_orchestration_status(request: web.Request) -> web.Response:
    """Get orchestration framework status."""
    try:
        return web.json_response({
            "status": "ok",
            "agent_hq": {
                "registered_agents": len(_AGENT_HQ.global_agents),
                "active_sessions": len(_AGENT_HQ.sessions),
                "persistence_dir": str(_orchestration_persistence_dir),
            },
            "delegation": _DELEGATION_API.get_queue_status(),
            "workspaces": {
                "active": len(_WORKSPACE_MANAGER.workspaces),
                "base_dir": str(_workspace_base_dir),
            },
            "tool_invoker": _MCP_TOOL_INVOKER.get_usage_report(),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_agents_list(request: web.Request) -> web.Response:
    """List all registered agents."""
    try:
        agents = [agent.to_dict() for agent in _AGENT_HQ.global_agents.values()]
        return web.json_response({"agents": agents, "count": len(agents)})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_agents_register(request: web.Request) -> web.Response:
    """Register a new agent."""
    try:
        data = await request.json()
        name = str(data.get("name", "")).strip()
        if not name:
            return web.json_response({"error": "name required"}, status=400)
        capabilities = set(data.get("capabilities", []))
        metadata = data.get("metadata", {})
        agent = _AGENT_HQ.register_agent(name, capabilities, metadata)
        _DELEGATION_API.register_agent(
            agent.agent_id,
            name,
            capabilities=capabilities,
            max_concurrent=int(data.get("max_concurrent", 5)),
        )
        return web.json_response({"status": "ok", "agent": agent.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_sessions_list(request: web.Request) -> web.Response:
    """List orchestration sessions."""
    try:
        state_filter = request.query.get("state")
        filter_enum = SessionState(state_filter) if state_filter else None
        sessions = _AGENT_HQ.list_sessions(state_filter=filter_enum)
        return web.json_response({
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_create(request: web.Request) -> web.Response:
    """Create a new orchestration session."""
    try:
        data = await request.json()
        name = str(data.get("name", "")).strip() or f"session-{int(time.time())}"
        context = data.get("context", {})
        session = _AGENT_HQ.create_session(name, context)
        return web.json_response({"status": "ok", "session": session.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_get(request: web.Request) -> web.Response:
    """Get session details."""
    try:
        session_id = request.match_info["session_id"]
        session = _AGENT_HQ.get_session(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        status = _AGENT_HQ.get_session_status(session_id)
        return web.json_response({
            "session": session.to_dict(),
            "status": status,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_start(request: web.Request) -> web.Response:
    """Start or resume a session."""
    try:
        session_id = request.match_info["session_id"]
        success = await _AGENT_HQ.start_session(session_id)
        if not success:
            return web.json_response({"error": "failed to start session"}, status=400)
        return web.json_response({"status": "ok", "session_id": session_id, "state": "running"})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_pause(request: web.Request) -> web.Response:
    """Pause a running session."""
    try:
        session_id = request.match_info["session_id"]
        success = await _AGENT_HQ.pause_session(session_id)
        if not success:
            return web.json_response({"error": "failed to pause session"}, status=400)
        return web.json_response({"status": "ok", "session_id": session_id, "state": "paused"})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_checkpoint(request: web.Request) -> web.Response:
    """Create a checkpoint for a session."""
    try:
        session_id = request.match_info["session_id"]
        data = await request.json()
        name = str(data.get("name", "")).strip() or None
        checkpoint = _AGENT_HQ.create_checkpoint(session_id, name)
        if not checkpoint:
            return web.json_response({"error": "failed to create checkpoint"}, status=400)
        return web.json_response({"status": "ok", "checkpoint": checkpoint.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_session_restore(request: web.Request) -> web.Response:
    """Restore session from a checkpoint."""
    try:
        session_id = request.match_info["session_id"]
        data = await request.json()
        checkpoint_id = str(data.get("checkpoint_id", "")).strip()
        if not checkpoint_id:
            return web.json_response({"error": "checkpoint_id required"}, status=400)
        success = _AGENT_HQ.restore_checkpoint(session_id, checkpoint_id)
        if not success:
            return web.json_response({"error": "failed to restore checkpoint"}, status=400)
        return web.json_response({"status": "ok", "restored": checkpoint_id})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_task_submit(request: web.Request) -> web.Response:
    """Submit a task for delegation."""
    try:
        session_id = request.match_info["session_id"]
        data = await request.json()
        description = str(data.get("description", "")).strip()
        if not description:
            return web.json_response({"error": "description required"}, status=400)
        capabilities = set(data.get("required_capabilities", []))
        priority = int(data.get("priority", 5))
        task = await _AGENT_HQ.submit_task(
            session_id,
            description,
            priority=priority,
            required_capabilities=capabilities or None,
        )
        if not task:
            return web.json_response({"error": "failed to submit task"}, status=400)
        return web.json_response({"status": "ok", "task": task.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_delegate(request: web.Request) -> web.Response:
    """Delegate a task directly via the delegation API."""
    try:
        data = await request.json()
        description = str(data.get("description", "")).strip()
        if not description:
            return web.json_response({"error": "description required"}, status=400)
        capabilities = set(data.get("required_capabilities", []))
        preferred_agent = data.get("preferred_agent")
        priority = int(data.get("priority", 5))
        timeout = float(data.get("timeout_seconds", 300.0))
        wait = bool(data.get("wait", False))
        _delegate_start = time.time()
        result = await _DELEGATION_API.delegate(
            task_description=description,
            required_capabilities=capabilities or None,
            preferred_agent=preferred_agent,
            priority=priority,
            timeout_seconds=timeout,
            wait=wait,
        )
        _delegate_duration_ms = (time.time() - _delegate_start) * 1000
        _PERFORMANCE_PROFILER.record_metric("delegation_api_delegate", _delegate_duration_ms, {"wait": wait, "priority": priority})
        return web.json_response({"status": "ok", "result": result.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_workspace_create(request: web.Request) -> web.Response:
    """Create an isolated workspace."""
    try:
        data = await request.json()
        agent_id = str(data.get("agent_id", "")).strip()
        session_id = str(data.get("session_id", "")).strip()
        if not agent_id or not session_id:
            return web.json_response({"error": "agent_id and session_id required"}, status=400)
        mode_str = str(data.get("mode", "temp_dir")).strip().lower()
        mode = IsolationMode(mode_str) if mode_str in [m.value for m in IsolationMode] else IsolationMode.TEMP_DIR
        source_path = data.get("source_path")
        workspace = await _WORKSPACE_MANAGER.create_workspace(
            agent_id=agent_id,
            session_id=session_id,
            source_path=Path(source_path) if source_path else None,
            mode=mode,
        )
        return web.json_response({"status": "ok", "workspace": workspace.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_workspace_list(request: web.Request) -> web.Response:
    """List workspaces."""
    try:
        session_id = request.query.get("session_id")
        agent_id = request.query.get("agent_id")
        workspaces = _WORKSPACE_MANAGER.list_workspaces(session_id=session_id, agent_id=agent_id)
        return web.json_response({
            "workspaces": [w.to_dict() for w in workspaces],
            "count": len(workspaces),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_workspace_cleanup(request: web.Request) -> web.Response:
    """Clean up a workspace."""
    try:
        workspace_id = request.match_info["workspace_id"]
        force = request.query.get("force", "false").lower() == "true"
        success = await _WORKSPACE_MANAGER.cleanup_workspace(workspace_id, force=force)
        if not success:
            return web.json_response({"error": "failed to cleanup workspace"}, status=400)
        return web.json_response({"status": "ok", "cleaned": workspace_id})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_tool_register(request: web.Request) -> web.Response:
    """Register an MCP tool."""
    try:
        data = await request.json()
        tool_id = str(data.get("tool_id", "")).strip()
        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()
        server_id = str(data.get("server_id", "")).strip()
        if not all([tool_id, name, description, server_id]):
            return web.json_response({"error": "tool_id, name, description, server_id required"}, status=400)
        tool = _MCP_TOOL_INVOKER.register_tool(
            tool_id=tool_id,
            name=name,
            description=description,
            server_id=server_id,
            capabilities=set(data.get("capabilities", [])),
            estimated_cost=float(data.get("estimated_cost", 0.0)),
            requires_approval=bool(data.get("requires_approval", False)),
            rate_limit=data.get("rate_limit"),
        )
        return web.json_response({"status": "ok", "tool": tool.to_dict()})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_tool_invoke(request: web.Request) -> web.Response:
    """Invoke an MCP tool."""
    try:
        data = await request.json()
        tool_id = str(data.get("tool_id", "")).strip()
        if not tool_id:
            return web.json_response({"error": "tool_id required"}, status=400)
        params = data.get("params", {})
        agent_id = str(data.get("agent_id", "system")).strip()
        result = await _MCP_TOOL_INVOKER.invoke(
            tool_id=tool_id,
            params=params,
            agent_id=agent_id,
        )
        return web.json_response({"status": "ok", "result": result})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_orchestration_tool_search(request: web.Request) -> web.Response:
    """Search for tools."""
    try:
        query = request.query.get("q", "")
        capabilities = request.query.get("capabilities", "").split(",") if request.query.get("capabilities") else []
        max_results = int(request.query.get("max_results", 10))
        tools = _MCP_TOOL_INVOKER.search_tools(
            query=query,
            capabilities=set(c.strip() for c in capabilities if c.strip()) or None,
            max_results=max_results,
        )
        return web.json_response({
            "tools": [t.to_dict() for t in tools],
            "count": len(tools),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Bottleneck detection endpoints
# ---------------------------------------------------------------------------

async def handle_bottleneck_status(request: web.Request) -> web.Response:
    """Get current bottleneck detection status and summary."""
    try:
        min_call_count = int(request.query.get("min_calls", 10))
        threshold_ms = float(request.query.get("threshold_ms", 100))
        bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
            min_call_count=min_call_count,
            threshold_ms=threshold_ms,
        )
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for b in bottlenecks:
            severity_counts[b.severity] += 1
        return web.json_response({
            "status": "ok",
            "operations_tracked": len(_PERFORMANCE_PROFILER.metrics),
            "total_metrics": sum(len(m) for m in _PERFORMANCE_PROFILER.metrics.values()),
            "bottleneck_count": len(bottlenecks),
            "severity_breakdown": severity_counts,
            "window_minutes": _PERFORMANCE_PROFILER.window_size.total_seconds() / 60,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_bottleneck_list(request: web.Request) -> web.Response:
    """List all detected bottlenecks with details."""
    try:
        min_call_count = int(request.query.get("min_calls", 10))
        threshold_ms = float(request.query.get("threshold_ms", 100))
        severity_filter = request.query.get("severity")
        bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
            min_call_count=min_call_count,
            threshold_ms=threshold_ms,
        )
        if severity_filter:
            bottlenecks = [b for b in bottlenecks if b.severity == severity_filter]
        return web.json_response({
            "bottlenecks": [
                {
                    "operation": b.operation,
                    "severity": b.severity,
                    "avg_ms": round(b.avg_duration_ms, 2),
                    "p95_ms": round(b.p95_duration_ms, 2),
                    "p99_ms": round(b.p99_duration_ms, 2),
                    "call_count": b.call_count,
                    "total_time_ms": round(b.total_time_ms, 2),
                    "percentage_of_total": round(b.percentage_of_total, 2),
                    "recommendation": b.recommendation,
                }
                for b in bottlenecks
            ],
            "count": len(bottlenecks),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_bottleneck_recommendations(request: web.Request) -> web.Response:
    """Get optimization recommendations for detected bottlenecks."""
    try:
        min_call_count = int(request.query.get("min_calls", 10))
        threshold_ms = float(request.query.get("threshold_ms", 100))
        max_priority = int(request.query.get("max_priority", 5))
        bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
            min_call_count=min_call_count,
            threshold_ms=threshold_ms,
        )
        recommendations = _PERFORMANCE_PROFILER.generate_optimization_recommendations(bottlenecks)
        recommendations = [r for r in recommendations if r.priority <= max_priority]
        return web.json_response({
            "recommendations": [
                {
                    "priority": r.priority,
                    "operation": r.bottleneck.operation,
                    "severity": r.bottleneck.severity,
                    "estimated_improvement_pct": r.estimated_improvement,
                    "implementation_effort": r.implementation_effort,
                    "description": r.description,
                    "action_items": r.action_items,
                }
                for r in recommendations
            ],
            "count": len(recommendations),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_bottleneck_operation_stats(request: web.Request) -> web.Response:
    """Get detailed statistics for a specific operation."""
    try:
        operation = request.query.get("operation")
        if not operation:
            return web.json_response({"error": "operation parameter required"}, status=400)
        stats = _PERFORMANCE_PROFILER.get_statistics(operation)
        return web.json_response(stats)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_bottleneck_report(request: web.Request) -> web.Response:
    """Export a full performance report as JSON."""
    try:
        report_path = _PERFORMANCE_PROFILER.export_report()
        with open(report_path) as f:
            report = json.load(f)
        return web.json_response(report)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_bottleneck_record(request: web.Request) -> web.Response:
    """Record a performance metric (used by internal components)."""
    try:
        data = await request.json()
        operation = data.get("operation")
        duration_ms = data.get("duration_ms")
        metadata = data.get("metadata", {})
        if not operation or duration_ms is None:
            return web.json_response(
                {"error": "operation and duration_ms required"}, status=400
            )
        _PERFORMANCE_PROFILER.record_metric(operation, duration_ms, metadata)
        from metrics import PROFILED_OPERATIONS, PROFILED_OPERATION_DURATION
        PROFILED_OPERATIONS.labels(operation=operation).inc()
        PROFILED_OPERATION_DURATION.labels(operation=operation).observe(duration_ms / 1000)
        return web.json_response({"status": "recorded"})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Review acceptance endpoint
# ---------------------------------------------------------------------------

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


def register_routes(http_app: web.Application) -> None:
    # Orchestration framework
    http_app.router.add_get("/control/orchestration/status", handle_orchestration_status)
    http_app.router.add_get("/control/orchestration/agents", handle_orchestration_agents_list)
    http_app.router.add_post("/control/orchestration/agents/register", handle_orchestration_agents_register)
    http_app.router.add_get("/control/orchestration/sessions", handle_orchestration_sessions_list)
    http_app.router.add_post("/control/orchestration/sessions", handle_orchestration_session_create)
    http_app.router.add_get("/control/orchestration/sessions/{session_id}", handle_orchestration_session_get)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/start", handle_orchestration_session_start)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/pause", handle_orchestration_session_pause)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/checkpoint", handle_orchestration_session_checkpoint)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/restore", handle_orchestration_session_restore)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/tasks", handle_orchestration_task_submit)
    http_app.router.add_post("/control/orchestration/delegate", handle_orchestration_delegate)
    http_app.router.add_get("/control/orchestration/workspaces", handle_orchestration_workspace_list)
    http_app.router.add_post("/control/orchestration/workspaces", handle_orchestration_workspace_create)
    http_app.router.add_delete("/control/orchestration/workspaces/{workspace_id}", handle_orchestration_workspace_cleanup)
    http_app.router.add_post("/control/orchestration/tools/register", handle_orchestration_tool_register)
    http_app.router.add_post("/control/orchestration/tools/invoke", handle_orchestration_tool_invoke)
    http_app.router.add_get("/control/orchestration/tools/search", handle_orchestration_tool_search)
    # Bottleneck detection
    http_app.router.add_get("/control/bottleneck/status", handle_bottleneck_status)
    http_app.router.add_get("/control/bottleneck/list", handle_bottleneck_list)
    http_app.router.add_get("/control/bottleneck/recommendations", handle_bottleneck_recommendations)
    http_app.router.add_get("/control/bottleneck/operation", handle_bottleneck_operation_stats)
    http_app.router.add_get("/control/bottleneck/report", handle_bottleneck_report)
    http_app.router.add_post("/control/bottleneck/record", handle_bottleneck_record)
    # Review acceptance gate
    http_app.router.add_post("/review/acceptance", handle_review_acceptance)
