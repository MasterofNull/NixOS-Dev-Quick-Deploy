#!/usr/bin/env python3
"""
Test Suite for Factory Kit K10: Worktree helper, Learn command, and Skills subset (Acceptance).

Validates:
1. `aq-factory learn`: scans repository, extracts project stacks, and emits JSON project facts.
2. `aq-factory worktree`: creates isolated worktrees cleanly with branch setup.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AQ_FACTORY = REPO_ROOT / "scripts" / "ai" / "aq-factory"

class TestFactoryKitK10(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="test_factory_k10_"))
        self.repo = self.tmpdir / "consumer_repo"
        self.repo.mkdir()

        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)

        (self.repo / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        (self.repo / "pyproject.toml").write_text('[project]\nname = "test"', encoding="utf-8")
        (self.repo / ".agent" / "memory").mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-m", "initial commit"], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_learn_command(self):
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "learn", "--repo", str(self.repo), "--json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(res.stdout)
        self.assertIn("node", data["stacks"])
        self.assertIn("python", data["stacks"])
        self.assertTrue((self.repo / ".agent" / "memory" / "project-facts.json").is_file())

    def test_worktree_command(self):
        wt_dir = self.tmpdir / "custom_worktrees"
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "worktree", "slice-test", "--repo", str(self.repo), "--dir", str(wt_dir)],
            capture_output=True, text=True, check=True
        )
        self.assertIn("Worktree created successfully", res.stdout)
        self.assertTrue((wt_dir / "slice-test" / ".git").is_file())

if __name__ == "__main__":
    unittest.main()
