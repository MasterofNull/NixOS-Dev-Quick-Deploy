#!/usr/bin/env python3
"""
Static regression checks for the expanded AI insights dashboard UI.
"""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'id="queryComplexityGrid"',
    'id="structuredRecommendationsList"',
    'id="agentLessonsGrid"',
    'id="routingProfileList"',
    'id="workflowComplianceSummary"',
    'function loadQueryComplexityInsights()',
    'function loadStructuredRecommendations()',
    'function loadAgentLessonsInsights()',
    '/api/insights/queries/complexity',
    '/api/insights/actions/recommendations',
    '/api/insights/agents/lessons',
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing expanded AI insights dashboard UI snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: expanded AI insights dashboard UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
