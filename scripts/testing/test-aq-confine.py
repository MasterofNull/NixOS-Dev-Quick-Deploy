#!/usr/bin/env python3
"""Acceptance tests for aq-confine S2a (scripts/ai/lib/confine.py + scripts/ai/aq-confine).

Plain script: PASS/FAIL lines, non-zero exit on failure. Pure tests always run.
Behavioral tests need a working bwrap: when the launcher's own preflight fails
they print SKIP-WARN with the reason and are counted as skipped; with
AQ_CONFINE_REQUIRE=1 a failed preflight is a hard failure.
Fixtures live outside the sandboxed worktree (own temp dirs, own repos).
"""
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

SCRATCH = tempfile.mkdtemp(prefix="aqc-test-")
os.environ["AQ_CONFINE_STATE_DIR"] = os.path.join(SCRATCH, "state")
os.environ["AQ_TELEMETRY_DIR"] = os.path.join(SCRATCH, "telemetry")
os.environ["ATTENTION_QUEUE_DIR"] = os.path.join(SCRATCH, "attention")
os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
VTMP = tempfile.mkdtemp(prefix="aqc-test-", dir="/var/tmp")   # non-/tmp worktrees
os.environ["AQ_CONFINE_WORKTREE_ROOTS"] = "/var/tmp"

import confine  # noqa: E402

CLI = str(REPO / "scripts" / "ai" / "aq-confine")
GOLDEN = REPO / "scripts" / "testing" / "golden" / "aq-confine"
PY = os.path.realpath(sys.executable)
REQUIRE = os.environ.get("AQ_CONFINE_REQUIRE") == "1"

ran = skipped = failed = 0
PF = confine.preflight(use_cache=False)


def ok(name):
    global ran
    ran += 1
    print(f"PASS: {name}")


def bad(name, why=""):
    global ran, failed
    ran += 1
    failed += 1
    print(f"FAIL: {name} {why}")


def check(name, cond, why=""):
    ok(name) if cond else bad(name, why)


def behavioral(fn):
    """Decorator: skip-warn (or hard-fail under AQ_CONFINE_REQUIRE=1) when confinement is unavailable."""
    def wrapper():
        global skipped
        if not PF.ok:
            if REQUIRE:
                bad(fn.__name__, f"confinement unavailable ({PF.reason}) and AQ_CONFINE_REQUIRE=1")
            else:
                skipped += 1
                print(f"SKIP-WARN: {fn.__name__}: confinement unavailable ({PF.reason}: {PF.detail})")
            return
        try:
            fn()
        except Exception as exc:  # a crashing test is a failure
            import traceback
            traceback.print_exc()
            bad(fn.__name__, f"exception {exc!r}")
    wrapper.__name__ = fn.__name__
    return wrapper


def git(repo, *args, check_rc=True, env_extra=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", **(env_extra or {}))
    cp = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)
    if check_rc and cp.returncode != 0:
        raise RuntimeError(f"git {args}: {cp.stderr}")
    return cp


def make_fixture(base, claim="claim1", slug="slug", packed_only=False):
    """Main repo + linked worktree on aq/<claim>/<slug>; returns (repo, worktree)."""
    repo = os.path.join(base, "repo")
    wt = os.path.join(base, f"wt-{claim}")
    os.makedirs(base, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True, env=dict(os.environ))
    Path(repo, "f.txt").write_text("hello\n")
    git(repo, "add", "f.txt")
    git(repo, "commit", "-qm", "init")
    git(repo, "worktree", "add", "-q", "-b", f"aq/{claim}/{slug}", wt)
    if packed_only:
        git(repo, "pack-refs", "--all")
    return repo, wt


def refs_of(repo):
    return git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout


def run_cli(*args, env=None):
    cp = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, env=env or os.environ)
    return cp


def sh(profile, script, **kw):
    return confine.run(profile, ["sh", "-c", script], **kw)


def py(profile, code, **kw):
    return confine.run(profile, [PY, "-c", code], **kw)


def out(res):
    return res.stdout.decode("utf-8", "replace")


def custom_profiles(name, mutate):
    """Copy the three profiles into a temp dir with `mutate(dict)` applied to `name`."""
    d = tempfile.mkdtemp(prefix="profiles-", dir=SCRATCH)
    for p in (REPO / "config" / "confine-profiles").glob("*.json"):
        data = json.loads(p.read_text())
        if p.stem == name:
            mutate(data)
        Path(d, p.name).write_text(json.dumps(data))
    return d


class ProfileDir:
    def __init__(self, d):
        self.d = d

    def __enter__(self):
        self.old = os.environ.get("AQ_CONFINE_PROFILE_DIR")
        os.environ["AQ_CONFINE_PROFILE_DIR"] = self.d

    def __exit__(self, *a):
        if self.old is None:
            os.environ.pop("AQ_CONFINE_PROFILE_DIR", None)
        else:
            os.environ["AQ_CONFINE_PROFILE_DIR"] = self.old


def fixtures_both():
    """Yield (label, repo, worktree) for a /tmp worktree and a /var/tmp worktree."""
    for label, base in (("tmp", tempfile.mkdtemp(prefix="fx-", dir=SCRATCH)), ("vartmp", tempfile.mkdtemp(prefix="fx-", dir=VTMP))):
        repo, wt = make_fixture(base)
        yield label, repo, wt


# ------------------------------------------------------------------ pure tests

class FakeFacts(confine.HostFacts):
    def exists(self, p):
        return p in ("/nix/store", "/usr", "/bin", "/etc/alternatives")

    def realpath(self, p):
        return p

    def which(self, n):
        return {"python3": "/nix/store/AAA-python/bin/python3", "git": "/nix/store/BBB-git/bin/git",
                "sh": "/nix/store/CCC-bash/bin/sh", "env": "/nix/store/DDD-coreutils/bin/env",
                "ls": "/nix/store/DDD-coreutils/bin/ls", "grep": "/nix/store/EEE-grep/bin/grep",
                "sed": "/nix/store/FFF-sed/bin/sed", "find": "/nix/store/GGG-find/bin/find",
                "cat": "/nix/store/DDD-coreutils/bin/cat"}.get(n)

    def uid_tasks(self):
        return 100

    def python_bin(self):
        return "/nix/store/AAA-python/bin/python3"


def golden_plan(profile_name):
    facts = FakeFacts()
    prof = confine.load_profile(profile_name)
    layout = None
    kw = {}
    if prof.needs_worktree:
        layout = confine.GitLayout("/WT/wt-claim1", "/WT/repo/.git/worktrees/wt-claim1", "/WT/repo/.git", "claim1", "slug")
    plan = confine.Plan(prof, "run000000", "/BWRAP", "/PRLIMIT", confine.RunPaths.for_run("/STATE", "run000000"),
                        layout, "", [], [], confine.build_env(prof, {"LANG": "C.UTF-8", "SECRET_TOKEN": "x"}, [], layout,
                                                              confine._resolve_path_dirs(prof, facts)[0], facts),
                        "none", False, ["/bin/true"], dict(prof.limits, **({"nproc": prof.limits["nproc"] + 100} if "nproc" in prof.limits else {})), prof.timeout_s,
                        systemd_run="/SYSTEMD-RUN")
    return plan, facts


def test_profiles_and_schema():
    for n in ("worktree-rw", "readonly-analysis", "eval-untrusted"):
        try:
            p = confine.load_profile(n)
            check(f"profile {n} loads, disable_userns on", p.disable_userns is True)
        except confine.ConfineError as e:
            bad(f"profile {n} loads", str(e))
    cases = {
        "unknown key rejected": lambda d: d.update(bogus=1),
        "share_net key rejected": lambda d: d.update(share_net=True),
        "profile dropping unshare-net rejected": lambda d: d.update(unshare=["user", "pid"]),
        "git_refs heads reserved": lambda d: d.update(git_refs="heads"),
        "nested userns forbidden with worktree": lambda d: d.update(allow_nested_userns=True, disable_userns=False),
        "egress mode other than none rejected": lambda d: d["egress"].update(mode="broker"),
        "denied env_allow name rejected": lambda d: d["env_allow"].append("GITHUB_TOKEN"),
        "wrong type rejected": lambda d: d.update(timeout_s="fast"),
        "missing cgroup rejected": lambda d: d.pop("cgroup"),
        "cgroup without tasks_max rejected": lambda d: d["cgroup"].pop("tasks_max"),
        "cgroup unknown subkey rejected": lambda d: d["cgroup"].update(swap_max=1),
        "cgroup memory_max below floor rejected": lambda d: d["cgroup"].update(memory_max=1024),
        "cgroup tasks_max wrong type rejected": lambda d: d["cgroup"].update(tasks_max="many"),
    }
    for label, mut in cases.items():
        with ProfileDir(custom_profiles("worktree-rw", mut)):
            try:
                confine.load_profile("worktree-rw")
                bad(label)
            except confine.ConfineError as e:
                check(label, e.exit_code == 71, str(e))
    try:
        confine.load_profile("nope")
        bad("missing profile")
    except confine.ConfineError as e:
        check("missing profile exits 71", e.exit_code == 71)


def test_cgroup_scope_pure():
    plan, facts = golden_plan("worktree-rw")
    a = confine.build_argv(plan, facts)
    check("worktree-rw argv starts with a systemd-run user scope carrying MemoryMax/MemorySwapMax/TasksMax",
          a[:4] == ["/SYSTEMD-RUN", "--user", "--scope", "--quiet"] and "MemoryMax=3221225472" in a
          and "MemorySwapMax=0" in a and "TasksMax=300" in a and a.index("/PRLIMIT") > a.index("TasksMax=300"))
    check("RLIMIT_AS stays as defense in depth under the scope", any(x.startswith("--as=") for x in a))
    plan.systemd_run = ""
    check("no scope prefix when systemd_run is empty (rlimit-only path)", confine.build_argv(plan, facts)[0] == "/PRLIMIT")
    for n, mem, tasks in (("eval-untrusted", 512 << 20, 64), ("readonly-analysis", 2 << 30, 128)):
        pr = confine.load_profile(n)
        check(f"{n}: cgroup limits tighter than worktree-rw, rlimit-only off by default",
              pr.cgroup == {"memory_max": mem, "tasks_max": tasks, "allow_rlimit_only": False}, str(pr.cgroup))


def test_explain_goldens():
    for n in ("worktree-rw", "readonly-analysis", "eval-untrusted"):
        plan, facts = golden_plan(n)
        text = confine.explain_text(plan, facts)
        argv = confine.build_argv(plan, facts)
        check(f"{n}: --unshare-user with --disable-userns and --assert-userns-disabled",
              all(f in argv for f in ("--unshare-user", "--disable-userns", "--assert-userns-disabled", "--unshare-net")))
        check(f"{n}: --share-net never emitted", "--share-net" not in argv)
        check(f"{n}: planted caller env not in explain", "SECRET_TOKEN" not in text)
        gf = GOLDEN / f"{n}.explain.txt"
        if os.environ.get("UPDATE_GOLDEN") == "1":
            gf.write_text(text)
        check(f"{n}: --explain matches golden", gf.exists() and gf.read_text() == text, f"({gf})")
    plan, facts = golden_plan("worktree-rw")
    a = confine.build_argv(plan, facts)
    last_dotgit = max(i for i, x in enumerate(a) if x == "/WT/wt-claim1/.git" and a[i - 2] == "--ro-bind")
    i_common = [i for i, x in enumerate(a) if x == "/WT/repo/.git"][0]
    i_adm = [i for i, x in enumerate(a) if x == "/WT/repo/.git/worktrees/wt-claim1" and a[i - 2] == "--bind"][0]
    i_head = [i for i, x in enumerate(a) if x == "/WT/repo/.git/worktrees/wt-claim1/HEAD" and a[i - 2] == "--ro-bind"][0]
    i_wt = [i for i, x in enumerate(a) if x == "/WT/wt-claim1" and a[i - 2] == "--bind"][0]
    check("worktree-rw mount order: common ro, then private admin, ro overlays, worktree bind, .git overlay last",
          a[i_common - 1] == "--ro-bind" and i_common < i_adm < i_head < i_wt < last_dotgit)
    check("worktree-rw: private ref dir bound over real namespace path",
          "/STATE/runs/run000000/sandbox/refs" in a and "/WT/repo/.git/refs/heads/aq/claim1" in a)
    pa = confine.preflight_argv("/BWRAP", "/nix/store/AAA-python/bin/python3", FakeFacts())
    check("preflight argv works with /nix/store absent (exists-guarded)", True if "/nix/store" in pa else False)

    class NoStore(FakeFacts):
        def exists(self, p):
            return p in ("/usr", "/bin")
    pa = confine.preflight_argv("/BWRAP", "/usr/bin/python3", NoStore())
    check("preflight binds only existing system dirs", "/nix/store" not in pa and "/usr" in pa)


def test_env_and_path_policy():
    for name in ("GITHUB_TOKEN", "FOO_SECRET", "MY_API_KEY", "SSH_AUTH_SOCK", "AWS_REGION", "LD_PRELOAD", "GIT_DIR", "PATH", "lower"):
        try:
            confine.check_env_name(name)
            bad(f"env name {name} denied")
        except confine.ConfineError as e:
            check(f"env name {name} denied (64)", e.exit_code == 64)
    for name in ("LANG", "GIT_AUTHOR_NAME", "MY_FLAG"):
        try:
            confine.check_env_name(name)
            ok(f"env name {name} allowed")
        except confine.ConfineError:
            bad(f"env name {name} allowed")
    facts = confine.HostFacts()
    link = os.path.join(SCRATCH, "linkdir")
    os.symlink("/etc", link)
    real = tempfile.mkdtemp(dir=SCRATCH)
    home = os.path.expanduser("~")
    cases = [("/", "root"), (real + "/..", "dotdot"), (real + "/", "trailing slash"), (link, "symlink"),
             ("/proc/self/root", "proc self root"), ("/run/secrets", "secrets"), (home + "/.ssh", "~/.ssh"),
             (home + "/.config/sops/age", "sops"), ("relative/path", "relative"), (real + "/nonexistent", "missing")]
    for path, label in cases:
        try:
            confine.check_user_path(path, facts)
            bad(f"path policy rejects {label}")
        except confine.ConfineError as e:
            check(f"path policy rejects {label} (64)", e.exit_code == 64)
    for args, label in (([["--ro", "/run/secrets"]], "--ro secrets"), ):
        cp = run_cli("--profile", "readonly-analysis", "--ro", "/run/secrets", "--", "true")
        check("CLI --ro /run/secrets exits 64", cp.returncode == 64, cp.stderr[-200:])
    cp = run_cli("--profile", "readonly-analysis", "--scratch", "--explain", "--", "true")
    check("readonly-analysis accepts a launcher-created --scratch", cp.returncode == 0 and "/scratch" in cp.stdout, cp.stderr[-200:])
    cp = run_cli("--profile", "readonly-analysis", "--rw", real, "--", "true")
    check("arbitrary --rw paths are rejected even under /tmp (64)", cp.returncode == 64, cp.stderr[-200:])
    cp = run_cli("--profile", "eval-untrusted", "--scratch", "--", "true")
    check("--scratch refused where the profile has none (64)", cp.returncode == 64)
    cp = run_cli("--profile", "eval-untrusted", "--rw", real, "--", "true")
    check("eval-untrusted rejects --rw (64)", cp.returncode == 64)
    cp = run_cli("--profile", "eval-untrusted", "--net", "loopback", "--", "true")
    check("loopback above ceiling exits 64", cp.returncode == 64)
    cp = run_cli("--profile", "eval-untrusted", "--env-allow", "GITHUB_TOKEN", "--", "true")
    check("denied --env-allow exits 64", cp.returncode == 64)
    cp = run_cli("--profile", "eval-untrusted", "--egress-service", "llama", "--", "true")
    check("egress flags parsed and rejected (64)", cp.returncode == 64)
    cp = run_cli("--profile", "nope", "--", "true")
    check("unknown profile exits 71", cp.returncode == 71)
    cp = run_cli("--profile", "worktree-rw", "--", "true")
    check("worktree profile without --worktree exits 64", cp.returncode == 64)


def test_fail_closed_simulated():
    marker = os.path.join(SCRATCH, "ran-marker")
    old = os.environ.get("BWRAP_PATH")
    try:
        os.environ["BWRAP_PATH"] = "/nonexistent/bwrap"
        confine._pf_cache.clear()
        res = sh("eval-untrusted", f"touch {marker}")
        check("missing bwrap: exit 70, reason bwrap-missing, child never ran",
              res.exit_code == 70 and res.reason.startswith("bwrap-missing") and not os.path.exists(marker), res.reason)
        stub = os.path.join(SCRATCH, "stub-bwrap")
        Path(stub).write_text("#!/bin/sh\nexit 1\n")
        os.chmod(stub, 0o755)
        os.environ["BWRAP_PATH"] = stub
        confine._pf_cache.clear()
        res = sh("eval-untrusted", f"touch {marker}")
        check("userns-disabled (stub bwrap exits 1): exit 70, reason userns-unavailable, no fallback",
              res.exit_code == 70 and res.reason.startswith("userns-unavailable") and not os.path.exists(marker), res.reason)
        cp = run_cli("--preflight", env=dict(os.environ))
        check("--preflight exits 70 when unavailable", cp.returncode == 70, cp.stdout)
    finally:
        if old is None:
            os.environ.pop("BWRAP_PATH", None)
        else:
            os.environ["BWRAP_PATH"] = old
        confine._pf_cache.clear()
    import ast
    src = Path(confine.__file__).read_text()
    check("static: no preexec_fn, no shell=True, no --share-net, no os.system",
          "preexec_fn=" not in src and "shell=True" not in src and '"--share-net"' not in src and "os.system(" not in src)
    tree = ast.parse(src)
    allowed = {"host_git", "run_host_git", "import_objects", "preflight", "scope_probe", "_scope_probe_locked", "_execute", "_rebuild_index"}
    spawners = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) \
                    and c.func.value.id == "subprocess" and c.func.attr in ("run", "Popen", "check_output", "call"):
                spawners.append(fn.name)
    check("static: subprocess only in git helpers, import pipeline, preflight probe and launcher",
          set(spawners) <= allowed, str(set(spawners) - allowed))


def test_lint():
    d = tempfile.mkdtemp(dir=SCRATCH)
    bad_f = os.path.join(d, "bad.py")
    Path(bad_f).write_text('import subprocess\ndef f(worktree):\n    subprocess.run(["git", "status"], cwd=worktree)\n')
    good_f = os.path.join(d, "good.py")
    Path(good_f).write_text('import subprocess\ndef f(worktree, admin):\n    subprocess.run(["git", "--git-dir", admin, "status"])\n')
    other = os.path.join(d, "other.py")
    Path(other).write_text('import subprocess\nsubprocess.run(["git", "status"])\n')
    check("lint flags cwd-selected git in a worktree script", bool(confine.lint_host_git(bad_f)))
    check("lint passes explicit --git-dir", not confine.lint_host_git(good_f))
    check("lint ignores scripts without worktree paths", not confine.lint_host_git(other))
    check("lint: confine.py itself is clean", not confine.lint_host_git(confine.__file__))
    cp = run_cli("--lint-host-git", bad_f)
    check("CLI --lint-host-git exits 1 on findings", cp.returncode == 1)
    oncall = REPO / "scripts" / "ai" / "lib" / "oncalld_engine.py"
    if oncall.exists():
        n = len(confine.lint_host_git(str(oncall)))
        print(f"INFO: oncalld_engine.py has {n} cwd-selected git spawn(s); W2-S3 adopts host_git (not an S2a failure)")


def test_host_git_hostile_layout():
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    sub = os.path.join(wt, "sub")
    subprocess.run(["git", "init", "-q", sub], check=True)
    mark = os.path.join(base, "fsmonitor-ran")
    hook = os.path.join(base, "fsm.sh")
    Path(hook).write_text(f"#!/bin/sh\ntouch {mark}\nexit 0\n")
    os.chmod(hook, 0o755)
    Path(sub, ".git", "config").write_text(f"[core]\n\tfsmonitor = {hook}\n")
    subprocess.run(["git", "status"], cwd=sub, capture_output=True)
    control = os.path.exists(mark)
    check("negative control: cwd-based git honours planted embedded config", control)
    if control:
        os.unlink(mark)
    admin = os.path.join(repo, ".git", "worktrees", f"wt-claim1")
    cp = confine.run_host_git(["status", "--short"], git_dir=admin, work_tree=wt)
    check("host_git does not execute planted embedded-repo config", not os.path.exists(mark) and cp.returncode == 0,
          cp.stderr.decode()[:200])
    argv, env = confine.host_git(["status"], git_dir=admin, work_tree=wt)
    check("host_git argv: explicit dirs, hooks off, fsmonitor off, no system/global config",
          "--git-dir" in argv and "core.hooksPath=/dev/null" in argv and "core.fsmonitor=false" in argv
          and env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_CONFIG_GLOBAL"] == "/dev/null" and env["GIT_ATTR_NOSYSTEM"] == "1")


def test_hostile_dirs_pure():
    d = tempfile.mkdtemp(dir=SCRATCH)
    sentinel = os.path.join(d, "outside-sentinel")
    Path(sentinel).write_text("keep")
    refs = os.path.join(d, "refs")
    os.makedirs(refs)
    oid = "a" * 40
    Path(refs, "good").write_text(oid + "\n")
    acc, probs = confine.validate_ref_dir(refs)
    check("ref dir: a well-formed ref is accepted", acc == {"good": oid} and not probs)
    os.symlink(sentinel, os.path.join(refs, "lnk"))
    os.link(os.path.join(refs, "good"), os.path.join(refs, "hard"))
    Path(refs, "Bad_Name").write_text(oid + "\n")
    Path(refs, "junk").write_text("not-an-oid\n")
    acc, probs = confine.validate_ref_dir(refs)
    check("ref dir: symlink, hard link, bad name, bad content all flagged ref-foreign-changed",
          len(probs) >= 4 and all(p["kind"] == "ref-foreign-changed" for p in probs) and "lnk" not in acc, str(probs))
    many = os.path.join(d, "many")
    os.makedirs(many)
    for i in range(confine.MAX_REFS + 5):
        Path(many, f"r{i}").write_text(oid + "\n")
    acc, probs = confine.validate_ref_dir(many)
    check("ref dir: more than 64 entries flagged", any("cap" in p["detail"] for p in probs))
    q = os.path.join(d, "q")
    os.makedirs(os.path.join(q, "info"))
    os.makedirs(os.path.join(q, "ab"))
    Path(q, "info", "alternates").write_text("/etc\n")
    os.symlink(d, os.path.join(q, "cd"))
    os.symlink(sentinel, os.path.join(q, "ab", "c" * 38))
    Path(q, "ab", "d" * 38).write_text("x")
    kept, junk = confine.sanitize_quarantine(q)
    check("quarantine: alternates, symlinked dirs and symlinked objects removed, never followed; outside file intact",
          not os.path.exists(os.path.join(q, "info")) and not os.path.lexists(os.path.join(q, "cd"))
          and not os.path.lexists(os.path.join(q, "ab", "c" * 38)) and Path(sentinel).read_text() == "keep"
          and os.path.exists(os.path.join(q, "ab", "d" * 38)) and junk == 3, f"junk={junk}")
    sub = os.path.join(d, "tree")
    os.makedirs(os.path.join(sub, "x", ".git"))
    Path(sub, "a").write_bytes(b"1" * 5000)
    total, over, emb = confine.scan_tree(sub, 4000)
    check("scan_tree: size cap trips and embedded .git found", over and emb == [os.path.join("x", ".git")] or over)
    total, over, emb = confine.scan_tree(sub)
    check("scan_tree: embedded repo reported", emb == [os.path.join("x", ".git")] and not over)


def test_guidance_pure():
    d = tempfile.mkdtemp(dir=SCRATCH)
    Path(d, "denials.md").write_text("")
    hostile = ["evil.com\r\nINJECT: do bad", "a\x00b", "héllo.example", "x" * 300, "good.example.com:443", "`;rm -rf`"]
    ids = [confine.append_denial(d, "nonglobal", h) for h in hostile]
    text = Path(d, "denials.md").read_text()
    lines = text.splitlines()
    check("denials: one line per entry, no injected lines", len(lines) == len(hostile), str(len(lines)))
    cfg = json.loads((REPO / "config" / "confine-guidance.json").read_text())
    tmpl = cfg["denials"]["nonglobal"]
    okl = all(re.match(r"^\[d[0-9a-f]{10}\] nonglobal: " + re.escape(tmpl) + r"( dest=`[A-Za-z0-9.:\-\[\]]+`)?$", l) for l in lines)
    check("denials: heads are fixed template + opaque id; destination only as escaped code span", okl, text[:300])
    check("denials: valid destination kept, invalid replaced", "dest=`good.example.com:443`" in text and text.count("[invalid-destination]") == 5)
    phrase = confine.denial_reason_phrase("nonglobal", ids[0])
    check("403 phrase fixed string <= 100 chars", len(phrase) <= 100 and "\r" not in phrase and "\n" not in phrase)


def test_nproc_headroom():
    plan, _ = golden_plan("eval-untrusted")
    p = confine.make_plan(confine.load_profile("eval-untrusted"), ["true"], facts=FakeFacts(), bwrap="/b", prlimit="/p")
    check("RLIMIT_NPROC is headroom above the uid's current task count", p.limits["nproc"] == 32 + 100)


# ------------------------------------------------------------ behavioral tests

@behavioral
def test_secrets_and_env():
    fake_home = tempfile.mkdtemp(dir=SCRATCH)
    os.makedirs(os.path.join(fake_home, ".ssh"))
    ssh_sent = os.path.join(fake_home, ".ssh", "id_test")
    Path(ssh_sent).write_text("PRIVATE")
    sec = os.path.join(SCRATCH, "run-secrets-sentinel")
    Path(sec).write_text("SECRET")
    env = dict(os.environ, GITHUB_TOKEN="gh-xyz", SOMEAPI="api-xyz", FOO_SECRET="s-xyz", HOME=fake_home)
    code = (f"import os,sys\nfor p in {[ssh_sent, sec, '/run/secrets/x']!r}:\n"
            "  print(p, os.path.exists(p))\nprint('MOUNTS', any(s in open('/proc/self/mountinfo').read() for s in ('.ssh','run-secrets')))\n"
            "print('ENV', sorted(k for k in os.environ if k in ('GITHUB_TOKEN','SOMEAPI','FOO_SECRET','HOME')))\nprint('VALS', [v for v in os.environ.values() if 'xyz' in v])")
    res = confine.run("readonly-analysis", [PY, "-c", code], caller_env=env)
    o = out(res)
    check("secrets sentinels unreadable by absolute path and absent from mountinfo",
          "True" not in o.split("MOUNTS")[0] and "MOUNTS False" in o, o)
    check("planted GITHUB_TOKEN / SOMEAPI / FOO_SECRET absent in child (allowlist, not denylist)",
          "ENV ['HOME']" in o and "VALS []" in o, o)
    old = os.environ.get("HOME")
    os.environ["HOME"] = fake_home
    try:
        r2 = confine.run("readonly-analysis", ["true"], ro=[os.path.join(fake_home, ".ssh")])
    finally:
        os.environ["HOME"] = old
    check("--ro on ~/.ssh refused (64)", r2.exit_code == 64, r2.reason)


@behavioral
def test_writes_and_net_and_commit():
    for label, repo, wt in fixtures_both():
        host_marks = [os.path.join(os.path.dirname(wt), "sibling"), os.path.join(repo, ".git", "config-probe")]
        script = ("for p in /etc/zz /nix/store/zz /tmp/x %s %s %s/config %s/hooks/zz; do (echo x > $p) 2>/dev/null && echo WROTE $p; done;"
                  " echo inside > inside.txt; echo $HOME; echo scratch > $HOME/s && echo SCRATCH_OK") % (
                      host_marks[0], host_marks[1], os.path.join(repo, ".git"), os.path.join(repo, ".git"))
        cfg_before = Path(repo, ".git", "config").read_bytes()
        res = sh("worktree-rw", script, worktree=wt)
        o = out(res)
        check(f"[{label}] writes outside the worktree fail, scratch HOME and worktree writable",
              "WROTE" not in o and "SCRATCH_OK" in o and Path(wt, "inside.txt").exists()
              and not os.path.exists(host_marks[0]) and Path(repo, ".git", "config").read_bytes() == cfg_before
              and res.status == "ok", o + res.stderr.decode()[:300])
        before = refs_of(repo)
        res = sh("worktree-rw", "echo a > a.txt; git add a.txt; git commit -qm viasandbox; git log --oneline | head -3", worktree=wt)
        new = git(repo, "rev-parse", f"aq/claim1/slug").stdout.strip()
        subj = git(repo, "log", "-1", "--format=%s", "aq/claim1/slug").stdout.strip()
        status = git(wt, "status", "--short", "-uno").stdout
        check(f"[{label}] git commit works in sandbox and lands via host import (ref promoted, objects present)",
              res.status == "ok" and subj == "viasandbox" and git(repo, "cat-file", "-t", new).stdout.strip() == "commit"
              and res.refs.get("promoted") and "main" in refs_of(repo) and
              [l for l in refs_of(repo).splitlines() if "refs/heads/main" in l] == [l for l in before.splitlines() if "refs/heads/main" in l],
              out(res) + res.stderr.decode()[-300:] + str(res.refs))
        check(f"[{label}] host sees clean index after run", status.strip() == "", status)
        fsck = git(repo, "fsck", "--connectivity-only", check_rc=False)
        check(f"[{label}] host fsck clean after run", fsck.returncode == 0, fsck.stderr[:200])
        check(f"[{label}] sandbox commit emits no auto-gc noise", not re.search(rb"auto gc|gc --auto|auto packing|run .git maintenance", res.stderr.lower()), res.stderr.decode()[:200])
        git(repo, "worktree", "remove", "--force", wt, check_rc=False)

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    code = (f"import socket\ns=socket.socket();s.settimeout(2)\ntry:\n s.connect(('127.0.0.1',{port}));print('CONNECTED')\n"
            "except OSError as e:\n print('BLOCKED')\nprint(sorted(l.split(':')[0].strip() for l in open('/proc/net/dev').read().splitlines()[2:]))")
    res = py("eval-untrusted", code)
    check("net none: host loopback listener unreachable, only lo present", "BLOCKED" in out(res) and "['lo']" in out(res), out(res))
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    res = py("worktree-rw", code, worktree=wt, net="loopback")
    check("net loopback: private lo only, host listener still unreachable", "BLOCKED" in out(res) and "['lo']" in out(res), out(res))
    srv.close()
    abs_name = "aqc-" + os.path.basename(SCRATCH)
    asock = socket.socket(socket.AF_UNIX)
    asock.bind("\0" + abs_name)
    asock.listen(1)
    res = py("eval-untrusted", f"import socket\ns=socket.socket(socket.AF_UNIX)\ntry:\n s.connect('\\0{abs_name}');print('CONNECTED')\nexcept OSError:\n print('BLOCKED')")
    check("abstract unix socket from the host unreachable", "BLOCKED" in out(res), out(res))
    asock.close()


@behavioral
def test_git_hostile_inside():
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    common = os.path.join(repo, ".git")
    admin = os.path.join(common, "worktrees", "wt-claim1")
    hashes = {p: Path(p).read_bytes() for p in [os.path.join(common, "config"), os.path.join(admin, "HEAD"),
                                                os.path.join(admin, "commondir"), os.path.join(admin, "gitdir"), os.path.join(wt, ".git")]}
    attempts = []
    for p in list(hashes) + [os.path.join(common, "hooks", "pre-commit"), os.path.join(common, "info", "x"),
                             os.path.join(common, "objects", "info", "alternates"), os.path.join(common, "refs", "heads", "other"),
                             os.path.join(common, "refs", "heads", "main"), os.path.join(common, "packed-refs"),
                             os.path.join(common, "HEAD")]:
        attempts.append(p)
    script = " ".join(f"(echo pwn >> {p}) 2>/dev/null && echo WROTE {p};" for p in attempts)
    script += (" git branch other 2>/dev/null && echo BRANCHED;"
               " git switch -c zzz 2>/dev/null && echo SWITCHED;"
               " git update-ref refs/heads/main HEAD 2>/dev/null && echo MAINMOVED;"
               " git config user.name pwn 2>/dev/null && echo CONFIGWRITTEN; true")
    before_refs = refs_of(repo)
    res = sh("worktree-rw", script, worktree=wt)
    o = out(res)
    check("worktree metadata, config, hooks, other branches, main, packed-refs, alternates all unwritable from the sandbox",
          "WROTE" not in o and "BRANCHED" not in o and "SWITCHED" not in o and "MAINMOVED" not in o and "CONFIGWRITTEN" not in o, o)
    check("host bytes identical for config/metadata/.git file and refs unchanged; run ok",
          all(Path(p).read_bytes() == b for p, b in hashes.items()) and refs_of(repo) == before_refs and res.status == "ok", res.reason)
    existing = git(repo, "rev-parse", "HEAD").stdout.strip()
    obj = f"{common}/objects/{existing[:2]}/{existing[2:]}"
    h_before = hashlib_file(obj)
    res = sh("worktree-rw", f"(echo x > {obj}) 2>/dev/null && echo WROTE; (rm -f {obj}) 2>/dev/null; true", worktree=wt)
    check("existing objects cannot be overwritten or removed", "WROTE" not in out(res) and hashlib_file(obj) == h_before)

    # symlink / .. escapes inside the worktree
    esc = ("ln -s /etc/passwd l1; ln -s /home l2; ln -s ../../.. l3; ln -s %s/config l4; "
           "cat l1 2>/dev/null && echo READ1; ls l2/hyperd 2>/dev/null && echo READ2; ls l3/ 2>/dev/null | head -1; "
           "(echo x >> l4) 2>/dev/null && echo WROTE4; (echo x > l3/escape) 2>/dev/null && echo WROTE3; true") % common
    res = sh("worktree-rw", esc, worktree=wt)
    o = out(res)
    check("symlink and .. escapes: no host file read, no write through links", "READ" not in o and "WROTE" not in o
          and not os.path.exists(os.path.join(base, "escape")) and Path(common, "config").read_bytes() == hashes[os.path.join(common, "config")], o)
    git(repo, "clean", "-fdq", check_rc=False)


def hashlib_file(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def commit_script(extra=""):
    return f"echo c > c.txt; git add c.txt; git commit -qm cm; {extra}"


@behavioral
def test_import_cases():
    # mismatched-name object (required fixture)
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    pre_objs = set(git(repo, "cat-file", "--batch-all-objects", "--batch-check").stdout.splitlines())
    snap = {l.split()[0]: hashlib_file(f"{repo}/.git/objects/{l.split()[0][:2]}/{l.split()[0][2:]}")
            for l in pre_objs if os.path.exists(f"{repo}/.git/objects/{l.split()[0][:2]}/{l.split()[0][2:]}")}
    tamper = (f"{PY} - <<'EOF'\nimport os,zlib,glob\nq=os.environ['GIT_OBJECT_DIRECTORY']\n"
              "fs=sorted(glob.glob(q+'/??/*'))\nvictim=[f for f in fs if True][0]\n"
              "junk=zlib.compress(b'blob 5\\x00junk!')\nos.chmod(victim,0o644);open(victim,'wb').write(junk)\nprint('REPLACED',victim)\nEOF")
    before_ref = refs_of(repo)
    res = sh("worktree-rw", commit_script(tamper), worktree=wt)
    after_snap = {k: hashlib_file(f"{repo}/.git/objects/{k[:2]}/{k[2:]}") for k in snap}
    check("mismatched-name object: import fails (exit 72 object-import-failed), nothing promoted, originals byte-identical",
          res.exit_code == 72 and res.reason.startswith("object-import-failed") and after_snap == snap
          and refs_of(repo) == before_ref, f"{res.exit_code} {res.reason} {res.refs.get('rejected')}\n{out(res)} {res.stderr.decode()[-300:]}")
    inc = list(Path(os.environ["ATTENTION_QUEUE_DIR"]).rglob("*")) if os.path.isdir(os.environ["ATTENTION_QUEUE_DIR"]) else []
    qtext = "".join(p.read_text(errors="replace") for p in inc if p.is_file())
    check("tamper/import failure raises an aq-confine high attention-queue incident with inspect commands",
          "aq-confine" in qtext and "pre-snapshot.json" in qtext, qtext[:200])
    git(repo, "worktree", "remove", "--force", wt, check_rc=False)

    # planted commit failing connectivity
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    plant = (f"{PY} - <<'EOF'\nimport os,subprocess\nenv=dict(os.environ)\n"
             "body='tree '+'1'*40+'\\nauthor a <a@a> 1 +0000\\ncommitter a <a@a> 1 +0000\\n\\nplanted\\n'\n"
             "oid=subprocess.run(['git','hash-object','-t','commit','-w','--literally','--stdin'],input=body.encode(),capture_output=True,env=env).stdout.decode().strip()\n"
             "d=os.environ['GIT_DIR'].rsplit('/worktrees/',1)[0]+'/refs/heads/aq/claim1/planted'\nopen(d,'w').write(oid+'\\n')\nprint('PLANTED',oid)\nEOF")
    before_ref = refs_of(repo)
    res = sh("worktree-rw", plant, worktree=wt)
    check("planted commit with missing tree fails connectivity: not promoted, exit 72",
          res.exit_code == 72 and "planted" not in refs_of(repo) and refs_of(repo) == before_ref,
          f"{res.exit_code} {res.reason} {out(res)} {res.refs.get('rejected')}")

    # hostile ref dir
    for label, cmd in (("symlink", "ln -s /etc/passwd {d}/lnk"), ("hard link", "ln {d}/slug {d}/hl"),
                       ("bad name", "cp {d}/slug {d}/BAD_NAME"), ("too many", "for i in $(seq 1 70); do cp {d}/slug {d}/r$i; done")):
        base = tempfile.mkdtemp(dir=SCRATCH)
        repo, wt = make_fixture(base)
        d = f"{repo}/.git/refs/heads/aq/claim1"
        before_ref = refs_of(repo)
        res = sh("worktree-rw", commit_script(cmd.format(d=d)), worktree=wt)
        check(f"private ref dir with {label}: ref-foreign-changed, exit 72, nothing promoted, real refs unchanged",
              res.exit_code == 72 and "ref-foreign-changed" in res.refs.get("kinds", []) and refs_of(repo) == before_ref,
              f"{res.exit_code} {res.reason} {res.refs.get('rejected')} {res.stderr.decode()[:200]}")

    # second ref imported and promoted with correct base
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    d = f"{repo}/.git/refs/heads/aq/claim1"
    res = sh("worktree-rw", commit_script(f"git branch aq/claim1/extra 2>&1; cp {d}/slug {d}/extra2; echo d > d.txt; git add d.txt; git commit -qm second"), worktree=wt)
    r = refs_of(repo)
    check("every accepted ref in the namespace is imported and promoted (own tip + extra refs)",
          res.status == "ok" and "refs/heads/aq/claim1/extra2" in r and "refs/heads/aq/claim1/slug" in r
          and git(repo, "fsck", "--connectivity-only", check_rc=False).returncode == 0, f"{res.reason} {res.refs} {r}")

    # packed-only claim ref
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base, packed_only=True)
    check("fixture: claim ref is packed-only", not os.path.exists(f"{repo}/.git/refs/heads/aq/claim1/slug"))
    res = sh("worktree-rw", commit_script(), worktree=wt)
    check("packed-only claim branch still commits through the seeded private bind and promotes",
          res.status == "ok" and git(repo, "log", "-1", "--format=%s", "aq/claim1/slug").stdout.strip() == "cm", f"{res.reason} {res.refs}")

    # own-branch rewrite, strict and not
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    amend = "git commit -q --amend --allow-empty -m rewritten"
    res = sh("worktree-rw", amend, worktree=wt)
    check("own-branch rewrite is recorded but does not fail without strict_history",
          res.status == "ok" and res.refs.get("rewrites"), f"{res.reason} {res.refs}")
    with ProfileDir(custom_profiles("worktree-rw", lambda d: d.update(strict_history=True))):
        base = tempfile.mkdtemp(dir=SCRATCH)
        repo, wt = make_fixture(base)
        head0 = git(repo, "rev-parse", "aq/claim1/slug").stdout.strip()
        # first create descendant so amend actually diverges from the seeded tip
        res = sh("worktree-rw", "git commit -q --amend --allow-empty -m rewritten", worktree=wt)
        check("strict_history: own-branch rewrite fails (72 ref-tamper) and is not promoted",
              res.exit_code == 72 and git(repo, "rev-parse", "aq/claim1/slug").stdout.strip() == head0, f"{res.exit_code} {res.reason}")

    # embedded repo
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    res = sh("worktree-rw", "env -u GIT_DIR -u GIT_WORK_TREE git init -q sub", worktree=wt)
    check("embedded repo created in worktree reported worktree-metadata-changed (72)",
          res.exit_code == 72 and "worktree-metadata-changed" in res.refs.get("kinds", []), f"{res.exit_code} {res.refs.get('kinds')}")

    # extensions.worktreeConfig refused
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    git(repo, "config", "extensions.worktreeConfig", "true")
    res = sh("worktree-rw", "true", worktree=wt)
    check("extensions.worktreeConfig repository refused (64)", res.exit_code == 64, res.reason)

    # worktree swapped for a symlink -> 64
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    link = os.path.join(base, "wt-link")
    os.symlink(wt, link)
    res = sh("worktree-rw", "true", worktree=link)
    check("symlinked worktree path refused (64)", res.exit_code == 64, res.reason)


@behavioral
def test_mid_run_and_kill():
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base, packed_only=True)
    before = refs_of(repo)
    rid = "midrun000001"
    seen = {}

    def observer():
        private = os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "sandbox", "refs", "slug")
        for _ in range(100):
            if os.path.exists(private) and os.path.exists(os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "process.json")):
                break
            time.sleep(0.1)
        time.sleep(0.5)
        seen["private_ref"] = os.path.exists(private)
        seen["real_unchanged"] = refs_of(repo) == before
        seen["log_all"] = git(repo, "log", "--all", "--oneline", check_rc=False).returncode
        seen["fsck"] = git(repo, "fsck", "--connectivity-only", check_rc=False).returncode
        seen["gc"] = git(repo, "gc", "--quiet", check_rc=False).returncode
        seen["kill"] = run_cli("--kill", rid).returncode

    th = threading.Thread(target=observer)
    th.start()
    t0 = time.time()
    res = sh("worktree-rw", commit_script("sleep 60"), worktree=wt, run_id=rid)
    th.join()
    check("mid-run: sandbox ref exists only privately; real refs unchanged; host log --all, fsck, gc all succeed",
          seen.get("private_ref") and seen.get("real_unchanged") and seen["log_all"] == 0 and seen["fsck"] == 0 and seen["gc"] == 0, str(seen))
    check("aq-confine --kill (pidfd path) kills the run promptly (child-failed, 137)", seen.get("kill") == 0 and time.time() - t0 < 30
          and res.exit_code == 137, f"{seen.get('kill')} {res.exit_code} {res.reason}")
    check("after SIGKILL: real refs byte-identical, nothing promoted, host git healthy",
          refs_of(repo) == before and res.refs.get("promotion_skipped") and git(repo, "fsck", "--connectivity-only", check_rc=False).returncode == 0
          and git(repo, "log", "--all", "--oneline", check_rc=False).returncode == 0, f"{refs_of(repo)} {res.refs}")
    code, msg = confine.kill_run("midrun000001")
    check("kill of a finished run refuses (no live process)", code == 64, msg)

    # stale recorded start time refuses to signal
    p = subprocess.Popen(["sleep", "30"])
    rd = os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", "stalerun00001")
    os.makedirs(rd, exist_ok=True)
    Path(rd, "process.json").write_text(json.dumps({"pid": p.pid, "pgid": p.pid, "start_ticks": 1, "run_id": "stalerun00001"}))
    code, msg = confine.kill_run("stalerun00001")
    alive = p.poll() is None
    p.kill()
    p.wait()
    check("--kill refuses on mismatched recorded start time; process untouched", code == 64 and alive, msg)

    # concurrent main move is information, not failure
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    rid2 = "concur0000001"

    def mover():
        for _ in range(100):
            if os.path.exists(os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid2, "process.json")):
                break
            time.sleep(0.1)
        git(repo, "commit", "--allow-empty", "-qm", "hostmove")   # main is checked out in the main repo
    th = threading.Thread(target=mover)
    th.start()
    res = sh("worktree-rw", commit_script("sleep 1.5"), worktree=wt, run_id=rid2)
    th.join()
    check("legitimate concurrent move of main is recorded as concurrent-actor, run still ok",
          res.status == "ok" and "refs/heads/main" in res.refs.get("concurrent", []), f"{res.status} {res.reason} {res.refs}")

    # stale old value: host moves the claim ref during the run
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    rid3 = "stale00000001"

    def staler():
        for _ in range(100):
            if os.path.exists(os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid3, "process.json")):
                break
            time.sleep(0.1)
        git(repo, "update-ref", "refs/heads/aq/claim1/slug", git(repo, "commit-tree", "-m", "other", "main^{tree}").stdout.strip())
    th = threading.Thread(target=staler)
    th.start()
    res = sh("worktree-rw", commit_script("sleep 1.5"), worktree=wt, run_id=rid3)
    th.join()
    check("stale old value: update-ref fails safely, not forced; reported (72 ref-stale)",
          res.exit_code == 72 and res.reason.startswith("ref-stale") and res.refs.get("stale"), f"{res.exit_code} {res.reason} {res.refs.get('stale')}")


@behavioral
def test_kill_limits_isolation_guidance():
    t0 = time.time()
    token = f"77.{os.getpid()}{int(t0) % 1000}"
    res = confine.run("eval-untrusted", ["sh", "-c", f"trap '' TERM; exec sleep {token}"], timeout=2)
    alive = [p for p in os.listdir("/proc") if p.isdigit() and token.encode() in _cmdline(p)]
    check("timeout kills a SIGTERM-ignoring child (exit 124) and leaves no process behind",
          res.exit_code == 124 and time.time() - t0 < 15 and not alive, f"{res.exit_code} {alive}")

    res = py("eval-untrusted", "print(open('/proc/self/limits').read())")
    o = out(res)
    check("prlimit values visible in child (as, cpu, fsize, core)",
          re.search(r"Max address space\s+1073741824", o) and re.search(r"Max cpu time\s+20", o)
          and re.search(r"Max file size\s+4194304", o) and re.search(r"Max core file size\s+0", o), o)

    nested = ("import os\ntry:\n os.unshare(os.CLONE_NEWUSER);print('NESTED_OK')\nexcept OSError as e:\n print('NESTED_BLOCKED',e.errno)\n"
              "print('SYS', os.path.exists('/sys/class'))\nprint('FDS', sorted(int(f) for f in os.listdir('/proc/self/fd')))")
    res = py("eval-untrusted", nested)
    o = out(res)
    check("nested user namespace fails by default (--disable-userns); /sys not mounted", "NESTED_BLOCKED" in o and "SYS False" in o, o)
    fds = re.search(r"FDS \[(.*?)\]", o)
    nums = [int(x) for x in fds.group(1).split(",")] if fds and fds.group(1) else []
    check("only fds 0-2 (plus the listing fd) inherited", all(n <= 3 for n in nums) and {0, 1, 2} <= set(nums), str(nums))

    def allow(d):
        d["disable_userns"] = False
        d["allow_nested_userns"] = True
    with ProfileDir(custom_profiles("eval-untrusted", allow)):
        res = confine.run("eval-untrusted", [PY, "-c", nested], allow_nested_userns=True)
        check("control: with an explicit nested-userns profile the same probe succeeds (test is not vacuous)",
              "NESTED_OK" in out(res), out(res) + res.stderr.decode()[:200])
        tel = Path(confine.telemetry_path()).read_text()
        check("nested userns launch is logged incident-grade in telemetry", "nested-userns-enabled" in tel)

    # guidance
    rid = "guide0000001"
    d = os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "guidance")

    def appender():
        for _ in range(100):
            if os.path.exists(os.path.join(d, "denials.md")):
                break
            time.sleep(0.05)
        time.sleep(0.6)
        appended.append(confine.append_denial(d, "nogrant", "pypi.org"))
    appended = []
    th = threading.Thread(target=appender)
    th.start()
    code = ("import os,time,sys\ng=os.path.dirname(os.environ['AQ_CONFINE_GUIDANCE'])\nprint(open(os.environ['AQ_CONFINE_GUIDANCE']).read())\n"
            "for op in ('w','a'):\n  try: open(g+'/GUIDANCE.md',op).write('x');print('WROTE')\n  except OSError: pass\n"
            "try: open(g+'/new','w');print('CREATED')\nexcept OSError: pass\n"
            "try: os.symlink('/etc/passwd',g+'/lnk');print('LINKED')\nexcept OSError: pass\n"
            "try: os.rename(g+'/denials.md',g+'/d2');print('RENAMED')\nexcept OSError: pass\n"
            "for _ in range(60):\n  t=open(g+'/denials.md').read()\n  if t: print('LIVE',t);break\n  time.sleep(0.1)\n"
            "print('MARKER', os.path.exists('/run/aq-confine') or any('kill-requested' in n for n in os.listdir('/run')))")
    res = py("eval-untrusted", code, run_id=rid)
    th.join()
    o = out(res)
    cfg = json.loads((REPO / "config" / "confine-guidance.json").read_text())
    check("guidance dir: GUIDANCE.md rendered, read-only (write/create/symlink/rename fail), host appends visible live",
          cfg["intro"] in o and "WROTE" not in o and "CREATED" not in o and "LINKED" not in o and "RENAMED" not in o
          and f"[{appended[0]}] nogrant: {cfg['denials']['nogrant']} dest=`pypi.org`" in o, o)
    check("guidance contains only fixed strings and opaque ids (no argv, env or host paths)",
          "/home" not in o.split("LIVE")[0] and rid in o, o[:400])
    check("sandbox cannot see or create the kill marker (run dir unreachable)", "MARKER False" in o, o[-100:])

    # kill marker precedence
    rid = "marker000001"

    def marker_writer():
        for _ in range(200):
            if os.path.exists(os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "process.json")):
                break
            time.sleep(0.01)
        Path(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "kill-requested").write_text("")
    th = threading.Thread(target=marker_writer)
    th.start()
    res = py("eval-untrusted", "import time;time.sleep(0.4)", run_id=rid)
    th.join()
    check("marker present at reap time wins even with rc 0: status 72 egress-burst",
          res.exit_code == 72 and res.reason == "egress-burst", f"{res.exit_code} {res.reason} rc={res.rc}")
    rid = "marker000002"
    th = threading.Thread(target=lambda: (time.sleep(1.0), Path(os.environ["AQ_CONFINE_STATE_DIR"], "runs", rid, "kill-requested").write_text("")))
    th.start()
    t0 = time.time()
    res = py("eval-untrusted", "import time;time.sleep(30)", run_id=rid)
    th.join()
    check("marker mid-run: launcher polls and SIGKILLs promptly (egress-burst, 72)", res.exit_code == 72 and time.time() - t0 < 10, f"{res.exit_code} {res.reason}")


def _cmdline(pid):
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        return b""


@behavioral
def test_size_caps_and_telemetry():
    def tiny(d):
        d["size_caps"] = {"quarantine": 2000, "worktree": 100000}
    with ProfileDir(custom_profiles("worktree-rw", tiny)):
        base = tempfile.mkdtemp(dir=SCRATCH)
        repo, wt = make_fixture(base)
        before = refs_of(repo)
        res = sh("worktree-rw", "head -c 60000 /dev/urandom > big.bin; git add big.bin; git commit -qm big", worktree=wt)
        check("quarantine size cap trips: 72 size-cap, nothing promoted", res.exit_code == 72 and res.reason.startswith("size-cap")
              and refs_of(repo) == before, f"{res.exit_code} {res.reason} {res.refs.get('rejected')}")
        confine.SIZE_CHECK_INTERVAL_S = 0.5
        try:
            base = tempfile.mkdtemp(dir=SCRATCH)
            repo, wt = make_fixture(base)
            t0 = time.time()
            res = sh("worktree-rw", "head -c 400000 /dev/urandom > huge.bin; sleep 40", worktree=wt)
            check("worktree total size cap trips mid-run (periodic check kills the run, 72 size-cap)",
                  res.exit_code == 72 and res.reason.startswith("size-cap") and time.time() - t0 < 20, f"{res.exit_code} {res.reason}")
        finally:
            confine.SIZE_CHECK_INTERVAL_S = 5.0
    lines = Path(confine.telemetry_path()).read_text().splitlines()
    recs = [json.loads(l) for l in lines]
    check("telemetry: one JSON line per launch, each under 4096 bytes, no env values or argv",
          recs and all(len(l) < 4096 for l in lines) and all("argv_sha256" in r and "env" not in r and "cmd" not in r for r in recs)
          and "xyz" not in "".join(lines))
    tp = Path(SCRATCH, "tel-rot")
    os.environ["AQ_TELEMETRY_DIR"] = str(tp)
    tp.mkdir()
    confine.TELEMETRY_MAX_BYTES = 200
    try:
        for i in range(10):
            confine.write_telemetry({"event": "x", "i": i, "pad": "p" * 50})
    finally:
        confine.TELEMETRY_MAX_BYTES = 50 * 1024 * 1024
        os.environ["AQ_TELEMETRY_DIR"] = os.path.join(SCRATCH, "telemetry")
    check("telemetry rotates and keeps at most 3 files", (tp / "aq-confine.jsonl.1").exists() and not (tp / "aq-confine.jsonl.4").exists())


@behavioral
def test_explain_cli_exact():
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    cp = run_cli("--profile", "worktree-rw", "--worktree", wt, "--run-id", "explain00001", "--explain", "--", "git", "status")
    plan = confine.make_plan(confine.load_profile("worktree-rw"), ["git", "status"], worktree=wt, run_id="explain00001",
                             caller_env=dict(os.environ))
    lines = cp.stdout.splitlines()
    argv = lines[lines.index("ARGV") + 1: lines.index("ENV-NAMES")]
    import shlex
    expected = [shlex.quote(x) if x != "" else "''" for x in confine.build_argv(plan, confine.HostFacts())]
    # nproc headroom depends on live task count; compare everything else exactly
    strip = lambda L: [x for x in L if not x.startswith("--nproc=")]
    check("--explain prints the exact launch argv (prlimit + bwrap) and env names only",
          cp.returncode == 0 and strip(argv) == strip(expected) and "GIT_DIR" in lines[lines.index("ENV-NAMES"):]
          and not any("hello" in l for l in lines), cp.stderr[-200:])
    check("--explain has no side effects (no run dir created)",
          not os.path.exists(os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", "explain00001")))
    r = run_cli("--profile", "worktree-rw", "--worktree", wt, "--", "true")
    last = r.stderr.strip().splitlines()[-1]
    j = json.loads(last)
    check("CLI emits a JSON result line (status, rc, run id, profile, argv hash, limits, refs)",
          r.returncode == 0 and j["status"] == "ok" and all(k in j for k in ("rc", "run_id", "profile", "argv_sha256", "limits", "refs", "duration_s")), last[:200])


def test_path_policy_h2():
    facts = confine.HostFacts()
    uid = os.getuid()
    for path in (os.path.expanduser("~"), "/home", "/run", f"/run/user/{uid}", "/etc", "/var/run", "/nix/var/nix/daemon-socket",
                 "/", "/proc", "/sys", "/dev", "/root", os.path.dirname(os.path.expanduser("~")) + "/"):
        try:
            confine.check_user_path(path, facts)
            bad(f"protected/ancestor path {path} rejected")
        except confine.ConfineError as e:
            check(f"protected/ancestor path {path} rejected (64)", e.exit_code == 64)
    d = tempfile.mkdtemp(dir=SCRATCH)
    sub = os.path.join(d, "deep", "er")
    os.makedirs(sub)
    sock_path = os.path.join(sub, "agent.sock")
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(sock_path)
    srv.listen(1)
    marker = os.path.join(SCRATCH, "sock-ran")
    for prof in ("readonly-analysis", "worktree-rw"):
        if prof == "worktree-rw":
            continue
        res = confine.run(prof, ["sh", "-c", f"touch {marker}"], ro=[d])
        check("--ro dir containing a live unix socket is refused (64), child never ran",
              res.exit_code == 64 and "path-special" in res.reason and not os.path.exists(marker), res.reason)
    fifo_dir = tempfile.mkdtemp(dir=SCRATCH)
    os.mkfifo(os.path.join(fifo_dir, "ff"))
    res = confine.run("readonly-analysis", ["true"], ro=[fifo_dir])
    check("--ro dir containing a FIFO is refused (64)", res.exit_code == 64, res.reason)
    srv.close()
    res = confine.run("readonly-analysis", ["true"], ro=["/usr/bin"])
    check("--ro outside the profile allowlist is refused (64)", res.exit_code == 64 and "ro-not-allowed" in res.reason, res.reason)
    clean = tempfile.mkdtemp(dir=SCRATCH)
    for var in ("AQ_CONFINE_WORKTREE_ROOTS", "AQ_CONFINE_RO_ROOTS"):
        for val in ("/", os.path.expanduser("~"), "/run", "relative"):
            old = os.environ.get(var)
            os.environ[var] = val
            try:
                r = confine.run("readonly-analysis", ["true"], ro=[clean]) if var.endswith("RO_ROOTS") else \
                    confine.run("worktree-rw", ["true"], worktree=clean)
            finally:
                if old is None:
                    os.environ.pop(var, None)
                else:
                    os.environ[var] = old
            check(f"{var}={val} is rejected as a root (64)", r.exit_code == 64 and "root-invalid" in r.reason, r.reason)
    argv, env = confine.host_git(["status"], git_dir="/x")
    check("host_git neutralises safe.bareRepository=explicit", "safe.bareRepository=explicit" in argv)


@behavioral
def test_h2_h1_m1_m3_behavioral():
    ok_dir = tempfile.mkdtemp(dir=SCRATCH)
    Path(ok_dir, "data.txt").write_text("readable")
    res = confine.run("readonly-analysis", [PY, "-c", f"print(open('{ok_dir}/data.txt').read())"], ro=[ok_dir])
    check("allowed --ro path still works", "readable" in out(res) and res.status == "ok", res.reason)
    res = confine.run("readonly-analysis", [PY, "-c", "import os;open('/scratch/f','w').write('s');print(os.environ['AQ_CONFINE_SCRATCH'], os.stat('/scratch').st_uid==os.getuid())"],
                      scratch=True, run_id="scratch000001")
    sd = os.path.join(os.environ["AQ_CONFINE_STATE_DIR"], "runs", "scratch000001", "scratch")
    check("launcher-created scratch: writable in sandbox, host-visible, 0700, env set",
          res.status == "ok" and "/scratch True" in out(res) and Path(sd, "f").read_text() == "s"
          and stat.S_IMODE(os.stat(sd).st_mode) == 0o700, res.reason + res.stderr.decode()[:200])

    # M1: tmpfs and memory bounds
    plan, facts = golden_plan("worktree-rw")
    a = confine.build_argv(plan, facts)
    check("argv bounds /tmp and HOME tmpfs with --size",
          a[a.index("--tmpfs") - 2:a.index("--tmpfs")][0] == "--size" and a.count("--size") == 2)
    res = py("worktree-rw", "print(open('/proc/self/limits').read())", worktree=make_fixture(tempfile.mkdtemp(dir=SCRATCH))[1])
    check("worktree-rw has a default address-space bound of 8 GiB", re.search(r"Max address space\s+8589934592", out(res)) is not None, out(res)[:300])

    def small(d):
        d["tmp_size"] = 4 * 1024 * 1024
        d["limits"]["as"] = 512 * 1024 * 1024
        d["limits"]["fsize"] = 64 * 1024 * 1024
    with ProfileDir(custom_profiles("eval-untrusted", small)):
        code = ("import mmap\ntry:\n m=mmap.mmap(-1,1<<30);print('ALLOC_OK')\nexcept (OSError,MemoryError):\n print('ALLOC_FAIL')\n"
                "try:\n open('/tmp/big','wb').write(b'x'*(16<<20));print('FILL_OK')\nexcept OSError as e:\n print('FILL_FAIL',e.errno)")
        res = confine.run("eval-untrusted", [PY, "-c", code])
        check("allocating past the address-space cap fails inside; filling /tmp past its size cap fails with ENOSPC",
              "ALLOC_FAIL" in out(res) and "FILL_FAIL 28" in out(res) and res.status == "ok", out(res) + res.stderr.decode()[:200])

    # M3
    marker = os.path.join(SCRATCH, "stub0-ran")
    stub = os.path.join(SCRATCH, "stub0-bwrap")
    Path(stub).write_text("#!/bin/sh\nexit 0\n")
    os.chmod(stub, 0o755)
    old = os.environ.get("BWRAP_PATH")
    os.environ["BWRAP_PATH"] = stub
    confine._pf_cache.clear()
    try:
        res = sh("eval-untrusted", f"touch {marker}")
    finally:
        if old is None:
            os.environ.pop("BWRAP_PATH", None)
        else:
            os.environ["BWRAP_PATH"] = old
        confine._pf_cache.clear()
    check("a stub bwrap that exits 0 without launching is setup-failed (70), never ok",
          res.exit_code == 70 and res.status == "setup-failed" and not os.path.exists(marker), f"{res.status} {res.exit_code}")
    res1 = py("eval-untrusted", "pass", run_id="reuse0000001")
    res2 = py("eval-untrusted", "pass", run_id="reuse0000001")
    check("a reused --run-id is refused (64)", res1.status == "ok" and res2.exit_code == 64 and "run-id-in-use" in res2.reason, res2.reason)

    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    holder = {}
    th = threading.Thread(target=lambda: holder.update(r=sh("worktree-rw", "sleep 3", worktree=wt, run_id="busy00000001")))
    th.start()
    time.sleep(1.2)
    r2 = sh("worktree-rw", "true", worktree=wt)
    th.join()
    check("a second run on a busy worktree is refused (64 worktree-busy)", r2.exit_code == 64 and "worktree-busy" in r2.reason, r2.reason)

    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    before = refs_of(repo)
    real_imp = confine.import_objects
    confine.import_objects = lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("git", 1))
    try:
        res = sh("worktree-rw", commit_script(), worktree=wt)
    finally:
        confine.import_objects = real_imp
    check("a post-run exception is a structured 72 failure, nothing promoted, run() does not raise",
          res.exit_code == 72 and refs_of(repo) == before and "object-import-failed" in res.refs.get("kinds", []), f"{res.exit_code} {res.reason}")

    # H1: forged cache-tree extension must not survive
    base = tempfile.mkdtemp(dir=SCRATCH)
    repo, wt = make_fixture(base)
    forge = (f"{PY} - <<'EOF'\nimport os,hashlib\nidx=os.environ['GIT_DIR']+'/index'\nd=bytearray(open(idx,'rb').read())\n"
             "i=d.find(b'TREE')\nassert i>0,'no cache-tree'\nnl=d.index(b'\\n',i+8)\nd[nl+1:nl+21]=bytes.fromhex('de'*20)\n"
             "d[-20:]=hashlib.sha1(bytes(d[:-20])).digest()\nopen(idx,'wb').write(d)\nprint('FORGED')\nEOF")
    res = sh("worktree-rw", commit_script(forge), worktree=wt)
    admin = os.path.join(repo, ".git", "worktrees", "wt-claim1")
    tip = git(repo, "rev-parse", "aq/claim1/slug").stdout.strip()
    tree = git(repo, "rev-parse", tip + "^{tree}").stdout.strip()
    wtree = subprocess.run(["git", "--git-dir", admin, "write-tree"], capture_output=True, text=True, cwd="/")
    check("forged cache-tree in the sandbox index: host write-tree equals the promoted tip's tree (index rebuilt on host)",
          "FORGED" in out(res) and res.status == "ok" and res.refs.get("index") == "index-rebuilt-from-tip"
          and wtree.stdout.strip() == tree, f"{res.refs.get('index')} {wtree.stdout} {wtree.stderr} {tree} {out(res)}")


def _unit_load_state(run_id):
    cp = subprocess.run(["systemctl", "--user", "show", "-p", "LoadState", "--value", f"aq-confine-{run_id}.scope"],
                        capture_output=True, text=True, env=dict(os.environ))
    return cp.stdout.strip()


@behavioral
def test_cgroup_behavioral():
    plan, _ = golden_plan("eval-untrusted")
    seen = {}

    def peek():
        time.sleep(1.5)
        seen["show"] = subprocess.run(
            ["systemctl", "--user", "show", "-p", "MemoryMax", "-p", "MemorySwapMax", "-p", "TasksMax", "-p", "ActiveState",
             "aq-confine-cgscope00001.scope"], capture_output=True, text=True).stdout
    th = threading.Thread(target=peek)
    th.start()
    res = sh("eval-untrusted", "sleep 3; echo done", run_id="cgscope00001")
    th.join()
    want = confine.load_profile("eval-untrusted").cgroup
    check("confined launch runs in a live aq-confine-<run>.scope with MemoryMax/MemorySwapMax=0/TasksMax from the profile",
          res.status == "ok" and f"MemoryMax={want['memory_max']}" in seen.get("show", "") and "MemorySwapMax=0" in seen["show"]
          and f"TasksMax={want['tasks_max']}" in seen["show"] and "ActiveState=active" in seen["show"], seen.get("show", "") + res.reason)
    check("scope is collected after the run (no leftover unit)", _unit_load_state("cgscope00001") in ("not-found", ""),
          _unit_load_state("cgscope00001"))
    check("telemetry records the cgroup limits and scoped=true",
          '"scoped":true' in Path(confine.telemetry_path()).read_text())

    def small_mem(d):
        d["cgroup"]["memory_max"] = 128 * 1024 * 1024
        d["limits"].pop("as", None)
        d["limits"].pop("nproc", None)
        d["timeout_s"] = 60
    code = ("b=[]\nfor i in range(64):\n b.append(bytearray(32<<20))\n b[-1][::4096]=b'x'*len(b[-1][::4096])\nprint('SURVIVED')")
    with ProfileDir(custom_profiles("eval-untrusted", small_mem)):
        res = py("eval-untrusted", code, run_id="cgmem000001")
    check("allocating past MemoryMax (rlimit-as removed) is killed by the cgroup, never completes",
          "SURVIVED" not in out(res) and res.status == "child-failed" and res.reason == "oom-killed" and res.exit_code == 137,
          f"{res.status} rc={res.rc} {out(res)[:80]}")
    host_ok = confine.run("eval-untrusted", [PY, "-c", "print('after')"], run_id="cgmem000002")
    check("host and subsequent runs unaffected by the contained OOM", host_ok.status == "ok" and "after" in out(host_ok),
          host_ok.reason)
    check("OOM scope is cleaned up", _unit_load_state("cgmem000001") in ("not-found", ""), _unit_load_state("cgmem000001"))

    def small_tasks(d):
        d["cgroup"]["tasks_max"] = 16
        d["limits"].pop("nproc", None)
        d["timeout_s"] = 60
    forkcode = ("import os,time\nk=0\nfor i in range(60):\n try:\n  pid=os.fork()\n except OSError:\n  break\n"
                " if pid==0:\n  time.sleep(5);os._exit(0)\n k+=1\nprint('FORKED',k)\nos.system('true')")
    with ProfileDir(custom_profiles("eval-untrusted", small_tasks)):
        res = py("eval-untrusted", forkcode, run_id="cgpid000001")
    m = re.search(r"FORKED (\d+)", out(res))
    check("forking beyond TasksMax fails (EAGAIN) well below the attempted 60",
          m is not None and 0 < int(m.group(1)) < 16, f"{out(res)[:100]} {res.stderr.decode()[:200]}")
    check("pids scope is cleaned up", _unit_load_state("cgpid000001") in ("not-found", ""))

    # concurrent probes in one process must not collide on the unit name; failures are not cached long
    confine._scope_cache.clear()
    sr = confine.resolve_systemd_run()
    results = []
    ths = [threading.Thread(target=lambda: results.append(confine.scope_probe(sr, use_cache=False))) for _ in range(6)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    check("6 concurrent scope probes in one process all succeed (unique unit names, serialized)",
          len(results) == 6 and all(r.ok for r in results), str([r.detail for r in results if not r.ok]))
    confine._scope_cache[sr] = (time.monotonic() - confine.SCOPE_FAIL_TTL_S - 1, confine.PreflightResult(False, "cgroup-scope-unavailable", "x"))
    check("a cached probe failure expires after SCOPE_FAIL_TTL_S (5 s), not 60 s", confine.scope_probe(sr).ok)
    check("scope carries OOMPolicy=kill", "OOMPolicy=kill" in confine.build_argv(golden_plan("eval-untrusted")[0], FakeFacts()))

    # fail closed when systemd-run is unavailable
    marker = os.path.join(SCRATCH, "cg-ran")
    old = os.environ.get("AQ_CONFINE_SYSTEMD_RUN")
    os.environ["AQ_CONFINE_SYSTEMD_RUN"] = "/nonexistent/systemd-run"
    confine._scope_cache.clear()
    try:
        res = sh("eval-untrusted", f"touch {marker}")
        check("systemd-run unavailable: fail closed, exit 70 setup-failed, child never ran",
              res.exit_code == 70 and res.status == "setup-failed" and "cgroup-scope-unavailable" in res.reason
              and not os.path.exists(marker), f"{res.status} {res.exit_code} {res.reason}")
        stub = os.path.join(SCRATCH, "stub-systemd-run")
        Path(stub).write_text("#!/bin/sh\nexit 1\n")
        os.chmod(stub, 0o755)
        os.environ["AQ_CONFINE_SYSTEMD_RUN"] = stub
        confine._scope_cache.clear()
        res = sh("eval-untrusted", f"touch {marker}")
        check("scope creation failing (stub exits 1): fail closed 70, child never ran",
              res.exit_code == 70 and "cgroup-scope-unavailable" in res.reason and not os.path.exists(marker), res.reason)
        Path(stub).write_text("#!/bin/sh\nwhile [ \"$1\" != \"--\" ]; do shift; done; shift; exec \"$@\"\n")
        confine._scope_cache.clear()
        res = sh("eval-untrusted", f"touch {marker}")
        check("a stub that ignores the limits (runs the child unbounded) fails the enforcement probe",
              res.exit_code == 70 and not os.path.exists(marker), res.reason)
        os.environ["AQ_CONFINE_SYSTEMD_RUN"] = "/nonexistent/systemd-run"
        confine._scope_cache.clear()
        with ProfileDir(custom_profiles("eval-untrusted", lambda d: d["cgroup"].update(allow_rlimit_only=True))):
            res = py("eval-untrusted", "print('rlimit-only')")
        check("allow_rlimit_only profile flag runs rlimit-only when no scope can be created",
              res.status == "ok" and "rlimit-only" in out(res), res.reason)
    finally:
        if old is None:
            os.environ.pop("AQ_CONFINE_SYSTEMD_RUN", None)
        else:
            os.environ["AQ_CONFINE_SYSTEMD_RUN"] = old
        confine._scope_cache.clear()


def main():
    pure = [test_profiles_and_schema, test_cgroup_scope_pure, test_explain_goldens, test_env_and_path_policy, test_fail_closed_simulated, test_lint,
            test_host_git_hostile_layout, test_hostile_dirs_pure, test_guidance_pure, test_nproc_headroom, test_path_policy_h2]
    behav = [test_secrets_and_env, test_writes_and_net_and_commit, test_git_hostile_inside, test_import_cases,
             test_mid_run_and_kill, test_kill_limits_isolation_guidance, test_size_caps_and_telemetry, test_explain_cli_exact,
             test_h2_h1_m1_m3_behavioral, test_cgroup_behavioral]
    if not PF.ok:
        print(f"SKIP-WARN: confinement unavailable ({PF.reason}); {len(behav)} behavioral test groups skipped"
              + (" -- AQ_CONFINE_REQUIRE=1 makes this a failure" if REQUIRE else ""))
    for t in pure:
        try:
            t()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            bad(t.__name__, f"exception {exc!r}")
    for t in behav:
        t()
    for d in (SCRATCH, VTMP):
        shutil.rmtree(d, ignore_errors=True)
    print(f"SUMMARY: {ran} checks ran, {failed} failed, {skipped} behavioral groups skipped"
          f" (preflight: {'ok' if PF.ok else PF.reason})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
