#!/usr/bin/env python3
"""Regression coverage for sandbox-denied host observer QA contract."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.testing.harness_qa.core import helpers


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_sandbox_denial_classifier() -> None:
    positives = [
        "Operation not permitted",
        "Failed to connect to bus: Permission denied",
        "cannot connect to socket at '/nix/var/nix/daemon-socket/socket': Operation not permitted",
        "Read-only file system",
    ]
    for text in positives:
        assert_true(helpers.is_sandbox_denied(text), f"expected sandbox denial: {text}")
    assert_true(not helpers.is_sandbox_denied("unit failed with exit-code"), "real unit failure is not sandbox denial")


def test_host_observer_url_defaults_to_dashboard_api() -> None:
    with mock.patch.dict(os.environ, {"DASHBOARD_API_URL": "http://127.0.0.1:9999"}, clear=False):
        assert_true(
            helpers.host_observer_url() == "http://127.0.0.1:9999/api/health/services/all",
            "default observer URL uses dashboard API",
        )


def test_host_observer_service_status_extracts_service() -> None:
    fixture = {
        "services": {
            "ai-hybrid-coordinator": {
                "status": "healthy",
                "systemd": {"active": True, "status": "active"},
            }
        }
    }
    with mock.patch.object(helpers, "http_json", return_value=fixture):
        observed = helpers.host_observer_service_status("ai-hybrid-coordinator")
    assert_true(observed is not None, "service record found")
    assert_true(observed["status"] == "healthy", "service status extracted")


def test_host_observer_service_status_reads_artifact() -> None:
    fixture = {
        "services": [
            {
                "name": "ai-hybrid-coordinator",
                "status": "active",
                "sub_state": "running",
                "pid": 123,
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "latest-system-state.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AQ_HOST_OBSERVER_FILE": str(path)}, clear=False):
            observed = helpers.host_observer_service_status("ai-hybrid-coordinator")
    assert_true(observed is not None, "artifact service record found")
    assert_true(observed["status"] == "healthy", "active artifact service normalizes to healthy")
    assert_true(observed["systemd"]["active"] is True, "artifact systemd active flag set")


def test_host_observer_service_status_handles_missing_surface() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        missing = str(Path(tmpdir) / "missing.json")
        env = {"AQ_HOST_OBSERVER_FILE": missing}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(helpers, "http_json", return_value={"pending": True}):
            observed = helpers.host_observer_service_status("ai-hybrid-coordinator")
    assert_true(observed is None, "missing services map is unavailable")


def test_bash_phase_runner_uses_host_observer() -> None:
    bash_runner = ROOT / "scripts" / "ai" / "_aq-qa-bash"
    text = bash_runner.read_text(encoding="utf-8")
    assert_true("_host_observer_service_status" in text, "bash runner has host observer helper")
    assert_true("AQ_HOST_OBSERVER_FILE" in text, "bash runner reads observer artifact")
    assert_true("observer:healthy" in text, "bash runner maps healthy observer state")
    assert_true("unit $unit active via host observer" in text, "bash runner reports observer-backed pass")


if __name__ == "__main__":
    tests = [
        ("sandbox denial classifier", test_sandbox_denial_classifier),
        ("host observer URL", test_host_observer_url_defaults_to_dashboard_api),
        ("service status extraction", test_host_observer_service_status_extracts_service),
        ("service status artifact", test_host_observer_service_status_reads_artifact),
        ("missing observer surface", test_host_observer_service_status_handles_missing_surface),
        ("bash phase runner observer wiring", test_bash_phase_runner_uses_host_observer),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
