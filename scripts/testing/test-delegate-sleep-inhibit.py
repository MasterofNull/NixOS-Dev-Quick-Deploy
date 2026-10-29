#!/usr/bin/env python3
"""Verify delegate-to-* workers run under a systemd sleep/idle inhibitor (P1.6).

systemd-inhibit is stubbed via PATH; no real task is dispatched.
"""
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "scripts" / "ai"
HELPER = AI / "lib" / "sleep-inhibit.sh"
# script -> regex for the worker launch that must carry the prefix
LAUNCHES = {
    "delegate-to-local": [r'setsid "\$\{AQ_INHIBIT_PREFIX\[@\]\}" bash -c', r'setsid "\$\{AQ_INHIBIT_PREFIX\[@\]\}" "\$\{_DISPATCH_ARGS'],
    "delegate-to-codex": [r'nohup "\$\{AQ_INHIBIT_PREFIX\[@\]\}" bash "\$SCRIPT_DIR/lib/codex-background-worker\.sh"'],
    "delegate-to-claude": [r'nohup "\$\{AQ_INHIBIT_PREFIX\[@\]\}" bash "\$SCRIPT_DIR/lib/claude-background-worker\.sh"',
                           r'"\$\{AQ_INHIBIT_PREFIX\[@\]\}" "\$\{cmd\[@\]\}" > "\$output_file"'],
    "delegate-to-gemini": [r'nohup "\$\{AQ_INHIBIT_PREFIX\[@\]\}" bash "\$SCRIPT_DIR/lib/gemini-background-worker\.sh"'],
}


def run_helper(path_dirs):
    """Source helper, build prefix for task T1, execute `echo worker` under it."""
    env = {"PATH": os.pathsep.join(path_dirs)}
    bash = shutil.which("bash")
    echo = shutil.which("echo")
    code = (f'source "{HELPER}"; aq_sleep_inhibit_prefix T1; '
            '"${AQ_INHIBIT_PREFIX[@]}" ' + echo + ' worker-ran')
    return subprocess.run([bash, "-c", code], env=env, capture_output=True, text=True)


class SleepInhibit(unittest.TestCase):
    def test_wrapped_with_stub(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "argv.log"
            stub = Path(d) / "systemd-inhibit"
            stub.write_text(f'#!{shutil.which("bash")}\nprintf "%s\\n" "$@" > "{log}"\n'
                            'while [[ "${1:-}" == --* ]]; do shift; done\nexec "$@"\n')
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
            r = run_helper([d, str(Path(shutil.which("bash")).parent), str(Path(shutil.which("echo")).parent)])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("worker-ran", r.stdout)
            argv = log.read_text().splitlines()
            self.assertIn("--what=idle", argv)
            self.assertIn("--mode=block", argv)
            self.assertIn("--who=aq-delegate", argv)
            self.assertIn("--why=delegated task T1 running", argv)
            self.assertEqual(r.stderr, "")

    def test_unwrapped_with_warning_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_helper([d])  # empty dir: no systemd-inhibit on PATH
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("worker-ran", r.stdout)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1)
            self.assertIn("systemd-inhibit not found", r.stderr)

    def test_each_delegate_script_wraps_worker(self):
        for name, patterns in LAUNCHES.items():
            text = (AI / name).read_text()
            self.assertIn("lib/sleep-inhibit.sh", text, name)
            self.assertIn("aq_sleep_inhibit_prefix", text, name)
            for pat in patterns:
                self.assertTrue(re.search(pat, text), f"{name}: missing wrapped launch {pat}")
            # no remaining unwrapped background-worker launch
            self.assertIsNone(re.search(r'nohup bash "\$SCRIPT_DIR/lib/\w+-background-worker\.sh"', text), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
