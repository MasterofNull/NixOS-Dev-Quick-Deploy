#!/usr/bin/env python3
"""Targeted checks for Continue/editor multi-window history reporting."""

from __future__ import annotations

import json
import os
import subprocess
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
        aq_report = SourceFileLoader("aq_report_continue_hist", str(AQ_REPORT_PATH)).load_module()

        now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
        records = [
            {"timestamp": (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"), "healthy": True, "total_checks": 6, "failed_n": 0},
            {"timestamp": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"), "healthy": False, "total_checks": 6, "failed_n": 1},
            {"timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"), "healthy": True, "total_checks": 6, "failed_n": 0},
        ]
        history_path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")

        windows = aq_report.continue_editor_windows(now=now, report_since=now - timedelta(days=7))
        assert_true(windows.get("available") is True, "expected continue editor history availability")
        one_h = (windows.get("windows") or {}).get("1h", {})
        twenty_four = (windows.get("windows") or {}).get("24h", {})
        seven_d = (windows.get("windows") or {}).get("7d", {})
        assert_true(one_h.get("healthy_pct") == 100.0, "expected 1h healthy pct")
        assert_true(twenty_four.get("healthy_pct") == 50.0, "expected 24h healthy pct")
        assert_true(round(float(seven_d.get("healthy_pct") or 0.0), 1) == 66.7, "expected 7d healthy pct")

        aq_report.append_continue_editor_snapshot(
            {"available": True, "healthy": True, "total_checks": 6, "passed_n": 6, "failed_n": 0, "skipped_n": 0},
            timestamp=now,
        )
        lines = history_path.read_text(encoding="utf-8").strip().splitlines()
        assert_true(len(lines) == 4, "expected append_continue_editor_snapshot to append one new record")

        def fake_run(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["aq-qa", "0", "--json"], timeout=35)

        aq_report.subprocess.run = fake_run
        fallback = aq_report.continue_editor_health()
        assert_true(fallback.get("available") is True, "expected history fallback to keep continue editor summary available")
        assert_true(fallback.get("fallback_source") == str(history_path), "expected fallback source to point at history file")
        assert_true("timed out" in str(fallback.get("warning", "")).lower(), "expected timeout warning in fallback health")
        assert_true(fallback.get("history_timestamp"), "expected fallback to expose history timestamp")

    print("PASS: Continue/editor multi-window history reporting works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
