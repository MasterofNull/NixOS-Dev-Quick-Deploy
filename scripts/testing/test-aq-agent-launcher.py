#!/usr/bin/env python3
"""Verify closed pane input cannot repeatedly launch provider sessions."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class LauncherTests(unittest.TestCase):
    def test_closed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts" / "ai"
            scripts.mkdir(parents=True)
            launcher = scripts / "aq-agent-launcher"
            shutil.copyfile(ROOT / "scripts/ai/aq-agent-launcher", launcher)
            calls = root / "calls"
            chat = scripts / "aq-chat"
            chat.write_text('#!/bin/sh\nprintf "call\\n" >> "' + str(calls) + '"\n')
            chat.chmod(0o755)
            env = dict(os.environ, HOME=str(root), PATH=str(scripts) + os.pathsep + os.environ["PATH"])
            for mode, expected in (("prompt", 0), ("new", 1)):
                with self.subTest(mode=mode):
                    result = subprocess.run(
                        ["bash", str(launcher), "local", mode], input="",
                        capture_output=True, text=True, env=env, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Input closed; exiting pane.", result.stdout)
                    count = len(calls.read_text().splitlines()) if calls.exists() else 0
                    self.assertEqual(count, expected)

    def test_gemini_native_cli_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts" / "ai"
            scripts.mkdir(parents=True)
            launcher = scripts / "aq-agent-launcher"
            shutil.copyfile(ROOT / "scripts/ai/aq-agent-launcher", launcher)
            calls = root / "calls"
            agy = scripts / "agy"
            agy.write_text('#!/bin/sh\nprintf "agy-called: %s\\n" "$*" >> "' + str(calls) + '"\n')
            agy.chmod(0o755)
            env = dict(os.environ, HOME=str(root), PATH=str(scripts) + os.pathsep + os.environ["PATH"])

            # Test 'new' mode
            result_new = subprocess.run(
                ["bash", str(launcher), "gemini", "new"], input="",
                capture_output=True, text=True, env=env, timeout=5,
            )
            self.assertEqual(result_new.returncode, 0, result_new.stderr)
            self.assertTrue(calls.exists(), "agy was not called in new mode")
            self.assertIn("agy-called: \n", calls.read_text())

            # Test 'resume' mode
            calls.unlink()
            result_resume = subprocess.run(
                ["bash", str(launcher), "gemini", "resume"], input="",
                capture_output=True, text=True, env=env, timeout=5,
            )
            self.assertEqual(result_resume.returncode, 0, result_resume.stderr)
            self.assertTrue(calls.exists(), "agy was not called in resume mode")
            self.assertIn("agy-called: --continue\n", calls.read_text())


if __name__ == "__main__":
    unittest.main()
