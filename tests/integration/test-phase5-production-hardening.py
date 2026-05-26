#!/usr/bin/env python3
"""
test-phase5-production-hardening.py — Validation for Phase 5 of P.A.E.A.
"""

import unittest
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

class TestPhase5(unittest.TestCase):
    def test_flake_age_check(self):
        script_path = REPO_ROOT / "scripts" / "governance" / "check-flake-age.sh"
        self.assertTrue(script_path.exists(), "check-flake-age.sh should exist")
        
        # We can't guarantee Nix is available in this test environment or that 
        # the flake is properly locked, so we just check if it's executable.
        self.assertTrue(os.access(script_path, os.X_OK), "Script must be executable")

    def test_collective_intelligence_script(self):
        script_path = REPO_ROOT / "scripts" / "ai" / "aq-push-intelligence"
        self.assertTrue(script_path.exists(), "aq-push-intelligence should exist")
        self.assertTrue(os.access(script_path, os.X_OK), "Script must be executable")
        
        # Run it and check output
        proc = subprocess.run([str(script_path)], capture_output=True, text=True)
        # Even if aq-insights fails, the script should handle it gracefully
        self.assertIn("Collective Intelligence Loop completed.", proc.stderr)

import os
if __name__ == "__main__":
    unittest.main()
