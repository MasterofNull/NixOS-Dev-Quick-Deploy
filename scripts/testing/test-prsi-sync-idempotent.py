#!/usr/bin/env python3
"""Hermetic: an idle PRSI incident sync must not rewrite the action queue; a real change must."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_TMP = tempfile.TemporaryDirectory(prefix="prsi-sync-idem-")
tmp = Path(_TMP.name)
os.environ["PRSI_INCIDENTS_FILE"] = str(tmp / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi_sync_idem", ROOT / "scripts/automation/prsi-orchestrator.py")
assert spec and spec.loader
prsi: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)

incidents = tmp / "rsi-incidents.json"


def write_incident(count: int, extra: bool = False) -> None:
    rows = {"fp-1": {"id": "rsi-incident-1", "status": "open", "severity": "high", "count": count,
                     "path": "scripts/testing/test-prsi-sync-idempotent.py"}}
    if extra:
        rows["fp-2"] = {"id": "rsi-incident-2", "status": "open", "severity": "high", "count": 1,
                        "path": "scripts/testing/test-prsi-sync-idempotent.py"}
    incidents.write_text(json.dumps({"version": 1, "incidents": rows}), encoding="utf-8")


queue = tmp / "action-queue.json"
prsi._RSI_INCIDENTS = incidents
prsi.QUEUE_PATH = queue
prsi.PRSI_STATE_PATH = tmp / "runtime-state.json"
prsi.ACTIONS_LOG_PATH = tmp / "prsi-actions.jsonl"

write_incident(1)
assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
first = queue.read_bytes()
first_mtime = queue.stat().st_mtime_ns
time.sleep(0.05)

for _ in range(2):
    assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
assert queue.read_bytes() == first, "idle sync changed queue bytes"
assert queue.stat().st_mtime_ns == first_mtime, "idle sync rewrote the queue (mtime moved)"
events = [json.loads(line) for line in prsi.ACTIONS_LOG_PATH.read_text().splitlines() if '"sync"' in line]
assert events[-1]["added"] == 0 and events[-1]["updated"] == 0, events[-1]
print("PASS: idle sync leaves queue bytes and mtime unchanged, updated=0")

write_incident(1, extra=True)
assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
assert queue.read_bytes() != first and queue.stat().st_mtime_ns > first_mtime
assert len(json.loads(queue.read_text())["actions"]) == 2
print("PASS: a new incident still writes the queue")

write_incident(5, extra=True)
mid = queue.read_bytes()
assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
rows = {r["raw_action"]["incident_id"]: r for r in json.loads(queue.read_text())["actions"]}
assert queue.read_bytes() != mid and rows["rsi-incident-1"]["seen_count"] == 2
print("PASS: a changed incident still updates its row")

# Presence signal: an unchanged but still-present row keeps last_seen_at fresh (aq-prsi-review
# staleness reads it), refreshed at most once per day so idle syncs stay byte-stable.
stale_sentinel = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
data = json.loads(queue.read_text())
for r in data["actions"]:
    r["last_seen_at"] = stale_sentinel
queue.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
fresh = {r["id"]: r for r in json.loads(queue.read_text())["actions"]}
assert all(r["last_seen_at"] != stale_sentinel for r in fresh.values()), "stale last_seen_at not refreshed"
assert all(datetime.now(timezone.utc) - datetime.fromisoformat(r["last_seen_at"]) < timedelta(minutes=5) for r in fresh.values())
settled = queue.read_bytes()
assert prsi.cmd_sync(Namespace(since="1d"), incidents_only=True) == 0
assert queue.read_bytes() == settled, "fresh last_seen_at must not trigger a rewrite"
print("PASS: last_seen_at refreshed once per day for unchanged rows, then stable")
