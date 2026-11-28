#!/usr/bin/env python3
"""tier0.d/check-stale-known-failing.py: stale (passing) known-failing -> FAIL; failing -> PASS."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "governance/tier0.d/check-stale-known-failing.py"
PY = "print('ok')"
FAIL = "print('first boom')\nprint('second')\nraise SystemExit(1)"
A = "scripts/testing/test-a.py"


def run(scripts, staged, mode="--pre-commit", env_extra=None, entry_extra=None):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "config").mkdir()
        entries = []
        for name, (cls, body) in scripts.items():
            rel = f"scripts/testing/{name}"
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body)
            entries.append({"script": rel, "class": cls, "reason": "x", **(entry_extra or {})})
        (root / "config/ci-checks.json").write_text(json.dumps({"checks": [], "test_exempt": entries}))
        env = {k: v for k, v in os.environ.items() if k not in ("TIER0_CI", "HOST_ONLY_STAGED")}
        env["HOST_ONLY_ROOT"] = str(root)
        if staged is not None:
            env["HOST_ONLY_STAGED"] = ",".join(staged)
        env.update(env_extra or {})
        p = subprocess.run([sys.executable, str(GATE), mode], capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr


class T(unittest.TestCase):
    def test_passing_known_failing_is_stale(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, [A])
        self.assertEqual(rc, 1, out)
        self.assertIn(f"known-failing exemption is stale: {A} passes", out)

    def test_still_failing_passes_with_first_line(self):
        rc, out = run({"test-a.py": ("known-failing", FAIL)}, [A])
        self.assertEqual(rc, 0, out)
        self.assertIn(f"PASS: {A} still fails", out)
        self.assertIn("first boom", out)

    def test_non_staged_skipped_in_precommit(self):
        s = {"test-a.py": ("known-failing", PY)}
        rc, out = run(s, ["README.md"])
        self.assertEqual(rc, 0, out)
        rc, out = run(s, ["README.md"], mode="--maintenance")
        self.assertEqual(rc, 1, out)

    def test_module_under_test_triggers(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, ["scripts/a.py"])
        self.assertEqual(rc, 1, out)

    def test_other_class_not_selected(self):
        rc, out = run({"test-a.py": ("sandbox-env", PY)}, [A])
        self.assertEqual(rc, 0, out)

    def test_exit_77_skips(self):
        rc, out = run({"test-a.py": ("known-failing", "raise SystemExit(77)")}, [A])
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP", out)

    def test_needs_missing_skips(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, [A], entry_extra={"needs": ["no-such-tool-xyz"]})
        self.assertEqual(rc, 0, out)
        self.assertIn("missing host prerequisite: no-such-tool-xyz", out)

    def test_ci_mode_skips(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, [A], mode="--ci")
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP", out)

    def test_tier0_ci_env_skips(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, [A], mode="--maintenance", env_extra={"TIER0_CI": "1"})
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP", out)

    def test_timeout_counts_as_still_failing(self):
        rc, out = run({"test-a.py": ("known-failing", "import time; time.sleep(30)")}, [A],
                      env_extra={"STALE_KF_TIMEOUT": "1"})
        self.assertEqual(rc, 0, out)
        self.assertIn("timed out", out)

    def test_git_failure_fails(self):
        rc, out = run({"test-a.py": ("known-failing", PY)}, None)
        self.assertEqual(rc, 1, out)
        self.assertIn("git diff --cached failed", out)


if __name__ == "__main__":
    unittest.main()
