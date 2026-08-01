#!/usr/bin/env python3
"""Unit tests for capability enforcement card endpoint.

Tests the logic of the get_capability_enforcement endpoint by extracting and
testing the core probe logic directly.

Tests can be run with:
  python3 test-capability-enforcement-card.py
"""

import sys
from pathlib import Path
from unittest import mock


def capability_enforcement_logic() -> dict:
    """
    Core logic of get_capability_enforcement endpoint.
    Extracted for testability without FastAPI/decorator overhead.
    """
    import subprocess

    result = {
        "c2": {"enforcement": "unknown", "key_present": None, "status": "unknown"},
        "c5": {"span_truth": "unknown", "status": "unknown"},
        "available": True,
    }

    # 1. Read ai-switchboard.service environment variables
    env_vars = {}
    try:
        r = subprocess.run(
            ["systemctl", "show", "ai-switchboard.service", "-p", "Environment", "--value"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            # systemctl command failed
            result["available"] = False
            return result
        if r.stdout.strip():
            # Parse space-separated VAR=value tokens
            for part in r.stdout.strip().split():
                if "=" in part:
                    key, val = part.split("=", 1)
                    env_vars[key] = val
    except Exception:
        result["available"] = False
        return result

    # 2. C2 Lease enforcement check
    c2_flag = env_vars.get("CAPABILITY_LEASE_ENFORCEMENT", "0").strip()
    key_path = Path("/run/secrets/aq-lease-signing-key")

    c2_flag_ok = c2_flag == "1"
    result["c2"]["enforcement"] = "on" if c2_flag_ok else "off"

    # Check key presence
    key_ok = False
    key_present_value = False  # Default: assume missing
    try:
        if key_path.exists():
            stat_info = key_path.stat()
            key_ok = stat_info.st_size > 0
            key_present_value = key_ok
            result["c2"]["key_present"] = key_present_value
        else:
            result["c2"]["key_present"] = False
    except PermissionError:
        # Can't determine if key exists due to permission; mark indeterminate
        result["c2"]["key_present"] = None
    except Exception:
        result["c2"]["key_present"] = None

    # C2 status: ok if both flag on AND key present, degraded if either fails
    if c2_flag_ok and key_ok:
        result["c2"]["status"] = "ok"
    elif not c2_flag_ok or (result["c2"]["key_present"] is False):
        result["c2"]["status"] = "degraded"
    else:
        result["c2"]["status"] = "unknown"

    # 3. C5 Span-truth check
    c5_flag = env_vars.get("CAPABILITY_SPAN_TRUTH", "0").strip()
    c5_flag_ok = c5_flag == "1"
    result["c5"]["span_truth"] = "on" if c5_flag_ok else "off"
    result["c5"]["status"] = "ok" if c5_flag_ok else "degraded"

    return result


def test_c2_c5_both_on():
    """Test: C2 and C5 both enabled with key present."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists, \
         mock.patch("pathlib.Path.stat") as mock_stat:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1",
            stderr=""
        )
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 256

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["enforcement"] == "on"
        assert result["c2"]["status"] == "ok"
        assert result["c2"]["key_present"] is True
        assert result["c5"]["span_truth"] == "on"
        assert result["c5"]["status"] == "ok"

    print("✓ test_c2_c5_both_on")


def test_c2_flag_off():
    """Test: C2 flag disabled (degraded)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists, \
         mock.patch("pathlib.Path.stat") as mock_stat:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=0 CAPABILITY_SPAN_TRUTH=1",
            stderr=""
        )
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 256

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["enforcement"] == "off"
        assert result["c2"]["status"] == "degraded"
        assert result["c5"]["span_truth"] == "on"

    print("✓ test_c2_flag_off")


def test_c2_key_missing():
    """Test: C2 flag on but key missing (degraded)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1",
            stderr=""
        )
        mock_exists.return_value = False

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["enforcement"] == "on"
        assert result["c2"]["key_present"] is False
        assert result["c2"]["status"] == "degraded"

    print("✓ test_c2_key_missing")


def test_c2_key_empty():
    """Test: C2 flag on but key is empty (degraded)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists, \
         mock.patch("pathlib.Path.stat") as mock_stat:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1",
            stderr=""
        )
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 0

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["key_present"] is False
        assert result["c2"]["status"] == "degraded"

    print("✓ test_c2_key_empty")


def test_c2_key_permission_error():
    """Test: C2 key permission denied (key_present = null, status = unknown)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists, \
         mock.patch("pathlib.Path.stat") as mock_stat:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1",
            stderr=""
        )
        mock_exists.return_value = True
        mock_stat.side_effect = PermissionError("Permission denied")

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["enforcement"] == "on"
        assert result["c2"]["key_present"] is None
        assert result["c2"]["status"] == "unknown"

    print("✓ test_c2_key_permission_error")


def test_c5_flag_off():
    """Test: C5 flag disabled (degraded)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists, \
         mock.patch("pathlib.Path.stat") as mock_stat:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=0",
            stderr=""
        )
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 256

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c5"]["span_truth"] == "off"
        assert result["c5"]["status"] == "degraded"
        assert result["c2"]["status"] == "ok"

    print("✓ test_c5_flag_off")


def test_systemctl_unavailable():
    """Test: systemctl command fails (available = false)."""
    with mock.patch("subprocess.run") as mock_run:

        mock_run.return_value = mock.MagicMock(
            returncode=1,
            stdout="",
            stderr="command not found"
        )

        result = capability_enforcement_logic()

        assert result["available"] is False
        assert result["c2"]["enforcement"] == "unknown"
        assert result["c5"]["span_truth"] == "unknown"

    print("✓ test_systemctl_unavailable")


def test_systemctl_exception():
    """Test: systemctl raises exception (available = false)."""
    with mock.patch("subprocess.run") as mock_run:

        mock_run.side_effect = Exception("systemctl timeout")

        result = capability_enforcement_logic()

        assert result["available"] is False

    print("✓ test_systemctl_exception")


def test_empty_env_vars():
    """Test: no capability flags set (both off by default)."""
    with mock.patch("subprocess.run") as mock_run, \
         mock.patch("pathlib.Path.exists") as mock_exists:

        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        mock_exists.return_value = False

        result = capability_enforcement_logic()

        assert result["available"] is True
        assert result["c2"]["enforcement"] == "off"
        assert result["c5"]["span_truth"] == "off"

    print("✓ test_empty_env_vars")


def main():
    """Run all tests."""
    tests = [
        test_c2_c5_both_on,
        test_c2_flag_off,
        test_c2_key_missing,
        test_c2_key_empty,
        test_c2_key_permission_error,
        test_c5_flag_off,
        test_systemctl_unavailable,
        test_systemctl_exception,
        test_empty_env_vars,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    if failed:
        print(f"\n{failed}/{len(tests)} tests failed")
        return 1
    else:
        print(f"\nAll {len(tests)} tests passed")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
