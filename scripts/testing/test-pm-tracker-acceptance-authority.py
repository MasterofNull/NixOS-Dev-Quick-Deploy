#!/usr/bin/env python3
"""Regression: agent lanes / test scripts cannot self-accept tracker items."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACKER = REPO / "scripts" / "ai" / "aq-pm-tracker"


def run_check(acceptance: dict, plan_name="plan-x", item_id="I1"):
    with tempfile.TemporaryDirectory() as td:
        plan = Path(td) / plan_name
        plan.mkdir()
        manifest = {
            "plan": {"title": "x"},
            "phases": [{"id": "p1", "name": "P1"}],
            "items": [{"id": item_id, "name": "i", "phase": "p1", "goal": "g",
                       "validation_goal": "v", "acceptance": acceptance}],
        }
        (plan / "tracker.json").write_text(json.dumps(manifest))
        r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--check"],
                           capture_output=True, text=True, cwd=REPO, timeout=120)
        return r.returncode, r.stdout + r.stderr


class AcceptanceAuthority(unittest.TestCase):
    def test_agent_self_acceptance_today_fails(self):
        rc, out = run_check({"status": "accepted", "by": "antigravity", "date": "2026-10-27"})
        self.assertEqual(rc, 1, out)
        self.assertIn("plan-x", out)
        self.assertIn("I1", out)
        self.assertIn("antigravity", out)

    def test_test_script_acceptor_fails(self):
        rc, out = run_check({"status": "accepted", "by": "test-foo.py", "date": "2026-10-27"})
        self.assertEqual(rc, 1, out)

    def test_agent_with_receipt_passes(self):
        rdir = REPO / ".agent" / "reviews" / "receipts"
        rdir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=rdir, suffix=".json") as f:
            rel = Path(f.name).relative_to(REPO).as_posix()
            rc, out = run_check({"status": "accepted", "by": "codex", "date": "2026-10-27",
                                 "receipt": rel})
        self.assertEqual(rc, 0, out)

    def test_agent_with_missing_receipt_fails(self):
        rc, out = run_check({"status": "accepted", "by": "codex", "date": "2026-10-27",
                             "receipt": ".agent/reviews/receipts/does-not-exist.json"})
        self.assertEqual(rc, 1, out)

    def test_human_passes(self):
        rc, out = run_check({"status": "accepted", "by": "hyperd", "date": "2026-10-27"})
        self.assertEqual(rc, 0, out)

    def test_allowlisted_legacy_passes_with_warn(self):
        data = json.loads((REPO / "config" / "pm-tracker-legacy-acceptances.json").read_text())
        e = data["entries"][0]
        rc, out = run_check({"status": "accepted", "by": e["by"], "date": "2026-10-27"},
                            plan_name=e["plan"], item_id=e["item"])
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN", out)

    def test_backdated_agent_not_in_allowlist_fails(self):
        rc, out = run_check({"status": "accepted", "by": "Claude Sonnet", "date": "2026-10-01"})
        self.assertEqual(rc, 1, out)
        self.assertIn("Claude Sonnet", out)


if __name__ == "__main__":
    unittest.main()
