#!/usr/bin/env python3
"""Offline trajectory collector (F3 S5): eligibility, privacy, file modes, idempotence, kill switch, range retry."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/data/collect-verified-trajectories.py"
BOARD = ROOT / "scripts/ai/aq-scoreboard"
spec = importlib.util.spec_from_file_location("collector", SCRIPT)
assert spec is not None and spec.loader is not None
col: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(col)

GH = """#!/bin/sh
# stub gh: `gh pr view N --json ...` prints $STUB_GH_JSON
[ "$1 $2" = "pr view" ] || exit 1
[ -n "$STUB_GH_JSON" ] || exit 1
printf '%s' "$STUB_GH_JSON"
"""


def _git(repo: Path, *a: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True, env=env).stdout.strip()


def _receipt(pr: int, **kw) -> dict:
    r = {"schema": 1, "pr": pr, "head_sha": "a" * 40, "author_lane": "claude", "reviewer_lanes": ["gemini"],
         "review_verdicts": ["PASS"], "request_changes_rounds": 0, "tier0": None, "ci": "pass", "tier0_failures": 0,
         "ci_failures": 0, "tokens": {"gemini": {"in": 1, "out": 2}}, "recorded_at": "2026-11-14T10:00:00Z"}
    r.update(kw)
    return r


class Collector(unittest.TestCase):
    def setUp(self) -> None:
        self._t = tempfile.TemporaryDirectory(dir=os.environ.get("TEST_TMP"))
        t = Path(self._t.name)
        self.d, self.repo, self.bin = t / "deleg", t / "repo", t / "bin"
        self.d.mkdir()
        self.bin.mkdir()
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("1\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "base")
        self.base = _git(self.repo, "rev-parse", "HEAD")
        (self.repo / "a.txt").write_text("1\n2\n3\n")
        (self.repo / "etc/run/secrets").mkdir(parents=True)
        (self.repo / "etc/run/secrets/k.txt").write_text("x\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "secret-path")
        self.mid = _git(self.repo, "rev-parse", "HEAD")
        (self.repo / "c.txt").write_text("z\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "clean")
        self.head = _git(self.repo, "rev-parse", "HEAD")
        gh = self.bin / "gh"
        gh.write_text(GH)
        gh.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", AQ_DELEGATION_DIR=str(self.d))
        self.env.pop("AQ_TRAJECTORY_COLLECT", None)
        self.set_gh(self.mid, self.head)  # default range: only c.txt
        self._old = dict(os.environ)
        os.environ.update(self.env)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self._t.cleanup()

    def set_gh(self, base: str, head: str) -> None:
        self.env["STUB_GH_JSON"] = json.dumps({"mergeCommit": {"oid": "c" * 40}, "baseRefOid": base, "headRefOid": head})
        os.environ["STUB_GH_JSON"] = self.env["STUB_GH_JSON"]

    def receipts(self, *recs: dict) -> None:
        (self.d / "outcome-receipts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))

    def lines(self, name: str) -> list[dict]:
        p = self.d / name
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def run_cli(self, *args: str, **env) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo), *args], capture_output=True,
                              text=True, env=dict(self.env, **env))

    def collect(self, **kw) -> dict:
        return col.collect(self.d, self.d, self.repo, **kw)

    def test_a_eligible_row_0600_with_rc_then_pass(self) -> None:
        self.receipts(_receipt(1), _receipt(2, request_changes_rounds=2, review_verdicts=["REQUEST_CHANGES", "PASS"]))
        c = self.collect()
        self.assertEqual(c["collected"], 2, c)
        rows = self.lines("trajectories.jsonl")
        self.assertEqual([r["rejected_rounds"] for r in rows], [0, 2])
        self.assertEqual(rows[0]["merge_sha"], "c" * 40)
        self.assertEqual(rows[0]["files"], [{"path": "c.txt", "added": 1, "deleted": 0}])
        self.assertEqual(stat.S_IMODE((self.d / "trajectories.jsonl").stat().st_mode), 0o600)

    def test_b_planted_secrets_quarantined_not_in_main(self) -> None:
        self.receipts(_receipt(1, author_lane="Bearer abcdefghijklmnopqrstuvwxyz0123"))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        self.set_gh(self.base, self.mid)  # a changed path under /run/secrets
        self.receipts(_receipt(2))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        self.assertFalse((self.d / "trajectories.jsonl").exists())
        q = (self.d / "trajectories.quarantine.jsonl").read_text()
        self.assertEqual(len(q.splitlines()), 2)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz0123", q)
        self.assertIn("pattern", q)

    def test_c_redacted_secret_still_quarantined(self) -> None:
        key = "AKIAIOSFODNN7EXAMPLE"
        row = json.dumps({"x": key})
        redacted, found = col._redact(row)
        self.assertNotIn(key, redacted)
        self.assertEqual(col.scan(redacted), [], "precondition: scan alone would pass the redacted text")
        self.receipts(_receipt(3, author_lane=key))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q = self.lines("trajectories.quarantine.jsonl")[0]
        self.assertNotIn(key, json.dumps(q))
        self.assertTrue(q["reasons"])

    def test_d_redactor_missing_quarantine_has_no_payload(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(4))
        orig = col._redact
        col._redact = lambda text: (text, ["redactor_unavailable"])
        try:
            c = self.collect()
        finally:
            col._redact = orig
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q = self.lines("trajectories.quarantine.jsonl")[0]
        self.assertEqual(set(q), {"pr", "recorded_at", "reasons"})
        self.assertEqual(q["reasons"], ["redactor_unavailable"])
        self.assertFalse((self.d / "trajectories.jsonl").exists())

    def test_e_group_readable_files_refuse(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(5))
        for name in ("trajectories.jsonl", "trajectories.quarantine.jsonl"):
            p = self.d / name
            p.write_text("")
            p.chmod(0o644)
            r = self.run_cli()
            self.assertEqual(r.returncode, 2, (name, r.stderr))
            self.assertIn("refusing", r.stderr)
            self.assertEqual(p.read_text(), "")
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o644, "mode must not be silently changed")
            p.unlink()
        self.assertEqual(self.run_cli().returncode, 0)

    def test_f_self_reviewed_and_ineligible_skipped(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(6, author_lane="gemini"), _receipt(7, ci=None), _receipt(8, review_verdicts=["REQUEST_CHANGES"]))
        c = self.collect()
        self.assertEqual((c["collected"], c["not_eligible"]), (0, 3), c)
        self.assertFalse((self.d / "trajectories.jsonl").exists())

    def test_g_second_run_adds_nothing(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(9), _receipt(10, author_lane="Bearer abcdefghijklmnopqrstuvwxyz0123"))
        self.assertEqual(self.run_cli().returncode, 0)
        n = (len(self.lines("trajectories.jsonl")), len(self.lines("trajectories.quarantine.jsonl")))
        self.assertEqual(n, (1, 1))
        c = json.loads(self.run_cli().stdout)
        self.assertEqual((c["collected"], c["quarantined"], c["already_done"]), (0, 0, 2), c)
        self.assertEqual((len(self.lines("trajectories.jsonl")), len(self.lines("trajectories.quarantine.jsonl"))), n)

    def test_h_kill_switch_writes_nothing(self) -> None:
        self.receipts(_receipt(11))
        r = self.run_cli(AQ_TRAJECTORY_COLLECT="0")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(sorted(p.name for p in self.d.iterdir()), ["outcome-receipts.jsonl"])

    def test_i_unreachable_range_quarantines_identifiers_and_retries(self) -> None:
        self.set_gh("d" * 40, "e" * 40)
        self.receipts(_receipt(12))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q = self.lines("trajectories.quarantine.jsonl")
        self.assertEqual(q, [{"pr": 12, "recorded_at": "2026-11-14T10:00:00Z", "reasons": ["range_unreachable"]}])
        self.assertFalse((self.d / "trajectories.jsonl").exists())
        c = self.collect()  # still unreachable: no duplicate quarantine row
        self.assertEqual((c["quarantined"], c["pending"]), (0, 1), c)
        self.assertEqual(len(self.lines("trajectories.quarantine.jsonl")), 1)
        self.set_gh(self.head, self.head)  # reachable now: retried and collected
        c = self.collect()
        self.assertEqual(c["collected"], 1, c)

    def test_gh_missing_is_pending(self) -> None:
        self.receipts(_receipt(13))
        os.environ.pop("STUB_GH_JSON")
        c = self.collect()
        self.assertEqual((c["pending"], c["collected"], c["quarantined"]), (1, 0, 0), c)

    def test_numstat_z_exact_paths(self) -> None:
        r = self.repo
        _git(r, "config", "core.quotepath", "true")
        (r / "mod.txt").write_text("".join(f"line{i}\n" for i in range(20)))
        _git(r, "add", ".")
        _git(r, "commit", "-qm", "pre")
        pre = _git(r, "rev-parse", "HEAD")
        uni, tab = "caf\u00e9-\u65e5\u672c.txt", "t\tab.txt"
        (r / uni).write_text("u\n")
        (r / tab).write_text("t\n")
        (r / "bin.dat").write_bytes(b"\x00\x01\x02\xff")
        _git(r, "mv", "mod.txt", "moved.txt")
        (r / "moved.txt").write_text("".join(f"line{i}\n" for i in range(20)) + "extra\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "paths")
        got = col._numstat(r, 1, pre, _git(r, "rev-parse", "HEAD"))
        by = {f["path"]: f for f in got}
        self.assertEqual(sorted(by), sorted([uni, tab, "bin.dat", "moved.txt"]), got)
        self.assertEqual((by["bin.dat"]["added"], by["bin.dat"]["deleted"]), (0, 0))
        self.assertEqual(by["moved.txt"]["renamed_from"], "mod.txt")
        self.assertEqual((by[uni]["added"], by[tab]["added"]), (1, 1))
        # privacy scan runs on these exact paths: a secret-looking path is still caught
        (r / "etc/run/secrets").mkdir(parents=True, exist_ok=True)
        (r / "etc/run/secrets/\u00e9.txt").write_text("x\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "sec")
        self.set_gh(_git(r, "rev-parse", "HEAD~1"), _git(r, "rev-parse", "HEAD"))
        self.receipts(_receipt(30))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

    def test_cr_and_non_utf8_paths_do_not_abort(self) -> None:
        r = self.repo
        cr = "a\rb.txt"
        bad = os.fsencode(r) + b"/bad\xff.txt"
        (r / cr).write_text("c\n")
        Path(os.fsdecode(bad)).write_text("b\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "odd")
        head = _git(r, "rev-parse", "HEAD")
        got = col._numstat(r, 1, self.head, head)
        paths = sorted(f["path"] for f in got)
        self.assertEqual(paths, sorted([cr, os.fsdecode(b"bad\xff.txt")]), got)  # \r exact, bytes reversible
        self.assertEqual(os.fsencode([p for p in paths if p != cr][0]), b"bad\xff.txt")
        self.set_gh(self.head, head)
        self.receipts(_receipt(40))
        c = self.collect()  # must not raise
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        self.assertEqual(self.lines("trajectories.quarantine.jsonl")[0]["reasons"], ["undecodable_path"])
        # \r-only path is collected with the exact name
        _git(r, "rm", "-q", "--cached", "bad\udcff.txt".encode("utf-8", "surrogateescape").decode("utf-8", "surrogateescape"))
        _git(r, "commit", "-qm", "drop")
        self.set_gh(self.head, _git(r, "rev-parse", "HEAD"))
        self.receipts(_receipt(41))
        c = self.collect()
        self.assertEqual(c["collected"], 1, c)
        row = [x for x in self.lines("trajectories.jsonl") if x["pr"] == 41][0]
        self.assertIn(cr, [f["path"] for f in row["files"]])

    def test_scoreboard_counts(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(14), _receipt(15, author_lane="Bearer abcdefghijklmnopqrstuvwxyz0123"),
                      _receipt(16, author_lane="gemini"), _receipt(17, ci=None))
        self.collect()
        out = subprocess.run([sys.executable, str(BOARD), "--dir", str(self.d), "--json"], capture_output=True, text=True,
                             check=True).stdout
        s = json.loads(out)
        self.assertIsInstance(s["trajectories_collected"], int)
        self.assertEqual((s["trajectories_collected"], s["trajectories_quarantined"], s["receipts_not_eligible"],
                          s["receipts_pending"]), (1, 1, 2, 0), s)

    def test_duplicate_receipts_one_run_one_row(self) -> None:
        self.set_gh(self.head, self.head)
        self.receipts(_receipt(50), _receipt(50, recorded_at="2026-11-14T11:00:00Z"))
        c = self.collect()
        self.assertEqual((c["collected"], c["already_done"]), (1, 1), c)
        self.assertEqual(len(self.lines("trajectories.jsonl")), 1)
        self.receipts(_receipt(51, author_lane="Bearer abcdefghijklmnopqrstuvwxyz0123"),
                      _receipt(51, author_lane="Bearer abcdefghijklmnopqrstuvwxyz0123"))
        c = self.collect()
        self.assertEqual((c["quarantined"], c["already_done"]), (1, 1), c)
        self.assertEqual(len([x for x in self.lines("trajectories.quarantine.jsonl") if x["pr"] == 51]), 1)

    def test_duplicate_unreachable_receipts_one_retry_row(self) -> None:
        self.set_gh("d" * 40, "e" * 40)
        self.receipts(_receipt(52), _receipt(52), _receipt(52))
        c = self.collect()
        self.assertEqual((c["quarantined"], c["pending"], c["already_done"]), (1, 0, 2), c)
        self.assertEqual(len(self.lines("trajectories.quarantine.jsonl")), 1)
        self.set_gh(self.head, self.head)  # retry then collect in one run: still one main row
        self.receipts(_receipt(52), _receipt(52))
        c = self.collect()
        self.assertEqual((c["collected"], c["already_done"]), (1, 1), c)
        self.assertEqual(len(self.lines("trajectories.jsonl")), 1)


if __name__ == "__main__":
    unittest.main()
