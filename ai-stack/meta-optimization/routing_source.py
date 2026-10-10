#!/usr/bin/env python3
"""Routing/model-call data source for meta-optimization (pure stdlib).

Replaces a former SQL routing table that never existed. The canonical record is the
agent-run event log (schema ``maeah.agent-run-event.v1``); only ``model_call``
events are used. Fixture rows (source containing "fixture", or model
"fixture-model") are test data and always excluded. The switchboard decision log
(``.agents/telemetry/routing-decisions.jsonl``) is a secondary, local-vs-remote
view.

All readers stream line by line (the event log is ~100 MB), tolerate malformed
lines, and return empty results when the file is missing.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

DEFAULT_EVENTS_PATH = "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl"
SUCCESS_STATUSES = frozenset({"succeeded", "success", "ok"})
# "running" rows are progress heartbeats, not outcomes.
NON_TERMINAL_STATUSES = frozenset({"running", "started", "pending", "in_progress"})


def events_path(path: Optional[str] = None) -> str:
    return path or os.getenv("AGENT_RUN_EVENTS_PATH") or DEFAULT_EVENTS_PATH


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _is_fixture(event: Dict[str, Any]) -> bool:
    return "fixture" in str(event.get("source") or "").lower() or event.get("model") == "fixture-model"


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def iter_model_calls(
    since: datetime,
    until: Optional[datetime] = None,
    path: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield non-fixture model_call events with since <= timestamp <= until."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    try:
        fh = open(events_path(path), "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            if '"model_call"' not in line:  # cheap prefilter before json parse
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict) or event.get("event_type") != "model_call":
                continue
            if _is_fixture(event):
                continue
            ts = _parse_ts(event.get("timestamp"))
            if ts is None or ts < since or (until is not None and ts > until):
                continue
            yield event


def aggregate_routing(
    days: float = 7,
    path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Group by (model, agent_id/lane_id, status).

    Rows: model_used, agent_type, status, count, avg_latency (ms), avg_tokens,
    sorted by count desc. avg_* are 0.0 when no row carried the value.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    acc: Dict[Tuple[str, str, str], List[Any]] = defaultdict(lambda: [0, 0.0, 0, 0.0, 0])
    for ev in iter_model_calls(since, now, path):
        key = (
            str(ev.get("model") or "unknown"),
            str(ev.get("agent_id") or ev.get("lane_id") or "unknown"),
            str(ev.get("status") or "unknown"),
        )
        slot = acc[key]
        slot[0] += 1
        lat = _num(ev.get("duration_ms"))
        if lat is not None:
            slot[1] += lat
            slot[2] += 1
        tokens = ev.get("tokens")
        tot = _num(tokens.get("total")) if isinstance(tokens, dict) else None
        if tot is not None:
            slot[3] += tot
            slot[4] += 1
    rows = [
        {
            "model_used": m,
            "agent_type": a,
            "status": s,
            "count": v[0],
            "avg_latency": v[1] / v[2] if v[2] else 0.0,
            "avg_tokens": v[3] / v[4] if v[4] else 0.0,
        }
        for (m, a, s), v in acc.items()
    ]
    rows.sort(key=lambda r: (-r["count"], r["model_used"], r["agent_type"], r["status"]))
    return rows


def success_rate(
    window_hours: float = 24,
    path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """Percent (0-100) of terminal model calls that succeeded; None if no data."""
    now = now or datetime.now(timezone.utc)
    total = ok = 0
    for ev in iter_model_calls(now - timedelta(hours=window_hours), now, path):
        status = str(ev.get("status") or "").lower()
        if status in NON_TERMINAL_STATUSES:
            continue
        total += 1
        ok += status in SUCCESS_STATUSES
    return (ok / total) * 100.0 if total else None


def avg_latency_ms(
    window_hours: float = 24,
    path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """Mean duration_ms of successful model calls; None if no data."""
    now = now or datetime.now(timezone.utc)
    total = n = 0.0
    for ev in iter_model_calls(now - timedelta(hours=window_hours), now, path):
        if str(ev.get("status") or "").lower() not in SUCCESS_STATUSES:
            continue
        lat = _num(ev.get("duration_ms"))
        if lat is not None:
            total += lat
            n += 1
    return total / n if n else None


def switchboard_decisions(
    days: float = 7,
    repo_root: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Secondary source: switchboard local-vs-remote routing decisions."""
    root = Path(repo_root or os.getenv("REPO_ROOT") or Path(__file__).resolve().parents[2])
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).timestamp()
    out: Dict[str, Any] = {"total": 0, "local": 0, "by_profile": {}}
    try:
        fh = open(root / ".agents" / "telemetry" / "routing-decisions.jsonl", "r", encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            ts = _num(row.get("ts")) if isinstance(row, dict) else None
            if ts is None or ts < cutoff:
                continue
            out["total"] += 1
            out["local"] += bool(row.get("local"))
            prof = str(row.get("profile") or "unknown")
            out["by_profile"][prof] = out["by_profile"].get(prof, 0) + 1
    return out
