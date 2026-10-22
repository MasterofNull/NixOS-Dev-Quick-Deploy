#!/usr/bin/env python3
"""Regression test for aq-skill-eval (W4-S3)."""
import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSkillEval(unittest.TestCase):
    def test_cli_runs(self):
        cmd = [str(REPO_ROOT / "scripts/ai/aq-skill-eval"), "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 50)
        # Verify template-skill is identified as a zero-delta prune candidate
        template = next((s for s in data if s["skill"] == "template-skill"), None)
        self.assertIsNotNone(template)
        self.assertTrue(template["zero_delta"])
        self.assertEqual(template["recommendation"], "archive")


if __name__ == "__main__":
    unittest.main()
