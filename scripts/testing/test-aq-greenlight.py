#!/usr/bin/env python3
"""Acceptance journeys for aq-greenlight using real disposable Git repositories."""
from __future__ import annotations

import hashlib
import importlib.util
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
from unittest.mock import patch

EVIDENCE_HEADINGS = [
    "## Objective", "## Workflow/Session IDs", "## Delegation Decision",
    "## Commands Executed", "## Validation Evidence", "## Rollback Plan",
    "## Residual Risk", "## Hint Feedback",
]

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

    def invoke(self, *args: str, tier: str | None = None,
               env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        before = self.snapshot()
        process = subprocess.run(
            [sys.executable, str(CLI), str(self.root), "--state-dir", str(self.state),
             "--json", "--gate-cmd", f"tier0_pre_commit={tier or shlex.quote(sys.executable) + ' -c pass'}",
             "--gate-cmd", "ci_test_coverage=" + shlex.quote(sys.executable) + " -c pass", *args],
            capture_output=True, text=True, env=os.environ | (env or {}) | {"AQ_USAGE_TELEMETRY": "0"},
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
                   "\n".join(EVIDENCE_HEADINGS[:6]))
        self.git("add", ".")
        process = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("## Residual Risk", process.stdout)
        self.assertIn("## Hint Feedback", process.stdout)
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
        body.write_text("## Details\nContext\n## What\nChange\n## How\nSteps\n## Why\nReason\n")
        self.assertEqual(self.invoke("--body-file", str(body)).returncode, 0)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertNotIn("pr_body_format", self.record()["results"])

    def test_body_format_matches_shared_validator(self) -> None:
        body = Path(self.temp.name) / "body.md"
        valid = "## Details\nContext\n## What\nChange\n## How\nSteps\n## Why\nReason\n"
        for content, message in [
            (valid.replace("Change\n", ""), "'## What' has no content"),
            (valid + "## What\nDuplicate\n", "exactly once"),
            ("# Intro\n" + valid, "first markdown heading"),
            ("```markdown\n" + valid + "```\n", "## Details"),
        ]:
            with self.subTest(message=message):
                body.write_text(content)
                process = self.invoke("--body-file", str(body))
                self.assertNotEqual(process.returncode, 0, process.stdout)
                self.assertIn(message, self.record()["results"]["pr_body_format"]["detail"])
        body.write_text(valid + "```markdown\n## What\n```\n")
        self.assertEqual(self.invoke("--body-file", str(body)).returncode, 0)

    def test_evidence_canonical_and_policy_headings(self) -> None:
        name = "docs/harness-first/evidence/slice.md"
        self.write(name, "\n".join(EVIDENCE_HEADINGS))
        self.git("add", ".")
        self.assertEqual(self.invoke().returncode, 0)
        self.write(name, "\n".join(f"## {n}. Section" for n in range(1, 9)))
        self.git("add", ".")
        process = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        for heading in EVIDENCE_HEADINGS:
            self.assertIn(heading, process.stdout)
        self.write("config/harness-first-policy.json", json.dumps({
            "required_evidence_sections": EVIDENCE_HEADINGS + ["## Extra policy section"],
        }))
        self.write(name, "\n".join(EVIDENCE_HEADINGS))
        self.git("add", ".")
        self.assertIn("## Extra policy section", self.invoke().stdout)
        self.write(name, "\n".join(EVIDENCE_HEADINGS + ["## Extra policy section"]))
        self.git("add", ".")
        self.assertEqual(self.invoke().returncode, 0)

    def test_caller_git_environment_is_isolated(self) -> None:
        self.write("slice", "staged\n")
        self.git("add", ".")
        index = self.root / ".git/index"
        self.snapshot()
        before = index.read_bytes()
        locators = {
            "GIT_DIR": str(self.root / ".git"),
            "GIT_WORK_TREE": str(self.root),
            "GIT_INDEX_FILE": str(index),
            "GIT_COMMON_DIR": str(self.root / ".git"),
            "GIT_OBJECT_DIRECTORY": str(self.root / ".git/objects"),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(self.root / ".git/objects"),
            "GIT_PREFIX": "caller/", "GIT_SUPER_PREFIX": "caller/",
        }
        gate = shlex.join([sys.executable, "-c",
                           "import os, subprocess; from pathlib import Path; "
                           f"assert not set({list(locators)!r}) & os.environ.keys(); "
                           "root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], "
                           "text=True).strip(); "
                           f"assert Path(root) != Path({str(self.root)!r}); "
                           "assert Path('slice').read_text() == 'staged\\n'"])
        process = self.invoke(tier=gate, env=locators)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(index.read_bytes(), before)

    def test_invalid_records_fail_cleanly(self) -> None:
        self.assertEqual(self.invoke().returncode, 0)
        path = next(self.state.glob("*.json"))
        valid = self.record()
        for record in [[], None, {}, valid | {"passed": "yes"},
                       valid | {"results": []}, valid | {"results": {"gate": {}}}]:
            for mode in ["--show", "--verify"]:
                with self.subTest(record=record, mode=mode):
                    path.write_text(json.dumps(record))
                    process = self.invoke(mode)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertIn("Invalid greenlight record", process.stdout)
                    self.assertNotIn("Traceback", process.stderr)

    def test_verify_rejects_tampered_success(self) -> None:
        self.assertEqual(self.invoke().returncode, 0)
        path = next(self.state.glob("*.json"))
        valid = self.record()
        for entry, code in [("cleanup", 1), ("runner", 1),
                            ("tier0_pre_commit", False), ("cleanup", False)]:
            with self.subTest(entry=entry, code=code):
                record = valid | {"results": valid["results"] | {
                    entry: {"status": "PASS", "exit_code": code, "detail": "tampered"},
                }}
                path.write_text(json.dumps(record))
                self.assertNotEqual(self.invoke("--verify").returncode, 0)
        path.write_text(json.dumps(valid | {"passed": False}))
        self.assertNotEqual(self.invoke("--verify").returncode, 0)

    def test_verify_rejects_failed_status_with_zero_exit(self) -> None:
        self.assertEqual(self.invoke().returncode, 0)
        path = next(self.state.glob("*.json"))
        valid = self.record()
        for entry in ("tier0_pre_commit", "cleanup"):
            with self.subTest(entry=entry):
                path.write_text(json.dumps(valid | {"results": valid["results"] | {
                    entry: {"status": "FAIL", "exit_code": 0, "detail": "tampered"},
                }}))
                process = self.invoke("--verify")
                self.assertNotEqual(process.returncode, 0)
                self.assertIn("declared gates did not all pass", process.stdout)

    def test_verify_binds_body_digest(self) -> None:
        body = Path(self.temp.name) / "valid.md"
        original = "## Details\nContext\n## What\nChange\n## How\nSteps\n## Why\nReason\n"
        body.write_text(original)
        self.assertEqual(self.invoke("--body-file", str(body)).returncode, 0)
        valid = self.record()
        self.assertEqual(valid["body_sha256"], hashlib.sha256(body.read_bytes()).hexdigest())
        self.assertEqual(self.invoke("--verify", "--body-file", str(body)).returncode, 0)
        other = Path(self.temp.name) / "other.md"
        other.write_text(original.replace("Reason", "Another reason"))
        body.write_text(original.replace("Change", "Edited change"))
        path = next(self.state.glob("*.json"))
        missing = {key: value for key, value in valid.items() if key != "body_sha256"}
        for label, candidate, record in [("edited", body, valid), ("different", other, valid),
                                         ("missing digest", body, missing)]:
            with self.subTest(case=label):
                path.write_text(json.dumps(record))
                process = self.invoke("--verify", "--body-file", str(candidate))
                self.assertNotEqual(process.returncode, 0)
                self.assertIn("body digest does not match", process.stdout)

    def test_missing_ci_coverage_gate_fails_closed(self) -> None:
        process = subprocess.run(
            [sys.executable, str(CLI), str(self.root), "--state-dir", str(self.state), "--json",
             "--gate-cmd", "tier0_pre_commit=" + shlex.quote(sys.executable) + " -c pass"],
            capture_output=True, text=True, env=os.environ | {"AQ_USAGE_TELEMETRY": "0"},
        )
        self.assertNotEqual(process.returncode, 0, process.stdout + process.stderr)
        record = self.record()
        self.assertFalse(record["passed"])
        self.assertEqual(record["results"]["ci_test_coverage"], {
            "status": "FAIL", "exit_code": 1, "detail": "Missing required gate script: "
            "scripts/governance/tier0.d/check-ci-test-coverage.sh",
        })
        self.assertNotEqual(self.invoke("--verify").returncode, 0)

    def test_verify_requires_all_requested_gates(self) -> None:
        self.assertEqual(self.invoke().returncode, 0)
        path = next(self.state.glob("*.json"))
        valid = self.record()
        path.write_text(json.dumps(valid | {"gate_list": ["tier0_pre_commit"]}))
        self.assertNotEqual(self.invoke("--verify").returncode, 0)
        path.write_text(json.dumps(valid))
        body = Path(self.temp.name) / "body.md"
        body.write_text("## Details\nContext\n## What\nChange\n## How\nSteps\n## Why\nReason\n")
        self.assertNotEqual(self.invoke("--verify", "--body-file", str(body)).returncode, 0)
        self.assertEqual(self.invoke("--body-file", str(body)).returncode, 0)
        self.assertEqual(self.invoke("--verify", "--body-file", str(body)).returncode, 0)

    def test_throwaway_checkout_disables_hooks(self) -> None:
        marker = Path(self.temp.name) / "post-checkout-marker"
        hooks = Path(self.temp.name) / "hooks"
        hooks.mkdir()
        hook = hooks / "post-checkout"
        hook.write_text("#!/bin/sh\ntouch " + shlex.quote(str(marker)) + "\n")
        hook.chmod(0o700)
        self.git("config", "core.hooksPath", str(hooks))
        self.assertEqual(self.invoke().returncode, 0)
        self.assertFalse(marker.exists())
        self.git("checkout", "--detach", "HEAD")
        self.assertTrue(marker.exists(), "hook fixture must execute when hooks are enabled")

    def test_read_only_modes_do_not_create_state_directory(self) -> None:
        for mode in ("--show", "--verify"):
            with self.subTest(mode=mode):
                self.assertFalse(self.state.exists())
                self.assertNotEqual(self.invoke(mode).returncode, 0)
                self.assertFalse(self.state.exists())

    def test_aborted_gate_cannot_pass_or_verify(self) -> None:
        spec = importlib.util.spec_from_file_location("greenlight", CLI.parent / "lib/greenlight.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for error in (RuntimeError("gate aborted"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                before = self.snapshot()
                with patch.object(module, "evidence", side_effect=error):
                    with self.assertRaises(type(error)):
                        module.run(self.root, state_dir=str(self.state), overrides={
                            "tier0_pre_commit": shlex.join([sys.executable, "-c", "pass"]),
                        })
                self.assertEqual(before, self.snapshot())
                record = self.record()
                self.assertEqual(record["results"]["tier0_pre_commit"]["exit_code"], 0)
                self.assertFalse(record["passed"])
                for gate in ("evidence_sections", "ci_test_coverage"):
                    self.assertNotEqual(record["results"][gate]["exit_code"], 0)
                self.assertNotEqual(self.invoke("--verify").returncode, 0)
                record["passed"] = True
                record["results"].pop("evidence_sections")
                next(self.state.glob("*.json")).write_text(json.dumps(record))
                process = self.invoke("--verify")
                self.assertNotEqual(process.returncode, 0)
                self.assertIn("declared gates did not all pass", process.stdout)

    def test_empty_xdg_state_home_uses_home(self) -> None:
        home = Path(self.temp.name) / "home"
        home.mkdir()
        process = subprocess.run(
            [sys.executable, str(CLI), str(self.root), "--json",
             "--gate-cmd", "tier0_pre_commit=" + shlex.quote(sys.executable) + " -c pass",
             "--gate-cmd", "ci_test_coverage=" + shlex.quote(sys.executable) + " -c pass"],
            capture_output=True, text=True,
            env=os.environ | {"HOME": str(home), "XDG_STATE_HOME": "",
                              "AQ_GREENLIGHT_DIR": "", "AQ_USAGE_TELEMETRY": "0"},
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(len(list((home / ".local/state/aq/greenlight").glob("*.json"))), 1)

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
