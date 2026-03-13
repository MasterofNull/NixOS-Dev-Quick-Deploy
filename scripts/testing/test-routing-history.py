#!/usr/bin/env python3
"""Targeted checks for routing multi-window reporting."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
aq_report = SourceFileLoader("aq_report", str(AQ_REPORT_PATH)).load_module()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    aq_report.prom_query = lambda _query: None
    entries = [
        {
            "timestamp": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {"backend": "local"},
        },
        {
            "timestamp": (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {"backend": "remote"},
        },
        {
            "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {"backend": "remote"},
        },
    ]

    windows = aq_report.routing_split_windows(
        entries,
        now=now,
        report_since=now - timedelta(days=7),
    )
    assert_true(windows.get("available") is True, "expected routing windows availability")
    one_h = (windows.get("windows") or {}).get("1h", {})
    twenty_four = (windows.get("windows") or {}).get("24h", {})
    seven_d = (windows.get("windows") or {}).get("7d", {})
    assert_true(one_h.get("local_n") == 1 and one_h.get("remote_n") == 0, "expected 1h local-only routing")
    assert_true(twenty_four.get("local_n") == 1 and twenty_four.get("remote_n") == 1, "expected 24h mixed routing")
    assert_true(seven_d.get("local_n") == 1 and seven_d.get("remote_n") == 2, "expected 7d routing totals")

    print("PASS: routing multi-window reporting works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
