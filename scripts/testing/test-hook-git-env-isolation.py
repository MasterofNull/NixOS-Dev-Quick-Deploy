#!/usr/bin/env python3
"""Guard: hook/tier0 test launches must not leak repo-locating GIT_* into child tests.

Incident 2026-10-28: a test run under a git hook inherited GIT_DIR/GIT_INDEX_FILE and its
temp-repo git init/add/commit acted on the real repository. Uses a decoy repo only.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/governance/lib/clean-git-env.sh"
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
BASE_ENV.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

CHILD = (
    "set -e; d=$(mktemp -d); cd \"$d\"; git init -q .; echo x > f; git add f; "
    "git commit -q -m child; git rev-parse --show-toplevel"
)


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, env=BASE_ENV, check=True).stdout.strip()


def snapshot(repo):
    return (git(repo, "rev-parse", "HEAD"), git(repo, "config", "core.bare"),
            git(repo, "branch", "--list"), git(repo, "status", "--porcelain"))


def run_runtime_check():
    with tempfile.TemporaryDirectory(prefix="hook-git-env-") as tmp:
        decoy = Path(tmp) / "decoy"
        decoy.mkdir()
        git(decoy, "init", "-q", "-b", "main")
        (decoy / "a").write_text("a")
        git(decoy, "add", "a")
        git(decoy, "commit", "-q", "-m", "decoy")
        before = snapshot(decoy)
        env = dict(BASE_ENV, GIT_DIR=str(decoy / ".git"), GIT_WORK_TREE=str(decoy),
                   GIT_INDEX_FILE=str(decoy / ".git/index"))
        # Python helper
        sys.path.insert(0, str(ROOT / "scripts/governance/lib"))
        from clean_git_env import clean_git_env
        cleaned = clean_git_env(env)
        assert not any(k.startswith("GIT_DIR") or k in ("GIT_WORK_TREE", "GIT_INDEX_FILE") for k in cleaned), "py helper leaked"
        assert cleaned.get("GIT_AUTHOR_NAME") == "t", "py helper must keep non-locating GIT_* vars"
        for label, cmd, kw in (
            ("bash", ["bash", "-c", f'source "{HELPER}"; clean_git_env_run bash -c \'{CHILD}\''], {"env": env}),
            ("python", ["bash", "-c", CHILD], {"env": cleaned}),
        ):
            r = subprocess.run(cmd, capture_output=True, text=True, **kw)
            assert r.returncode == 0, f"{label} child failed: {r.stderr}"
            top = os.path.realpath(r.stdout.strip().splitlines()[-1])
            assert not top.startswith(os.path.realpath(str(decoy))), f"{label}: child repo is the decoy"
            assert top.startswith(os.path.realpath(tempfile.gettempdir())), f"{label}: child repo outside tmp: {top}"
            assert snapshot(decoy) == before, f"{label}: decoy repo changed"
        # Negative control: without scrubbing, the decoy IS hit (proves the test can fail).
        r = subprocess.run(["bash", "-c", CHILD], capture_output=True, text=True, env=env)
        top = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        hit = r.returncode != 0 or snapshot(decoy) != before or os.path.realpath(top).startswith(os.path.realpath(str(decoy)))
        assert hit, "negative control: unscrubbed env did not affect decoy; test is not exercising the hazard"


def run_static_checks():
    gov = ROOT / "scripts/governance"
    tier0 = (gov / "tier0-validation-gate.sh").read_text()
    assert "lib/clean-git-env.sh" in tier0, "tier0 does not source helper"
    # Every launch of a test script/QA runner in tier0 must go through the helper.
    for i, line in enumerate(tier0.splitlines(), 1):
        code = line.split("#", 1)[0]
        if re.search(r"python3\s+(\"\$\{test_script\}\"|scripts/testing/)|verify-flake-first-roadmap-completion\.sh\"|scripts/ai/aq-qa\"", code):
            assert "clean_git_env_run" in code, f"tier0.sh:{i} launches tests without helper: {line.strip()}"
    for name, needle in (
        ("run-ci-checks.sh", "clean_git_env()"),
        ("run-focused-ci-checks.sh", "env=clean_git_env()"),
    ):
        assert needle in (gov / name).read_text(), f"{name} missing helper use"
    par = (gov / "ci-merge-parity.sh").read_text()
    assert par.count("clean_git_env_run ./scripts/governance/run-ci-checks.sh") == 1 and "clean_git_env_run bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh" in par
    push = (ROOT / ".githooks/pre-push").read_text()
    assert "clean_git_env_run ./scripts/governance/ci-merge-parity.sh" in push and "clean_git_env_run ./scripts/governance/run-ci-checks.sh" in push


if __name__ == "__main__":
    run_runtime_check()
    run_static_checks()
    print("PASS: hook git-env isolation")
