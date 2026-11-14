#!/usr/bin/env python3
"""Outcome receipts: append, quarantine on secrets, null tokens, exact scoreboard counts."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import outcome_receipt as orc  # noqa: E402

BOARD = ROOT / "scripts/ai/aq-scoreboard"
H = "a" * 40


def _registry(d: Path, rows: list[dict]) -> None:
    (d / "registry.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _lines(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


class Receipt(unittest.TestCase):
    def setUp(self) -> None:
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)

    def tearDown(self) -> None:
        self._t.cleanup()

    def test_append_and_mode(self) -> None:
        _registry(self.d, [{"id": "r1", "agent": "gemini", "tokens_in": 100, "tokens_out": 20}])
        out = orc.record_landing(self.d, pr=1, head=H, author_lane="claude",
                                 reviews=[{"lane": "gemini", "run_id": "r1", "verdict": "PASS"}], ci="pass")
        self.assertEqual(out, "written")
        rec = _lines(self.d / orc.LOG)[0]
        self.assertEqual(rec["tokens"], {"gemini": {"in": 100, "out": 20}})
        self.assertEqual(rec["head_sha"], H)
        self.assertEqual(stat.S_IMODE((self.d / orc.LOG).stat().st_mode), 0o600)
        self.assertEqual(orc.record_landing(self.d, pr=1, head=H, author_lane="claude", reviews=[]), "duplicate")
        self.assertEqual(len(_lines(self.d / orc.LOG)), 1)

    def test_unknown_tokens_are_null(self) -> None:
        _registry(self.d, [{"id": "r1", "agent": "local-direct", "tokens_in": None, "tokens_out": None}])
        orc.record_landing(self.d, pr=2, head=H, author_lane="claude",
                           reviews=[{"lane": "local", "run_id": "r1", "verdict": "PASS"},
                                    {"lane": "codex", "run_id": "missing", "verdict": "PASS"}])
        t = _lines(self.d / orc.LOG)[0]["tokens"]
        self.assertEqual(t["local"], {"in": None, "out": None})
        self.assertEqual(t["codex"], {"in": None, "out": None})

    def test_secret_is_quarantined(self) -> None:
        bad = ["x password=hunter2hunter2", "/home/someone/file", "Bearer abcdefghijklmnopqrstuvwxyz0123",
               "Zk9QxLm3VbN8cR2tYw7HdFg5JpA1sEu4"]
        for i, lane in enumerate(bad, start=10):
            self.assertEqual(orc.record_landing(self.d, pr=i, head=H, author_lane=lane, reviews=[]), "quarantined", lane)
        self.assertFalse((self.d / orc.LOG).exists())
        q = (self.d / orc.QUARANTINE).read_text()
        self.assertNotIn("hunter2hunter2", q)
        self.assertEqual(len(q.splitlines()), 4)


class Board(unittest.TestCase):
    def test_counts_exact(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            _registry(d, [{"id": "a", "tokens_in": 10, "tokens_out": 1}, {"id": "b", "tokens_in": 5, "tokens_out": 2},
                          {"id": "c"}])
            spec = [  # pr, author, reviewer lane, run, rc rounds, tier0 fails, ci fails, date
                (1, "claude", "gemini", "a", 1, 0, 0, "2026-11-12T10:00:00Z"),
                (2, "claude", "codex", "b", 0, 1, 0, "2026-11-13T10:00:00Z"),
                (3, "codex", "gemini", "c", 2, 0, 1, "2026-11-13T11:00:00Z"),
                (4, "gemini", "local", "zz", 0, 0, 0, "2026-11-13T12:00:00Z"),
                (5, "claude", "gemini", "a", 0, 2, 0, "2026-11-13T13:00:00Z"),
            ]
            for pr, au, lane, run, rc, t0, ci, ts in spec:
                orc.record_landing(d, pr=pr, head=H, author_lane=au, reviews=[{"lane": lane, "run_id": run, "verdict": "PASS"}],
                                   request_changes_rounds=rc, tier0_failures=t0, ci_failures=ci, now=ts)
            orc.record_landing(d, pr=6, head=H, author_lane="a password=hunter2hunter2", reviews=[], now="2026-11-13T14:00:00Z")
            r = subprocess.run([sys.executable, str(BOARD), "--dir", str(d), "--json"], capture_output=True, text=True, check=True)
            s = json.loads(r.stdout)
            self.assertEqual(s["prs_landed"], 5)
            self.assertEqual(s["by_author_lane"], {"claude": 3, "codex": 1, "gemini": 1})
            self.assertEqual(s["by_reviewer_lane"], {"gemini": 3, "codex": 1, "local": 1})
            self.assertEqual(s["request_changes_rounds"], 3)
            self.assertEqual(s["tier0_failures_before_merge"], 3)
            self.assertEqual(s["ci_failures_before_merge"], 1)
            self.assertEqual(s["quarantined"], 1)
            self.assertEqual(s["tokens_by_lane"]["gemini"], {"in": 20, "out": 2, "known": 2, "unknown": 1})
            self.assertEqual(s["tokens_by_lane"]["codex"], {"in": 5, "out": 2, "known": 1, "unknown": 0})
            self.assertEqual(s["tokens_by_lane"]["local"], {"in": 0, "out": 0, "known": 0, "unknown": 1})
            r = subprocess.run([sys.executable, str(BOARD), "--dir", str(d), "--json", "--since", "2026-11-13"],
                               capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(r.stdout)["prs_landed"], 4)
            text = subprocess.run([sys.executable, str(BOARD), "--dir", str(d)], capture_output=True, text=True, check=True).stdout
            self.assertIn("PRs landed: 5", text)


if __name__ == "__main__":
    os.environ.pop("AQ_DELEGATION_DIR", None)
    unittest.main()
