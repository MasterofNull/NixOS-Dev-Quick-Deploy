#!/usr/bin/env python3
"""Tests for scripts/ai/aq-review-receipt (mint/verify/audit) with a temp registry."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
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
        self.set_entry()
        self.head = self._repo()  # mint binds a real commit's tree, so every test needs a repo
        self.log.write_text(f"reviewed {self.head[:12]}\nReview-Disposition: PASS\n")

    def tearDown(self):
        self._t.cleanup()

    def set_entry(self, **kw):
        e = {"id": "r1", "agent": "codex", "role": "reviewer", "output_file": "out/rev.log", "status": "done"}
        e.update(kw)
        self.reg.write_text(json.dumps(e) + "\n")

    def run_tool(self, *a):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.d), "--registry", str(self.reg), *a],
                              capture_output=True, text=True)

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
        self.log.write_text(f"{self.head}\nno verdict\n")
        self.set_entry()
        self.assertNotEqual(self.mint().returncode, 0)

    def test_verify_rejects_verdict_edit(self):
        self.log.write_text(f"reviewed {self.head[:12]}\nReview-Disposition: REQUEST_CHANGES\n")
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
        self.log.write_text("")
        r = self.mint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("empty", r.stderr)
        self.assertFalse(self.rfile.exists())

    def test_verify_detects_tamper_and_missing_run(self):
        self.assertEqual(self.mint().returncode, 0)
        self.log.write_text(self.log.read_text() + "edited\n")
        r = self.run_tool("verify", str(self.rfile))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sha256", r.stderr)
        self.reg.write_text("")
        self.assertNotEqual(self.run_tool("audit").returncode, 0)

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
        self.log.write_text(f"reviewed {head[:12]}\nReview-Disposition: PASS\n")
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
