#!/usr/bin/env python3
"""Static regression checks for testing dashboard UI wiring."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'href="#section-testing"',
    'id="section-testing"',
    'data-card-id="testing-ops"',
    'data-load-fn="loadTestingOps"',
    'id="testingOpsBadge"',
    'id="testingSuiteCount"',
    'id="testingExecutionCount"',
    'id="testingRunningCount"',
    'id="testingSelectedStatus"',
    'id="testingSuiteSelect"',
    'id="testingDryRun"',
    'id="testingConfirmLiveRun"',
    'id="testingExecutionSummary"',
    'id="testingSuiteList"',
    'id="testingExecutionList"',
    'function loadTestingOps()',
    'function loadTestingSuites()',
    'function loadTestingExecutions()',
    'function renderTestingUI()',
    'function submitTestingExecution()',
    'function selectTestingExecution(',
    '/api/testing/suites',
    '/api/testing/executions',
    '/api/testing/execute',
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing testing dashboard UI snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: testing dashboard UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
