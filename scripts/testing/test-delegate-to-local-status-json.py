#!/usr/bin/env python3
"""Regression test for delegate-to-local --status --json flag support."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDelegateToLocalStatusJson(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = REPO_ROOT / "scripts" / "ai" / "delegate-to-local"
        self.assertTrue(self.cli.exists(), "delegate-to-local missing")

    def test_status_then_json_flag(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "--status", "nonexistent-task-id", "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotIn("Unknown option: --json", proc.stderr)
        self.assertNotIn("Unknown option: --json", proc.stdout)
        self.assertIn("Task not found", proc.stdout + proc.stderr)

    def test_json_flag_then_status(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "--json", "--status", "nonexistent-task-id"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotIn("Unknown option: --json", proc.stderr)
        self.assertNotIn("Unknown option: --json", proc.stdout)
        self.assertIn("Task not found", proc.stdout + proc.stderr)

    def test_status_missing_id_dies(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "--status"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--status requires a task ID", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
