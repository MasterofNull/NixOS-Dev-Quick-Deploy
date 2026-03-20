#!/usr/bin/env python3
"""
Static regression checks for A2A insights dashboard UI wiring.
"""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'id="a2aReadinessGrid"',
    'id="a2aMethodList"',
    'function loadA2AReadiness()',
    '/api/insights/workflows/a2a-readiness',
    "Analytics + A2A",
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing A2A insights dashboard UI snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: A2A insights dashboard UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
