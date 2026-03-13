#!/usr/bin/env python3
"""Targeted checks for delegated remote profile utilization reporting."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
aq_report = SourceFileLoader("aq_report", str(AQ_REPORT_PATH)).load_module()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    entries = [
        {
            "tool_name": "ai_coordinator_delegate",
            "outcome": "ok",
            "metadata": {
                "selected_profile": "remote-free",
                "selected_runtime_id": "openrouter-free",
                "fallback_applied": False,
                "delegation_finalization_applied": False,
            },
        },
        {
            "tool_name": "ai_coordinator_delegate",
            "outcome": "ok",
            "metadata": {
                "selected_profile": "remote-tool-calling",
                "selected_runtime_id": "openrouter-tool-calling",
                "fallback_applied": False,
                "delegation_finalization_applied": True,
            },
        },
        {
            "tool_name": "ai_coordinator_delegate",
            "outcome": "error",
            "metadata": {
                "selected_profile": "remote-free",
                "selected_runtime_id": "openrouter-free",
                "fallback_applied": True,
                "delegation_finalization_applied": False,
            },
        },
        {
            "tool_name": "route_search",
            "outcome": "ok",
            "metadata": {"selected_profile": "remote-free"},
        },
    ]

    summary = aq_report.remote_profile_utilization(entries, window="1h")
    assert_true(summary.get("available") is True, "expected utilization summary availability")
    assert_true(summary.get("total_calls") == 3, "expected only delegate remote-profile calls to count")
    assert_true(summary.get("success_count") == 2, "expected success_count=2")
    assert_true(summary.get("fallback_applied") == 1, "expected one fallback")
    assert_true(summary.get("finalization_applied") == 1, "expected one finalization")
    top_profiles = summary.get("top_profiles") or []
    assert_true(top_profiles[0][0] == "remote-free", "expected remote-free as top profile")
    top_runtime_ids = summary.get("top_runtime_ids") or []
    assert_true(any(name == "openrouter-tool-calling" for name, _count in top_runtime_ids), "expected tool-calling runtime in summary")

    empty = aq_report.remote_profile_utilization([], window="1h")
    assert_true(empty.get("available") is False, "empty entries should report unavailable")

    print("PASS: delegated remote profile utilization reporting works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
