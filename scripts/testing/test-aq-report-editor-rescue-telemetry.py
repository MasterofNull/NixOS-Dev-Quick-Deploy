#!/usr/bin/env python3
"""Targeted checks for aq-report editor rescue telemetry windows."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aq-report-editor-rescue-") as tmpdir:
        root = Path(tmpdir)
        history_path = root / "editor-rescue-history.jsonl"
        now = datetime(2026, 5, 8, 16, 0, tzinfo=timezone.utc)
        records = [
            {
                "timestamp": "2026-05-08T15:10:00Z",
                "task": "VSCodium AI surfaces are freezing",
                "execute": True,
                "qa_available": True,
                "qa_failed": 1,
                "qa_failure_ids": ["0.5.2"],
                "repair_attempted": True,
                "repair_ok": True,
                "regenerate_requested": False,
                "final_ok": False,
                "state_budget_failed_ids": ["continue_hot_corpus"],
            },
            {
                "timestamp": "2026-05-08T15:20:00Z",
                "task": "VSCodium AI surfaces are freezing",
                "execute": True,
                "qa_available": True,
                "qa_failed": 0,
                "qa_failure_ids": [],
                "repair_attempted": True,
                "repair_ok": True,
                "regenerate_requested": True,
                "regenerate_ok": True,
                "final_ok": True,
                "state_budget_failed_ids": [],
            },
            {
                "timestamp": "2026-05-08T15:40:00Z",
                "task": "Continue context limit loop",
                "execute": False,
                "qa_available": True,
                "qa_failed": 1,
                "qa_failure_ids": ["0.5.7"],
                "repair_attempted": False,
                "repair_ok": None,
                "regenerate_requested": False,
                "final_ok": False,
                "state_budget_failed_ids": ["continue_hot_corpus"],
            },
        ]
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")

        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["AQ_EDITOR_RESCUE_HISTORY_PATH"] = str(history_path)
        aq_report = SourceFileLoader("aq_report_editor_rescue_telemetry", str(AQ_REPORT_PATH)).load_module()

        rescue_windows = aq_report.editor_rescue_windows(now=now, report_since=now.replace(hour=0, minute=0))
        window_1h = (rescue_windows.get("windows") or {}).get("1h") or {}
        assert_true(window_1h.get("samples") == 3, "expected all rescue samples in the 1h window")
        assert_true(window_1h.get("repair_ok_n") == 2, "expected repair success count to aggregate")
        assert_true(window_1h.get("regenerate_ok_n") == 1, "expected Continue regeneration success count to aggregate")
        assert_true(window_1h.get("qa_healthy_n") == 1, "expected QA healthy end-state count to aggregate")
        repeated = window_1h.get("repeated_tasks") or []
        assert_true(repeated and repeated[0].get("count") == 2, "expected repeated rescue task detection")
        qa_failures = window_1h.get("top_qa_failures") or []
        assert_true(any(item.get("id") == "0.5.2" for item in qa_failures), "expected top QA failure IDs in rescue summary")

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
                {"available": False},
                {"available": False, "windows": {}},
                rescue_windows,
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
        rescue_payload = payload.get("editor_rescue_windows") or {}
        assert_true(rescue_payload.get("available") is True, "expected rescue windows in aq-report JSON payload")

    print("PASS: aq-report summarizes editor rescue telemetry windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
