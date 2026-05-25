#!/usr/bin/env python3
"""Focused CI guard for new ai-stack logical orphan candidates."""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "ai" / "aq-integrity-scan"
BASELINE = REPO_ROOT / "config" / "aq-integrity-logical-orphans.json"


def validate_baseline_metadata() -> int:
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"failed to read logical orphan baseline: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for entry in baseline.get("entries", []):
        path = entry.get("path")
        if not path:
            failures.append("baseline entry missing path")
            continue
        if not (REPO_ROOT / path).exists():
            failures.append(f"baseline path no longer exists: {path}")

        classification = entry.get("classification")
        action = entry.get("action")
        rationale = entry.get("rationale", "")
        if classification == "referenced_entrypoint_candidate" and action == "keep":
            failures.append(
                f"referenced entrypoint cannot be blanket keep without coverage proof: {path}"
            )
        if rationale == "Verified entrypoint referenced externally in baseline rationale.":
            failures.append(f"generic baseline rationale hides required evidence: {path}")

    if failures:
        for failure in failures[:20]:
            print(f"LOGICAL BASELINE: {failure}", file=sys.stderr)
        if len(failures) > 20:
            print(f"... {len(failures) - 20} more logical baseline failures", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    baseline_status = validate_baseline_metadata()
    if baseline_status != 0:
        return baseline_status

    proc = subprocess.run(
        [
            str(SCANNER),
            "--json",
            "--timeout-seconds",
            "18",
            "--max-files",
            "5000",
            "--max-logical-files",
            "1500",
            "--fail-on-new-logical",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=25,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode or 1

    counts = payload.get("meta", {}).get("finding_counts", {})
    if payload.get("meta", {}).get("truncated"):
        warnings = ", ".join(payload.get("meta", {}).get("warnings", []))
        print(f"aq-integrity logical baseline scan truncated: {warnings}", file=sys.stderr)
        return 3

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
