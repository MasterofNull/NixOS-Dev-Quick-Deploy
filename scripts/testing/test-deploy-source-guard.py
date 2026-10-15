#!/usr/bin/env python3
"""Tests for scripts/governance/check-deploy-source.sh using temp git repos (bare origin + clone)."""
import os
import subprocess
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "governance/check-deploy-source.sh"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
ENV.pop("AQ_DEPLOY_ALLOW_BRANCH", None)


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True, env=ENV).stdout


def make(d):
    origin, work = Path(d) / "origin.git", Path(d) / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    git(work, "checkout", "-q", "-b", "main")
    for f in ("flake.nix", "docs/a.md", ".agent/memory/log.md"):
        (work / f).parent.mkdir(parents=True, exist_ok=True)
        (work / f).write_text("x\n")
    git(work, "add", "-A"); git(work, "commit", "-q", "-m", "i"); git(work, "push", "-q", "origin", "main")
    return origin, work


def run(work, **env):
    e = dict(ENV, AQ_DEPLOY_GUARD_LOG=str(Path(work).parent / "guard.log"), **env)
    p = subprocess.run(["bash", str(GUARD), str(work)], capture_output=True, text=True, env=e)
    return p.returncode, p.stderr


def check(name, cond, info=""):
    assert cond, f"FAIL {name}: {info}"
    print(f"ok - {name}")


with tempfile.TemporaryDirectory() as d:
    origin, work = make(d)

    rc, err = run(work)
    check("main+clean+in-sync passes", rc == 0 and "OK" in err, err)

    (work / "docs/a.md").write_text("changed\n"); (work / ".agent/memory/log.md").write_text("changed\n")
    rc, err = run(work)
    check("inert-dirty warns and passes", rc == 0 and "inert files" in err and "dirtyRev" in err, err)
    git(work, "checkout", "--", ".")

    (work / "flake.nix").write_text("changed\n")
    rc, err = run(work)
    check("build-dirty blocks", rc == 4 and "affect the build" in err and "flake.nix" in err, err)
    rc, err = run(work, AQ_DEPLOY_ALLOW_BRANCH="1")
    check("override passes build-dirty with loud warning + log", rc == 0 and "AQ_DEPLOY_ALLOW_BRANCH=1" in err
          and "override" in (Path(d) / "guard.log").read_text())
    git(work, "checkout", "--", ".")

    git(work, "checkout", "-q", "-b", "feat/x")
    rc, err = run(work)
    check("feature branch fails with fix commands", rc == 4 and "not main" in err and "switch main" in err
          and "pull --ff-only" in err, err)
    rc, err = run(work, AQ_DEPLOY_ALLOW_BRANCH="1")
    check("feature branch override passes with warning", rc == 0 and "NON-CANONICAL" in err, err)
    git(work, "checkout", "-q", "main")

    other = Path(d) / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True, capture_output=True)
    (other / "new.txt").write_text("n\n"); git(other, "add", "-A"); git(other, "commit", "-q", "-m", "n"); git(other, "push", "-q", "origin", "main")
    rc, err = run(work)
    check("behind origin fails", rc == 4 and "1 behind" in err, err)
    git(work, "pull", "-q", "--ff-only", "origin", "main")

    git(work, "remote", "set-url", "origin", str(Path(d) / "does-not-exist.git"))
    rc, err = run(work)
    check("offline fetch blocks and prints the fetch error", rc == 4 and "cannot be proven up to date" in err
          and "does-not-exist" in err, err)
    rc, err = run(work, AQ_DEPLOY_OFFLINE="1")
    check("offline + AQ_DEPLOY_OFFLINE=1 passes with banner + log", rc == 0 and "cannot prove up to date; deploying cached origin/main" in err
          and "offline deploy" in (Path(d) / "guard.log").read_text(), err)
    (work / "flake.nix").write_text("changed\n")
    rc, err = run(work, AQ_DEPLOY_OFFLINE="1")
    check("offline + dirty build still blocked", rc == 4 and "affect the build" in err, err)
    rc, err = run(work, AQ_DEPLOY_ALLOW_BRANCH="1")
    check("offline + ALLOW_BRANCH override passes", rc == 0, err)
print("PASS")
