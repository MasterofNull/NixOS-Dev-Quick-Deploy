#!/usr/bin/env python3
"""Targeted checks for delegated prompt failure trend classification and hints."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")

AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
AQ_REPORT_SPEC = importlib.util.spec_from_loader(
    "aq_report_delegate_trend",
    SourceFileLoader("aq_report_delegate_trend", str(AQ_REPORT_PATH)),
)
if AQ_REPORT_SPEC is None or AQ_REPORT_SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
aq_report = importlib.util.module_from_spec(AQ_REPORT_SPEC)
AQ_REPORT_SPEC.loader.exec_module(aq_report)

sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))
from hints_engine import HintsEngine  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _entry(ts: datetime, failure_class: str) -> dict:
    return {
        "timestamp": ts.isoformat().replace("+00:00", "Z"),
        "failure_class": failure_class,
        "selected_profile": "remote-free",
        "failure_stage": "response_contract",
        "task_excerpt": "bounded delegated smoke",
        "response_preview": "empty contract reply",
        "improvement_actions": ["tighten envelope"],
        "salvage": {"has_useful_data": False},
    }


def main() -> int:
    now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    entries = [
        _entry(now - timedelta(minutes=10), "empty_content"),
        _entry(now - timedelta(minutes=20), "empty_content"),
        _entry(now - timedelta(minutes=30), "tool_call_without_final_text"),
        _entry(now - timedelta(hours=3), "empty_content"),
        _entry(now - timedelta(hours=8), "empty_content"),
        _entry(now - timedelta(hours=12), "tool_call_without_final_text"),
    ]
    windows = aq_report.delegated_prompt_failure_windows(
        {"available": True, "source": "test", "entries": entries},
        now=now,
        report_since=now - timedelta(days=7),
    )
    trend = windows.get("trend") or {}
    assert_true(trend.get("status") == "worsening", "expected worsening delegated failure trend")
    assert_true(
        any("tighten delegated task envelopes" in action for action in (trend.get("actions") or [])),
        "expected delegated failure trend remediation action",
    )

    with tempfile.TemporaryDirectory(prefix="delegated-failure-trend-") as tmpdir:
        report_path = Path(tmpdir) / "latest-aq-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "delegated_prompt_failures": {
                        "available": True,
                        "total_failures": 6,
                        "top_failure_classes": [["empty_content", 4], ["tool_call_without_final_text", 2]],
                    },
                    "delegated_prompt_failure_windows": windows,
                }
            ),
            encoding="utf-8",
        )
        engine = HintsEngine(report_json_path=report_path)
        hints = engine._hints_from_latest_report("improve openrouter delegation prompts and sub-agent contracts", [])
        hint_ids = [item.id for item in hints]
        assert_true("runtime_delegation_prompt_contract" in hint_ids, "expected delegation prompt-contract hint")

    print("PASS: delegated prompt failure trend classification and hints work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
