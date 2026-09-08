#!/usr/bin/env python3
"""Auto-fold an approved frontier candidate into a plan's tracker (FA-3).

When a backlog candidate is approved/scheduled, it should become a real, projected
plan slice — not a note someone re-types. This turns the candidate into a tracker
item (goal from its proposed_slice, validation_goal from its acceptance_goal) and
appends it, idempotently, to the target plan's tracker.json. Status stays PROJECTED
from git (anti-gaming); we only add the editorial item.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Only a finding that PASSED multi-expert debate (accepted), or is already being
# implemented (scheduled), may fold into a plan. A merely-proposed or in-review
# finding is never auto-folded — the debate gate comes first.
FOLDABLE_STATUSES = ("accepted", "scheduled")


def _marker(candidate_id: str) -> str:
    return f"[frontier-fold {candidate_id}]"


def slice_from_candidate(candidate: dict[str, Any], phase_id: str) -> dict[str, Any]:
    cid = candidate.get("id", "fe-unknown")
    return {
        "id": f"frontier-{cid.lower()}",
        "name": (candidate.get("technique") or cid)[:64],
        "phase": phase_id,
        "kind": "slice",
        "goal": candidate.get("proposed_slice") or candidate.get("claim") or "",
        "validation_goal": candidate.get("acceptance_goal") or "benchmark-first; measured before/after",
        "deps": [],
        "editorial_note": f"{_marker(cid)} folded from frontier backlog; verdict {candidate.get('verdict')}; "
                          f"source: {candidate.get('source', '')[:120]}",
    }


def already_folded(tracker: dict[str, Any], candidate_id: str) -> bool:
    m = _marker(candidate_id)
    sid = f"frontier-{candidate_id.lower()}"
    return any(it.get("id") == sid or m in (it.get("editorial_note") or "")
               for it in tracker.get("items", []))


def fold_candidate(tracker: dict[str, Any], candidate: dict[str, Any], *,
                   phase_id: str | None = None) -> tuple[dict[str, Any], bool, str]:
    """Return (tracker, added, message). Idempotent; refuses non-foldable statuses."""
    status = candidate.get("status")
    if status not in FOLDABLE_STATUSES:
        return tracker, False, (f"candidate status '{status}' is not foldable — route it through "
                                "multi-expert debate to 'accepted' first (aq-frontier review/verdict/accept)")
    if already_folded(tracker, candidate.get("id", "")):
        return tracker, False, "already folded (idempotent no-op)"
    phases = tracker.get("phases") or []
    pid = phase_id or (phases[0]["id"] if phases else None)
    if pid is None:
        return tracker, False, "target tracker has no phases to attach the slice to"
    if not any(p.get("id") == pid for p in phases):
        return tracker, False, f"phase '{pid}' not in target tracker"
    tracker.setdefault("items", []).append(slice_from_candidate(candidate, pid))
    return tracker, True, f"folded {candidate.get('id')} -> slice frontier-{candidate.get('id','').lower()}"


def load_tracker(plan_dir: str | os.PathLike) -> dict[str, Any]:
    return json.loads((Path(plan_dir) / "tracker.json").read_text(encoding="utf-8"))


def write_tracker(plan_dir: str | os.PathLike, tracker: dict[str, Any]) -> None:
    (Path(plan_dir) / "tracker.json").write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")
