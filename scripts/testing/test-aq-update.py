#!/run/current-system/sw/bin/python3
"""Tests for scripts/maintenance/aq-update.

Local bare repo as origin, a clone as the "primary checkout", and stubs for nix, nixos-version,
aq-land, aq-deploy-current and the MCP baseline script. Every stub appends one token to a call
log; mutating stubs also touch a sentinel. No network, sudo, systemctl or real deploy.
Kill tests make a stub (or the post-merge hook) SIGKILL aq-update mid-stage, then --resume.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/maintenance/aq-update"
PREPUSH = REPO_ROOT / "scripts/governance/pre-push-nix-eval.sh"
REAL_LAND = os.environ.get("AQ_LAND_REAL") or str(REPO_ROOT / "scripts/ai/aq-land")
TRAIL = ".agent/memory/issues-backlog.md"
STATE = ".agent/collaboration/rsi-incidents.json"

KILL_PARENT = 'kill -9 "$PPID"'
STUBS = {
    "nix": """#!/bin/sh
shift 2
sub="$1 $2"
echo "$sub" >> "$STUB_DIR/calls.log"
[ "$NIX_KILL" = "$sub" ] && kill -9 "$PPID"
case "$sub" in
  "flake update")
    name="$3"
    case " $NIX_FAIL_INPUTS " in *" $name "*) [ -n "$name" ] && { echo "error: cannot lock $name" >&2; exit 1; } ;; esac
    [ -z "$name" ] && [ -n "$NIX_FAIL_INPUTS" ] && { echo "error: update failed" >&2; exit 1; }
    touch "$STUB_DIR/mutated"
    [ -z "$NIX_NOCHANGE" ] && python3 "$STUB_DIR/bump.py" "$name" ;;
  "flake check") [ -n "$NIX_CHECK_MOVE_MAIN" ] && sh "$STUB_DIR/move_main.sh" ;;
esac
exit 0
""",
    "nixos-version": """#!/bin/sh
echo version >> "$STUB_DIR/calls.log"
[ -n "$VERSION_KILL" ] && [ -e "$STUB_DIR/baseline.done" ] && kill -9 "$PPID"
cat "$STUB_DIR/running_rev"
""",
    "aq-land": """#!/bin/sh
echo land >> "$STUB_DIR/calls.log"; touch "$STUB_DIR/mutated"
exec python3 "$STUB_DIR/land_wrapper.py" "$@"
""",
    "sudo": """#!/bin/sh
echo "sudo $*" >> "$STUB_DIR/sudo.log"
[ -n "$SUDO_FAIL" ] && exit 1
exec "$@"
""",
    "land_wrapper.py": """import importlib.machinery, importlib.util, os, subprocess, sys, types
real = os.environ.get("AQ_LAND_REAL", "")


def finish(worktree):
    if subprocess.run(["git", "-C", worktree, "push", "-q", "origin", "HEAD:main"]).returncode:
        sys.exit(1)
    if os.environ.get("LAND_MOVE_MAIN"):
        subprocess.run(["sh", os.environ["STUB_DIR"] + "/move_main.sh"])
    if os.environ.get("LAND_KILL"):
        os.kill(os.getppid(), 9)
    sys.exit(0)


if not os.path.exists(real):
    finish(os.getcwd())
loader = importlib.machinery.SourceFileLoader("real_land", real)
mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("real_land", loader))
loader.exec_module(mod)


class Fake:  # the REAL argparse in mod.main() parses argv; Land (the network/review part) is replaced
    def __init__(self, a):
        self.a = a

    def go(self):
        a = self.a
        assert os.path.isdir(a.worktree) and a.title, (a.worktree, a.title)
        for f in (a.body_file, a.commit_msg_file, a.criteria_file):
            assert f and os.path.isfile(f) and f.startswith(os.environ["AQ_UPDATE_STATE_DIR"]), f
        assert "Co-Authored-By:" in open(a.commit_msg_file).read()
        rec = dict(disposition="PASS", subject="s", head="h" * 40, reviewer="r", notes=[], run_id="x", lane="l")
        body = REAL.body(types.SimpleNamespace(a=a), rec)  # real body(): needs "## What", strips placeholders
        assert body.index("### Review record") < body.index("## What"), body
        assert body.rstrip().endswith("\U0001F916 Generated with [Claude Code](https://claude.com/claude-code)"), body[-120:]
        assert body.count("Review-Disposition:") == 1 and "Reviewed-by: pending" not in body, body
        open(os.environ["STUB_DIR"] + "/land-args.json", "w").write(__import__("json").dumps(vars(a)))
        finish(a.worktree)


REAL = mod.Land\nmod.Land = Fake
sys.exit(mod.main())
""",
    "aq-deploy-current": """#!/bin/sh
echo "deploy" >> "$STUB_DIR/calls.log"; touch "$STUB_DIR/mutated"
echo "deploy-head $(git rev-parse HEAD)" >> "$STUB_DIR/heads.log"
[ "$DEPLOY_KILL" = before ] && { kill -9 "$PPID"; exit 1; }
git rev-parse HEAD > "$STUB_DIR/running_rev"
[ "$DEPLOY_KILL" = after ] && kill -9 "$PPID"
exit 0
""",
    "baseline": """#!/bin/sh
echo baseline >> "$STUB_DIR/calls.log"; touch "$STUB_DIR/mutated"
[ -n "$BASELINE_KILL" ] && { kill -9 "$PPID"; exit 1; }
touch "$STUB_DIR/baseline.done"
""",
    "bump.py": """import json, sys
name = sys.argv[1] if len(sys.argv) > 1 else ""
import os
lock = json.load(open("flake.lock"))
for k, n in lock["nodes"].items():
    if k != "root" and name in ("", k):
        n["locked"]["rev"] = n["locked"]["rev"] + "x"
if os.environ.get("NIX_UNLOCK_NODE"):
    lock["nodes"][os.environ["NIX_UNLOCK_NODE"]].pop("locked")
json.dump(lock, open("flake.lock", "w"), indent=1)
""",
    "move_main.sh": """#!/bin/sh
cd "$STUB_DIR/other" && git pull -q origin main && echo "moved $(date +%s%N)" >> docs/moved.md \
  && git add -A && git commit -q -m moved && git push -q origin HEAD:main
""",
}


def sh(*cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def git(cwd, *a):
    p = sh("git", "-C", str(cwd), *a)
    assert p.returncode == 0, (a, p.stderr)
    return p.stdout.strip()


class Fx:
    def __init__(self, tmp):
        self.t = Path(tmp)
        self.stub = self.t / "stub"
        self.stub.mkdir()
        self.origin = self.t / "origin.git"
        self.repo = self.t / "main"
        self.state = self.t / "state"
        self.worktrees = self.repo / ".agents/delegation/worktrees"
        sh("git", "init", "-q", "--bare", "-b", "main", str(self.origin))
        seed = self.t / "seed"
        sh("git", "clone", "-q", str(self.origin), str(seed))
        lock = {"nodes": {"root": {"inputs": {"nixpkgs": "nixpkgs", "foo": "foo"}},
                          "nixpkgs": {"locked": {"rev": "a"}}, "foo": {"locked": {"rev": "b"}}}, "root": "root", "version": 7}
        files = {"flake.nix": "{}\n", "flake.lock": json.dumps(lock, indent=1), "nix/mod.nix": "1\n",
                 "docs/a.md": "a\n", "docs/moved.md": "", TRAIL: "base\n", STATE: '{"n":0}\n',
                 ".agent/collaboration/AGENT-CATCHUP-QUEUE.md": "q\n", "ai-stack/mcp-servers/x.py": "x=1\n",
                 ".agents/plans/frontier-evidence-intake/BACKLOG.jsonl": "b\n",
                 ".agents/plans/frontier-evidence-intake/scan-state.json": "{}\n",
                 "scripts/governance/pre-push-nix-eval.sh": PREPUSH.read_text()}
        for f, c in files.items():
            (seed / f).parent.mkdir(parents=True, exist_ok=True)
            (seed / f).write_text(c)
        for a in (["config", "user.name", "t"], ["config", "user.email", "t@t"]):
            git(seed, *a)
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "c1")
        git(seed, "push", "-q", "origin", "HEAD:main")
        self.c1 = git(seed, "rev-parse", "HEAD")
        for name in ("main", "other"):
            dst = self.repo if name == "main" else self.stub / "other"
            sh("git", "clone", "-q", str(self.origin), str(dst))
            git(dst, "config", "user.name", "t")
            git(dst, "config", "user.email", "t@t")
        for n, body in STUBS.items():
            p = self.stub / n
            p.write_text(body)
            p.chmod(0o755)
        (self.stub / "running_rev").write_text(self.c1)
        hook = self.repo / ".git/hooks/post-merge"
        hook.write_text('#!/bin/sh\n[ -n "$SYNC_MOVE_MAIN" ] && sh "$STUB_DIR/move_main.sh"\n'
                        '[ -n "$SYNC_KILL" ] && kill -9 "$(awk \'{print $4}\' /proc/$PPID/stat)"\nexit 0\n')
        hook.chmod(0o755)
        self.env = {**os.environ, "STUB_DIR": str(self.stub), "PATH": f"{self.stub}:{os.environ['PATH']}",
                    "AQ_UPDATE_REPO": str(self.repo), "AQ_UPDATE_STATE_DIR": str(self.state),
                    "AQ_UPDATE_LAND": str(self.stub / "aq-land"), "AQ_UPDATE_DEPLOY": str(self.stub / "aq-deploy-current"),
                    "AQ_UPDATE_BASELINE": str(self.stub / "baseline"), "AQ_LAND_REAL": REAL_LAND, "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for k in ("NIX_FAIL_INPUTS", "NIX_UNLOCK_NODE", "NIX_KILL", "XDG_STATE_HOME"):
            self.env.pop(k, None)

    def advance(self, path="docs/a.md", text="more\n"):
        o = self.stub / "other"
        git(o, "pull", "-q", "origin", "main")
        f = o / path
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a") as fh:
            fh.write(text)
        git(o, "add", "-A")
        git(o, "commit", "-q", "-m", f"touch {path}")
        git(o, "push", "-q", "origin", "HEAD:main")
        return git(o, "rev-parse", "HEAD")

    def run(self, *args, **env):
        e = {**self.env, **env}
        p = subprocess.run([sys.executable, str(SCRIPT), *args], env=e, text=True, capture_output=True, cwd=self.repo)
        return p

    def calls(self):
        f = self.stub / "calls.log"
        return f.read_text().split("\n")[:-1] if f.exists() else []

    def origin_head(self):
        return git(self.origin, "rev-parse", "main")

    def ledger(self):
        f = self.state / "ledger.jsonl"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def snapshot(self):
        """Everything dry-run must not touch: refs, HEAD, worktrees, status, flake.lock, every .git file but objects."""
        h = hashlib.sha256()
        for p in sorted((self.repo / ".git").rglob("*")):
            if p.is_file() and "objects" not in p.relative_to(self.repo / ".git").parts[:1]:
                h.update(str(p).encode() + p.read_bytes())
        return (git(self.repo, "for-each-ref"), git(self.repo, "rev-parse", "HEAD"), git(self.repo, "worktree", "list"),
                git(self.repo, "status", "--porcelain", "--ignored"), (self.repo / "flake.lock").read_bytes(),
                h.hexdigest(), self.state.exists(), (self.stub / "mutated").exists(), self.origin_head())


class Skip(Exception):
    pass


def check(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


def with_fx(fn):
    def wrapper():
        with tempfile.TemporaryDirectory() as d:
            fn(Fx(d))
    wrapper.__name__ = fn.__name__
    return wrapper


def one_line_fail(p, stage, *needles):
    err = p.stderr.strip()
    check(p.returncode == 1, (p.returncode, p.stdout, p.stderr))
    check(len(err.splitlines()) == 1 and err.startswith(f"aq-update: FAIL {stage}:"), err)
    for n in needles:
        check(n in err, (n, err))


@with_fx
def t_no_delta_syncs_without_flake_update_or_deploy(fx):
    new = fx.advance("docs/a.md")
    p = fx.run()
    check(p.returncode == 0, p.stderr)
    check("no rebuild needed" in p.stdout, p.stdout)
    check(git(fx.repo, "rev-parse", "HEAD") == new, "checkout not synced")
    check(not any(c in fx.calls() for c in ("flake update", "deploy", "land", "baseline")), fx.calls())
    check(not (fx.stub / "mutated").exists(), "mutating stub ran")
    check(fx.ledger()[-1]["event"] == "finished" and fx.ledger()[-1]["rebuild"] is False, fx.ledger())


@with_fx
def t_delta_runs_stages_in_order(fx):
    new = fx.advance("nix/mod.nix", "2\n")
    p = fx.run()
    check(p.returncode == 0, p.stderr + p.stdout)
    seq = [c for c in fx.calls() if c in ("flake update", "flake check", "land", "deploy", "baseline", "version")]
    firsts = [seq.index(x) for x in ("flake update", "flake check", "land", "deploy", "baseline")]
    check(firsts == sorted(firsts) and seq.index("version", seq.index("baseline")) > seq.index("baseline"), seq)
    check(fx.calls().count("flake check") == 2 and "flake show" in fx.calls() and "eval" in "".join(fx.calls()), fx.calls())
    head = git(fx.repo, "rev-parse", "HEAD")
    check(head == fx.origin_head() and head != new, "lock was not landed and synced")
    check((fx.stub / "heads.log").read_text().strip() == f"deploy-head {head}", "deployed a revision other than the synced one")
    check(json.loads(git(fx.repo, "show", "HEAD:flake.lock"))["nodes"]["foo"]["locked"]["rev"] == "bx", "lock not refreshed")
    check(fx.ledger()[-1]["event"] == "finished" and fx.ledger()[-1]["rebuild"] is True, fx.ledger())


@with_fx
def t_unlockable_input_blocks_with_name(fx):
    fx.advance("nix/mod.nix", "2\n")
    p = fx.run(NIX_FAIL_INPUTS="foo")
    one_line_fail(p, "refresh", "foo")
    check("nixpkgs" not in p.stderr, p.stderr)
    check("land" not in fx.calls() and "deploy" not in fx.calls(), fx.calls())


@with_fx
def t_unlocked_node_blocks_with_name(fx):
    fx.advance("nix/mod.nix", "2\n")
    one_line_fail(fx.run(NIX_UNLOCK_NODE="foo"), "refresh", "unlocked", "foo")
    check("land" not in fx.calls() and "deploy" not in fx.calls(), fx.calls())


@with_fx
def t_missing_aq_land_fails_before_any_nix_work(fx):
    fx.advance("nix/mod.nix", "2\n")
    one_line_fail(fx.run(AQ_UPDATE_LAND=str(fx.t / "nope")), "land", "aq-land not found")
    check(fx.calls() == ["version"], fx.calls())


@with_fx
def t_main_moves_after_verify_no_lock_change(fx):
    fx.advance("nix/mod.nix", "2\n")
    p = fx.run(NIX_NOCHANGE="1", NIX_CHECK_MOVE_MAIN="1")
    one_line_fail(p, "land", "moved")
    check("deploy" not in fx.calls(), fx.calls())


@with_fx
def t_main_moves_during_landing(fx):
    fx.advance("nix/mod.nix", "2\n")
    one_line_fail(fx.run(LAND_MOVE_MAIN="1"), "land", "main moved")
    check("deploy" not in fx.calls(), fx.calls())


@with_fx
def t_main_moves_between_sync_and_deploy(fx):
    fx.advance("nix/mod.nix", "2\n")
    p = fx.run(SYNC_MOVE_MAIN="1")
    one_line_fail(p, "deploy", "moved")
    check("deploy" not in fx.calls() and not (fx.stub / "heads.log").exists(), fx.calls())


@with_fx
def t_dry_run_changes_nothing(fx):
    for path in ("docs/a.md", "nix/mod.nix"):
        fx.advance(path, "z\n")
        (fx.repo / TRAIL).write_text("base\nlocal\n")  # allowed dirt
        before = fx.snapshot()
        p = fx.run("--dry-run")
        check(p.returncode == 0, p.stderr)
        check("dry-run" in p.stdout, p.stdout)
        check(fx.snapshot() == before, f"dry-run changed state for {path}")
        check(set(fx.calls()) == {"version"}, fx.calls())  # read-only detection only
        git(fx.repo, "checkout", "--", TRAIL)


@with_fx
def t_dry_run_still_fails_on_missing_aq_land(fx):
    fx.advance("nix/mod.nix", "2\n")
    one_line_fail(fx.run("--dry-run", AQ_UPDATE_LAND=str(fx.t / "nope")), "land")


KILLS = {  # name -> (env, stage call counts after kill + resume)
    "update": ({"NIX_KILL": "flake update"}, {"flake update": 2, "land": 1, "deploy": 1, "baseline": 1}),
    "check": ({"NIX_KILL": "flake check"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 1}),
    "land": ({"LAND_KILL": "1"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 1}),
    "sync": ({"SYNC_KILL": "1"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 1}),
    "deploy_before": ({"DEPLOY_KILL": "before"}, {"flake update": 1, "land": 1, "deploy": 2, "baseline": 1}),
    "deploy_after": ({"DEPLOY_KILL": "after"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 1}),
    "baseline": ({"BASELINE_KILL": "1"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 2}),
    "validate": ({"VERSION_KILL": "1"}, {"flake update": 1, "land": 1, "deploy": 1, "baseline": 1}),
}


def kill_case(name):
    env, want = KILLS[name]

    @with_fx
    def t(fx):
        fx.advance("nix/mod.nix", "2\n")
        (fx.repo / TRAIL).write_text("base\nlocal-append\n")
        (fx.repo / STATE).write_text('{"n":99}\n')
        p = fx.run(**env)
        check(p.returncode != 0, f"{name}: expected a killed run, got rc=0")
        check(not any(e["event"] == "finished" for e in fx.ledger()), "killed run recorded as finished")
        r = fx.run("--resume")
        check(r.returncode == 0, f"{name}: resume failed: {r.stderr}")
        calls = fx.calls()
        for stage, n in want.items():
            check(calls.count(stage) == n, f"{name}: {stage} ran {calls.count(stage)}x, want {n}: {calls}")
        head = git(fx.repo, "rev-parse", "HEAD")
        check(head == fx.origin_head() and (fx.stub / "running_rev").read_text().strip() == head, "end state not at verified main")
        check("local-append" in (fx.repo / TRAIL).read_text(), "trail append lost across resume")
        check((fx.repo / STATE).read_text() == '{"n":99}\n', "runtime state not restored")
        check(fx.ledger()[-1]["event"] == "finished", fx.ledger()[-1])
        check("nothing to resume" in fx.run("--resume").stdout, "finished run still resumable")

    t.__name__ = f"t_resume_after_kill_in_{name}"
    return t


for _n in KILLS:
    globals()[f"t_resume_after_kill_in_{_n}"] = kill_case(_n)


@with_fx
def t_dirty_checkout_refused(fx):
    fx.advance("docs/a.md")
    (fx.repo / "docs/a.md").write_text("dirty\n")
    one_line_fail(fx.run(), "preflight", "docs/a.md")
    check(set(fx.calls()) <= {"version"} and git(fx.repo, "rev-parse", "HEAD") == fx.c1, "refused run still changed something")


@with_fx
def t_trail_and_state_preserved_across_sync(fx):
    o = fx.stub / "other"
    git(o, "pull", "-q", "origin", "main")
    (o / TRAIL).write_text("base\nfrom-origin\n")
    (o / STATE).write_text('{"n":1}\n')
    git(o, "add", "-A")
    git(o, "commit", "-q", "-m", "trail")
    git(o, "push", "-q", "origin", "HEAD:main")
    (fx.repo / TRAIL).write_text("base\nlocal-append\n")
    (fx.repo / STATE).write_text('{"n":42}\n')
    p = fx.run()
    check(p.returncode == 0, p.stderr)
    text = (fx.repo / TRAIL).read_text()
    check("from-origin" in text and "local-append" in text, text)
    check((fx.repo / STATE).read_text() == '{"n":42}\n', "runtime state not restored")
    check(git(fx.repo, "rev-parse", "HEAD") == fx.origin_head(), "not synced")


@with_fx
def t_aq_land_call_matches_real_cli(fx):
    if not os.path.isfile(REAL_LAND):
        raise Skip(f"{REAL_LAND} absent (aq-land is on sibling slice S3 until it merges); set AQ_LAND_REAL to test it")
    fx.advance("nix/mod.nix", "2\n")
    p = fx.run()  # the stub aq-land runs the REAL argparse and the real Land.body() on what aq-update generated
    check(p.returncode == 0, p.stderr + p.stdout)
    a = json.loads((fx.stub / "land-args.json").read_text())
    check(a["title"].startswith("chore(flake): refresh all inputs") and Path(a["worktree"]).parent == fx.worktrees, a)
    check(str(fx.state) in a["body_file"] and str(fx.state) in a["criteria_file"], a)


@with_fx
def t_baseline_runs_through_sudo(fx):
    fx.advance("nix/mod.nix", "2\n")
    check(fx.run().returncode == 0, "run failed")
    check((fx.stub / "sudo.log").read_text().strip() == f"sudo {fx.stub / 'baseline'}", (fx.stub / "sudo.log").read_text())


@with_fx
def t_baseline_refresh_failure_is_reported_recorded_and_resumable(fx):
    fx.advance("nix/mod.nix", "2\n")
    p = fx.run(SUDO_FAIL="1")
    one_line_fail(p, "baseline", f"sudo {fx.stub / 'baseline'}", "aq-update --resume")
    last = fx.ledger()[-1]
    check(last["event"] == "fail" and last["stage"] == "baseline" and "NOT refreshed" in last["reason"], last)
    check(not any(e["event"] == "finished" for e in fx.ledger()), "failed baseline recorded as finished")
    r = fx.run("--resume")
    check(r.returncode == 0, r.stderr)
    check(fx.calls().count("deploy") == 1 and fx.calls().count("baseline") == 1, fx.calls())
    check(fx.ledger()[-1]["event"] == "finished", fx.ledger()[-1])


@with_fx
def t_unknown_deployed_revision_fails(fx):
    fx.advance("docs/a.md")
    (fx.stub / "running_rev").write_text("")
    one_line_fail(fx.run(), "detect", "deployed revision unknown")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Skip as exc:
            print(f"SKIP {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed (SKIP counts as passed; see SKIP lines)")
    sys.exit(1 if failed else 0)
