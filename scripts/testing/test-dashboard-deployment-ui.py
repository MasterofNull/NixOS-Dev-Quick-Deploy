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
    'id="deploymentSearchMode"',
    'id="deploymentSearchStatusGrid"',
    'id="deploymentSearchStatusList"',
    '<option value="natural">Natural Language</option>',
    '<option value="auto">Auto Route</option>',
    'id="deploymentGraphSummary"',
    'id="deploymentGraphList"',
    'id="deploymentGraphView"',
    'id="deploymentGraphFocus"',
    'id="deploymentGraphViewState"',
    'id="deploymentGraphFocusMatches"',
    'id="deploymentGraphClusters"',
    'id="deploymentGraphRootCluster"',
    'id="deploymentGraphRankedClusters"',
    'id="deploymentGraphCauseChain"',
    '<option value="causality">Causality</option>',
    'why related',
    'cluster summary',
    'similar failure family',
    'score ${item.score} / count ${item.count}',
    'cluster score breakdown',
    'ranked cause factors',
    'cluster evidence',
    'query analysis',
    'result.explanation?.summary',
    '/api/deployments/search/context?query=${encodeURIComponent(query)}&limit=8&mode=${encodeURIComponent(mode)}',
    'sources=d:${searchMeta.sources.deployment ?? 0}/l:${searchMeta.sources.logs ?? 0}/c:${searchMeta.sources.config ?? 0}/code:${searchMeta.sources.code ?? 0}',
    'function loadDeploymentOps()',
    'function connectDeploymentWebSocket()',
    'function searchDeploymentHistory()',
    'function loadDeploymentSearchStatus()',
    'function loadDeploymentGraph()',
    'function executeDeploymentRollback()',
    '/api/deployments/history?limit=12&include_timeline_preview=true',
    '/api/deployments/search?query=${encodeURIComponent(query)}&limit=8&mode=${encodeURIComponent(mode)}',
    '/api/deployments/search/status?recent_limit=6',
    "/api/deployments/graph?${params.toString()}",
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
