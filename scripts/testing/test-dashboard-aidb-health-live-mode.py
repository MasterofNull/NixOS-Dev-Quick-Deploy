#!/usr/bin/env python3
"""Static regression checks for live-mode AIDB health fetching."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    required = [
        "async function fetchAidbDetailedHealth()",
        "if (DASHBOARD_DEMO_MODE) {",
        "fetch(`${FASTAPI_BASE}/api/aidb/health/detailed`, { cache: 'no-store' })",
    ]
    missing = [snippet for snippet in required if snippet not in text]
    if missing:
        print("Missing live-mode AIDB health fetch snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1

    forbidden = "if (!DASHBOARD_DEMO_MODE) {"
    if forbidden in text[text.index("async function fetchAidbDetailedHealth()"):text.index("async function fetchHarnessOverview()")]:
        print("AIDB detailed health fetch still uses inverted live/demo gating", file=sys.stderr)
        return 1

    print("PASS: dashboard AIDB health fetch is enabled in live mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
