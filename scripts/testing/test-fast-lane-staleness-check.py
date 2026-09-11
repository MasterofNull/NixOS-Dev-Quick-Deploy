#!/usr/bin/env python3
"""Tiny test for the fast-lane staleness checker's version-compare logic
(.agents/plans/split-channel-packaging/DESIGN.md sc-2). Pure-function tests
only — no network, no `nix` invocation."""

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "health" / "fast-lane-staleness-check.py"
_spec = importlib.util.spec_from_file_location("fast_lane_staleness_check", _SCRIPT)
fast_lane = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fast_lane
_spec.loader.exec_module(fast_lane)  # type: ignore[union-attr]


def test_compare_versions_equal_is_not_behind():
    assert fast_lane.compare_versions("2.5.5", "2.5.5") is False


def test_compare_versions_different_is_behind():
    assert fast_lane.compare_versions("2.5.5", "2.6.0") is True


def test_compare_versions_unknown_installed_is_not_behind():
    # A transient eval failure (installed=None) must never be reported as "behind".
    assert fast_lane.compare_versions(None, "2.6.0") is False


def test_compare_versions_unknown_available_is_not_behind():
    assert fast_lane.compare_versions("2.5.5", None) is False


def test_pin_age_days_computes_from_last_modified():
    now = fast_lane.time.time()
    locked = {"lastModified": now - (10 * 86400)}
    age = fast_lane.pin_age_days(locked)
    assert age is not None
    assert 9.9 <= age <= 10.1


def test_pin_age_days_none_when_missing():
    assert fast_lane.pin_age_days(None) is None
    assert fast_lane.pin_age_days({}) is None


def test_check_package_behind_when_versions_differ(monkeypatch):
    locked_ref = "github:NixOS/nixpkgs/deadbeef"

    def fake_eval(flake_ref, attr):
        assert attr == "antigravity-ide"
        return "1.23.2" if flake_ref == locked_ref else "2.5.5"

    monkeypatch.setattr(fast_lane, "_nix_eval_version", fake_eval)
    status = fast_lane.check_package("antigravity", {"antigravity": "antigravity-ide"}, locked_ref)
    assert status.unstable_attr == "antigravity-ide"
    assert status.installed_version == "1.23.2"
    assert status.available_version == "2.5.5"
    assert status.behind is True
    assert status.error is None


def test_check_package_not_behind_when_versions_match(monkeypatch):
    monkeypatch.setattr(fast_lane, "_nix_eval_version", lambda flake_ref, attr: "2.5.5")
    status = fast_lane.check_package("antigravity", {"antigravity": "antigravity-ide"}, "github:NixOS/nixpkgs/deadbeef")
    assert status.behind is False
    assert status.error is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
