#!/usr/bin/env python3
"""One-time backfill for workflow sessions missing intent_contract.

Safety defaults:
- Dry-run by default (no writes)
- Atomic write on apply
- Timestamped backup before modification
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


DEFAULT_WORKFLOW_SESSIONS_PATH = Path(
    os.getenv("WORKFLOW_SESSIONS_PATH", "/var/lib/ai-stack/hybrid/workflow-sessions.json")
)


def _default_intent_contract(objective: str) -> Dict[str, Any]:
    text = (objective or "").strip()[:280] or "complete current workflow objective"
    return {
        "user_intent": text,
        "definition_of_done": "deliver validated results that satisfy the objective",
        "depth_expectation": "minimum",
        "spirit_constraints": [
            "follow declarative-first policy",
            "capture validation evidence for major actions",
        ],
        "no_early_exit_without": [
            "all requested checks completed",
            "known blockers documented with remediation",
        ],
        "anti_goals": [],
    }


def _load_sessions(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"workflow sessions file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected top-level object in {path}, got {type(raw).__name__}")
    return raw


def _backfill_sessions(data: Dict[str, Any]) -> Tuple[int, int]:
    total = 0
    changed = 0
    for _sid, session in data.items():
        if not isinstance(session, dict):
            continue
        total += 1
        if isinstance(session.get("intent_contract"), dict):
            continue
        objective = str(session.get("objective", "") or "")
        session["intent_contract"] = _default_intent_contract(objective)
        changed += 1
    return total, changed


def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            st = path.stat()
            os.chmod(tmp_path, st.st_mode)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing intent_contract in workflow sessions")
    parser.add_argument(
        "--sessions-path",
        default=str(DEFAULT_WORKFLOW_SESSIONS_PATH),
        help=f"Path to workflow-sessions.json (default: {DEFAULT_WORKFLOW_SESSIONS_PATH})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes in-place (default is dry-run)",
    )
    args = parser.parse_args()

    path = Path(args.sessions_path)
    try:
        sessions = _load_sessions(path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    total, changed = _backfill_sessions(sessions)
    mode = "apply" if args.apply else "dry-run"
    print(f"mode={mode}")
    print(f"sessions_path={path}")
    print(f"total_sessions={total}")
    print(f"missing_intent_contract={changed}")

    if changed == 0:
        print("No missing entries found. Nothing to do.")
        return 0

    if not args.apply:
        print("Dry-run only. Re-run with --apply to write changes.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    _write_atomic(path, sessions)

    print(f"backup_created={backup}")
    print("apply_status=ok")
    print(f"rollback=cp {backup} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
