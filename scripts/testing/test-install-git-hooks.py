#!/usr/bin/env python3
"""install-git-hooks.sh: heals absolute/foreign hooksPath to relative .githooks; refuses bare repos."""
import shutil
import subprocess
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
INST = "scripts/deploy/install-git-hooks.sh"

def sh(*a, cwd=None, ok=True):
    p = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    if ok:
        assert p.returncode == 0, (a, p.stdout, p.stderr)
    return p

def mk(root: Path):
    sh("git", "init", "-q", str(root))
    (root / ".githooks").mkdir()
    (root / ".githooks/pre-commit").write_text("#!/bin/sh\nexit 0\n")
    (root / "scripts/deploy").mkdir(parents=True)
    shutil.copy(SRC / INST, root / INST)

def hp(root):
    return sh("git", "-C", str(root), "config", "--get", "core.hooksPath", ok=False).stdout.strip()

with tempfile.TemporaryDirectory() as d:
    r = Path(d) / "r"; mk(r)
    sh("git", "-C", str(r), "config", "core.hooksPath", str(r / ".githooks"))
    p = sh("bash", str(r / INST), "--quiet")
    assert hp(r) == ".githooks" and "healed" in p.stderr, (hp(r), p.stderr)
    assert sh("bash", str(r / INST), "--quiet").stderr == ""  # idempotent, silent when already correct
    sh("git", "-C", str(r), "config", "core.hooksPath", "/dev/null")
    sh("bash", str(r / INST)); assert hp(r) == ".githooks"
    # linked worktree inherits the relative value and resolves to its OWN .githooks
    sh("git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
    w = Path(d) / "w"; sh("git", "-C", str(r), "worktree", "add", "-q", str(w))
    assert hp(w) == ".githooks"
    (w / ".githooks").mkdir(exist_ok=True)
    got = sh("git", "-C", str(w), "rev-parse", "--path-format=absolute", "--git-path", "hooks").stdout.strip()
    assert Path(got).resolve() == (w / ".githooks").resolve(), got
    # per-worktree override (extensions.worktreeConfig) shadows the shared value: effective value must heal
    sh("git", "-C", str(r), "config", "extensions.worktreeConfig", "true")
    (w / "scripts/deploy").mkdir(parents=True, exist_ok=True); shutil.copy(SRC / INST, w / INST)
    for bad in ("/dev/null", str(w / ".githooks")):
        sh("git", "-C", str(w), "config", "--worktree", "core.hooksPath", bad)
        assert hp(w) == bad, hp(w)
        p = sh("bash", str(w / INST), "--quiet")  # worktree's own copy, so REPO_ROOT is the worktree
        assert hp(w) == ".githooks" and "healed" in p.stderr, (bad, hp(w), p.stderr)
    # bare repo: refuse
    b = Path(d) / "b"; sh("git", "init", "-q", "--bare", str(b))
    (b / ".githooks").mkdir(); (b / "scripts/deploy").mkdir(parents=True); shutil.copy(SRC / INST, b / INST)
    p = sh("bash", str(b / INST), ok=False)
    assert p.returncode != 0 and "non-bare" in p.stderr, p.stderr
print("PASS")
