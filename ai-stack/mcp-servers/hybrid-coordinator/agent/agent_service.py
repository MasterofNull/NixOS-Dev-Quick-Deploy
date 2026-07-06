"""
agent/agent_service.py — AgentService for the hybrid-coordinator.

Phase R2.6 (Strangler Fig): route registration extracted from http_server.py.
Handles:
  GET  /api/agent-ops/status  — live drift state + profile override
  POST /api/agent-events      — ingest delegation/lesson/decision events
  GET  /api/agent-events      — recent events from tool-audit.jsonl
  *    /a2a/*                 — A2A task protocol (delegated to openai_a2a_handlers)

Standalone async handlers are converted from run_http_mode() closures using
direct module imports. No configure() injection required.

Note: _continuous_learning is not defined in http_server.py (latent NameError
caught silently by the outer try/except). Preserved here as None so CL is
never fed — identical observable behavior.

No handler logic beyond the extracted closures — other agent routes remain
delegated to their respective handler modules.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from aiohttp import web

logger = logging.getLogger(__name__)

# Preserved from http_server.py: _continuous_learning was undefined there
# (NameError caught silently). Set to None to maintain behavioral parity.
_continuous_learning: Any = None

_VALID_EVENT_TYPES = frozenset({
    "task_completed", "error_resolution", "lesson", "decision",
    "delegation_start", "delegation_end",
    "memory", "safety", "workflow",
})

# Phase 64.2: Canonical sub_type taxonomy for ContinuousLearning clustering
# Callers may pass any string; this set is used only for documentation + GET filter hints.
_CANONICAL_SUB_TYPES = frozenset({
    "schema_violation", "context_overflow", "logic_deadlock",
    "tool_timeout", "safety_block", "contradiction_detected",
    "drift_alert", "budget_exceeded",
})
_VALID_AGENTS = frozenset({
    "gemini", "codex", "claude", "local", "coordinator", "unknown",
})

_agent_ops_state: dict = {
    "drift_score": None,
    "profile_override": None,
    "alert_active": False,
    "since": None,
}

# A2A secret-scan guard (scripts/ai/lib/a2a_guard.py). The coordinator is the
# canonical A2A hub — every delegate-to-* posts its event summary here, so it is the
# right central checkpoint to (a) redact secrets before they are persisted to the
# shared tool-audit.jsonl and (b) flag findings for visibility. Loaded lazily and
# fails OPEN: a missing/broken guard must never drop a delegation audit event.
_a2a_guard_mod: Any = None  # None = not tried, False = load failed, module = ready


def _get_a2a_guard():
    global _a2a_guard_mod
    if _a2a_guard_mod is not None:
        return _a2a_guard_mod or None
    try:
        from importlib.machinery import SourceFileLoader
        from pathlib import Path
        guard_path = Path(__file__).resolve().parents[4] / "scripts" / "ai" / "lib" / "a2a_guard.py"
        _a2a_guard_mod = SourceFileLoader("a2a_guard", str(guard_path)).load_module()
    except Exception as _exc:  # noqa: BLE001 — fail open, never block audit ingest
        logger.debug("a2a_guard load failed (audit scan disabled): %s", _exc)
        _a2a_guard_mod = False
    return _a2a_guard_mod or None


# ---------------------------------------------------------------------------
# Standalone handlers (converted from closures in http_server.run_http_mode)
# ---------------------------------------------------------------------------


async def handle_agent_ops_status(_request: web.Request) -> web.Response:
    """GET /api/agent-ops/status — live drift state + profile override."""
    import drift_analyzer as _da
    da = _da.get_analyzer()
    try:
        drift_data = await da.compute_drift(window=20)
        score = drift_data.get("drift_score")
    except Exception:
        score = None
    return web.json_response({
        "drift_score":      score,
        "profile_override": _agent_ops_state.get("profile_override"),
        "alert_active":     _agent_ops_state.get("alert_active", False),
        "since":            _agent_ops_state.get("since"),
        "window_size":      20,
    })


async def handle_agent_events_post(request: web.Request) -> web.Response:
    """POST /api/agent-events — ingest a delegation/lesson/decision event."""
    from agent_registry import (
        _agent_lessons_lock,
        _load_agent_lessons_registry,
        _save_agent_lessons_registry,
    )

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    event_type = str(data.get("event_type") or "task_completed").strip()
    sub_type   = str(data.get("sub_type") or "").strip()
    agent      = str(data.get("agent") or "unknown").strip()
    outcome    = str(data.get("outcome") or "success").strip()
    summary    = str(data.get("summary") or "")[:400]
    tags       = data.get("tags") or []
    try:
        latency_ms = int(data.get("latency_ms") or 0)
    except (ValueError, TypeError):
        return web.json_response({"error": "latency_ms must be integer"}, status=400)
    task_id    = str(data.get("task_id") or "")[:64]

    # A2A safeguard: scan the event summary for secret-like content BEFORE it is
    # persisted to the shared audit log or fed to ContinuousLearning. Redact in place
    # so the central audit never itself leaks a secret; record finding kinds for
    # visibility. Fails open — a guard error must not drop the event.
    _secret_findings: list = []
    _guard = _get_a2a_guard()
    if _guard is not None and summary:
        try:
            _secret_findings = _guard.scan_secrets(summary)
            if _secret_findings:
                summary = _guard.redact(summary)
                logger.warning(
                    "a2a_secret_in_event agent=%s task_id=%s kinds=%s (redacted before persist)",
                    agent, task_id, [f["kind"] for f in _secret_findings],
                )
        except Exception as _exc:  # noqa: BLE001 — fail open
            logger.debug("a2a_guard scan skipped err=%s", _exc)

    if event_type not in _VALID_EVENT_TYPES:
        return web.json_response(
            {"error": f"unknown event_type '{event_type}'; valid: {sorted(_VALID_EVENT_TYPES)}"},
            status=400,
        )
    if agent not in _VALID_AGENTS:
        agent = "unknown"

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    audit_entry = {
        "tool_name": "ai_coordinator_delegate",
        "timestamp": ts,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "parameters": {
            "agent": agent,
            "task_id": task_id,
            "event_type": event_type,
            "sub_type": sub_type,
            "summary": summary,
            "tags": tags,
            "secret_findings": [f["kind"] for f in _secret_findings],
        },
        "error_message": "" if outcome == "success" else summary[:120],
    }
    audit_log = os.getenv(
        "TOOL_AUDIT_LOG_PATH",
        "/var/log/ai-audit-sidecar/tool-audit.jsonl",
    )
    try:
        with open(audit_log, "a", encoding="utf-8") as _fh:
            _fh.write(json.dumps(audit_entry) + "\n")
    except OSError as _e:
        logger.warning("agent_event_audit_write_failed path=%s err=%s", audit_log, _e)

    if event_type in {"task_completed", "error_resolution"}:
        try:
            if event_type == "task_completed":
                _cl_event = {
                    "event": event_type,
                    "timestamp": ts,
                    "task": {
                        "task_id": task_id,
                        "prompt": summary,
                        "output": summary,
                        "backend": agent,
                        "context": {"sub_type": sub_type, "outcome": outcome},
                    },
                }
            else:
                _cl_event = {
                    "event": event_type,
                    "timestamp": ts,
                    "error_id": task_id,
                    "error_description": summary,
                    "solution": summary,
                    "resolution_time": latency_ms / 1000.0,
                }
            if hasattr(_continuous_learning, "process_event"):
                asyncio.create_task(_continuous_learning.process_event(_cl_event))
        except Exception as _exc:
            logger.debug("agent_event_cl_feed_skip err=%s", _exc)

    if event_type == "lesson" and summary:
        try:
            async with _agent_lessons_lock:
                _registry = await _load_agent_lessons_registry()
                _entries = list(_registry.get("entries") or [])
                import hashlib as _hl
                _key = "auto-" + _hl.md5(summary.encode()).hexdigest()[:8]
                _exists = any(e.get("lesson_key") == _key for e in _entries)
                if not _exists:
                    _entries.append({
                        "lesson_key": _key,
                        "summary": summary[:240],
                        "source_agent": agent,
                        "state": "pending_review",
                        "created_at": ts,
                        "tags": tags,
                    })
                    _registry["entries"] = _entries
                    await _save_agent_lessons_registry(_registry)
        except Exception as _exc:
            logger.debug("agent_event_lesson_registry_skip err=%s", _exc)

    return web.json_response({
        "accepted": True,
        "event_type": event_type,
        "sub_type": sub_type or None,
        "agent": agent,
        "outcome": outcome,
        "timestamp": ts,
        "secret_findings": [f["kind"] for f in _secret_findings],
    })


_AUDIT_TAIL_BYTES = 512 * 1024  # read at most the last 512 KB — avoids 359 MB readlines()


def _read_audit_tail_sync(
    audit_log: str,
    limit: int,
    filter_type: str,
    filter_sub_type: str,
    window_s: int,
) -> list:
    """Blocking helper — MUST be called via asyncio.to_thread().

    Tail-reads the last _AUDIT_TAIL_BYTES of the JSONL log so we never load
    the full file (currently 359 MB) into memory on every poll request.
    """
    from datetime import datetime as _dt
    now = time.time()
    events: list = []
    try:
        with open(audit_log, "r", encoding="utf-8", errors="replace") as _fh:
            _fh.seek(0, 2)  # seek to end
            file_size = _fh.tell()
            _fh.seek(max(0, file_size - _AUDIT_TAIL_BYTES))
            chunk = _fh.read()
        lines = chunk.splitlines()
        for raw in reversed(lines):
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
                ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if now - ts > window_s:
                continue
            params = entry.get("parameters") or {}
            if filter_type and params.get("event_type") != filter_type:
                continue
            if filter_sub_type and params.get("sub_type") != filter_sub_type:
                continue
            events.append({
                "event_type": params.get("event_type", "task_completed"),
                "sub_type":   params.get("sub_type", ""),
                "agent":      params.get("agent", "unknown"),
                "outcome":    entry.get("outcome", ""),
                "summary":    params.get("summary", ""),
                "task_id":    params.get("task_id", ""),
                "tags":       params.get("tags") or [],
                "latency_ms": entry.get("latency_ms", 0),
                "timestamp":  ts_str,
            })
            if len(events) >= limit:
                break
    except OSError:
        pass
    return events


async def handle_agent_events_get(request: web.Request) -> web.Response:
    """GET /api/agent-events — recent events from tool-audit.jsonl."""
    try:
        limit = min(int(request.rel_url.query.get("limit", "20")), 100)
    except (ValueError, TypeError):
        limit = 20
    filter_type     = request.rel_url.query.get("event_type", "")
    filter_sub_type = request.rel_url.query.get("sub_type", "")
    try:
        window_s = int(request.rel_url.query.get("window_s", "86400"))
    except (ValueError, TypeError):
        window_s = 86400

    audit_log = os.getenv(
        "TOOL_AUDIT_LOG_PATH",
        "/var/log/ai-audit-sidecar/tool-audit.jsonl",
    )
    # Run blocking file I/O in a thread — never block the aiohttp event loop.
    events = await asyncio.to_thread(
        _read_audit_tail_sync, audit_log, limit, filter_type, filter_sub_type, window_s
    )
    return web.json_response({"events": events, "total_in_window": len(events)})


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all AgentService routes on the given aiohttp Application."""
    app.router.add_get("/api/agent-ops/status", handle_agent_ops_status)
    app.router.add_post("/api/agent-events", handle_agent_events_post)
    app.router.add_get("/api/agent-events", handle_agent_events_get)

    # A2A task protocol — already fully extracted to openai_a2a_handlers
    import openai_a2a_handlers as _a2a
    _a2a.register_routes(app)
