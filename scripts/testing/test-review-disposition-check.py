#!/usr/bin/env python3
"""Tests for scripts/governance/check-review-disposition.py (review-disposition required PR check)."""
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
