#!/usr/bin/env python3
"""Targeted checks for delegated prompt-failure multi-window reporting."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "delegation-feedback.jsonl"
        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["DELEGATION_FEEDBACK_LOG_PATH"] = str(feedback_path)
        aq_report = SourceFileLoader("aq_report_delegated_failure_hist", str(AQ_REPORT_PATH)).load_module()

        now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
        records = [
            {
                "timestamp": (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
                "failure_class": "empty_content",
                "selected_profile": "remote-free",
                "failure_stage": "provider_response",
                "fallback_applied": False,
                "salvage": {"has_useful_data": True},
            },
            {
                "timestamp": (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                "failure_class": "tool_call_without_final_text",
                "selected_profile": "remote-tool-calling",
                "failure_stage": "provider_response",
                "fallback_applied": True,
                "salvage": {"has_useful_data": True},
            },
            {
                "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                "failure_class": "rate_limited",
                "selected_profile": "remote-coding",
                "failure_stage": "provider_response",
                "fallback_applied": False,
                "salvage": {"has_useful_data": False},
            },
        ]
        feedback_path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")

        raw = aq_report.read_delegation_feedback(now - timedelta(days=7))
        windows = aq_report.delegated_prompt_failure_windows(raw, now=now, report_since=now - timedelta(days=7))
        assert_true(windows.get("available") is True, "expected delegated failure window availability")
        one_h = (windows.get("windows") or {}).get("1h", {})
        twenty_four = (windows.get("windows") or {}).get("24h", {})
        seven_d = (windows.get("windows") or {}).get("7d", {})
        assert_true(one_h.get("total_failures") == 1, "expected 1h failure count")
        assert_true(twenty_four.get("total_failures") == 2, "expected 24h failure count")
        assert_true(seven_d.get("total_failures") == 3, "expected 7d failure count")
        assert_true(one_h.get("salvageable_pct") == 100.0, "expected 1h salvageable pct")
        assert_true(twenty_four.get("salvageable_pct") == 100.0, "expected 24h salvageable pct")
        assert_true(round(float(seven_d.get("salvageable_pct") or 0.0), 1) == 66.7, "expected 7d salvageable pct")

        historical_records = [
            {
                "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                "failure_class": "provider_http_error",
                "selected_profile": "remote-free",
                "failure_stage": "provider_response",
                "fallback_applied": False,
                "salvage": {"has_useful_data": True},
            },
            {
                "timestamp": (now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
                "failure_class": "provider_request_error",
                "selected_profile": "remote-free",
                "failure_stage": "provider_response",
                "fallback_applied": False,
                "salvage": {"has_useful_data": True},
            },
        ]
        historical_raw = {"available": True, "source": "test", "entries": historical_records}
        historical_summary = aq_report.aggregate_delegation_feedback(historical_raw)
        historical_windows = aq_report.delegated_prompt_failure_windows(
            historical_raw,
            now=now,
            report_since=now - timedelta(days=7),
        )
        recs = aq_report.build_recommendations(
            {},
            {"available": True, "local_pct": 100.0},
            {"available": False},
            {"available": False},
            [],
            delegated_prompt_failures=historical_summary,
            delegated_prompt_failure_windows=historical_windows,
        )
        joined = "\n".join(recs)
        assert_true("historical only" in joined, "expected historical-only delegated failure recommendation")
        assert_true("salvage rate" not in joined, "historical failures should not emit active salvage guidance")
        actions = aq_report.build_structured_actions(
            {},
            {"available": True, "local_pct": 100.0},
            {"available": False},
            {"available": False},
            [],
            delegated_prompt_failures=historical_summary,
            delegated_prompt_failure_windows=historical_windows,
        )
        assert_true(
            not any(action.get("action") == "tighten_openrouter_delegation_contract" for action in actions),
            "historical-only failures should not emit active prompt-contract action",
        )

    print("PASS: delegated prompt-failure multi-window history reporting works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
