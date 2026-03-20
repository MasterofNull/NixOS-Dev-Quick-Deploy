#!/usr/bin/env python3
"""
Static regression checks for deployment dashboard UI wiring.
"""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'id="section-deployments"',
    'id="deploymentHistoryList"',
    'id="deploymentTimeline"',
    'function loadDeploymentOps()',
    'function connectDeploymentWebSocket()',
    'function searchDeploymentHistory()',
    'function executeDeploymentRollback()',
    '/api/deployments/history?limit=12&include_timeline_preview=true',
    '/api/ws/deployments',
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing deployment dashboard UI snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: deployment dashboard UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
