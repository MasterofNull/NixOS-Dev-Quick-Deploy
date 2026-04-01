#!/usr/bin/env python3
"""Static regression checks for dashboard operator links using FASTAPI_BASE."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = REPO_ROOT / "dashboard.html"


REQUIRED_SNIPPETS = [
    'id="apiHealthLink"',
    'id="prometheusLink"',
    "function updateOperatorLinks()",
    "apiHealthLink.href = `${FASTAPI_BASE}/api/health`",
    "prometheusLink.href = `${FASTAPI_BASE}/metrics`",
    "updateOperatorLinks();",
]


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Missing operator link FASTAPI_BASE snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: dashboard operator links use FASTAPI_BASE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
