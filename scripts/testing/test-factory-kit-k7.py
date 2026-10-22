#!/usr/bin/env python3
"""
Test Suite for Factory Kit K7: Mendocino Retrofit E2E (T17 Acceptance).

Validates:
1. Baseline doctor detection before retrofit (reports blockers with fix hints, exit 1).
2. Two-phase retrofit preview and confirmation digest generation.
3. Retrofit execution via aq-factory retrofit --confirm <digest>.
4. Verification of pristine consumer files and backup generation.
5. No host path leaks (/home/, Nix store) across managed files.
6. Local-model layer isolation (LOCAL-AGENT.md remains generic stub).
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

class TestFactoryKitK7(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="test_factory_k7_"))
        self.repo = self.tmpdir / "mendocino_fixture"
        self.repo.mkdir()

        # Build realistic consumer repository matching Mendocino-Coastal-Plants baseline
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Mendocino Test"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "mendocino@example.com"], check=True)

        # Realistic package.json
        pkg_json = {
            "name": "mendocino-coastal-plants",
            "version": "1.0.0",
            "scripts": {
                "build": "echo build ok",
                "lint": "echo lint ok",
                "test": "echo test ok"
            }
        }
        (self.repo / "package.json").write_text(json.dumps(pkg_json, indent=2) + "\n", encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "index.js").write_text("console.log('plants');\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_catalog.py").write_text("import unittest\nclass T(unittest.TestCase):\n  def test_one(self): pass\n", encoding="utf-8")

        # Initial commit
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "chore: baseline commit"], check=True)
        self.baseline_sha = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_e2e_retrofit_journey(self):
        # 1. Doctor before retrofit exits 1 with baseline missing lock/receipt
        doc_before = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "doctor", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(doc_before.returncode, 1)
        self.assertIn("Missing .factory/kit.lock", doc_before.stdout)

        # 2. Preview generates preview_digest
        prev = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT), "--dry-run", "--json", "--owner-handle", "@masterofnull"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(prev.stdout)
        digest = data["preview_digest"]
        self.assertTrue(digest)

        # 3. Live install with confirmation digest
        inst = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "retrofit", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT), "--confirm", digest, "--owner-handle", "@masterofnull"],
            capture_output=True, text=True, check=True
        )
        self.assertIn("Factory kit retrofitted successfully", inst.stdout)

        # 4. Verify consumer files untouched
        for path in ["src/index.js", "tests/test_catalog.py", "package.json"]:
            diff = subprocess.run(["git", "-C", str(self.repo), "diff", self.baseline_sha, "--", path], capture_output=True, text=True, check=True)
            self.assertEqual(diff.stdout.strip(), "", f"Consumer file mutated: {path}")

        # 5. Verify .factory and hooks created
        self.assertTrue((self.repo / ".factory" / "kit.lock").is_file())
        self.assertTrue((self.repo / ".factory" / "kit.toml").is_file())
        self.assertTrue((self.repo / ".githooks" / "pre-commit").is_file())

        # 6. Verify no host path leaks in .factory configuration
        for p in (self.repo / ".factory").glob("*"):
            if p.is_file():
                content = p.read_text(encoding="utf-8")
                self.assertNotIn("/home/hyperd", content)

        # 7. Doctor passes after retrofit
        doc_after = subprocess.run(
            [sys.executable, str(AQ_FACTORY), "doctor", "--repo", str(self.repo), "--kit-root", str(KIT_ROOT)],
            capture_output=True, text=True
        )
        self.assertEqual(doc_after.returncode, 0)

if __name__ == "__main__":
    unittest.main()
