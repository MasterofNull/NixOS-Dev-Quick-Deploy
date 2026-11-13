#!/usr/bin/env python3
"""check-python-types.py: baseline ratchet semantics with fake tools in temp repos (no network)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "governance", "check-python-types.py")

# Fake basedpyright: one error per line containing "undefined_name", line number in the range (must not matter).
FAKE_BP = """#!/usr/bin/env python3
import json, sys
out = []
for f in [a for a in sys.argv[1:] if not a.startswith("--")]:
    for i, line in enumerate(open(f), 1):
        if "undefined_name" in line:
            out.append({"file": f, "severity": "error", "rule": "reportUndefinedVariable",
                        "message": '"undefined_name" is not defined', "range": {"start": {"line": i, "character": 0}}})
print(json.dumps({"generalDiagnostics": out}))
sys.exit(1 if out else 0)
"""
FAKE_RUFF = "#!/bin/sh\necho '[]'\n"
FAKE_NIX_FAIL = "#!/bin/sh\necho 'error: no network' >&2\nexit 1\n"


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


class Repo:
    def __init__(self, tools=("basedpyright", "ruff"), nix_fails=False):
        self.dir = tempfile.mkdtemp()
        self.bin = os.path.join(self.dir, "_bin")
        os.makedirs(self.bin)
        self.root = os.path.join(self.dir, "repo")
        os.makedirs(self.root)
        fakes = {"basedpyright": FAKE_BP, "ruff": FAKE_RUFF}
        for t in tools:
            self.put(os.path.join(self.bin, t), fakes[t], 0o755)
        if nix_fails:
            self.put(os.path.join(self.bin, "nix"), FAKE_NIX_FAIL, 0o755)
        # PATH is the fake bin dir only (git linked in): a real ruff/basedpyright/nix must not leak in.
        for t in ("git", "python3"):
            os.symlink(shutil.which(t), os.path.join(self.bin, t))
        self.env = {"PATH": self.bin, "HOME": self.dir, "GIT_CONFIG_GLOBAL": "/dev/null"}
        sh(["git", "init", "-q"], self.root, self.env)
        sh(["git", "config", "user.email", "t@t"], self.root, self.env)
        sh(["git", "config", "user.name", "t"], self.root, self.env)

    @staticmethod
    def put(path, text, mode=0o644):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, mode)

    def write(self, rel, text):
        self.put(os.path.join(self.root, rel), text)

    def git(self, *a):
        return sh(["git", *a], self.root, self.env)

    def gate(self, *a):
        return sh([sys.executable, GATE, *a], self.root, self.env)

    def baseline(self):
        with open(os.path.join(self.root, "config", "python-check-baseline.json")) as f:
            return json.load(f)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class CheckPythonTypes(unittest.TestCase):
    def setUp(self):
        self.r = Repo()
        self.addCleanup(self.r.close)

    def test_new_undefined_name_in_staged_file_fails(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        p = self.r.gate("--staged")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("reportUndefinedVariable", p.stdout)
        self.assertIn("a.py", p.stdout)

    def test_baselined_diagnostic_passes(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.assertEqual(self.r.gate("--write-baseline").returncode, 0)
        p = self.r.gate("--staged")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.r.gate("--all").returncode, 0)

    def test_moved_baselined_diagnostic_passes(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.r.gate("--write-baseline")
        self.r.write("a.py", "import os\n\n\n\ny = 1\nx = undefined_name\n")
        self.r.git("add", "a.py")
        p = self.r.gate("--staged")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_second_occurrence_of_baselined_fingerprint_fails(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.r.gate("--write-baseline")
        self.r.write("a.py", "x = undefined_name\ny = undefined_name\n")
        self.r.git("add", "a.py")
        self.assertEqual(self.r.gate("--staged").returncode, 1)

    def test_write_baseline_refuses_growth_without_flag(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.r.gate("--write-baseline")
        self.r.write("b.py", "y = undefined_name\n")
        self.r.git("add", "b.py")
        p = self.r.gate("--write-baseline")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("--allow-growth", p.stdout)
        self.assertEqual(self.r.baseline()["totals"]["basedpyright"], 1)
        p = self.r.gate("--write-baseline", "--allow-growth")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.r.baseline()["totals"]["basedpyright"], 2)

    def test_write_baseline_may_shrink(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.r.gate("--write-baseline")
        self.r.write("a.py", "x = 1\n")
        self.r.git("add", "a.py")
        self.assertEqual(self.r.gate("--write-baseline").returncode, 0)
        self.assertEqual(self.r.baseline()["totals"]["basedpyright"], 0)

    def test_staged_file_with_unstaged_changes_fails(self):
        self.r.write("a.py", "x = undefined_name\n")
        self.r.git("add", "a.py")
        self.r.write("a.py", "x = 1\n")  # unstaged fix hides the staged breakage
        p = self.r.gate("--staged")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("unstaged changes", p.stdout)
        self.assertIn("a.py", p.stdout)
        self.r.git("add", "a.py")
        self.assertEqual(self.r.gate("--staged").returncode, 0)

    def test_excluded_paths_are_not_checked(self):
        self.r.write(".agent/archive/old.py", "x = undefined_name\n")
        self.r.git("add", "-f", ".agent/archive/old.py")
        self.assertEqual(self.r.gate("--staged").returncode, 0)


class MissingTool(unittest.TestCase):
    def test_missing_tool_with_failing_nix_build_fails(self):
        r = Repo(tools=("ruff",), nix_fails=True)
        self.addCleanup(r.close)
        r.write("a.py", "x = 1\n")
        r.git("add", "a.py")
        p = r.gate("--staged")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("basedpyright", p.stdout + p.stderr)
        self.assertIn("not on PATH", p.stdout + p.stderr)

    def test_missing_tool_without_nix_fails(self):
        r = Repo(tools=("basedpyright",))
        self.addCleanup(r.close)
        r.write("a.py", "x = 1\n")
        r.git("add", "a.py")
        p = r.gate("--staged")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("ruff", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
