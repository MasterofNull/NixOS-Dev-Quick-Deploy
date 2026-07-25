#!/usr/bin/env python3
"""Offline test suite for scripts/ai/aq-plans-index.

No network access, no dependence on the real repo's .agents/plans/ state.
Loads the target script via importlib (it ships without a .py extension),
builds a synthetic plans tree per-test in a tmpdir, monkeypatches the
module's PLANS_DIR global and _git_last_date() so recency is deterministic,
and exercises: lifecycle overrides, tracker.json rollups, the recency
heuristic, STATUS_ORDER sorting, `--check` drift detection, render_html()
self-containment (artifact-CSP-safe: no external refs), and index()
determinism.

Run: python3 scripts/testing/test-plans-index.py
"""
from __future__ import annotations

import datetime
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "scripts" / "ai" / "aq-plans-index"


def _load_module():
    # TARGET has no .py suffix, so spec_from_file_location can't infer a
    # loader from the extension — build the SourceFileLoader explicitly.
    loader = importlib.machinery.SourceFileLoader("aq_plans_index_under_test", str(TARGET))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, obj) -> None:
    _write(path, json.dumps(obj))


class PlansIndexTestBase(unittest.TestCase):
    """Loads a fresh module instance + builds an isolated fixture tree per test."""

    def setUp(self):
        self.mod = _load_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.plans_dir = Path(self._tmp.name) / "plans"
        self.plans_dir.mkdir(parents=True)
        # Monkeypatch the module globals — index()/_plan_record() read these
        # as module-level names at call time, so reassigning here is enough.
        self.mod.PLANS_DIR = self.plans_dir
        self._dates: dict[str, str] = {}
        self.mod._git_last_date = self._fake_git_last_date

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_git_last_date(self, rel: str) -> str:
        return self._dates.get(rel, "")

    def _mk_plan(self, name: str, *, date: str | None = None) -> Path:
        d = self.plans_dir / name
        d.mkdir(parents=True)
        _write(d / "README.md", f"# {name.replace('-', ' ').title()}\n")
        if date is not None:
            self._dates[f".agents/plans/{name}"] = date
        return d


class LifecycleOverrideTests(PlansIndexTestBase):
    def test_superseded_records_status_and_pointer(self):
        d = self._mk_plan("plan-a", date="2026-07-01")
        _write_json(d / ".plan-lifecycle.json",
                    {"lifecycle": "superseded", "superseded_by": "plan-b"})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "superseded")
        self.assertEqual(rec["superseded_by"], "plan-b")

    def test_complete_lifecycle_honored(self):
        d = self._mk_plan("plan-b")
        _write_json(d / ".plan-lifecycle.json", {"lifecycle": "complete"})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "complete")

    def test_retired_lifecycle_honored(self):
        d = self._mk_plan("plan-c")
        _write_json(d / ".plan-lifecycle.json", {"lifecycle": "retired"})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "retired")

    def test_active_lifecycle_honored(self):
        d = self._mk_plan("plan-d")
        _write_json(d / ".plan-lifecycle.json", {"lifecycle": "active"})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "active")

    def test_invalid_lifecycle_falls_through_to_projection(self):
        # No tracker, old date -> projection must yield 'dormant', not the bogus value.
        d = self._mk_plan("plan-e", date="2020-01-01")
        _write_json(d / ".plan-lifecycle.json", {"lifecycle": "bogus-value"})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "dormant")
        self.assertNotEqual(rec["status"], "bogus-value")


class TrackerRollupTests(PlansIndexTestBase):
    def test_all_done_rolls_up_to_done(self):
        d = self._mk_plan("plan-done")
        _write_json(d / "tracker.json", {"items": [{"status": "done"}, {"status": "complete"}]})
        rec = self.mod._plan_record(d)
        self.assertIn(rec["status"], ("done", "complete"))
        self.assertTrue(rec["has_tracker"])
        self.assertFalse(rec["untracked"])

    def test_any_blocked_rolls_up_to_blocked(self):
        d = self._mk_plan("plan-blocked")
        _write_json(d / "tracker.json", {"items": [{"status": "done"}, {"status": "blocked"}]})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "blocked")

    def test_mixed_statuses_roll_up_to_active(self):
        d = self._mk_plan("plan-mixed")
        _write_json(d / "tracker.json", {"items": [{"status": "done"}, {"status": "review"}]})
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "active")


class RecencyHeuristicTests(PlansIndexTestBase):
    def test_recent_date_is_active_and_untracked(self):
        recent = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        d = self._mk_plan("plan-recent", date=recent)
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "active")
        self.assertTrue(rec["untracked"])

    def test_old_date_is_dormant(self):
        old = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
        d = self._mk_plan("plan-old", date=old)
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "dormant")

    def test_no_date_is_dormant(self):
        d = self._mk_plan("plan-nodate")  # no fixture date -> _git_last_date returns ""
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "dormant")
        self.assertEqual(rec["last_activity"], "")

    def test_untracked_flag_true_without_tracker_json(self):
        d = self._mk_plan("plan-untracked", date="2026-07-01")
        rec = self.mod._plan_record(d)
        self.assertTrue(rec["untracked"])
        self.assertFalse(rec["has_tracker"])

    def test_boundary_90_days_is_active(self):
        d90 = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
        d = self._mk_plan("plan-boundary-90", date=d90)
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "active")

    def test_boundary_91_days_is_dormant(self):
        d91 = (datetime.date.today() - datetime.timedelta(days=91)).isoformat()
        d = self._mk_plan("plan-boundary-91", date=d91)
        rec = self.mod._plan_record(d)
        self.assertEqual(rec["status"], "dormant")


class SortingTests(PlansIndexTestBase):
    def test_status_order_and_recency_within_group(self):
        today = datetime.date.today()
        self._mk_plan("z-active-recent", date=(today - datetime.timedelta(days=1)).isoformat())
        self._mk_plan("a-active-older", date=(today - datetime.timedelta(days=5)).isoformat())
        d_blocked = self._mk_plan("m-blocked")
        _write_json(d_blocked / "tracker.json", {"items": [{"status": "blocked"}]})
        self._mk_plan("b-dormant", date=(today - datetime.timedelta(days=200)).isoformat())
        d_superseded = self._mk_plan("c-superseded")
        _write_json(d_superseded / ".plan-lifecycle.json",
                    {"lifecycle": "superseded", "superseded_by": "x"})

        data = self.mod.index()
        ids = [p["id"] for p in data["plans"]]

        # STATUS_ORDER group ordering: blocked(0) < active(1) < dormant(3) < superseded(5)
        self.assertLess(ids.index("m-blocked"), ids.index("z-active-recent"))
        self.assertLess(ids.index("z-active-recent"), ids.index("b-dormant"))
        self.assertLess(ids.index("b-dormant"), ids.index("c-superseded"))

        # Within the active group: most-recent-first.
        self.assertLess(ids.index("z-active-recent"), ids.index("a-active-older"))


class CheckDriftTests(PlansIndexTestBase):
    def test_check_passes_on_identical_baseline(self):
        self._mk_plan("plan-x", date="2026-07-01")
        data = self.mod.index()
        baseline_file = Path(self._tmp.name) / "baseline.json"
        _write(baseline_file, json.dumps(data))
        rc = self.mod.main(["--check", "--baseline", str(baseline_file)])
        self.assertEqual(rc, 0)

    def test_check_ignores_generated_field(self):
        self._mk_plan("plan-y", date="2026-07-01")
        data = self.mod.index()
        base = dict(data)
        base["generated"] = "1999-01-01"  # different 'generated', everything else identical
        baseline_file = Path(self._tmp.name) / "baseline2.json"
        _write(baseline_file, json.dumps(base))
        rc = self.mod.main(["--check", "--baseline", str(baseline_file)])
        self.assertEqual(rc, 0)

    def test_check_fails_on_changed_status(self):
        self._mk_plan("plan-z", date="2026-07-01")
        data = self.mod.index()
        base = json.loads(json.dumps(data))  # deep copy
        base["plans"][0]["status"] = "blocked"
        base["by_status"] = {"blocked": 1}
        baseline_file = Path(self._tmp.name) / "baseline3.json"
        _write(baseline_file, json.dumps(base))
        rc = self.mod.main(["--check", "--baseline", str(baseline_file)])
        self.assertEqual(rc, 1)


class RenderHtmlTests(PlansIndexTestBase):
    def test_render_contains_viz_cards_rows_and_no_external_refs(self):
        self._mk_plan("plan-one", date="2026-07-01")
        self._mk_plan("plan-two", date="2020-01-01")
        data = self.mod.index()
        out = self.mod.render_html(data)

        self.assertIn("distbar", out)
        self.assertIn("pbar-fill", out)
        self.assertIn("hist", out)

        row_count = out.count('<tr data-status="')
        self.assertEqual(row_count, len(data["plans"]))

        # Self-contained / artifact-CSP-safe: no external network references.
        self.assertNotIn("http://", out)
        self.assertNotIn("https://", out)
        self.assertNotIn("@import", out)
        self.assertNotIn("cdn", out.lower())
        self.assertNotRegex(out, r"\bsrc=")
        self.assertNotRegex(out, r'href="http')


class DeterminismTests(PlansIndexTestBase):
    def test_index_twice_matches_except_generated(self):
        self._mk_plan("plan-alpha", date="2026-07-01")
        d_beta = self._mk_plan("plan-beta")
        _write_json(d_beta / "tracker.json", {"items": [{"status": "done"}]})

        d1 = self.mod.index()
        d2 = self.mod.index()
        a = {k: v for k, v in d1.items() if k != "generated"}
        b = {k: v for k, v in d2.items() if k != "generated"}
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
