#!/usr/bin/env python3
"""
Test Suite for Factory Kit K8: Update with git merge-file and Rollback (T13 Acceptance).

Validates:
1. Clean 3-way merge on local text modifications when kit template changes.
2. Conflict detection on conflicting modifications (leaves conflict markers and exits 1).
3. Rollback (--rollback) restores backed up files byte-identically.
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

class TestFactoryKitK8(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="test_factory_k8_"))
        self.repo = self.tmpdir / "consumer_repo"
        self.repo.mkdir()

        # Simulated custom kit source
        self.custom_kit = self.tmpdir / "custom_kit"
        shutil.copytree(KIT_ROOT, self.custom_kit)

        # Initialize git repo and run init
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)

        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "init", "--repo", str(self.repo), "--kit-root", str(self.custom_kit), "--owner-handle", "@testuser"],
            capture_output=True, text=True, check=True
        )
        # Commit initial state
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-m", "chore: initial factory init"], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_clean_three_way_merge(self):
        # 1. Modify a text file in consumer repo and in kit template
        # Both repo and custom_kit have README.md
        readme = self.repo / "README.md"
        if not readme.exists():
            readme.write_text("Header\nLine 1\nLine 2\nLine 3\nFooter\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(self.repo), "add", str(readme)], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-m", "add readme"], check=True)

        # Baseline in custom_kit
        kit_readme = self.custom_kit / "README.md"
        kit_readme.write_text("Header\nLine 1\nLine 2\nLine 3\nFooter\n", encoding="utf-8")

        # Consumer edits Line 1
        readme.write_text("Header\nLine 1 - custom\nLine 2\nLine 3\nFooter\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-am", "consumer line 1 edit"], check=True)

        # Upstream kit edits Line 3
        kit_readme.write_text("Header\nLine 1\nLine 2\nLine 3 - upstream\nFooter\n", encoding="utf-8")

        # Run update
        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "update", "--repo", str(self.repo), "--kit-root", str(self.custom_kit)],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0, f"update stderr: {res.stderr}\nstdout: {res.stdout}")
        merged_text = readme.read_text(encoding="utf-8")
        self.assertIn("Line 1 - custom", merged_text)
        self.assertIn("Line 3 - upstream", merged_text)

    def test_update_conflict_handling(self):
        readme = self.repo / "README.md"
        readme.write_text("Header\nSame Line\nFooter\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", str(readme)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-m", "add readme"], check=True)

        kit_readme = self.custom_kit / "README.md"
        kit_readme.write_text("Header\nSame Line\nFooter\n", encoding="utf-8")

        # Conflicting edits to same line
        readme.write_text("Header\nSame Line - consumer\nFooter\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-am", "local edit"], check=True)

        kit_readme.write_text("Header\nSame Line - upstream\nFooter\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "update", "--repo", str(self.repo), "--kit-root", str(self.custom_kit)],
            capture_output=True, text=True
        )
        # Should report conflict (rc=1)
        self.assertEqual(res.returncode, 1)
        self.assertIn("<<<<<<<", readme.read_text(encoding="utf-8"))

    def test_update_rollback(self):
        readme = self.repo / "README.md"
        readme.write_text("original content before update\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--no-verify", "-q", "-m", "before update"], check=True)

        # Upstream change
        kit_readme = self.custom_kit / "README.md"
        kit_readme.write_text("completely new upstream content\n", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "update", "--repo", str(self.repo), "--kit-root", str(self.custom_kit)],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(readme.read_text(encoding="utf-8"), "completely new upstream content\n")

        # Now test rollback
        res_rollback = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "update", "--repo", str(self.repo), "--rollback"],
            capture_output=True, text=True
        )
        self.assertEqual(res_rollback.returncode, 0)
        self.assertEqual(readme.read_text(encoding="utf-8"), "original content before update\n")

if __name__ == "__main__":
    unittest.main()
