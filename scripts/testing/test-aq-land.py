#!/usr/bin/env python3
"""Tests for scripts/ai/aq-land with a local bare origin and stubbed gh, delegates, receipt tool and tier0 (no network)."""
import fcntl
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/ai/aq-land"

STUB_DELEGATE = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys, time
lane = os.path.basename(sys.argv[0]).split("delegate-to-")[1]
S = os.environ["STUB_DIR"]
cfg = json.load(open(f"{S}/cfg.json"))
args = sys.argv[1:]
open(f"{S}/calls.log", "a").write(f"{lane} {' '.join(args)}\n")
open(f"{S}/cwd.log", "a").write(f"{lane} {os.getcwd()}\n")
if "--prompt-file" in args:
    open(f"{S}/prompt-{lane}.txt", "w").write(open(args[args.index("--prompt-file") + 1]).read())
if "--budget-check-only" in args:
    sys.exit(cfg.get(lane, {}).get("budget_rc", 0))
c = cfg.get(lane, {"mode": "ok"})
n = len([l for l in open(f"{S}/calls.log") if l.startswith(lane + " ") and "--budget" not in l])
prompt = open(args[args.index("--prompt-file") + 1]).read()
head = re.search(r"head ([0-9a-f]{40})", prompt).group(1)
rid = f"{lane}-20261106-12{n:04d}-abc{n}"
print(f"[delegate-to-{lane}] Delegating task: {rid}", flush=True)
side = c.get("side") if n == 1 else None
if side == "main_moves":
    subprocess.run(["git", "clone", "-q", f"{S}/origin.git", f"{S}/c2"], check=True)
    subprocess.run(["git", "-C", f"{S}/c2", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "--allow-empty", "-m", "m"], check=True)
    open(f"{S}/c2/other.txt", "w").write("o\n")
    subprocess.run(["git", "-C", f"{S}/c2", "add", "."], check=True)
    subprocess.run(["git", "-C", f"{S}/c2", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "main moves"], check=True)
    subprocess.run(["git", "-C", f"{S}/c2", "push", "-q", "origin", "HEAD:main"], check=True)
if side == "local_commit":
    open("extra.txt", "w").write("x\n")
    subprocess.run(["git", "add", "extra.txt"], check=True)
    subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "late edit"], check=True)
mode = c["mode"]
model = args[args.index("--model") + 1] if "--model" in args else ""
if model and model in c.get("quota_models", []):
    mode = "quota"
if mode == "quota":
    print("Error: 429 RESOURCE_EXHAUSTED quota exceeded")
    sys.exit(1)
if mode == "silent":
    time.sleep(60)
if mode == "hang":
    while True:
        print("working", flush=True)
        time.sleep(0.3)
out = f"{S}/{rid}.log"
shown = head if mode != "wronghead" else "f" * 40
verdict = "REQUEST_CHANGES" if mode == "negative" else "PASS"
text = f"looks fine\nReviewed-head-sha: {shown}\nReview-Disposition: {verdict}\n"
open(out, "w").write(text)
print(f"Output file: {out}")
print(text)
'''

STUB_GH = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
S = os.environ["STUB_DIR"]
P = f"{S}/gh.json"
st = json.load(open(P))
a = sys.argv[1:]
def save():
    json.dump(st, open(P, "w"))
def flag(n):
    return a[a.index(n) + 1] if n in a else None
def suicide(tag):
    if st.get("kill") == tag:
        st["kill"] = ""
        save()
        os.kill(os.getppid(), 9)
        sys.exit(1)
def bump(k):
    st[k] = st.get(k, 0) + 1
    save()
    return st[k]
st.setdefault("calls", []).append(" ".join(a[:3]))
cmd = " ".join(a[:2])
branch_head = lambda b: subprocess.run(["git", "--git-dir", f"{S}/origin.git", "rev-parse", f"refs/heads/{b}"], capture_output=True, text=True).stdout.strip()
if cmd == "pr list":
    if bump("n_list") == 2:
        suicide("after_push")
    print(json.dumps([{"number": p["number"], "state": p["state"]} for p in st["prs"] if p["branch"] == flag("--head")]))
elif cmd == "pr create":
    n = 77
    st["prs"].append({"number": n, "state": "OPEN", "branch": flag("--head"), "body": open(flag("--body-file")).read()})
    st["creates"] = st.get("creates", 0) + 1
    save()
    print(f"https://github.com/o/r/pull/{n}")
    suicide("after_create")
elif cmd == "pr view":
    pr = [p for p in st["prs"] if p["number"] == int(a[2])][0]
    seq = st.get("rollups", [[]])
    roll = seq.pop(0) if len(seq) > 1 else seq[0]
    save()
    print(json.dumps({"headRefOid": st.get("head_override") or branch_head(pr["branch"]), "state": pr["state"], "body": pr["body"], "statusCheckRollup": roll}))
elif cmd == "pr edit":
    [p for p in st["prs"] if p["number"] == int(a[2])][0]["body"] = open(flag("--body-file")).read()
    save()
elif cmd == "pr merge":
    st["merges"] = st.get("merges", 0) + 1
    assert flag("--match-head-commit")
    [p for p in st["prs"] if p["number"] == int(a[2])][0]["state"] = "MERGED"
    save()
    suicide("after_merge")
elif cmd == "repo view":
    print(json.dumps({"nameWithOwner": "o/r"}))
elif cmd == "run rerun":
    st.setdefault("reruns", []).append(a[2])
    save()
elif a[0] == "api":
    if "required_status_checks" in a[1]:
        if st.get("required") is None:
            sys.exit(1)
        print(json.dumps({"contexts": st["required"]}))
    else:
        print(json.dumps(st["jobs"][a[1].rsplit("/", 1)[1]]))
else:
    sys.exit(2)
'''

STUB_RECEIPT = r'''#!/usr/bin/env python3
import json, os, sys
S = os.environ["STUB_DIR"]
a = sys.argv[1:]
open(f"{S}/receipt.log", "a").write(" ".join(a) + "\n")
if a[0] == "mint":
    rid = a[a.index("--run-id") + 1]
    lane = rid.split("-")[0]
    json.dump({"run_id": rid, "reviewer_lane": "local-direct" if lane == "local" else lane, "reviewed_head_sha": a[a.index("--head") + 1]},
              open(a[a.index("--out") + 1], "w"))
else:
    done = f"{S}/published"
    key = os.path.basename(a[1])
    seen = open(done).read().split() if os.path.exists(done) else []
    if key in seen:
        print("already published")
    else:
        open(done, "a").write(key + "\n")
        print("published")
    if json.load(open(f"{S}/gh.json")).get("kill") == "after_publish":
        g = json.load(open(f"{S}/gh.json")); g["kill"] = ""; json.dump(g, open(f"{S}/gh.json", "w"))
        os.kill(os.getppid(), 9)
'''

STUB_TIER0 = '#!/bin/sh\necho tier0 >> "$STUB_DIR/tier0.log"\n[ -e "$STUB_DIR/tier0.fail" ] && { echo "FAIL: stub gate"; exit 1; }\nexit 0\n'

RD_OK = {"name": "review-disposition", "status": "COMPLETED", "conclusion": "SUCCESS"}
BODY = "## Details\n- scope\n\n## What\nw\n\n## How\nh\n\n## Why\ny\n"


def sh(cwd, *a):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.S = pathlib.Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.origin, self.wd = self.S / "origin.git", self.S / "wd"
        sh(self.S, "git", "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.wd.mkdir()
        self.g = lambda *a: sh(self.wd, "git", *a)
        self.g("init", "-q", "-b", "main")
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            self.g("config", k, v)
        self.g("remote", "add", "origin", str(self.origin))
        (self.wd / "shared.txt").write_text("base\n")
        self.g("add", "."); self.g("commit", "-qm", "base"); self.g("push", "-q", "origin", "main")
        self.g("checkout", "-qb", "feat/x")
        self.change("scripts/foo.py", "print(1)\n")
        (self.S / "body.md").write_text(BODY)
        for name, src in (("delegate-to-gemini", STUB_DELEGATE), ("delegate-to-codex", STUB_DELEGATE), ("delegate-to-local", STUB_DELEGATE),
                          ("gh", STUB_GH), ("receipt", STUB_RECEIPT), ("tier0", STUB_TIER0)):
            (self.S / name).write_text(src)
            (self.S / name).chmod(0o755)
        self.cfg({})
        self.gh_state({})
        self.env = {**os.environ, "STUB_DIR": str(self.S), "AQ_LAND_GH": str(self.S / "gh"), "AQ_LAND_DELEGATE_DIR": str(self.S),
                    "AQ_LAND_RECEIPT_TOOL": str(self.S / "receipt"), "AQ_LAND_TIER0": str(self.S / "tier0"),
                    "AQ_LAND_STATE_DIR": str(self.S / "state"), "AQ_LAND_POLL_S": "0.05", "AQ_LAND_STALL_S": "2",
                    "AQ_LAND_REVIEW_TIMEOUT_S": "4", "AQ_LAND_CHECKS_TIMEOUT_S": "5", "AQ_LAND_LOCK_WAIT_S": "1"}

    def tearDown_state(self):
        for n in ("calls.log", "published", "receipt.log"):
            (self.S / n).unlink(missing_ok=True)
        import shutil
        shutil.rmtree(self.S / "state", ignore_errors=True)
        subprocess.run(["git", "--git-dir", str(self.origin), "update-ref", "-d", "refs/heads/feat/x"], check=True)

    def change(self, path, text, commit=True):
        p = self.wd / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        self.g("add", path)
        if commit:
            self.g("commit", "-qm", f"change {path}")

    def cfg(self, c):
        (self.S / "cfg.json").write_text(json.dumps(c))

    def gh_state(self, extra):
        st = {"prs": [], "rollups": [[{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}, RD_OK]], "required": ["test"], "jobs": {}}
        st.update(extra)
        (self.S / "gh.json").write_text(json.dumps(st))

    def ghs(self):
        return json.loads((self.S / "gh.json").read_text())

    def calls(self, lane):
        p = self.S / "calls.log"
        return [l for l in (p.read_text().splitlines() if p.exists() else []) if l.startswith(lane + " ") and "--budget" not in l]

    def land(self, *extra, expect=None):
        args = [sys.executable, str(TOOL), "--worktree", str(self.wd), "--title", "t", "--body-file", str(self.S / "body.md"), *extra]
        r = subprocess.run(args, capture_output=True, text=True, env=self.env, timeout=120)
        self.assertNotIn("Traceback", r.stderr)
        if expect is not None:
            self.assertEqual(r.returncode, expect, r.stdout + r.stderr)
        return r

    def stop_line(self, r):
        lines = [l for l in r.stderr.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("aq-land: STOP "), lines)
        return lines[0]

    def pr_body(self):
        return self.ghs()["prs"][0]["body"]

    def published(self):
        p = self.S / "published"
        return p.read_text().split() if p.exists() else []


class Landing(Base):
    def test_happy_path_no_clutter_commit(self):
        head = self.g("rev-parse", "HEAD")
        self.land(expect=0)
        self.assertEqual(self.ghs()["prs"][0]["state"], "MERGED")
        self.assertEqual(len(self.calls("gemini")), 1)
        self.assertEqual(self.g("rev-parse", "HEAD"), head)  # no receipt or other commit on the branch
        self.assertEqual(sh(self.S, "git", "--git-dir", str(self.origin), "rev-parse", "refs/heads/feat/x"), head)
        body = self.pr_body()
        self.assertIn(f"Reviewed-head-sha: {head}", body)
        self.assertIn("Reviewed-by: gemini", body)
        self.assertLess(body.index("### Review record"), body.index("## What"))
        self.assertEqual(len(self.published()), 1)
        self.assertNotIn("--no-verify", (self.S / "calls.log").read_text())

    def test_changed_body_file_is_pushed_on_rerun_and_unchanged_is_not(self):
        edits = lambda: [c for c in self.ghs()["calls"] if c.startswith("pr edit")]
        self.gh_state({"required": ["never-reported"]})
        self.land(expect=1)
        self.assertEqual(edits(), [])
        self.land(expect=1)
        self.assertEqual(edits(), [])  # unchanged body: no edit
        (self.S / "body.md").write_text(BODY.replace("- scope", "- scope corrected"))
        self.land(expect=1)
        self.assertEqual(len(edits()), 1)
        self.assertIn("scope corrected", self.pr_body())

    def test_resume_after_kill_never_duplicates(self):
        for point in ("after_push", "after_create", "after_publish", "after_merge"):
            with self.subTest(point=point):
                self.tearDown_state()
                self.gh_state({"kill": point})
                first = self.land()
                self.assertEqual(first.returncode, -9, first.stderr)
                second = self.land(expect=0)
                st = self.ghs()
                self.assertEqual((st["creates"], st["merges"]), (1, 1), point)
                self.assertEqual(len(self.calls("gemini")), 1, point)  # one review across both runs
                self.assertEqual(len(self.published()), 1, point)  # one receipt, never a duplicate
                self.assertEqual(st["prs"][0]["state"], "MERGED")
                if point == "after_merge":
                    self.assertIn("already merged", second.stdout)

    def test_lock_contention_stops_with_named_reason(self):
        lock = self.S / "state"
        lock.mkdir(exist_ok=True)
        with open(lock / "lock", "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            r = self.land(expect=1)
        self.assertIn("STOP lock", self.stop_line(r))
        self.assertEqual(self.calls("gemini"), [])


class StaleEvidence(Base):
    def test_main_moves_clean_merge_keeps_review(self):
        reviewed = self.g("rev-parse", "HEAD")
        self.cfg({"gemini": {"mode": "ok", "side": "main_moves"}})
        self.land(expect=0)
        self.assertEqual(len(self.calls("gemini")), 1)  # the clean merge of main did not cost a second review
        pushed = sh(self.S, "git", "--git-dir", str(self.origin), "rev-parse", "refs/heads/feat/x")
        self.assertNotEqual(pushed, reviewed)
        self.assertIn(f"Reviewed-head-sha: {reviewed}", self.pr_body())
        self.assertIn(f"--head {reviewed}", (self.S / "receipt.log").read_text())

    def test_head_changed_by_a_real_commit_needs_a_new_review(self):
        self.cfg({"gemini": {"mode": "ok", "side": "local_commit"}})
        self.land(expect=0)
        self.assertEqual(len(self.calls("gemini")), 2)
        head = self.g("rev-parse", "HEAD")
        self.assertIn(f"Reviewed-head-sha: {head}", self.pr_body())

    def test_review_of_another_head_is_rejected(self):
        self.cfg({"gemini": {"mode": "wronghead"}, "codex": {"budget_rc": 3}, "local": {"mode": "wronghead"}})
        r = self.land(expect=1)
        self.assertIn("covers head", self.stop_line(r))
        self.assertEqual(self.ghs()["prs"], [])

    def test_conflict_stops_and_leaves_worktree_clean(self):
        self.change("shared.txt", "branch edit\n")
        sh(self.S, "git", "clone", "-q", str(self.origin), str(self.S / "c3"))
        (self.S / "c3/shared.txt").write_text("main edit\n")
        sh(self.S / "c3", "git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qam", "main edit")
        sh(self.S / "c3", "git", "push", "-q", "origin", "HEAD:main")
        r = self.land(expect=1)
        line = self.stop_line(r)
        self.assertIn("STOP merge: conflict", line)
        self.assertIn("shared.txt", line)
        self.assertFalse((self.wd / ".git/MERGE_HEAD").exists())
        self.assertEqual(self.calls("gemini"), [])


class Lanes(Base):
    def test_stall_and_budget_fall_through_to_local_and_are_recorded(self):
        self.cfg({"codex": {"mode": "silent"}, "local": {"mode": "ok"}})
        self.land("--lanes", "codex,local", expect=0)
        body = self.pr_body()
        self.assertIn("codex: stall", body)
        self.assertIn("Reviewed-by: local-direct", body)
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"budget_rc": 3}, "local": {"mode": "ok"}})
        self.tearDown_state(); self.gh_state({})
        self.land("--lanes", "codex,local", expect=0)
        self.assertIn("codex: budget refused", self.pr_body())
        self.assertEqual(self.calls("codex"), [])  # budget refused: never dispatched
        self.assertNotIn("--force-budget", (self.S / "calls.log").read_text())

    def test_gemini_has_no_stall_limit_a_silent_review_hits_the_hard_limit(self):
        # gemini -p prints only its final answer, so silence is normal for minutes; stall must not kill it
        self.cfg({"gemini": {"mode": "silent"}, "local": {"mode": "ok"}})
        self.land("--lanes", "gemini,local", expect=0)
        body = self.pr_body()
        self.assertIn("gemini: timeout after 4s", body)
        self.assertNotIn("gemini: stall", body)

    def test_gemini_gets_an_explicit_model_default_and_override(self):
        self.land(expect=0)
        self.assertIn("--model gemini-3.8-flash-high", self.calls("gemini")[0])
        self.tearDown_state(); self.gh_state({})
        self.env["AQ_LAND_GEMINI_MODEL"] = "gemini-x-custom"
        self.land(expect=0)
        self.assertIn("--model gemini-x-custom", self.calls("gemini")[-1])

    def test_gemini_quota_retries_once_on_the_fallback_model_and_records_it(self):
        self.cfg({"gemini": {"mode": "ok", "quota_models": ["gemini-3.8-flash-high"]}})
        self.land(expect=0)
        calls = self.calls("gemini")
        self.assertEqual(len(calls), 2, calls)
        self.assertIn("--model gemini-3.8-flash-high", calls[0])
        self.assertIn("--model gemini-3.8-flash-medium", calls[1])
        body = self.pr_body()
        self.assertIn("gemini: model gemini-3.8-flash-high quota error; retried with gemini-3.8-flash-medium", body)
        self.assertIn("Reviewed-by: gemini", body)

    def test_gemini_quota_on_both_models_leaves_the_lane_after_one_retry(self):
        self.cfg({"gemini": {"mode": "quota"}, "local": {"mode": "ok"}})
        self.land("--lanes", "gemini,local", expect=0)
        self.assertEqual(len(self.calls("gemini")), 2)
        body = self.pr_body()
        self.assertIn("retried with gemini-3.8-flash-medium", body)
        self.assertIn("gemini: quota error", body)
        self.assertIn("Reviewed-by: local-direct", body)

    def test_reviewer_prompt_points_at_the_worktree_and_runs_there(self):
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        self.land("--lanes", "gemini", expect=0)
        wd = str(self.wd)
        text = (self.S / "prompt-gemini.txt").read_text()
        self.assertIn(f"under the worktree path {wd}", text)
        self.assertIn("main checkout", text)
        self.assertIn("out of date", text)
        self.assertIn("Do not run test suites", text)
        cwd = [l for l in (self.S / "cwd.log").read_text().splitlines() if l.startswith("gemini ")][0].split(" ", 1)[1]
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(wd))
        self.tearDown_state(); self.gh_state({})
        self.land("--lanes", "local", expect=0)
        self.assertNotIn("worktree path", (self.S / "prompt-local.txt").read_text())

    def test_codex_wrapper_runs_in_the_directory_aq_land_names(self):
        self.land("--lanes", "codex", expect=0)
        self.assertIn("--shared", self.calls("codex")[0])
        src = (ROOT / "scripts/ai/delegate-to-codex").read_text()
        self.assertGreaterEqual(src.count("${AQ_DELEGATE_CWD:-$REPO_ROOT}"), 3)

    def test_hard_timeout_and_quota_error_fall_through(self):
        self.cfg({"gemini": {"mode": "hang"}, "codex": {"mode": "quota"}, "local": {"mode": "ok"}})
        self.land(expect=0)
        body = self.pr_body()
        self.assertIn("gemini: timeout after 4s", body)
        self.assertIn("codex: quota error", body)

    def test_no_eligible_lane_stops_and_releases_the_lock(self):
        self.cfg({"gemini": {"mode": "quota"}, "codex": {"budget_rc": 3}, "local": {"mode": "quota"}})
        r = self.land(expect=1)
        self.assertIn("STOP review: no eligible independent lane", self.stop_line(r))
        with open(self.S / "state/lock", "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if still held
        self.assertEqual(self.ghs()["prs"], [])

    def test_never_the_authors_lane(self):
        r = self.land("--author-lane", "gemini", "--lanes", "gemini", expect=1)
        self.assertIn("author's lane", self.stop_line(r))
        self.assertEqual(self.calls("gemini"), [])

    def test_negative_review_stops_without_falling_back(self):
        self.cfg({"gemini": {"mode": "negative"}})
        r = self.land(expect=1)
        self.assertIn("returned REQUEST_CHANGES", self.stop_line(r))
        self.assertEqual(self.calls("codex") + self.calls("local"), [])

    def test_trust_critical_change_never_goes_to_local_alone(self):
        self.change("scripts/governance/new-gate.sh", "#!/bin/sh\n")
        self.cfg({"gemini": {"mode": "quota"}, "codex": {"budget_rc": 3}, "local": {"mode": "ok"}})
        r = self.land(expect=1)
        line = self.stop_line(r)
        self.assertIn("needs codex or gemini", line)
        self.assertEqual(self.calls("local"), [])

    def test_local_has_a_small_diff_limit(self):
        self.cfg({"gemini": {"mode": "quota"}, "codex": {"budget_rc": 3}, "local": {"mode": "ok"}})
        self.env["AQ_LAND_LOCAL_MAX_DIFF"] = "10"
        r = self.land(expect=1)
        self.assertIn("over the small-diff limit", self.stop_line(r))
        self.assertEqual(self.calls("local"), [])


class Preflight(Base):
    def test_docs_only_change_is_refused_unless_allowed(self):
        self.g("reset", "-q", "--hard", "origin/main")
        self.change("docs/a.md", "x\n")
        self.change(".agent/notes.txt", "x\n")
        r = self.land(expect=1)
        self.assertIn("documentation-only", self.stop_line(r))
        self.assertEqual(self.calls("gemini"), [])
        r = self.land("--allow-docs-only", expect=0)

    def test_code_under_doc_dirs_is_code_but_docs_alone_are_refused(self):
        self.g("reset", "-q", "--hard", "origin/main")
        self.change(".agent/skills/x/scripts/a.py", "print(1)\n")
        self.land(expect=0)
        self.tearDown_state()
        self.g("reset", "-q", "--hard", "origin/main")
        self.change("docs/a.md", "x\n")
        self.assertIn("documentation-only", self.stop_line(self.land(expect=1)))

    def test_executable_file_under_doc_dirs_is_code(self):
        self.g("reset", "-q", "--hard", "origin/main")
        self.change(".agents/tool", "#!/bin/sh\n")
        self.g("update-index", "--chmod=+x", ".agents/tool")
        self.g("commit", "-qm", "exec")
        self.land(expect=0)

    def test_receipt_files_in_the_pr_are_refused(self):
        self.change(".agent/reviews/receipts/pr1-x.json", "{}\n")
        r = self.land(expect=1)
        self.assertIn("receipt files in the diff", self.stop_line(r))

    def test_tier0_gate_runs_before_commit_and_blocks_it(self):
        self.change("scripts/bar.py", "print(2)\n", commit=False)
        msg = self.S / "msg.txt"
        msg.write_text("feat(x): bar\n")
        (self.S / "tier0.fail").write_text("")
        before = self.g("rev-parse", "HEAD")
        r = self.land("--commit-msg-file", str(msg), expect=1)
        self.assertIn("STOP tier0", self.stop_line(r))
        self.assertEqual(self.g("rev-parse", "HEAD"), before)
        (self.S / "tier0.fail").unlink()
        hook = self.wd / ".git/hooks/pre-commit"
        hook.write_text(f"#!/bin/sh\necho hook >> {self.S}/hook.log\n")
        hook.chmod(0o755)
        self.land("--commit-msg-file", str(msg), expect=0)
        self.assertNotEqual(self.g("rev-parse", "HEAD"), before)
        self.assertTrue((self.S / "hook.log").exists())  # hooks ran: no --no-verify

    def test_source_has_no_no_verify_or_force_push(self):
        src = TOOL.read_text()
        for bad in ("--no-verify", "--force", "force-with-lease", '"-f"'):
            self.assertNotIn(bad, src)
        self.assertNotIn("force-budget", src.replace("never --force", ""))


class Checks(Base):
    def run_checks(self, rollups, required=("test",), jobs=None, expect=0, review=True, **extra):
        if review:
            rollups = [r if any(c.get("name") == "review-disposition" for c in r) or not r else r + [RD_OK] for r in rollups]
        self.gh_state({"rollups": rollups, "required": list(required) if required is not None else None, "jobs": jobs or {}, **extra})
        return self.land(expect=expect)

    def test_empty_rollup_and_unreadable_protection_never_merges(self):
        r = self.run_checks([[]], required=None, review=False, expect=1)
        self.assertIn("timed out waiting for: review-disposition", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_other_checks_green_without_review_disposition_never_merges(self):
        ok = {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        r = self.run_checks([[ok]], required=None, review=False, expect=1)
        self.assertIn("review-disposition", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_stuck_in_progress_check_with_succeeded_job_counts_as_passed(self):
        stuck = {"name": "repo-structure-lint", "status": "IN_PROGRESS", "detailsUrl": "https://github.com/o/r/actions/runs/5/job/9"}
        ok = {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        self.run_checks([[stuck, ok]], required=["test", "repo-structure-lint"], jobs={"9": {"status": "completed", "conclusion": "success"}})
        self.assertEqual(self.ghs()["merges"], 1)

    def test_unfinished_job_is_never_treated_as_passed(self):
        stuck = {"name": "lint", "status": "IN_PROGRESS", "detailsUrl": "https://x/actions/runs/5/job/9"}
        r = self.run_checks([[stuck]], required=["lint"], jobs={"9": {"status": "in_progress", "conclusion": None}}, expect=1)
        self.assertIn("timed out waiting for: lint", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_failed_job_behind_a_stuck_check_fails(self):
        stuck = {"name": "lint", "status": "IN_PROGRESS", "detailsUrl": "https://x/actions/runs/5/job/9"}
        r = self.run_checks([[stuck]], required=["lint"], jobs={"9": {"status": "completed", "conclusion": "failure"}}, expect=1)
        self.assertIn("failed: lint", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_waits_for_pending_then_merges(self):
        pend = {"name": "test", "status": "IN_PROGRESS", "detailsUrl": "https://x/nojob"}
        ok = {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        self.run_checks([[pend], [pend], [ok]])
        self.assertEqual(self.ghs()["merges"], 1)

    def test_failed_and_missing_required_checks_block_the_merge(self):
        bad = {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}
        r = self.run_checks([[bad]], expect=1)
        self.assertIn("failed: test", self.stop_line(r))
        ok = {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        self.tearDown_state()
        r = self.run_checks([[ok]], required=["test", "never-reported"], expect=1)
        self.assertIn("never-reported", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_optional_check_may_fail_but_a_required_one_may_not(self):
        ok = {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
        flaky = {"name": "flaky", "status": "COMPLETED", "conclusion": "FAILURE"}
        self.gh_state({"rollups": [[ok, flaky, RD_OK]], "required": ["test"]})
        self.land("--optional-check", "flaky", expect=0)

    def test_head_that_is_not_the_one_landed_never_reuses_a_green(self):
        r = self.run_checks([[{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}]], head_override="e" * 40, expect=1)
        self.assertIn("refusing to reuse checks for another head", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_review_disposition_failure_is_rerun_after_the_receipt_exists(self):
        bad = {"name": "review-disposition", "status": "COMPLETED", "conclusion": "FAILURE", "detailsUrl": "https://x/actions/runs/12/job/3"}
        ok = {"name": "review-disposition", "status": "COMPLETED", "conclusion": "SUCCESS"}
        self.run_checks([[bad], [ok]], required=["review-disposition"])
        self.assertEqual(self.ghs()["reruns"], ["12"])
        self.assertEqual(self.ghs()["merges"], 1)


if __name__ == "__main__":
    unittest.main()
