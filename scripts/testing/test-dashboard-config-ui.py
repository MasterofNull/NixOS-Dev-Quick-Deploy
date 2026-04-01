#!/usr/bin/env python3
"""Static regression checks for dashboard control-plane configuration UI."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'id="configScopeNotice"',
    'id="liveHarnessConfig"',
    'id="workflowBlueprintConfig"',
    'id="controlSurfaceFindings"',
    'function renderControlPlaneLists(snapshot)',
    'Live AI Harness Runtime',
    'Workflow Blueprint Orchestration (Redeploy Required)',
    'Dashboard API Runtime Controls (Local Only)',
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing dashboard config control-plane UI snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: dashboard config control-plane UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
