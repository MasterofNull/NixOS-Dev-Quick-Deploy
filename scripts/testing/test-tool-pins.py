#!/usr/bin/env python3
"""Tests for W6-S5 tool-pins manifest and version skew check."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PINS_FILE = REPO_ROOT / "config" / "tool-pins.json"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "governance" / "tier0.d" / "check-tool-pins-skew.sh"

class TestToolPins(unittest.TestCase):
    def test_pins_file_valid_json(self):
        self.assertTrue(PINS_FILE.exists())
        data = json.loads(PINS_FILE.read_text(encoding="utf-8"))
        self.assertIn("pins", data)
        self.assertIn("python", data["pins"])
        self.assertIn("gitleaks", data["pins"])

    def test_skew_check_passes(self):
        res = subprocess.run([str(CHECK_SCRIPT)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Unexpected failure:\n{res.stderr}\n{res.stdout}")
        self.assertIn("PASS: tool versions meet canonical floors", res.stdout)

if __name__ == "__main__":
    unittest.main()
