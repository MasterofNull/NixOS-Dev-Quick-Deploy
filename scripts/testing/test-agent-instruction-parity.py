#!/usr/bin/env python3
"""Focused tests for scripts/governance/check-agent-instruction-parity.py."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("parity", REPO / "scripts/governance/check-agent-instruction-parity.py")
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)

MANIFEST = """
blocks:
  rules:
    source: blocks/rules.md
    targets: [A.md, {path: B.md, mode: summary}]
agent_files:
  budget_bytes: 400
  lane_budget_bytes: 100
  files: [A.md, B.md]
"""
GOOD = "# x\n<!-- lane:begin -->\nlane\n<!-- lane:end -->\n<!-- canon:begin rules -->\nr\n<!-- canon:end rules -->\n"


def make(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "canon").mkdir()
    (root / "canon/canon.yaml").write_text(MANIFEST)
    for k, v in files.items():
        (root / k).write_text(v)
    return root


class ParityTests(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(parity.check(make({"A.md": GOOD, "B.md": GOOD})), [])

    def test_missing_block(self):
        bad = GOOD.replace("canon:begin rules", "x").replace("canon:end rules", "y")
        out = parity.check(make({"A.md": bad, "B.md": GOOD}))
        self.assertEqual(len(out), 1)
        self.assertIn("A.md", out[0])
        self.assertIn("'rules' missing", out[0])

    def test_over_budget(self):
        out = parity.check(make({"A.md": GOOD + "x" * 500, "B.md": GOOD}))
        self.assertTrue(any("exceeds budget" in p for p in out))

    def test_lane_over_budget(self):
        big = GOOD.replace("lane\n", "l" * 150 + "\n")
        out = parity.check(make({"A.md": GOOD, "B.md": big}))
        self.assertTrue(any("lane region" in p and "B.md" in p for p in out))

    def test_missing_lane_region(self):
        out = parity.check(make({"A.md": GOOD.replace("<!-- lane:begin -->", ""), "B.md": GOOD}))
        self.assertTrue(any("lane region" in p for p in out))

    def test_real_repo_passes(self):
        self.assertEqual(parity.check(REPO), [])


if __name__ == "__main__":
    unittest.main()
