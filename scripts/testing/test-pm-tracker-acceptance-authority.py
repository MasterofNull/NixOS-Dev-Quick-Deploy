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


SHA40 = "a" * 40
SHA64 = "b" * 64


def good_receipt(**over):
    d = {"schema": 1, "pr": 1, "reviewed_head_sha": SHA40, "run_id": "r1",
         "reviewer_lane": "codex", "author_lane": "claude", "verdict": "PASS",
         "output_file": "x", "output_sha256": SHA64, "created_at": "2026-10-27T00:00:00Z"}
    d.update(over)
    return d


def run_with_receipt(content, by="codex"):
    rdir = REPO / ".agent" / "reviews" / "receipts"
    rdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=rdir, suffix=".json", mode="w") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))
        f.flush()
        rel = Path(f.name).relative_to(REPO).as_posix()
        return run_check({"status": "accepted", "by": by, "date": "2026-10-27", "receipt": rel})


class AcceptanceAuthority(unittest.TestCase):
    def test_non_owner_strings_fail(self):
        for by in ["antigravity", "anti-gravity", "G3mini", "codex2", "test-foo.sh", "test-foo.py",
                   None, "", "Claude Sonnet"]:
            rc, out = run_check({"status": "accepted", "by": by, "date": "2026-10-27"})
            self.assertEqual(rc, 1, f"{by!r}: {out}")
            self.assertIn("plan-x", out)
            self.assertIn("I1", out)
            if by:
                self.assertIn(str(by), out)

    def test_owner_passes(self):
        for by in ["hyperd", "hyperd (owner directive 2026-09-26)"]:
            rc, out = run_check({"status": "accepted", "by": by, "date": "2026-10-27"})
            self.assertEqual(rc, 0, f"{by!r}: {out}")

    def test_valid_receipt_passes(self):
        rc, out = run_with_receipt(good_receipt())
        self.assertEqual(rc, 0, out)
        rc, out = run_with_receipt(good_receipt(verdict="PASS_WITH_FOLLOWUPS", reviewer_lane=" Codex "))
        self.assertEqual(rc, 0, out)

    def test_invalid_receipts_fail(self):
        cases = {
            "empty": "",
            "request_changes": good_receipt(verdict="REQUEST_CHANGES"),
            "same_lane": good_receipt(author_lane="Codex"),
            "reviewer_ne_by": good_receipt(reviewer_lane="gemini"),
            "bad_schema": good_receipt(schema=2),
            "bad_head": good_receipt(reviewed_head_sha="abc"),
            "bad_out_sha": good_receipt(output_sha256="B" * 64),
            "no_run_id": good_receipt(run_id=""),
            "not_object": "[1]",
        }
        for name, c in cases.items():
            rc, out = run_with_receipt(c)
            self.assertEqual(rc, 1, f"{name}: {out}")

    def test_missing_or_escaping_receipt_fails(self):
        for r in [".agent/reviews/receipts/does-not-exist.json",
                  ".agent/reviews/receipts/../../README.md", "/etc/passwd"]:
            rc, out = run_check({"status": "accepted", "by": "codex", "date": "2026-10-27", "receipt": r})
            self.assertEqual(rc, 1, f"{r}: {out}")

    def test_allowlisted_legacy_passes_with_warn(self):
        data = json.loads((REPO / "config" / "pm-tracker-legacy-acceptances.json").read_text())
        e = data["entries"][0]
        rc, out = run_check({"status": "accepted", "by": e["by"], "date": "2026-10-27"},
                            plan_name=e["plan"], item_id=e["item"])
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN", out)

    def test_legacy_allowlist_remove_only(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("aq_pm_tracker", str(TRACKER))
        spec = importlib.util.spec_from_loader("aq_pm_tracker", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        base = {("p", "i1", "a"), ("p", "i2", "b")}
        self.assertEqual(mod.legacy_additions({("p", "i1", "a")}, base), set())
        self.assertEqual(mod.legacy_additions(base, base), set())
        self.assertEqual(mod.legacy_additions(base | {("p", "i3", "c")}, base), {("p", "i3", "c")})
        self.assertEqual(mod._legacy_entries('{"entries":[{"plan":"p","item":"i","by":"x"}]}'),
                         {("p", "i", "x")})


if __name__ == "__main__":
    unittest.main()
