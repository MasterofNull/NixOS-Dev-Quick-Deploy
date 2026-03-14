#!/usr/bin/env python3
"""Targeted checks for Continue/editor failure-category reporting."""

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
        history_path = Path(tmpdir) / "continue-editor-history.jsonl"
        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["CONTINUE_EDITOR_HISTORY_PATH"] = str(history_path)
        aq_report = SourceFileLoader("aq_report_continue_failcats", str(AQ_REPORT_PATH)).load_module()

        now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
        snapshot = {
            "available": True,
            "healthy": False,
            "total_checks": 6,
            "passed_n": 4,
            "failed_n": 2,
            "skipped_n": 0,
            "failure_categories": [["agent_flow", 1], ["switchboard_routing", 1]],
        }
        aq_report.append_continue_editor_snapshot(snapshot, timestamp=now - timedelta(minutes=30))

        windows = aq_report.continue_editor_windows(now=now, report_since=now - timedelta(days=7))
        one_h = (windows.get("windows") or {}).get("1h", {})
        assert_true(one_h.get("latest_failure_categories") == snapshot["failure_categories"], "expected latest failure categories in window summary")

        health = {
            "available": True,
            "healthy": False,
            "total_checks": 6,
            "passed_n": 4,
            "failed_n": 2,
            "skipped_n": 0,
            "checks": [
                {"id": "0.5.4", "description": "continue-local switchboard smoke", "status": "FAIL", "failure_category": "switchboard_routing"},
                {"id": "0.5.6", "description": "Continue/editor prompt to feedback smoke", "status": "FAIL", "failure_category": "agent_flow"},
            ],
            "failure_categories": [["agent_flow", 1], ["switchboard_routing", 1]],
            "top_failure_category": "agent_flow",
        }
        payload = json.loads(
            aq_report.format_json(
                "7d",
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                [],
                [],
                [],
                {},
                {},
                health,
                windows,
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                [],
            )
        )
        continue_editor = payload.get("continue_editor") or {}
        assert_true(continue_editor.get("top_failure_category") == "agent_flow", "expected top failure category in json payload")
        assert_true((payload.get("continue_editor_windows") or {}).get("windows", {}).get("1h", {}).get("latest_failure_categories") == snapshot["failure_categories"], "expected window latest failure categories in json payload")

    print("PASS: Continue/editor failure categories are reported and persisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
