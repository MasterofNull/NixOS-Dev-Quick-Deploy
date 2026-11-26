#!/usr/bin/env python3
"""Tests for scripts/ai/aq-review-receipt (mint/verify/audit) with a temp registry."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import hashlib
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/ai/aq-review-receipt"


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self._t.name)
        (self.d / "out").mkdir()
        self.log = self.d / "out/rev.log"
        self.reg = self.d / "registry.jsonl"
        self.rev_dir = self.d / "revocations"
        self.entry_kw = {}
        os.environ["AQ_REVIEW_REVOCATIONS_DIR"] = str(self.rev_dir)  # never touch the live checkout's revocation dir
        self.addCleanup(os.environ.pop, "AQ_REVIEW_REVOCATIONS_DIR", None)
        os.environ["AQ_RECEIPT_HASH_ENFORCED_FROM"] = "2000-01-01"  # tests mint "now"; the legacy test sets an old created_at
        self.addCleanup(os.environ.pop, "AQ_RECEIPT_HASH_ENFORCED_FROM", None)
        self.head = self._repo()  # mint binds a real commit's tree, so every test needs a repo
        self.write_log(f"reviewed {self.head[:12]}\n## Findings\nnone in a/b.py\nReview-Disposition: PASS\n")

    def tearDown(self):
        self._t.cleanup()

    def set_entry(self, **kw):
        """Registry row as the delegate wrappers leave it: done plus the recorded output hash. Pass
        output_sha256=None (etc.) to drop a field and model a hand-written row."""
        self.entry_kw = kw
        e: dict = {"id": "r1", "agent": "codex", "role": "reviewer", "output_file": "out/rev.log", "status": "done"}
        if self.log.exists():
            data = self.log.read_bytes()
            e.update(output_sha256=hashlib.sha256(data).hexdigest(), output_bytes=len(data),
                     output_recorded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 1)))
        e.update(kw)
        self.reg.write_text(json.dumps({k: v for k, v in e.items() if v is not None}) + "\n")

    def write_log(self, text):
        self.log.write_text(text)
        self.set_entry(**getattr(self, "entry_kw", {}))

    def run_tool(self, *a):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.d), "--registry", str(self.reg), *a],
                              capture_output=True, text=True, env={**os.environ, "AQ_REVIEW_REVOCATIONS_DIR": str(self.rev_dir)})

    def mint(self, author="claude", head=None):
        return self.run_tool("mint", "--run-id", "r1", "--pr", "7", "--head", head or self.head, "--author-lane", author,
                             "--repo", "o/r", "--out", str(self.rfile))

    @property
    def rfile(self):
        return self.d / ".agent/reviews/receipts/pr7.json"

    def test_mint_is_off_branch_by_default(self):
        r = self.run_tool("mint", "--run-id", "r1", "--pr", "7", "--head", self.head, "--author-lane", "claude", "--repo", "o/r",
                          "--out", str(self.d / "plain.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads((self.d / "plain.json").read_text())
        self.assertEqual((rec["schema"], rec["tree"]), (2, self.g("rev-parse", "HEAD^{tree}")))

    def test_mint_and_verify(self):
        r = self.mint()
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(self.rfile.read_text())
        self.assertEqual((rec["reviewer_lane"], rec["verdict"], rec["output_file"]), ("codex", "PASS", "out/rev.log"))
        self.assertEqual(self.run_tool("verify", str(self.rfile)).returncode, 0)
        self.assertEqual(self.run_tool("audit").returncode, 0)

    def test_verify_local_receipt_binds_pr_and_head(self):
        minted = self.mint()
        self.assertEqual(minted.returncode, 0, minted.stderr)
        cases = (
            ("7", self.head, ""),
            ("8", self.head, "receipt pr does not match --pr"),
            ("7", "0" * 40, "receipt reviewed_head_sha does not match --head"),
            ("0", self.head, "positive"),
            ("-1", self.head, "positive"),
            ("7", "A" * 40, "lowercase hex"),
        )
        for pr, head, error in cases:
            with self.subTest(pr=pr, head=head):
                result = self.run_tool("verify", str(self.rfile), "--pr", pr, "--head", head)
                self.assertEqual(result.returncode, int(bool(error)), result.stderr)
                if error:
                    self.assertIn(error, result.stderr)

        receipt = json.loads(self.rfile.read_text())
        receipt["pr"] = True
        self.rfile.write_text(json.dumps(receipt))
        result = self.run_tool("verify", str(self.rfile), "--pr", "1")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("receipt pr does not match --pr 1", result.stderr)

        for pr in ("0", "-1"):
            with self.subTest(revoke_pr=pr):
                result = self.run_tool("revoke", "--pr", pr, "--head", self.head, "--reason", "bad")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("--pr must be positive", result.stderr)

    def test_mint_rejections(self):
        self.assertNotEqual(self.mint(author="Codex").returncode, 0)
        self.assertNotEqual(self.mint(head="b" * 40).returncode, 0)  # head not in output
        self.set_entry(status="running")
        self.assertNotEqual(self.mint().returncode, 0)
        self.set_entry(role="implementer")
        self.assertNotEqual(self.mint().returncode, 0)
        self.write_log(f"{self.head}\n## Findings\nx\nno verdict\n")
        self.assertNotEqual(self.mint().returncode, 0)

    def test_verify_rejects_verdict_edit(self):
        self.write_log(f"reviewed {self.head[:12]}\n## Findings\nbug in a/b.py\nReview-Disposition: REQUEST_CHANGES\n")
        self.assertEqual(self.mint().returncode, 0)  # minting records the real verdict
        rec = json.loads(self.rfile.read_text())
        self.assertEqual(rec["verdict"], "REQUEST_CHANGES")
        rec["verdict"] = "PASS"
        self.rfile.write_text(json.dumps(rec))
        r = self.run_tool("verify", str(self.rfile))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("verdict", r.stderr)
        self.assertNotEqual(self.run_tool("audit").returncode, 0)

    def test_empty_output_rejected(self):
        self.write_log("")
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("empty", r.stderr)
        self.assertFalse(self.rfile.exists())

    def test_verify_detects_tamper_and_missing_run(self):
        self.assertEqual(self.mint().returncode, 0)
        self.log.write_text(self.log.read_text() + "edited\n")  # not re-stamped: tamper after the wrapper recorded it
        r = self.run_tool("verify", str(self.rfile))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sha256", r.stderr)
        self.reg.write_text("")
        self.assertNotEqual(self.run_tool("audit").returncode, 0)


    # --- run-integrity rejections (incident 2026-11-19: hand-minted receipts) ---
    def test_hand_written_row_without_recorded_hash_rejected(self):
        self.set_entry(output_sha256=None, output_bytes=None, output_recorded_at=None)
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("wrapper-recorded output hash", r.stderr)

    def test_hash_of_a_different_log_rejected(self):
        self.set_entry(output_sha256="0" * 64)
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match the hash", r.stderr)

    def test_output_modified_after_recording_rejected(self):
        self.set_entry(output_recorded_at="2020-01-01T00:00:00Z")
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("modified after", r.stderr)

    def test_row_head_and_pr_must_match(self):
        self.set_entry(head="b" * 40)
        self.assertIn("registry row head", self.mint().stderr)
        self.set_entry(head=self.head, pr=99)
        self.assertIn("registry row pr", self.mint().stderr)
        self.set_entry(head=self.head, pr=7)
        self.assertEqual(self.mint().returncode, 0)

    def test_output_disposition_must_be_the_receipt_verdict(self):
        self.assertEqual(self.mint().returncode, 0)
        rec = json.loads(self.rfile.read_text())
        rec["verdict"] = "PASS_WITH_FOLLOWUPS"
        self.rfile.write_text(json.dumps(rec))
        self.assertIn("verdict", self.run_tool("verify", str(self.rfile)).stderr)

    def test_author_lane_equal_rejected(self):
        self.assertIn("equals author lane", self.mint(author="codex").stderr)

    def test_unsubstantive_review_rejected_and_each_rule_accepted(self):
        self.write_log(f"reviewed {self.head[:12]}\nCI green. LGTM.\nReview-Disposition: PASS\n")
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("substantive", r.stderr)
        self.write_log(f"reviewed {self.head[:12]}\nNo findings after reading scripts/ai/aq-land.\nReview-Disposition: PASS\n")
        self.assertEqual(self.mint().returncode, 0)  # no-findings statement that names reviewed files
        self.write_log(f"reviewed {self.head[:12]}\nNo findings.\nReview-Disposition: PASS\n")
        self.assertNotEqual(self.mint().returncode, 0)  # ...but not without file paths
        self.write_log(f"reviewed {self.head[:12]}\n" + ("The change reads the registry row and checks it. " * 40) + "\nReview-Disposition: PASS\n")
        self.assertEqual(self.mint().returncode, 0)  # long enough prose

    def test_gemini_style_hand_written_flow_is_rejected(self):
        """What the incident script did: hand-written log, hand-appended row, then mint."""
        self.reg.write_text(json.dumps({"id": "r1", "agent": "gemini", "role": "review", "status": "done",
                                        "output_file": "out/rev.log", "created_at": "2026-11-19T06:31:00Z", "head": self.head}) + "\n")
        self.log.write_text(f"Reviewed-head-sha: {self.head}\nReview-Disposition: PASS\n## Review Notes\nCI green\n")
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("wrapper-recorded output hash", r.stderr)
        self.assertIn("substantive", r.stderr)
        self.assertFalse(self.rfile.exists())

    def test_mint_records_registry_hash_fields(self):
        self.assertEqual(self.mint().returncode, 0)
        rec = json.loads(self.rfile.read_text())
        self.assertEqual(rec["registry_output_sha256"], rec["output_sha256"])
        self.assertEqual(rec["output_bytes"], len(self.log.read_bytes()))

    # --- revocation ---
    def test_revoke_then_verify_and_audit_reject(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(self._publish(f).returncode, 0)
        self.assertEqual(self.run_tool("verify", str(f)).returncode, 0)
        rv = self.run_tool("revoke", "--no-rerun", "--pr", "7", "--head", head, "--reason", "hand-minted, no real review")
        self.assertEqual(rv.returncode, 0, rv.stderr)
        shown = subprocess.run(["git", "-C", str(self.bare), "show", f"review-receipts:revocations/pr7-{head[:12]}.json"],
                               capture_output=True, text=True).stdout
        self.assertIn("hand-minted", json.loads(shown)["reason"])
        v = self.run_tool("verify", str(f))
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("REVOKED", v.stderr)
        # the published receipt is still on the branch, and a re-publish of a revoked receipt is refused
        self.assertIn("REVOKED", self._publish(f).stderr)
        a = self.run_tool("audit", "--branch")
        self.assertIn("REVOKED", a.stdout)
        self.assertEqual(a.returncode, 0, a.stdout)  # revoked receipts are dealt with, not a standing failure
        again = self.run_tool("revoke", "--no-rerun", "--pr", "7", "--head", head, "--reason", "again")
        self.assertIn("already revoked", again.stdout)

    def test_revoke_reruns_matching_open_pr_checks_after_publish(self):
        gh = self.d / "gh-stub"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, pathlib, subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "subprocess.run(['git', 'ls-remote', '--exit-code', 'origin', 'refs/heads/review-receipts'],\n"
            "               check=True, stdout=subprocess.DEVNULL)\n"
            "with pathlib.Path('gh-calls.jsonl').open('a') as log:\n"
            "    print(json.dumps(args), file=log)\n"
            "fixture = json.loads(pathlib.Path('gh-fixture.json').read_text())\n"
            "if args[:2] == ['pr', 'view']:\n"
            "    print(json.dumps(fixture['pr']))\n"
            "    sys.exit(fixture['failure'] == 'view')\n"
            "sys.exit(fixture['failure'] == 'rerun')\n"
        )
        gh.chmod(0o755)
        view = ["pr", "view", "7", "--json", "state,headRefOid,body,statusCheckRollup"]
        reruns = [["run", "rerun", "123"], ["run", "rerun", "456"]]
        checks = [
            {"name": "review-disposition", "detailsUrl": "/actions/runs/123/job/71", "databaseId": 71},
            {"name": "review-disposition", "detailsUrl": "/actions/runs/123/job/72", "databaseId": 72},
            {"name": "review-disposition", "detailsUrl": "/actions/runs/456/job/73"},
            {"name": "review-disposition", "databaseId": 74},
            {"name": "other", "detailsUrl": "/actions/runs/789/job/75"},
        ]
        cases = (
            ("matching", [view, *reruns], ""),
            ("merge-only-body", [view, *reruns], ""),
            ("merged", [view], "skipping check rerun"),
            ("changed", [view], "skipping check rerun"),
            ("no-rerun", [], ""),
            ("view", [view], "cannot inspect PR"),
            ("rerun", [view, *reruns], "cannot rerun workflow"),
            ("missing", [], "cannot inspect PR"),
        )
        calls = self.d / "gh-calls.jsonl"
        for mode, expected_calls, note in cases:
            with self.subTest(mode=mode):
                calls.write_text("")
                pr = {"state": "MERGED" if mode == "merged" else "OPEN",
                      "headRefOid": "0" * 40 if mode in ("changed", "merge-only-body") else self.head,
                      "body": f"Reviewed-head-sha: {self.head}\r\n" if mode == "merge-only-body" else "",
                      "statusCheckRollup": checks}
                (self.d / "gh-fixture.json").write_text(json.dumps({"pr": pr, "failure": mode}))
                executable = self.d / "missing-gh" if mode == "missing" else gh
                flags = ["--no-rerun"] if mode == "no-rerun" else []
                with patch.dict(os.environ, {"AQ_REVIEW_RECEIPT_GH": str(executable)}):
                    result = self.run_tool("revoke", "--pr", "7", "--head", self.head, "--reason", "bad", *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                published = self.g("show", f"review-receipts:revocations/pr7-{self.head[:12]}.json", cwd=self.bare)
                self.assertEqual(json.loads(published)["reviewed_head_sha"], self.head)
                self.assertEqual([json.loads(line) for line in calls.read_text().splitlines()], expected_calls)
                if note:
                    self.assertIn(note, result.stderr)

    def test_revoke_validates_input_and_verify_fails_closed_when_required(self):
        self.assertNotEqual(self.run_tool("revoke", "--pr", "7", "--head", "abc", "--reason", "x").returncode, 0)
        self.assertEqual(self.mint().returncode, 0)
        subprocess.run(["git", "-C", str(self.d), "remote", "set-url", "origin", str(self.d / "nope.git")], check=True)
        self.assertEqual(self.run_tool("verify", str(self.rfile)).returncode, 0)  # warns only
        r = self.run_tool("verify", "--require-revocation-check", str(self.rfile))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("failing closed", r.stderr)

    # --- detection ---
    def _burst_receipts(self, n, lane="gemini", gap=20):
        rd = self.d / ".agent/reviews/receipts"
        rd.mkdir(parents=True, exist_ok=True)
        base = time.time() - 3600
        for i in range(n):
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * gap))
            (rd / f"p{i}.json").write_text(json.dumps({"schema": 1, "pr": i, "run_id": f"x{i}", "reviewer_lane": lane,
                                                       "author_lane": "claude", "verdict": "PASS", "created_at": ts}))

    def test_audit_flags_receipt_burst_and_threshold_is_env_overridable(self):
        self._burst_receipts(5)
        out = self.run_tool("audit")
        self.assertIn("BURST: 5 receipts from reviewer lane 'gemini'", out.stdout)
        self.assertNotEqual(out.returncode, 0)
        env = {**os.environ, "AQ_RECEIPT_BURST_MAX": "9"}
        quiet = subprocess.run([sys.executable, str(TOOL), "--root", str(self.d), "--registry", str(self.reg), "audit"],
                               capture_output=True, text=True, env=env)
        self.assertNotIn("BURST", quiet.stdout)

    def test_audit_burst_ignores_slow_issuance(self):
        self._burst_receipts(5, gap=900)
        self.assertNotIn("BURST", self.run_tool("audit").stdout)

    def test_audit_warns_on_ci_claims_without_failing_for_it(self):
        self.write_log(f"reviewed {self.head[:12]}\n## Findings\nnone in a/b.py; CI is green\nReview-Disposition: PASS\n")
        self.assertEqual(self.mint().returncode, 0)
        a = self.run_tool("audit")
        self.assertIn("WARN: review text asserts CI state", a.stdout)
        self.assertEqual(a.returncode, 0, a.stdout)

    def test_audit_flags_receipt_with_no_recorded_hash(self):
        self.assertEqual(self.mint().returncode, 0)
        self.set_entry(output_sha256=None, output_bytes=None, output_recorded_at=None)
        a = self.run_tool("audit")
        self.assertNotEqual(a.returncode, 0)
        self.assertIn("wrapper-recorded output hash", a.stdout)

    def test_audit_flags_merge_burst(self):
        base = time.time() - 600
        rows = [{"number": 800 + i, "mergedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * 6)),
                 "body": "Reviewed-by: gemini\nAuthor-lane: claude"} for i in range(5)]
        mj = self.d / "merges.json"
        mj.write_text(json.dumps(rows))
        a = self.run_tool("audit", "--merges-json", str(mj))
        self.assertIn("MERGE-BURST: 5 merges backed by lane 'gemini'", a.stdout)
        self.assertNotEqual(a.returncode, 0)

    def test_legacy_receipt_without_hash_before_cutoff_still_verifies(self):
        self.assertEqual(self.mint().returncode, 0)
        rec = json.loads(self.rfile.read_text())
        rec["created_at"] = "2026-11-01T00:00:00Z"
        self.rfile.write_text(json.dumps(rec))
        os.environ["AQ_RECEIPT_HASH_ENFORCED_FROM"] = "2026-11-20"
        self.set_entry(output_sha256=None, output_bytes=None, output_recorded_at=None)
        self.assertEqual(self.run_tool("verify", str(self.rfile)).returncode, 0)

    def test_task_registry_stamps_hash_when_a_row_goes_done(self):
        sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
        from task_registry import TaskRegistry  # noqa: E402
        dd = self.d / ".agents/delegation"
        (dd / "outputs").mkdir(parents=True)
        (dd / "outputs/o.log").write_text("review text\n")
        reg = TaskRegistry(dd)
        reg.append("t1", "d", ".agents/delegation/outputs/o.log", "direct", "review")
        self.assertNotIn("output_sha256", reg.get("t1"))
        reg.update_status("t1", "done")
        row = reg.get("t1")
        self.assertEqual((row["output_sha256"], row["output_bytes"]), (hashlib.sha256(b"review text\n").hexdigest(), 12))
        self.assertTrue(row["output_recorded_at"])
        # the shell wrappers with their own status writer call `registry-update.py stamp`
        reg.append("t2", "d", ".agents/delegation/outputs/o.log", "direct", "review")
        subprocess.run([sys.executable, str(ROOT / "scripts/ai/lib/registry-update.py"), "stamp", str(dd / "registry.jsonl"), "t2"], check=True)
        self.assertEqual(reg.get("t2")["output_bytes"], 12)

    def test_task_registry_stamps_only_bounded_regular_outputs(self):
        sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
        import task_registry

        registry = task_registry.TaskRegistry(self.d / ".agents/delegation", self.d)
        self.log.write_bytes(b"ok")
        (self.d / "out/link").symlink_to(self.log)
        (self.d / "out/large").write_bytes(b"big")
        os.mkfifo(self.d / "out/fifo")
        read = os.read
        with (
            patch.object(task_registry, "_OUTPUT_STAMP_MAX_BYTES", 2),
            patch.object(task_registry.os, "read", side_effect=lambda fd, size: read(fd, min(size, 1))),
        ):
            stamp = registry._output_stamp({"output_file": "out/rev.log"})
            self.assertEqual(stamp["output_sha256"], hashlib.sha256(b"ok").hexdigest())
            self.assertEqual(stamp["output_bytes"], 2)
            self.assertTrue(stamp["output_recorded_at"])
            for name in ("link", "large", "fifo"):
                with self.subTest(output=name):
                    self.assertEqual(registry._output_stamp({"output_file": f"out/{name}"}), {})

    # --- off-branch receipts: mint --offbranch + publish (local bare origin) ---
    def _repo(self):
        if getattr(self, "_head", None):
            return self._head
        def g(*a, cwd=None):
            return subprocess.run(["git", "-C", str(cwd or self.work), *a], capture_output=True, text=True, check=True).stdout.strip()
        bt = tempfile.TemporaryDirectory()
        self.addCleanup(bt.cleanup)
        self.bare, self.work = pathlib.Path(bt.name) / "o.git", self.d
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.bare)], check=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        g("config", "commit.gpgsign", "false"); g("remote", "add", "origin", str(self.bare))
        (self.work / "a").write_text("a")
        g("add", "a"); g("commit", "-qm", "a"); g("push", "-q", "origin", "main"); g("fetch", "-q", "origin")
        g("checkout", "-qb", "pr")
        (self.work / "b").write_text("b")
        g("add", "b"); g("commit", "-qm", "b")
        self.g = g
        self._head = g("rev-parse", "HEAD")
        return self._head

    def _ob(self, head, **extra):
        self.write_log(f"reviewed {head[:12]}\n## Findings\nnone in a/b.py\nReview-Disposition: PASS\n")
        out = self.d / "ob.json"
        r = subprocess.run([sys.executable, str(TOOL), "--root", str(self.work), "--registry", str(self.reg), "mint", "--run-id", "r1",
                            "--pr", "7", "--head", head, "--author-lane", "claude", "--offbranch", "--repo", "o/r", "--out", str(out)],
                           capture_output=True, text=True)
        return r, out

    def _publish(self, f):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.work), "--registry", str(self.reg), "publish", str(f)],
                              capture_output=True, text=True)

    def _standalone_clone(self):
        clone = self.bare.parent / "clone"
        self.g("clone", "-q", "--branch", "pr", str(self.work), str(clone))
        self.g("remote", "set-url", "origin", str(self.bare), cwd=clone)
        self.assertEqual(self.g("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=clone), str(clone / ".git"))
        return clone

    def _shared_review(self, delegation_dir, output_file):
        review = self.log.read_text()
        self.reg = delegation_dir / "registry.jsonl"
        self.log = delegation_dir / "outputs/rev.log"
        self.log.parent.mkdir(parents=True)
        self.write_log(review + "CI passed.\n")
        self.set_entry(output_file=output_file)

    def _checkout_tool(self, checkout, *args, use_env=False):
        env = dict(os.environ)
        command = [sys.executable, str(TOOL), "--root", str(checkout)]
        if use_env:
            env["AQ_DELEGATION_DIR"] = str(self.reg.parent)
        else:
            command.extend(("--registry", str(self.reg)))
        return subprocess.run([*command, *args], cwd=checkout, env=env, capture_output=True, text=True)

    def _checkout_mint(self, checkout, *, use_env=False):
        receipt = self.bare.parent / "receipt.json"
        result = self._checkout_tool(checkout, "mint", "--run-id", "r1", "--pr", "7", "--head", self.head,
                                     "--author-lane", "claude", "--repo", "o/r", "--out", str(receipt), use_env=use_env)
        return result, receipt

    def _assert_shared_receipt_lifecycle(self, checkout, *, use_env=False):
        output_file = ".agents/delegation/outputs/rev.log"
        self._shared_review(self.work / ".agents/delegation", output_file)
        self.assertFalse((checkout / output_file).exists())
        minted, receipt = self._checkout_mint(checkout, use_env=use_env)
        self.assertEqual(minted.returncode, 0, minted.stderr)
        self.assertEqual(json.loads(receipt.read_text())["output_file"], output_file)

        published_args = ("verify", "--pr", "7", "--head", self.head, "--require-revocation-check")
        for root, args in (
            (checkout, ("publish", str(receipt))),
            (checkout, ("verify", str(receipt))),
            (checkout, published_args),
            (checkout, ("audit", "--branch")),
            (self.work, ("verify", str(receipt))),
            (self.work, published_args),
        ):
            with self.subTest(checkout=root, command=args):
                result = self._checkout_tool(root, *args, use_env=use_env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if args[0] == "audit":
                    self.assertIn("OK  WARN: review text asserts CI state", result.stdout)

    def test_shared_registry_from_linked_worktree(self):
        checkout = self.bare.parent / "linked"
        self.g("worktree", "add", "--detach", str(checkout), self.head)
        self._assert_shared_receipt_lifecycle(checkout)

    def test_shared_registry_from_standalone_clone_with_flag(self):
        self._assert_shared_receipt_lifecycle(self._standalone_clone())

    def test_shared_registry_from_standalone_clone_with_env(self):
        self._assert_shared_receipt_lifecycle(self._standalone_clone(), use_env=True)

    def test_custom_registry_from_standalone_clone(self):
        clone = self._standalone_clone()
        output_file = "outputs/rev.log"
        self._shared_review(self.bare.parent / "shared", output_file)
        minted, receipt = self._checkout_mint(clone)
        self.assertEqual(minted.returncode, 0, minted.stderr)
        self.assertEqual(json.loads(receipt.read_text())["output_file"], output_file)
        verified = self._checkout_tool(clone, "verify", str(receipt))
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_standalone_clone_rejects_registry_path_escapes(self):
        clone = self._standalone_clone()
        delegation_dir = self.work / ".agents/delegation"
        self._shared_review(delegation_dir, ".agents/delegation/outputs/rev.log")
        external = self.bare.parent / "external.log"
        secret = self.work / "secret.txt"
        for path in (external, secret, delegation_dir.parent / "outside.log"):
            path.write_bytes(self.log.read_bytes())

        symlink_paths = []
        for name, target in (
            ("evil.log", external),
            ("evil-local.log", secret),
            ("evil-broken.log", self.bare.parent / "missing.log"),
        ):
            link = delegation_dir / "outputs" / name
            link.symlink_to(target)
            symlink_paths.append(str(link.relative_to(self.work)))

        for output_file in ("../outside.log", "secret.txt", ".agents/delegation/../../secret.txt",
                            *symlink_paths, str(external)):
            with self.subTest(output_file=output_file):
                self.set_entry(output_file=output_file)
                result, receipt = self._checkout_mint(clone)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("outside the repo", result.stderr)
                self.assertFalse(receipt.exists())

    def test_offbranch_mint_publish_idempotent_and_branch_untouched(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(f.read_text())
        self.assertEqual((rec["schema"], rec["repo"], rec["tree"]), (2, "o/r", self.g("rev-parse", "HEAD^{tree}")))
        status0 = self.g("status", "--porcelain")
        p1 = self._publish(f)
        self.assertEqual(p1.returncode, 0, p1.stderr)
        tip = subprocess.run(["git", "-C", str(self.bare), "rev-parse", "refs/heads/review-receipts"], capture_output=True, text=True).stdout
        # re-mint (new created_at) and re-publish: no new commit
        rec["created_at"] = "2030-01-01T00:00:00Z"
        f.write_text(json.dumps(rec))
        p2 = self._publish(f)
        self.assertEqual(p2.returncode, 0, p2.stderr)
        self.assertIn("already published", p2.stdout)
        self.assertEqual(tip, subprocess.run(["git", "-C", str(self.bare), "rev-parse", "refs/heads/review-receipts"], capture_output=True, text=True).stdout)
        self.assertEqual(self.g("rev-parse", "HEAD"), head)
        self.assertEqual(self.g("rev-parse", "--abbrev-ref", "HEAD"), "pr")
        self.assertEqual(self.g("status", "--porcelain"), status0)
        shown = subprocess.run(["git", "-C", str(self.bare), "show", f"review-receipts:receipts/pr7-{head[:12]}.json"], capture_output=True, text=True).stdout
        self.assertEqual(json.loads(shown)["run_id"], "r1")

    def test_publish_retries_on_non_fast_forward(self):
        head = self._repo()
        r, f = self._ob(head)
        seed = self.d / "seed.json"
        seed.write_text(json.dumps({**json.loads(f.read_text()), "pr": 8}))
        self.assertEqual(self._publish(seed).returncode, 0)  # branch exists, so a lost race is a true non-fast-forward
        # a concurrent publisher lands between our fetch and the ref update: the hook advances the branch once
        subprocess.run(["git", "-C", str(self.bare), "config", "receive.denyNonFastForwards", "true"], check=True)  # as GitHub
        hook = self.bare / "hooks/pre-receive"
        marker = self.d / "raced"
        hook.write_text(
            "#!/bin/sh\nunset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
            f"if [ ! -e {marker} ]; then : > {marker}\n"
            "  b=$(echo other | git hash-object -w --stdin)\n"
            "  old=$(git rev-parse refs/heads/review-receipts)\n"
            "  t=$( (git ls-tree $old; printf '100644 blob %s\\tother.txt\\n' $b) | git mktree)\n"
            "  c=$(GIT_AUTHOR_NAME=x GIT_AUTHOR_EMAIL=x@x GIT_COMMITTER_NAME=x GIT_COMMITTER_EMAIL=x@x git commit-tree $t -p $old -m other)\n"
            "  git update-ref refs/heads/review-receipts $c\n"
            "fi\nexit 0\n")
        hook.chmod(0o755)
        p = self._publish(f)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(marker.exists())
        files = subprocess.run(["git", "-C", str(self.bare), "ls-tree", "-r", "--name-only", "review-receipts"], capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(files), sorted(["other.txt", f"receipts/pr8-{head[:12]}.json", f"receipts/pr7-{head[:12]}.json"]))  # rebuilt on the new tip, nothing lost

    def test_publish_retry_rechecks_revocations_at_new_parent(self):
        head = self._repo()
        r, f = self._ob(head)
        seed = self.d / "seed.json"
        seed.write_text(json.dumps({**json.loads(f.read_text()), "pr": 8}))
        self.assertEqual(self._publish(seed).returncode, 0)
        subprocess.run(["git", "-C", str(self.bare), "config", "receive.denyNonFastForwards", "true"], check=True)
        hook = self.bare / "hooks/pre-receive"
        marker = self.d / "revocation-raced"
        key = f"pr7-{head[:12]}"
        hook.write_text(
            "#!/bin/sh\nunset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
            f"if [ ! -e {marker} ]; then : > {marker}\n"
            f"  b=$(printf '%s\\n' '{{\"reason\": \"raced revocation\"}}' | git hash-object -w --stdin)\n"
            "  old=$(git rev-parse refs/heads/review-receipts)\n"
            "  i=$(mktemp)\nGIT_INDEX_FILE=$i git read-tree $old\n"
            f"  GIT_INDEX_FILE=$i git update-index --add --cacheinfo 100644,$b,revocations/{key}.json\n"
            "  t=$(GIT_INDEX_FILE=$i git write-tree)\n"
            "  c=$(GIT_AUTHOR_NAME=x GIT_AUTHOR_EMAIL=x@x GIT_COMMITTER_NAME=x GIT_COMMITTER_EMAIL=x@x git commit-tree $t -p $old -m revoke)\n"
            "  git update-ref refs/heads/review-receipts $c\nfi\nexit 0\n")
        hook.chmod(0o755)
        p = self._publish(f)
        self.assertNotEqual(p.returncode, 0)
        self.assertTrue(marker.exists())
        self.assertIn("REVOKED", p.stderr)
        files = subprocess.run(["git", "-C", str(self.bare), "ls-tree", "-r", "--name-only", "review-receipts"], capture_output=True, text=True).stdout.split()
        self.assertNotIn(f"receipts/pr7-{head[:12]}.json", files)

    def test_publish_rejects_invalid_and_never_overwrites_pass(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(self._publish(f).returncode, 0)
        rec = json.loads(f.read_text())
        rec["run_id"] = "r1"
        rec["output_sha256"] = "0" * 64  # mismatched output digest
        f.write_text(json.dumps(rec))
        bad = self._publish(f)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("sha256", bad.stderr)
        self.set_entry(agent="claude")  # invented/self run
        r2, f2 = self._ob(head)
        self.assertNotEqual(r2.returncode, 0)
        legacy = self.d / "legacy.json"
        legacy.write_text(json.dumps({**json.loads(f.read_text()), "schema": 1}))
        self.assertNotEqual(self._publish(legacy).returncode, 0)  # schema 1 cannot be published

    def _legacy_publish(self, head):
        """Put a PASS receipt lacking the integrity fields on the branch, as pre-integrity mints did."""
        r, f = self._ob(head)
        rec = json.loads(f.read_text())
        for k in ("registry_output_sha256", "output_bytes"):
            rec.pop(k)
        bare = self.bare
        env = {**os.environ, "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x"}
        blob = subprocess.run(["git", "-C", str(bare), "hash-object", "-w", "--stdin"], input=json.dumps(rec), capture_output=True, text=True, check=True).stdout.strip()
        sub = subprocess.run(["git", "-C", str(bare), "mktree"], input=f"100644 blob {blob}\tpr7-{head[:12]}.json\n", capture_output=True, text=True, check=True).stdout.strip()
        top = subprocess.run(["git", "-C", str(bare), "mktree"], input=f"040000 tree {sub}\treceipts\n", capture_output=True, text=True, check=True).stdout.strip()
        c = subprocess.run(["git", "-C", str(bare), "commit-tree", top, "-m", "legacy"], capture_output=True, text=True, check=True, env=env).stdout.strip()
        subprocess.run(["git", "-C", str(bare), "update-ref", "refs/heads/review-receipts", c], check=True)

    def test_fresh_receipt_supersedes_legacy_pass_without_integrity_fields(self):
        head = self._repo()
        self._legacy_publish(head)
        r, f = self._ob(head)
        p = self._publish(f)
        self.assertEqual(p.returncode, 0, p.stderr)
        shown = subprocess.run(["git", "-C", str(self.bare), "show", f"review-receipts:receipts/pr7-{head[:12]}.json"], capture_output=True, text=True).stdout
        self.assertIn("registry_output_sha256", json.loads(shown))
        # a receipt that carries the integrity fields is still append-only against a different verdict/run
        rec = json.loads(f.read_text())
        rec["run_id"] = "r1"
        other = self.d / "other.json"
        other.write_text(json.dumps({**rec, "author_lane": "gemini"}))
        self.assertNotEqual(self._publish(other).returncode, 0)

    def test_publish_and_verify_refuse_missing_or_mismatched_integrity_fields(self):
        head = self._repo()
        r, f = self._ob(head)
        rec = json.loads(f.read_text())
        for label, mut in (("missing sha", lambda x: x.pop("registry_output_sha256")),
                           ("missing bytes", lambda x: x.pop("output_bytes")),
                           ("bad sha", lambda x: x.update(registry_output_sha256="0" * 64)),
                           ("bad bytes", lambda x: x.update(output_bytes=rec["output_bytes"] + 1))):
            bad = json.loads(json.dumps(rec))
            mut(bad)
            bf = self.d / "bad.json"
            bf.write_text(json.dumps(bad))
            p = self._publish(bf)
            self.assertNotEqual(p.returncode, 0, label)
            self.assertTrue("registry_output_sha256" in p.stderr or "output_bytes" in p.stderr, (label, p.stderr))
            self.assertNotEqual(self.run_tool("verify", str(bf)).returncode, 0, label)
        self.assertEqual(self._publish(f).returncode, 0)

    def test_verify_published_receipt_without_local_file_and_fails_closed(self):
        head = self._repo()
        r, f = self._ob(head)
        absent = self.run_tool("verify", "--require-revocation-check", "--pr", "7", "--head", head)
        self.assertNotEqual(absent.returncode, 0)
        self.assertIn("no readable published receipt", absent.stderr)
        self.assertEqual(self._publish(f).returncode, 0)
        ok = self.run_tool("verify", "--require-revocation-check", "--pr", "7", "--head", head)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(self.run_tool("revoke", "--no-rerun", "--pr", "7", "--head", head, "--reason", "bad").returncode, 0)
        shutil.rmtree(self.rev_dir, ignore_errors=True)  # only the published revocation remains
        v = self.run_tool("verify", "--require-revocation-check", "--pr", "7", "--head", head)
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("REVOKED", v.stderr)

    def test_branch_reads_ignore_concurrent_fetch_head(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(self._publish(f).returncode, 0)
        self.assertEqual(self.run_tool("revoke", "--no-rerun", "--pr", "7", "--head", head, "--reason", "bad").returncode, 0)
        shutil.rmtree(self.rev_dir, ignore_errors=True)
        # a concurrent fetch of a ref with no revocations dir lands in FETCH_HEAD during our fetch window
        hook = self.work / "fetch-shim"
        real = shutil.which("git")
        hook.write_text(f"#!/bin/sh\n{real} \"$@\"; rc=$?\ncase \"$*\" in *fetch*aq-receipt-tmp*) {real} -C {self.work} fetch -q origin main >/dev/null 2>&1;; esac\nexit $rc\n")
        hook.chmod(0o755)
        env = {**os.environ, "PATH": f"{self.work}/shimbin:{os.environ['PATH']}"}
        (self.work / "shimbin").mkdir()
        (self.work / "shimbin/git").write_text(hook.read_text())
        (self.work / "shimbin/git").chmod(0o755)
        v = subprocess.run([sys.executable, str(TOOL), "--root", str(self.work), "--registry", str(self.reg), "verify",
                            "--require-revocation-check", "--pr", "7", "--head", head], capture_output=True, text=True, env=env)
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("REVOKED", v.stderr)

    def test_published_verify_fails_closed_on_revocation_read_error(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(self._publish(f).returncode, 0)
        self.assertEqual(self.run_tool("revoke", "--no-rerun", "--pr", "9", "--head", "a" * 40, "--reason", "unrelated").returncode, 0)
        real = shutil.which("git")
        shim = self.work / "git-read-failure"
        shim.write_text(f"#!/bin/sh\ncase \"$*\" in *show*revocations/*) exit 1;; esac\nexec {real} \"$@\"\n")
        shim.chmod(0o755)
        (self.work / "readfail-bin").mkdir()
        (self.work / "readfail-bin/git").write_text(shim.read_text())
        (self.work / "readfail-bin/git").chmod(0o755)
        env = {**os.environ, "PATH": f"{self.work}/readfail-bin:{os.environ['PATH']}"}
        v = subprocess.run([sys.executable, str(TOOL), "--root", str(self.work), "--registry", str(self.reg), "verify",
                            "--pr", "7", "--head", head], capture_output=True, text=True, env=env)
        self.assertNotEqual(v.returncode, 0)
        self.assertIn("cannot read revocations", v.stderr)

    def test_push_timeout_is_clean_and_leaves_branch_untouched(self):
        head = self._repo()
        r, f = self._ob(head)
        hook = self.bare / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nsleep 6\nexit 0\n")
        hook.chmod(0o755)
        status0, head0 = self.g("status", "--porcelain"), self.g("rev-parse", "HEAD")
        p = subprocess.run([sys.executable, str(TOOL), "--root", str(self.work), "--registry", str(self.reg), "publish", str(f)],
                           capture_output=True, text=True, env={**os.environ, "AQ_REVIEW_RECEIPT_PUSH_TIMEOUT": "1"})
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        lines = [l for l in p.stderr.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("publish FAILED: git timed out after 1s"), lines)
        self.assertIn("not retrying", lines[0])
        self.assertEqual((self.g("status", "--porcelain"), self.g("rev-parse", "HEAD"), self.g("rev-parse", "--abbrev-ref", "HEAD")),
                         (status0, head0, "pr"))

    def test_published_commit_identity_has_dotted_domain(self):
        head = self._repo()
        r, f = self._ob(head)
        self.assertEqual(self._publish(f).returncode, 0)
        who = subprocess.run(["git", "-C", str(self.bare), "log", "-1", "--format=%ae %ce", "review-receipts"], capture_output=True, text=True).stdout.split()
        self.assertEqual(who, ["aq-review-receipt@noreply.invalid"] * 2)

    def test_tier0d_gate_check_review_receipt_integrity_warns_never_fails(self):
        """check-review-receipt-integrity.sh runs in a sandbox repo: burst -> WARN, rc 0; clean -> OK."""
        sb = self.d / "sb"
        (sb / "scripts/governance/tier0.d").mkdir(parents=True)
        shutil.copytree(ROOT / "scripts/ai/lib", sb / "scripts/ai/lib")
        shutil.copy(TOOL, sb / "scripts/ai/aq-review-receipt")
        gate = sb / "scripts/governance/tier0.d/check-review-receipt-integrity.sh"
        shutil.copy(ROOT / "scripts/governance/tier0.d/check-review-receipt-integrity.sh", gate)
        subprocess.run(["git", "-C", str(sb), "init", "-q"], check=True)
        subprocess.run(["git", "init", "-q", "--bare", str(self.d / "sb.git")], check=True)  # no origin -> audit WARNs
        subprocess.run(["git", "-C", str(sb), "remote", "add", "origin", str(self.d / "sb.git")], check=True)
        env = {**os.environ, "AQ_RECEIPT_AUDIT_SINCE": "2000-01-01", "AQ_REVIEW_REVOCATIONS_DIR": str(self.rev_dir),
               "AQ_DELEGATION_DIR": str(self.d / "deleg")}
        clean = subprocess.run(["bash", str(gate)], cwd=sb, capture_output=True, text=True, env=env)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertIn("OK", clean.stdout)
        rd = sb / ".agent/reviews/receipts"
        rd.mkdir(parents=True)
        base = time.time() - 3600
        for i in range(5):
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * 20))
            (rd / f"p{i}.json").write_text(json.dumps({"schema": 1, "pr": i, "run_id": f"x{i}", "reviewer_lane": "gemini",
                                                       "author_lane": "claude", "verdict": "PASS", "created_at": ts}))
        bad = subprocess.run(["bash", str(gate)], cwd=sb, capture_output=True, text=True, env=env)
        self.assertEqual(bad.returncode, 0, bad.stdout + bad.stderr)
        self.assertIn("WARN", bad.stdout)


if __name__ == "__main__":
    unittest.main()
