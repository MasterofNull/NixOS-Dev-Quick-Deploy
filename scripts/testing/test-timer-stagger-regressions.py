#!/usr/bin/env python3
"""Regressions: fractional MCP timeout scale keeps a >=1s timeout; stagger check demands activation-relative offsets on monotonic timers only; non-finite recall env falls back."""
import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class EnvTimeout(unittest.TestCase):
    def setUp(self):
        self.bridge = load("mcp_bridge_hybrid", "scripts/ai/mcp-bridge-hybrid.py")
        self._saved = {k: os.environ.get(k) for k in ("AQ_MCP_TIMEOUT_SCALE", "AQ_MCP_TIMEOUT_GET_HINTS_S")}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def t(self, scale, default=5):
        os.environ["AQ_MCP_TIMEOUT_SCALE"] = scale
        return self.bridge._env_timeout("get_hints", default)

    def test_fractional_scale_never_zero(self):
        self.assertEqual(self.t("0.1"), 1.0)
        self.assertGreaterEqual(self.t("0.01", 2), 1.0)

    def test_fractional_value_preserved(self):
        self.assertAlmostEqual(self.t("1.5"), 7.5)
        self.assertAlmostEqual(self.t("2"), 10.0)

    def test_bad_scale_falls_back_to_default(self):
        for v in ("0", "-1", "nan", "inf", "abc"):
            self.assertEqual(self.t(v), 5, v)


class RecallDefault(unittest.TestCase):
    KEYS = ("AI_MEMORY_BROKER_RW_TIMEOUT_S", "AQ_MCP_RECALL_MARGIN_S")

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_nonfinite_env_does_not_crash_import_and_falls_back(self):
        for bad in ("nan", "inf", "-inf", "NaN", "abc"):
            for key in self.KEYS:
                os.environ.pop(self.KEYS[0], None)
                os.environ.pop(self.KEYS[1], None)
                os.environ[key] = bad
                bridge = load("mcp_bridge_hybrid_x", "scripts/ai/mcp-bridge-hybrid.py")
                self.assertEqual(bridge._recall_memory_default(), 20, (key, bad))

    def test_valid_values_still_used(self):
        os.environ["AI_MEMORY_BROKER_RW_TIMEOUT_S"] = "5"
        os.environ["AQ_MCP_RECALL_MARGIN_S"] = "7"
        bridge = load("mcp_bridge_hybrid_y", "scripts/ai/mcp-bridge-hybrid.py")
        self.assertEqual(bridge._recall_memory_default(), 12)


class StaggerCheck(unittest.TestCase):
    def setUp(self):
        self.chk = load("check_timer_stagger", "scripts/testing/check-timer-stagger.py")

    base = {"RandomizedDelaySec": "2min", "AccuracySec": "1min", "FixedRandomDelay": True, "OnActiveSec": "5min"}

    def test_good_timer_passes(self):
        self.assertEqual(self.chk.check({"ai-x": dict(self.base)}), [])

    def test_boot_next_to_active_fails(self):
        cfg = dict(self.base)
        cfg["OnBootSec"] = "5min"
        errs = self.chk.check({"ai-x": cfg})
        self.assertTrue(any("OnBootSec still set" in e for e in errs), errs)

    def test_empty_boot_list_ok(self):
        cfg = dict(self.base)
        cfg["OnBootSec"] = []
        self.assertEqual(self.chk.check({"ai-x": cfg}), [])

    def test_calendar_only_passes_without_active(self):
        cfg = {"RandomizedDelaySec": "30min", "AccuracySec": "5min", "FixedRandomDelay": True,
               "OnCalendar": "daily"}
        self.assertEqual(self.chk.check({"ai-x": cfg}), [])

    def test_calendar_with_active_fails(self):
        cfg = {"RandomizedDelaySec": "30min", "AccuracySec": "5min", "FixedRandomDelay": True,
               "OnCalendar": "daily", "OnActiveSec": "18min"}
        errs = self.chk.check({"ai-x": cfg})
        self.assertTrue(any("calendar timer has OnActiveSec" in e for e in errs), errs)

    def test_boot_relative_only_fails(self):
        cfg = dict(self.base)
        del cfg["OnActiveSec"]
        cfg["OnBootSec"] = "5min"
        errs = self.chk.check({"ai-x": cfg})
        self.assertTrue(any("OnActiveSec" in e for e in errs), errs)

    def test_missing_fixed_random_delay_fails(self):
        cfg = dict(self.base)
        del cfg["FixedRandomDelay"]
        self.assertTrue(any("FixedRandomDelay" in e for e in self.chk.check({"ai-x": cfg})))

    def test_heavy_slot_collision_detected(self):
        a, b = dict(self.base), dict(self.base)
        errs = self.chk.check({"ai-optimizer": a, "ai-aidb-reindex": b})
        self.assertTrue(any("collides" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
