#!/usr/bin/env python3
"""Tests for scripts/governance/check-review-disposition.py (review-disposition required PR check)."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/governance/check-review-disposition.py"
spec = importlib.util.spec_from_file_location("crd", SCRIPT)
crd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crd)

HEAD = "a" * 40
BODY = (
    "Author-lane: claude\nReview-Disposition: PASS\n"
    f"Reviewed-subject-sha256: {'b' * 64}\nReviewed-head-sha: {HEAD}\nReviewed-by: codex\n"
    "Review-Receipt: .agent/reviews/receipts/pr1-aaaaaaaaaaaa.json\n"
)
RPATH = ".agent/reviews/receipts/pr1-aaaaaaaaaaaa.json"


def receipt(**kw):
    r = {"schema": 1, "pr": 1, "reviewed_head_sha": HEAD, "run_id": "r1", "reviewer_lane": "codex",
         "author_lane": "claude", "verdict": "PASS", "output_file": "x.log", "output_sha256": "c" * 64,
         "created_at": "2026-10-27T00:00:00Z"}
    r.update(kw)
    return json.dumps(r)


def ev(body, head=HEAD):
    return {"pull_request": {"body": body, "head": {"sha": head}}}


class T(unittest.TestCase):
    def setUp(self):
        self._orig = crd._git
        self.rcpt = receipt()
        self.mode = "100644"
        crd._git = lambda *a: (self.rcpt if a[0] == "show" else f"{self.mode} blob {'e' * 40}\t{RPATH}" if a[0] == "ls-tree"
                               else self._orig(*a))

    def tearDown(self):
        crd._git = self._orig

    def test_missing_receipt_field_fails(self):
        errs = crd.check(ev(BODY.replace("Review-Receipt:", "X:")))
        self.assertIn("missing Review-Receipt", errs)

    def test_receipt_file_absent_fails(self):
        def boom(*a):
            raise subprocess.CalledProcessError(128, "git")
        crd._git = boom
        self.assertTrue(any("not found" in e for e in crd.check(ev(BODY))))

    def test_reviewer_mismatch_fails(self):
        self.rcpt = receipt(reviewer_lane="gemini")
        self.assertTrue(any("reviewer_lane" in e for e in crd.check(ev(BODY))))

    def test_request_changes_and_bad_hash_fail(self):
        self.rcpt = receipt(verdict="REQUEST_CHANGES", output_sha256="zz")
        errs = crd.check(ev(BODY))
        self.assertTrue(any("verdict" in e for e in errs) and any("output_sha256" in e for e in errs))

    def test_valid(self):
        self.assertEqual(crd.check(ev(BODY)), [])
        self.rcpt = receipt(verdict="PASS_WITH_FOLLOWUPS")
        self.assertEqual(crd.check(ev(BODY.replace("PASS", "PASS_WITH_FOLLOWUPS", 1).replace("\n", "\r\n"))), [])

    def test_missing_fields(self):
        errs = crd.check(ev("just a summary"))
        self.assertGreaterEqual(len(errs), 6)
        self.assertEqual(crd.check(ev(None))[0], "missing Review-Disposition")

    def test_same_lane(self):
        errs = crd.check(ev(BODY.replace("Reviewed-by: codex", "Reviewed-by: Claude")))
        self.assertTrue(any("must differ" in e for e in errs))

    def test_stale_head(self):
        errs = crd.check(ev(BODY, head="c" * 40))
        self.assertTrue(any("stale review" in e for e in errs))

    def test_bad_disposition_and_hex(self):
        errs = crd.check(ev(BODY.replace("PASS", "ACCEPTED", 1).replace("b" * 64, "xyz")))
        self.assertEqual(len(errs), 3)  # disposition, hex, receipt verdict mismatch

    def test_receipt_type_confusion_rejected(self):
        for kw in ({"schema": True}, {"run_id": {"a": 1}}, {"reviewer_lane": None}, {"author_lane": None},
                   {"pr": True}, {"verdict": ""}, {"reviewed_head_sha": "a" * 12}, {"run_id": " "}):
            self.rcpt = receipt(**kw)
            self.assertNotEqual(crd.check(ev(BODY)), [], kw)

    def test_receipt_symlink_rejected(self):
        self.mode = "120000"
        self.assertTrue(any("regular file" in e for e in crd.check(ev(BODY))))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "e.json"
            p.write_text(json.dumps(ev("x")))
            r = subprocess.run([sys.executable, str(SCRIPT), str(p)], capture_output=True)
            self.assertEqual(r.returncode, 1)


def _run(cwd, *a):
    return subprocess.run(["/run/current-system/sw/bin/git" if pathlib.Path("/run/current-system/sw/bin/git").exists() else "git", *a],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class MergeTolerant(unittest.TestCase):
    """Head-binding with a real temp repo: merge-only updates pass, content changes fail."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        g = lambda *a: _run(self.d, *a)
        g("init", "-q", "-b", "main")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        g("config", "commit.gpgsign", "false")
        (pathlib.Path(self.d) / "base.txt").write_text("base\n")
        g("add", "."); g("commit", "-qm", "base")
        self.base0 = g("rev-parse", "HEAD")
        g("checkout", "-qb", "pr")
        (pathlib.Path(self.d) / "feat.txt").write_text("feat\n")
        g("add", "."); g("commit", "-qm", "feat")
        self.reviewed = g("rev-parse", "HEAD")
        self._commit_receipt(g)
        g("checkout", "-q", "main")
        (pathlib.Path(self.d) / "other.txt").write_text("other\n")
        g("add", "."); g("commit", "-qm", "main moves")
        self.base1 = g("rev-parse", "HEAD")
        g("checkout", "-q", "pr")
        self.g = g

    def _commit_receipt(self, g):
        rp = pathlib.Path(self.d) / RPATH
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(receipt(reviewed_head_sha=self.reviewed))
        g("add", "."); g("commit", "-qm", "receipt")

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, head, reviewed=None, base=None):
        body = BODY.replace(HEAD, reviewed or self.reviewed)
        e = {"pull_request": {"body": body, "head": {"sha": head}, "base": {"sha": base or self.base1}}}
        old = os.getcwd()
        os.chdir(self.d)
        try:
            return crd.check(e)
        finally:
            os.chdir(old)

    def test_receipt_only_followup_accepted(self):
        self.assertEqual(self._check(self.g("rev-parse", "HEAD"), base=self.base0), [])

    def test_non_receipt_followup_rejected(self):
        (pathlib.Path(self.d) / "feat.txt").write_text("changed\n")
        self.g("commit", "-qam", "extra")
        errs = self._check(self.g("rev-parse", "HEAD"), base=self.base0)
        self.assertTrue(any("stale review" in e for e in errs), errs)

    def _followup_errs(self, mutate):
        mutate(self.g)
        return self._check(self.g("rev-parse", "HEAD"), base=self.base0)

    def test_rename_out_of_reviewed_path_into_receipts_rejected(self):
        (pathlib.Path(self.d) / ".agent/reviews/receipts").mkdir(parents=True, exist_ok=True)

        def mv(g):
            g("mv", "feat.txt", ".agent/reviews/receipts/feat.json")
            g("commit", "-qm", "sneak")
        errs = self._followup_errs(mv)
        self.assertTrue(any("stale review" in e for e in errs), errs)

    def test_receipt_deletion_and_non_json_rejected(self):
        def add_txt(g):
            (pathlib.Path(self.d) / ".agent/reviews/receipts/x.txt").write_text("x")
            g("add", "."); g("commit", "-qm", "txt")
        errs = self._followup_errs(add_txt)
        self.assertTrue(any("stale review" in e for e in errs), errs)

    def test_receipt_symlink_followup_rejected(self):
        def ln(g):
            os.symlink("../../../feat.txt", pathlib.Path(self.d) / ".agent/reviews/receipts/l.json")
            g("add", "."); g("commit", "-qm", "link")
        errs = self._followup_errs(ln)
        self.assertTrue(any("stale review" in e for e in errs), errs)

    def test_merge_only_update_passes(self):
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        self.assertEqual(self._check(self.g("rev-parse", "HEAD")), [])

    def test_extra_commit_fails(self):
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        (pathlib.Path(self.d) / "feat.txt").write_text("changed\n")
        self.g("commit", "-qam", "extra")
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("stale review" in e and "net change differs" in e for e in errs), errs)

    def test_not_ancestor_fails(self):
        self.g("reset", "-q", "--hard", self.base0)
        (pathlib.Path(self.d) / "feat.txt").write_text("rewritten\n")
        self.g("add", "."); self.g("commit", "-qm", "rewritten")
        self._commit_receipt(self.g)
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("stale review" in e and "not an ancestor" in e for e in errs), errs)

    def test_missing_reviewed_fails(self):
        errs = self._check(self.g("rev-parse", "HEAD"), reviewed="d" * 40)
        self.assertTrue(any("stale review" in e and "unavailable" in e for e in errs), errs)

    def test_whitespace_only_change_fails(self):
        f = pathlib.Path(self.d) / "m.py"
        self.g("checkout", "-q", "-B", "pr", self.reviewed)
        f.write_text("if x:\n    a()\nb()\n")
        self.g("add", "."); self.g("commit", "-qm", "py")
        self.reviewed = self.g("rev-parse", "HEAD")
        self._commit_receipt(self.g)
        f.write_text("if x:\n    a()\n    b()\n")
        self.g("commit", "-qam", "indent")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        errs = self._check(self.g("rev-parse", "HEAD"))
        self.assertTrue(any("net change differs" in e for e in errs), errs)


REPO = "o/r"


class OffBranch(unittest.TestCase):
    """Live-state evaluation with a local bare origin and a stubbed GitHub API (no network)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self._tmp.name)
        self.bare, self.wd = str(t / "origin.git"), str(t / "wd")
        _run(str(t), "init", "-q", "--bare", "-b", "main", self.bare)
        os.mkdir(self.wd)
        self.g = lambda *a: _run(self.wd, *a)
        g = self.g
        g("init", "-q", "-b", "main"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        g("config", "commit.gpgsign", "false"); g("remote", "add", "origin", self.bare)
        (pathlib.Path(self.wd) / "base.txt").write_text("base\n")
        g("add", "."); g("commit", "-qm", "base"); self.base = g("rev-parse", "HEAD")
        g("checkout", "-qb", "pr")
        (pathlib.Path(self.wd) / "feat.txt").write_text("feat\n")
        g("add", "."); g("commit", "-qm", "feat")
        self.head = g("rev-parse", "HEAD"); self.tree = g("rev-parse", "HEAD^{tree}")
        g("push", "-q", "origin", "main", f"{self.head}:refs/pull/1/head")
        self.body = (f"Author-lane: claude\nReview-Disposition: PASS\nReviewed-subject-sha256: {'b' * 64}\n"
                     f"Reviewed-head-sha: {self.head}\nReviewed-by: codex\n")
        self.api_fail = False
        self.mutate = {}
        self.live = {"head": {"sha": self.head}, "base": {"sha": self.base, "ref": "main", "repo": {"full_name": REPO}}, "body": self.body}

    def tearDown(self):
        self._tmp.cleanup()

    def rec(self, **kw):
        r = {"schema": 2, "repo": REPO, "pr": 1, "reviewed_head_sha": self.head, "tree": self.tree, "base_commit": self.base,
             "policy_version": crd.POLICY_VERSION, "run_id": "r1", "reviewer_lane": "codex", "author_lane": "claude",
             "verdict": "PASS", "output_file": "x.log", "output_sha256": "c" * 64, "created_at": "2026-11-06T00:00:00Z"}
        r.update(kw)
        return r

    def publish(self, r, name=None, raw=None, parent=True, mode="100644"):
        """Append a receipt file to the bare repo's review-receipts branch (test double for `publish`)."""
        name = name or f"receipts/pr{r['pr']}-{r['reviewed_head_sha'][:12]}.json"
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(self._tmp.name, "idx"), "GIT_AUTHOR_NAME": "t",
               "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        run = lambda *a, i=None: subprocess.run(["git", "-C", self.wd, *a], env=env, input=i, capture_output=True,
                                                 text=True, check=True).stdout.strip()
        if os.path.exists(env["GIT_INDEX_FILE"]):
            os.remove(env["GIT_INDEX_FILE"])
        par = subprocess.run(["git", "-C", self.bare, "rev-parse", "-q", "--verify", "refs/heads/review-receipts"],
                             capture_output=True, text=True).stdout.strip()
        if par:
            run("fetch", "-q", "origin", "refs/heads/review-receipts"); run("read-tree", par)
        blob = run("hash-object", "-w", "--stdin", i=raw if raw is not None else json.dumps(r))
        run("update-index", "--add", "--cacheinfo", f"{mode},{blob},{name}")
        c = run("commit-tree", run("write-tree"), "-m", "r", *(["-p", par] if par else []))
        run("push", "-q", "origin", f"{c}:refs/heads/review-receipts")

    def evaluate(self, event=None, number=1, fetch_head=True):
        self.calls = 0

        def get(url):
            self.calls += 1
            if self.api_fail:
                raise OSError("api down")
            if self.calls in self.mutate:
                self.mutate[self.calls]()
            self.assertTrue(url.endswith(f"/repos/{REPO}/pulls/{number}"), url)
            return self.live
        old = os.getcwd()
        os.chdir(self.wd)
        try:
            ev = event or {"repository": {"full_name": REPO},
                           "pull_request": {"number": number, "body": "", "head": {"sha": (self.live.get("head") or {}).get("sha", self.head)}}}
            return crd.evaluate(ev, get=get, fetch_head=fetch_head)
        finally:
            os.chdir(old)

    def test_valid_receipt_head_unchanged(self):
        self.publish(self.rec())
        self.assertEqual(self.evaluate(), [])
        self.assertEqual(self.g("rev-parse", "pr"), self.head)  # no receipt commit on the PR branch

    def test_edit_event_with_stale_body_reads_live_body(self):
        # Same-second push and edit: the event for the final head carries an empty/old body; the live body decides.
        self.publish(self.rec())
        ev = {"repository": {"full_name": REPO}, "pull_request": {"number": 1, "body": "", "head": {"sha": self.head}}}
        self.assertEqual(self.evaluate(ev), [])
        # Re-run on an unchanged head picks up a corrected body.
        self.live["body"] = "wrong"
        self.assertTrue(self.evaluate(ev))
        self.live["body"] = self.body
        self.assertEqual(self.evaluate(ev), [])

    def test_event_for_old_head_is_stale_and_never_validates_the_live_head(self):
        self.publish(self.rec())
        ev = {"repository": {"full_name": REPO}, "pull_request": {"number": 1, "body": self.body, "head": {"sha": "9" * 40}}}
        errs = self.evaluate(ev)
        self.assertTrue(any("stale run" in e for e in errs), errs)
        errs = self.evaluate({"repository": {"full_name": REPO}, "pull_request": {"number": 1}})
        self.assertTrue(any("lacks the PR head" in e for e in errs), errs)

    def test_head_or_body_changed_during_check_fails(self):
        self.publish(self.rec())
        self.mutate = {2: lambda: self.live.update(body="edited after the receipt was read")}
        errs = self.evaluate()
        self.assertTrue(any("changed while the check ran" in e for e in errs), errs)
        self.mutate = {2: lambda: self.live.update(head={"sha": "8" * 40})}
        self.live["body"] = self.body
        self.assertTrue(any("changed while the check ran" in e for e in errs + self.evaluate()))

    def test_api_failure_fails_closed(self):
        self.publish(self.rec())
        self.api_fail = True
        errs = self.evaluate()
        self.assertTrue(any("failing closed" in e for e in errs), errs)
        self.api_fail = False
        self.live = {"head": {}}
        self.assertTrue(any("failing closed" in e for e in self.evaluate()))

    def test_live_head_not_fetchable_or_moved_fails(self):
        self.publish(self.rec())
        self.live["head"]["sha"] = "9" * 40
        self.live["body"] = self.body.replace(self.head, "9" * 40)
        self.assertTrue(any("moved" in e or "cannot fetch" in e for e in self.evaluate()))

    def test_missing_receipt_and_missing_branch(self):
        errs = self.evaluate()  # branch absent
        self.assertTrue(any("missing receipt" in e for e in errs), errs)
        self.publish(self.rec(), name="receipts/pr9-aaaaaaaaaaaa.json")  # branch exists, wrong file
        self.assertTrue(any("missing receipt" in e for e in self.evaluate()))

    def test_malformed_receipt_rejected(self):
        self.publish(self.rec(), raw="{not json")
        self.assertTrue(any("cannot read" in e for e in self.evaluate()))

    def test_schema_and_type_confusion_rejected(self):
        for kw in ({"schema": 1}, {"schema": True}, {"pr": True}, {"repo": None}, {"tree": "abc"}, {"base_commit": ""},
                   {"output_sha256": "zz"}, {"policy_version": "other"}, {"run_id": " "}):
            self.setUp_branch_reset()
            self.publish(self.rec(**kw))
            self.assertNotEqual(self.evaluate(), [], kw)

    def setUp_branch_reset(self):
        subprocess.run(["git", "-C", self.bare, "update-ref", "-d", "refs/heads/review-receipts"], capture_output=True)

    def test_self_review_rejected(self):
        self.publish(self.rec(reviewer_lane="claude"))
        self.live["body"] = self.body.replace("Reviewed-by: codex", "Reviewed-by: claude")
        errs = self.evaluate()
        self.assertTrue(any("self-review" in e or "must differ" in e for e in errs), errs)

    def test_lane_and_verdict_mismatch_rejected(self):
        for kw in ({"reviewer_lane": "gemini"}, {"author_lane": "qwen"}, {"verdict": "PASS_WITH_FOLLOWUPS"}, {"verdict": "REQUEST_CHANGES"}):
            self.setUp_branch_reset()
            self.publish(self.rec(**kw))
            self.assertNotEqual(self.evaluate(), [], kw)

    def test_replay_onto_other_pr_head_repo_rejected(self):
        # receipt for PR 2 copied to PR 1's path
        self.publish(self.rec(pr=2), name=f"receipts/pr1-{self.head[:12]}.json")
        self.assertTrue(any("replay" in e for e in self.evaluate()))
        self.setUp_branch_reset()
        self.publish(self.rec(repo="evil/fork"))
        self.assertTrue(any("replay" in e for e in self.evaluate()))
        # receipt for another head (and tree) under this head's path
        self.setUp_branch_reset()
        other = "d" * 40
        self.publish(self.rec(reviewed_head_sha=other, tree="e" * 40), name=f"receipts/pr1-{self.head[:12]}.json")
        errs = self.evaluate()
        self.assertTrue(any("reviewed_head_sha" in e for e in errs), errs)
        # right head, wrong tree
        self.setUp_branch_reset()
        self.publish(self.rec(tree="e" * 40))
        self.assertTrue(any("tree" in e for e in self.evaluate()))

    def test_stale_head_rejected(self):
        self.publish(self.rec())
        (pathlib.Path(self.wd) / "feat.txt").write_text("changed\n")
        self.g("commit", "-qam", "more")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/1/head")
        self.live["head"]["sha"] = new
        errs = self.evaluate()
        self.assertTrue(any("stale review" in e or "net change differs" in e for e in errs), errs)

    def test_merge_only_update_keeps_receipt_valid(self):
        self.publish(self.rec())
        self.g("checkout", "-q", "main")
        (pathlib.Path(self.wd) / "other.txt").write_text("o\n")
        self.g("add", "."); self.g("commit", "-qm", "main moves")
        nb = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "origin", "main")
        self.g("checkout", "-q", "pr")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/1/head")
        self.live["head"]["sha"], self.live["base"]["sha"] = new, nb
        self.assertEqual(self.evaluate(), [])

    def test_legacy_committed_receipt_still_validates(self):
        rp = pathlib.Path(self.wd) / RPATH.replace("aaaaaaaaaaaa", self.head[:12])
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(receipt(reviewed_head_sha=self.head))
        self.g("add", "."); self.g("commit", "-qm", "legacy receipt")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/1/head")
        self.live["head"]["sha"] = new
        self.live["body"] = self.body + f"Review-Receipt: {rp.relative_to(self.wd)}\n"
        self.assertEqual(self.evaluate(), [])

    def test_offbranch_receipt_takes_precedence_over_legacy(self):
        rp = pathlib.Path(self.wd) / ".agent/reviews/receipts/pr1-x.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(receipt(reviewed_head_sha=self.head))
        self.g("add", "."); self.g("commit", "-qm", "legacy receipt")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/1/head")
        self.live["head"]["sha"] = new
        self.live["body"] = self.body + "Review-Receipt: .agent/reviews/receipts/pr1-x.json\n"
        self.publish(self.rec(verdict="REQUEST_CHANGES"))
        self.assertTrue(any("verdict" in e for e in self.evaluate()))

    def _legacy_pr(self, number=1, receipt_pr=None):
        rp = pathlib.Path(self.wd) / ".agent/reviews/receipts/pr-x.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(receipt(reviewed_head_sha=self.head, pr=receipt_pr or number))
        self.g("add", "."); self.g("commit", "-qm", "legacy receipt")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/{number}/head")
        self.live["head"]["sha"] = new
        self.live["body"] = self.body + "Review-Receipt: .agent/reviews/receipts/pr-x.json\n"

    def test_unreadable_offbranch_receipt_never_falls_back_to_legacy(self):
        self._legacy_pr()
        self.assertEqual(self.evaluate(), [])  # sanity: legacy alone passes (branch absent)
        cases = {"malformed": dict(raw="{nope"), "null": dict(raw="null"), "list": dict(raw="[]"),
                 "symlink": dict(mode="120000")}
        for name, kw in cases.items():
            self.setUp_branch_reset()
            self.publish(self.rec(), **kw)
            errs = self.evaluate()
            self.assertTrue(errs, name)
        # branch exists but cannot be fetched
        self.setUp_branch_reset()
        self.publish(self.rec())
        self.g("remote", "set-url", "origin", str(pathlib.Path(self.wd) / "nowhere.git"))
        self.assertTrue(self.evaluate(fetch_head=False))

    def test_legacy_fallback_frozen_to_cohort_and_bound_to_pr(self):
        self.g("push", "-q", "origin", f"{self.head}:refs/pull/721/head")
        self._legacy_pr(number=721)
        errs = self.evaluate(number=721)
        self.assertTrue(any("legacy cohort" in e for e in errs), errs)
        self.g("reset", "-q", "--hard", self.head)
        self._legacy_pr(number=1, receipt_pr=999)  # receipt names another PR
        errs = self.evaluate()
        self.assertTrue(any("replay" in e for e in errs), errs)


    def _evil_merge(self):
        """PR retargeted to an attacker branch holding unreviewed commit E; clean merge (reviewed head, E)."""
        self.publish(self.rec())
        self.g("checkout", "-q", "-b", "evil", self.base)
        (pathlib.Path(self.wd) / "evil.txt").write_text("unreviewed\n")
        self.g("add", "."); self.g("commit", "-qm", "E")
        e = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "origin", "evil")
        self.g("checkout", "-q", "pr")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "evil")
        new = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "-f", "origin", f"{new}:refs/pull/1/head")
        self.live["head"]["sha"] = new
        return e

    def test_attacker_selected_base_throughout_rejected(self):
        e = self._evil_merge()
        self.live["base"].update(sha=e, ref="evil")
        errs = self.evaluate()
        self.assertTrue(any("only" in x and "main" in x for x in errs), errs)
        # even a forged ref=main with the attacker sha cannot launder E: ancestry is tested against origin's main
        self.live["base"].update(ref="main")
        errs = self.evaluate()
        self.assertTrue(any("not in the base branch" in x for x in errs), errs)

    def test_base_changing_back_to_main_between_reads_rejected(self):
        e = self._evil_merge()
        self.live["base"].update(sha=e, ref="evil")
        self.mutate = {2: lambda: self.live["base"].update(sha=self.base, ref="main")}
        self.assertTrue(self.evaluate())
        # base changes between reads while a legitimately reviewed head looks acceptable
        self.g("push", "-q", "-f", "origin", f"{self.head}:refs/pull/1/head")
        self.live["head"]["sha"] = self.head
        self.live["base"].update(sha=self.base, ref="main")
        self.mutate = {2: lambda: self.live["base"].update(sha=self.head)}
        self.assertTrue(any("changed while the check ran" in x for x in self.evaluate()))
        self.mutate = {2: lambda: self.live["base"].update(ref="evil")}
        self.live["base"].update(sha=self.base, ref="main")
        self.assertTrue(self.evaluate())

    def test_foreign_repo_base_rejected(self):
        self.publish(self.rec())
        self.live["base"]["repo"] = {"full_name": "evil/fork"}
        self.assertTrue(any("only" in x for x in self.evaluate()))

    def test_main_throughout_control_passes(self):
        self.publish(self.rec())
        self.assertEqual(self.evaluate(), [])

    def test_real_http_api_path(self):
        import http.server, threading
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                ok = self.path == f"/repos/{REPO}/pulls/1" and self.headers.get("Authorization") == "Bearer tok"
                self.send_response(200 if ok else 404)
                self.end_headers()
                self.wfile.write(json.dumps(outer.live if ok else {}).encode())

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.publish(self.rec())
        env = {k: os.environ.get(k) for k in ("GITHUB_API_URL", "GH_TOKEN")}
        os.environ["GITHUB_API_URL"], os.environ["GH_TOKEN"] = f"http://127.0.0.1:{srv.server_port}", "tok"
        old = os.getcwd()
        os.chdir(self.wd)
        try:
            ev1 = {"repository": {"full_name": REPO}, "pull_request": {"number": 1, "head": {"sha": self.head}}}
            self.assertEqual(crd.evaluate(ev1), [])
            os.environ["GH_TOKEN"] = "bad"  # 404 -> HTTPError -> fail closed
            self.assertTrue(any("failing closed" in e for e in crd.evaluate(ev1)))
        finally:
            os.chdir(old)
            srv.shutdown()
            for k, v in env.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_event_without_pr_number_fails(self):
        self.assertTrue(self.evaluate({"pull_request": {}}))


class Relocation(unittest.TestCase):
    """Merge-only updates must be clean automatic merges; a patch-id match is not enough."""

    LINES = ["k"] * 3 + ["b"] + ["k"] * 6 + ["b"] + ["k"] * 3

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name
        g = self.g = lambda *a: _run(self.d, *a)
        g("init", "-q", "-b", "main"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        g("config", "commit.gpgsign", "false")
        self.write("m.txt", self.LINES)
        g("add", "."); g("commit", "-qm", "base"); self.base0 = g("rev-parse", "HEAD")
        g("checkout", "-qb", "pr")
        self.write("m.txt", self.edit(first=True))
        g("commit", "-qam", "reviewed change"); self.reviewed = g("rev-parse", "HEAD")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, lines):
        (pathlib.Path(self.d) / name).write_text("\n".join(lines) + "\n")

    def edit(self, first):
        out = list(self.LINES)
        out[3 if first else 10] = "B"
        return out

    def main_commit(self, name="other.txt", lines=("o",)):
        self.g("checkout", "-q", "main")
        self.write(name, list(lines))
        self.g("add", "."); self.g("commit", "-qm", "main moves")
        base = self.g("rev-parse", "HEAD")
        self.g("checkout", "-q", "pr")
        return base

    def errs(self, base, number=None):
        pr = {"body": BODY.replace(HEAD, self.reviewed), "head": {"sha": self.g("rev-parse", "HEAD")}, "base": {"sha": base}}
        if number:
            pr["number"] = number
        old = os.getcwd()
        os.chdir(self.d)
        try:
            return crd.check({"pull_request": pr, "repository": {"full_name": REPO}})
        finally:
            os.chdir(old)

    def stale(self, errs):
        return any("stale review" in e and "net change differs" in e for e in errs)

    def test_patch_id_equal_relocation_commit_rejected(self):
        base = self.main_commit()
        self.write("m.txt", self.edit(first=False))  # same edit, other hunk: identical patch-id
        self.g("commit", "-qam", "relocate")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        self.assertTrue(self.stale(self.errs(base)), self.errs(base))

    def test_relocation_hidden_inside_merge_rejected(self):
        base = self.main_commit()
        self.g("merge", "-q", "--no-ff", "--no-commit", "main")
        self.write("m.txt", self.edit(first=False))
        self.g("add", "."); self.g("commit", "-qm", "Update branch")
        self.assertTrue(self.stale(self.errs(base)), self.errs(base))

    def test_hand_resolved_conflict_rejected(self):
        changed = list(self.LINES); changed[3] = "Z"
        base = self.main_commit("m.txt", changed)
        r = subprocess.run(["git", "-C", self.d, "merge", "--no-ff", "-m", "x", "main"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)  # really conflicts
        self.write("m.txt", self.edit(first=True))
        self.g("add", "."); self.g("commit", "-qm", "Update branch (resolved by hand)")
        self.assertTrue(self.stale(self.errs(base)), self.errs(base))

    def test_merge_of_commit_outside_base_rejected(self):
        base = self.main_commit()
        self.g("checkout", "-qb", "side", self.base0)
        self.write("side.txt", ["s"])
        self.g("add", "."); self.g("commit", "-qm", "unreviewed side work")
        self.g("checkout", "-q", "pr")
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "side")
        errs = self.errs(base)
        self.assertTrue(any("not in the base branch" in e for e in errs), errs)

    def test_clean_automatic_merge_accepted(self):
        base = self.main_commit()
        self.g("merge", "-q", "--no-ff", "-m", "Update branch", "main")
        self.assertFalse([e for e in self.errs(base) if "stale" in e])

    def test_receipt_only_update_is_legacy_cohort_only(self):
        base = self.main_commit()
        rp = pathlib.Path(self.d) / ".agent/reviews/receipts/x.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("{}")
        self.g("add", "."); self.g("commit", "-qm", "receipt")
        self.assertFalse([e for e in self.errs(base, number=5) if "stale" in e])
        self.assertTrue([e for e in self.errs(base, number=721) if "stale" in e])


if __name__ == "__main__":
    unittest.main()
