#!/usr/bin/env python3
"""Focused checks for RSI adapter installation and explicit runner semantics."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from unittest.mock import Mock, call, patch


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts/ai/aq-rsi-hook-install"
RUNNER = ROOT / "scripts/ai/aq-rsi-run"


def load_installer():
    loader = SourceFileLoader("rsi_hook_install", str(INSTALLER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RSIHookInstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Path(self.tempdir.name) / "settings.json"

    def tearDown(self):
        self.tempdir.cleanup()

    @staticmethod
    def settings_with(*commands: str) -> dict:
        return {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": command} for command in commands],
                    }
                ]
            }
        }

    def write_settings(self, state: dict, mode: int = 0o600) -> bytes:
        original = json.dumps(state, indent=2).encode() + b"\n"
        self.settings.write_bytes(original)
        os.chmod(self.settings, mode)
        return original

    def test_installs_once_preserves_mode_and_is_idempotent(self):
        original = self.write_settings(
            self.settings_with("lean-ctx hook codex-pretooluse"), mode=0o600
        )

        self.assertEqual(self.installer.main([str(self.settings)]), 0)

        state = json.loads(self.settings.read_text())
        expected = shlex.join(
            [sys.executable, str(ROOT / "scripts/ai/aq-rsi-hook")]
        )
        self.assertEqual(
            state["hooks"]["PreToolUse"][0]["hooks"][0]["command"], expected
        )
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode), 0o600)
        self.assertEqual(
            self.settings.with_name("settings.json.before-rsi").read_bytes(), original
        )

        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.installer.main([str(self.settings)]), 0)
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode), 0o600)

    def test_rejects_ambiguous_or_mixed_configuration_without_writing(self):
        adapter = shlex.join([sys.executable, str(ROOT / "scripts/ai/aq-rsi-hook")])
        cases = (
            ("two-upstream", ("lean-ctx hook codex-pretooluse", "lean-ctx hook codex-pretooluse")),
            ("mixed", ("lean-ctx hook codex-pretooluse", adapter)),
            ("two-adapters", (adapter, adapter)),
        )
        for name, commands in cases:
            with self.subTest(name=name):
                self.settings = Path(self.tempdir.name) / f"{name}.json"
                original = self.write_settings(self.settings_with(*commands))
                with self.assertRaises(SystemExit):
                    self.installer.main([str(self.settings)])
                self.assertEqual(self.settings.read_bytes(), original)
                self.assertFalse(
                    self.settings.with_name("settings.json.before-rsi").exists()
                )


class RSIRunnerTests(unittest.TestCase):
    def run_runner(self, argv: list[str], lifecycle, popen: Mock, killpg: Mock):
        with (
            patch.object(sys, "argv", ["aq-rsi-run", *argv]),
            patch.dict(sys.modules, {"rsi_lifecycle": lifecycle}),
            patch("subprocess.Popen", popen),
            patch("os.killpg", killpg),
        ):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_path(str(RUNNER), run_name="__rsi_runner_test__")
        return exited.exception.code

    def test_rg_no_match_does_not_record_an_incident(self):
        lifecycle = types.SimpleNamespace(failure=Mock())
        process = Mock()
        process.wait.return_value = 1
        popen = Mock(return_value=process)

        code = self.run_runner(
            ["--subject", "no-match", "--", "/tmp/rg"], lifecycle, popen, Mock()
        )

        self.assertEqual(code, 1)
        popen.assert_called_once_with(["/tmp/rg"], start_new_session=True)
        lifecycle.failure.assert_not_called()

    def test_timeout_terminates_the_process_group_and_records_once(self):
        lifecycle = types.SimpleNamespace(failure=Mock())
        process = Mock(pid=4242)
        process.wait.side_effect = (
            subprocess.TimeoutExpired(["/tmp/fake"], 0.01),
            subprocess.TimeoutExpired(["/tmp/fake"], 2),
            -9,
        )
        popen = Mock(return_value=process)
        killpg = Mock()

        code = self.run_runner(
            ["--subject", "timeout", "--timeout", "0.01", "--", "/tmp/fake"],
            lifecycle,
            popen,
            killpg,
        )

        self.assertEqual(code, 124)
        self.assertEqual(
            killpg.call_args_list,
            [call(4242, signal.SIGTERM), call(4242, signal.SIGKILL)],
        )
        lifecycle.failure.assert_called_once()
        arguments, keywords = lifecycle.failure.call_args
        self.assertEqual(arguments[:4], ("codex", "timeout", "fake", "/tmp/fake"))
        self.assertEqual(arguments[5], "command exit status 124")
        self.assertEqual(
            keywords["root_fix"],
            "Inspect bounded command evidence and fix the producer before retrying",
        )

    def test_recording_failure_does_not_change_command_exit_status(self):
        lifecycle = types.SimpleNamespace(failure=Mock(side_effect=OSError("ledger down")))
        process = Mock()
        process.wait.return_value = 7

        code = self.run_runner(
            ["--subject", "failure", "--", "/tmp/fake"],
            lifecycle,
            Mock(return_value=process),
            Mock(),
        )

        self.assertEqual(code, 7)
        lifecycle.failure.assert_called_once()


if __name__ == "__main__":
    unittest.main()
