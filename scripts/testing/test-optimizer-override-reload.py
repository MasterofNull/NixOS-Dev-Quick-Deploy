#!/usr/bin/env python3
"""Test optimizer override reload behavior via systemd path units."""
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[2]

# Load aq-optimizer via importlib.machinery (it has no .py suffix)
loader = importlib.machinery.SourceFileLoader("aq_optimizer", str(ROOT / "scripts" / "ai" / "aq-optimizer"))
spec = importlib.util.spec_from_loader("aq_optimizer", loader)
aq_optimizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aq_optimizer)


class OptimizerOverrideReloadTest(unittest.TestCase):
    def setUp(self):
        """Set up temp directory and mock the overrides file path."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.overrides_file = self.tmp_path / "overrides.env"

    def test_reload_declared_for_consumers(self):
        """Consumer services get 'reload_declared' outcome, no subprocess calls."""
        # Mock the overrides file path
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            action = {
                "env_overrides": {"SOME_VAR": "value1"},
                "services": ["ai-hybrid-coordinator", "ai-switchboard"],
            }
            # Patch subprocess.run to fail if called
            with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")):
                results = aq_optimizer.apply_routing(action, dry_run=False)

        # Both services should report reload_declared
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {"service": "ai-hybrid-coordinator", "outcome": "reload_declared"})
        self.assertEqual(results[1], {"service": "ai-switchboard", "outcome": "reload_declared"})
        # File should be written
        self.assertTrue(self.overrides_file.exists())

    def test_applied_pending_restart_for_unknown_services(self):
        """Unknown services get 'applied_pending_restart' outcome."""
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            action = {
                "env_overrides": {"SOME_VAR": "value2"},
                "services": ["some-other-service"],
            }
            with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")):
                results = aq_optimizer.apply_routing(action, dry_run=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"service": "some-other-service", "outcome": "applied_pending_restart"})

    def test_unchanged_on_identical_apply(self):
        """Second identical apply returns 'unchanged' and file mtime does not change."""
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            action = {
                "env_overrides": {"KEY": "val"},
                "services": ["ai-hybrid-coordinator"],
            }
            # First apply
            results1 = aq_optimizer.apply_routing(action, dry_run=False)
            self.assertEqual(results1[0]["outcome"], "reload_declared")
            self.assertTrue(self.overrides_file.exists())
            mtime1 = self.overrides_file.stat().st_mtime

            # Small sleep to ensure mtime would differ if written
            import time
            time.sleep(0.01)

            # Second apply with identical content
            with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")):
                results2 = aq_optimizer.apply_routing(action, dry_run=False)

        self.assertEqual(results2[0]["outcome"], "unchanged")
        mtime2 = self.overrides_file.stat().st_mtime
        self.assertEqual(mtime1, mtime2, "File mtime should not change on unchanged content")

    def test_dry_run_returns_dry_run_outcome(self):
        """Dry-run mode returns 'dry_run' for all services."""
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            action = {
                "env_overrides": {"KEY": "val"},
                "services": ["ai-hybrid-coordinator", "some-service"],
            }
            results = aq_optimizer.apply_routing(action, dry_run=True)

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result["outcome"], "dry_run")
        # File should NOT exist in dry-run
        self.assertFalse(self.overrides_file.exists())

    def test_mixed_services(self):
        """Mix of consumer and non-consumer services report correct outcomes."""
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            action = {
                "env_overrides": {"X": "y"},
                "services": ["ai-hybrid-coordinator", "other-svc", "ai-switchboard"],
            }
            with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")):
                results = aq_optimizer.apply_routing(action, dry_run=False)

        outcomes = {r["service"]: r["outcome"] for r in results}
        self.assertEqual(outcomes["ai-hybrid-coordinator"], "reload_declared")
        self.assertEqual(outcomes["other-svc"], "applied_pending_restart")
        self.assertEqual(outcomes["ai-switchboard"], "reload_declared")

    def test_write_overrides_returns_bool(self):
        """_write_overrides returns True on write, False on unchanged."""
        with patch.object(aq_optimizer, "OVERRIDES_ENV_PATH", self.overrides_file):
            # First write should return True
            result1 = aq_optimizer._write_overrides({"A": "b"})
            self.assertTrue(result1)
            self.assertTrue(self.overrides_file.exists())

            # Identical write should return False
            result2 = aq_optimizer._write_overrides({"A": "b"})
            self.assertFalse(result2)

            # Different write should return True
            result3 = aq_optimizer._write_overrides({"A": "c"})
            self.assertTrue(result3)


if __name__ == "__main__":
    unittest.main()
