#!/usr/bin/env python3
"""Regression test for instruction line budget enforcement (w4-s4)."""
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestInstructionBudget(unittest.TestCase):
    def test_instruction_budget_script(self):
        script = REPO_ROOT / "scripts/governance/tier0.d/check-instruction-budget.sh"
        self.assertTrue(script.is_file(), f"{script} must exist")
        res = subprocess.run(["bash", str(script)], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Script failed: {res.stdout}\n{res.stderr}")
        self.assertIn("All instruction files are within line budget", res.stdout)

    def test_individual_files_under_200_lines(self):
        files = [
            REPO_ROOT / "CLAUDE.md",
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / ".agent/CODEX.md",
            REPO_ROOT / ".agent/GEMINI.md",
            REPO_ROOT / ".agent/LOCAL-AGENT.md",
        ]
        for f in files:
            self.assertTrue(f.is_file(), f"{f} must exist")
            lines = len(f.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 200, f"{f.name} exceeds 200 lines ({lines} lines)")


if __name__ == "__main__":
    unittest.main()
