#!/usr/bin/env python3
"""Admission sub-slice: refuse composition without executing or changing the target."""
from __future__ import annotations

import hashlib
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import factory_gate_install as installer

PLAN = ROOT / ".agents/plans/factory-hook-composition-20261112"
OUTPUTS = ROOT / ".agents/delegation/outputs"


def snapshot(root: Path) -> dict[str, object]:
    records: dict[str, object] = {}

    def visit(path: Path) -> None:
        info = path.lstat()
        record = [info.st_mode, info.st_mtime_ns, info.st_ctime_ns]
        if stat.S_ISLNK(info.st_mode):
            record.append(os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            record.append(hashlib.sha256(path.read_bytes()).hexdigest())
        records[str(path.relative_to(root))] = record
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)

    visit(root)
    return records


class CompositionAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        # Retain fixtures for review; delegate outputs must never use /tmp.
        self.base = Path(tempfile.mkdtemp(prefix="hook-composition-test-", dir=OUTPUTS))
        self.target = self.base / "repository"
        self.target.mkdir()
        (self.target / ".git").mkdir()
        (self.target / ".git/config").write_text("[core]\n\thooksPath = .githooks\n")
        (self.target / ".git/HEAD").write_text("ref: refs/heads/main\n")
        (self.target / ".git/index").write_bytes(b"index fixture")
        (self.target / ".githooks").mkdir()
        self.put_hook(self.target / ".githooks/pre-commit")
        self.bundle = self.base / "absent-bundle"

    def put_hook(self, path: Path) -> None:
        path.write_text("#!/bin/sh\nprintf ran > COMMAND_EXECUTED\nexit 99\n")
        path.chmod(0o755)

    def assert_refused(self, report: dict[str, object], code: str) -> None:
        self.assertFalse(report["safe_to_install"])
        self.assertFalse(report["ready"])
        self.assertIsNone(report["preview_digest"])
        self.assertEqual(report["state"], code)
        self.assertEqual(report["writes"], [])
        self.assertEqual(report["directories"], [])
        self.assertEqual(report["proof"], {"state": "NOT_RUN"})
        self.assertEqual(report["activation"], {"state": "BLOCKED"})

    def assert_all_entrypoints_refuse(self, code: str) -> None:
        before = snapshot(self.target)
        calls = (
            lambda: installer.preview(self.target, self.bundle, None, "fixture"),
            lambda: installer.retrofit_preview(self.target, self.bundle, None, "fixture"),
            lambda: installer.install(self.target, self.bundle, None, "fixture"),
            lambda: installer.retrofit_install(self.target, self.bundle, None, "fixture", "forged"),
            lambda: installer.status(self.target, self.bundle, None, "fixture"),
            lambda: installer.readiness_preflight(self.target, self.bundle, None, "fixture"),
            lambda: installer.composition_preview(self.target),
        )
        with patch.object(installer, "git", side_effect=AssertionError("Git executed")), \
             patch.object(installer.subprocess, "run", side_effect=AssertionError("command executed")):
            for call in calls:
                self.assert_refused(call(), code)
                self.assertEqual(snapshot(self.target), before)

    def test_foreign_yaml_is_refused_by_all_library_entrypoints(self) -> None:
        (self.target / ".pre-commit-config.yaml").write_text("repos: []\n")
        self.assert_all_entrypoints_refuse("FOREIGN_HOOK_MANAGER")

    def test_alternate_yaml_and_forged_ordinary_proof_cannot_grant_readiness(self) -> None:
        (self.target / ".pre-commit-config.yml").write_text("repos: []\n")
        (self.target / ".factory").mkdir()
        for name in ("gate-install.json", "gate-run-evidence.json"):
            (self.target / ".factory" / name).write_text(json.dumps({
                "schema_version": 1, "ready": True, "activation": "ACTIVE",
                "proof": {"state": "PASS"}, "hooks": {"configured_path": ".githooks"},
            }))
        self.assert_all_entrypoints_refuse("FOREIGN_HOOK_MANAGER")

    def test_missing_boundary_never_produces_confirmation(self) -> None:
        before = snapshot(self.target)
        report = installer.composition_preview(self.target)
        self.assert_refused(report, "OFFLINE_BOUNDARY_UNAVAILABLE")
        self.assertEqual(len(report["inventory_digest"]), 64)
        self.assertEqual(snapshot(self.target), before)
        (self.target / ".git/config").write_text("[core]\n\thooksPath = other\n")
        changed = installer.composition_preview(self.target)
        self.assertNotEqual(report["inventory_digest"], changed["inventory_digest"])
        self.assertIsNone(changed["preview_digest"])

    def test_receipt_quarantine_covers_corrupt_forged_links_directories_and_fifos(self) -> None:
        outside = self.base / "outside"
        outside.write_bytes(b"outside")
        for kind in ("corrupt", "forged", "symlink", "directory", "fifo"):
            with self.subTest(kind=kind):
                factory = self.target / ".factory"
                factory.mkdir()
                receipt = self.target / installer.COMPOSITION_RECEIPT
                if kind == "corrupt":
                    receipt.write_bytes(b"\xffnot-json")
                elif kind == "forged":
                    receipt.write_text('{"schema_version":1,"state":"COMPOSITION_ACTIVE"}')
                elif kind == "symlink":
                    receipt.symlink_to(outside)
                elif kind == "directory":
                    receipt.mkdir()
                else:
                    os.mkfifo(receipt)
                self.assert_all_entrypoints_refuse("COMPOSITION_RECEIPT_INVALID")
                factory.rename(self.base / ("retained-" + kind))
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_factory_parent_symlink_is_quarantined(self) -> None:
        external = self.base / "external"
        external.mkdir()
        (self.target / ".factory").symlink_to(external, target_is_directory=True)
        before = snapshot(external)
        self.assert_all_entrypoints_refuse("COMPOSITION_RECEIPT_INVALID")
        self.assertEqual(snapshot(external), before)

    def test_inventory_rejects_links_and_special_files_without_following(self) -> None:
        outside = self.base / "outside"
        outside.write_bytes(b"private")
        (self.target / ".pre-commit-config.yaml").symlink_to(outside)
        os.mkfifo(self.target / ".pre-commit-config.yml")
        before = snapshot(self.target)
        report = installer.composition_preview(self.target)
        self.assert_refused(report, "FOREIGN_HOOK_MANAGER")
        for name in (".pre-commit-config.yaml", ".pre-commit-config.yml"):
            self.assertEqual(report["inventory"][name]["state"], "UNSAFE")
        self.assertEqual(snapshot(self.target), before)

    def test_redirected_git_directory_is_never_traversed(self) -> None:
        (self.target / ".git").rename(self.base / "external-git")
        (self.target / ".git").symlink_to(self.base / "external-git", target_is_directory=True)
        before = snapshot(self.base)
        report = installer.composition_preview(self.target)
        self.assertEqual(report["inventory"][".git/config"]["state"], "UNSAFE")
        self.assert_refused(report, "OFFLINE_BOUNDARY_UNAVAILABLE")
        self.assertEqual(snapshot(self.base), before)

    def test_inventory_is_bounded_and_detects_drift(self) -> None:
        index = self.target / ".git/index"
        index.write_bytes(b"x" * (1024 * 1024 + 1))
        self.assertEqual(installer.composition_preview(self.target)["inventory"][".git/index"]["state"],
                         "UNSUPPORTED")
        index.write_bytes(b"original")
        original_read = os.read
        changed = False

        def read_and_mutate(descriptor: int, count: int) -> bytes:
            nonlocal changed
            result = original_read(descriptor, count)
            if not changed:
                changed = True
                index.write_bytes(b"changed")
            return result

        with patch.object(installer.os, "read", side_effect=read_and_mutate):
            record = installer._composition_inventory_file(self.target, ".git/index")
        self.assertEqual(record["state"], "UNSAFE")

    def test_inspection_errors_fail_closed(self) -> None:
        (self.target / ".factory").mkdir()
        original_lstat = Path.lstat
        before = snapshot(self.target)
        for relative in (".factory", str(installer.COMPOSITION_RECEIPT),
                         ".pre-commit-config.yaml", ".pre-commit-config.yml"):
            for error in (errno.EACCES, errno.EIO):
                with self.subTest(path=relative, error=error):
                    failing = self.target / relative

                    def inspect(path: Path, *args: object, **kwargs: object) -> os.stat_result:
                        if path == failing:
                            raise OSError(error, "injected inspection failure")
                        return original_lstat(path, *args, **kwargs)

                    with patch.object(Path, "lstat", inspect):
                        report = installer.preview(self.target, self.bundle, None, "fixture")
                    self.assert_refused(report, "COMPOSITION_RECEIPT_INVALID")
                    self.assertEqual(snapshot(self.target), before)

    def test_inventory_io_failures_close_every_opened_descriptor(self) -> None:
        original_open, original_close = os.open, os.close
        before = snapshot(self.target)
        for operation in ("open", "fstat", "read"):
            with self.subTest(operation=operation):
                opened: list[int] = []
                closed: list[int] = []

                def open_file(*args: object, **kwargs: object) -> int:
                    if operation == "open" and len(opened) == 2:
                        raise OSError(errno.EIO, "injected open failure")
                    descriptor = original_open(*args, **kwargs)
                    opened.append(descriptor)
                    return descriptor

                def close_file(descriptor: int) -> None:
                    closed.append(descriptor)
                    original_close(descriptor)

                with patch.object(installer.os, "open", side_effect=open_file), \
                     patch.object(installer.os, "close", side_effect=close_file):
                    if operation == "open":
                        record = installer._composition_inventory_file(self.target, ".git/index")
                    else:
                        with patch.object(installer.os, operation,
                                          side_effect=OSError(errno.EIO, "injected I/O failure")):
                            record = installer._composition_inventory_file(self.target, ".git/index")
                self.assertEqual(record["state"], "UNSAFE")
                self.assertEqual(closed, list(reversed(opened)))
                self.assertEqual(snapshot(self.target), before)

    def test_refusal_never_attempts_mutation_primitives(self) -> None:
        before = snapshot(self.target)
        with patch.object(os, "fsync", side_effect=AssertionError("fsync attempted")), \
             patch.object(os, "replace", side_effect=AssertionError("rename attempted")), \
             patch.object(Path, "mkdir", side_effect=AssertionError("mkdir attempted")), \
             patch.object(Path, "write_text", side_effect=AssertionError("write attempted")), \
             patch.object(installer, "git", side_effect=AssertionError("Git attempted")):
            self.assert_refused(installer.composition_preview(self.target),
                                "OFFLINE_BOUNDARY_UNAVAILABLE")
        self.assertEqual(snapshot(self.target), before)

    def test_gitfile_and_commondir_never_authorize_composition(self) -> None:
        original = self.base / "original-git"
        (self.target / ".git").rename(original)
        (self.target / ".git").write_text("gitdir: ../original-git\n")
        before = snapshot(self.base)
        report = installer.composition_preview(self.target)
        self.assert_refused(report, "OFFLINE_BOUNDARY_UNAVAILABLE")
        self.assertEqual(report["inventory"][".git/config"]["state"], "UNSAFE")
        self.assertEqual(snapshot(self.base), before)
        (self.target / ".git").rename(self.base / "retained-gitfile")
        original.rename(self.target / ".git")
        (self.target / ".git/commondir").write_text("../outside\n")
        before = snapshot(self.base)
        report = installer.composition_preview(self.target)
        self.assert_refused(report, "OFFLINE_BOUNDARY_UNAVAILABLE")
        self.assertEqual(report["inventory"][".git/commondir"]["state"], "PRESENT")
        self.assertEqual(snapshot(self.base), before)

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        poison = self.base / "poison-bin"
        poison.mkdir(exist_ok=True)
        for name in ("git", "pre-commit"):
            self.put_hook(poison / name)
        env = dict(os.environ, PATH=str(poison))
        return subprocess.run([sys.executable, str(ROOT / "scripts/ai/aq-factory"), *arguments],
                              cwd=self.target, env=env, text=True, capture_output=True,
                              check=False, timeout=10)

    def test_explicit_cli_refuses_even_with_confirmation_and_without_dry_run(self) -> None:
        digest = installer.composition_preview(self.target)["inventory_digest"]
        before = snapshot(self.target)
        for flags in (("--dry-run",), (), ("--confirm", str(digest))):
            with self.subTest(flags=flags):
                result = self.cli("retrofit", "--repo", str(self.target), "--compose-pre-commit",
                                  "--json", *flags)
                self.assertEqual(result.returncode, 4, result.stderr + result.stdout)
                self.assert_refused(json.loads(result.stdout), "OFFLINE_BOUNDARY_UNAVAILABLE")
                self.assertEqual(snapshot(self.target), before)

    def test_cli_default_init_update_rollback_and_doctor_refuse_before_commands(self) -> None:
        (self.target / ".factory").mkdir()
        (self.target / installer.COMPOSITION_RECEIPT).write_text("{}")
        (self.target / ".factory/kit.lock").write_text("{}")
        (self.target / ".factory/gate-install.json").write_text("{}")
        before = snapshot(self.target)
        for command, flags, code in (("init", (), 4), ("retrofit", (), 4),
                                     ("update", (), 4), ("update", ("--rollback", "latest"), 4),
                                     ("doctor", (), 1)):
            with self.subTest(command=command, flags=flags):
                result = self.cli(command, "--repo", str(self.target), "--json", *flags)
                self.assertEqual(result.returncode, code, result.stderr + result.stdout)
                self.assert_refused(json.loads(result.stdout), "COMPOSITION_RECEIPT_INVALID")
                self.assertEqual(snapshot(self.target), before)

    def test_concurrent_confirmation_and_rollback_both_refuse(self) -> None:
        (self.target / ".factory").mkdir()
        (self.target / installer.COMPOSITION_RECEIPT).write_text("{}")
        poison = self.base / "concurrent-poison-bin"
        poison.mkdir()
        for name in ("git", "pre-commit"):
            self.put_hook(poison / name)
        before = snapshot(self.target)

        def run(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts/ai/aq-factory"), *arguments,
                 "--repo", str(self.target), "--json"], cwd=self.target,
                env=dict(os.environ, PATH=str(poison)), text=True, capture_output=True,
                check=False, timeout=10)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (("retrofit", "--compose-pre-commit", "--confirm", "forged"),
                                          ("update", "--rollback", "latest"))))
        for result in results:
            self.assertEqual(result.returncode, 4, result.stderr + result.stdout)
            self.assert_refused(json.loads(result.stdout), "COMPOSITION_RECEIPT_INVALID")
        self.assertEqual(snapshot(self.target), before)

    def test_design_hash_schema_and_ci_registration(self) -> None:
        self.assertEqual(hashlib.sha256((PLAN / "DESIGN.md").read_bytes()).hexdigest(),
                         "4b9d4b3ac52745c826dcb57c81b878de2fb067139206cc9b45292544c122b5ac")
        schema = json.loads((PLAN / "hook-composition.schema.json").read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(schema["properties"]["schema_version"], {"const": 1})
        self.assertIn("preview_sha256", schema["required"])
        self.assertIn("journal_generation", schema["required"])
        checks = json.loads((ROOT / "config/ci-checks.json").read_text())
        # The CI file is an object with its check registry under checks.
        registry = checks["checks"] if isinstance(checks, dict) else checks
        factory = next(check for check in registry if check["id"] == "tests-factory")
        relative = str(Path(__file__).relative_to(ROOT))
        self.assertIn(relative, factory["paths"])
        self.assertIn(relative, factory["tests"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
