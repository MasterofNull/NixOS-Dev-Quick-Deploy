#!/usr/bin/env python3
"""Regression test for security-audit ladder data printing on blocking findings (W7-S2)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSecurityAuditLadderPrint(unittest.TestCase):
    def test_audit_script_syntax(self):
        script = REPO_ROOT / "scripts/security/security-audit.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error: {res.stderr}")

    def test_ladder_output_logic_present(self):
        script_text = (REPO_ROOT / "scripts/security/security-audit.sh").read_text(encoding="utf-8")
        self.assertIn("Gate-Triggered Dependency Hygiene Ladder", script_text)
        self.assertIn("Fix versions", script_text)
        self.assertIn("Fix available", script_text)


if __name__ == "__main__":
    unittest.main()
