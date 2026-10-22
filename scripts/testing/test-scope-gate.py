#!/usr/bin/env python3
"""Integration tests for W4-S1: Rust-backed owned-path scope gate."""

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "crates" / "contract-validator"

class TestScopeGate(unittest.TestCase):
    def test_cargo_unit_tests_pass(self):
        res = subprocess.run(
            ["cargo", "test", "--manifest-path", str(CRATE_DIR / "Cargo.toml")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Cargo tests failed:\n{res.stderr}\n{res.stdout}")

    def test_in_scope_cli_passes(self):
        cmd = [
            "cargo", "run", "--quiet", "--manifest-path", str(CRATE_DIR / "Cargo.toml"),
            "--", "--root", str(REPO_ROOT), "scope-gate",
            "--owned", "crates/**,scripts/**",
            "--base", "HEAD",
            "--allow-uncommitted",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Unexpected failure:\n{res.stderr}\n{res.stdout}")
        self.assertIn("PASS: slice changes are strictly within owned scope", res.stdout)

    def test_out_of_scope_cli_blocks(self):
        cmd = [
            "cargo", "run", "--quiet", "--manifest-path", str(CRATE_DIR / "Cargo.toml"),
            "--", "--root", str(REPO_ROOT), "scope-gate",
            "--owned", "nonexistent-scope/**",
            "--base", "HEAD",
            "--allow-uncommitted",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("FAIL: modified file is outside declared owned paths", res.stderr)

    def test_uncommitted_blocks_by_default(self):
        cmd = [
            "cargo", "run", "--quiet", "--manifest-path", str(CRATE_DIR / "Cargo.toml"),
            "--", "--root", str(REPO_ROOT), "scope-gate",
            "--owned", "crates/**,scripts/**",
            "--base", "HEAD",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("FAIL: uncommitted changes detected in working tree", res.stderr)

if __name__ == "__main__":
    unittest.main()
