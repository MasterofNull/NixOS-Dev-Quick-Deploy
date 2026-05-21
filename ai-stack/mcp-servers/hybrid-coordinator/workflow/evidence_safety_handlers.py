"""
Evidence, safety, message-bus, capability, and rollback HTTP handlers.

Covers:
  - POST /control/evidence/record
  - GET  /control/evidence/list
  - POST /control/safety/check
  - POST /control/safety/register-hook
  - POST /control/message-bus/publish
  - POST /control/message-bus/subscribe
  - GET  /control/message-bus/poll
  - POST /control/capability/record-outcome
  - GET  /control/capability/score
  - POST /control/rollback/register
  - POST /control/rollback/execute
  - GET  /control/rollback/status

Extracted from http_server.py (Phase 12.4 decomposition).
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]

from aiohttp import web
try:
    from workflow import lifecycle_fsm as _lifecycle_fsm  # Phase 28: use qualified import to share same module instance as intake_gateway
except ImportError:
    _lifecycle_fsm = None  # type: ignore[assignment]

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state (promoted from run_http_mode() closure variables)
# ---------------------------------------------------------------------------

_evidence_store: Dict[str, List[Dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# YAML safety rails (Phase 62.3, AM-C3)
# ---------------------------------------------------------------------------

def _load_safety_rails() -> List[Dict[str, Any]]:
    """Load structured safety rails from config/safety-rails.yaml.

    Returns an empty list if the file is absent, unreadable, or yaml is unavailable.
    The CWD at service start is the repo root, matching the pattern used by
    workflow/runtime_manager.py for other config files.
    """
    if _yaml is None:
        return []
    rails_path = os.environ.get("SAFETY_RAILS_FILE", "config/safety-rails.yaml")
    try:
        with open(rails_path, "r") as fh:
            doc = _yaml.safe_load(fh)
        return doc.get("rails", []) if isinstance(doc, dict) else []
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("safety-rails.yaml load error: %s", exc)
        return []


_safety_rails: List[Dict[str, Any]] = _load_safety_rails()

_safety_hooks: List[Dict[str, Any]] = [
    {"pattern": "rm -rf /", "action": "block", "reason": "System wipe attempt"},
    {"pattern": "git push --force", "action": "warn", "reason": "Force push can lose history"},
    {"pattern": "DROP TABLE", "action": "block", "reason": "Destructive SQL operation"},
    {"pattern": "nixos-rebuild switch", "action": "require_approval", "reason": "System change"},
    {"pattern": "sudo rm", "action": "warn", "reason": "Privileged file deletion"},
]

_message_bus_topics: Dict[str, List[Dict[str, Any]]] = {}
_message_bus_subscribers: Dict[str, List[str]] = {}  # topic -> [agent_ids]

_capability_history: Dict[str, List[Dict[str, Any]]] = {}  # agent_id -> [outcomes]

_rollback_registry: Dict[str, Dict[str, Any]] = {}  # session_id -> rollback_info


# ---------------------------------------------------------------------------
# Evidence handlers
# ---------------------------------------------------------------------------

async def handle_evidence_record(request: web.Request) -> web.Response:
    """Record evidence for a task/session (IndyDevDan pattern: Structured Evidence Capture)."""
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        evidence = {
            "id": f"ev-{int(time.time() * 1000)}",
            "session_id": session_id,
            "task_id": data.get("task_id", ""),
            "agent_id": data.get("agent_id", ""),
            "evidence_type": data.get("type", "general"),  # command, test, file_change, validation
            "content": data.get("content", {}),
            "command": data.get("command", ""),
            "output": data.get("output", ""),
            "exit_code": data.get("exit_code"),
            "files_changed": data.get("files_changed", []),
            "timestamp": time.time(),
            "tags": data.get("tags", []),
        }

        if session_id not in _evidence_store:
            _evidence_store[session_id] = []
        _evidence_store[session_id].append(evidence)

        return web.json_response({
            "status": "recorded",
            "evidence_id": evidence["id"],
            "session_id": session_id,
            "total_evidence": len(_evidence_store[session_id]),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_evidence_list(request: web.Request) -> web.Response:
    """List evidence for a session with optional filtering."""
    try:
        session_id = request.query.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        evidence_list = _evidence_store.get(session_id, [])
        evidence_type = request.query.get("type")
        if evidence_type:
            evidence_list = [e for e in evidence_list if e["evidence_type"] == evidence_type]

        task_id = request.query.get("task_id")
        if task_id:
            evidence_list = [e for e in evidence_list if e["task_id"] == task_id]

        return web.json_response({
            "session_id": session_id,
            "evidence": evidence_list,
            "count": len(evidence_list),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Safety gate handlers
# ---------------------------------------------------------------------------

async def handle_safety_check(request: web.Request) -> web.Response:
    """Check if a command/operation is safe to execute (IndyDevDan pattern: Safety Gates)."""
    try:
        data = await request.json()
        command = data.get("command", "")
        operation = data.get("operation", "")

        check_text = command or operation
        if not check_text:
            return web.json_response({"error": "command or operation required"}, status=400)

        violations = []
        for hook in _safety_hooks:
            pattern = hook["pattern"]
            if pattern.lower() in check_text.lower():
                violations.append({
                    "pattern": pattern,
                    "action": hook["action"],
                    "reason": hook["reason"],
                })

        # Phase 62.3: evaluate structured YAML safety rails
        request_fields = {
            "command": data.get("command", ""),
            "operation": data.get("operation", ""),
            "path": data.get("path", ""),
        }
        for rail in _safety_rails:
            pattern = rail.get("pattern", "")
            if not pattern:
                continue
            match_fields = rail.get("match_fields", ["command", "operation"])
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                for field in match_fields:
                    field_val = request_fields.get(field, "")
                    if field_val and compiled.search(field_val):
                        violations.append({
                            "pattern": pattern,
                            "action": rail.get("action", "warn"),
                            "reason": rail.get("reason", rail.get("id", "safety-rail")),
                            "rail_id": rail.get("id"),
                        })
                        break
            except re.error:
                pass

        if not violations:
            return web.json_response({
                "safe": True,
                "command": check_text,
                "action": "allow",
            })

        # Determine overall action (most restrictive wins)
        actions = [v["action"] for v in violations]
        if "block" in actions:
            overall_action = "block"
        elif "require_approval" in actions:
            overall_action = "require_approval"
        else:
            overall_action = "warn"

        return web.json_response({
            "safe": overall_action not in ("block", "require_approval"),
            "command": check_text,
            "action": overall_action,
            "violations": violations,
            "recommendation": "Request approval or modify command" if overall_action != "warn" else "Proceed with caution",
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_safety_register_hook(request: web.Request) -> web.Response:
    """Register a new safety hook pattern."""
    try:
        data = await request.json()
        pattern = data.get("pattern", "")
        action = data.get("action", "warn")
        reason = data.get("reason", "Custom safety rule")

        if not pattern:
            return web.json_response({"error": "pattern required"}, status=400)
        if action not in ("block", "warn", "require_approval"):
            return web.json_response({"error": "action must be block/warn/require_approval"}, status=400)

        hook = {"pattern": pattern, "action": action, "reason": reason}
        _safety_hooks.append(hook)

        return web.json_response({
            "status": "registered",
            "hook": hook,
            "total_hooks": len(_safety_hooks),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Inter-agent message bus handlers
# ---------------------------------------------------------------------------

async def handle_message_bus_publish(request: web.Request) -> web.Response:
    """Publish a message to a topic (IndyDevDan pattern: Inter-Agent Message Bus)."""
    try:
        data = await request.json()
        topic = data.get("topic", "")
        if not topic:
            return web.json_response({"error": "topic required"}, status=400)

        message = {
            "id": f"msg-{int(time.time() * 1000)}",
            "topic": topic,
            "from_agent": data.get("from_agent", ""),
            "payload": data.get("payload", {}),
            "message_type": data.get("type", "info"),  # info, request, response, event
            "timestamp": time.time(),
            "correlation_id": data.get("correlation_id", ""),
        }

        if topic not in _message_bus_topics:
            _message_bus_topics[topic] = []
        _message_bus_topics[topic].append(message)

        # Keep only last 100 messages per topic
        if len(_message_bus_topics[topic]) > 100:
            _message_bus_topics[topic] = _message_bus_topics[topic][-100:]

        subscriber_count = len(_message_bus_subscribers.get(topic, []))

        return web.json_response({
            "status": "published",
            "message_id": message["id"],
            "topic": topic,
            "subscriber_count": subscriber_count,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_message_bus_subscribe(request: web.Request) -> web.Response:
    """Subscribe an agent to a topic."""
    try:
        data = await request.json()
        topic = data.get("topic", "")
        agent_id = data.get("agent_id", "")

        if not topic or not agent_id:
            return web.json_response({"error": "topic and agent_id required"}, status=400)

        if topic not in _message_bus_subscribers:
            _message_bus_subscribers[topic] = []
        if agent_id not in _message_bus_subscribers[topic]:
            _message_bus_subscribers[topic].append(agent_id)

        return web.json_response({
            "status": "subscribed",
            "topic": topic,
            "agent_id": agent_id,
            "total_subscribers": len(_message_bus_subscribers[topic]),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_message_bus_poll(request: web.Request) -> web.Response:
    """Poll messages from a topic for an agent."""
    try:
        topic = request.query.get("topic", "")
        agent_id = request.query.get("agent_id", "")
        since = float(request.query.get("since", "0"))
        limit = int(request.query.get("limit", "50"))

        if not topic:
            return web.json_response({"error": "topic required"}, status=400)

        messages = _message_bus_topics.get(topic, [])
        # Filter messages after 'since' timestamp
        if since > 0:
            messages = [m for m in messages if m["timestamp"] > since]
        # Exclude own messages if agent_id provided
        if agent_id:
            messages = [m for m in messages if m["from_agent"] != agent_id]

        messages = messages[-limit:]

        return web.json_response({
            "topic": topic,
            "messages": messages,
            "count": len(messages),
            "latest_timestamp": messages[-1]["timestamp"] if messages else since,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Historical capability scoring handlers
# ---------------------------------------------------------------------------

async def handle_capability_record_outcome(request: web.Request) -> web.Response:
    """Record a capability outcome for an agent (IndyDevDan pattern: Historical Scoring)."""
    try:
        data = await request.json()
        agent_id = data.get("agent_id", "")
        capability = data.get("capability", "")

        if not agent_id or not capability:
            return web.json_response({"error": "agent_id and capability required"}, status=400)

        outcome = {
            "id": f"out-{int(time.time() * 1000)}",
            "agent_id": agent_id,
            "capability": capability,
            "task_id": data.get("task_id", ""),
            "success": data.get("success", True),
            "quality_score": data.get("quality_score", 1.0),  # 0.0 to 1.0
            "duration_seconds": data.get("duration_seconds"),
            "error_type": data.get("error_type"),
            "notes": data.get("notes", ""),
            "timestamp": time.time(),
        }

        if agent_id not in _capability_history:
            _capability_history[agent_id] = []
        _capability_history[agent_id].append(outcome)

        # Keep only last 500 outcomes per agent
        if len(_capability_history[agent_id]) > 500:
            _capability_history[agent_id] = _capability_history[agent_id][-500:]

        return web.json_response({
            "status": "recorded",
            "outcome_id": outcome["id"],
            "agent_id": agent_id,
            "capability": capability,
            "total_outcomes": len(_capability_history[agent_id]),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_capability_score(request: web.Request) -> web.Response:
    """Get capability scores for an agent based on historical performance."""
    try:
        agent_id = request.query.get("agent_id", "")
        capability = request.query.get("capability")
        window_hours = int(request.query.get("window_hours", "168"))  # Default 1 week

        if not agent_id:
            return web.json_response({"error": "agent_id required"}, status=400)

        outcomes = _capability_history.get(agent_id, [])
        cutoff = time.time() - (window_hours * 3600)
        outcomes = [o for o in outcomes if o["timestamp"] > cutoff]

        if capability:
            outcomes = [o for o in outcomes if o["capability"] == capability]

        if not outcomes:
            return web.json_response({
                "agent_id": agent_id,
                "capability": capability,
                "scores": {},
                "message": "No historical data available",
            })

        # Calculate scores by capability
        capabilities: Dict[str, List[Dict[str, Any]]] = {}
        for o in outcomes:
            cap = o["capability"]
            if cap not in capabilities:
                capabilities[cap] = []
            capabilities[cap].append(o)

        scores = {}
        for cap, cap_outcomes in capabilities.items():
            total = len(cap_outcomes)
            successes = sum(1 for o in cap_outcomes if o["success"])
            avg_quality = sum(o.get("quality_score", 1.0) for o in cap_outcomes) / total
            durations = [o["duration_seconds"] for o in cap_outcomes if o.get("duration_seconds")]
            avg_duration = sum(durations) / len(durations) if durations else None

            scores[cap] = {
                "success_rate": successes / total,
                "average_quality": round(avg_quality, 3),
                "sample_count": total,
                "average_duration_seconds": round(avg_duration, 2) if avg_duration else None,
                "recent_errors": [o["error_type"] for o in cap_outcomes[-5:] if o.get("error_type")],
            }

        # Calculate overall score
        overall_success = sum(1 for o in outcomes if o["success"]) / len(outcomes)
        overall_quality = sum(o.get("quality_score", 1.0) for o in outcomes) / len(outcomes)

        return web.json_response({
            "agent_id": agent_id,
            "window_hours": window_hours,
            "overall": {
                "success_rate": round(overall_success, 3),
                "average_quality": round(overall_quality, 3),
                "total_outcomes": len(outcomes),
            },
            "by_capability": scores,
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Rollback handlers
# ---------------------------------------------------------------------------

async def handle_rollback_register(request: web.Request) -> web.Response:
    """Register a rollback procedure for a session/task."""
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        rollback_info = {
            "session_id": session_id,
            "task_id": data.get("task_id", ""),
            "rollback_commands": data.get("commands", []),
            "rollback_files": data.get("files", {}),  # {path: original_content}
            "description": data.get("description", ""),
            "registered_at": time.time(),
            "registered_by": data.get("agent_id", ""),
            "status": "registered",
        }

        _rollback_registry[session_id] = rollback_info

        return web.json_response({
            "status": "registered",
            "session_id": session_id,
            "command_count": len(rollback_info["rollback_commands"]),
            "file_count": len(rollback_info["rollback_files"]),
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_rollback_execute(request: web.Request) -> web.Response:
    """Execute a registered rollback (IndyDevDan pattern: Safe Rollback)."""
    try:
        data = await request.json()
        session_id = data.get("session_id", "")
        dry_run = data.get("dry_run", True)  # Default to dry-run for safety

        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        rollback_info = _rollback_registry.get(session_id)
        if not rollback_info:
            return web.json_response({"error": f"No rollback registered for session {session_id}"}, status=404)

        if dry_run:
            return web.json_response({
                "status": "dry_run",
                "session_id": session_id,
                "would_execute": rollback_info["rollback_commands"],
                "would_restore_files": list(rollback_info["rollback_files"].keys()),
                "description": rollback_info["description"],
                "message": "Set dry_run=false to execute",
            })

        # Execute rollback (file restoration only - command execution requires approval)
        restored_files = []
        for file_path, content in rollback_info["rollback_files"].items():
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                restored_files.append(file_path)
            except Exception as e:
                logger.warning("Failed to restore %s: %s", file_path, e)

        rollback_info["status"] = "executed"
        rollback_info["executed_at"] = time.time()
        rollback_info["restored_files"] = restored_files

        return web.json_response({
            "status": "executed",
            "session_id": session_id,
            "restored_files": restored_files,
            "pending_commands": rollback_info["rollback_commands"],
            "message": "Files restored. Execute commands manually for safety.",
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_rollback_status(request: web.Request) -> web.Response:
    """Get rollback status for a session."""
    try:
        session_id = request.query.get("session_id", "")
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        rollback_info = _rollback_registry.get(session_id)
        if not rollback_info:
            return web.json_response({
                "session_id": session_id,
                "has_rollback": False,
                "message": "No rollback registered",
            })

        return web.json_response({
            "session_id": session_id,
            "has_rollback": True,
            "status": rollback_info["status"],
            "registered_at": rollback_info["registered_at"],
            "command_count": len(rollback_info["rollback_commands"]),
            "file_count": len(rollback_info["rollback_files"]),
            "description": rollback_info["description"],
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Phase 28 — safety gate configuration endpoints
# ---------------------------------------------------------------------------

_VALID_SAFETY_MODES = frozenset({"open", "review", "strict"})


async def handle_safety_gate_set(request: web.Request) -> web.Response:
    """POST /control/safety/gate — set the safety mode for a UAG session.

    Body: {"session_id": str, "safety_mode": "open"|"review"|"strict"}
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    session_id = body.get("session_id", "").strip()
    mode = body.get("safety_mode", "").strip()

    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)
    if mode not in _VALID_SAFETY_MODES:
        return web.json_response(
            {"error": f"safety_mode must be one of {sorted(_VALID_SAFETY_MODES)}"},
            status=400,
        )

    # healthcheck probe — validate mode schema only, no session lookup required
    if session_id == "healthcheck":
        return web.json_response({"ok": True, "session_id": session_id, "safety_mode": mode})

    if _lifecycle_fsm is None:
        return web.json_response({"error": "lifecycle_fsm unavailable"}, status=503)

    session = _lifecycle_fsm.get_session(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    session.safety_mode = mode
    _lifecycle_fsm._write_session(session)
    return web.json_response({"ok": True, "session_id": session_id, "safety_mode": mode})


async def handle_safety_gate_get(request: web.Request) -> web.Response:
    """GET /control/safety/gate/{session_id} — read gate state for a session."""
    session_id = request.match_info.get("session_id", "")
    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)

    if _lifecycle_fsm is None:
        return web.json_response({"error": "lifecycle_fsm unavailable"}, status=503)

    session = _lifecycle_fsm.get_session(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    return web.json_response({
        "session_id": session_id,
        "safety_mode": getattr(session, "safety_mode", "open"),
        "gate_log": getattr(session, "safety_gate_log", []),
    })


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/control/evidence/record", handle_evidence_record)
    http_app.router.add_get("/control/evidence/list", handle_evidence_list)
    http_app.router.add_post("/control/safety/check", handle_safety_check)
    http_app.router.add_post("/control/safety/register-hook", handle_safety_register_hook)
    http_app.router.add_post("/control/message-bus/publish", handle_message_bus_publish)
    http_app.router.add_post("/control/message-bus/subscribe", handle_message_bus_subscribe)
    http_app.router.add_get("/control/message-bus/poll", handle_message_bus_poll)
    http_app.router.add_post("/control/capability/record-outcome", handle_capability_record_outcome)
    http_app.router.add_get("/control/capability/score", handle_capability_score)
    http_app.router.add_post("/control/rollback/register", handle_rollback_register)
    http_app.router.add_post("/control/rollback/execute", handle_rollback_execute)
    http_app.router.add_get("/control/rollback/status", handle_rollback_status)
    # Phase 28 — guarded execution safety gate
    http_app.router.add_post("/control/safety/gate", handle_safety_gate_set)
    http_app.router.add_get("/control/safety/gate/{session_id}", handle_safety_gate_get)
