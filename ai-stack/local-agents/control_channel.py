#!/usr/bin/env python3
"""control_channel — per-task operator intervention queue for running agents.

First cut of the polling control channel: an operator appends messages to a per-task
queue file; a running agent loop (agent_executor) polls it between turns and injects the
messages into its conversation (or honors a cancel). This turns the ops window from
read-only monitoring into a two-way console without a PTY — it fits the headless model
because the agent pulls between turns rather than being pushed to.

Queue: .agents/delegation/control/<task_id>.jsonl  (one JSON message per line)
Message: {"ts","kind","text","from"}   kind in inject|cancel

Pure + dependency-free. Append is atomic (single write with O_APPEND). Poll is
cursor-based (line count consumed) so each message is delivered exactly once.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

_REPO = Path(__file__).resolve().parents[2]
_CONTROL_DIR = _REPO / ".agents" / "delegation" / "control"
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def control_path(task_id: str) -> Path:
    """Queue file for a task. Rejects unsafe ids (no path traversal)."""
    if not task_id or not _SAFE_ID.match(task_id):
        raise ValueError(f"unsafe task_id: {task_id!r}")
    return _CONTROL_DIR / f"{task_id}.jsonl"


def send(task_id: str, text: str, kind: str = "inject", from_: str = "operator") -> dict:
    """Append one control message to the task's queue. Returns the record written."""
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
        "text": text or "",
        "from": from_,
    }
    p = control_path(task_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:      # O_APPEND: atomic per-line
        fh.write(json.dumps(rec) + "\n")
    return rec


def poll(task_id: str, cursor: int = 0) -> Tuple[List[dict], int]:
    """Return (new_messages_since_cursor, new_cursor). Never raises — a broken queue
    yields no messages and an unchanged cursor so the agent loop is never disrupted."""
    try:
        p = control_path(task_id)
    except ValueError:
        return [], cursor
    if not p.exists():
        return [], cursor
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], cursor
    new = []
    for ln in lines[cursor:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            new.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return new, len(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: control_channel.py <task_id> <text> [--cancel]", file=sys.stderr)
        sys.exit(2)
    _kind = "cancel" if "--cancel" in sys.argv[3:] else "inject"
    r = send(sys.argv[1], sys.argv[2], kind=_kind)
    print(f"queued {r['kind']} -> {sys.argv[1]}")
