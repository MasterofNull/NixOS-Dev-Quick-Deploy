#!/usr/bin/env python3
"""Phase-0 ignored-state checks must validate the primary Git checkout."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

from harness_qa.phases import phase0  # noqa: E402
from harness_qa.core.result import Status  # noqa: E402


class WorktreeStateTests(unittest.TestCase):
    def test_primary_state_is_authoritative(self):
        with tempfile.TemporaryDirectory() as temporary:
            primary = Path(temporary) / "primary"
            worktree = Path(temporary) / "delegate"
            primary.mkdir()

            def git(*args):
                subprocess.run(
                    ["git", "-C", str(primary), *args], check=True,
                    capture_output=True, text=True,
                )

            git("init")
            (primary / ".gitignore").write_text(
                ".agent/collaboration/\n.agents/improvement/\n", encoding="utf-8",
            )
            (primary / "data").mkdir()
            (primary / "data/harness-golden-evals.json").write_text(
                json.dumps({"cases": [{}] * 15}), encoding="utf-8",
            )
            git("add", ".gitignore", "data/harness-golden-evals.json")
            git("-c", "user.name=QA", "-c", "user.email=qa@example.invalid",
                "-c", "core.hooksPath=/dev/null", "commit", "-m", "test: fixture")
            git("worktree", "add", "--detach", str(worktree))

            valid = {
                ".agent/collaboration/PULSE.log":
                    "[2026-10-07T15:00:00Z] [codex] [write]: fixture — valid\n",
                ".agent/collaboration/RESUME.json": json.dumps({
                    "current_objective": "fixture", "phase": "VALIDATE",
                    "todo_snapshot": [], "uncommitted_changes": [], "resume_hint": "test",
                }),
                ".agents/improvement/candidates.json": json.dumps({
                    "candidates": [{"trust_score": 1}],
                }),
            }
            ids = {"0.152.3", "0.152.4", "0.152.9"}

            def check(root, expected):
                previous = Path.cwd()
                try:
                    os.chdir(root)
                    results = phase0._check_golden_eval_parity(SimpleNamespace(repo_root=root))
                finally:
                    os.chdir(previous)
                rows = {r.id: r.status for r in results if r.id in ids}
                self.assertEqual(rows, dict.fromkeys(ids, expected))
                # Tracked contracts must still come from the checkout under test.
                self.assertEqual(next(r.status for r in results if r.id == "0.152.2"), Status.FAIL)

            for relative, content in valid.items():
                path = primary / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                self.assertFalse((worktree / relative).exists())
            check(primary, Status.PASS)
            check(worktree, Status.PASS)

            # A local valid copy must not mask malformed or absent primary state.
            for relative, content in valid.items():
                shadow = worktree / relative
                shadow.parent.mkdir(parents=True, exist_ok=True)
                shadow.write_text(content, encoding="utf-8")
            malformed = ["invalid pulse\n", "{}", '{"candidates":[{"trust_score":0}]}']
            for relative, content in zip(valid, malformed):
                (primary / relative).write_text(content, encoding="utf-8")
            check(primary, Status.FAIL)
            check(worktree, Status.FAIL)
            for relative in valid:
                (primary / relative).write_text("{invalid", encoding="utf-8")
            check(worktree, Status.FAIL)
            for relative in valid:
                path = primary / relative
                path.rename(path.with_name(path.name + ".archived"))
            check(primary, Status.FAIL)
            check(worktree, Status.FAIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
