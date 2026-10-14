#!/usr/bin/env python3
"""Local pre-commit hook + tier0 check must match CI gitleaks (.gitleaks.toml)."""
import os, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".githooks/pre-commit"
CHECK = ROOT / "scripts/governance/tier0.d/check-gitleaks-ci-parity.sh"
assert shutil.which("gitleaks"), "gitleaks required"

def g(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)

def scan(repo):
    src = HOOK.read_text()
    start = src.index("run_secret_scan() {")
    end = src.index("\nrun_shell_validation()")
    script = src[start:end] + "\nrun_secret_scan\n"
    env = dict(os.environ); env.pop("SKIP_SECRET_SCAN", None)
    return subprocess.run(["bash", "-c", script], cwd=repo, env=env, capture_output=True, text=True)

def stage(repo, rel, text):
    f = repo / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
    g(repo, "add", rel)

with tempfile.TemporaryDirectory() as d:
    repo = Path(d); g(repo, "init", "-q")
    shutil.copy(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
    bad = '{"GITHUB_TOKEN": "ghp_secret123"}\n'
    stage(repo, "scripts/ai/aq-fake", f'cfg = {bad}')
    p = scan(repo); assert p.returncode != 0 and "unknown flag" not in p.stderr, ("must block", p.stdout, p.stderr)
    g(repo, "reset", "-q")
    stage(repo, "scripts/ai/aq-fake", 'cfg = {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}\n')
    p = scan(repo); assert p.returncode == 0, ("placeholder must pass", p.stdout, p.stderr)
    g(repo, "reset", "-q")
    stage(repo, "scripts/testing/test-fake.py", f'cfg = {bad}')
    p = scan(repo); assert p.returncode == 0, ("allowlisted path must pass", p.stdout, p.stderr)
    (repo / "scripts/ai").mkdir(parents=True, exist_ok=True)
    (repo / "scripts/ai/aq-fake").write_text(f'cfg = {bad}')
    env = dict(os.environ, GITLEAKS_PARITY_ROOT=str(repo))
    p = subprocess.run(["bash", str(CHECK), "--pre-commit"], env=env, capture_output=True, text=True)
    assert p.returncode == 1, ("tier0 check must fail", p.stdout, p.stderr)
print("PASS")
