#!/usr/bin/env python3
"""Regression checks for ai-stack-health-monitor."""

from __future__ import annotations

import contextlib
import io
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

    from attention_queue import AlertSpec

    accepted = []
    def validating_push(**spec):
        AlertSpec(**spec).validate()
        accepted.append(spec)

    original_push = monitor.push
    original_run_qa = monitor.run_aq_qa
    original_phases = monitor._PHASES
    original_write_status = monitor.write_status
    try:
        monitor.push = validating_push
        full_title = "x" * 243
        monitor.push_alert(source="test", severity="high", autonomy_boundary="human_gate",
                           title=full_title, detail="detail", proposed_action="inspect")
        assert_true(accepted[0]["title"] == "x" * 79 + "…", "243-character title should truncate")
        assert_true(full_title in accepted[0]["detail"], "full title should remain in detail")
        try:
            AlertSpec(source="test", severity="high", autonomy_boundary="human_gate",
                      title=full_title, detail="detail", proposed_action="inspect").validate()
        except ValueError:
            pass
        else:
            raise AssertionError("queue validation must remain strict")

        calls = []
        def reject_first(**spec):
            calls.append(spec)
            if len(calls) == 1:
                spec["severity"] = "invalid"
            return validating_push(**spec)

        monitor.push = reject_first
        monitor._PHASES = ["bad", "good"]
        monitor.run_aq_qa = lambda phase: {"error": full_title} if phase == "bad" else {
            "tests": [{"id": "bad", "status": "FAIL", "description": full_title}]}
        statuses = []
        monitor.write_status = statuses.append
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            assert_true(monitor.main() == 0, "invalid alert must not abort monitor")
        assert_true(len(calls) == 2 and len(accepted) == 2, "batch should queue the next valid alert")
        assert_true(all(len(item["title"]) <= 80 for item in calls), "both producers should bound titles")
        assert_true(full_title in accepted[-1]["detail"], "QA row detail should remain intact")
        assert_true("Skipping invalid alert" in stderr.getvalue(), "invalid alert should be logged")
        assert_true(statuses[0]["total_failures"] == 2, "status should record both failures")
    finally:
        monitor.push = original_push
        monitor.run_aq_qa = original_run_qa
        monitor._PHASES = original_phases
        monitor.write_status = original_write_status

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
    assert_true(captured["env"].get("PATH", "").startswith(f"{monitor._PYTHON_BIN}:{monitor._SYSTEM_BIN}"), "run_aq_qa should prefer service Python before system tools")
    assert_true(captured["env"].get("PYTHONDONTWRITEBYTECODE") == "1", "run_aq_qa should not write pyc files into the read-only repo")
    assert_true(captured["env"].get("PYTHONPYCACHEPREFIX") == str(monitor._PYTHONPYCACHEPREFIX), "run_aq_qa should redirect pycache writes")
    assert_true(captured["env"].get("CARGO_TARGET_DIR") == str(monitor._CARGO_TARGET_DIR), "run_aq_qa should redirect cargo target writes")
    assert_true(monitor._TMPDIR.exists(), "run_aq_qa should create repo-local tmpdir")
    assert_true(monitor._PYTHONPYCACHEPREFIX.exists(), "run_aq_qa should create pycache dir")
    assert_true(monitor._CARGO_TARGET_DIR.exists(), "run_aq_qa should create cargo target dir")

    original_status_path = monitor._STATUS_PATH
    try:
        monitor._STATUS_PATH = ROOT / ".agents" / "tmp" / "test-health-monitor-status.json"
        monitor.write_status({"source": "test", "total_failures": 0})
        status = json.loads(monitor._STATUS_PATH.read_text(encoding="utf-8"))
        assert_true(status["source"] == "test", "write_status should persist JSON status")
        assert_true(status["total_failures"] == 0, "write_status should preserve counters")
    finally:
        monitor._STATUS_PATH = original_status_path

    # aq-qa phase 0 takes its evidence lock in hybrid/telemetry; under
    # ProtectSystem=strict the unit must declare it writable (2026-10-02 EROFS).
    nix_src = (Path(__file__).resolve().parents[2] / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
    unit = nix_src.split("systemd.services.ai-stack-health-monitor = {", 1)[1].split("systemd.timers.ai-stack-health-monitor", 1)[0]
    assert_true('"${cfg.mcpServers.dataDir}/hybrid/telemetry"' in unit,
                "health monitor unit must allow writes to the QA evidence lock dir")

    # Verify configurable harness timeout is properly configured.
    assert_true(hasattr(monitor, "_HARNESS_TIMEOUT_S"),
                "monitor should define _HARNESS_TIMEOUT_S constant")
    assert_true(monitor._HARNESS_TIMEOUT_S >= 430,
                f"default _HARNESS_TIMEOUT_S ({monitor._HARNESS_TIMEOUT_S}s) must be >= 430s (measured 2.5x phase 0 time)")
    assert_true("HARNESS_TIMEOUT_S=430" in unit or "HARNESS_TIMEOUT_S" in unit,
                "health monitor unit serviceConfig must set HARNESS_TIMEOUT_S env var")
    assert_true("TimeoutStartSec" in unit and "490" in unit,
                "health monitor unit must set TimeoutStartSec >= 490s (harness timeout + margin)")
    assert_true("MemoryMax" in unit and "768M" in unit,
                "health monitor unit must set MemoryMax >= 768M (1.5x measured 504M peak RSS)")

    print("PASS: ai-stack-health-monitor handles aq-qa JSON schema, TMPDIR, status writes, evidence-lock path, and configurable timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
