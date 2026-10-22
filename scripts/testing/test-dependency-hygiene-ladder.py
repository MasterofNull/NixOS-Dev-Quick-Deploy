#!/usr/bin/env python3
"""Regression test for gate-triggered dependency hygiene ladder (W7-S1)."""
import subprocess
import unittest
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestDependencyHygieneLadder(unittest.TestCase):
    def test_canon_blocks_exist(self):
        full = REPO_ROOT / "canon/blocks/dependency-hygiene.md"
        summary = REPO_ROOT / "canon/blocks/dependency-hygiene.summary.md"
        self.assertTrue(full.is_file(), f"{full} must exist")
        self.assertTrue(summary.is_file(), f"{summary} must exist")
        self.assertIn("Gate-Triggered Dependency Hygiene Ladder", full.read_text(encoding="utf-8"))
        self.assertIn("Trigger", summary.read_text(encoding="utf-8"))

    def test_canon_yaml_entry(self):
        manifest_path = REPO_ROOT / "canon/canon.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("dependency-hygiene", manifest["blocks"])
        targets = manifest["blocks"]["dependency-hygiene"]["targets"]
        target_paths = [t if isinstance(t, str) else t["path"] for t in targets]
        expected = ["AGENTS.md", "CLAUDE.md", ".agent/CODEX.md", ".agent/GEMINI.md", ".agent/LOCAL-AGENT.md", ".agent/WORKFLOW-CANON.md"]
        for exp in expected:
            self.assertIn(exp, target_paths)

    def test_canon_check_passes(self):
        res = subprocess.run(["python3", "scripts/governance/canon-compile.py", "--check"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Canon compile check failed: {res.stdout}\n{res.stderr}")

    def test_agent_instruction_parity_passes(self):
        res = subprocess.run(["bash", "scripts/governance/tier0.d/check-agent-instruction-parity.sh"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parity gate failed: {res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
