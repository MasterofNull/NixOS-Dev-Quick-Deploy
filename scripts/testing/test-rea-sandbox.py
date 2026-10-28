#!/usr/bin/env python3
"""Unit and isolation tests for mcp-rea-sandboxed launcher (W1-S2)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHER = REPO_ROOT / "scripts" / "ai" / "mcp-rea-sandboxed"


class TestReaSandbox(unittest.TestCase):
    def test_launcher_executable_exists(self):
        self.assertTrue(LAUNCHER.exists(), f"Launcher does not exist at {LAUNCHER}")
        self.assertTrue(os.access(LAUNCHER, os.X_OK), "Launcher is not executable")

    def _run_with_stub_confine(self, candidates, catalog):
        """Run the real launcher against fixture registries and a stub aq-confine that records argv."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            argv_out = td / "argv.txt"
            stub = td / "stub-confine"
            stub.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$ARGV_OUT"\n')
            stub.chmod(0o755)
            # Launcher resolves config and aq-confine relative to its own location; build a throwaway repo layout.
            root = td / "repo"
            (root / "scripts" / "ai").mkdir(parents=True)
            (root / "config").mkdir()
            (root / "config" / "agent-capability-intake-candidates.json").write_text(json.dumps(candidates))
            (root / "config" / "system-capability-catalog.json").write_text(json.dumps(catalog))
            launcher = root / "scripts" / "ai" / "mcp-rea-sandboxed"
            launcher.write_bytes(LAUNCHER.read_bytes())
            launcher.chmod(0o755)
            env = dict(os.environ, ARGV_OUT=str(argv_out), AQ_CONFINE_BIN="../../../" + stub.name)
            (root / stub.name).symlink_to(stub)
            proc = subprocess.run([str(launcher), "rea", "--transport", "stdio"], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            argv = argv_out.read_text().splitlines() if argv_out.exists() else None
            return proc, argv

    def test_refuses_when_candidate_not_admitted(self):
        proc, argv = self._run_with_stub_confine(
            {"candidates": [{"id": "rea-reverse-engineering", "state": "proposed"}]},
            {"capabilities": {"rea-reverse-engineering": {"status": "enabled"}}},
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("REJECT", proc.stderr)
        self.assertIsNone(argv, "aq-confine must not be reached when admission fails")

    def test_admitted_launch_passes_profile_to_aq_confine(self):
        proc, argv = self._run_with_stub_confine(
            {"candidates": [{"id": "rea-reverse-engineering", "state": "enabled"}]},
            {"capabilities": {"rea-reverse-engineering": {"status": "enabled"}}},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            argv,
            ["--profile", "readonly-analysis", "--net", "none", "--scratch", "--", "rea", "--transport", "stdio"],
        )

    def test_real_aq_confine_accepts_launcher_argv(self):
        # aq-confine --explain needs no root and validates the profile + argv shape the launcher builds.
        proc = subprocess.run(
            [str(REPO_ROOT / "scripts" / "ai" / "aq-confine"), "--profile", "readonly-analysis", "--net", "none",
             "--scratch", "--explain", "--", "rea", "--transport", "stdio"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
