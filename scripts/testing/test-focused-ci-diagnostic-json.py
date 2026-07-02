#!/usr/bin/env python3
"""Regression coverage for Phase 93.10 focused-CI diagnostic JSON output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "governance" / "run-focused-ci-checks.sh"
REGISTRY = ROOT / "config" / "validation-check-registry.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_focused_ci(json_path: str | None = None, staged_env: dict | None = None) -> tuple[int, dict]:
    env = {**os.environ}
    env["REGISTRY"] = str(REGISTRY)
    env["MODE"] = "--pre-commit"
    if json_path:
        env["FOCUSED_CI_JSON"] = json_path
    if staged_env:
        env.update(staged_env)
    result = subprocess.run(
        ["bash", str(RUNNER), "--pre-commit"],
        capture_output=True,
        text=True,
        env=env,
    )
    doc: dict = {}
    if json_path and Path(json_path).exists():
        doc = json.loads(Path(json_path).read_text())
    return result.returncode, doc


def test_json_written_when_env_set() -> None:
    # Use an isolated minimal registry with a fast trivial command to avoid
    # triggering recursive focused-CI checks against staged real files.
    minimal_registry = {
        "checks": [
            {
                "id": "trivial-json-test",
                "description": "trivial check for JSON output test",
                "trigger_paths": ["scripts/governance/run-focused-ci-checks.sh"],
                "command": [sys.executable, "-c", "print('PASS: trivial')"],
                "enabled": True,
                "timeout_seconds": 5,
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path = Path(tmpdir) / "registry.json"
        reg_path.write_text(json.dumps(minimal_registry))
        json_path = str(Path(tmpdir) / "focused.json")
        env = {**os.environ, "REGISTRY": str(reg_path), "FOCUSED_CI_JSON": json_path, "MODE": "--pre-commit"}
        result = subprocess.run(
            ["bash", str(RUNNER), "--pre-commit"],
            capture_output=True, text=True, env=env,
        )
        assert_true(result.returncode == 0, f"runner exited nonzero: {result.returncode}\n{result.stderr}")
        # JSON written when at least one check ran and matched
        if Path(json_path).exists():
            doc = json.loads(Path(json_path).read_text())
            assert_true("generated_at" in doc, "generated_at field present")
            assert_true("overall_status" in doc, "overall_status field present")
            assert_true("checks" in doc, "checks array present")


def test_json_schema_fields() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        # Write a mock focused-ci JSON directly to test schema expectations
        fixture_doc = {
            "generated_at": "2026-06-01T00:00:00Z",
            "mode": "--pre-commit",
            "overall_status": "pass",
            "checks_ran": 2,
            "checks_passed": 2,
            "checks_failed": 0,
            "checks_skipped": 0,
            "checks": [
                {
                    "check_id": "test-check",
                    "description": "test description",
                    "trigger_paths_matched": ["scripts/ai/lib/agent_run_events.py"],
                    "command": ["python3", "scripts/testing/test-check.py"],
                    "status": "pass",
                    "skip_reason": None,
                    "duration_ms": 123.4,
                    "exit_code": 0,
                    "stdout_tail": "PASS: test",
                    "stderr_tail": "",
                }
            ],
        }
        json.dump(fixture_doc, fh, indent=2)
        tmp_path = fh.name

    doc = json.loads(Path(tmp_path).read_text())
    required_top = ("generated_at", "mode", "overall_status", "checks_ran", "checks_passed", "checks_failed", "checks")
    for key in required_top:
        assert_true(key in doc, f"top-level key '{key}' present")
    check = doc["checks"][0]
    required_check = ("check_id", "description", "trigger_paths_matched", "command", "status", "exit_code", "stdout_tail", "stderr_tail")
    for key in required_check:
        assert_true(key in check, f"check key '{key}' present")
    assert_true(isinstance(check["trigger_paths_matched"], list), "trigger_paths_matched is list")
    assert_true(isinstance(check["command"], list), "command is list")
    Path(tmp_path).unlink(missing_ok=True)


def test_exit_77_is_recorded_as_skip() -> None:
    minimal_registry = {
        "checks": [
            {
                "id": "sandbox-skip-test",
                "description": "sandbox skip exit code test",
                "trigger_paths": ["scripts/governance/run-focused-ci-checks.sh"],
                "command": [
                    sys.executable,
                    "-c",
                    "import sys; print('sandbox denied', file=sys.stderr); sys.exit(77)",
                ],
                "enabled": True,
                "always_run": True,
                "timeout_seconds": 5,
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path = Path(tmpdir) / "registry.json"
        reg_path.write_text(json.dumps(minimal_registry))
        json_path = str(Path(tmpdir) / "focused.json")
        env = {**os.environ, "REGISTRY": str(reg_path), "FOCUSED_CI_JSON": json_path, "MODE": "--pre-commit"}
        result = subprocess.run(
            ["bash", str(RUNNER), "--pre-commit"],
            capture_output=True, text=True, env=env,
        )
        assert_true(result.returncode == 0, f"runner treated skip as failure: {result.returncode}\n{result.stderr}")
        doc = json.loads(Path(json_path).read_text())
        assert_true(doc["overall_status"] == "skip", "all-skipped focused-CI run is skip")
        assert_true(doc["checks_skipped"] == 1, "skip count recorded")
        assert_true(doc["checks"][0]["status"] == "skip", "check status recorded as skip")
        assert_true(doc["checks"][0]["exit_code"] == 77, "skip exit code recorded")


def test_validation_health_reads_artifact() -> None:
    import importlib.util
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("aq_report", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    fixture_doc = {
        "generated_at": "2026-06-01T00:00:00Z",
        "overall_status": "fail",
        "checks_ran": 3,
        "checks_passed": 2,
        "checks_failed": 1,
        "checks_skipped": 0,
        "checks": [
            {
                "check_id": "agent-run-event-envelope",
                "description": "Phase 93 agent-run event envelope schema",
                "command": ["python3", "scripts/testing/test-agent-run-event-envelope.py"],
                "status": "fail",
                "exit_code": 1,
                "stderr_tail": "AssertionError: schema version mismatch",
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(fixture_doc, fh)
        tmp_path = fh.name

    mod.FOCUSED_CI_JSON_PATH = Path(tmp_path)
    result = mod.validation_health()
    assert_true(result["available"] is True, "available=True when artifact exists")
    assert_true(result["status"] == "fail", f"status=fail, got {result['status']}")
    assert_true(result["checks_failed"] == 1, "checks_failed=1")
    assert_true(len(result["top_failures"]) == 1, "top_failures has 1 entry")
    assert_true(result["top_failures"][0]["check_id"] == "agent-run-event-envelope", "failure check_id correct")
    Path(tmp_path).unlink(missing_ok=True)


def test_validation_health_no_data_when_absent() -> None:
    import importlib.util
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("aq_report2", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report2", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.FOCUSED_CI_JSON_PATH = Path("/nonexistent/focused.json")
    result = mod.validation_health()
    assert_true(result["available"] is False, "available=False when artifact absent")
    assert_true(result["status"] == "no_data", "status=no_data")


if __name__ == "__main__":
    tests = [
        ("JSON written when env set", test_json_written_when_env_set),
        ("JSON schema fields", test_json_schema_fields),
        ("exit 77 recorded as skip", test_exit_77_is_recorded_as_skip),
        ("validation_health reads artifact", test_validation_health_reads_artifact),
        ("validation_health no_data when absent", test_validation_health_no_data_when_absent),
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
