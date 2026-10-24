#!/usr/bin/env python3
"""Regression test suite for aq-decide DEC-S9 & DEC-S10."""
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts" / "ai" / "lib"))

from approval_inbox import triage_approvals_advisory
from aq_decide import evaluate_gliclass_candidate


class TestAqDecideS9S10(unittest.TestCase):

    def test_s9_approvals_triage_critical_keywords(self):
        items = [
            {"title": "Routine task", "detail": "standard update", "severity": "low", "action": "run test"},
            {"title": "Nix rebuild switch", "detail": "execute sudo nixos-rebuild switch", "severity": "medium", "action": "deploy"},
            {"title": "Bug fix", "detail": "minor typo", "severity": "high", "action": "commit"},
        ]
        triaged = triage_approvals_advisory(items)
        # Sudo / rebuild item must be high_impact and first
        self.assertEqual(triaged[0]["approval_class"], "high_impact")
        self.assertEqual(triaged[0]["approval_urgency"], "high")
        # High severity without critical keyword should be needs_read
        self.assertEqual(triaged[1]["approval_class"], "needs_read")
        # Routine item should be routine
        self.assertEqual(triaged[2]["approval_class"], "routine")

    def test_s9_cannot_downrank_critical_security(self):
        items = [
            {"title": "Secret rotation", "detail": "rotate api keys", "severity": "low", "action": "none"}
        ]
        triaged = triage_approvals_advisory(items)
        self.assertEqual(triaged[0]["approval_class"], "high_impact")

    def test_s10_gliclass_evaluation_pending(self):
        res = evaluate_gliclass_candidate("/nonexistent/model.onnx")
        self.assertEqual(res["candidate"], "gliclass-modernbert-onnx")
        self.assertFalse(res["model_present"])
        self.assertEqual(res["evaluation_verdict"], "PENDING_INTAKE")

    def test_s10_gliclass_evaluation_verified(self):
        with tempfile.TemporaryDirectory() as td:
            mpath = Path(td) / "model.onnx"
            mpath.write_text("dummy onnx")
            manifest = Path(td) / "model.onnx.manifest.json"
            manifest.write_text('{"status": "verified"}')
            res = evaluate_gliclass_candidate(mpath)
            self.assertTrue(res["model_present"])
            self.assertTrue(res["intake_verified"])


if __name__ == "__main__":
    unittest.main()
