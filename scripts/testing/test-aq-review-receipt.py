#!/usr/bin/env python3
"""Tests for scripts/ai/aq-review-receipt (mint/verify/audit) with a temp registry."""
import json
import os
import pathlib
import subprocess
import sys
import hashlib
import tempfile
import time
import unittest

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
        rv = self.run_tool("revoke", "--pr", "7", "--head", head, "--reason", "hand-minted, no real review")
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
        again = self.run_tool("revoke", "--pr", "7", "--head", head, "--reason", "again")
        self.assertIn("already revoked", again.stdout)

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


if __name__ == "__main__":
    unittest.main()
