#!/usr/bin/env python3
"""aq-deploy-current --rev: refuse unless HEAD after the pull is exactly the requested revision.

Runs the real script inside a throwaway primary checkout whose origin is a local bare repo. The
guard scripts are stubs that exit 1, so a run that gets PAST the --rev gate stops at
"check-deploy-source.sh failed" with nothing built. No sudo, nix or network.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts/maintenance/aq-deploy-current")
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print(f"FAIL: {msg}")


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True).stdout.strip()


def fixture(tmp):
    bare, work = os.path.join(tmp, "origin.git"), os.path.join(tmp, "work")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
    subprocess.run(["git", "clone", "-q", bare, work], check=True, capture_output=True)
    git(work, "config", "user.email", "t@t"); git(work, "config", "user.name", "t")
    os.makedirs(os.path.join(work, "scripts/maintenance")); os.makedirs(os.path.join(work, "scripts/governance"))
    shutil.copy(SCRIPT, os.path.join(work, "scripts/maintenance/aq-deploy-current"))
    with open(os.path.join(work, "scripts/governance/check-deploy-source.sh"), "w") as f:
        f.write("#!/bin/sh\ninert_re='^docs/'\nexit 1\n")
    os.chmod(os.path.join(work, "scripts/governance/check-deploy-source.sh"), 0o755)
    git(work, "checkout", "-q", "-b", "main"); git(work, "add", "-A"); git(work, "commit", "-qm", "one")
    git(work, "push", "-q", "origin", "main")
    first = git(work, "rev-parse", "HEAD")
    git(work, "commit", "-q", "--allow-empty", "-m", "two"); git(work, "push", "-q", "origin", "main")
    git(work, "reset", "-q", "--hard", first)
    return work, first, subprocess.run(["git", "-C", bare, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()


def deploy(work, *args):
    r = subprocess.run(["bash", os.path.join(work, "scripts/maintenance/aq-deploy-current"), *args],
                       capture_output=True, text=True, cwd=work, timeout=60)
    return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as tmp:
    work, old, new = fixture(tmp)
    rc, out = deploy(work, "--rev", old)  # pull moves HEAD to `new`, so the requested old rev must be refused
    check(rc == 1 and "not the requested --rev" in out and "check-deploy-source" not in out, (rc, out))
    check(git(work, "rev-parse", "HEAD") == new, "pull should still have fast-forwarded")
    rc, out = deploy(work, "--rev", new)  # exact match gets past the gate (then stops at the stub guard)
    check(rc == 1 and "check-deploy-source.sh failed" in out and "requested --rev" not in out, (rc, out))
    rc, out = deploy(work, f"--rev={new}")
    check("check-deploy-source.sh failed" in out and "requested --rev" not in out, (rc, out))
    rc, out = deploy(work)  # no flag: unchanged behaviour
    check(rc == 1 and "check-deploy-source.sh failed" in out and "requested --rev" not in out, (rc, out))
    for bad in (["--rev"], ["--rev", "abc123"], ["--rev", new.upper()], ["--rev", ""]):
        rc, out = deploy(work, *bad)
        check(rc == 2 and "--rev" in out, (bad, rc, out))

body = open(SCRIPT).read()
check("((HAVE_REV)) && [[ \"$(git rev-parse HEAD)\" != \"$WANT_REV\" ]]" in body
      and body.index("git pull --ff-only") < body.index("((HAVE_REV)) && [[ \"$(git rev-parse HEAD)\"") < body.index("pre-rebuild-preflight.sh failed"),
      "the --rev check must sit after the pull and before any guard or rebuild")
check("--rev" in open(os.path.join(ROOT, "scripts/maintenance/aq-update")).read(), "aq-update must pass --rev")
print("FAILED" if fails else f"test-aq-deploy-current-rev: all checks passed")
sys.exit(1 if fails else 0)
