#!/usr/bin/env python3
"""Focused CI guard for new ai-stack logical orphan candidates."""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "ai" / "aq-integrity-scan"


def main() -> int:
    proc = subprocess.run(
        [
            str(SCANNER),
            "--json",
            "--timeout-seconds",
            "10",
            "--max-files",
            "5000",
            "--max-logical-files",
            "1500",
            "--fail-on-new-logical",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode or 1

    counts = payload.get("meta", {}).get("finding_counts", {})
    new_items = payload.get("findings", {}).get("new_logical_orphans", [])
    print(
        "aq-integrity logical baseline: "
        f"{counts.get('logical_orphans', 0)} known, "
        f"{counts.get('new_logical_orphans', 0)} new"
    )
    if new_items:
        for item in new_items[:20]:
            print(f"NEW logical orphan: {item.get('path')} ({item.get('classification')})", file=sys.stderr)
        if len(new_items) > 20:
            print(f"... {len(new_items) - 20} more new logical orphan candidates", file=sys.stderr)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
