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
ROOT = CLI.parents[2]
HOOK_GUARDS = [
    "scripts/governance/check-repo-allowlist-integrity.sh",
    "scripts/governance/check-root-file-hygiene.sh",
    "scripts/governance/check-generated-artifact-hygiene.sh",
    "scripts/governance/check-doc-links.sh",
    "scripts/governance/check-doc-metadata-standards.sh",
    "scripts/governance/check-doc-script-path-migration.sh",
    "scripts/governance/check-script-shim-consistency.sh",
    "scripts/governance/check-archive-path-consistency.sh",
    "scripts/governance/check-legacy-deprecated-root.sh",
]


class GreenlightTests(unittest.TestCase):
    def setUp(self) -> None:
        # A caller's hook environment or options must not steer the disposable repositories.
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        for key in list(os.environ):
            if key.startswith(("GIT_", "AQ_GREENLIGHT_")) or key in (
                    "SKIP_SECRET_SCAN", "SKIP_CVE_SCAN", "AQ_DELEGATE_HANDBACK"):
                del os.environ[key]
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

    def verify(self, *args: str, env: dict[str, str] | None = None
               ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), str(self.root), "--state-dir", str(self.state),
             "--verify", "--audit", *args],
            capture_output=True, text=True,
            env=os.environ | {"AQ_USAGE_TELEMETRY": "0"} | (env or {}),
        )

    def greenlight_slice(self) -> str:
        self.write("slice", "staged\n")
        self.git("add", ".")
        process = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return self.record()["main_sha"]

    def advance_base(self, name: str, remove: str | None = None,
                     content: str | None = None) -> None:
        """Add one commit to origin/main without touching the slice branch or its index."""
        env = os.environ | {"GIT_INDEX_FILE": str(Path(self.temp.name) / "base-index")}

        def plumbing(*args: str, data: str = "") -> str:
            return subprocess.run(["git", "-C", str(self.root), *args], input=data, env=env,
                                  check=True, capture_output=True, text=True).stdout.strip()

        plumbing("read-tree", "origin/main")
        if remove:
            plumbing("update-index", "--force-remove", remove)
        blob = plumbing("hash-object", "-w", "--stdin", data=content or f"{name}\n")
        plumbing("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
        commit = plumbing("commit-tree", plumbing("write-tree"), "-p", "origin/main",
                          data="advance base\n")
        plumbing("update-ref", "refs/remotes/origin/main", commit)

    def audit_rows(self) -> list[dict[str, Any]]:
        log = self.state / "audit.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def assert_rejected(self, process: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertNotEqual(process.returncode, 0, process.stdout)
        self.assertNotIn("accepted", process.stdout)
        self.assertIn(message, process.stderr)
        self.assertNotIn("Traceback", process.stderr)

    def test_j3_accept_prints_and_audits(self) -> None:
        main = self.greenlight_slice()
        self.assertEqual(self.audit_rows(), [])
        path = next(self.state.glob("*.json"))
        for count in (1, 2):
            process = self.verify()
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout, f"greenlight {path.stem} accepted\n")
            self.assertEqual(len(self.audit_rows()), count)
        row = self.audit_rows()[0]
        self.assertEqual(set(row), {"at", "branch", "staged_tree_sha", "parent_sha",
                                    "main_sha", "record_path", "gate_list"})
        self.assertEqual(
            (row["branch"], row["staged_tree_sha"], row["parent_sha"], row["main_sha"]),
            ("feat/x/y", self.git("write-tree"), self.git("rev-parse", "HEAD"), main))
        self.assertEqual(row["record_path"], str(path))
        self.assertEqual(row["gate_list"], self.record()["gate_list"])
        self.assertEqual((self.state / "audit.jsonl").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.invoke("--verify").returncode, 0)
        self.assertEqual(len(self.audit_rows()), 2, "--verify without --audit must not log")

    def test_j3_edit_invalidates(self) -> None:
        self.greenlight_slice()
        self.write("slice", "edited\n")
        self.assert_rejected(self.verify(), "unstaged")
        self.git("add", ".")
        self.assert_rejected(self.verify(), self.git("write-tree"))
        self.assertEqual(self.audit_rows(), [])

    def test_freshness_commit_bound(self) -> None:
        self.greenlight_slice()
        for number in range(20):
            self.advance_base(f"notes-{number}")
        self.assertEqual(self.verify().returncode, 0, "exactly the default bound is fresh")
        self.advance_base("notes-20")
        self.assert_rejected(self.verify(), "stale greenlight: base advanced 21 commits (max 20)")
        self.assertEqual(self.verify("--max-behind", "21").returncode, 0)
        env = {"AQ_GREENLIGHT_MAX_BEHIND": "21"}
        self.assertEqual(self.verify(env=env).returncode, 0)
        self.assert_rejected(self.verify("--max-behind", "20", env=env), "stale greenlight")
        self.assertEqual(len(self.audit_rows()), 3)
        self.assertNotEqual(self.invoke("--show").returncode, 0)

    def test_max_behind_must_be_positive(self) -> None:
        self.greenlight_slice()
        for value in ("0", "-1", "many"):
            with self.subTest(value=value):
                self.assert_rejected(self.verify(env={"AQ_GREENLIGHT_MAX_BEHIND": value}),
                                     "positive integer")
        self.assert_rejected(self.verify("--max-behind", "0"), "positive integer")
        self.assertEqual(self.audit_rows(), [])

    def test_f13_gate_covered_base_change_is_stale(self) -> None:
        main = self.greenlight_slice()
        for name in ("config/foo.json", "scripts/governance/gate.sh", "scripts/testing/test.py",
                     "nix/module.nix", ".githooks/pre-push"):
            with self.subTest(name=name):
                self.git("update-ref", "refs/remotes/origin/main", main)
                self.advance_base(name)
                self.assert_rejected(self.verify(), f"gate-listed path changed on base: {name}")
        self.assertEqual(self.audit_rows(), [])

    def test_f13_move_out_of_covered_path_is_stale(self) -> None:
        self.advance_base("config/moved.json")
        self.greenlight_slice()
        # Identical content under a new name is what rename detection would collapse.
        self.advance_base("docs/moved.json", remove="config/moved.json",
                          content="config/moved.json\n")
        self.assert_rejected(self.verify(), "gate-listed path changed on base: config/moved.json")

    def test_non_gate_base_change_stays_fresh(self) -> None:
        self.greenlight_slice()
        self.advance_base("README.md")
        process = self.verify()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("accepted", process.stdout)

    def test_base_ref_environment_override(self) -> None:
        self.greenlight_slice()
        self.git("update-ref", "refs/heads/other-base", "origin/main")
        self.advance_base("config/foo.json")
        self.assert_rejected(self.verify(), "gate-listed path")
        self.assertEqual(
            self.verify(env={"AQ_GREENLIGHT_BASE_REF": "other-base"}).returncode, 0)

    def test_rewritten_base_and_forged_main_are_rejected(self) -> None:
        self.greenlight_slice()
        path = next(self.state.glob("*.json"))
        valid = self.record()
        for forged in ("--output=x", "origin/main", None):
            with self.subTest(forged=forged):
                path.write_text(json.dumps(valid | {"main_sha": forged}))
                self.assert_rejected(self.verify(), "main_sha is not a commit id")
        path.write_text(json.dumps(valid))
        unrelated = self.git("commit-tree", "origin/main^{tree}", "-m", "rewritten")
        self.git("update-ref", "refs/remotes/origin/main", unrelated)
        self.assert_rejected(self.verify(), "not an ancestor")

    def test_foreign_commit_index_is_rejected(self) -> None:
        self.greenlight_slice()
        index = Path(self.temp.name) / "other-index"
        env = {"GIT_INDEX_FILE": str(index)}
        subprocess.run(["git", "-C", str(self.root), "read-tree", "HEAD"], check=True,
                       env=os.environ | env, capture_output=True)
        self.assert_rejected(self.verify(env=env), "Index being committed does not match")
        self.assertEqual(
            self.verify(env={"GIT_INDEX_FILE": str(self.root / ".git/index")}).returncode, 0)

    def test_unwritable_audit_log_fails_closed(self) -> None:
        self.greenlight_slice()
        (self.state / "audit.jsonl").mkdir()
        self.assert_rejected(self.verify(), "audit.jsonl")

    def test_audit_requires_verify(self) -> None:
        process = self.invoke("--audit")
        self.assertEqual(process.returncode, 2)
        self.assertIn("--audit requires --verify", process.stderr)

    def install_hook(self) -> Path:
        """Commit the real hook and verifier, with logging stubs for every other check."""
        calls = Path(self.temp.name) / "calls.log"
        for name in (".githooks/pre-commit", "scripts/ai/aq-greenlight",
                     "scripts/ai/lib/greenlight.py"):
            self.write(name, (ROOT / name).read_text())
            (self.root / name).chmod(0o755)
        self.write("scripts/ai/lib/integration_guard.py", "")
        self.write(".gitignore", "__pycache__/\n")
        for name in [*HOOK_GUARDS, "scripts/governance/repo-structure-lint.sh",
                     "scripts/governance/lint-color-echo-usage.sh",
                     "scripts/governance/run-focused-ci-checks.sh"]:
            self.write(name, f"#!/bin/sh\necho {Path(name).name} >> {shlex.quote(str(calls))}\n")
            (self.root / name).chmod(0o755)
        gitleaks = Path(self.temp.name) / "bin/gitleaks"
        gitleaks.parent.mkdir()
        gitleaks.write_text(f"#!/bin/sh\necho gitleaks >> {shlex.quote(str(calls))}\n")
        gitleaks.chmod(0o755)
        self.git("add", ".")
        self.git("commit", "-m", "install hook")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("config", "core.hooksPath", ".githooks")
        os.environ.update(PATH=f"{gitleaks.parent}{os.pathsep}{os.environ['PATH']}",
                          AQ_GREENLIGHT_DIR=str(self.state), AQ_USAGE_TELEMETRY="0")
        return calls

    def commit(self, calls: Path, *args: str, env: dict[str, str] | None = None
               ) -> tuple[str, list[str]]:
        calls.write_text("")
        process = subprocess.run(["git", "-C", str(self.root), "commit", "-m", "slice", *args],
                                 capture_output=True, text=True, env=os.environ | (env or {}))
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        ran = calls.read_text().split()
        for guard in ("gitleaks", "lint-color-echo-usage.sh", "repo-structure-lint.sh",
                      *(Path(name).name for name in HOOK_GUARDS)):
            self.assertIn(guard, ran, "security/structure guards must always run")
        return process.stdout + process.stderr, ran

    def test_hook_accepts_greenlight_but_runs_guards(self) -> None:
        calls = self.install_hook()
        self.greenlight_slice()
        stem = next(self.state.glob("*.json")).stem
        output, ran = self.commit(calls)
        self.assertIn(f"greenlight {stem} accepted", output)
        self.assertNotIn("run-focused-ci-checks.sh", ran)
        self.assertEqual(len(self.audit_rows()), 1)

    def test_hook_runs_focused_ci_after_edit(self) -> None:
        calls = self.install_hook()
        self.greenlight_slice()
        self.write("slice", "edited\n")
        self.git("add", ".")
        output, ran = self.commit(calls)
        self.assertNotIn("accepted", output)
        self.assertIn("run-focused-ci-checks.sh", ran)
        self.assertEqual(self.audit_rows(), [])

    def test_hook_fallbacks_run_focused_ci(self) -> None:
        calls = self.install_hook()
        for label, env in [("disabled", {"AQ_GREENLIGHT_DISABLE": "1"}),
                           ("no base ref", {"AQ_GREENLIGHT_BASE_REF": "missing-ref"}),
                           ("verifier error", {"AQ_GREENLIGHT_MAX_BEHIND": "0"})]:
            with self.subTest(case=label):
                self.write("slice", f"{label}\n")
                self.git("add", ".")
                self.assertEqual(self.invoke().returncode, 0)
                output, ran = self.commit(calls, env=env)
                self.assertNotIn("accepted", output)
                self.assertIn("run-focused-ci-checks.sh", ran)
                for path in self.state.glob("*.json"):
                    path.unlink()
        self.assertEqual(self.audit_rows(), [])

    def test_hook_rejects_partial_commit(self) -> None:
        calls = self.install_hook()
        self.write("other", "second\n")
        self.greenlight_slice()
        output, ran = self.commit(calls, "--", "slice")
        self.assertNotIn("accepted", output)
        self.assertIn("run-focused-ci-checks.sh", ran)
        self.assertEqual(self.audit_rows(), [])

    def test_hook_blocks_commit_when_focused_ci_fails(self) -> None:
        self.install_hook()
        self.write("scripts/governance/run-focused-ci-checks.sh", "#!/bin/sh\nexit 1\n")
        self.git("add", ".")
        head = self.git("rev-parse", "HEAD")
        process = subprocess.run(["git", "-C", str(self.root), "commit", "-m", "blocked"],
                                 capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("focused CI-sensitive checks failed", process.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)


if __name__ == "__main__":
    unittest.main()
