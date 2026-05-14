#!/usr/bin/env python3
"""Static regression checks for command center dashboard lens controls."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'class="command-lenses"',
    'class="command-deck"',
    'id="commandDeck"',
    'id="deckCpuValue"',
    'id="deckGpuValue"',
    'id="deckMemoryValue"',
    'id="deckDiskValue"',
    'id="deckNetworkValue"',
    'id="deckStackValue"',
    'id="deckLayerRail"',
    'id="deckAlertList"',
    'id="lensSummary"',
    'data-lens="overview"',
    'data-lens="stack"',
    'data-lens="operations"',
    'data-lens="intelligence"',
    'data-lens="security"',
    'data-lens="all"',
    "const DASHBOARD_LENS_DEFINITIONS",
    "const DASHBOARD_CARD_SEMANTICS",
    "function applyDashboardCardSemantics",
    "section.dataset.module",
    "section.dataset.criticality",
    "section.dataset.layer",
    "function applyDashboardLens",
    "function initializeDashboardLenses",
    "function updateCommandDeckMetrics",
    "function updateCommandDeckLayers",
    "function renderCommandDeckAlerts",
    "command-center-dashboard-lens",
    'id="section-agentic-readiness"',
    'id="section-security"',
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing command lens dashboard snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: command center dashboard lens UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
