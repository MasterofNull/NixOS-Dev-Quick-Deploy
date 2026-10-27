#!/usr/bin/env python3
"""Tests for scripts/ai/aq-review-receipt (mint/verify/audit) with a temp registry."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/ai/aq-review-receipt"
HEAD = "a" * 40


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self._t.name)
        (self.d / "out").mkdir()
        self.log = self.d / "out/rev.log"
        self.log.write_text(f"reviewed {HEAD[:12]}\nReview-Disposition: PASS\n")
        self.reg = self.d / "registry.jsonl"
        self.set_entry()

    def tearDown(self):
        self._t.cleanup()

    def set_entry(self, **kw):
        e = {"id": "r1", "agent": "codex", "role": "reviewer", "output_file": "out/rev.log", "status": "done"}
        e.update(kw)
        self.reg.write_text(json.dumps(e) + "\n")

    def run_tool(self, *a):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.d), "--registry", str(self.reg), *a],
                              capture_output=True, text=True)

    def mint(self, author="claude", head=HEAD):
        return self.run_tool("mint", "--run-id", "r1", "--pr", "7", "--head", head, "--author-lane", author)

    @property
    def rfile(self):
        return self.d / f".agent/reviews/receipts/pr7-{HEAD[:12]}.json"

    def test_mint_and_verify(self):
        r = self.mint()
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(self.rfile.read_text())
        self.assertEqual((rec["reviewer_lane"], rec["verdict"], rec["output_file"]), ("codex", "PASS", "out/rev.log"))
        self.assertEqual(self.run_tool("verify", str(self.rfile)).returncode, 0)
        self.assertEqual(self.run_tool("audit").returncode, 0)

    def test_mint_rejections(self):
        self.assertNotEqual(self.mint(author="Codex").returncode, 0)
        self.assertNotEqual(self.mint(head="b" * 40).returncode, 0)  # head not in output
        self.set_entry(status="running")
        self.assertNotEqual(self.mint().returncode, 0)
        self.set_entry(role="implementer")
        self.assertNotEqual(self.mint().returncode, 0)
        self.log.write_text(f"{HEAD}\nno verdict\n")
        self.set_entry()
        self.assertNotEqual(self.mint().returncode, 0)

    def test_verify_detects_tamper_and_missing_run(self):
        self.assertEqual(self.mint().returncode, 0)
        self.log.write_text(self.log.read_text() + "edited\n")
        r = self.run_tool("verify", str(self.rfile))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sha256", r.stderr)
        self.reg.write_text("")
        self.assertNotEqual(self.run_tool("audit").returncode, 0)


if __name__ == "__main__":
    unittest.main()
