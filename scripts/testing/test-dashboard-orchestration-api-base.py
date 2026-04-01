#!/usr/bin/env python3
"""Static regression checks for dashboard orchestration API base usage."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    required = [
        "fetch(`${FASTAPI_BASE}/api/aistack/orchestration/team/${encodeURIComponent(sessionId)}`)",
        "fetch(`${FASTAPI_BASE}/api/aistack/orchestration/arbiter/${encodeURIComponent(sessionId)}`)",
        "fetch(`${FASTAPI_BASE}/api/aistack/orchestration/evaluations/trends`)",
    ]
    missing = [snippet for snippet in required if snippet not in text]
    if missing:
        print("Missing FASTAPI_BASE orchestration fetch snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1

    forbidden = [
        "fetch(`/api/aistack/orchestration/team/${sessionId}`)",
        "fetch(`/api/aistack/orchestration/arbiter/${sessionId}`)",
        "fetch('/api/aistack/orchestration/evaluations/trends')",
    ]
    present_forbidden = [snippet for snippet in forbidden if snippet in text]
    if present_forbidden:
        print("Found same-origin orchestration fetches that bypass FASTAPI_BASE:", file=sys.stderr)
        for snippet in present_forbidden:
            print(f"  - {snippet}", file=sys.stderr)
        return 1

    print("PASS: dashboard orchestration uses FASTAPI_BASE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
