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
import time
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
receipt_spec = importlib.util.spec_from_file_location("outcome_receipt_mod", ROOT / "scripts/ai/lib/outcome_receipt.py")
assert receipt_spec is not None and receipt_spec.loader is not None
receipt_mod: Any = importlib.util.module_from_spec(receipt_spec)
receipt_spec.loader.exec_module(receipt_mod)

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

    def test_j_long_changed_repo_path_exempt_from_entropy_while_slash_secret_quarantines(self) -> None:
        r = self.repo
        long_rel = "docs/harness-first/evidence/2026-11-15-deploy-validation.md"
        self.assertEqual(col.scan(json.dumps({"path": long_rel})), ["entropy"],
                         "precondition: bare scan flags this 59-char path as entropy > 4.0")
        (r / long_rel).parent.mkdir(parents=True, exist_ok=True)
        (r / long_rel).write_text("ok\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "long-path")
        long_head = _git(r, "rev-parse", "HEAD")
        self.set_gh(self.head, long_head)
        self.receipts(_receipt(60))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (1, 0), c)
        # A real base64-like secret containing '/' in another field still quarantines with entropy
        slash_secret = "AbCdEfGhIjKlMnOpQrStUvWxYz012345/789+AbCdEf"
        self.receipts(_receipt(61, author_lane=slash_secret))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q = [x for x in self.lines("trajectories.quarantine.jsonl") if x["pr"] == 61][0]
        self.assertIn("entropy", q["reasons"])
        # A matching high-entropy token in an unrelated field must NOT be exempted by changed files
        self.receipts(_receipt(62, author_lane=long_rel))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q62 = [x for x in self.lines("trajectories.quarantine.jsonl") if x["pr"] == 62][0]
        self.assertIn("entropy", q62["reasons"])
        # Single-segment high-entropy filename (no '/') remains subject to entropy even when in allowed_paths
        single_seg = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        self.assertEqual(col.scan(json.dumps({"files": [{"path": single_seg}]}), allowed_paths={single_seg}), ["entropy"])

    def test_k_long_unicode_changed_path_and_renamed_from_exempt_while_unrelated_field_quarantines(self) -> None:
        r = self.repo
        uni_long = "caf\u00e9/docs/harness-first/evidence/2026-11-15-deploy-validation.md"
        self.assertEqual(col.scan(json.dumps({"path": uni_long})), ["entropy"],
                         "precondition: JSON escaping produces u00e9/docs/... with entropy > 4.0")
        (r / uni_long).parent.mkdir(parents=True, exist_ok=True)
        (r / uni_long).write_text("".join(f"line{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "unicode-long-path")
        uni_head = _git(r, "rev-parse", "HEAD")
        self.set_gh(self.head, uni_head)
        self.receipts(_receipt(63))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (1, 0), c)
        row63 = [x for x in self.lines("trajectories.jsonl") if x["pr"] == 63][0]
        self.assertEqual(row63["files"][0]["path"], uni_long)
        # Same Unicode path in renamed_from must also be exempt at the verified field occurrence
        (r / "docs/moved").mkdir(parents=True, exist_ok=True)
        _git(r, "mv", uni_long, "docs/moved/note.md")
        _git(r, "commit", "-qm", "rename-unicode-long-path")
        rename_head = _git(r, "rev-parse", "HEAD")
        self.set_gh(uni_head, rename_head)
        self.receipts(_receipt(64))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (1, 0), c)
        row64 = [x for x in self.lines("trajectories.jsonl") if x["pr"] == 64][0]
        self.assertEqual(row64["files"][0]["renamed_from"], uni_long)
        # Same Unicode path appearing in an unrelated field must still be quarantined
        self.receipts(_receipt(65, author_lane=uni_long))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)
        q65 = [x for x in self.lines("trajectories.quarantine.jsonl") if x["pr"] == 65][0]
        self.assertIn("entropy", q65["reasons"])

    def test_l_high_entropy_nested_path_dir_and_renamed_from_quarantine(self) -> None:
        r = self.repo
        secret_tok = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        # 1) Nested filename containing an opaque high-entropy component must quarantine
        nested_file = f"docs/nested/{secret_tok}.txt"
        (r / nested_file).parent.mkdir(parents=True, exist_ok=True)
        (r / nested_file).write_text("ok\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "nested-secret-filename")
        h1 = _git(r, "rev-parse", "HEAD")
        self.set_gh(self.head, h1)
        self.receipts(_receipt(66))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # 2) Directory component containing an opaque high-entropy token must quarantine
        secret_dir = f"docs/Dir{secret_tok}/note.md"
        (r / secret_dir).parent.mkdir(parents=True, exist_ok=True)
        (r / secret_dir).write_text("ok\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "nested-secret-dirname")
        h2 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h1, h2)
        self.receipts(_receipt(67))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # 3) Rename source (renamed_from) containing a high-entropy component must quarantine
        rename_src = f"archive/Old{secret_tok}.md"
        (r / rename_src).parent.mkdir(parents=True, exist_ok=True)
        (r / rename_src).write_text("".join(f"line{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "seed-rename-src")
        h3 = _git(r, "rev-parse", "HEAD")
        (r / "docs/moved-clean").mkdir(parents=True, exist_ok=True)
        _git(r, "mv", rename_src, "docs/moved-clean/target.md")
        _git(r, "commit", "-qm", "rename-secret-src")
        h4 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h3, h4)
        self.receipts(_receipt(68))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        self.assertEqual(self.lines("trajectories.jsonl"), [])
        quar_by_pr = {x["pr"]: x for x in self.lines("trajectories.quarantine.jsonl")}
        for pr in (66, 67, 68):
            self.assertIn("entropy", quar_by_pr[pr]["reasons"])

    def test_m_slash_secret_in_verified_path_and_renamed_from_quarantines(self) -> None:
        r = self.repo
        # Halves are each < 32 chars so splitting on '/' would bypass _BLOB unless _path_like blocks it.
        b64_slash = "AbCdEfGhIjKlMnOpQr01/2345+6789AbCdEfGhIj="
        (r / b64_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / b64_slash).write_text("ok\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "b64-slash-path")
        h1 = _git(r, "rev-parse", "HEAD")
        self.set_gh(self.head, h1)
        self.receipts(_receipt(69))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Direct scan checks for base64 (+/=), lowercase (+/=), and mixed-case without +/=
        self.assertEqual(
            col.scan(
                json.dumps({"files": [{"path": "AbCdEfGhIjKlMnOpQrStUvWxYz012345/789+AbCdEf"}]}),
                allowed_paths={"AbCdEfGhIjKlMnOpQrStUvWxYz012345/789+AbCdEf"},
            ),
            ["entropy"],
        )
        low_b64 = "abcdefghij0123456789/klmnop+qrstuv=wxyz01"
        self.assertEqual(col.scan(json.dumps({"files": [{"path": low_b64}]}), allowed_paths={low_b64}), ["entropy"])
        self.assertEqual(
            col.scan(
                json.dumps({"files": [{"path": "AbCdEfGhIjKlMnOpQrStUvWxYz012345/6789AbCdEfGhIj"}]}),
                allowed_paths={"AbCdEfGhIjKlMnOpQrStUvWxYz012345/6789AbCdEfGhIj"},
            ),
            ["entropy"],
        )
        mixed_hyphen = "docs/Secret_Token-Here_Now/file_AbCdEfGhIjKlMnOp.md"
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": mixed_hyphen}]}), allowed_paths={mixed_hyphen}),
            ["entropy"],
        )

        # Mixed-case slash secret WITHOUT +/= in verified files[*].path and files[*].renamed_from
        mixed_slash = "AbCdEfGhIjKlMnOpQr01/23456789AbCdEfGhIjKl"
        (r / mixed_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / mixed_slash).write_text("".join(f"line{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "mixed-slash-path")
        h2 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h1, h2)
        self.receipts(_receipt(70))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        (r / "docs/moved-clean").mkdir(parents=True, exist_ok=True)
        _git(r, "mv", mixed_slash, "docs/moved-clean/renamed-target.md")
        _git(r, "commit", "-qm", "mixed-slash-rename")
        h3 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h2, h3)
        self.receipts(_receipt(71))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # TitleCase slash secret (< 8 chars per part, each '/'-half < 32 chars, total _BLOB entropy > 4.0)
        title_slash = "Qwxz01-Vbnm23/Kjhg45-Plok67_Mnbv89"
        self.assertGreater(receipt_mod._entropy(title_slash), 4.0)
        self.assertTrue(all(len(seg) < 32 for seg in title_slash.split("/")))
        self.assertEqual(col.scan(json.dumps({"files": [{"path": title_slash}]}), allowed_paths={title_slash}), ["entropy"])
        (r / title_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / title_slash).write_text("".join(f"title-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "title-slash-path")
        h4 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h3, h4)
        self.receipts(_receipt(72))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", title_slash, "docs/moved-clean/renamed-title-target.md")
        _git(r, "commit", "-qm", "title-slash-rename")
        h5 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 73, h4, h5)[0].get("renamed_from"), title_slash)
        self.set_gh(h4, h5)
        self.receipts(_receipt(73))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Long (>= 8) single-case mixed-alphanumeric slash secret (each '/'-half < 32 chars, total _BLOB entropy > 4.0)
        alnum_slash = "a1b2c3d4e5f6g7h8/i9j0k1l2m3n4o5p6q7r8"
        self.assertGreater(receipt_mod._entropy(alnum_slash), 4.0)
        self.assertTrue(all(len(seg) < 32 for seg in alnum_slash.split("/")))
        self.assertEqual(col.scan(json.dumps({"files": [{"path": alnum_slash}]}), allowed_paths={alnum_slash}), ["entropy"])
        (r / alnum_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / alnum_slash).write_text("".join(f"alnum-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "alnum-slash-path")
        h6 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h5, h6)
        self.receipts(_receipt(74))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", alnum_slash, "docs/moved-clean/renamed-alnum-target.md")
        _git(r, "commit", "-qm", "alnum-slash-rename")
        h7 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 75, h6, h7)[0].get("renamed_from"), alnum_slash)
        self.set_gh(h6, h7)
        self.receipts(_receipt(75))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Multi-chunk hyphenated mixed-alphanumeric token and uninterrupted high-entropy single component
        chunked_alnum = "docs/kx9q2-mz7p4-vb8w1-nf6t3-rc5y0-hd4j8.txt"
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": chunked_alnum}]}), allowed_paths={chunked_alnum}),
            ["entropy"],
        )
        long_single_comp = "docs/qwertyuiopasdfghjklzxcvbnm123456.txt"
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": long_single_comp}]}), allowed_paths={long_single_comp}),
            ["entropy"],
        )

        # P1: case change across '-' inside a slash segment in files[*].path and files[*].renamed_from
        case_switch_slash = "qxjfzpwnrt-VMKDHYCLBG/tsgkvbnmqu-SXWRJHFPDZ"
        self.assertGreater(receipt_mod._entropy(case_switch_slash), 4.0)
        self.assertTrue(all(len(seg) < 32 for seg in case_switch_slash.split("/")))
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": case_switch_slash}]}), allowed_paths={case_switch_slash}),
            ["entropy"],
        )
        (r / case_switch_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / case_switch_slash).write_text("".join(f"case-switch-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "case-switch-slash-path")
        h8 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h7, h8)
        self.receipts(_receipt(76))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", case_switch_slash, "docs/moved-clean/renamed-case-switch-target.md")
        _git(r, "commit", "-qm", "case-switch-slash-rename")
        h9 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 77, h8, h9)[0].get("renamed_from"), case_switch_slash)
        self.set_gh(h8, h9)
        self.receipts(_receipt(77))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Slash-less high-entropy hyphenated hex token after '.' in verified files[*].path and files[*].renamed_from
        dot_uuid_tok = "01234567-89ab-cdef-0123-456789abcdef"
        dot_uuid = f"docs/prefix.{dot_uuid_tok}"
        dot_uuid_txt = f"{dot_uuid}.txt"
        self.assertGreater(receipt_mod._entropy(dot_uuid_tok), 4.0)
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": dot_uuid}]}), allowed_paths={dot_uuid}),
            ["entropy"],
        )
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": dot_uuid_txt}]}), allowed_paths={dot_uuid_txt}),
            ["entropy"],
        )
        (r / dot_uuid_txt).parent.mkdir(parents=True, exist_ok=True)
        (r / dot_uuid_txt).write_text("".join(f"dot-uuid-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "dot-uuid-path")
        h10 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h9, h10)
        self.receipts(_receipt(78))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", dot_uuid_txt, "docs/moved-clean/renamed-dot-uuid-target.md")
        _git(r, "commit", "-qm", "dot-uuid-rename")
        h11 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 79, h10, h11)[0].get("renamed_from"), dot_uuid_txt)
        self.set_gh(h10, h11)
        self.receipts(_receipt(79))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Nested basename/dir high-entropy hyphenated hex token in verified files[*].path and files[*].renamed_from
        nested_uuid = f"docs/{dot_uuid_tok}.txt"
        nested_prefixed_uuid = f"docs/key-{dot_uuid_tok}.txt"
        nested_dir_uuid = f"docs/{dot_uuid_tok}/note.md"
        for p in (nested_uuid, nested_prefixed_uuid, nested_dir_uuid):
            self.assertEqual(
                col.scan(json.dumps({"files": [{"path": p}]}), allowed_paths={p}),
                ["entropy"],
                p,
            )
        (r / nested_uuid).parent.mkdir(parents=True, exist_ok=True)
        (r / nested_uuid).write_text("".join(f"nested-uuid-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "nested-uuid-path")
        h12 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h11, h12)
        self.receipts(_receipt(80))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", nested_uuid, "docs/moved-clean/renamed-nested-uuid-target.md")
        _git(r, "commit", "-qm", "nested-uuid-rename")
        h13 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 81, h12, h13)[0].get("renamed_from"), nested_uuid)
        self.set_gh(h12, h13)
        self.receipts(_receipt(81))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Hex-character prefixes before a UUID token must not dilute _HYPHEN_HEX entropy below 4.0
        added_uuid = f"docs/added-{dot_uuid_tok}.txt"
        deadbeef_uuid = f"docs/deadbeef-{dot_uuid_tok}.txt"
        aaa_uuid = f"docs/aaaaa{dot_uuid_tok}.txt"
        for p in (added_uuid, deadbeef_uuid, aaa_uuid):
            self.assertEqual(
                col.scan(json.dumps({"files": [{"path": p}]}), allowed_paths={p}),
                ["entropy"],
                p,
            )
        (r / added_uuid).parent.mkdir(parents=True, exist_ok=True)
        (r / added_uuid).write_text("".join(f"added-uuid-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "added-uuid-path")
        h14 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h13, h14)
        self.receipts(_receipt(82))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", added_uuid, "docs/moved-clean/renamed-added-uuid-target.md")
        _git(r, "commit", "-qm", "added-uuid-rename")
        h15 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 83, h14, h15)[0].get("renamed_from"), added_uuid)
        self.set_gh(h14, h15)
        self.receipts(_receipt(83))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Cross-segment / whole-match opaque base64 credentials containing '/' (without '+'/'=')
        for b64_vec in (
            "ABCDEFGHIJKLMNOP/qrstuvwxyz012345",
            "ABCDEFGH/ijklmnop/QRSTUVWX/yz012345",
            "docs/harness-first/ABCDEFGHIJKLMNOP/qrstuvwxyzabcdef-1",
            "qxjfzpwnrt/vmkdhyclbg/tsgkvbnmqu/sxwrjhfpdz",
            "a1b2c3d/e4f5g6h/i7j8k9m/n0p1q2r/s3t4u5v",
            "0123456789abcdef/0123456789abcdef",
            "ABCDEFGH-X/ijklmnop-y/QRSTUVWX-Z/yz012345-a",
        ):
            self.assertEqual(
                col.scan(json.dumps({"files": [{"path": b64_vec}]}), allowed_paths={b64_vec}),
                ["entropy"],
                b64_vec,
            )

        b64_cross_seg = "ABCDEFGHIJKLMNOP/qrstuvwxyz012345"
        (r / b64_cross_seg).parent.mkdir(parents=True, exist_ok=True)
        (r / b64_cross_seg).write_text("".join(f"b64-cross-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "b64-cross-seg-path")
        h16 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h15, h16)
        self.receipts(_receipt(84))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", b64_cross_seg, "docs/moved-clean/renamed-b64-cross-seg.md")
        _git(r, "commit", "-qm", "b64-cross-seg-rename")
        h17 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 85, h16, h17)[0].get("renamed_from"), b64_cross_seg)
        self.set_gh(h16, h17)
        self.receipts(_receipt(85))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        lower_b64_slash = "qxjfzpwnrt/vmkdhyclbg/tsgkvbnmqu/sxwrjhfpdz"
        (r / lower_b64_slash).parent.mkdir(parents=True, exist_ok=True)
        (r / lower_b64_slash).write_text("ok\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "lower-b64-slash-path")
        h18 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h17, h18)
        self.receipts(_receipt(86))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        # Low-entropy parent directory dilution must not pull credential blobs below 4.0
        long_parent = "a" * 80
        diluted_uuid = f"{long_parent}/{dot_uuid_tok}.txt"
        self.assertLess(receipt_mod._entropy(diluted_uuid.rsplit(".", 1)[0]), 4.0)
        diluted_added_uuid = f"{long_parent}/added-{dot_uuid_tok}.txt"
        for p in (
            diluted_uuid,
            diluted_added_uuid,
            f"{long_parent}/{'a' * 32}AbCdEfGhIjKlMnOpQrStUvWxYz0123456789.txt",
            f"{long_parent}/ABCDEFGHIJKLMNOP/qrstuvwxyz012345",
            f"{long_parent}/qxjfzpwnrt/vmkdhyclbg/tsgkvbnmqu/sxwrjhfpdz",
            f"{long_parent}/docs/harness-first/ABCDEFGHIJKLMNOP/qrstuvwxyzabcdef-1",
        ):
            self.assertEqual(
                col.scan(json.dumps({"files": [{"path": p}]}), allowed_paths={p}),
                ["entropy"],
                p,
            )

        (r / diluted_added_uuid).parent.mkdir(parents=True, exist_ok=True)
        (r / diluted_added_uuid).write_text("".join(f"diluted-uuid-{i}\n" for i in range(20)))
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "diluted-added-uuid-path")
        h19 = _git(r, "rev-parse", "HEAD")
        self.set_gh(h18, h19)
        self.receipts(_receipt(87))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        _git(r, "mv", diluted_added_uuid, "docs/moved-clean/renamed-diluted-uuid.md")
        _git(r, "commit", "-qm", "diluted-added-uuid-rename")
        h20 = _git(r, "rev-parse", "HEAD")
        self.assertEqual(col._numstat(r, 88, h19, h20)[0].get("renamed_from"), diluted_added_uuid)
        self.set_gh(h19, h20)
        self.receipts(_receipt(88))
        c = self.collect()
        self.assertEqual((c["collected"], c["quarantined"]), (0, 1), c)

        self.assertEqual(self.lines("trajectories.jsonl"), [])
        quar_by_pr = {x["pr"]: x for x in self.lines("trajectories.quarantine.jsonl")}
        for pr in range(69, 89):
            self.assertIn("entropy", quar_by_pr[pr]["reasons"])


class ScanPathEntropy(unittest.TestCase):
    """PR 788 false positive: long lowercase repo paths tripped the entropy heuristic and quarantined a clean row."""

    def test_long_repo_paths_are_clean(self) -> None:
        for p in (
            "docs/harness-first/evidence/2026-11-15-deploy-validation",
            "agent/PROJECT-DEPLOY-VALIDATION-PRD",
            "docs/harness-first/evidence/DEPLOY-README.md",
            "scripts/security/compare-github-code-scanning-alerts.sh",
            "docs/harness-first/evidence/2026-03-04-harness-first-owner-approval.md",
            "docs/harness-first/evidence/2026-10-01-local-first-token-budget.md",
            "docs/architecture/GOOGLE-ADK-PARITY-MATRIX-2026-03.md",
            "scripts/testing/phase58b-routing-audit.py",
            ".agents/plans/aqos-refoundation-cycle0/evidence/cas/sha256/491dce6c806b8638f0d97aab379ed4421c78272beb58090e55d178c15def4649.json",
            "nix/modules/hardware/cpu/riscv64.nix",
            "dashboard/backend/api/routes/deployments.py",
        ):
            txt = json.dumps({"files": [{"path": p}]})
            self.assertEqual(col.scan(txt, allowed_paths={p}), [], p)
            self.assertEqual(col.scan(txt), ["entropy"], f"unverified path must still flag: {p}")
            self.assertEqual(col.scan(json.dumps({"path": p})), ["entropy"], f"bare path must still flag: {p}")

    def test_nil_uuid_is_clean(self) -> None:
        self.assertEqual(col.scan(json.dumps({"id": "00000000-0000-0000-0000-000000000000"})), [])

    def test_long_single_values_are_linear_time(self) -> None:
        plain_hex = json.dumps({"id": "a" * 16384})
        with_trailing_dash = json.dumps({"id": "a" * 16383 + "-"})
        delimited = json.dumps({"id": "a-" * 8192})
        with_uuid = json.dumps({"id": "a" * 8192 + "-01234567-89ab-cdef-0123-456789abcdef"})

        t0 = time.monotonic()
        self.assertEqual(col.scan(plain_hex), [])
        self.assertLess(time.monotonic() - t0, 0.05)
        self.assertEqual(col.scan(with_trailing_dash), [])
        self.assertEqual(col.scan(delimited), [])
        self.assertEqual(col.scan(with_uuid), ["entropy"])
        self.assertLess(time.monotonic() - t0, 0.5)

    def test_real_blobs_still_caught(self) -> None:
        self.assertEqual(col.scan("k=Zx9Qm3Lp7Tr2Vb8Nc5Kd1Hf6Gj4Sw0Ya+Ue/Ei=="), ["entropy"])
        self.assertEqual(col.scan("tok Zx9Qm3Lp7Tr2Vb8Nc5Kd1Hf6Gj4Sw0YaUeEi"), ["entropy"])

    def test_duplicate_json_key_fails_closed(self) -> None:
        p = "docs/harness-first/evidence/2026-11-15-deploy-validation.md"
        dup = (
            '{"files":[{"path":"' + p + '"}],'
            '"label":"AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",'
            '"label":"clean"}'
        )
        self.assertEqual(col.scan(dup, allowed_paths={p}), ["entropy"])

    def test_aq_land_calls_collector_nonfatally(self) -> None:
        land = (ROOT / "scripts/ai/aq-land").read_text()
        self.assertIn("self.collect_trajectory(n)", land)
        self.assertIn("collect-verified-trajectories.py", land)
        self.assertIn("WARN trajectory", land)

    def test_deeply_nested_clean_path_is_bounded_and_clean(self) -> None:
        deep_clean = "/".join(["dir"] * 500) + "/file.txt"
        deep_bad = "/".join(["dir"] * 500) + "/ABCDEFGHIJKLMNOP/qrstuvwxyz012345"
        t0 = time.monotonic()
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": deep_clean}]}), allowed_paths={deep_clean}),
            [],
        )
        self.assertEqual(
            col.scan(json.dumps({"files": [{"path": deep_bad}]}), allowed_paths={deep_bad}),
            ["entropy"],
        )
        self.assertLess(time.monotonic() - t0, 1.0)


if __name__ == "__main__":
    unittest.main()
