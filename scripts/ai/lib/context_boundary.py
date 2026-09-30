#!/usr/bin/env python3
"""Small, local context-boundary meter for post-tool and drop events.

The meter stores only numeric estimates and metadata.  It is advisory: the
parent model runtime owns native compaction, while this module prepares a
fresh-session handoff before that limit is reached.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_NATIVE_LIMIT = 50_000
DEFAULT_SAFE_RATIO = 0.80
DEFAULT_HARD_RATIO = 0.90


def estimate_tokens(chars: int) -> int:
    """Estimate tokens conservatively from UTF-8 character count."""
    return max(0, math.ceil(max(0, int(chars)) / 4))


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _session_id(value: str | None) -> str:
    return value or uuid.uuid4().hex


def _handoff(repo_root: Path, task: str, state: dict, source: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = repo_root / ".agent" / "collaboration" / f"HANDOFF-CONTEXT-{stamp}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"""# Context Boundary Handoff ({stamp})

Task: {task}
Trigger: {source}
Session: {state['session_id']}

The boundary meter estimates {state['estimated_tokens']:,} tokens across
{state['event_count']} boundary events.  Native limit: {state['native_limit']:,};
safe threshold: {state['safe_threshold']:,}; hard threshold: {state['hard_threshold']:,}.
Payload contents were intentionally not retained.

Resume with:

```bash
aq-context-manage summary --task {task!r} --json
aq-context-bootstrap --task {('resume ' + task)!r} --scope context-offload --format json
aq-context-card --card context-offload --level standard
```
"""
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return str(path)


def record_boundary(
    repo_root: str | Path,
    source: str,
    chars: int,
    *,
    tokens: int | None = None,
    task: str = "resume context work",
    session_id: str | None = None,
    native_limit: int = DEFAULT_NATIVE_LIMIT,
    safe_ratio: float = DEFAULT_SAFE_RATIO,
    hard_ratio: float = DEFAULT_HARD_RATIO,
    reset: bool = False,
    force: bool = False,
) -> dict:
    """Record one boundary event and return a compact status payload."""
    root = Path(repo_root)
    state_path = root / ".agent" / "collaboration" / "CONTEXT-BOUNDARY.json"
    previous = {}
    if state_path.exists() and not reset:
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
    sid = session_id or previous.get("session_id") or _session_id(None)
    if previous.get("session_id") != sid:
        previous = {}

    estimated = max(0, int(tokens)) if tokens is not None else estimate_tokens(chars)
    native_limit = max(1, int(native_limit))
    safe_threshold = max(1, int(native_limit * float(safe_ratio)))
    hard_threshold = max(safe_threshold, int(native_limit * float(hard_ratio)))
    total = int(previous.get("estimated_tokens", 0)) + estimated
    prior_status = previous.get("status", "ok")
    status = "ok"
    if force or total >= hard_threshold:
        status = "hard_limit"
    elif total >= safe_threshold:
        status = "handoff_recommended"

    state = {
        "session_id": sid,
        "estimated_tokens": total,
        "event_count": int(previous.get("event_count", 0)) + 1,
        "last_source": source,
        "native_limit": native_limit,
        "safe_threshold": safe_threshold,
        "hard_threshold": hard_threshold,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    handoff = previous.get("handoff")
    if status != "ok" and prior_status == "ok":
        handoff = _handoff(root, task, state, source)
    if handoff:
        state["handoff"] = handoff
    _atomic_json(state_path, state)
    return {
        "status": status,
        "source": source,
        "chars": max(0, int(chars)),
        "estimated_tokens": estimated,
        "cumulative_tokens": total,
        "event_count": state["event_count"],
        "safe_threshold": safe_threshold,
        "hard_threshold": hard_threshold,
        "handoff": handoff,
        "state_path": str(state_path),
    }
