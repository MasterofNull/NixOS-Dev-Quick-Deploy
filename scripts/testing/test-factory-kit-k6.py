#!/usr/bin/env python3
"""
Unit and integration tests for aq-factory retrofit and foreign-hook refusal (Slice K6).
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
KIT_ROOT = REPO_ROOT / "templates" / "factory-kit"

class TestFactoryKitK6(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="test_factory_k6_"))
        self.repo = self.tmpdir / "test_repo"
        self.repo.mkdir()
        # Initialize git repo
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        # Create an initial commit so tree is valid
        (self.repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "chore: initial commit"], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_retrofit_refuses_dirty_tree(self):
        (self.repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 4)
        self.assertIn("Working tree is dirty", res.stderr)

    def test_retrofit_refuses_foreign_husky(self):
        (self.repo / ".husky").mkdir()
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 4)
        self.assertIn("Foreign hook manager(s) detected", res.stderr)
        self.assertIn(".husky", res.stderr)

    def test_retrofit_refuses_foreign_pre_commit(self):
        (self.repo / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", ".pre-commit-config.yaml"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "add pre-commit"], check=True)
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 4)
        self.assertIn("Foreign hook manager(s) detected", res.stderr)
        self.assertIn(".pre-commit-config.yaml", res.stderr)

    def test_retrofit_preview_and_install_with_confirmation(self):
        # 1. Dry run / preview
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT), "--dry-run", "--json", "--owner-handle", "@testuser"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(res.stdout)
        digest = data["preview_digest"]
        self.assertTrue(digest)

        # 2. Run without confirmation -> exits 4 asking for confirmation
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT), "--owner-handle", "@testuser"],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 4)
        self.assertIn(f"--confirm {digest}", res.stderr)

        # 3. Run with confirmation -> installs successfully
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT), "--owner-handle", "@testuser", "--confirm", digest],
            capture_output=True, text=True, check=True
        )
        self.assertIn("Factory kit retrofitted successfully", res.stdout)
        self.assertTrue((self.repo / ".factory" / "kit.lock").exists())
        self.assertTrue((self.repo / ".factory" / "gate-install.json").exists())

        # Verify doctor passes after retrofit
        doc = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "doctor", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(doc.returncode, 0)

if __name__ == "__main__":
    unittest.main()
