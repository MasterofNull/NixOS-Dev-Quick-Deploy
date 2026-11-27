#!/usr/bin/env python3
"""Acceptance journeys for aq-greenlight using real disposable Git repositories."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Any

CLI = Path(__file__).resolve().parents[1] / "ai/aq-greenlight"


class GreenlightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.state = Path(self.temp.name) / "state"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@localhost")
        self.write("base", "initial\n")
        self.git("add", ".")
        self.git("commit", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-b", "feat/x/y")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name: str, content: str) -> None:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def snapshot(self) -> tuple[str, str, str, str]:
        return (self.git("rev-parse", "HEAD"), self.git("write-tree"),
                self.git("symbolic-ref", "HEAD"), self.git("status", "--porcelain"))

    def invoke(self, *args: str, tier: str | None = None) -> subprocess.CompletedProcess[str]:
        before = self.snapshot()
        process = subprocess.run(
            [sys.executable, str(CLI), str(self.root), "--state-dir", str(self.state),
             "--json", "--gate-cmd", f"tier0_pre_commit={tier or shlex.quote(sys.executable) + ' -c pass'}",
             "--gate-cmd", "ci_test_coverage=" + shlex.quote(sys.executable) + " -c pass", *args],
            capture_output=True, text=True, env=os.environ | {"AQ_USAGE_LOG": os.devnull},
        )
        self.assertEqual(before, self.snapshot(), process.stdout + process.stderr)
        self.assertEqual(len(self.git("worktree", "list", "--porcelain").split("worktree ")) - 1, 1)
        return process

    def record(self) -> dict[str, Any]:
        paths = list(self.state.glob("*.json"))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text())

    def test_j1_missing_evidence_sections(self) -> None:
        self.write("docs/harness-first/evidence/slice.md",
                   "\n".join(f"## {n}. Section" for n in range(1, 7)))
        self.git("add", ".")
        process = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("## 7", process.stdout)
        self.assertIn("## 8", process.stdout)
        self.assertFalse(self.record()["passed"])

    def test_j2_conflict(self) -> None:
        self.write("base", "main\n")
        self.git("add", ".")
        self.git("commit", "-m", "main change")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("reset", "--hard", "HEAD~1")
        self.write("base", "slice\n")
        self.git("add", ".")
        process = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("base", self.record()["results"]["merge"]["detail"])

    def test_j6_committed_shellcheck_error_is_staged(self) -> None:
        self.assertIsNotNone(shutil.which("shellcheck"), "J6 requires real shellcheck")
        self.write("broken.sh", '#!/bin/sh\necho "$unassigned_variable"\n')
        self.git("add", ".")
        self.git("commit", "-m", "slice with shell error")
        gate = "bash -c " + shlex.quote(
            "git diff --cached --name-only -- '*.sh' | "
            "while IFS= read -r name; do shellcheck --format=gcc \"$name\" || exit; done")
        process = self.invoke(tier=gate)
        self.assertNotEqual(process.returncode, 0, process.stdout)
        self.assertIn("broken.sh", self.record()["results"]["tier0_pre_commit"]["detail"])

    def test_f1_dirty_and_untracked(self) -> None:
        self.write("base", "unstaged\n")
        self.assertIn("unstaged", self.invoke().stdout)
        self.git("add", ".")
        self.write("untracked", "new\n")
        self.assertIn("untracked", self.invoke().stdout)

    def test_f6_optional_body(self) -> None:
        body = Path(self.temp.name) / "body.md"
        body.write_text("## Details\n## What\n## How\n")
        self.assertNotEqual(self.invoke("--body-file", str(body)).returncode, 0)
        self.assertIn("## Why", self.record()["results"]["pr_body_format"]["detail"])
        body.write_text("## Why\n## Details\n## What\n## How\n")
        self.assertNotEqual(self.invoke("--body-file", str(body)).returncode, 0)
        body.write_text("## Details\n## What\n## How\n## Why\n")
        self.assertEqual(self.invoke("--body-file", str(body)).returncode, 0)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertNotIn("pr_body_format", self.record()["results"])

    def test_f2_f12_record_and_verification(self) -> None:
        self.write("slice", "staged\n")
        self.git("add", ".")
        self.assertEqual(self.invoke().returncode, 0)
        record = self.record()
        self.assertEqual(set(record), {"schema", "branch", "staged_tree_sha", "parent_sha",
                                      "main_sha", "merged_tree_sha", "gate_list", "results",
                                      "passed", "tool_version", "at"})
        path = next(self.state.glob("*.json"))
        self.assertTrue(path.name.startswith("feat%2Fx%2Fy-"))
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(record["staged_tree_sha"], self.git("write-tree"))
        self.assertEqual(record["parent_sha"], self.git("rev-parse", "HEAD"))
        self.assertEqual(record["main_sha"], self.git("rev-parse", "origin/main"))
        self.assertEqual(self.invoke("--verify").returncode, 0)
        self.assertEqual(self.invoke("--show").returncode, 0)
        self.git("commit", "-m", "same tree different parent")
        self.assertNotEqual(self.invoke("--verify").returncode, 0)
        self.write("slice", "edited\n")
        self.assertNotEqual(self.invoke("--verify").returncode, 0)
        self.git("add", ".")
        self.assertNotEqual(self.invoke("--verify").returncode, 0)

    def test_clean_merge_runs_on_incoming_main(self) -> None:
        self.write("upstream", "incoming\n")
        self.git("add", ".")
        self.git("commit", "-m", "incoming")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("reset", "--hard", "HEAD~1")
        self.write("slice", "slice\n")
        self.git("add", ".")
        gate = shlex.join([sys.executable, "-c",
                           "from pathlib import Path; assert Path('upstream').read_text() == 'incoming\\n'"])
        process = self.invoke(tier=gate)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertNotEqual(self.record()["merged_tree_sha"], self.git("write-tree"))


if __name__ == "__main__":
    unittest.main()
