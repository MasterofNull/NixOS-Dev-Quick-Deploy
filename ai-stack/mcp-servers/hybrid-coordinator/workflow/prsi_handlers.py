"""
PRSI (Pessimistic Recursive Self-Improvement) HTTP handlers.

Extracted from http_server.py (Phase 12.4 decomposition).

Owns the PRSI queue read, actions list, and action execute surfaces.
All handlers are file/subprocess-only; no ML model calls.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aiohttp import web

logger = __import__("logging").getLogger("hybrid-coordinator")

_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None


def init(*, error_payload_fn: Callable[[str, Exception], Dict[str, Any]]) -> None:
    global _error_payload
    _error_payload = error_payload_fn

def _prsi_queue_path() -> Path:
    return Path(os.getenv("PRSI_ACTION_QUEUE_PATH", "/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json"))


def _prsi_pending_rows(rows) -> list:
    """Rows awaiting owner sign-off; same rule as approval_inbox.collect() approval section."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        raw = row.get("raw_action") if isinstance(row.get("raw_action"), dict) else {}
        ap = row.get("approval") if isinstance(row.get("approval"), dict) else {}
        status = row.get("status", "")
        if raw.get("source") == "rsi-incidents.json":
            if status in ("rsi_pending", "rsi_failed") and row.get("risk") == "high" and not ap.get("verifier_by"):
                out.append(row)
        elif status == "pending_approval":
            out.append(row)
    return out


def _prsi_summary(row) -> dict:
    raw = row.get("raw_action") if isinstance(row.get("raw_action"), dict) else {}
    return {
        "id": row.get("id", ""),
        "type": row.get("type", ""),
        "action": row.get("action", ""),
        "reason": str(row.get("reason") or raw.get("reason") or "")[:200],
        "risk": row.get("risk", ""),
        "status": row.get("status", ""),
        "summary": str(row.get("reason") or raw.get("reason") or row.get("action") or "")[:200],
        "created_at": row.get("created_at", ""),
    }


_PRSI_REFUSALS = {
    "approve": "Owner decisions are not recorded by agents. Use the approval inbox: `aq-approve` (numbered list); the owner confirms in chat.",
    "reject": "Owner decisions are not recorded by agents. Use the approval inbox: `aq-approve` (numbered list); the owner confirms in chat.",
    "execute": "Execution is run by the ai-prsi-orchestrator timers (the coordinator cannot write the canonical queue).",
    "sync": "Queue sync is run by the ai-prsi-orchestrator timers (the coordinator cannot write the canonical queue).",
}


def prsi_orchestrate_readonly(action: str) -> Dict[str, Any]:
    """MCP prsi_orchestrate: read-only `list`; every mutation is refused with a pointer to its owner path."""
    action = str(action or "").strip()
    if action in _PRSI_REFUSALS:
        return {"status": "refused", "action": action, "reason": _PRSI_REFUSALS[action], "valid_actions": ["list"]}
    if action != "list":
        return {"status": "error", "error": f"unknown action '{action}'", "valid_actions": ["list"]}
    path = _prsi_queue_path()
    if not path.exists():
        return {"status": "ok", "pending": [], "count": 0, "queue_exists": False}
    try:
        queue = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return {"status": "error", "error": f"queue unreadable: {exc}"}
    rows = queue if isinstance(queue, list) else (queue.get("actions", []) if isinstance(queue, dict) else [])
    pending = [_prsi_summary(a) for a in _prsi_pending_rows(rows)]
    return {"status": "ok", "pending": pending, "count": len(pending), "queue_exists": True}


async def handle_prsi_pending(_request: web.Request) -> web.Response:
    """
    GET /control/prsi/pending — Fast read of pending PRSI actions from queue file.

    Does NOT shell out to aq-report (which is slow). Reads the queue JSON
    directly and returns only actions in a pending/awaiting-approval state.
    Intended for local model context injection and MCP tool calls.
    """
    queue_path = _prsi_queue_path()
    try:
        if not queue_path.exists():
            return web.json_response({
                "status": "ok",
                "pending": [],
                "count": 0,
                "queue_exists": False,
            })

        with open(queue_path) as f:
            queue = json.load(f)

        all_actions = queue if isinstance(queue, list) else (queue.get("actions", []) if isinstance(queue, dict) else [])
        pending = [_prsi_summary(a) for a in _prsi_pending_rows(all_actions)]
        state_counts: Dict[str, int] = {}
        for a in all_actions:
            if isinstance(a, dict):
                s = a.get("status", "unknown")
                state_counts[s] = state_counts.get(s, 0) + 1

        return web.json_response({
            "status": "ok",
            "pending": pending,
            "count": len(pending),
            "state_counts": state_counts,
            "triage_cmd": "python3 scripts/automation/prsi-orchestrator.py list",
            "approve_cmd": "python3 scripts/automation/prsi-orchestrator.py approve --id <id> --by <name>",
            "execute_cmd": "python3 scripts/automation/prsi-orchestrator.py execute --limit 1",
        })
    except json.JSONDecodeError as exc:
        return web.json_response({"status": "error", "error": f"malformed queue JSON: {exc}"}, status=500)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_prsi_actions_list(_request: web.Request) -> web.Response:
    """
    GET /control/prsi/actions — List available PRSI optimization actions.

    Calls aq-report --format=json and returns structured_actions.
    """
    try:
        repo_root = Path(__file__).parent.parent.parent.parent
        scripts_dir = repo_root / "scripts/ai"
        aq_report_path = scripts_dir / "aq-report"

        if not aq_report_path.exists():
            return web.json_response({
                "status": "error",
                "error": "aq-report script not found",
                "path": str(aq_report_path)
            }, status=404)

        result = subprocess.run(
            [sys.executable, str(aq_report_path), "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return web.json_response({
                "status": "error",
                "error": "aq-report failed",
                "stderr": result.stderr[:500]
            }, status=500)

        try:
            report_data = json.loads(result.stdout)
            actions = report_data.get("structured_actions", [])
            return web.json_response({
                "status": "ok",
                "service": "prsi",
                "actions": actions,
                "action_count": len(actions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except json.JSONDecodeError as exc:
            return web.json_response({
                "status": "error",
                "error": "invalid JSON from aq-report",
                "detail": str(exc)
            }, status=500)

    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_prsi_action_execute(request: web.Request) -> web.Response:
    """
    POST /control/prsi/actions/execute — Execute a PRSI optimization action.

    Body:
        {
            "action_id": "routing.01",  # Optional - defaults to running aq-optimizer
            "dry_run": true,            # Optional - defaults to true
            "action_type": "routing",   # Optional: routing, knowledge, maintenance
            "params": {}                # Optional: action-specific parameters
        }
    """
    try:
        data = await request.json() if request.can_read_body else {}
        dry_run = bool(data.get("dry_run", True))
        action_type = str(data.get("action_type", "")).strip()

        repo_root = Path(__file__).parent.parent.parent.parent
        scripts_dir = repo_root / "scripts/ai"

        if not action_type:
            aq_optimizer_path = scripts_dir / "aq-optimizer"
            if not aq_optimizer_path.exists():
                return web.json_response({
                    "status": "error",
                    "error": "aq-optimizer script not found"
                }, status=404)

            cmd = [sys.executable, str(aq_optimizer_path)]
            if dry_run:
                cmd.append("--dry-run")
            cmd.append("--output-json")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            return web.json_response({
                "status": "ok" if result.returncode == 0 else "failed",
                "service": "prsi",
                "tool": "aq-optimizer",
                "dry_run": dry_run,
                "exit_code": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500] if result.stderr else "",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        elif action_type == "gap_remediation":
            aq_gap_path = scripts_dir / "aq-gap-auto-remediate"
            if not aq_gap_path.exists():
                return web.json_response({
                    "status": "error",
                    "error": "aq-gap-auto-remediate script not found"
                }, status=404)

            cmd = [sys.executable, str(aq_gap_path)]
            if dry_run:
                cmd.append("--dry-run")
            cmd.extend(["--limit", "5"])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            return web.json_response({
                "status": "ok" if result.returncode == 0 else "failed",
                "service": "prsi",
                "tool": "aq-gap-auto-remediate",
                "dry_run": dry_run,
                "exit_code": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500] if result.stderr else "",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        else:
            return web.json_response({
                "status": "error",
                "error": f"unknown action_type: {action_type}",
                "supported_types": ["routing", "knowledge", "maintenance", "gap_remediation"]
            }, status=400)

    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/control/prsi/pending", handle_prsi_pending)
    http_app.router.add_get("/control/prsi/actions", handle_prsi_actions_list)
    http_app.router.add_post("/control/prsi/actions/execute", handle_prsi_action_execute)
