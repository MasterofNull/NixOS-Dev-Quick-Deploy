#!/usr/bin/env python3
"""Integration tests for W5-S3: Tier 0 anti-fabrication lint."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "governance" / "tier0.d" / "check-anti-fabrication.sh"

class TestAntiFabricationLint(unittest.TestCase):
    def test_current_repo_passes(self):
        res = subprocess.run([str(SCRIPT_PATH)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Unexpected failure:\n{res.stderr}\n{res.stdout}")
        self.assertIn("PASS: anti-fabrication constraints verified", res.stdout)

    def test_pct_hint_triggers_failure(self):
        # Create a dummy tracker.json with pct_hint
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = Path(REPO_ROOT) / ".agents" / "plans" / "temp-test-tracker.json"
            try:
                tracker.write_text('{"items": [{"id": "t1", "pct_hint": 50}]}', encoding="utf-8")
                res = subprocess.run([str(SCRIPT_PATH)], capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("Forbidden 'pct_hint' detected", res.stderr)
            finally:
                if tracker.exists():
                    tracker.unlink()

if __name__ == "__main__":
    unittest.main()
