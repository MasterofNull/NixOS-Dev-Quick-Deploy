#!/usr/bin/env python3
"""tier0.d/check-host-only-tests.py: selected+matching passes, failing -> FAIL, non-matching skipped, missing tool -> SKIP."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "governance/tier0.d/check-host-only-tests.py"


def run(scripts, staged, mode="--pre-commit"):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "config").mkdir()
        entries = []
        for name, (cls, body) in scripts.items():
            rel = f"scripts/testing/{name}"
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body)
            entries.append({"script": rel, "class": cls, "reason": "x"})
        (root / "config/ci-checks.json").write_text(json.dumps({"checks": [], "test_exempt": entries}))
        env = {**os.environ, "HOST_ONLY_ROOT": str(root), "HOST_ONLY_STAGED": ",".join(staged)}
        p = subprocess.run([sys.executable, str(GATE), mode], capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr


class T(unittest.TestCase):
    def test_pass(self):
        rc, out = run({"test-a.py": ("sandbox-env", "print('ok')")}, ["scripts/testing/test-a.py"])
        self.assertEqual(rc, 0, out)
        self.assertIn("PASS: scripts/testing/test-a.py", out)

    def test_fail(self):
        rc, out = run({"test-a.py": ("sandbox-env", "print('boom detail')\nraise SystemExit(1)")},
                      ["scripts/testing/test-a.py"])
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL: scripts/testing/test-a.py", out)
        self.assertIn("boom detail", out)

    def test_non_matching_skipped_in_precommit(self):
        s = {"test-a.py": ("sandbox-env", "raise SystemExit(1)")}
        rc, out = run(s, ["README.md"])
        self.assertEqual(rc, 0, out)
        rc, out = run(s, ["README.md"], mode="--maintenance")
        self.assertEqual(rc, 1, out)

    def test_ci_mode_skips(self):
        rc, out = run({"test-a.py": ("sandbox-env", "raise SystemExit(1)")}, ["scripts/testing/test-a.py"], mode="--ci")
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP: host-only tests do not run under --ci", out)

    def test_module_under_test_triggers(self):
        rc, out = run({"test-a.py": ("sandbox-env", "raise SystemExit(1)")}, ["scripts/a.py"])
        self.assertEqual(rc, 1, out)

    def test_other_class_not_selected(self):
        rc, out = run({"test-a.py": ("known-failing", "raise SystemExit(1)")}, ["scripts/testing/test-a.py"])
        self.assertEqual(rc, 0, out)

    def test_missing_tool_skips(self):
        rc, out = run({"test-a.py": ("sandbox-env", "raise FileNotFoundError(2, 'No such file', 'codex')")},
                      ["scripts/testing/test-a.py"])
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP: scripts/testing/test-a.py (missing host prerequisite: codex)", out)
        rc, out = run({"test-a.py": ("sandbox-env", "raise SystemExit(77)")}, ["scripts/testing/test-a.py"])
        self.assertIn("SKIP", out)


if __name__ == "__main__":
    unittest.main()
