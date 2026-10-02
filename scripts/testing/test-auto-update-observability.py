#!/usr/bin/env python3
"""Auto-update observability: aq-rsi status CLI + shared API function over fixture state dirs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "ai" / "aq-rsi"
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import auto_update_status as aus  # noqa: E402

BASE = {"outcome": "applied", "started_at": "2026-10-01T00:00:00+00:00", "versions_moved": ["a", "b"],
        "rollback": False, "pending_reboot": False, "reason": ""}


class ObsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)
        self.sd = self.t / "state"

    def fixture(self, status=None, raw=None, halted=False):
        self.sd.mkdir(exist_ok=True)
        if raw is not None:
            (self.sd / "status.json").write_text(raw)
        elif status is not None:
            (self.sd / "status.json").write_text(json.dumps(dict(BASE, **status)))
        if halted:
            (self.sd / "halted").write_text("x")

    def cli(self):
        env = dict(os.environ, AQ_AUTO_UPDATE_STATE_DIR=str(self.sd), RSI_RUNTIME_DIR=str(self.t),
                   PRSI_ACTION_QUEUE_PATH=str(self.t / "q.json"))
        env.pop("PRSI_INCIDENTS_FILE", None)
        (self.t / "q.json").write_text("[]")
        j = subprocess.run([sys.executable, str(CLI), "status", "--json"], env=env, capture_output=True, text=True)
        text = subprocess.run([sys.executable, str(CLI), "status"], env=env, capture_output=True, text=True).stdout
        return json.loads(j.stdout)["auto_update"], text

    def both(self):
        api = aus.read_status(self.sd)
        cli_json, text = self.cli()
        self.assertEqual(api, cli_json)
        return api, text

    def test_ok(self):
        self.fixture({})
        s, text = self.both()
        self.assertEqual((s["state"], s["versions_moved"]), ("ok", 2))
        self.assertIn("auto-update: OK", text)

    def test_rollback(self):
        self.fixture({"rollback": True, "outcome": "rolled_back"})
        s, text = self.both()
        self.assertEqual(s["state"], "attention")
        self.assertIn("rollback=YES", text)

    def test_halted(self):
        self.fixture({}, halted=True)
        s, text = self.both()
        self.assertTrue(s["halted"])
        self.assertIn("halted=YES", text)

    def test_reboot_within_sla(self):
        self.fixture({"pending_reboot": True, "pending_reboot_hours": 5.0, "reboot_sla_hours": 24.0})
        s, text = self.both()
        self.assertEqual(s["state"], "ok")
        self.assertNotIn("BREACH", text)
        self.assertIn("5.0h of 24.0h", text)

    def test_reboot_breached(self):
        self.fixture({"pending_reboot": True, "pending_reboot_hours": 30.0, "reboot_sla_hours": 24.0})
        s, text = self.both()
        self.assertTrue(s["reboot_breach"])
        self.assertEqual(s["state"], "attention")
        self.assertIn("BREACH", text)

    def test_corrupt_is_unknown(self):
        self.fixture(raw="{not json")
        s, text = self.both()
        self.assertEqual(s["state"], "unknown")
        self.assertIn("UNKNOWN", text)
        self.assertNotIn("auto-update: OK", text)

    def test_missing_status_file_is_unknown(self):
        self.fixture()
        self.assertEqual(self.both()[0]["state"], "unknown")

    def test_missing_dir_not_enabled(self):
        s, text = self.both()
        self.assertEqual(s["state"], "not_enabled")
        self.assertIn("auto-update: not enabled", text)


if __name__ == "__main__":
    unittest.main()
