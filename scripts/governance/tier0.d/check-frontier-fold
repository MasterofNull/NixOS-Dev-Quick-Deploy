#!/usr/bin/env python3
"""Tier0 extension: FA-3 orphan fold validation (Rule 19 fail-closed).

FA-3 (auto-fold) appends approved frontier candidates as slices to their target plan's
tracker.json. This check ensures every scheduled candidate:
 1. Has a target_plan field (the plan dir where it was folded)
 2. That plan's tracker.json actually exists
 3. That tracker contains the folded slice (id=frontier-{id} or marker in editorial_note)

Fails HARD on any orphan: scheduled candidate without target, or target doesn't exist,
or folded slice is missing (regression detection per Rule 19).

Environment variables:
  FRONTIER_REPO_ROOT: where to find the backlog and plans (default: derived from script path)
  CODE_REPO_ROOT: where to find the implementation modules (default: derived from script path)
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Derive repo roots
SCRIPT_PATH = Path(__file__).resolve()
CODE_REPO = Path(os.environ.get("CODE_REPO_ROOT", SCRIPT_PATH.parents[3])).resolve()
DATA_REPO = Path(os.environ.get("FRONTIER_REPO_ROOT", str(CODE_REPO))).resolve()

# Import from the CODE_REPO's scripts (always the real implementation)
sys.path.insert(0, str(CODE_REPO / "scripts" / "ai" / "lib"))
import frontier_backlog as fb
import frontier_fold as ff

# But read the backlog from DATA_REPO (the repo being checked, which might be a test repo)
STORE = str(DATA_REPO / fb.DEFAULT_STORE)

def _marker(candidate_id: str) -> str:
    """Match frontier_fold._marker()."""
    return f"[frontier-fold {candidate_id}]"

def is_folded(tracker: dict, candidate_id: str) -> bool:
    """Check if candidate is folded in this tracker (matches frontier_fold.already_folded)."""
    m = _marker(candidate_id)
    sid = f"frontier-{candidate_id.lower()}"
    return any(it.get("id") == sid or m in (it.get("editorial_note") or "")
               for it in tracker.get("items", []))

def main() -> int:
    """Load backlog, verify each scheduled candidate has a valid target plan with folded slice."""
    backlog = fb.load(STORE)
    scheduled = [b for b in backlog if b.get("status") == "scheduled"]

    if not scheduled:
        print("[tier0.d/check-frontier-fold] PASS: no scheduled backlog items")
        return 0

    failures: list[str] = []
    for cand in scheduled:
        cand_id = cand.get("id", "unknown")
        target_plan = cand.get("target_plan")

        # FAIL if no target_plan field
        if not target_plan:
            failures.append(f"{cand_id} is scheduled but has no target_plan field (required for scheduled)")
            continue

        # FAIL if target plan doesn't exist
        plan_dir = DATA_REPO / target_plan if not Path(target_plan).is_absolute() else Path(target_plan)
        tracker_path = plan_dir / "tracker.json"

        if not tracker_path.exists():
            failures.append(f"{cand_id} targets {target_plan}/tracker.json which does not exist (orphan fold)")
            continue

        # FAIL if tracker doesn't contain the folded slice
        try:
            tracker = ff.load_tracker(plan_dir)
            if not is_folded(tracker, cand_id):
                failures.append(
                    f"{cand_id} is scheduled with target {target_plan}, but the folded slice "
                    f"(id=frontier-{cand_id.lower()}) is not in that tracker (orphan slice)"
                )
        except Exception as e:
            failures.append(f"{cand_id} targets {target_plan}, but tracker.json is corrupt: {e}")

    if failures:
        print("[tier0.d/check-frontier-fold] FAIL: scheduled candidates with orphan targets:", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print(f"[tier0.d/check-frontier-fold] PASS: {len(scheduled)} scheduled item(s) have valid target plans with folded slices")
    return 0

raise SystemExit(main())
