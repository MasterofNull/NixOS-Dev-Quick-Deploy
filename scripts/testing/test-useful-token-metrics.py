#!/usr/bin/env python3
"""Regression coverage for Phase 93.5 useful-token metrics in aq-report."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
os.environ.setdefault("AI_STRICT_ENV", "false")

import agent_run_events as _are


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


def test_no_data_when_file_absent() -> None:
    mod = _load_aq_report()
    mod.AGENT_RUN_EVENTS_PATH = Path("/nonexistent/agent-run-events.jsonl")
    result = mod.useful_token_metrics()
    assert_true(result["available"] is False, "available=False when file absent")
    assert_true(result["status"] == "no_data", "status=no_data when file absent")
    assert_true("reason" in result, "reason present")


def test_no_data_when_file_empty() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write("")
        tmp_path = fh.name
    mod.AGENT_RUN_EVENTS_PATH = Path(tmp_path)
    result = mod.useful_token_metrics()
    assert_true(result["available"] is False, "available=False for empty file")
    assert_true(result["status"] == "no_data", "status=no_data for empty file")
    Path(tmp_path).unlink(missing_ok=True)


def test_aggregates_token_events() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for i in range(3):
            ev = _are.make_event(
                "token_usage",
                source="test",
                run_id=f"run-{i}",
                tokens={
                    "input": 100,
                    "output": 200,
                    "context": 50,
                    "tool_output": 30,
                    "accepted_artifact": 180,
                    "rework": 20,
                    "total": 380,
                },
            )
            fh.write(json.dumps(ev) + "\n")
        tmp_path = fh.name
    mod.AGENT_RUN_EVENTS_PATH = Path(tmp_path)
    result = mod.useful_token_metrics()
    assert_true(result["available"] is True, "available=True with token events")
    assert_true(result["status"] == "ok", f"status=ok, got {result['status']}")
    assert_true(result["token_events"] == 3, "3 token events found")
    assert_true(result["total_tokens"] == 1140, f"total_tokens=1140, got {result['total_tokens']}")
    assert_true(result["accepted_artifact_tokens"] == 540, "accepted_artifact_tokens correct")
    assert_true(result["rework_tokens"] == 60, "rework_tokens correct")
    assert_true(result["useful_ratio"] is not None, "useful_ratio computed")
    assert_true(0 < result["useful_ratio"] <= 1.0, "useful_ratio in valid range")
    Path(tmp_path).unlink(missing_ok=True)


def test_per_run_breakdown() -> None:
    mod = _load_aq_report()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for run_id in ("run-a", "run-b"):
            ev = _are.make_event(
                "token_usage",
                source="test",
                run_id=run_id,
                tokens={"input": 50, "output": 100, "accepted_artifact": 90, "total": 200},
            )
            fh.write(json.dumps(ev) + "\n")
        tmp_path = fh.name
    mod.AGENT_RUN_EVENTS_PATH = Path(tmp_path)
    result = mod.useful_token_metrics()
    assert_true(result["runs"] == 2, f"2 distinct runs, got {result['runs']}")
    assert_true(len(result["per_run"]) == 2, "per_run has 2 entries")
    Path(tmp_path).unlink(missing_ok=True)


def test_format_json_includes_useful_tokens() -> None:
    mod = _load_aq_report()
    dummy = {"available": True, "status": "ok", "useful_ratio": 0.72}
    result_json = mod.format_json(
        "7d",
        {}, {}, {}, {}, {}, {}, {}, [], [], [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
        [],
        useful_tokens=dummy,
    )
    doc = json.loads(result_json)
    assert_true("useful_tokens" in doc, "useful_tokens key present in format_json output")
    assert_true(doc["useful_tokens"]["useful_ratio"] == 0.72, "useful_ratio value preserved")


def test_format_json_includes_validation_health() -> None:
    mod = _load_aq_report()
    dummy_vh = {"available": True, "status": "pass", "checks_ran": 5, "checks_passed": 5}
    result_json = mod.format_json(
        "7d",
        {}, {}, {}, {}, {}, {}, {}, [], [], [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
        [],
        validation_health_summary=dummy_vh,
    )
    doc = json.loads(result_json)
    assert_true("validation_health" in doc, "validation_health key present in format_json output")
    assert_true(doc["validation_health"]["checks_ran"] == 5, "checks_ran preserved")


if __name__ == "__main__":
    tests = [
        ("no_data when file absent", test_no_data_when_file_absent),
        ("no_data when file empty", test_no_data_when_file_empty),
        ("aggregates token events", test_aggregates_token_events),
        ("per-run breakdown", test_per_run_breakdown),
        ("format_json includes useful_tokens", test_format_json_includes_useful_tokens),
        ("format_json includes validation_health", test_format_json_includes_validation_health),
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
