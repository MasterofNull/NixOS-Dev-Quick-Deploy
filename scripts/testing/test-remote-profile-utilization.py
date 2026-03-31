#!/usr/bin/env python3
"""Targeted checks for delegated remote profile reporting and latency decomposition."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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
    now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    entries = [
        {
            "timestamp": (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "success",
            "latency_ms": 900.0,
            "metadata": {"backend": "local", "route_strategy": "hybrid"},
        },
        {
            "timestamp": (now - timedelta(minutes=9)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "client_error",
            "latency_ms": 40.0,
            "metadata": {"backend": "unknown", "route_strategy": "hybrid", "http_status": 400},
        },
        {
            "timestamp": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "error",
            "latency_ms": 1900.0,
            "metadata": {
                "backend": "local",
                "route_strategy": "hybrid",
                "fallback_reason": "remote_4xx_local_fallback",
                "http_status": 502,
            },
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

    windows = aq_report.remote_profile_utilization_windows(
        entries,
        now=now,
        report_since=now - timedelta(days=7),
    )
    assert_true(windows.get("available") is True, "expected remote profile windows availability")
    assert_true((windows.get("windows") or {}).get("1h", {}).get("total_calls") == 1, "expected one delegated call in 1h window")
    assert_true((windows.get("windows") or {}).get("24h", {}).get("total_calls") == 2, "expected two delegated calls in 24h window")
    assert_true((windows.get("windows") or {}).get("7d", {}).get("total_calls") == 3, "expected three delegated calls in 7d window")

    route_latency = aq_report.route_search_latency_decomposition(entries, window="7d")
    assert_true(route_latency.get("available") is True, "expected route latency decomposition availability")
    assert_true(route_latency.get("total_calls") == 3, "expected three route_search calls in latency decomposition")
    assert_true(route_latency.get("client_error_count") == 1, "expected one client-error route_search call")
    assert_true(route_latency.get("actionable_calls") == 2, "expected actionable calls to exclude 4xx/client errors")
    assert_true(route_latency.get("backend_valid_calls") == 2, "expected backend-valid calls to keep only local/remote rows")
    breakdown = route_latency.get("breakdown") or []
    assert_true(any(item.get("label") == "backend:local" for item in breakdown), "expected backend:local breakdown")
    assert_true(any(item.get("label") == "status:4xx" for item in breakdown), "expected 4xx breakdown")
    assert_true(
        any(item.get("label") == "fallback:remote_4xx_local_fallback" for item in breakdown),
        "expected fallback latency breakdown",
    )

    empty = aq_report.remote_profile_utilization([], window="1h")
    assert_true(empty.get("available") is False, "empty entries should report unavailable")

    print("PASS: delegated remote profile reporting and latency decomposition work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
