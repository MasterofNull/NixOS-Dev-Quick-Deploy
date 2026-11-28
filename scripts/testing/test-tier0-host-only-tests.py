#!/usr/bin/env python3
"""tier0.d/check-host-only-tests.py: selection, FAIL/SKIP semantics, --ci skip, env scrubbing, timeout."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "governance/tier0.d/check-host-only-tests.py"
PY = "print('ok')"
FAIL = "raise SystemExit(1)"


def run(scripts, staged, mode="--pre-commit", env_extra=None, entry_extra=None, timeout=None, cwd_git=False):
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
        env.update({"HOST_ONLY_ROOT": str(root)})
        if staged is not None:
            env["HOST_ONLY_STAGED"] = ",".join(staged)
        if timeout:
            env["HOST_ONLY_TIMEOUT"] = str(timeout)
        env.update(env_extra or {})
        p = subprocess.run([sys.executable, str(GATE), mode], capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr


A = "scripts/testing/test-a.py"


class T(unittest.TestCase):
    def test_pass(self):
        rc, out = run({"test-a.py": ("sandbox-env", PY)}, [A])
        self.assertEqual(rc, 0, out)
        self.assertIn(f"PASS: {A}", out)

    def test_fail(self):
        rc, out = run({"test-a.py": ("sandbox-env", "print('boom detail')\n" + FAIL)}, [A])
        self.assertEqual(rc, 1, out)
        self.assertIn(f"FAIL: {A}", out)
        self.assertIn("boom detail", out)

    def test_non_matching_skipped_in_precommit(self):
        s = {"test-a.py": ("sandbox-env", FAIL)}
        rc, out = run(s, ["README.md"])
        self.assertEqual(rc, 0, out)
        rc, out = run(s, ["README.md"], mode="--maintenance")
        self.assertEqual(rc, 1, out)

    def test_module_under_test_triggers(self):
        rc, out = run({"test-a.py": ("sandbox-env", FAIL)}, ["scripts/a.py"])
        self.assertEqual(rc, 1, out)

    def test_stem_dash_underscore_normalised(self):
        rc, out = run({"test-exec-cell.py": ("sandbox-env", FAIL)}, ["pkg/exec_cell.py"])
        self.assertEqual(rc, 1, out)

    def test_paths_glob_triggers(self):
        s = {"test-a.py": ("sandbox-env", FAIL)}
        rc, _ = run(s, ["lib/x/y.py"], entry_extra={"paths": ["lib/**/*.py"]})
        self.assertEqual(rc, 1)
        rc, _ = run(s, ["other/y.py"], entry_extra={"paths": ["lib/**/*.py"]})
        self.assertEqual(rc, 0)

    def test_other_class_not_selected(self):
        rc, out = run({"test-a.py": ("known-failing", FAIL)}, [A])
        self.assertEqual(rc, 0, out)

    def test_sh_runner(self):
        rc, out = run({"test-a.sh": ("sandbox-env", "echo hi\n")}, ["scripts/testing/test-a.sh"])
        self.assertEqual(rc, 0, out)
        self.assertIn("PASS: scripts/testing/test-a.sh", out)
        rc, out = run({"test-a.sh": ("sandbox-env", "exit 3\n")}, ["scripts/testing/test-a.sh"])
        self.assertEqual(rc, 1, out)

    def test_timeout_fails(self):
        rc, out = run({"test-a.py": ("sandbox-env", "import time; time.sleep(30)")}, [A], timeout=1)
        self.assertEqual(rc, 1, out)
        self.assertIn("timed out", out)

    def test_exit_77_skips(self):
        rc, out = run({"test-a.py": ("sandbox-env", "raise SystemExit(77)")}, [A])
        self.assertEqual(rc, 0, out)
        self.assertIn(f"SKIP: {A} (missing host prerequisite", out)

    def test_declared_needs_missing_skips(self):
        rc, out = run({"test-a.py": ("sandbox-env", FAIL)}, [A], entry_extra={"needs": ["no-such-tool-xyz"]})
        self.assertEqual(rc, 0, out)
        self.assertIn("missing host prerequisite: no-such-tool-xyz", out)

    def test_filenotfound_path_fails(self):
        body = "raise FileNotFoundError(2, 'No such file', '/x/config/model.json')"
        rc, out = run({"test-a.py": ("sandbox-env", body)}, [A])
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL", out)

    def test_filenotfound_bare_tool_fails(self):
        rc, out = run({"test-a.py": ("sandbox-env", "raise FileNotFoundError(2, 'No such file', 'codex')")}, [A])
        self.assertEqual(rc, 1, out)

    def test_ci_mode_skips(self):
        rc, out = run({"test-a.py": ("sandbox-env", FAIL)}, [A], mode="--ci")
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP: host-only tests do not run under --ci", out)

    def test_tier0_ci_env_skips_any_mode(self):
        rc, out = run({"test-a.py": ("sandbox-env", FAIL)}, [A], mode="--maintenance", env_extra={"TIER0_CI": "1"})
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP: host-only tests do not run under --ci", out)

    def test_git_env_scrubbed_for_children(self):
        body = ("import os,sys\n"
                "bad=[k for k in ('GIT_DIR','GIT_INDEX_FILE','GIT_WORK_TREE') if k in os.environ]\n"
                "sys.exit(1 if bad else 0)\n")
        rc, out = run({"test-a.py": ("sandbox-env", body)}, [A],
                      env_extra={"GIT_DIR": "/x", "GIT_INDEX_FILE": "/y", "GIT_WORK_TREE": "/z"})
        self.assertEqual(rc, 0, out)

    def test_git_failure_fails(self):
        # HOST_ONLY_ROOT is a temp dir that is not a git repo, so `git diff --cached` errors.
        rc, out = run({"test-a.py": ("sandbox-env", PY)}, None)
        self.assertEqual(rc, 1, out)
        self.assertIn("git diff --cached failed", out)


if __name__ == "__main__":
    unittest.main()
