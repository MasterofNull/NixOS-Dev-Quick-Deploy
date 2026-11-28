#!/usr/bin/env python3
"""aq-main-sync: hermetic proof that it fast-forwards only when safe.

Each case builds a bare upstream + clone in a temp dir; no network, sudo or nix.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts/maintenance/aq-main-sync")
GUARD = os.path.join(ROOT, "scripts/governance/check-deploy-source.sh")
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print(f"FAIL: {msg}")


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True).stdout.strip()


def commit(d, path, text, msg):
    full = os.path.join(d, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a") as f:
        f.write(text)
    git(d, "add", path)
    git(d, "commit", "-qm", msg)


def fixture(tmp):
    bare, work, other = (os.path.join(tmp, n) for n in ("origin.git", "work", "other"))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
    for d in (work, other):
        subprocess.run(["git", "clone", "-q", bare, d], check=True, capture_output=True)
        git(d, "config", "user.email", "t@t")
        git(d, "config", "user.name", "t")
    os.makedirs(os.path.join(work, "scripts/governance"))
    shutil.copy(GUARD, os.path.join(work, "scripts/governance/check-deploy-source.sh"))
    git(work, "checkout", "-q", "-b", "main")
    commit(work, "app.py", "v1\n", "one")
    commit(work, ".agent/collaboration/PULSE.log", "a\n", "pulse")
    git(work, "add", "scripts")
    git(work, "commit", "-qm", "guard")
    git(work, "push", "-q", "origin", "main")
    git(other, "pull", "-q", "origin", "main")
    return work, other


def run(work, **env):
    e = {**os.environ, **env}
    r = subprocess.run(["bash", SCRIPT, "--repo", work], capture_output=True, text=True, env=e, timeout=60)
    return r.returncode, r.stdout + r.stderr


def upstream_advance(other, path="app.py"):
    commit(other, path, "more\n", "upstream")
    git(other, "push", "-q", "origin", "main")
    return git(other, "rev-parse", "HEAD")


def case(name, setup, expect_synced, reason=None, **env):
    with tempfile.TemporaryDirectory() as tmp:
        work, other = fixture(tmp)
        before = git(work, "rev-parse", "HEAD")
        new = upstream_advance(other)
        setup(work, other)
        head_pre = git(work, "rev-parse", "HEAD")
        rc, out = run(work, **env)
        head = git(work, "rev-parse", "HEAD")
        check(rc == 0, f"{name}: exit {rc}: {out}")
        if expect_synced:
            check(head == new and "synced" in out, f"{name}: expected fast-forward to {new}, got {head}: {out}")
            check(before[:8] in out and new[:8] in out, f"{name}: log line lacks before/after sha: {out}")
        else:
            check(head == head_pre and "skip:" in out, f"{name}: expected skip with HEAD unchanged: {out}")
            if reason:
                check(reason in out, f"{name}: reason '{reason}' missing: {out}")
        check(git(work, "stash", "list") == "", f"{name}: must never stash")


def dirty_file(path):
    def s(work, _o):
        with open(os.path.join(work, path), "a") as f:
            f.write("local edit\n")
    return s


case("clean and behind", lambda w, o: None, True)
case("dirty build-affecting", dirty_file("app.py"), False, "build-affecting")

def dirty_nix_md(work, _o):
    os.makedirs(os.path.join(work, "nix"), exist_ok=True)
    with open(os.path.join(work, "nix/x.md"), "w") as f:
        f.write("x\n")
    git(work, "add", "nix/x.md")  # tracked, build-affecting even though *.md


case("dirty nix/*.md", dirty_nix_md, False, "build-affecting")
case("only append-only dirty", dirty_file(".agent/collaboration/PULSE.log"), True)


def off_main(work, _o):
    git(work, "checkout", "-q", "-b", "feature")


case("not on main", off_main, False, "not main")


def diverged(work, _o):
    commit(work, "app.py", "local\n", "local commit")


case("diverged", diverged, False, "diverged")


def merging(work, _o):
    open(os.path.join(git(work, "rev-parse", "--absolute-git-dir"), "MERGE_HEAD"), "w").write(git(work, "rev-parse", "HEAD") + "\n")


case("operation in progress", merging, False, "in progress")
case("kill switch", lambda w, o: None, False, "kill switch", AQ_MAIN_SYNC="0")

# overlap: inert file dirty locally AND changed upstream -> git refuses, we skip without touching it
with tempfile.TemporaryDirectory() as tmp:
    work, other = fixture(tmp)
    upstream_advance(other, ".agent/collaboration/PULSE.log")
    dirty_file(".agent/collaboration/PULSE.log")(work, None)
    pre = git(work, "rev-parse", "HEAD")
    rc, out = run(work)
    check(rc == 0 and "skip:" in out and git(work, "rev-parse", "HEAD") == pre, f"overlap: {rc} {out}")
    check("local edit" in open(os.path.join(work, ".agent/collaboration/PULSE.log")).read(), "overlap: local edit lost")

# fetch fails (bogus remote URL) but local origin/main is ahead -> still fast-forwards, logs fallback
with tempfile.TemporaryDirectory() as tmp:
    work, other = fixture(tmp)
    new = upstream_advance(other)
    git(work, "fetch", "-q", "origin", "main")  # local origin/main now ahead of main
    git(work, "remote", "set-url", "origin", os.path.join(tmp, "does-not-exist.git"))
    rc, out = run(work)
    check(rc == 0 and git(work, "rev-parse", "HEAD") == new, f"fetch-fail fallback: {rc} {out}")
    check("fetch failed; using local origin/main" in out and "ago)" in out and "synced" in out, f"fallback log: {out}")

# fetch fails and no local origin/main ref -> skip
with tempfile.TemporaryDirectory() as tmp:
    work, other = fixture(tmp)
    git(work, "update-ref", "-d", "refs/remotes/origin/main")
    git(work, "remote", "set-url", "origin", os.path.join(tmp, "does-not-exist.git"))
    rc, out = run(work)
    check(rc == 0 and "skip: fetch failed and no local origin/main" in out, f"no ref: {rc} {out}")

if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("OK: test-aq-main-sync")
