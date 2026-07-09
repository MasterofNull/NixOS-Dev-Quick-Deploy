#!/usr/bin/env python3
"""resume_projector — render RESUME.json / PULSE.log from the A2A event log (WS2).

RESUME.json stops being directly written; it becomes a read-only PROJECTION of
`resume.update` events. Clobber dies because folding is PER FIELD:
  - two agents updating DIFFERENT fields -> both survive.
  - two agents updating the SAME field   -> latest ts wins, the other is
    preserved under agent_snapshots + visible in provenance (nothing is lost
    silently, which was the actual bug).

Backward-compatible: top-level current_objective / phase / todo_snapshot /
uncommitted_changes / resume_hint / written_at are still present exactly as
aq-resume expects. Added keys (_generated, _provenance, agent_snapshots) are
additive.

PULSE.log is rendered from `pulse.append` events (append-only already; here it
becomes reproducible from the log).

CLI:
    resume_projector.py resume   # (re)write RESUME.json from events
    resume_projector.py pulse    # (re)write PULSE.log from events
    resume_projector.py all
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import event_log  # noqa: E402

_COLLAB = _REPO_ROOT / ".agent" / "collaboration"


# Output paths are env-overridable and resolved at CALL time so tests (and
# sandboxed runs) NEVER touch the real session anchor. Learned the hard way: an
# early E2E test pointed the event log at a temp file but the projector still
# wrote the real RESUME.json, clobbering it — the very bug this slice kills.
def _resume_path() -> Path:
    return Path(os.environ.get("RESUME_JSON_PATH", str(_COLLAB / "RESUME.json")))


def _pulse_path() -> Path:
    return Path(os.environ.get("PULSE_LOG_PATH", str(_COLLAB / "PULSE.log")))

# Scalar fields fold as last-writer-wins; list/complex fields also LWW at the
# field level (the whole list is one agent's latest snapshot of that field).
_RESUME_FIELDS = (
    "current_objective", "phase", "todo_snapshot", "uncommitted_changes",
    "resume_hint", "previous_objective_preserved", "verification_commands",
    "session_commits",
)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def project_resume(events=None) -> dict[str, Any]:
    """Fold resume.update events into the RESUME projection dict."""
    events = events if events is not None else event_log.read_all()
    resume_events = sorted(
        (e for e in events if e.type == "resume.update"),
        key=lambda e: e.ts,
    )
    top: dict[str, Any] = {}
    provenance: dict[str, dict[str, Any]] = {}
    agent_snapshots: dict[str, dict[str, Any]] = {}
    last_ts = 0.0

    for ev in resume_events:
        last_ts = max(last_ts, ev.ts)
        snap = agent_snapshots.setdefault(ev.agent, {"updated_at": ev.ts, "fields": {}})
        snap["updated_at"] = ev.ts
        for field, value in ev.payload.items():
            if field not in _RESUME_FIELDS:
                continue
            # Per-field last-writer-wins by ts (append order breaks ties).
            prior = provenance.get(field)
            if prior is None or ev.ts >= prior["ts"]:
                top[field] = value
                provenance[field] = {"agent": ev.agent, "ts": ev.ts, "event_id": ev.event_id}
            snap["fields"][field] = value

    top["written_at"] = (
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_ts)) if last_ts else None
    )
    top["_generated"] = "projection of .agents/events/a2a-events.jsonl (resume.update) — do not edit by hand; emit events via aq-event"
    top["_provenance"] = provenance
    top["agent_snapshots"] = agent_snapshots
    return top


def write_resume(events=None) -> dict[str, Any]:
    proj = project_resume(events)
    _atomic_write(_resume_path(), json.dumps(proj, indent=2) + "\n")
    return proj


def project_pulse(events=None) -> str:
    events = events if events is not None else event_log.read_all()
    lines = []
    for ev in sorted((e for e in events if e.type == "pulse.append"), key=lambda e: e.ts):
        iso = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ev.ts))
        action = ev.payload.get("action", ev.type)
        scope = ev.subject or ev.payload.get("scope", "")
        outcome = ev.payload.get("outcome", "")
        tail = f": {scope}" if scope else ""
        tail += f" — {outcome}" if outcome else ""
        lines.append(f"[{iso}] [{ev.agent}] [{action}]{tail}")
    return "\n".join(lines) + ("\n" if lines else "")


def write_pulse(events=None) -> int:
    text = project_pulse(events)
    _atomic_write(_pulse_path(), text)
    return text.count("\n")


def emit_resume_update(agent: str, **fields: Any) -> None:
    """Convenience for agents/tools: emit a resume.update instead of writing the file."""
    payload = {k: v for k, v in fields.items() if k in _RESUME_FIELDS}
    event_log.emit(agent, "resume.update", payload=payload)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("resume", "all"):
        p = write_resume()
        print(f"RESUME.json <- {len(p.get('_provenance', {}))} fields from "
              f"{len(p.get('agent_snapshots', {}))} agent(s)")
    if cmd in ("pulse", "all"):
        n = write_pulse()
        print(f"PULSE.log <- {n} line(s)")
