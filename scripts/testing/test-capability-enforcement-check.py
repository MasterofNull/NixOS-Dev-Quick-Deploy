#!/usr/bin/env python3
"""Verify C2 lease enforcement and C5 span-truth flag detection in aq-health-spider."""

import importlib.machinery
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

SPIDER = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-health-spider"
health_spider = importlib.machinery.SourceFileLoader("aq_health_spider", str(SPIDER)).load_module()


def test_c2_lease_enforcement_green_when_flag_and_key_present(tmp_path):
    """C2 GREEN when CAPABILITY_LEASE_ENFORCEMENT=1 and key file exists + non-empty."""
    key_file = tmp_path / "aq-lease-signing-key"
    key_file.write_text("secret-key-data", encoding="utf-8")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 100
                anomalies = health_spider._capability_enforcement_check()

    # Should have no C2 or C5 anomalies when both are GREEN
    assert not any(a["type"].startswith("c2_") or a["type"].startswith("c5_") for a in anomalies)


def test_c2_lease_enforcement_red_when_flag_off():
    """C2 RED when CAPABILITY_LEASE_ENFORCEMENT is not 1."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=0 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        anomalies = health_spider._capability_enforcement_check()

    c2_anomalies = [a for a in anomalies if a["type"] == "c2_lease_enforcement_disabled"]
    assert len(c2_anomalies) == 1
    assert "CAPABILITY_LEASE_ENFORCEMENT" in c2_anomalies[0]["detail"]
    assert "degraded to dev-key" in c2_anomalies[0]["detail"]


def test_c2_lease_key_missing_red_when_key_absent():
    """C2 RED when key file doesn't exist."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=False):
            anomalies = health_spider._capability_enforcement_check()

    c2_key_anomalies = [a for a in anomalies if a["type"] == "c2_lease_key_missing"]
    assert len(c2_key_anomalies) == 1
    assert "/run/secrets/aq-lease-signing-key" in c2_key_anomalies[0]["detail"]
    assert "does not exist or is empty" in c2_key_anomalies[0]["detail"]


def test_c2_lease_key_empty_red_when_key_zero_size():
    """C2 RED when key file exists but is empty."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 0
                anomalies = health_spider._capability_enforcement_check()

    c2_key_anomalies = [a for a in anomalies if a["type"] == "c2_lease_key_missing"]
    assert len(c2_key_anomalies) == 1


def test_c5_span_truth_red_when_flag_off():
    """C5 RED when CAPABILITY_SPAN_TRUTH is not 1."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=0"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 100
                anomalies = health_spider._capability_enforcement_check()

    c5_anomalies = [a for a in anomalies if a["type"] == "c5_span_truth_disabled"]
    assert len(c5_anomalies) == 1
    assert "CAPABILITY_SPAN_TRUTH" in c5_anomalies[0]["detail"]
    assert "not set to 1" in c5_anomalies[0]["detail"]


def test_c5_span_truth_green_when_flag_on_ignores_event_log():
    """C5 GREEN when flag is 1, regardless of recent events (no false failures for quiet systems)."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 100
                anomalies = health_spider._capability_enforcement_check()

    c5_anomalies = [a for a in anomalies if a["type"] == "c5_span_truth_disabled"]
    assert len(c5_anomalies) == 0  # Flag is ON, so no anomaly


def test_capability_check_silent_fail_on_systemctl_error():
    """Capability check gracefully handles systemctl read error (returns empty list)."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        anomalies = health_spider._capability_enforcement_check()

    # Should silently fail and return empty list (never break health-spider)
    assert anomalies == []


def test_both_c2_and_c5_flags_off():
    """Both C2 and C5 degradation is detected together."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=0 CAPABILITY_SPAN_TRUTH=0"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 100
                anomalies = health_spider._capability_enforcement_check()

    types = {a["type"] for a in anomalies}
    assert "c2_lease_enforcement_disabled" in types
    assert "c5_span_truth_disabled" in types


def test_c2_lease_key_permission_error_no_red():
    """C2 does NOT emit RED when PermissionError prevents determining key status (indeterminate)."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "CAPABILITY_LEASE_ENFORCEMENT=1 CAPABILITY_SPAN_TRUTH=1"

    with patch("subprocess.run", return_value=mock_result):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                # Simulate PermissionError when trying to stat the key
                mock_stat.side_effect = PermissionError("Permission denied")
                anomalies = health_spider._capability_enforcement_check()

    c2_key_anomalies = [a for a in anomalies if a["type"] == "c2_lease_key_missing"]
    assert len(c2_key_anomalies) == 0  # NO RED when indeterminate due to permission error


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
