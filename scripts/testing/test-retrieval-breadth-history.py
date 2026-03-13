#!/usr/bin/env python3
"""Targeted checks for retrieval-breadth multi-window reporting."""

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
    entries = [
        {
            "timestamp": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "success",
            "metadata": {
                "retrieval_profile": "continuation",
                "retrieval_collection_count": 2,
            },
        },
        {
            "timestamp": (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "success",
            "metadata": {
                "retrieval_profile": "broad",
                "retrieval_collection_count": 5,
            },
        },
        {
            "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "success",
            "metadata": {
                "retrieval_profile": "broad",
                "retrieval_collection_count": 7,
            },
        },
    ]

    recent = aq_report.route_retrieval_breadth(entries[:1])
    assert_true(recent.get("avg_collection_count") == 2.0, "expected avg_collection_count=2.0")

    windows = aq_report.route_retrieval_breadth_windows(
        entries,
        now=now,
        report_since=now - timedelta(days=7),
    )
    assert_true(windows.get("available") is True, "expected retrieval breadth windows availability")
    one_h = (windows.get("windows") or {}).get("1h", {})
    twenty_four = (windows.get("windows") or {}).get("24h", {})
    seven_d = (windows.get("windows") or {}).get("7d", {})
    assert_true(one_h.get("avg_collection_count") == 2.0, "expected 1h avg=2.0")
    assert_true(twenty_four.get("avg_collection_count") == 3.5, "expected 24h avg=3.5")
    assert_true(round(float(seven_d.get("avg_collection_count") or 0.0), 2) == 4.67, "expected 7d avg=4.67")
    assert_true((seven_d.get("top_profiles") or [])[0][0] == "broad", "expected broad top profile in 7d window")

    print("PASS: retrieval breadth multi-window reporting works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
