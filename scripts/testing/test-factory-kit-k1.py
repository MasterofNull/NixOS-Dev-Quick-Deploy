#!/usr/bin/env python3
"""K1 regression proof: kit blockers B1, B2, B5, B17, B18 and the commit-msg behavior matrix."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import factory_gate_install as fgi  # noqa: E402

BUNDLE = ROOT / "templates/factory-gate-bundle"
INSTALLER = ROOT / "scripts/ai/lib/factory_gate_install.py"
LEAKS = re.compile(r"/home/|/run/current-system|MasterofNull|hyperd|@gmail\.com|noreply\.github\.com")


def sh(*cmd: str, cwd: Path | None = None, env: dict | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, text=True, capture_output=True, check=False)
    if ok and r.returncode:
        raise AssertionError(f"{cmd} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def new_repo(base: Path, name: str) -> Path:
    repo = base / name
    repo.mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    sh("git", "config", "user.email", "author@example.test", cwd=repo)
    sh("git", "config", "user.name", "Author", cwd=repo)
    return repo


def test_export_scan() -> None:  # B1
    hits = [f"{p.relative_to(BUNDLE)}:{n}" for p in BUNDLE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1) if LEAKS.search(line)]
    assert not hits, f"host/maintainer identity in bundle: {hits}"


def test_owner_handle() -> None:  # B2
    _, entries = fgi.manifest_entries(BUNDLE)
    entry = next(e for e in entries if e["install_target"] == ".github/CODEOWNERS")
    src = BUNDLE / entry["bundle_path"]
    os.environ["FACTORY_OWNER_HANDLE"] = "example-user"
    text = fgi.rendered(src, fgi.render_values("p", {})).decode()
    assert text.strip() == "* @example-user", text
    assert not LEAKS.search(text)
    del os.environ["FACTORY_OWNER_HANDLE"]
    for bad in ("evil\nuser", "bad user", "x;rm"):
        os.environ["FACTORY_OWNER_HANDLE"] = bad
        assert fgi.owner_handle() == fgi.OWNER_HANDLE_UNSET, bad
        assert any("unset or invalid" in h for h in fgi.install_hints([]))
    del os.environ["FACTORY_OWNER_HANDLE"]
    assert any(h.startswith("build:") and "configure the build command" in h for h in fgi.install_hints(["build: x"]))
    with tempfile.TemporaryDirectory() as empty:
        old = os.environ["PATH"]
        os.environ["PATH"] = empty
        try:
            assert fgi.owner_handle() == fgi.OWNER_HANDLE_UNSET
            assert any("OWNER_HANDLE unset" in h for h in fgi.install_hints([]))
        finally:
            os.environ["PATH"] = old


def test_receipt_and_router_and_hints(base: Path) -> None:  # B17, B18
    repo = new_repo(base, "greenfield")
    nobin = base / "nogitleaks"
    nobin.mkdir()
    for tool in ("git", "sh", "bash", "env"):
        (nobin / tool).symlink_to(shutil.which(tool))
    out = sh(sys.executable, str(INSTALLER), "install", "--target", str(repo), "--bundle-root", str(BUNDLE),
             "--project-name", "k1", "--stack", "generic", env={"FACTORY_OWNER_HANDLE": "example-user", "PATH": str(nobin)})
    receipt_text = (repo / ".factory/gate-install.json").read_text()
    receipt = json.loads(receipt_text)
    assert receipt["target"] == "." and str(base) not in receipt_text
    assert receipt["checks"]["state"] == "CONFIGURATION_BLOCKED"
    assert any("gitleaks" in h for h in receipt["checks"]["install_hints"]), receipt["checks"]
    assert "@example-user" in (repo / ".github/CODEOWNERS").read_text()
    assert oct((repo / ".factory/gate-install.json").stat().st_mode & 0o777) == "0o644"
    del out
    # router: no baked path, resolves root at runtime, works from a clone at another path
    router = fgi.router_script(repo, "pre-commit", True).decode()
    assert str(repo) not in router and "git rev-parse --show-toplevel" in router
    moved = new_repo(base, "moved")
    (moved / ".factory/gate-retrofit-hooks").mkdir(parents=True)
    hook = moved / ".factory/gate-retrofit-hooks/pre-commit"
    hook.write_text("#!/usr/bin/env bash\necho ran-at \"$(pwd)\"\n")
    hook.chmod(0o755)
    rfile = moved / "router"
    rfile.write_bytes(router.encode())
    rfile.chmod(0o755)
    run = sh(str(rfile), cwd=moved)
    assert "ran-at" in run.stdout and str(moved.resolve()) in run.stdout, run.stdout
    # real linked worktree: --git-common-dir hook lookup
    sh("git", "add", "-A", cwd=moved)
    sh("git", "commit", "-qm", "base", cwd=moved)
    (moved / ".git/hooks").mkdir(exist_ok=True)
    orig = moved / ".git/hooks/pre-commit"
    orig.write_text("#!/usr/bin/env bash\necho original-hook-ran\n")
    orig.chmod(0o755)
    linked = base / "linked"
    sh("git", "worktree", "add", "-q", "-b", "wt", str(linked), cwd=moved)
    run = sh(str(rfile), cwd=linked)
    assert "original-hook-ran" in run.stdout and f"ran-at {linked.resolve()}" in run.stdout, run.stdout
    # gate-runner: missing risk classifier is announced, not fatal
    gate = BUNDLE / "gate-runner"
    r = sh("bash", str(gate), "--pre-commit", cwd=moved, env={"FACTORY_RISK_TIER_CMD": str(base / "no-such-aq-risk-tier"),
                                                              "FACTORY_REPO_ROOT": str(moved)}, ok=False)
    assert "risk classifier not installed" in r.stderr, r.stderr


def test_commit_msg_matrix(base: Path) -> None:
    repo = new_repo(base, "cm")
    sh("git", "commit", "-q", "--allow-empty", "-m", "init", cwd=repo)
    hook = base / "commit-msg"  # rendered as the installer does
    hook.write_bytes(fgi.rendered(BUNDLE / "hooks/commit-msg", fgi.render_values("p", {})))
    env: dict = {}

    def stage(name: str) -> None:
        (repo / name).write_text(name + "\n")
        sh("git", "add", name, cwd=repo)

    def run(branch: str, msg: str, staged: bool = True) -> int:
        sh("git", "checkout", "-q", "-B", branch, cwd=repo)
        sh("git", "reset", "-q", cwd=repo)
        if staged:
            stage("f-" + hashlib.md5((branch + msg).encode()).hexdigest()[:8])
        mf = base / "msg"
        sha = hashlib.sha256(sh("git", "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--", cwd=repo).stdout.encode()).hexdigest()
        mf.write_text(msg.replace("SHA", sha))
        return sh("bash", str(hook), str(mf), cwd=repo, env=env, ok=False).returncode

    good = ("feat: x\n\nReview-Disposition: ACCEPTED\nIndependent-Review: PASS\nReviewed-subject-sha256: SHA\n"
            "Reviewed-by: Reviewer <reviewer@example.test>\n")
    assert run("feature/x", "feat: x\n") == 0
    assert run("main", "feat: x\n", staged=False) == 0
    for branch in ("main", "master", "trunk"):
        assert run(branch, "feat: x\n") == 1, branch
        assert run(branch, good) == 0, branch
    assert run("main", good.replace("Independent-Review: PASS\n", "")) == 1
    assert run("main", good.replace("reviewer@example.test", "author@example.test")) == 1
    assert run("main", good.replace("Reviewed-subject-sha256: SHA", "Reviewed-subject-sha256: " + "0" * 64)) == 1
    assert run("main", good.replace("ACCEPTED", "REJECTED")) == 1
    assert run("main", good.replace("ACCEPTED", "ACTIVATION_BLOCKED")) == 1
    assert run("main", good.replace("ACCEPTED", "IMPLEMENTED_FOLLOWUP_REQUIRED")) == 1
    follow = good.replace("ACCEPTED", "IMPLEMENTED_FOLLOWUP_REQUIRED") + "Safe-At-Rest: true\nActivation-Authority: false\nNext-Slice: k2\n"
    assert run("main", follow) == 0
    assert run("main", good + "Integration-State: provisional\n") == 1


def main() -> int:
    test_export_scan()
    test_owner_handle()
    with tempfile.TemporaryDirectory(prefix="factory-k1 ") as t:
        base = Path(t)
        test_receipt_and_router_and_hints(base)
        test_commit_msg_matrix(base)
    print("PASS: factory kit K1 (B1 scan, B2 owner handle, B17 receipt/router, B18 hints, commit-msg matrix)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
