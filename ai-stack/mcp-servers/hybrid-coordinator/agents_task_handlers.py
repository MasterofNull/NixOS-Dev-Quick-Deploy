"""
Agent subprocess management, task manager, and review handoff HTTP handlers.

Covers:
  - GET/POST /control/agents              — agent spawn/status/team/kill/roles
  - POST     /control/task-manager/*     — polling-based task queue (IndyDevDan pattern)
  - POST/GET /control/review/*            — agent-to-agent review handoff

Extracted from http_server.py (Phase 12.4 decomposition).
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from aiohttp import web

from config import Config

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state (promoted from run_http_mode() closures)
# ---------------------------------------------------------------------------

_AGENT_STATE: Dict[str, Any] = {}       # agent_id -> instance dict
_TASK_QUEUE: List[Dict[str, Any]] = []  # In-memory task queue
_REVIEW_QUEUE: Dict[str, Dict[str, Any]] = {}  # session_id -> review state

# Embedded subprocess agent script — runs via sys.executable -c
_LOCAL_AGENT_CODE = '''
import asyncio, json, os, sys, time, httpx, pathlib
AGENT_ID = os.environ["AGENT_ID"]
AGENT_ROLE = os.environ["AGENT_ROLE"]
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
AGENT_TASK = os.environ["AGENT_TASK"]
SWITCHBOARD_URL = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085")
STATE_FILE = os.environ.get("AGENT_STATE_FILE", "")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "4096"))
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))

def _profile_for_role(role):
    normalized = str(role or "").strip().lower()
    if normalized == "coder":
        return "local-tool-calling"
    return "continue-local"

def _write_state(state):
    if STATE_FILE:
        p = pathlib.Path(STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))

async def run():
    state = {"id": AGENT_ID, "role": AGENT_ROLE, "status": "running",
             "started_at": time.time(), "tool_calls": 0}
    _write_state(state)
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": AGENT_TASK},
        ]
        async with httpx.AsyncClient(timeout=float(os.environ.get("AGENT_TIMEOUT", "120"))) as client:
            resp = await client.post(
                f"{SWITCHBOARD_URL}/v1/chat/completions",
                json={"messages": messages, "temperature": TEMPERATURE,
                      "max_tokens": MAX_TOKENS, "stream": False},
                headers={"X-AI-Profile": _profile_for_role(AGENT_ROLE),
                         "X-AI-Route": "local"},
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            state.update({"status": "completed", "result": content,
                          "completed_at": time.time()})
            _write_state(state)
            print(json.dumps({"ok": True, "content": content, "agent_id": AGENT_ID}))
    except Exception as e:
        state.update({"status": "failed", "error": str(e), "completed_at": time.time()})
        _write_state(state)
        print(json.dumps({"ok": False, "error": str(e), "agent_id": AGENT_ID}), file=sys.stderr)
        sys.exit(1)
asyncio.run(run())
'''


# ---------------------------------------------------------------------------
# Agent subprocess helper
# ---------------------------------------------------------------------------

async def _spawn_local_agent_instance(
    *,
    role: str,
    task_text: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout_sec: float,
    team_id: Optional[str] = None,
) -> tuple:
    agent_id = str(uuid4())[:8]
    state_file = f"/tmp/agent-spawner/agent-{agent_id}.json"
    Path("/tmp/agent-spawner").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "AGENT_ID": agent_id,
        "AGENT_ROLE": role,
        "AGENT_TASK": task_text,
        "AGENT_SYSTEM_PROMPT": system_prompt,
        "AGENT_STATE_FILE": state_file,
        "AGENT_MAX_TOKENS": str(max_tokens),
        "AGENT_TEMPERATURE": str(temperature),
        "AGENT_TIMEOUT": str(timeout_sec),
        "SWITCHBOARD_URL": Config.SWITCHBOARD_URL,
        "PYTHONUNBUFFERED": "1",
    })

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", _LOCAL_AGENT_CODE,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    instance: Dict[str, Any] = {
        "id": agent_id,
        "role": role,
        "task": task_text,
        "status": "running",
        "pid": proc.pid,
        "started_at": datetime.now().isoformat(),
        "state_file": state_file,
    }
    if team_id:
        instance["team_id"] = team_id
    _AGENT_STATE[agent_id] = instance

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        instance["status"] = "timeout"
        instance["completed_at"] = datetime.now().isoformat()
        return instance, 504

    if proc.returncode != 0:
        instance["status"] = "failed"
        instance["error"] = stderr.decode(errors="replace")[:500] if stderr else "unknown"
        instance["completed_at"] = datetime.now().isoformat()
        return instance, 500

    try:
        result = json.loads(stdout.decode())
        if result.get("ok"):
            instance["status"] = "completed"
            instance["result"] = result.get("content", "")
        else:
            instance["status"] = "failed"
            instance["error"] = result.get("error", "unknown")
    except (json.JSONDecodeError, UnicodeDecodeError):
        instance["status"] = "completed"
        instance["result"] = stdout.decode(errors="replace")[:2000]

    instance["completed_at"] = datetime.now().isoformat()
    return instance, 201


# ---------------------------------------------------------------------------
# Agent management handlers
# ---------------------------------------------------------------------------

async def handle_agents_status(request: web.Request) -> web.Response:
    """GET /control/agents — list all agent instances"""
    instance_id = request.query.get("id")
    if instance_id:
        inst = _AGENT_STATE.get(instance_id)
        if not inst:
            return web.json_response({"error": f"Instance {instance_id} not found"})
        return web.json_response(inst)
    return web.json_response({
        "active_agents": sum(1 for v in _AGENT_STATE.values() if v.get("status") in ("pending", "running")),
        "total_agents": len(_AGENT_STATE),
        "instances": list(_AGENT_STATE.values()),
    })


async def handle_agents_spawn(request: web.Request) -> web.Response:
    """POST /control/agents/spawn — spawn a single agent subprocess"""
    data = await request.json()
    role = data.get("role", "coordinator")
    task_text = data.get("task", "")
    if not task_text:
        return web.json_response({"error": "task required"}, status=400)
    instance, status_code = await _spawn_local_agent_instance(
        role=role,
        task_text=task_text,
        system_prompt=data.get("system_prompt", f"You are a {role} agent. Complete the assigned task."),
        max_tokens=int(data.get("max_tokens", 2048)),
        temperature=float(data.get("temperature", 0.3)),
        timeout_sec=float(data.get("timeout", 120)),
    )
    return web.json_response({"status": "ok", "instance": instance}, status=status_code)


async def handle_agents_team(request: web.Request) -> web.Response:
    """POST /control/agents/team — spawn a coordinated team of agents"""
    data = await request.json()
    agents_spec = data.get("agents", [])
    if not agents_spec:
        return web.json_response({"error": "agents list required"}, status=400)
    team_id = data.get("team_id") or f"team-{uuid4().hex[:8]}"
    results = []
    for spec in agents_spec:
        role = spec.get("role", "agent")
        task_text = spec.get("task", "")
        if not task_text:
            results.append({"role": role, "error": "task required", "status": "skipped"})
            continue
        instance, _status = await _spawn_local_agent_instance(
            role=role,
            task_text=task_text,
            system_prompt=spec.get("system_prompt", f"You are a {role} agent. Complete the assigned task."),
            max_tokens=int(spec.get("max_tokens", 2048)),
            temperature=float(spec.get("temperature", 0.3)),
            timeout_sec=float(spec.get("timeout", 120)),
            team_id=team_id,
        )
        results.append(instance)
    return web.json_response({
        "status": "ok",
        "team_id": team_id,
        "agents": results,
        "count": len(results),
    })


async def handle_agents_kill(request: web.Request) -> web.Response:
    """POST /control/agents/kill — kill a running agent"""
    data = await request.json()
    agent_id = data.get("id", "")
    instance = _AGENT_STATE.get(agent_id)
    if not instance:
        return web.json_response({"error": f"Agent {agent_id} not found"}, status=404)
    pid = instance.get("pid")
    if pid:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            instance["status"] = "killed"
            instance["completed_at"] = datetime.now().isoformat()
        except ProcessLookupError:
            instance["status"] = "already_gone"
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
    return web.json_response({"status": "ok", "agent_id": agent_id, "instance": instance})


async def handle_agents_roles(request: web.Request) -> web.Response:
    """GET /control/agents/roles — list available agent roles"""
    return web.json_response({
        "roles": [
            {"role": "coordinator", "description": "Orchestrates other agents and tasks"},
            {"role": "coder", "description": "Writes and modifies code (uses tool-calling profile)"},
            {"role": "reviewer", "description": "Reviews artifacts and provides structured feedback"},
            {"role": "researcher", "description": "Gathers context and information"},
            {"role": "agent", "description": "General-purpose agent"},
        ]
    })


# ---------------------------------------------------------------------------
# Task manager handlers (IndyDevDan polling-based pattern)
# ---------------------------------------------------------------------------

async def handle_task_manager_poll(request: web.Request) -> web.Response:
    """POST /control/task-manager/poll — poll for tasks to work on."""
    try:
        data = await request.json()
        source = data.get("source", "local")
        status_filter = data.get("status_filter", "todo")
        max_tasks = int(data.get("max_tasks", 5))
        agent = data.get("agent", "codex")

        available_tasks = [
            t for t in _TASK_QUEUE
            if t.get("status") == status_filter
            and (source == "local" or t.get("source") == source)
        ][:max_tasks]

        for task in available_tasks:
            task["status"] = "in_progress"
            task["assigned_to"] = agent
            task["assigned_at"] = time.time()

        return web.json_response({
            "status": "ok",
            "source": source,
            "tasks": available_tasks,
            "count": len(available_tasks),
            "remaining": len([t for t in _TASK_QUEUE if t.get("status") == "todo"]),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_task_manager_complete(request: web.Request) -> web.Response:
    """POST /control/task-manager/complete — mark a task as completed."""
    try:
        data = await request.json()
        task_id = data.get("task_id", "")
        result = data.get("result", "completed")
        evidence = data.get("evidence", "")

        task = next((t for t in _TASK_QUEUE if t.get("id") == task_id), None)
        if not task:
            return web.json_response({"error": f"Task {task_id} not found"}, status=404)

        task["status"] = result
        task["completed_at"] = time.time()
        task["evidence"] = evidence

        return web.json_response({
            "status": "ok",
            "task_id": task_id,
            "result": result,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_task_manager_create(request: web.Request) -> web.Response:
    """POST /control/task-manager/create — create a new task."""
    try:
        data = await request.json()
        title = data.get("title", "")
        if not title:
            return web.json_response({"error": "title required"}, status=400)

        task_id = f"task-{uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "title": title,
            "description": data.get("description", ""),
            "source": data.get("source", "local"),
            "priority": data.get("priority", "normal"),
            "assignee": data.get("assignee", ""),
            "status": "todo",
            "created_at": time.time(),
        }
        _TASK_QUEUE.append(task)

        return web.json_response({
            "status": "ok",
            "task": task,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Review handoff helpers and handlers (IndyDevDan pattern)
# ---------------------------------------------------------------------------

def _load_review_artifact_preview(
    artifact_path: str,
    inline_content: str,
    max_chars: int = 6000,
) -> Dict[str, Any]:
    preview = str(inline_content or "").strip()
    source = "inline"
    resolved_path = str(artifact_path or "").strip()
    if not preview and resolved_path:
        candidate = Path(resolved_path)
        candidate_paths = [candidate]
        if not candidate.is_absolute():
            candidate_paths.append(Path(__file__).resolve().parents[3] / candidate)
        existing_candidate = next((item for item in candidate_paths if item.exists() and item.is_file()), None)
        if existing_candidate:
            try:
                preview = existing_candidate.read_text(encoding="utf-8", errors="replace")[:max_chars]
                source = "file"
                resolved_path = str(existing_candidate)
            except Exception as exc:
                preview = f"[artifact preview unavailable: {exc}]"
                source = "error"
    elif preview:
        preview = preview[:max_chars]
    return {
        "artifact_path": resolved_path,
        "preview": preview,
        "preview_source": source,
        "preview_truncated": len(preview) >= max_chars if preview else False,
    }


def _parse_review_agent_result(result_text: str) -> Dict[str, Any]:
    raw = str(result_text or "").strip()
    parsed: Dict[str, Any] = {}
    if not raw:
        return {
            "decision": "needs_manual_review",
            "reason": "reviewer returned empty output",
            "evidence": "",
            "feedback": "",
            "suggested_fixes": [],
            "raw_result": raw,
        }
    try:
        candidate = json.loads(raw)
        if isinstance(candidate, dict):
            parsed = candidate
    except json.JSONDecodeError:
        parsed = {}

    decision = str(parsed.get("decision", "") or "").strip().lower()
    if decision not in {"accept", "accepted", "approve", "approved", "reject", "rejected"}:
        lowered = raw.lower()
        if any(token in lowered for token in ("\"decision\":\"accept", "\"decision\": \"accept", "approved", "accept")):
            decision = "accept"
        elif any(token in lowered for token in ("\"decision\":\"reject", "\"decision\": \"reject", "rejected", "reject")):
            decision = "reject"
        else:
            decision = "needs_manual_review"

    return {
        "decision": "accept" if decision.startswith("accept") or decision.startswith("approv") else (
            "reject" if decision.startswith("reject") else "needs_manual_review"
        ),
        "reason": str(parsed.get("reason", "") or "").strip(),
        "evidence": str(parsed.get("evidence", "") or "").strip(),
        "feedback": str(parsed.get("feedback", "") or "").strip(),
        "suggested_fixes": (
            [str(item).strip() for item in parsed.get("suggested_fixes", []) if str(item).strip()]
            if isinstance(parsed.get("suggested_fixes"), list) else []
        ),
        "raw_result": raw[:4000],
    }


async def handle_review_agent_handoff(request: web.Request) -> web.Response:
    """POST /control/review/agent-handoff — hand off work for review."""
    try:
        data = await request.json()
        from_agent = data.get("from_agent", "codex")
        to_agent = data.get("to_agent", "qwen")
        session_id = data.get("session_id") or f"review-{uuid4().hex[:8]}"
        artifact_type = data.get("artifact_type", "code")
        artifact_path = data.get("artifact_path", "")
        review_criteria = data.get("review_criteria", ["correctness", "style"])
        auto_merge = data.get("auto_merge", False)
        timeout_sec = float(data.get("timeout", 45))
        artifact_preview = _load_review_artifact_preview(
            str(artifact_path or ""),
            str(data.get("artifact_content") or data.get("artifact_excerpt") or ""),
        )

        review: Dict[str, Any] = {
            "session_id": session_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "artifact_type": artifact_type,
            "artifact_path": artifact_path,
            "artifact_preview_source": artifact_preview["preview_source"],
            "review_criteria": review_criteria,
            "auto_merge": auto_merge,
            "status": "running_review",
            "created_at": time.time(),
            "history": [
                {
                    "event": "handoff_initiated",
                    "from": from_agent,
                    "to": to_agent,
                    "timestamp": time.time(),
                }
            ],
        }
        _REVIEW_QUEUE[session_id] = review

        reviewer_prompt = (
            "Review the supplied artifact and return strict JSON only.\n"
            "Schema:\n"
            "{\"decision\":\"accept|reject\",\"reason\":\"...\",\"evidence\":\"...\","
            "\"feedback\":\"...\",\"suggested_fixes\":[\"...\"]}\n"
            "Use decision=accept only when the artifact meets the stated criteria."
        )
        review_task = (
            f"Review handoff session: {session_id}\n"
            f"From agent: {from_agent}\n"
            f"Reviewer agent role requested: {to_agent}\n"
            f"Artifact type: {artifact_type}\n"
            f"Artifact path: {artifact_preview['artifact_path'] or '[none provided]'}\n"
            f"Review criteria: {', '.join(str(item) for item in review_criteria)}\n"
            "Artifact preview:\n"
            f"{artifact_preview['preview'] or '[no artifact preview available]'}"
        )
        reviewer_instance, reviewer_status = await _spawn_local_agent_instance(
            role="reviewer",
            task_text=review_task,
            system_prompt=reviewer_prompt,
            max_tokens=int(data.get("max_tokens", 400)),
            temperature=float(data.get("temperature", 0.1)),
            timeout_sec=timeout_sec,
        )
        review["review_agent_instance_id"] = reviewer_instance.get("id")
        review["review_agent_status"] = reviewer_instance.get("status")
        review["review_agent_result"] = reviewer_instance.get("result", "")

        if reviewer_status == 201 and reviewer_instance.get("status") == "completed":
            parsed_result = _parse_review_agent_result(str(reviewer_instance.get("result", "")))
            review["review_result"] = parsed_result
            if parsed_result["decision"] == "accept":
                review["status"] = "accepted"
                review["accepted_at"] = time.time()
                review["accepted_by"] = to_agent
                review["acceptance_reason"] = parsed_result["reason"] or "accepted by delegated reviewer"
                review["acceptance_evidence"] = parsed_result["evidence"]
                review["history"].append({
                    "event": "review_accepted",
                    "by": to_agent,
                    "reason": review["acceptance_reason"],
                    "timestamp": time.time(),
                })
            elif parsed_result["decision"] == "reject":
                review["status"] = "rejected"
                review["rejected_at"] = time.time()
                review["rejected_by"] = to_agent
                review["rejection_reason"] = parsed_result["reason"] or "rejected by delegated reviewer"
                review["feedback"] = parsed_result["feedback"]
                review["suggested_fixes"] = parsed_result["suggested_fixes"]
                review["history"].append({
                    "event": "review_rejected",
                    "by": to_agent,
                    "reason": review["rejection_reason"],
                    "timestamp": time.time(),
                })
            else:
                review["status"] = "pending_review"
                review["history"].append({
                    "event": "review_needs_manual_followup",
                    "by": to_agent,
                    "reason": parsed_result["reason"] or "delegated reviewer returned inconclusive output",
                    "timestamp": time.time(),
                })
        else:
            review["status"] = "pending_review"
            review["history"].append({
                "event": "review_agent_unavailable",
                "by": to_agent,
                "reason": f"delegated reviewer finished with status={reviewer_instance.get('status', 'unknown')}",
                "timestamp": time.time(),
            })

        return web.json_response({
            "status": "ok",
            "session_id": session_id,
            "review": review,
            "next_action": (
                "merge" if review.get("status") == "accepted" and review.get("auto_merge")
                else "manual merge required" if review.get("status") == "accepted"
                else f"Agent {from_agent} should address feedback and resubmit" if review.get("status") == "rejected"
                else f"Agent {to_agent} should review and call /control/review/accept or /control/review/reject"
            ),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_review_status(request: web.Request) -> web.Response:
    """GET /control/review/status — check review status."""
    try:
        session_id = request.query.get("session_id", "")
        if session_id:
            review = _REVIEW_QUEUE.get(session_id)
            if not review:
                return web.json_response({"error": f"Review {session_id} not found"}, status=404)
            return web.json_response(review)

        return web.json_response({
            "pending_reviews": len([r for r in _REVIEW_QUEUE.values() if r.get("status") == "pending_review"]),
            "total_reviews": len(_REVIEW_QUEUE),
            "reviews": list(_REVIEW_QUEUE.values()),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_review_accept(request: web.Request) -> web.Response:
    """POST /control/review/accept — accept and approve a review."""
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        review = _REVIEW_QUEUE.get(session_id)
        if not review:
            return web.json_response({"error": f"Review {session_id} not found"}, status=404)

        reviewer_agent = data.get("reviewer_agent", "codex")
        reason = data.get("reason", "approved")
        evidence = data.get("evidence", "")

        review["status"] = "accepted"
        review["accepted_at"] = time.time()
        review["accepted_by"] = reviewer_agent
        review["acceptance_reason"] = reason
        review["acceptance_evidence"] = evidence
        review["history"].append({
            "event": "review_accepted",
            "by": reviewer_agent,
            "reason": reason,
            "timestamp": time.time(),
        })

        return web.json_response({
            "status": "ok",
            "session_id": session_id,
            "accepted": True,
            "auto_merge": review.get("auto_merge", False),
            "next_action": "merge" if review.get("auto_merge") else "manual merge required",
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_review_reject(request: web.Request) -> web.Response:
    """POST /control/review/reject — reject a review with feedback."""
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        review = _REVIEW_QUEUE.get(session_id)
        if not review:
            return web.json_response({"error": f"Review {session_id} not found"}, status=404)

        reviewer_agent = data.get("reviewer_agent", "codex")
        reason = data.get("reason", "")
        feedback = data.get("feedback", "")
        suggested_fixes = data.get("suggested_fixes", [])

        review["status"] = "rejected"
        review["rejected_at"] = time.time()
        review["rejected_by"] = reviewer_agent
        review["rejection_reason"] = reason
        review["feedback"] = feedback
        review["suggested_fixes"] = suggested_fixes
        review["history"].append({
            "event": "review_rejected",
            "by": reviewer_agent,
            "reason": reason,
            "timestamp": time.time(),
        })

        return web.json_response({
            "status": "ok",
            "session_id": session_id,
            "rejected": True,
            "feedback": feedback,
            "suggested_fixes": suggested_fixes,
            "next_action": f"Agent {review.get('from_agent')} should address feedback and resubmit",
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/control/agents", handle_agents_status)
    http_app.router.add_get("/control/agents/roles", handle_agents_roles)
    http_app.router.add_post("/control/agents/spawn", handle_agents_spawn)
    http_app.router.add_post("/control/agents/team", handle_agents_team)
    http_app.router.add_post("/control/agents/kill", handle_agents_kill)
    http_app.router.add_post("/control/task-manager/poll", handle_task_manager_poll)
    http_app.router.add_post("/control/task-manager/complete", handle_task_manager_complete)
    http_app.router.add_post("/control/task-manager/create", handle_task_manager_create)
    http_app.router.add_post("/control/review/agent-handoff", handle_review_agent_handoff)
    http_app.router.add_get("/control/review/status", handle_review_status)
    http_app.router.add_post("/control/review/accept", handle_review_accept)
    http_app.router.add_post("/control/review/reject", handle_review_reject)
