#!/usr/bin/env python3
"""Tests for config_loader + switchboard profile schema (WS1 config contracts).

Run: python3 scripts/testing/test-config-loader.py
"""

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(REPO))

import config_loader  # noqa: E402

REAL = REPO / "config" / "switchboard-profiles.yaml"

_MINIMAL = """\
_meta:
  version: "1"
profiles:
  default:
    forceProvider: null
    maxInputTokens: 1500
    profileCard: "hi"
  remote-x:
    forceProvider: remote
    maxOutputTokens: 900
"""


def _write(tmp: Path, text: str) -> Path:
    p = tmp / "switchboard-profiles.yaml"
    p.write_text(text)
    return p


def test_real_config_valid():
    ok, msg = config_loader.validate_file(REAL)
    assert ok, msg
    ok, msg = config_loader.round_trip_ok(REAL)
    assert ok, msg
    print("PASS real config validates + round-trips")


def test_schema_registered():
    from contracts.config import registry
    reg = registry()
    assert "config/switchboard-profiles.yaml" in reg, list(reg)
    print(f"PASS schema registered ({len(reg)} config schema(s))")


def test_bad_provider_rejected():
    # Validate against the schema directly (temp path isn't in the registry).
    from contracts.config.switchboard_profiles import SwitchboardProfileCatalog
    try:
        SwitchboardProfileCatalog.model_validate(
            {"profiles": {"default": {"forceProvider": "cloud"}}}
        )
    except Exception as exc:
        assert "forceProvider" in str(exc), exc
        print("PASS invalid forceProvider rejected")
        return
    raise AssertionError("expected validation error for forceProvider=cloud")


def test_negative_budget_rejected():
    from contracts.config.switchboard_profiles import SwitchboardProfileCatalog
    try:
        SwitchboardProfileCatalog.model_validate(
            {"profiles": {"default": {"maxInputTokens": -5}}}
        )
    except Exception:
        print("PASS negative token budget rejected")
        return
    raise AssertionError("expected validation error for negative maxInputTokens")


def test_missing_default_rejected():
    from contracts.config.switchboard_profiles import SwitchboardProfileCatalog
    try:
        SwitchboardProfileCatalog.model_validate({"profiles": {"only-remote": {}}})
    except Exception as exc:
        assert "default" in str(exc), exc
        print("PASS catalog without 'default' profile rejected")
        return
    raise AssertionError("expected validation error for missing default profile")


def test_watcher_applies_valid_reload():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        p = _write(tmp, _MINIMAL)
        applied = {"count": 0, "last": None}

        def on_reload(raw):
            applied["count"] += 1
            applied["last"] = raw

        w = config_loader.ConfigWatcher(p, on_reload, interval_s=0.1)
        # No change yet.
        assert w.check_once() is False
        time.sleep(0.02)
        p.write_text(_MINIMAL.replace('maxInputTokens: 1500', 'maxInputTokens: 1600'))
        # mtime must advance.
        import os
        os.utime(p, None)
        assert w.check_once() is True, "valid reload should apply"
        assert applied["count"] == 1
        print("PASS watcher applies valid reload")


def test_watcher_rejects_invalid_reload():
    # Register the temp path so the watcher validates it like the real one.
    from contracts.config import CONFIG_SCHEMA_REGISTRY
    from contracts.config.switchboard_profiles import SwitchboardProfileCatalog
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        p = _write(tmp, _MINIMAL)
        rel = config_loader._repo_rel(p)
        CONFIG_SCHEMA_REGISTRY[rel] = lambda: SwitchboardProfileCatalog
        try:
            applied = {"count": 0}
            w = config_loader.ConfigWatcher(p, lambda raw: applied.__setitem__("count", applied["count"] + 1), interval_s=0.1)
            import os
            # Write an INVALID edit (bad provider) and bump mtime.
            p.write_text(_MINIMAL.replace("forceProvider: remote", "forceProvider: cloud"))
            os.utime(p, None)
            assert w.check_once() is False, "invalid reload must be rejected"
            assert applied["count"] == 0, "callback must not fire on invalid reload"
            print("PASS watcher rejects invalid reload (last-good kept)")
        finally:
            CONFIG_SCHEMA_REGISTRY.pop(rel, None)


if __name__ == "__main__":
    test_schema_registered()
    test_real_config_valid()
    test_bad_provider_rejected()
    test_negative_budget_rejected()
    test_missing_default_rejected()
    test_watcher_applies_valid_reload()
    test_watcher_rejects_invalid_reload()
    print("ALL PASS")
