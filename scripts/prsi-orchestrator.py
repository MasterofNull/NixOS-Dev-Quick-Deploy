#!/usr/bin/env python3
"""
prsi-orchestrator.py

Pessimistic Recursive Self-Improvement (PRSI) control loop:
1. Identify actions from aq-report structured_actions
2. Queue with risk/approval state
3. Approve/reject actions
4. Execute approved actions through aq-optimizer
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
QUEUE_PATH = Path(os.getenv("PRSI_ACTION_QUEUE_PATH", "/var/lib/nixos-ai-stack/prsi/action-queue.json"))
ACTIONS_LOG_PATH = Path(os.getenv("PRSI_ACTIONS_LOG_PATH", "/var/log/nixos-ai-stack/prsi-actions.jsonl"))
AUTO_APPROVE_LOW_RISK = os.getenv("PRSI_AUTO_APPROVE_LOW_RISK", "true").lower() == "true"


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _log_event(event: Dict[str, Any]) -> None:
    try:
        ACTIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACTIONS_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        pass


def _action_fingerprint(action: Dict[str, Any]) -> str:
    stable = {
        "type": action.get("type"),
        "action": action.get("action"),
        "reason": action.get("reason"),
        "topic": action.get("topic"),
        "services": action.get("services"),
        "env_overrides": action.get("env_overrides"),
        "script": action.get("script"),
        "script_args": action.get("script_args"),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _risk_tier(action: Dict[str, Any]) -> str:
    if action.get("safe"):
        if action.get("type") in {"maintenance", "knowledge"}:
            return "low"
        if action.get("type") == "routing":
            return "medium"
        return "low"
    return "high"


def _load_queue() -> Dict[str, Any]:
    payload = _read_json(QUEUE_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    actions = payload.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    return {"updated_at": payload.get("updated_at"), "actions": actions}


def _save_queue(queue: Dict[str, Any]) -> None:
    queue["updated_at"] = _now()
    _write_json(QUEUE_PATH, queue)


def _fetch_structured_actions(since: str) -> List[Dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "aq-report"), f"--since={since}", "--format=json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"aq-report failed: {(result.stderr or '').strip()[:200]}")
    report = json.loads(result.stdout or "{}")
    actions = report.get("structured_actions", [])
    return [a for a in actions if isinstance(a, dict)]


def cmd_sync(args: argparse.Namespace) -> int:
    queue = _load_queue()
    existing = {a.get("id"): a for a in queue["actions"] if isinstance(a, dict)}
    discovered = _fetch_structured_actions(args.since)
    added = 0
    updated = 0

    for action in discovered:
        aid = _action_fingerprint(action)
        risk = _risk_tier(action)
        status = "approved" if (risk == "low" and AUTO_APPROVE_LOW_RISK) else "pending_approval"
        if aid in existing:
            row = existing[aid]
            row["last_seen_at"] = _now()
            row["seen_count"] = int(row.get("seen_count", 1)) + 1
            row["confidence"] = action.get("confidence")
            row["reason"] = action.get("reason")
            row["raw_action"] = action
            updated += 1
        else:
            existing[aid] = {
                "id": aid,
                "type": action.get("type"),
                "action": action.get("action"),
                "reason": action.get("reason"),
                "risk": risk,
                "safe": bool(action.get("safe", False)),
                "status": status,
                "confidence": action.get("confidence"),
                "created_at": _now(),
                "last_seen_at": _now(),
                "seen_count": 1,
                "raw_action": action,
                "approval": {"by": None, "at": None, "note": None},
                "execution": {"last_run_at": None, "result": None},
            }
            added += 1

    queue["actions"] = sorted(existing.values(), key=lambda x: (x.get("status") != "pending_approval", x.get("created_at", "")))
    _save_queue(queue)
    event = {"ts": _now(), "event": "sync", "since": args.since, "added": added, "updated": updated, "total": len(queue["actions"])}
    _log_event(event)
    print(json.dumps(event, sort_keys=True))
    return 0


def _set_approval(action_id: str, decision: str, by: str, note: str) -> Dict[str, Any]:
    queue = _load_queue()
    for row in queue["actions"]:
        if row.get("id") == action_id:
            row["status"] = "approved" if decision == "approve" else "rejected"
            row["approval"] = {"by": by or "unknown", "at": _now(), "note": note or None}
            _save_queue(queue)
            event = {"ts": _now(), "event": decision, "id": action_id, "by": by, "note": note}
            _log_event(event)
            return row
    raise KeyError(action_id)


def cmd_approve(args: argparse.Namespace) -> int:
    row = _set_approval(args.id, "approve", args.by, args.note)
    print(json.dumps({"ok": True, "id": row.get("id"), "status": row.get("status")}, sort_keys=True))
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    row = _set_approval(args.id, "reject", args.by, args.note)
    print(json.dumps({"ok": True, "id": row.get("id"), "status": row.get("status")}, sort_keys=True))
    return 0


def _list_actions(status: str | None, risk: str | None) -> List[Dict[str, Any]]:
    queue = _load_queue()
    rows = [a for a in queue["actions"] if isinstance(a, dict)]
    if status:
        rows = [a for a in rows if str(a.get("status")) == status]
    if risk:
        rows = [a for a in rows if str(a.get("risk")) == risk]
    return rows


def cmd_list(args: argparse.Namespace) -> int:
    rows = _list_actions(args.status, args.risk)
    payload = {
        "updated_at": _load_queue().get("updated_at"),
        "count": len(rows),
        "counts": {
            "pending_approval": len([r for r in rows if r.get("status") == "pending_approval"]),
            "approved": len([r for r in rows if r.get("status") == "approved"]),
            "executed": len([r for r in rows if r.get("status") == "executed"]),
            "rejected": len([r for r in rows if r.get("status") == "rejected"]),
        },
        "actions": rows,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    queue = _load_queue()
    approved = [
        a for a in queue["actions"]
        if isinstance(a, dict) and a.get("status") == "approved" and isinstance(a.get("raw_action"), dict)
    ]
    if args.limit:
        approved = approved[: args.limit]
    if not approved:
        print(json.dumps({"ok": True, "executed": 0, "message": "no approved actions"}, sort_keys=True))
        return 0

    actions_payload = [a["raw_action"] for a in approved]
    tmp_actions = Path("/tmp/prsi-actions-exec.json")
    _write_json(tmp_actions, actions_payload)

    argv = [
        sys.executable,
        str(SCRIPT_DIR / "aq-optimizer"),
        f"--actions-json={tmp_actions}",
        "--output-json",
    ]
    if args.dry_run:
        argv.append("--dry-run")
    result = subprocess.run(argv, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode != 0:
        event = {"ts": _now(), "event": "execute_failed", "stderr": (result.stderr or "")[:300]}
        _log_event(event)
        raise RuntimeError(f"aq-optimizer execution failed: {(result.stderr or '').strip()[:180]}")
    payload = json.loads(result.stdout or "{}")

    applied = payload.get("applied", [])
    for row in approved:
        row["execution"] = {"last_run_at": _now(), "result": "applied"}
        row["status"] = "executed" if not args.dry_run else "approved"
    _save_queue(queue)

    event = {"ts": _now(), "event": "execute", "count": len(approved), "dry_run": args.dry_run, "applied_count": len(applied)}
    _log_event(event)
    print(json.dumps({"ok": True, "selected": len(approved), "applied_count": len(applied), "dry_run": args.dry_run}, sort_keys=True))
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    sync_args = argparse.Namespace(since=args.since)
    cmd_sync(sync_args)
    # Auto-approve low-risk pending actions when configured.
    if AUTO_APPROVE_LOW_RISK:
        queue = _load_queue()
        changed = 0
        for row in queue["actions"]:
            if row.get("status") == "pending_approval" and row.get("risk") == "low":
                row["status"] = "approved"
                row["approval"] = {"by": "prsi-auto", "at": _now(), "note": "auto-approve low risk"}
                changed += 1
        if changed:
            _save_queue(queue)
            _log_event({"ts": _now(), "event": "auto_approve", "count": changed})
    exec_args = argparse.Namespace(limit=args.execute_limit, dry_run=args.dry_run)
    return cmd_execute(exec_args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PRSI orchestrator")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_sync = sub.add_parser("sync", help="Sync queue from aq-report structured actions")
    s_sync.add_argument("--since", default="1d")
    s_sync.set_defaults(func=cmd_sync)

    s_list = sub.add_parser("list", help="List queue actions")
    s_list.add_argument("--status", default=None)
    s_list.add_argument("--risk", default=None)
    s_list.set_defaults(func=cmd_list)

    s_approve = sub.add_parser("approve", help="Approve queued action")
    s_approve.add_argument("--id", required=True)
    s_approve.add_argument("--by", default="manual")
    s_approve.add_argument("--note", default="")
    s_approve.set_defaults(func=cmd_approve)

    s_reject = sub.add_parser("reject", help="Reject queued action")
    s_reject.add_argument("--id", required=True)
    s_reject.add_argument("--by", default="manual")
    s_reject.add_argument("--note", default="")
    s_reject.set_defaults(func=cmd_reject)

    s_exec = sub.add_parser("execute", help="Execute approved queued actions")
    s_exec.add_argument("--limit", type=int, default=5)
    s_exec.add_argument("--dry-run", action="store_true")
    s_exec.set_defaults(func=cmd_execute)

    s_cycle = sub.add_parser("cycle", help="sync + optional auto-approve + execute")
    s_cycle.add_argument("--since", default="1d")
    s_cycle.add_argument("--execute-limit", type=int, default=5)
    s_cycle.add_argument("--dry-run", action="store_true")
    s_cycle.set_defaults(func=cmd_cycle)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
