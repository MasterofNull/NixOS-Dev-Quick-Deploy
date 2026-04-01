#!/usr/bin/env python3
"""Regression checks for aq-report reliability interpretation."""

from __future__ import annotations

import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_aq_report():
    os.environ.setdefault("AI_STRICT_ENV", "false")
    spec = importlib.util.spec_from_loader(
        "aq_report_reliability_interpretation",
        SourceFileLoader("aq_report_reliability_interpretation", str(AQ_REPORT_PATH)),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load aq-report")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    aq_report = load_aq_report()

    entries = [
        {
            "tool_name": "store_agent_memory",
            "outcome": "client_error",
            "latency_ms": 10.0,
            "metadata": {"http_status": 400},
        },
        {
            "tool_name": "store_agent_memory",
            "outcome": "client_error",
            "latency_ms": 11.0,
            "metadata": {"http_status": 422},
        },
        {
            "tool_name": "store_agent_memory",
            "outcome": "success",
            "latency_ms": 18.0,
            "metadata": {"http_status": 200},
        },
        {
            "tool_name": "store_agent_memory",
            "outcome": "success",
            "latency_ms": 21.0,
            "metadata": {"http_status": 200},
        },
        {
            "tool_name": "store_agent_memory",
            "outcome": "success",
            "latency_ms": 19.0,
            "metadata": {"http_status": 200},
        },
    ]
    recent_stats = aq_report.aggregate_tool_audit(entries)
    memory_recent = recent_stats["store_agent_memory"]
    interpretation = aq_report._tool_reliability_interpretation(
        "store_agent_memory",
        memory_recent,
        memory_recent,
    )
    assert_true(interpretation["status"] == "caller_input_only", "expected caller-input-only interpretation")
    assert_true(interpretation["active_incident"] is False, "caller misuse should not be active incident")

    snapshot = aq_report.recent_health_snapshot(recent_stats)
    assert_true(
        not any(item["tool"] == "store_agent_memory" for item in snapshot["flaky_tools"]),
        "caller-only memory-write noise should not appear as active flaky tool",
    )

    recommendations = aq_report.build_recommendations(
        recent_stats,
        {"available": True, "local_pct": 100.0},
        {"available": False},
        {"available": False},
        [],
        recent_tool_stats=recent_stats,
    )
    joined = "\n".join(recommendations)
    assert_true("store_agent_memory" not in joined, "caller-only memory-write noise should not produce active incident recommendation")

    historical_stats = {
        "store_agent_memory": {
            "calls": 5,
            "actionable_calls": 5,
            "observed_calls": 5,
            "p50_ms": 30.0,
            "p95_ms": 50.0,
            "success_pct": 60.0,
            "error_count": 2,
            "client_error_count": 0,
            "unknown_count": 0,
            "recovered_fallback_count": 0,
        }
    }
    watch = aq_report.historical_watchlist(historical_stats, {})
    historical = next(item for item in watch["flaky_tools"] if item["tool"] == "store_agent_memory")
    assert_true(historical["active_incident"] is False, "historical-only memory-write debt should not be marked active")
    assert_true(historical["reliability_status"] == "historical_backend_debt", "expected historical backend debt status")
    assert_true("historical backend memory-write debt" in historical["reliability_note"], "expected historical debt note")

    rendered = aq_report.format_text(
        since_label="1h",
        tool_stats=historical_stats,
        route={"available": True, "local_n": 5, "remote_n": 0, "local_pct": 100.0, "fallback_used": False},
        recent_route={"available": True, "local_n": 5, "remote_n": 0, "local_pct": 100.0, "window": "1h", "fallback_used": False},
        routing_windows={"available": False, "windows": {}},
        cache={"available": False},
        cache_prewarm={"available": False},
        eval_trend={"available": False},
        leaderboard=[],
        top_prompts=[],
        gaps=[],
        rag_posture_summary={"available": False},
        recent_health={"available": True, "window": "1h", "healthy": True, "slow_tools": [], "flaky_tools": []},
        continue_editor={"available": False},
        continue_editor_windows={"available": False, "windows": {}},
        shared_skill_registry={"available": False},
        delegated_prompt_failures={"available": False},
        delegated_prompt_failure_windows={"available": False},
        remote_profile_summary={"available": False},
        remote_profile_windows={"available": False},
        route_latency_decomposition={"available": False},
        retrieval_breadth={"available": False},
        retrieval_breadth_windows={"available": False},
        provider_fallbacks={"available": False, "window": "1h"},
        historical_watch=watch,
        recs=[],
    )
    assert_true("historical backend memory-write debt remains visible" in rendered, "expected historical note in text report")

    print("PASS: aq-report separates memory-write caller misuse from backend failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
