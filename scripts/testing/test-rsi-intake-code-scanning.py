#!/usr/bin/env python3
"""Regression tests for rsi-intake-code-scanning.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTAKE_SCRIPT = ROOT / "scripts" / "security" / "rsi-intake-code-scanning.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_filters_dismissed_alerts() -> None:
    """Alerts with state != 'open' must be skipped."""
    alerts = [
        {
            "state": "dismissed",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: badpkg\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "high"}
        },
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: goodpkg\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "high"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        # Last line is summary JSON
        lines = result.stdout.strip().split("\n")
        planned = json.loads(lines[-2]) if len(lines) > 1 else []
        summary = json.loads(lines[-1])

        assert_true(summary["groups"] == 1, f"Expected 1 group (dismissed filtered), got {summary['groups']}")
        assert_true(
            any(p["package"] == "goodpkg" for p in planned),
            "goodpkg (open) must be in planned incidents"
        )
        assert_true(
            not any(p["package"] == "badpkg" for p in planned),
            "badpkg (dismissed) must not be in planned incidents"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_merges_same_package_with_max_severity() -> None:
    """Two alerts for same package must merge with max severity."""
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: mypkg\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "medium"}
        },
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: mypkg\nInstalled Version: 1.0\nFixed Version: 3.0"}
            },
            "rule": {"security_severity_level": "high"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        planned = json.loads(lines[-2]) if len(lines) > 1 else []
        summary = json.loads(lines[-1])

        assert_true(summary["groups"] == 1, f"Expected 1 merged group, got {summary['groups']}")
        assert_true(len(planned) == 1, f"Expected 1 incident, got {len(planned)}")

        incident = planned[0]
        assert_true(incident["severity"] == "high", f"Severity must be 'high' (max), got {incident['severity']}")
        assert_true(incident["alert_count"] == 2, f"Alert count must be 2, got {incident['alert_count']}")
        assert_true(incident["fixed"] == "3.0", f"Fixed version must be 3.0 (max), got {incident['fixed']}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_handles_unknown_fixed_version() -> None:
    """Alert with no fixed version must use 'unknown'."""
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: unfixed\nInstalled Version: 1.0"}
            },
            "rule": {"security_severity_level": "low"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        planned = json.loads(lines[-2]) if len(lines) > 1 else []

        assert_true(len(planned) == 1, "Expected 1 incident")
        incident = planned[0]
        assert_true(incident["fixed"] == "unknown", f"Fixed version must be 'unknown', got {incident['fixed']}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_version_comparison_semver() -> None:
    """Verify semantic version comparison."""
    # Test via two alerts with different fixed versions for same package
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: semver-pkg\nInstalled Version: 1.0\nFixed Version: 1.5"}
            },
            "rule": {"security_severity_level": "medium"}
        },
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: semver-pkg\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "medium"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        planned = json.loads(lines[-2]) if len(lines) > 1 else []

        assert_true(len(planned) == 1, "Expected 1 merged group")
        incident = planned[0]
        assert_true(incident["fixed"] == "2.0", f"Max version must be 2.0, got {incident['fixed']}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_manifest_resolution_requirements_txt() -> None:
    """Verify manifest path resolution for requirements.txt."""
    # This test verifies the real repo's nixos-docs package
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-nixos-docs",
                "message": {"text": "Package: gitpython\nInstalled Version: 3.1.0\nFixed Version: 3.1.1"}
            },
            "rule": {"security_severity_level": "high"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        planned = json.loads(lines[-2]) if len(lines) > 1 else []

        assert_true(len(planned) >= 1, "Expected at least 1 incident")
        incident = planned[0]
        # nixos-docs has ai-stack/mcp-servers/nixos-docs/requirements.txt
        expected = "ai-stack/mcp-servers/nixos-docs/requirements.txt"
        assert_true(
            incident["manifest"] == expected,
            f"Manifest must resolve to requirements.txt, got {incident['manifest']}"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_os_error_stability() -> None:
    """os_error must be stable across identical alerts (identity hash basis)."""
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: pkg1\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "medium"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path1 = fh.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path2 = fh.name

    try:
        # Run twice with identical alerts
        result1 = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path1, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        result2 = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path2, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )

        lines1 = result1.stdout.strip().split("\n")
        lines2 = result2.stdout.strip().split("\n")

        incident1 = json.loads(lines1[-2]) if len(lines1) > 1 else []
        incident2 = json.loads(lines2[-2]) if len(lines2) > 1 else []

        assert_true(len(incident1) > 0 and len(incident2) > 0, "Expected incidents in both runs")
        assert_true(
            incident1[0]["os_error"] == incident2[0]["os_error"],
            f"os_error must be stable: '{incident1[0]['os_error']}' vs '{incident2[0]['os_error']}'"
        )
    finally:
        Path(tmp_path1).unlink(missing_ok=True)
        Path(tmp_path2).unlink(missing_ok=True)


def test_dry_run_does_not_record() -> None:
    """--dry-run must not write to the RSI ledger."""
    alerts = [
        {
            "state": "open",
            "most_recent_instance": {
                "category": "trivy-custom-test",
                "message": {"text": "Package: testpkg\nInstalled Version: 1.0\nFixed Version: 2.0"}
            },
            "rule": {"security_severity_level": "medium"}
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(alerts, fh)
        tmp_path = fh.name

    try:
        # Check that ledger doesn't exist or is empty before
        ledger_path = ROOT / ".agent" / "collaboration" / "rsi-incidents.json"
        existed_before = ledger_path.exists()
        if existed_before:
            content_before = ledger_path.read_text()

        # Run with --dry-run
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )

        # Check summary indicates dry_run=true and recorded=0
        lines = result.stdout.strip().split("\n")
        summary = json.loads(lines[-1])
        assert_true(summary["dry_run"] is True, "dry_run must be true")
        assert_true(summary["recorded"] == 0, "recorded must be 0 in dry-run mode")

        # Verify ledger wasn't modified
        if existed_before:
            content_after = ledger_path.read_text()
            assert_true(
                content_before == content_after,
                "Ledger must not be modified in dry-run mode"
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_empty_alerts_returns_zero_groups() -> None:
    """Empty alert list must produce 0 groups."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump([], fh)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [str(INTAKE_SCRIPT), "--alerts", tmp_path, "--dry-run"],
            capture_output=True,
            text=True,
            check=False
        )
        assert_true(result.returncode == 0, f"Script failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        summary = json.loads(lines[-1])

        assert_true(summary["groups"] == 0, f"Expected 0 groups for empty alerts, got {summary['groups']}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_syntax_valid_python() -> None:
    """Verify scripts are valid Python (compile check)."""
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(INTAKE_SCRIPT)],
        capture_output=True,
        check=False
    )
    assert_true(result.returncode == 0, f"Intake script has syntax errors: {result.stderr.decode()}")


def main() -> int:
    tests = [
        ("syntax valid python", test_syntax_valid_python),
        ("filters dismissed alerts", test_filters_dismissed_alerts),
        ("merges same package with max severity", test_merges_same_package_with_max_severity),
        ("handles unknown fixed version", test_handles_unknown_fixed_version),
        ("version comparison semver", test_version_comparison_semver),
        ("manifest resolution requirements.txt", test_manifest_resolution_requirements_txt),
        ("os_error stability", test_os_error_stability),
        ("dry_run does not record", test_dry_run_does_not_record),
        ("empty alerts returns zero groups", test_empty_alerts_returns_zero_groups),
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
        return 1
    print(f"\n{len(tests)}/{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
