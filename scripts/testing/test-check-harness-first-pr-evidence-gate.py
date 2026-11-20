#!/usr/bin/env python3
"""Hermetic tests for check-harness-first-pr-evidence-gate.sh."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "testing" / "check-harness-first-pr-evidence-gate.sh"


class TestHarnessFirstPREvidenceGate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test-hf-gate-")
        self.repo = Path(self.temp_dir)
        # Initialize test git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=self.repo, check=True)

        # Setup required config files
        config_dir = self.repo / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "harness-first-high-impact-paths.txt").write_text(
            "nix/modules/core/options.nix\nscripts/ai/aq-report\nrequirements.txt\n",
            encoding="utf-8",
        )
        policy = {
            "required_evidence_sections": [
                "## Objective",
                "## Workflow/Session IDs",
                "## Delegation Decision",
                "## Commands Executed",
                "## Validation Evidence",
                "## Rollback Plan",
                "## Residual Risk",
                "## Hint Feedback",
            ],
            "dependabot_manifest_exemption": {
                "author": "dependabot[bot]",
                "manifest_globs": ["requirements*.txt", "*.lock", ".github/workflows/*.yml"],
            },
        }
        (config_dir / "harness-first-policy.json").write_text(json.dumps(policy), encoding="utf-8")

        # Initial commit on main
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.repo, check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_gate(self, env_overrides=None):
        env = os.environ.copy()
        env["ROOT"] = str(self.repo)
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_main_branch_skips(self):
        res = self._run_gate()
        self.assertEqual(res.returncode, 0)
        self.assertIn("skipping harness-first PR evidence gate", res.stdout)

    def test_feature_branch_no_high_impact_changes(self):
        subprocess.run(["git", "checkout", "-b", "feat/regular-change"], cwd=self.repo, check=True)
        test_file = self.repo / "docs" / "some-note.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("just a doc", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "add note"], cwd=self.repo, check=True, capture_output=True)

        res = self._run_gate({"BASE_REF": "main"})
        self.assertEqual(res.returncode, 0)
        self.assertIn("no high-impact path changes; evidence file not required", res.stdout)

    def test_feature_branch_high_impact_missing_evidence_fails(self):
        subprocess.run(["git", "checkout", "-b", "feat/high-impact"], cwd=self.repo, check=True)
        hi_file = self.repo / "nix" / "modules" / "core" / "options.nix"
        hi_file.parent.mkdir(parents=True, exist_ok=True)
        hi_file.write_text("# options change", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "modify options"], cwd=self.repo, check=True, capture_output=True)

        res = self._run_gate({"BASE_REF": "main"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("FAIL: high-impact paths changed but no new evidence file was added", res.stderr)

    def test_feature_branch_high_impact_with_valid_evidence_passes(self):
        subprocess.run(["git", "checkout", "-b", "feat/high-impact-with-ev"], cwd=self.repo, check=True)
        hi_file = self.repo / "nix" / "modules" / "core" / "options.nix"
        hi_file.parent.mkdir(parents=True, exist_ok=True)
        hi_file.write_text("# options change", encoding="utf-8")

        ev_file = self.repo / "docs" / "harness-first" / "evidence" / "2026-10-11-test-task.md"
        ev_file.parent.mkdir(parents=True, exist_ok=True)
        ev_content = """# Evidence
## Objective
Tested
## Workflow/Session IDs
WF-1
## Delegation Decision
Local
## Commands Executed
Test cmd
## Validation Evidence
PASS
## Rollback Plan
git revert
## Residual Risk
None
## Hint Feedback
OK
"""
        ev_file.write_text(ev_content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "modify options with evidence"], cwd=self.repo, check=True, capture_output=True)

        res = self._run_gate({"BASE_REF": "main"})
        self.assertEqual(res.returncode, 0)
        self.assertIn("harness-first PR evidence gate satisfied", res.stdout)

    def _commit_files(self, branch, files):
        subprocess.run(["git", "checkout", "-b", branch], cwd=self.repo, check=True)
        for rel in files:
            f = self.repo / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("change", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "bump"], cwd=self.repo, check=True, capture_output=True)

    def test_dependabot_manifest_only_passes(self):
        self._commit_files("dependabot/pip/x", ["requirements.txt", ".github/workflows/test.yml"])
        res = self._run_gate({"BASE_REF": "main", "PR_AUTHOR": "dependabot[bot]"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("dependabot manifest-only exemption", res.stdout)

    def test_dependabot_with_non_manifest_file_fails(self):
        self._commit_files("dependabot/pip/y", ["requirements.txt", "scripts/ai/aq-report"])
        res = self._run_gate({"BASE_REF": "main", "PR_AUTHOR": "dependabot[bot]"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("no new evidence file was added", res.stderr)

    def test_human_manifest_only_fails(self):
        self._commit_files("feat/human-bump", ["requirements.txt"])
        res = self._run_gate({"BASE_REF": "main", "PR_AUTHOR": "someone"})
        self.assertEqual(res.returncode, 1)
        res = self._run_gate({"BASE_REF": "main"})
        self.assertEqual(res.returncode, 1)

    def test_lookalike_author_fails(self):
        self._commit_files("feat/spoof", ["requirements.txt"])
        res = self._run_gate({"BASE_REF": "main", "PR_AUTHOR": "dependabot"})
        self.assertEqual(res.returncode, 1)


if __name__ == "__main__":
    unittest.main()
