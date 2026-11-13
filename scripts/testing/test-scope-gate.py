#!/usr/bin/env python3
"""Integration tests for W4-S1: Rust-backed owned-path scope gate."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "crates" / "contract-validator"

VALIDATOR = [shutil.which("harness-contracts") or str(
    subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f"{REPO_ROOT}#harness-contracts"],
                   capture_output=True, text=True, check=True).stdout.split()[-1] + "/bin/harness-contracts")]


class TestScopeGate(unittest.TestCase):
    def test_cargo_unit_tests_pass(self):
        res = subprocess.run(
            ["cargo", "test", "--manifest-path", str(CRATE_DIR / "Cargo.toml")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Cargo tests failed:\n{res.stderr}\n{res.stdout}")

    def _repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self._git(root, "init", "-q", "-b", "main")
        (root / "crates").mkdir()
        (root / "scripts").mkdir()
        (root / "crates/a.rs").write_text("a\n")
        (root / "scripts/b.sh").write_text("b\n")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-q", "-m", "base")
        self._git(root, "checkout", "-q", "-b", "slice")
        return root

    @staticmethod
    def _git(root, *args):
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
             "-c", "commit.gpgsign=false", *args],
            check=True, capture_output=True,
        )

    def _gate(self, root, owned, *extra):
        return subprocess.run(
            [*VALIDATOR, "--root", str(root), "scope-gate", "--owned", owned, "--base", "main", *extra],
            capture_output=True, text=True,
        )

    def _commit(self, root, rel):
        (root / rel).write_text("changed\n")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-q", "-m", "change")

    def test_in_scope_cli_passes(self):
        root = self._repo()
        self._commit(root, "crates/a.rs")
        res = self._gate(root, "crates/**,scripts/**")
        self.assertEqual(res.returncode, 0, f"Unexpected failure:\n{res.stderr}\n{res.stdout}")
        self.assertIn("PASS: slice changes are strictly within owned scope", res.stdout)

    def test_out_of_scope_cli_blocks(self):
        root = self._repo()
        self._commit(root, "scripts/b.sh")
        res = self._gate(root, "crates/**")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("FAIL: modified file is outside declared owned paths", res.stderr)

    def test_uncommitted_blocks_by_default(self):
        root = self._repo()
        (root / "crates/a.rs").write_text("dirty\n")
        res = self._gate(root, "crates/**,scripts/**")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("FAIL: uncommitted changes detected in working tree", res.stderr)

if __name__ == "__main__":
    unittest.main()
