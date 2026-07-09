#!/usr/bin/env python3
"""Regression checks for ai-stack-health-monitor."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "scripts" / "health" / "ai-stack-health-monitor.py"


def load_monitor():
    spec = importlib.util.spec_from_file_location("ai_stack_health_monitor_under_test", MONITOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    monitor = load_monitor()

    failures = monitor.failed_checks({
        "tests": [
            {"id": "ok", "status": "PASS", "description": "healthy"},
            {"id": "bad", "status": "FAIL", "description": "broken"},
        ]
    })
    assert_true(len(failures) == 1 and failures[0]["id"] == "bad", "monitor should read current aq-qa tests schema")

    captured = {}

    def fake_run(cmd, *, env=None, capture_output=False, text=False, timeout=None):
        captured["cmd"] = cmd
        captured["env"] = dict(env or {})
        return subprocess.CompletedProcess(cmd, 0, stdout='{"tests":[]}', stderr="")

    original_run = monitor.subprocess.run
    try:
        monitor.subprocess.run = fake_run
        payload = monitor.run_aq_qa("0")
    finally:
        monitor.subprocess.run = original_run

    assert_true(payload["tests"] == [], "run_aq_qa should parse JSON output")
    assert_true(payload["_monitor_returncode"] == 0, "run_aq_qa should preserve subprocess return code")
    assert_true(captured["cmd"] == [sys.executable, str(monitor._HARNESS_RUNNER), "0", "--json"], "run_aq_qa should bypass shell launcher")
    for name in ("TMPDIR", "TEMP", "TMP"):
        assert_true(captured["env"].get(name) == str(monitor._TMPDIR), f"{name} should use repo-local writable tmp")
    assert_true(captured["env"].get("PATH", "").startswith(monitor._SYSTEM_BIN), "run_aq_qa should expose system bash/python tools")
    assert_true(monitor._TMPDIR.exists(), "run_aq_qa should create repo-local tmpdir")

    original_status_path = monitor._STATUS_PATH
    try:
        monitor._STATUS_PATH = ROOT / ".agents" / "tmp" / "test-health-monitor-status.json"
        monitor.write_status({"source": "test", "total_failures": 0})
        status = json.loads(monitor._STATUS_PATH.read_text(encoding="utf-8"))
        assert_true(status["source"] == "test", "write_status should persist JSON status")
        assert_true(status["total_failures"] == 0, "write_status should preserve counters")
    finally:
        monitor._STATUS_PATH = original_status_path

    print("PASS: ai-stack-health-monitor handles aq-qa JSON schema, TMPDIR, and status writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
