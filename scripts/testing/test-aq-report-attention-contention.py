#!/usr/bin/env python3
"""Regression coverage for Phase 93.14 attention queue contention telemetry in aq-report."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_aq_report():
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("aq_report", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _contention_event(ts: str, attempt_count: int = 2, duration_ms: float = 80.0, error_code: str = "EAGAIN") -> str:
    ev = {
        "event_type": "queue_lock_contention",
        "timestamp": ts,
        "details": {
            "attempt_count": attempt_count,
            "duration_ms": duration_ms,
            "error_code": error_code,
        },
    }
    return json.dumps(ev)


def test_no_data_when_file_absent() -> None:
    mod = _load_aq_report()
    mod._ATTENTION_TELEMETRY_PATH = Path("/nonexistent/hybrid-events.jsonl")
    result = mod.attention_contention_summary()
    assert_true(result["available"] is False, "available=False when file absent")
    assert_true(result["status"] == "no_data", f"status=no_data, got {result['status']}")
    assert_true("reason" in result, "reason key present")


def test_ok_with_zero_when_no_contention_events() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        # Write a different event type — should be ignored
        fh.write(json.dumps({"event_type": "tool_call", "timestamp": "2026-06-01T10:00:00Z"}) + "\n")
        tmp_path = fh.name
    mod._ATTENTION_TELEMETRY_PATH = Path(tmp_path)
    result = mod.attention_contention_summary()
    assert_true(result["available"] is True, "available=True when file exists")
    assert_true(result["status"] == "ok", f"status=ok when no contention events, got {result['status']}")
    assert_true(result["total_contention_events"] == 0, "zero events")
    assert_true(result["exceeds_threshold"] is False, "threshold not exceeded with zero events")
    Path(tmp_path).unlink(missing_ok=True)


def test_ok_below_threshold() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        # 2 events spread over 1 hour → 2/hr, below 3/hr threshold
        fh.write(_contention_event("2026-06-01T10:00:00Z") + "\n")
        fh.write(_contention_event("2026-06-01T11:00:00Z") + "\n")
        tmp_path = fh.name
    mod._ATTENTION_TELEMETRY_PATH = Path(tmp_path)
    result = mod.attention_contention_summary()
    assert_true(result["available"] is True, "available=True with events")
    assert_true(result["total_contention_events"] == 2, f"2 events found, got {result['total_contention_events']}")
    assert_true(result["max_retries"] == 2, f"max_retries=2, got {result['max_retries']}")
    assert_true(result["status"] == "ok", f"status=ok when rate <= 3/hr, got {result['status']}")
    assert_true(result["exceeds_threshold"] is False, "exceeds_threshold=False below 3/hr")
    Path(tmp_path).unlink(missing_ok=True)


def test_warn_above_threshold() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        # 10 events in 1 hour → 10/hr, above 3/hr threshold
        for i in range(10):
            fh.write(_contention_event(f"2026-06-01T10:0{i}:00Z") + "\n")
        tmp_path = fh.name
    mod._ATTENTION_TELEMETRY_PATH = Path(tmp_path)
    result = mod.attention_contention_summary()
    assert_true(result["status"] == "warn", f"status=warn when rate > 3/hr, got {result['status']}")
    assert_true(result["exceeds_threshold"] is True, "exceeds_threshold=True above 3/hr")
    assert_true(result["total_contention_events"] == 10, "10 events counted")
    assert_true(result["events_per_hour"] > 3.0, f"events_per_hour > 3.0, got {result['events_per_hour']}")
    Path(tmp_path).unlink(missing_ok=True)


def test_format_json_includes_attention_contention() -> None:
    mod = _load_aq_report()
    dummy = {
        "available": True,
        "status": "warn",
        "total_contention_events": 7,
        "exceeds_threshold": True,
        "events_per_hour": 4.2,
    }
    result_json = mod.format_json(
        "7d",
        {}, {}, {}, {}, {}, {}, {}, [], [], [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
        [],
        attention_contention_summary=dummy,
    )
    doc = json.loads(result_json)
    assert_true("attention_contention" in doc, "attention_contention key present in format_json output")
    assert_true(doc["attention_contention"]["total_contention_events"] == 7, "event count preserved")
    assert_true(doc["attention_contention"]["exceeds_threshold"] is True, "exceeds_threshold preserved")


if __name__ == "__main__":
    tests = [
        ("no_data when file absent", test_no_data_when_file_absent),
        ("ok with zero when no contention events", test_ok_with_zero_when_no_contention_events),
        ("ok below 3/hr threshold", test_ok_below_threshold),
        ("warn above 3/hr threshold", test_warn_above_threshold),
        ("format_json includes attention_contention", test_format_json_includes_attention_contention),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
