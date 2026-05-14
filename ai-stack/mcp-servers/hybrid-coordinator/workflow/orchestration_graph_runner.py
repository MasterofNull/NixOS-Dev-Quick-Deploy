"""
Orchestration Graph Runner — Phase 49.

Provides a DAG-style multi-agent staged workflow executor.  Each node in the
graph represents an agent role (lane) with an optional prompt template; edges
are encoded as ``depends_on`` lists.  The runner serialises a topological
execution order, dispatches nodes to the coordinator query API in dependency
order, and tracks progress in a lightweight JSON registry.

HTTP surface (registered via register_routes):
  POST /workflow/graph/run          — submit graph + task → run_id
  GET  /workflow/graph/run/{run_id} — status + per-node results
  GET  /workflow/graph/templates    — list built-in graph templates
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from aiohttp import web

logger = __import__("logging").getLogger("hybrid-coordinator")

# ── Registry ──────────────────────────────────────────────────────────────────

_GRAPH_RUNS_FILE = Path(
    os.getenv("ORCHESTRATION_GRAPH_RUNS_FILE", "data/orchestration-graph-runs.json")
)
_graph_runs_lock = asyncio.Lock()

_GRAPH_TEMPLATES_FILE = Path(
    os.getenv("ORCHESTRATION_GRAPH_TEMPLATES_FILE",
               str(Path(__file__).parent.parent / "config" / "orchestration-graph-templates.json"))
)


def _load_graph_runs() -> Dict[str, Any]:
    if _GRAPH_RUNS_FILE.exists():
        try:
            return json.loads(_GRAPH_RUNS_FILE.read_text())
        except Exception:
            pass
    return {"runs": {}}


def _save_graph_runs(data: Dict[str, Any]) -> None:
    try:
        _GRAPH_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _GRAPH_RUNS_FILE.write_text(json.dumps(data, indent=2))
    except OSError as e:
        logger.warning("graph runner: could not save runs file: %s", e)


def _load_graph_templates() -> Dict[str, Any]:
    if _GRAPH_TEMPLATES_FILE.exists():
        try:
            return json.loads(_GRAPH_TEMPLATES_FILE.read_text())
        except Exception:
            pass
    return {"templates": []}


# ── Graph validation ──────────────────────────────────────────────────────────

def _validate_graph(nodes: List[Dict[str, Any]]) -> Optional[str]:
    """Return error string or None if graph is valid."""
    if not nodes:
        return "graph must have at least one node"
    ids: Set[str] = set()
    for i, node in enumerate(nodes):
        nid = str(node.get("id") or "").strip()
        if not nid:
            return f"node[{i}] missing id"
        if nid in ids:
            return f"duplicate node id: {nid}"
        ids.add(nid)
    for node in nodes:
        for dep in node.get("depends_on", []):
            if str(dep) not in ids:
                return f"node '{node['id']}' depends_on unknown id '{dep}'"
    # Cycle detection via DFS
    adj: Dict[str, List[str]] = {str(n["id"]): [str(d) for d in n.get("depends_on", [])] for n in nodes}
    visited: Set[str] = set()
    in_stack: Set[str] = set()

    def _has_cycle(nid: str) -> bool:
        visited.add(nid)
        in_stack.add(nid)
        for dep in adj.get(nid, []):
            if dep not in visited:
                if _has_cycle(dep):
                    return True
            elif dep in in_stack:
                return True
        in_stack.discard(nid)
        return False

    for nid in adj:
        if nid not in visited:
            if _has_cycle(nid):
                return f"cycle detected in graph (at or involving node '{nid}')"
    return None


def _topological_order(nodes: List[Dict[str, Any]]) -> List[List[str]]:
    """Return nodes grouped by execution wave (parallel-safe batches)."""
    deps: Dict[str, Set[str]] = {str(n["id"]): set(str(d) for d in n.get("depends_on", [])) for n in nodes}
    completed: Set[str] = set()
    waves: List[List[str]] = []
    remaining = set(deps.keys())
    while remaining:
        wave = [nid for nid in remaining if deps[nid].issubset(completed)]
        if not wave:
            # Should not happen after cycle check
            break
        waves.append(sorted(wave))
        completed.update(wave)
        remaining -= set(wave)
    return waves


# ── Graph execution (background task) ────────────────────────────────────────

async def _execute_graph_run(run_id: str, nodes: List[Dict[str, Any]], task: str,
                              coordinator_url: str) -> None:
    """Execute the graph in wave order, updating run registry after each node."""
    waves = _topological_order(nodes)
    node_by_id = {str(n["id"]): n for n in nodes}
    node_outputs: Dict[str, Any] = {}

    async with _graph_runs_lock:
        data = _load_graph_runs()
        run = data["runs"].get(run_id, {})
        run["status"] = "running"
        run["started_at"] = int(time.time())
        data["runs"][run_id] = run
        _save_graph_runs(data)

    all_ok = True
    for wave_idx, wave in enumerate(waves):
        # Execute all nodes in this wave concurrently
        tasks = []
        for nid in wave:
            node = node_by_id[nid]
            tasks.append(_execute_node(run_id, nid, node, task, node_outputs, coordinator_url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for nid, result in zip(wave, results):
            if isinstance(result, Exception):
                logger.error("graph run %s node %s failed: %s", run_id, nid, result)
                all_ok = False
                async with _graph_runs_lock:
                    data = _load_graph_runs()
                    run = data["runs"].get(run_id, {})
                    run["nodes"][nid]["status"] = "failed"
                    run["nodes"][nid]["error"] = str(result)[:300]
                    data["runs"][run_id] = run
                    _save_graph_runs(data)
            else:
                node_outputs[nid] = result

    async with _graph_runs_lock:
        data = _load_graph_runs()
        run = data["runs"].get(run_id, {})
        run["status"] = "completed" if all_ok else "failed"
        run["completed_at"] = int(time.time())
        data["runs"][run_id] = run
        _save_graph_runs(data)


async def _execute_node(run_id: str, nid: str, node: Dict[str, Any], base_task: str,
                         prior_outputs: Dict[str, Any], coordinator_url: str) -> Any:
    """Execute one node: build prompt, POST to coordinator, store result."""
    import httpx

    lane = str(node.get("lane") or node.get("role") or "implementation").strip()
    safety_mode = str(node.get("safety_mode") or "plan-readonly").strip()
    prompt_template = str(node.get("prompt_template") or "{task}").strip()

    # Inject prior outputs into prompt template
    deps_summary = ""
    for dep_id in node.get("depends_on", []):
        out = prior_outputs.get(dep_id, {})
        if isinstance(out, dict):
            snippet = str(out.get("response") or out.get("answer") or "")[:400]
        else:
            snippet = str(out)[:400]
        deps_summary += f"\n[{dep_id} output]: {snippet}"

    prompt = prompt_template.replace("{task}", base_task).replace("{deps}", deps_summary.strip())

    payload = {
        "query": prompt,
        "mode": safety_mode,
        "prefer_local": True,
        "orchestration_lane": lane,
        "metadata": {"graph_run_id": run_id, "graph_node_id": nid},
    }

    async with _graph_runs_lock:
        data = _load_graph_runs()
        run = data["runs"].get(run_id, {})
        run.setdefault("nodes", {})[nid] = {
            "status": "running", "started_at": int(time.time()),
            "lane": lane, "safety_mode": safety_mode,
        }
        data["runs"][run_id] = run
        _save_graph_runs(data)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{coordinator_url}/query", json=payload)
            resp.raise_for_status()
            result = resp.json()
    except Exception as exc:
        raise RuntimeError(f"node {nid} HTTP error: {exc}") from exc

    async with _graph_runs_lock:
        data = _load_graph_runs()
        run = data["runs"].get(run_id, {})
        run.setdefault("nodes", {})[nid].update({
            "status": "completed",
            "completed_at": int(time.time()),
            "response_preview": str(result.get("response") or result.get("answer") or "")[:300],
        })
        data["runs"][run_id] = run
        _save_graph_runs(data)

    return result


# ── HTTP handlers ─────────────────────────────────────────────────────────────

_error_payload = None


def init(*, error_payload_fn) -> None:
    global _error_payload
    _error_payload = error_payload_fn


async def handle_graph_run_submit(request: web.Request) -> web.Response:
    """POST /workflow/graph/run — submit a graph definition + task."""
    try:
        data = await request.json()
        task = str(data.get("task") or data.get("query") or "").strip()
        if not task:
            return web.json_response({"error": "missing required field: task"}, status=400)

        # Support inline nodes or a named template
        nodes = data.get("nodes")
        template_id = str(data.get("template_id") or "").strip()
        if not nodes and template_id:
            templates = _load_graph_templates()
            tmpl_map = {t["id"]: t for t in templates.get("templates", []) if isinstance(t, dict)}
            if template_id not in tmpl_map:
                return web.json_response(
                    {"error": f"template not found: {template_id}",
                     "available": list(tmpl_map.keys())}, status=404
                )
            nodes = tmpl_map[template_id].get("nodes", [])

        if not nodes:
            return web.json_response(
                {"error": "provide either 'nodes' list or 'template_id'"}, status=400
            )

        err = _validate_graph(nodes)
        if err:
            return web.json_response({"error": f"invalid graph: {err}"}, status=400)

        run_id = str(data.get("run_id") or uuid4())
        coordinator_url = os.getenv("WORKFLOW_EXECUTOR_COORDINATOR_URL", "http://127.0.0.1:8003").rstrip("/")
        now = int(time.time())

        run_record = {
            "run_id": run_id,
            "task": task[:500],
            "template_id": template_id or None,
            "node_count": len(nodes),
            "waves": _topological_order(nodes),
            "status": "pending",
            "created_at": now,
            "nodes": {},
        }

        async with _graph_runs_lock:
            runs_data = _load_graph_runs()
            runs_data["runs"][run_id] = run_record
            _save_graph_runs(runs_data)

        # Fire-and-forget graph execution
        asyncio.ensure_future(_execute_graph_run(run_id, nodes, task, coordinator_url))

        return web.json_response({
            "run_id": run_id,
            "status": "pending",
            "node_count": len(nodes),
            "waves": run_record["waves"],
            "task_preview": task[:120],
        }, status=202)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_graph_run_get(request: web.Request) -> web.Response:
    """GET /workflow/graph/run/{run_id} — status + per-node results."""
    try:
        run_id = request.match_info.get("run_id", "")
        async with _graph_runs_lock:
            data = _load_graph_runs()
        run = data["runs"].get(run_id)
        if not run:
            return web.json_response({"error": "run not found"}, status=404)
        return web.json_response(run)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_graph_templates(request: web.Request) -> web.Response:
    """GET /workflow/graph/templates — list built-in orchestration graph templates."""
    try:
        templates = _load_graph_templates()
        tmpl_list = templates.get("templates", [])
        return web.json_response({
            "count": len(tmpl_list),
            "templates": [
                {"id": t.get("id"), "name": t.get("name"), "description": t.get("description"),
                 "node_count": len(t.get("nodes", [])),
                 "categories": [n.get("lane") for n in t.get("nodes", [])]}
                for t in tmpl_list if isinstance(t, dict)
            ],
            "template_file": str(_GRAPH_TEMPLATES_FILE),
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/workflow/graph/run", handle_graph_run_submit)
    http_app.router.add_get("/workflow/graph/run/{run_id}", handle_graph_run_get)
    http_app.router.add_get("/workflow/graph/templates", handle_graph_templates)
