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
if side == "main_manifest":
    subprocess.run(["git", "clone", "-q", f"{S}/origin.git", f"{S}/c2"], check=True)
    open(f"{S}/c2/{c['theirs_path']}", "w").write(c["theirs_text"])
    subprocess.run(["git", "-C", f"{S}/c2", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qam", "main edits manifest"], check=True)
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
if mode == "transport":
    print("Reconnecting... 5/5\nworkspace routing discovery failed: error sending request")
    sys.exit(1)
if mode == "cap":
    print("[delegate-to-x] local headless cap reached (self-imposed)")
    sys.exit(3)
if mode == "silent":
    time.sleep(60)
if mode == "hang":
    while True:
        print("working", flush=True)
        time.sleep(0.3)
out = f"{S}/{rid}.log"
shown = head if mode != "wronghead" else "f" * 40
verdict = "REQUEST_CHANGES" if mode in ("negative", "cantrun", "finding", "prose", "bullet", "real", "mixed") else "PASS"
body = {"cantrun": "I am unable to proceed: every command timed out. Please check the status of the environment.\n",
        "real": "The sandbox environment appears to be unresponsive, causing all command attempts to time out. As I cannot access the worktree files or the provided diff to perform the required review, I am unable to proceed with the task.\n\nPlease check the status of the environment.\n",
        "finding": "scripts/ai/aq-land:365 drops valid rejections when a command timed out.\n",
        "prose": "The lock is released twice, which corrupts state. I was also unable to access one file.\n",
        "mixed": "The lock is released twice, which corrupts state. I am unable to proceed because subsequent commands timed out.\n",
        "bullet": "- The retry loop never stops after the command timed out.\n",
        "missing_upstream_evidence": "## Upstream changes reviewed\n- package and range reviewed; looks fine.\n",
        "missing_package": "## Upstream changes reviewed\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: lock input matched the deployed closure.\n",
        "missing_old": "## Upstream changes reviewed\n- Package and range: pkg -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/closure-before /tmp/closure-after; exit 0 (no differences).\n",
        "multi_package": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0; other 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/closure-before /tmp/closure-after; exit 0 (no differences).\n",
        "negated_runtime": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; differences found.\n- Deployed runtime: no deployed service was run.\n- Runtime result: passed\n",
        "no_deployed_runtime": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; differences found.\n- Runtime result: passed\n",
        "placeholder_authority": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: <Nix or manifest>\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: lock input matched the deployed closure.\n",
        "negated_authority": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: not Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: lock input matched the deployed closure.\n",
        "placeholder_closure": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: <changed or unchanged>\n- Closure evidence: lock input matched the deployed closure.\n",
        "negated_closure": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: no closure evidence was collected.\n",
        "failed_active": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: failed but active\n",
        "unhealthy_active": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: active but unhealthy\n",
        "changed_without_operands": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures; differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: active\n",
        "changed_exit_zero": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; exit 0, differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: active\n",
        "changed_operand_only": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old-changed /nix/store/new\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: active\n",
        "timed_out_active": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; exit 0, differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: timed out but active\n",
        "unchanged_operand_only": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/unchanged /tmp/closure-after\n",
        "changed_no_differences": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: changed\n- Closure evidence: nix store diff-closures /nix/store/old /nix/store/new; no differences found.\n- Deployed runtime: systemctl is-active pkg.service\n- Runtime result: active\n",
        "unchanged_explicitly_changed": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/closure-before /tmp/closure-after; differences found.\n",
        "arbitrary_closure": "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: lock input matched the deployed closure.\n",
        "wrong_package_range": "## Upstream changes reviewed\n- Package and range: other 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/closure-before /tmp/closure-after; exit 0 (no differences).\n"}.get(mode, "## Upstream changes reviewed\n- Package and range: pkg 1.0 -> 2.0\n- Release notes: https://example.test/pkg/releases/2.0\n- Authority: Nix\n- Input path: flake.lock\n- Closure: unchanged\n- Closure evidence: git diff --no-index /tmp/closure-before /tmp/closure-after; exit 0 (no differences).\n")
text = f"{body}Reviewed-head-sha: {shown}\nReview-Disposition: {verdict}\n"
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
fl = st.get("flaky")
if fl and cmd == fl["cmd"] and bump("n_flaky") <= fl["times"]:
    sys.stderr.write(fl["msg"] + "\n")
    sys.exit(1)
def move_main(msg):
    c = f"{S}/cm-{st.get('n_moves', 0)}"
    st["n_moves"] = st.get("n_moves", 0) + 1
    save()
    subprocess.run(["git", "clone", "-q", f"{S}/origin.git", c], check=True)
    open(f"{c}/moved{st['n_moves']}.txt", "w").write("m\n")
    subprocess.run(["git", "-C", c, "add", "."], check=True)
    subprocess.run(["git", "-C", c, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", msg], check=True)
    subprocess.run(["git", "-C", c, "push", "-q", "origin", "HEAD:main"], check=True)
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
    roll = seq[0]
    if "statusCheckRollup" in flag("--json") and len(seq) > 1:
        seq.pop(0)  # only a status poll consumes the rollup sequence, never a head-only view
        save()
    if "mergeStateStatus" in flag("--json"):
        print(json.dumps({"headRefOid": branch_head(pr["branch"]), "mergeStateStatus": st.get("merge_state", "CLEAN"), "baseRefOid": branch_head("main")}), flush=True)
        if st.get("move_after_state_view") == bump("n_state"):
            move_main("main moved between the freshness check and the merge")
        sys.exit(0)
    if st.get("main_moves_at_wait") and "statusCheckRollup" in flag("--json") and bump("n_wait") == 1:
        move_main("main moved after CI")
    print(json.dumps({"headRefOid": st.get("head_override") or branch_head(pr["branch"]), "state": pr["state"], "body": pr["body"], "statusCheckRollup": roll}))
elif cmd == "pr update-branch":
    bump("updates")
    pr = [p for p in st["prs"] if p["number"] == int(a[2])][0]
    c = f"{S}/c3-{st['updates']}"
    subprocess.run(["git", "clone", "-q", "-b", pr["branch"], f"{S}/origin.git", c], check=True)
    subprocess.run(["git", "-C", c, "-c", "user.name=x", "-c", "user.email=x@x", "merge", "-q", "--no-ff", "-m", "Merge main", "origin/main"], check=True)
    subprocess.run(["git", "-C", c, "push", "-q", "origin", "HEAD"], check=True)
    if st.get("after_update_rollups"):
        st["rollups"] = st.pop("after_update_rollups")
        save()
    if st.get("keep_moving"):
        move_main("main moved again")
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
        print(json.dumps({"contexts": st["required"], "strict": st.get("strict", False)}))
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
    if a[0] == "publish":
        g = json.load(open(f"{S}/gh.json")); g.setdefault("calls", []).append("RECEIPT publish"); json.dump(g, open(f"{S}/gh.json", "w"))
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
        (self.wd / "requirements.txt").write_text("pkg>=1.0\n")
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
                    "AQ_LAND_STATE_DIR": str(self.S / "state"),
                    # without this record_outcome writes the stub PR to the live outcome-receipts.jsonl
                    "AQ_DELEGATION_DIR": str(self.S / "deleg"),
                    "AQ_LAND_WORKTREE_DIR": str(self.S / "wts"), "AQ_LAND_POLL_S": "0.05", "AQ_LAND_STALL_S": "2",
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
        rc = self.S / "deleg" / "outcome-receipts.jsonl"  # the outcome receipt lands in the isolated dir, never the live one
        self.assertEqual([json.loads(l)["pr"] for l in rc.read_text().splitlines()], [77])
        self.assertEqual(oct(rc.stat().st_mode & 0o777), "0o600")

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

    def test_push_survives_main_moving_when_branch_tracks_origin_main(self):
        """A branch made from refs/remotes/origin/main tracks it; pre-push's sync check then reads main as the upstream."""
        self.g("branch", "--set-upstream-to=origin/main")
        hook = self.wd / ".git/hooks/pre-push"
        # Models the real hook's sync check, with main advancing once right before it (after aq-land's last look).
        hook.write_text(f'''#!/usr/bin/env bash
set -e
S="{self.S}"
if [ ! -e "$S/hook-moved" ]; then
  touch "$S/hook-moved"
  git clone -q "$S/origin.git" "$S/c3"
  echo m > "$S/c3/late.txt"
  git -C "$S/c3" add .
  git -C "$S/c3" -c user.name=x -c user.email=x@x commit -q -m late
  git -C "$S/c3" push -q origin HEAD:main
fi
up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{{upstream}}' 2>/dev/null || true)"
[ -n "$up" ] || exit 0
git fetch -q --no-tags "${{up%%/*}}" "${{up#*/}}"
behind="$(git rev-list --count "HEAD..$up")"
[ "$behind" -eq 0 ] || {{ echo "pre-push: behind $up by $behind" >&2; exit 1; }}
''')
        hook.chmod(0o755)
        self.land(expect=0)
        self.assertEqual(len(self.calls("gemini")), 1)
        self.assertEqual(sh(self.S, "git", "--git-dir", str(self.origin), "rev-parse", "refs/heads/feat/x"), self.g("rev-parse", "HEAD"))
        self.assertEqual(self.g("rev-parse", "--abbrev-ref", "@{upstream}"), "origin/feat/x")

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


CI0 = {"checks": [{"id": "a", "cmd": "x"}], "test_exempt": []}
WF0 = "jobs:\n  a:\n    steps: []\n"


def jtext(d):
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


class Manifests(Base):
    """main moves into conflict only in additive manifests: structural merge, fresh review; anything else stops."""

    def conflict(self, base, ours, theirs):
        """Each arg maps path -> text: base lands on main (and the branch), ours on the branch, theirs on main."""
        self.g("checkout", "-q", "main")
        for pth, t in base.items():
            self.change(pth, t)
        self.g("push", "-q", "origin", "main")
        self.g("checkout", "-q", "feat/x")
        self.g("merge", "-q", "--no-edit", "main")
        for pth, t in ours.items():
            self.change(pth, t)
        sh(self.S, "git", "clone", "-q", str(self.origin), str(self.S / "c3"))
        for pth, t in theirs.items():
            (self.S / "c3" / pth).parent.mkdir(parents=True, exist_ok=True)
            (self.S / "c3" / pth).write_text(t)
        if theirs:
            sh(self.S / "c3", "git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qam", "main edits")
            sh(self.S / "c3", "git", "push", "-q", "origin", "HEAD:main")

    def clean_stop(self, r, *needles):
        line = self.stop_line(r)
        self.assertIn("STOP merge", line)
        for n in needles:
            self.assertIn(n, line)
        self.assertFalse((self.wd / ".git/MERGE_HEAD").exists())
        self.assertEqual(self.g("status", "--porcelain", "--untracked-files=no"), "")
        self.assertEqual(self.calls("gemini"), [])

    def test_two_sides_adding_entries_merge_and_keep_formatting(self):
        b = {"checks": [{"id": "a", "cmd": "x"}], "test_exempt": []}
        o = {"checks": [{"id": "a", "cmd": "x"}, {"id": "ours", "cmd": "o"}], "test_exempt": []}
        t = {"checks": [{"id": "a", "cmd": "x"}, {"id": "theirs", "cmd": "t"}], "test_exempt": [{"script": "s", "reason": "r"}]}
        wf = lambda extra: WF0 + extra
        self.conflict({"config/ci-checks.json": jtext(b), ".github/workflows/test.yml": WF0},
                      {"config/ci-checks.json": jtext(o), ".github/workflows/test.yml": wf("  ours:\n    steps: []\n")},
                      {"config/ci-checks.json": jtext(t), ".github/workflows/test.yml": wf("  theirs:\n    steps: []\n")})
        r = self.land(expect=0)
        self.assertIn("resolved additive manifest conflicts", r.stdout)
        ids = [c["id"] for c in json.loads((self.wd / "config/ci-checks.json").read_text())["checks"]]
        self.assertEqual(sorted(ids), ["a", "ours", "theirs"])
        text = (self.wd / "config/ci-checks.json").read_text()
        self.assertEqual(text, jtext(json.loads(text)))
        self.assertEqual(json.loads(text)["test_exempt"], t["test_exempt"])
        wf_text = (self.wd / ".github/workflows/test.yml").read_text()
        self.assertIn("  ours:", wf_text)
        self.assertIn("  theirs:", wf_text)
        self.assertEqual(len(self.g("rev-list", "--parents", "-n1", "HEAD").split()), 3)  # a real merge commit

    def test_resolved_merge_during_review_gets_a_fresh_review(self):
        b = {"checks": [{"id": "a", "cmd": "x"}]}
        o = {"checks": [{"id": "a", "cmd": "x"}, {"id": "ours", "cmd": "o"}]}
        t = {"checks": [{"id": "a", "cmd": "x"}, {"id": "theirs", "cmd": "t"}]}
        self.conflict({"config/ci-checks.json": jtext(b)}, {"config/ci-checks.json": jtext(o)}, {})
        self.cfg({"gemini": {"mode": "ok", "side": "main_manifest", "theirs_path": "config/ci-checks.json", "theirs_text": jtext(t)}})
        self.land(expect=0)
        self.assertEqual(len(self.calls("gemini")), 2)  # the first review does not cover the hand-resolved merge
        head = self.g("rev-parse", "HEAD")
        self.assertIn(f"Reviewed-head-sha: {head}", self.pr_body())
        ids = [c["id"] for c in json.loads((self.wd / "config/ci-checks.json").read_text())["checks"]]
        self.assertEqual(sorted(ids), ["a", "ours", "theirs"])

    def test_deletion_on_one_side_is_kept(self):
        b = {"checks": [{"id": "a", "cmd": "x"}, {"id": "b", "cmd": "y"}]}
        o = {"checks": [{"id": "a", "cmd": "x"}]}
        t = {"checks": [{"id": "a", "cmd": "x"}, {"id": "b", "cmd": "y"}, {"id": "c", "cmd": "z"}]}
        self.conflict({"config/ci-checks.json": jtext(b)}, {"config/ci-checks.json": jtext(o)}, {"config/ci-checks.json": jtext(t)})
        self.land(expect=0)
        ids = [c["id"] for c in json.loads((self.wd / "config/ci-checks.json").read_text())["checks"]]
        self.assertEqual(ids, ["a", "c"])

    def test_true_conflict_on_a_scalar_stops_and_aborts(self):
        mk = lambda v: jtext({"checks": [{"id": "a", "cmd": v}]})
        self.conflict({"config/ci-checks.json": mk("x")}, {"config/ci-checks.json": mk("y")}, {"config/ci-checks.json": mk("z")})
        self.clean_stop(self.land(expect=1), "ci-checks.json", "both sides changed")

    def test_invalid_result_stops(self):
        self.conflict({"config/ci-checks.json": jtext(CI0)}, {"config/ci-checks.json": jtext({**CI0, "n": 1})},
                      {"config/ci-checks.json": "{not json\n"})
        self.clean_stop(self.land(expect=1), "not valid JSON")

    def test_invalid_workflow_union_stops(self):
        self.conflict({".github/workflows/test.yml": "a: 1\n"}, {".github/workflows/test.yml": "a: 1\nb: [\n"},
                      {".github/workflows/test.yml": "a: 1\nc: 2\n"})
        self.clean_stop(self.land(expect=1), "not valid YAML")

    def test_non_manifest_conflict_alongside_a_manifest_stops(self):
        self.conflict({"config/ci-checks.json": jtext(CI0), "shared2.txt": "b\n"},
                      {"config/ci-checks.json": jtext({**CI0, "p": 1}), "shared2.txt": "o\n"},
                      {"config/ci-checks.json": jtext({**CI0, "q": 1}), "shared2.txt": "t\n"})
        self.clean_stop(self.land(expect=1), "shared2.txt", "outside the additive manifests")


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

    def test_transport_failure_is_retried_once_and_not_called_quota(self):
        self.cfg({"gemini": {"mode": "transport"}, "local": {"mode": "ok"}})
        self.env["AQ_LAND_TRANSPORT_WAIT_S"] = "0"
        self.land(expect=0)
        body = self.pr_body()
        self.assertIn("gemini: transport error", body)
        self.assertNotIn("gemini: quota error", body)
        self.assertEqual(len(self.calls("gemini")), 2)

    def test_local_cap_is_labelled_and_not_retried(self):
        self.cfg({"gemini": {"mode": "cap"}, "local": {"mode": "ok"}})
        self.land(expect=0)
        self.assertIn("gemini: local cap", self.pr_body())
        self.assertEqual(len(self.calls("gemini")), 1)

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

    def test_could_not_run_request_changes_stops_with_a_rerun_hint_never_falls_through(self):
        self.cfg({"gemini": {"mode": "real"}, "codex": {"mode": "ok"}, "local": {"mode": "ok"}})
        r = self.land("--lanes", "gemini,codex,local", expect=1)
        line = self.stop_line(r)
        self.assertIn("returned REQUEST_CHANGES but its reply says it could not run", line)
        self.assertIn("re-run with --lanes codex,local", line)
        self.assertEqual(self.calls("codex") + self.calls("local"), [])
        self.assertEqual(self.ghs()["prs"], [])
        self.assertIn("could not run", json.loads((next((self.S / "state").glob("*/checkpoint.json"))).read_text())["review_suspect"])

    def test_could_not_run_on_the_only_lane_says_no_other_lane_is_left(self):
        self.cfg({"gemini": {"mode": "real"}})
        r = self.land("--lanes", "gemini", expect=1)
        self.assertIn("no other eligible lane is left", self.stop_line(r))

    def test_mixed_finding_and_could_not_run_reply_stops_plain(self):
        self.cfg({"gemini": {"mode": "mixed"}, "local": {"mode": "ok"}})
        r = self.land("--lanes", "gemini,local", expect=1)
        line = self.stop_line(r)
        self.assertIn("returned REQUEST_CHANGES; fix the findings", line)
        self.assertNotIn("re-run with", line)
        self.assertEqual(self.calls("local"), [])

    def test_request_changes_with_findings_stop_plain(self):
        for mode in ("finding", "prose", "bullet"):
            self.tearDown_state(); self.gh_state({})
            self.cfg({"gemini": {"mode": mode}, "local": {"mode": "ok"}})
            r = self.land("--lanes", "gemini,local", expect=1)
            self.assertIn("returned REQUEST_CHANGES; fix the findings", self.stop_line(r), mode)
            self.assertEqual(self.calls("local"), [], mode)

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


class DepFastLane(Base):
    def dep_branch(self, path="requirements.txt"):
        self.g("reset", "-q", "--hard", "origin/main")
        self.change(path, "pkg>=2.0\n")

    def cp(self):
        return json.loads(next((self.S / "state").glob("*/checkpoint.json")).read_text())

    def test_dependabot_manifest_only_uses_fast_lane(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        r = self.land("--author-lane", "Dependabot", expect=0)
        self.assertIn("fast-lane: dependency-bump (pkg 1.0 -> 2.0)", r.stdout)
        self.assertEqual(self.cp()["fast_lane"], "dependency-bump")
        self.assertEqual(len(self.calls("gemini")), 1)
        self.assertEqual(self.calls("local"), [])
        self.assertIn("Upstream changes reviewed", (self.S / "prompt-gemini.txt").read_text())

    def test_fast_lane_malformed_pass_tries_next_lane(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "missing_upstream_evidence"}, "codex": {"mode": "ok"}})
        self.land("--author-lane", "dependabot", expect=0)
        self.assertEqual(self.cp().get("rc_rounds", 0), 0)
        self.assertEqual(len(self.calls("codex")), 1)
        self.assertTrue(any(note.startswith("gemini: malformed PASS") for note in self.cp()["review"]["notes"]))

    def test_fast_lane_malformed_dependency_evidence_tries_next_lane(self):
        for mode in ("missing_package", "negated_runtime", "no_deployed_runtime", "placeholder_authority",
                     "negated_authority", "placeholder_closure", "negated_closure", "missing_old",
                     "multi_package", "failed_active", "unhealthy_active", "changed_without_operands",
                     "changed_no_differences", "unchanged_explicitly_changed", "arbitrary_closure",
                     "changed_operand_only", "unchanged_operand_only", "timed_out_active"):
            with self.subTest(mode=mode):
                self.tearDown_state(); self.gh_state({})
                self.dep_branch()
                self.cfg({"gemini": {"mode": mode}, "codex": {"mode": "ok"}})
                self.land("--author-lane", "dependabot", expect=0)
                self.assertEqual(len(self.calls("codex")), 1)

    def test_multi_package_diff_uses_normal_review_path(self):
        self.dep_branch()
        self.change("requirements.txt", "pkg>=2.0\nother>=2.0\n")
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        r = self.land("--author-lane", "dependabot", expect=0)
        self.assertIn("fast-lane: ambiguous or unsupported dependency diff, normal review path", r.stdout)
        self.assertEqual(self.cp().get("fast_lane", ""), "")
        self.assertNotIn("Upstream changes reviewed", (self.S / "prompt-gemini.txt").read_text())

    def test_evidence_package_and_range_must_match_actual_diff(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "wrong_package_range"}, "codex": {"mode": "ok"}})
        self.land("--author-lane", "dependabot", expect=0)
        self.assertEqual(len(self.calls("codex")), 1)

    def test_criteria_file_help_is_additive(self):
        r = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("added to dependency-bump criteria", r.stdout)

    def test_fast_lane_accepts_explicit_unchanged_closure_evidence(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        self.land("--author-lane", "dependabot", expect=0)
        self.assertEqual(len(self.calls("gemini")), 1)
        self.assertEqual(self.calls("codex"), [])

    def test_fast_lane_accepts_changed_closure_reported_with_successful_comparison(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "changed_exit_zero"}, "codex": {"mode": "ok"}})
        self.land("--author-lane", "dependabot", expect=0)
        self.assertEqual(self.calls("codex"), [])

    def test_unsupported_version_constraint_uses_normal_review_path(self):
        for requirement in ("pkg==2.0", "pkg>=2.0,<3"):
            with self.subTest(requirement=requirement):
                self.tearDown_state()
                self.gh_state({})
                self.dep_branch()
                self.change("requirements.txt", requirement + "\n")
                self.cfg({"gemini": {"mode": "ok"}})
                self.land("--author-lane", "dependabot", expect=0)
                self.assertEqual(self.cp()["fast_lane"], "")

    def test_non_manifest_file_means_normal_path(self):
        self.dep_branch()
        self.change("scripts/foo2.py", "print(2)\n")
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        r = self.land("--author-lane", "dependabot", expect=0)
        self.assertNotIn("fast-lane", r.stdout)
        self.assertEqual(self.cp().get("fast_lane", ""), "")
        self.assertNotIn("Upstream changes reviewed", (self.S / "prompt-gemini.txt").read_text())

    def test_non_dependabot_author_is_not_fast_laned(self):
        self.dep_branch()
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        r = self.land("--author-lane", "claude", expect=0)
        self.assertNotIn("fast-lane", r.stdout)
        self.assertEqual(self.cp().get("fast_lane", ""), "")

    def test_explicit_lanes_win_and_custom_criteria_retains_dependency_baseline(self):
        self.dep_branch()
        crit = self.S / "crit.md"
        crit.write_text("MY CRITERIA\n")
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}, "local": {"mode": "ok"}})
        r = self.land("--author-lane", "dependabot", "--lanes", "local", "--criteria-file", str(crit), expect=0)
        self.assertIn("fast-lane: dependency-bump", r.stdout)
        self.assertEqual(self.calls("gemini"), [])
        self.assertEqual(len(self.calls("local")), 1)
        text = (self.S / "prompt-local.txt").read_text()
        self.assertIn("MY CRITERIA", text)
        self.assertIn("Upstream changes reviewed", text)

    def test_staged_non_manifest_change_committed_before_review_means_normal_path(self):
        self.dep_branch()
        self.change("scripts/foo3.py", "print(3)\n", commit=False)
        msg = self.S / "msg.txt"
        msg.write_text("feat: x\n")
        self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
        r = self.land("--author-lane", "dependabot", "--commit-msg-file", str(msg), expect=0)
        self.assertNotIn("fast-lane: dependency-bump", r.stdout)
        self.assertEqual(self.cp()["fast_lane"], "")
        self.assertNotIn("Upstream changes reviewed", (self.S / "prompt-gemini.txt").read_text())

    def test_malformed_policy_globs_use_the_normal_path(self):
        for bad in (None, "*", ["*"], [""]):
            with self.subTest(globs=bad):
                self.tearDown_state(); self.gh_state({})
                pol = self.S / "policy.json"
                pol.write_text(json.dumps({"dependabot_manifest_exemption": {"author": "dependabot[bot]", "manifest_globs": bad}}))
                self.env["AQ_LAND_POLICY_FILE"] = str(pol)
                self.dep_branch()
                self.cfg({"gemini": {"mode": "ok"}, "codex": {"mode": "ok"}})
                r = self.land("--author-lane", "dependabot", expect=0)
                self.assertIn("fast-lane: policy invalid, normal review path", r.stdout)
                self.assertEqual(self.cp()["fast_lane"], "")


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
        line = self.stop_line(r)
        self.assertIn("STOP tier0", line)
        self.assertIn("FAIL: stub gate", line)  # the blocker, never just "tier0 failed"
        log = line.split("full output ")[1]
        self.assertIn("FAIL: stub gate", pathlib.Path(log).read_text())
        self.assertEqual(self.g("rev-parse", "HEAD"), before)
        (self.S / "tier0.fail").unlink()
        hook = self.wd / ".git/hooks/pre-commit"
        hook.write_text(f"#!/bin/sh\necho hook >> {self.S}/hook.log\n")
        hook.chmod(0o755)
        self.land("--commit-msg-file", str(msg), expect=0)
        self.assertNotEqual(self.g("rev-parse", "HEAD"), before)
        self.assertTrue((self.S / "hook.log").exists())  # hooks ran: no --no-verify

    def test_failing_commit_hook_shows_its_output_and_a_log(self):
        self.change("scripts/bar.py", "print(2)\n", commit=False)
        msg = self.S / "msg.txt"
        msg.write_text("feat(x): bar\n")
        hook = self.wd / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho 'ERROR: hook says no' >&2\nexit 1\n")
        hook.chmod(0o755)
        line = self.stop_line(self.land("--commit-msg-file", str(msg), expect=1))
        self.assertIn("STOP commit", line)
        self.assertIn("hook says no", line)
        self.assertTrue(pathlib.Path(line.split("full output ")[1]).is_file())

    def test_source_has_no_no_verify_or_force_push(self):
        src = TOOL.read_text()
        for bad in ("--no-verify", "--force", "force-with-lease", '"-f"'):
            self.assertNotIn(bad, src)
        self.assertNotIn("force-budget", src.replace("never --force", ""))


class OwnedPaths(Base):
    def owned(self, *globs):
        p = self.S / "owned.txt"
        p.write_text("# slice scope\n" + "\n".join(globs) + "\n")
        return str(p)

    def refusals(self):
        p = self.S / "state" / "owned-path-refusals.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def test_in_scope_change_passes_and_is_recorded_as_declared(self):
        self.land("--owned", self.owned("scripts/*.py"), expect=0)
        self.assertEqual(self.refusals(), [])

    def test_out_of_scope_stops_before_any_review_and_lists_files(self):
        self.change("config/other.json", "{}\n")
        r = self.land("--owned", self.owned("scripts/"), expect=1)
        line = self.stop_line(r)
        self.assertIn("outside the slice's owned paths", line)
        self.assertIn("config/other.json", line)
        self.assertNotIn("scripts/foo.py", line)
        self.assertEqual(self.calls("gemini"), [])
        rows = self.refusals()
        self.assertEqual([(x["branch"], x["files"]) for x in rows], [("feat/x", ["config/other.json"])])

    def test_declaration_file_in_the_branch_and_evidence_are_always_allowed(self):
        self.change(".agents/delegation/owned/feat_x.txt", "scripts/*.py\n")
        self.change("docs/harness-first/evidence/2026-11-18-x.md", "e\n")
        self.land(expect=0)

    def test_undeclared_warns_and_does_not_block(self):
        r = self.land(expect=0)
        self.assertIn("WARN no owned-path declaration", r.stdout + r.stderr)
        cp = json.loads(next((self.S / "state").glob("*/checkpoint.json")).read_text())
        self.assertEqual(cp["owned_paths"], "undeclared")

    def test_missing_owned_file_stops(self):
        r = self.land("--owned", str(self.S / "nope.txt"), expect=1)
        self.assertIn("--owned file not found", self.stop_line(r))

    def test_committed_rename_from_an_unowned_path_stops(self):
        self.g("checkout", "-q", "main")
        self.change("config/example.json", "{\"a\": 1, \"b\": 2, \"c\": 3}\n")
        self.g("push", "-q", "origin", "main")
        self.g("checkout", "-q", "feat/x")
        self.g("merge", "-q", "--no-edit", "main")
        self.g("mv", "config/example.json", "scripts/example.json")
        self.g("commit", "-qm", "move")
        r = self.land("--owned", self.owned("scripts/"), expect=1)
        self.assertIn("config/example.json", self.stop_line(r))

    def test_staged_rename_from_an_unowned_path_stops(self):
        self.g("checkout", "-q", "main")
        self.change("config/example.json", "{\"a\": 1, \"b\": 2, \"c\": 3}\n")
        self.g("push", "-q", "origin", "main")
        self.g("checkout", "-q", "feat/x")
        self.g("merge", "-q", "--no-edit", "main")
        self.g("mv", "config/example.json", "scripts/example.json")
        r = self.land("--owned", self.owned("scripts/"), expect=1)
        self.assertIn("config/example.json", self.stop_line(r))

    def test_relative_owned_path_resolves_against_the_callers_cwd(self):
        self.owned("scripts/*.py")
        args = [sys.executable, str(TOOL), "--worktree", str(self.wd), "--title", "t", "--body-file", str(self.S / "body.md"),
                "--owned", "owned.txt"]
        r = subprocess.run(args, capture_output=True, text=True, env=self.env, cwd=self.S, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_commit_added_during_review_outside_the_scope_stops_before_a_second_review_and_push(self):
        self.cfg({"gemini": {"mode": "ok", "side": "local_commit"}})  # adds extra.txt after the first review
        r = self.land("--owned", self.owned("scripts/"), expect=1)
        self.assertIn("extra.txt", self.stop_line(r))
        self.assertEqual(len(self.calls("gemini")), 1)
        self.assertEqual(self.published(), [])
        self.assertEqual(self.refusals()[-1]["files"], ["extra.txt"])

    def test_non_ascii_and_tab_filenames_match_their_real_paths(self):
        names = ["café ü.py", "a\tb.py"]
        for n in names:
            self.change("scripts/" + n, "x\n")
        self.land("--owned", self.owned("scripts/"), expect=0)
        self.tearDown_state()
        for n in names:
            self.change("config/" + n, "x\n")
        r = self.land("--owned", self.owned("scripts/"), expect=1)
        line = self.stop_line(r)
        self.assertIn("config/café ü.py", line)
        self.assertIn("config/a\tb.py", line)

    def test_merging_main_into_the_branch_does_not_count_mains_files(self):
        c2 = self.S / "c2"
        sh(self.S, "git", "clone", "-q", str(self.origin), str(c2))
        (c2 / "other.txt").write_text("o\n")
        sh(c2, "git", "add", ".")
        sh(c2, "git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "main moves")
        sh(c2, "git", "push", "-q", "origin", "HEAD:main")
        self.g("fetch", "-q", "origin")
        self.g("merge", "-q", "--no-edit", "origin/main")
        self.land("--owned", self.owned("scripts/*.py"), expect=0)


class Checks(Base):
    def run_checks(self, rollups, required=("test",), jobs=None, expect=0, review=True, **extra):
        if review:
            rollups = [r if any(c.get("name") == "review-disposition" for c in r) or not r else r + [RD_OK] for r in rollups]
        self.gh_state({"rollups": rollups, "required": list(required) if required is not None else None, "jobs": jobs or {}, **extra})
        return self.land(expect=expect)

    def test_transient_network_error_is_retried_within_the_deadline(self):
        self.env["AQ_LAND_RETRY_S"] = "0.05"
        r = self.run_checks([[{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}]],
                            flaky={"cmd": "pr view", "times": 3, "msg": "error connecting to api.github.com\nCheck your internet connection"})
        self.assertEqual(self.ghs()["merges"], 1)
        self.assertEqual(r.stdout.count("transient gh error"), 1)  # one line for the whole outage

    def test_persistent_network_failure_stops_at_the_deadline(self):
        self.env.update({"AQ_LAND_RETRY_S": "0.05", "AQ_LAND_CHECKS_TIMEOUT_S": "1"})
        r = self.run_checks([[]], flaky={"cmd": "pr view", "times": 100000, "msg": "error connecting to api.github.com"}, expect=1)
        self.assertIn("still failing", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_non_transient_gh_error_stops_at_once(self):
        r = self.run_checks([[]], flaky={"cmd": "pr view", "times": 100000, "msg": "HTTP 404: Not Found"}, expect=1)
        self.assertIn("STOP gh: gh pr view failed: HTTP 404", self.stop_line(r))
        self.assertEqual(self.ghs()["n_flaky"], 1)

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


class MergeFreshness(Base):
    """G0: a PR whose CI ran on an older main is updated and re-checked, never merged on stale results."""
    OK = [{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}, RD_OK]

    def jsonl(self):
        p = self.S / "deleg/outputs/aq-land/merge-freshness.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def test_up_to_date_pr_merges_without_update(self):
        self.gh_state({})
        self.land(expect=0)
        st = self.ghs()
        self.assertEqual((st["merges"], st.get("updates", 0)), (1, 0))
        row = self.jsonl()[0]
        self.assertEqual((row["pr"], row["was_behind"], row["updates"], row["extra_ci_wait_s"], row["merged"]), (77, False, 0, 0, True))

    def test_behind_pr_is_updated_rechecked_then_merged(self):
        self.gh_state({"main_moves_at_wait": True, "after_update_rollups": [[{"name": "test", "status": "IN_PROGRESS", "detailsUrl": "https://x/nojob"}, RD_OK], self.OK]})
        r = self.land(expect=0)
        st = self.ghs()
        self.assertEqual((st["updates"], st["merges"]), (1, 1))
        self.assertIn("is behind origin/main; updating", r.stdout)
        calls = st["calls"]
        self.assertLess(calls.index("pr update-branch 77"), len(calls) - 1 - calls[::-1].index("pr merge 77"))
        row = self.jsonl()[0]
        self.assertEqual((row["was_behind"], row["updates"], row["merged"]), (True, 1, True))
        self.assertGreater(row["extra_ci_wait_s"], 0)

    def test_resumed_settled_path_also_updates_when_behind(self):
        self.gh_state({"required": ["never-reported"]})
        self.land(expect=1)  # PR pushed, reviewed, receipted; stops at checks
        g = self.ghs()
        g.update({"required": ["test"], "main_moves_at_wait": True, "after_update_rollups": [self.OK]})
        (self.S / "gh.json").write_text(json.dumps(g))
        r = self.land(expect=0)
        self.assertIn("resuming PR #77", r.stdout)
        st = self.ghs()
        self.assertEqual((st["updates"], st["merges"], st["creates"]), (1, 1, 1))
        self.assertEqual(len(self.calls("gemini")), 1)  # the update kept the review; no second one

    def test_update_bound_exhausted_stops_without_merging(self):
        self.gh_state({"main_moves_at_wait": True, "keep_moving": True, "after_update_rollups": [self.OK]})
        r = self.land("--max-updates", "1", expect=1)
        self.assertIn("still behind origin/main after 1 update(s)", self.stop_line(r))
        st = self.ghs()
        self.assertEqual(st["updates"], 1)
        self.assertNotIn("merges", st)
        row = self.jsonl()[0]
        self.assertEqual((row["was_behind"], row["merged"]), (True, False))

    def test_main_advancing_after_the_check_is_caught_by_the_final_recheck(self):
        self.gh_state({"move_after_state_view": 1, "after_update_rollups": [self.OK]})
        self.land(expect=0)
        st = self.ghs()
        self.assertEqual((st["updates"], st["merges"]), (1, 1))

    def test_non_strict_protection_is_flagged_and_logged(self):
        self.gh_state({})
        r = self.land(expect=0)
        self.assertIn("main protection is not strict", r.stdout)
        self.assertIs(self.jsonl()[0]["strict"], False)

    def test_strict_protection_has_no_warning(self):
        self.gh_state({"strict": True})
        r = self.land(expect=0)
        self.assertNotIn("not strict", r.stdout)
        self.assertIs(self.jsonl()[0]["strict"], True)

    def test_resume_adopts_a_github_update_instead_of_a_second_merge(self):
        self.gh_state({"required": ["never-reported"]})
        self.land(expect=1)  # PR pushed, reviewed, receipted; stops at checks
        c = self.S / "c9"
        gi = ["git", "-C", str(c), "-c", "user.name=x", "-c", "user.email=x@x"]
        subprocess.run(["git", "clone", "-q", str(self.S / "origin.git"), str(c)], check=True)
        (c / "m.txt").write_text("m\n")
        subprocess.run([*gi, "add", "."], check=True)
        subprocess.run([*gi, "commit", "-qm", "main moves"], check=True)
        subprocess.run([*gi, "push", "-q", "origin", "HEAD:main"], check=True)
        subprocess.run([*gi, "checkout", "-q", "-b", "pr", "origin/" + self.g("rev-parse", "--abbrev-ref", "HEAD")], check=True)
        subprocess.run([*gi, "merge", "-q", "--no-ff", "-m", "Merge main", "origin/main"], check=True)
        subprocess.run([*gi, "push", "-q", "origin", "HEAD:" + self.g("rev-parse", "--abbrev-ref", "HEAD")], check=True)  # what GitHub update-branch did
        g = self.ghs()
        g.update({"required": ["test"]})
        (self.S / "gh.json").write_text(json.dumps(g))
        r = self.land(expect=0)
        self.assertIn("adopted the PR branch update", r.stdout)
        st = self.ghs()
        self.assertEqual((st.get("updates", 0), st["merges"]), (0, 1))
        self.assertEqual(len(self.calls("gemini")), 1)
        merges = self.g("rev-list", "--merges", "--count", "origin/main..HEAD")
        self.assertEqual(merges, "1")

    def test_after_an_update_the_ordinary_checks_must_reappear(self):
        self.env["AQ_LAND_CHECKS_TIMEOUT_S"] = "4"
        # protection requires ONLY review-disposition: the wait for "test" can come solely from the carry-forward
        self.gh_state({"required": ["review-disposition"], "main_moves_at_wait": True, "after_update_rollups": [[RD_OK]]})
        r = self.land(expect=1)
        self.assertIn("timed out waiting for: test", self.stop_line(r))
        self.assertNotIn("merges", self.ghs())

    def test_carried_checks_survive_an_interrupted_run(self):
        self.env["AQ_LAND_CHECKS_TIMEOUT_S"] = "3"
        self.gh_state({"required": ["review-disposition"], "main_moves_at_wait": True, "after_update_rollups": [[RD_OK]]})
        self.land(expect=1)  # updated, then stopped waiting for the ordinary check
        cp = json.loads(next(self.S.glob("**/checkpoint.json")).read_text())
        self.assertEqual(cp["expected_checks"]["names"], ["test"])
        g = self.ghs()
        g.update({"rollups": [[RD_OK], [RD_OK], self.OK]})  # a rerun's first polls still lack "test"
        (self.S / "gh.json").write_text(json.dumps(g))
        self.land(expect=0)
        st = self.ghs()
        self.assertEqual(st["merges"], 1)
        self.assertEqual(st["rollups"], [self.OK])  # the rerun polled past both review-only rollups instead of merging on the first
        cp = json.loads(next(self.S.glob("**/checkpoint.json")).read_text())
        self.assertIsNone(cp.get("expected_checks"))


class Friction(Base):
    """aq-land delivery-friction fixes of 2026-11-14 (issues-backlog, AQ-LAND)."""

    def raw(self, *args, cwd=None):
        r = subprocess.run([sys.executable, str(TOOL), "--worktree", str(self.wd), *args], capture_output=True, text=True,
                           env=self.env, cwd=cwd, timeout=120)
        self.assertNotIn("Traceback", r.stderr)
        return r

    def test_resume_without_body_file_uses_the_saved_body(self):
        self.gh_state({"required": ["never-reported"]})
        self.land(expect=1)  # PR created, reviewed, receipted; stops at checks
        r = self.raw("--title", "t")
        self.assertNotIn("IsADirectoryError", r.stderr)
        self.assertIn("STOP checks", r.stderr)  # got past the body stage
        self.assertIn("### Review record", self.pr_body())

    def test_no_body_file_and_no_saved_body_stops_before_review(self):
        r = self.raw("--title", "t")
        self.assertIn("no --body-file and no saved body", self.stop_line(r))
        self.assertEqual(self.calls("gemini"), [])

    def test_relative_body_commit_msg_and_criteria_paths_survive_the_chdir(self):
        (self.S / "msg.txt").write_text("feat: rel\n")
        (self.S / "crit.txt").write_text("CRITERIA-MARK\n")
        self.change("scripts/bar.py", "print(2)\n", commit=False)
        r = self.raw("--title", "t", "--body-file", "body.md", "--commit-msg-file", "msg.txt", "--criteria-file", "crit.txt", cwd=self.S)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CRITERIA-MARK", (self.S / "prompt-gemini.txt").read_text())
        self.assertEqual(self.g("log", "-1", "--format=%s"), "feat: rel")

    def test_receipt_is_published_before_the_pr_body_is_edited(self):
        self.gh_state({"required": ["never-reported"]})
        self.land(expect=1)
        self.change("scripts/baz.py", "print(3)\n")
        (self.S / "body.md").write_text(BODY.replace("- scope", "- scope v2"))
        self.land(expect=1)
        calls = self.ghs()["calls"]
        edit = calls.index("pr edit 77")
        self.assertEqual([i for i, c in enumerate(calls) if c == "RECEIPT publish"][-1] < edit, True, calls)
        self.assertEqual(len(self.published()), 2)

    def test_bad_body_format_stops_in_preflight_before_any_review_or_push(self):
        (self.S / "body.md").write_text(BODY.replace("## Details", "## Summary"))
        r = self.land(expect=1)
        line = self.stop_line(r)
        self.assertIn("preflight", line)
        self.assertIn("## Details", line)
        self.assertEqual(self.calls("gemini"), [])
        self.assertEqual(self.ghs()["prs"], [])

    def test_static_gates_failure_stops_in_preflight_and_a_pass_proceeds(self):
        gate = self.S / "static-gates.sh"
        gate.write_text('#!/bin/sh\necho "FAIL: no evidence file"\nexit 1\n')
        gate.chmod(0o755)
        self.env["AQ_LAND_STATIC_GATES"] = str(gate)
        line = self.stop_line(self.land(expect=1))
        self.assertIn("preflight", line)
        self.assertIn("no evidence file", line)
        self.assertEqual(self.calls("gemini"), [])
        gate.write_text("#!/bin/sh\nexit 0\n")
        self.land(expect=0)


def _flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from _flatten(t)
        else:
            yield t


def _run_sharded():
    """Each test owns a private tempdir/bare origin and shares nothing, so the ~80 subprocess-heavy tests run in parallel
    shards; serially they exceed the 120 s per-file CI limit (run-test-group.py). AQ_LAND_TEST_JOBS=1 runs serially."""
    shard = os.environ.get("AQ_LAND_TEST_SHARD")
    if shard:
        k, n = map(int, shard.split("/"))
        tests = sorted(_flatten(unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"])), key=lambda t: t.id())
        res = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests[k::n]))
        sys.exit(0 if res.wasSuccessful() else 1)
    jobs = int(os.environ.get("AQ_LAND_TEST_JOBS", "0")) or min(8, os.cpu_count() or 1)
    if jobs <= 1 or len(sys.argv) > 1:  # selectors and unittest flags need plain unittest semantics
        unittest.main()
    procs = [subprocess.Popen([sys.executable, __file__], env={**os.environ, "AQ_LAND_TEST_SHARD": f"{k}/{jobs}"}) for k in range(jobs)]
    sys.exit(1 if any(p.wait() for p in procs) else 0)


if __name__ == "__main__":
    _run_sharded()
