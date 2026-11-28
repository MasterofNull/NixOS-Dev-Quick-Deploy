#!/usr/bin/env python3
"""J5: delegation artifacts must survive reboot and stay in durable work roots."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts/ai/lib"
sys.path.insert(0, str(LIB))
from delegation_dir import resolve_delegation_dir, resolve_main_root, validate_durable_artifact_path


class DurableArtifacts(unittest.TestCase):
    def setUp(self) -> None:
        # A real durable sandbox: the tests must exercise the guard without its escape hatch.
        self.sandbox = tempfile.TemporaryDirectory(prefix="s5-guard-", dir=Path.home())
        self.addCleanup(self.sandbox.cleanup)
        self.base = Path(self.sandbox.name)
        self.delegation = self.base / ".agents/delegation"
        self.delegation.mkdir(parents=True)
        self.claude = self.base / "claude-tmp"
        self.env = dict(os.environ)
        self.env.pop("AQ_ALLOW_VOLATILE_DIR", None)
        self.env.update(AQ_DELEGATION_DIR=str(self.delegation), CLAUDE_CODE_TMPDIR=str(self.claude))
        self.main = resolve_main_root(ROOT / "scripts/ai")

    def shell_guard(self, path: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", 'source "$1"; validate_durable_artifact_path "$2" "--prompt-file" "$3"',
             "guard", str(LIB / "delegation-dir.sh"), str(path), str(self.delegation)],
            env=self.env if env is None else env, text=True, capture_output=True, timeout=15,
        )

    def assert_helpers(self, path: Path, accepted: bool, env: dict[str, str] | None = None) -> None:
        selected = self.env if env is None else env
        result = self.shell_guard(path, selected)
        self.assertEqual(result.returncode == 0, accepted, result.stderr)
        stderr = io.StringIO()
        with patch.dict(os.environ, selected, clear=True), contextlib.redirect_stderr(stderr):
            if accepted:
                self.assertEqual(validate_durable_artifact_path(path, "--prompt-file", self.delegation), path.resolve())
            else:
                with self.assertRaises(SystemExit) as raised:
                    validate_durable_artifact_path(path, "--prompt-file", self.delegation)
                self.assertEqual(raised.exception.code, 1)
        if not accepted:
            for error in (result.stderr, stderr.getvalue()):
                self.assertIn("ERROR:", error)
                self.assertIn("--prompt-file", error)
                self.assertIn(str(path), error)
                self.assertIn(".agents/delegation/", error)

    def wrapper(self, name: str, path: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(ROOT / "scripts/ai" / f"delegate-to-{name}"), "--prompt-file", path],
            env=self.env if env is None else env, capture_output=True, text=True, timeout=15,
        )

    def test_j5_all_wrappers(self) -> None:
        for name in ("codex", "gemini", "local", "claude"):
            for path in ("/tmp/x.md", "/var/tmp/x.md", "/dev/shm/x.md", str(self.base / "outside.md")):
                with self.subTest(wrapper=name, path=path):
                    result = self.wrapper(name, path)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("--prompt-file", result.stderr)
                    self.assertIn(".agents/delegation/", result.stderr)
                    self.assertNotIn("Prompt file not found", result.stderr)

    def test_helpers_accept_durable_roots(self) -> None:
        for path in (self.delegation / "outputs/p.md", self.main / ".agents/plans/p.md", self.claude / "p.md"):
            with self.subTest(path=path):
                self.assert_helpers(path, True)

    def test_shell_guard_without_dir_argument_honors_override(self) -> None:
        path = self.delegation / "outputs/p.md"
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; validate_durable_artifact_path "$2" "--prompt-file"',
             "guard", str(LIB / "delegation-dir.sh"), str(path)],
            env=self.env, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_helpers_reject_volatile_and_outside(self) -> None:
        for path in (Path("/tmp/x.md"), Path("/var/tmp/x.md"), Path("/dev/shm/x.md"),
                     self.delegation / "../outside.md", self.base / ".agents/delegation-other/p.md"):
            with self.subTest(path=path):
                self.assert_helpers(path, False)

    def test_symlink_escape(self) -> None:
        link = self.delegation / "escape.md"
        link.symlink_to("/tmp/escape.md")
        self.assert_helpers(link, False)
        for name in ("codex", "gemini", "local", "claude"):
            result = self.wrapper(name, str(link))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(".agents/delegation/", result.stderr)

    def test_volatile_claude_root_is_not_an_allowlist(self) -> None:
        env = {**self.env, "CLAUDE_CODE_TMPDIR": "/tmp/fake"}
        self.assert_helpers(Path("/tmp/fake/p.md"), False, env)

    def test_codex_output_override(self) -> None:
        result = self.wrapper("codex", str(self.delegation / "p.md"), {**self.env, "DELEGATE_OUTPUTS_DIR": "/tmp/evil"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DELEGATE_OUTPUTS_DIR", result.stderr)
        self.assertIn(".agents/delegation/", result.stderr)

    def test_derived_volatile_delegation_rejected(self) -> None:
        env = dict(self.env)
        env.pop("AQ_DELEGATION_DIR", None)
        with tempfile.TemporaryDirectory(prefix="s5-derived-", dir="/tmp") as tmp:
            scripts = Path(tmp) / "scripts/ai"
            scripts.mkdir(parents=True)
            for allowed in (False, True):
                selected = dict(env)
                if allowed:
                    selected["AQ_ALLOW_VOLATILE_DIR"] = "1"
                result = subprocess.run(
                    ["bash", "-c", 'source "$1"; resolve_delegation_dir "$2"',
                     "guard", str(LIB / "delegation-dir.sh"), str(scripts)],
                    env=selected, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode == 0, allowed, result.stderr)
                with patch.dict(os.environ, selected, clear=True):
                    if allowed:
                        self.assertEqual(resolve_delegation_dir(scripts), Path(tmp) / ".agents/delegation")
                    else:
                        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                            resolve_delegation_dir(scripts)

    def test_explicit_volatile_delegation_preserves_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s5-explicit-", dir="/tmp") as tmp:
            env = {**self.env, "AQ_DELEGATION_DIR": str(Path(tmp) / "deleg")}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(resolve_delegation_dir(ROOT / "scripts/ai"), Path(env["AQ_DELEGATION_DIR"]))
            for name in ("codex", "gemini", "local", "claude"):
                with self.subTest(wrapper=name):
                    # Reaching prompt existence checking proves startup accepted the override.
                    result = self.wrapper(name, str(self.claude / "missing.md"), env)
                    self.assertIn("Prompt file not found", result.stderr)
                    result = self.wrapper(name, "/tmp/x.md", env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("--prompt-file", result.stderr)
                    self.assertIn(".agents/delegation/", result.stderr)
                    self.assertNotIn("Prompt file not found", result.stderr)

    def test_escape_hatch(self) -> None:
        env = {**self.env, "AQ_ALLOW_VOLATILE_DIR": "1"}
        self.assert_helpers(Path("/tmp/x.md"), True, env)
        for name in ("codex", "gemini", "local", "claude"):
            result = self.wrapper(name, str(self.base / "missing.md"), env)
            self.assertIn("Prompt file not found", result.stderr)
        result = self.wrapper("codex", str(self.base / "missing.md"), {**env, "DELEGATE_OUTPUTS_DIR": "/tmp/evil"})
        self.assertIn("Prompt file not found", result.stderr)

    def test_local_review_uses_durable_prompt_and_cleans_up(self) -> None:
        # Avoid external inference; inspect the real file passed to the subprocess.
        with patch.dict(os.environ, self.env, clear=True):
            module = runpy.run_path(str(ROOT / "scripts/ai/aq-local-review"), run_name="s5_local_review")
            run_local = module["run_local"]
            seen: list[Path] = []
            original_run = subprocess.run

            def delegate(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                if argv[0] == "git":
                    return original_run(argv, capture_output=True, text=True, check=True, timeout=10)
                path = Path(argv[argv.index("--prompt-file") + 1])
                seen.append(path)
                self.assertEqual(path.parent, self.delegation / "outputs/local-review")
                self.assertEqual(path.read_text(), "review me")
                raise RuntimeError("synthetic delegate failure")

            with patch("subprocess.run", side_effect=delegate):
                with self.assertRaisesRegex(RuntimeError, "synthetic delegate failure"):
                    run_local("review me", 1)
            self.assertEqual(len(seen), 1)
            self.assertFalse(seen[0].exists())


if __name__ == "__main__":
    unittest.main()
