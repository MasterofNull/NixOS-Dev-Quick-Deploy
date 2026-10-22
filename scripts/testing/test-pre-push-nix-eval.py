#!/usr/bin/env python3
"""
Unit tests for scripts/governance/pre-push-nix-eval.sh (w6-s2)
"""

import os
import subprocess
import tempfile
import unittest

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../governance/pre-push-nix-eval.sh"))

class TestPrePushNixEval(unittest.TestCase):
    def test_script_exists_and_executable(self):
        self.assertTrue(os.path.exists(SCRIPT_PATH), f"Script not found at {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "Script is not executable")

    def test_skip_env_var(self):
        env = os.environ.copy()
        env["SKIP_NIX_EVAL"] = "1"
        res = subprocess.run([SCRIPT_PATH, "HEAD~1", "HEAD"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SKIP_NIX_EVAL set", res.stdout)

    def test_no_nix_files_changed(self):
        # When comparing HEAD to HEAD, changed_files is empty, so should skip
        env = os.environ.copy()
        env.pop("SKIP_NIX_EVAL", None)
        res = subprocess.run([SCRIPT_PATH, "HEAD", "HEAD"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("no Nix-impacting files modified", res.stdout)

if __name__ == "__main__":
    unittest.main()
