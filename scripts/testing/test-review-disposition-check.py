#!/usr/bin/env python3
"""Tests for scripts/governance/check-review-disposition.py (review-disposition required PR check)."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/governance/check-review-disposition.py"
spec = importlib.util.spec_from_file_location("crd", SCRIPT)
crd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crd)

HEAD = "a" * 40
BODY = (
    "Author-lane: claude\nReview-Disposition: PASS\n"
    f"Reviewed-subject-sha256: {'b' * 64}\nReviewed-head-sha: {HEAD}\nReviewed-by: codex\n"
)


def ev(body, head=HEAD):
    return {"pull_request": {"body": body, "head": {"sha": head}}}


class T(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(crd.check(ev(BODY)), [])
        self.assertEqual(crd.check(ev(BODY.replace("PASS", "PASS_WITH_FOLLOWUPS", 1).replace("\n", "\r\n"))), [])

    def test_missing_fields(self):
        errs = crd.check(ev("just a summary"))
        self.assertGreaterEqual(len(errs), 5)
        self.assertEqual(crd.check(ev(None))[0], "missing Review-Disposition")

    def test_same_lane(self):
        errs = crd.check(ev(BODY.replace("Reviewed-by: codex", "Reviewed-by: Claude")))
        self.assertTrue(any("must differ" in e for e in errs))

    def test_stale_head(self):
        errs = crd.check(ev(BODY, head="c" * 40))
        self.assertTrue(any("stale review" in e for e in errs))

    def test_bad_disposition_and_hex(self):
        errs = crd.check(ev(BODY.replace("PASS", "ACCEPTED", 1).replace("b" * 64, "xyz")))
        self.assertEqual(len(errs), 2)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            for body, rc in ((BODY, 0), ("x", 1)):
                p = pathlib.Path(d) / "e.json"
                p.write_text(json.dumps(ev(body)))
                r = subprocess.run([sys.executable, str(SCRIPT), str(p)], capture_output=True)
                self.assertEqual(r.returncode, rc)


def _run(cwd, *a):
    return subprocess.run(["/run/current-system/sw/bin/git" if pathlib.Path("/run/current-system/sw/bin/git").exists() else "git", *a],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class MergeTolerant(unittest.TestCase):
    """Head-binding with a real temp repo: merge-only updates pass, content changes fail."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        g = lambda *a: _run(self.d, *a)
        g("init", "-q", "-b", "main")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        g("config", "commit.gpgsign", "false")
        (pathlib.Path(self.d) / "base.txt").write_text("base\n")
        g("add", "."); g("commit", "-qm", "base")
        self.base0 = g("rev-parse", "HEAD")
        g("checkout", "-qb", "pr")
        (pathlib.Path(self.d) / "feat.txt").write_text("feat\n")
        g("add", "."); g("commit", "-qm", "feat")
        self.reviewed = g("rev-parse", "HEAD")
        g("checkout", "-q", "main")
        (pathlib.Path(self.d) / "other.txt").write_text("other\n")
        g("add", "."); g("commit", "-qm", "main moves")
        self.base1 = g("rev-parse", "HEAD")
        g("checkout", "-q", "pr")
        self.g = g

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, head, reviewed=None, base=None):
        body = BODY.replace(HEAD, reviewed or self.reviewed)
        e = {"pull_request": {"body": body, "head": {"sha": head}, "base": {"sha": base or self.base1}}}
        old = os.getcwd()
        os.chdir(self.d)
        try:
            return crd.check(e)
        finally:
            os.chdir(old)

    def test_merge_only_update_passes(self):
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        self.assertEqual(self._check(self.g("rev-parse", "HEAD")), [])

    def test_extra_commit_fails(self):
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        (pathlib.Path(self.d) / "feat.txt").write_text("changed\n")
        self.g("commit", "-qam", "extra")
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("stale review" in e and "net change differs" in e for e in errs), errs)

    def test_not_ancestor_fails(self):
        self.g("commit", "-q", "--amend", "-m", "rewritten")
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("stale review" in e and "not an ancestor" in e for e in errs), errs)

    def test_missing_reviewed_fails(self):
        errs = self._check(self.g("rev-parse", "HEAD"), reviewed="d" * 40)
        self.assertTrue(any("stale review" in e and "unavailable" in e for e in errs), errs)

    def test_whitespace_only_change_fails(self):
        f = pathlib.Path(self.d) / "m.py"
        self.g("checkout", "-q", "-B", "pr", self.reviewed)
        f.write_text("if x:\n    a()\nb()\n")
        self.g("add", "."); self.g("commit", "-qm", "py")
        self.reviewed = self.g("rev-parse", "HEAD")
        f.write_text("if x:\n    a()\n    b()\n")
        self.g("commit", "-qam", "indent")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("net change differs" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
