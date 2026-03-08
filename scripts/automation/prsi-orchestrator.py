#!/usr/bin/env python3
"""
prsi-orchestrator.py

Pessimistic Recursive Self-Improvement (PRSI) control loop:
1. Identify actions from aq-report structured_actions
2. Queue with risk/approval state
3. Approve/reject actions
4. Execute approved actions through aq-optimizer

Budget-aware policy (v2):
- token-cap gating (estimated remote token budget)
- low-rate counterfactual sampling markers (no always-on dual execution)
- escalation flags from report degradation signals
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
AI_SCRIPT_DIR = SCRIPT_DIR.parent / "ai"
REPO_ROOT = SCRIPT_DIR.parent.parent
QUEUE_PATH = Path(os.getenv("PRSI_ACTION_QUEUE_PATH", "/var/lib/nixos-ai-stack/prsi/action-queue.json"))
ACTIONS_LOG_PATH = Path(os.getenv("PRSI_ACTIONS_LOG_PATH", "/var/log/nixos-ai-stack/prsi-actions.jsonl"))
AUTO_APPROVE_LOW_RISK = os.getenv("PRSI_AUTO_APPROVE_LOW_RISK", "true").lower() == "true"
PRSI_POLICY_FILE = Path(os.getenv("PRSI_POLICY_FILE", str(REPO_ROOT / "config/runtime-prsi-policy.json")))
PRSI_STATE_PATH = Path(os.getenv("PRSI_STATE_PATH", "/var/lib/nixos-ai-stack/prsi/runtime-state.json"))


DEFAULT_POLICY: Dict[str, Any] = {
    "enabled": True,
    "since": "1d",
    "max_execute_per_cycle": 5,
    "counterfactual": {
        "sample_rate": 0.08,
        "max_samples_per_day": 3,
        "eligible_action_types": ["routing", "prompt", "workflow"],
    },
    "budget": {
        "remote_token_cap_daily": 120000,
        "default_action_token_cost": 1800,
        "hard_stop_on_cap": True,
        "estimated_cost_by_type": {
            "knowledge": 400,
            "maintenance": 900,
            "routing": 1500,
            "prompt": 2200,
            "workflow": 2500,
        },
    },
    "escalation": {
        "enable_on_degrade": True,
        "hint_adoption_below_pct": 65,
        "eval_latest_below_pct": 60,
        "cache_hit_below_pct": 50,
        "intent_coverage_below_pct": 60,
    },
    "gates": {
        "allow_action_types": ["knowledge", "maintenance", "routing", "prompt", "workflow"],
        "block_high_risk_without_approval": True,
    },
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _today_utc() -> str:
    return datetime.now(tz=timezone.utc).date().isoformat()


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


def _load_policy() -> Dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    loaded = _read_json(PRSI_POLICY_FILE, {})
    if isinstance(loaded, dict):
        for key, val in loaded.items():
            if isinstance(policy.get(key), dict) and isinstance(val, dict):
                merged = dict(policy[key])
                merged.update(val)
                policy[key] = merged
            else:
                policy[key] = val
    return policy


def _load_state() -> Dict[str, Any]:
    state = _read_json(PRSI_STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    today = _today_utc()
    if state.get("date") != today:
        state = {
            "date": today,
            "remote_tokens_used": 0,
            "counterfactual_samples": 0,
            "last_updated": _now(),
        }
    state.setdefault("remote_tokens_used", 0)
    state.setdefault("counterfactual_samples", 0)
    state.setdefault("date", today)
    state.setdefault("last_updated", _now())
    return state


def _save_state(state: Dict[str, Any]) -> None:
    state["last_updated"] = _now()
    _write_json(PRSI_STATE_PATH, state)


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
    return {
        "updated_at": payload.get("updated_at"),
        "actions": actions,
        "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
    }


def _save_queue(queue: Dict[str, Any]) -> None:
    queue["updated_at"] = _now()
    _write_json(QUEUE_PATH, queue)


def _fetch_report(since: str) -> Dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(AI_SCRIPT_DIR / "aq-report"), f"--since={since}", "--format=json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"aq-report failed: {(result.stderr or '').strip()[:200]}")
    payload = json.loads(result.stdout or "{}")
    return payload if isinstance(payload, dict) else {}


def _fetch_structured_actions(since: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    report = _fetch_report(since)
    actions = report.get("structured_actions", [])
    return [a for a in actions if isinstance(a, dict)], report


def _compute_degradation_flags(report: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    esc = policy.get("escalation", {}) if isinstance(policy.get("escalation"), dict) else {}
    flags: Dict[str, Any] = {"degraded": False, "reasons": []}

    def low(metric_name: str, value: Any, threshold_key: str) -> None:
        try:
            v = float(value)
            t = float(esc.get(threshold_key, -1))
        except (TypeError, ValueError):
            return
        if t >= 0 and v < t:
            flags["degraded"] = True
            flags["reasons"].append(f"{metric_name}_below_threshold:{v:.1f}<{t:.1f}")

    hint = report.get("hint_adoption", {}) if isinstance(report.get("hint_adoption"), dict) else {}
    eval_trend = report.get("eval_trend", {}) if isinstance(report.get("eval_trend"), dict) else {}
    cache = report.get("cache", {}) if isinstance(report.get("cache"), dict) else {}
    intent = report.get("intent_contract_compliance", {}) if isinstance(report.get("intent_contract_compliance"), dict) else {}

    low("hint_adoption", hint.get("adoption_pct"), "hint_adoption_below_pct")
    low("eval_latest", eval_trend.get("latest_pct"), "eval_latest_below_pct")
    low("cache_hit", cache.get("hit_pct"), "cache_hit_below_pct")
    low("intent_contract", intent.get("contract_coverage_pct"), "intent_coverage_below_pct")
    return flags


def _estimate_action_token_cost(action: Dict[str, Any], policy: Dict[str, Any]) -> int:
    try:
        explicit = int(action.get("cost_estimate_tokens", 0) or 0)
    except (TypeError, ValueError):
        explicit = 0
    if explicit > 0:
        return explicit
    budget = policy.get("budget", {}) if isinstance(policy.get("budget"), dict) else {}
    by_type = budget.get("estimated_cost_by_type", {}) if isinstance(budget.get("estimated_cost_by_type"), dict) else {}
    action_type = str(action.get("type", "") or "").strip().lower()
    try:
        if action_type in by_type:
            return max(1, int(by_type[action_type]))
        return max(1, int(budget.get("default_action_token_cost", 1800)))
    except (TypeError, ValueError):
        return 1800


def cmd_sync(args: argparse.Namespace) -> int:
    policy = _load_policy()
    queue = _load_queue()
    existing = {a.get("id"): a for a in queue["actions"] if isinstance(a, dict)}
    discovered, report = _fetch_structured_actions(args.since)
    degradation = _compute_degradation_flags(report, policy)
    added = 0
    updated = 0

    for action in discovered:
        aid = _action_fingerprint(action)
        risk = _risk_tier(action)
        status = "approved" if (risk == "low" and AUTO_APPROVE_LOW_RISK) else "pending_approval"
        est_cost = _estimate_action_token_cost(action, policy)
        if aid in existing:
            row = existing[aid]
            row["last_seen_at"] = _now()
            row["seen_count"] = int(row.get("seen_count", 1)) + 1
            row["confidence"] = action.get("confidence")
            row["reason"] = action.get("reason")
            row["raw_action"] = action
            row["estimated_token_cost"] = est_cost
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
                "estimated_token_cost": est_cost,
                "created_at": _now(),
                "last_seen_at": _now(),
                "seen_count": 1,
                "raw_action": action,
                "approval": {"by": None, "at": None, "note": None},
                "execution": {"last_run_at": None, "result": None},
            }
            added += 1

    queue["actions"] = sorted(existing.values(), key=lambda x: (x.get("status") != "pending_approval", x.get("created_at", "")))
    queue["meta"] = {
        "since": args.since,
        "degradation": degradation,
        "policy_file": str(PRSI_POLICY_FILE),
    }
    _save_queue(queue)
    event = {
        "ts": _now(),
        "event": "sync",
        "since": args.since,
        "added": added,
        "updated": updated,
        "total": len(queue["actions"]),
        "degraded": bool(degradation.get("degraded", False)),
        "degradation_reasons": degradation.get("reasons", []),
    }
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


def _set_verifier(action_id: str, by: str, note: str) -> Dict[str, Any]:
    queue = _load_queue()
    for row in queue["actions"]:
        if row.get("id") == action_id:
            approval = row.get("approval") if isinstance(row.get("approval"), dict) else {}
            approval.update({"verifier_by": by or "unknown", "verifier_at": _now(), "verifier_note": note or None})
            row["approval"] = approval
            _save_queue(queue)
            event = {"ts": _now(), "event": "verify", "id": action_id, "by": by, "note": note}
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


def cmd_verify(args: argparse.Namespace) -> int:
    row = _set_verifier(args.id, args.by, args.note)
    print(json.dumps({"ok": True, "id": row.get("id"), "verifier_by": row.get("approval", {}).get("verifier_by")}, sort_keys=True))
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
    queue = _load_queue()
    payload = {
        "updated_at": queue.get("updated_at"),
        "meta": queue.get("meta", {}),
        "count": len(rows),
        "counts": {
            "pending_approval": len([r for r in rows if r.get("status") == "pending_approval"]),
            "approved": len([r for r in rows if r.get("status") == "approved"]),
            "executed": len([r for r in rows if r.get("status") == "executed"]),
            "counterfactual_queued": len([r for r in rows if r.get("status") == "counterfactual_queued"]),
            "rejected": len([r for r in rows if r.get("status") == "rejected"]),
        },
        "actions": rows,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _select_actions_for_execution(approved: List[Dict[str, Any]], policy: Dict[str, Any], state: Dict[str, Any], hard_limit: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    budget = policy.get("budget", {}) if isinstance(policy.get("budget"), dict) else {}
    gates = policy.get("gates", {}) if isinstance(policy.get("gates"), dict) else {}
    cf = policy.get("counterfactual", {}) if isinstance(policy.get("counterfactual"), dict) else {}

    cap = int(budget.get("remote_token_cap_daily", 120000) or 120000)
    used = int(state.get("remote_tokens_used", 0) or 0)
    remaining = max(0, cap - used)
    hard_stop = bool(budget.get("hard_stop_on_cap", True))

    allowed_types = {str(t).strip().lower() for t in gates.get("allow_action_types", [])} if isinstance(gates.get("allow_action_types"), list) else set()
    block_high_risk = bool(gates.get("block_high_risk_without_approval", True))
    require_independent_verifier = bool(gates.get("require_independent_verifier_for_high_risk", False))

    sample_rate = float(cf.get("sample_rate", 0.0) or 0.0)
    sample_rate = max(0.0, min(1.0, sample_rate))
    max_samples = int(cf.get("max_samples_per_day", 0) or 0)
    sample_used = int(state.get("counterfactual_samples", 0) or 0)
    eligible_cf_types = {str(t).strip().lower() for t in cf.get("eligible_action_types", [])} if isinstance(cf.get("eligible_action_types"), list) else set()

    selected: List[Dict[str, Any]] = []
    sampled: List[Dict[str, Any]] = []

    for row in approved:
        if len(selected) >= hard_limit:
            break
        action = row.get("raw_action") if isinstance(row.get("raw_action"), dict) else {}
        action_type = str(row.get("type", "") or action.get("type", "")).strip().lower()
        risk = str(row.get("risk", "") or "")

        if allowed_types and action_type not in allowed_types:
            row.setdefault("execution", {})["result"] = "skipped_policy_disallow_type"
            continue
        if block_high_risk and risk == "high" and row.get("status") != "approved":
            row.setdefault("execution", {})["result"] = "skipped_policy_high_risk"
            continue
        if require_independent_verifier and risk == "high":
            approval = row.get("approval") if isinstance(row.get("approval"), dict) else {}
            if not approval.get("verifier_by"):
                row.setdefault("execution", {})["result"] = "skipped_missing_independent_verifier"
                continue

        est_cost = int(row.get("estimated_token_cost", _estimate_action_token_cost(action, policy)) or 0)

        can_sample = (
            sample_rate > 0
            and sample_used < max_samples
            and (not eligible_cf_types or action_type in eligible_cf_types)
        )
        if can_sample and random.random() < sample_rate:
            sampled.append(row)
            sample_used += 1
            row["status"] = "counterfactual_queued"
            row.setdefault("execution", {})["result"] = "queued_counterfactual"
            continue

        if est_cost > remaining:
            row.setdefault("execution", {})["result"] = "skipped_budget_cap"
            if hard_stop:
                break
            continue

        selected.append(row)
        remaining -= est_cost

    state["counterfactual_samples"] = sample_used
    consumed = max(0, (cap - used) - remaining)
    return selected, sampled, consumed


def cmd_execute(args: argparse.Namespace) -> int:
    policy = _load_policy()
    if not bool(policy.get("enabled", True)):
        print(json.dumps({"ok": True, "executed": 0, "message": "policy disabled"}, sort_keys=True))
        return 0

    queue = _load_queue()
    approved = [
        a for a in queue["actions"]
        if isinstance(a, dict) and a.get("status") == "approved" and isinstance(a.get("raw_action"), dict)
    ]
    limit = int(args.limit or int(policy.get("max_execute_per_cycle", 5) or 5))
    if limit > 0:
        approved = approved[: limit]
    if not approved:
        print(json.dumps({"ok": True, "executed": 0, "message": "no approved actions"}, sort_keys=True))
        return 0

    state = _load_state()
    selected, sampled, est_consumed = _select_actions_for_execution(approved, policy, state, limit)
    if not selected:
        _save_queue(queue)
        _save_state(state)
        payload = {
            "ok": True,
            "selected": 0,
            "sampled_counterfactual": len(sampled),
            "estimated_tokens_consumed": 0,
            "message": "no actions selected after policy gates",
        }
        _log_event({"ts": _now(), "event": "execute_skipped", **payload})
        print(json.dumps(payload, sort_keys=True))
        return 0

    actions_payload = [a["raw_action"] for a in selected]
    tmp_actions = Path("/tmp/prsi-actions-exec.json")
    _write_json(tmp_actions, actions_payload)

    argv = [
        sys.executable,
        str(AI_SCRIPT_DIR / "aq-optimizer"),
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
    for row in selected:
        row["execution"] = {"last_run_at": _now(), "result": "applied"}
        row["status"] = "executed" if not args.dry_run else "approved"
    _save_queue(queue)

    if not args.dry_run:
        state["remote_tokens_used"] = int(state.get("remote_tokens_used", 0) or 0) + int(est_consumed)
    _save_state(state)

    event = {
        "ts": _now(),
        "event": "execute",
        "count": len(selected),
        "sampled_counterfactual": len(sampled),
        "dry_run": args.dry_run,
        "applied_count": len(applied),
        "estimated_tokens_consumed": est_consumed,
        "remote_tokens_used_today": int(state.get("remote_tokens_used", 0) or 0),
        "remote_token_cap_daily": int(policy.get("budget", {}).get("remote_token_cap_daily", 120000)),
    }
    _log_event(event)
    print(json.dumps({"ok": True, **{k: v for k, v in event.items() if k != "ts"}}, sort_keys=True))
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    policy = _load_policy()
    since = str(args.since or policy.get("since", "1d"))
    sync_args = argparse.Namespace(since=since)
    cmd_sync(sync_args)

    queue = _load_queue()
    degradation = queue.get("meta", {}).get("degradation", {}) if isinstance(queue.get("meta", {}), dict) else {}
    esc = policy.get("escalation", {}) if isinstance(policy.get("escalation"), dict) else {}
    if bool(esc.get("enable_on_degrade", True)) and bool(degradation.get("degraded", False)):
        _log_event({
            "ts": _now(),
            "event": "degradation_detected",
            "reasons": degradation.get("reasons", []),
            "note": "Escalation flagged; run deeper eval only on demand to preserve token budget.",
        })

    # Auto-approve low-risk pending actions when configured.
    if AUTO_APPROVE_LOW_RISK:
        changed = 0
        for row in queue["actions"]:
            if row.get("status") == "pending_approval" and row.get("risk") == "low":
                row["status"] = "approved"
                row["approval"] = {"by": "prsi-auto", "at": _now(), "note": "auto-approve low risk"}
                changed += 1
        if changed:
            _save_queue(queue)
            _log_event({"ts": _now(), "event": "auto_approve", "count": changed})

    limit = int(args.execute_limit or int(policy.get("max_execute_per_cycle", 5) or 5))
    exec_args = argparse.Namespace(limit=limit, dry_run=args.dry_run)
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

    s_verify = sub.add_parser("verify", help="Record independent verifier sign-off for high-risk action")
    s_verify.add_argument("--id", required=True)
    s_verify.add_argument("--by", required=True)
    s_verify.add_argument("--note", default="")
    s_verify.set_defaults(func=cmd_verify)

    s_exec = sub.add_parser("execute", help="Execute approved queued actions")
    s_exec.add_argument("--limit", type=int, default=5)
    s_exec.add_argument("--dry-run", action="store_true")
    s_exec.set_defaults(func=cmd_execute)

    s_cycle = sub.add_parser("cycle", help="sync + optional auto-approve + execute")
    s_cycle.add_argument("--since", default=None)
    s_cycle.add_argument("--execute-limit", type=int, default=0)
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
