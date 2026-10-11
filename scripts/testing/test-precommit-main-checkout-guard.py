#!/usr/bin/env python3
"""Behavioural test: verify pre-commit refuses commits on main in primary checkout.

Verifies:
1. Commit on main in primary checkout is refused.
2. Commit on main in primary checkout with AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1 is allowed.
3. Commit on a feature branch is allowed.
4. Commit in a linked worktree (even on main or tracking main) is allowed.

Exits 0 and prints PASS on success.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def setup_temp_repo(temp_dir: Path) -> Path:
    repo_dir = temp_dir / "primary-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize repo with main branch
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test-agent@harness.local"], cwd=repo_dir, check=True)

    # Copy pre-commit hook from real repo into temp repo .githooks
    hooks_dir = repo_dir / ".githooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    real_hook = Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"
    dest_hook = hooks_dir / "pre-commit"
    shutil.copy2(real_hook, dest_hook)
    make_executable(dest_hook)

    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo_dir, check=True)

    # Stub scripts/ai/lib/integration_guard.py so it exits 0
    guard_stub = repo_dir / "scripts" / "ai" / "lib" / "integration_guard.py"
    guard_stub.parent.mkdir(parents=True, exist_ok=True)
    guard_stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n", encoding="utf-8")
    make_executable(guard_stub)

    # Stub scripts/governance checks so rest of hook succeeds when guard allows commit
    gov_dir = repo_dir / "scripts" / "governance"
    gov_dir.mkdir(parents=True, exist_ok=True)

    stub_scripts = [
        "run-focused-ci-checks.sh",
        "check-repo-allowlist-integrity.sh",
        "check-root-file-hygiene.sh",
        "check-generated-artifact-hygiene.sh",
        "check-doc-links.sh",
        "check-doc-metadata-standards.sh",
        "check-doc-script-path-migration.sh",
        "check-script-shim-consistency.sh",
        "check-archive-path-consistency.sh",
        "check-legacy-deprecated-root.sh",
    ]
    for s in stub_scripts:
        stub_file = gov_dir / s
        stub_file.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        make_executable(stub_file)

    return repo_dir


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        repo_dir = setup_temp_repo(temp_dir)

        base_env = os.environ.copy()
        base_env["SKIP_SECRET_SCAN"] = "1"
        base_env.pop("AQ_DELEGATE_HANDBACK", None)
        base_env.pop("AQ_ALLOW_MAIN_CHECKOUT_COMMIT", None)

        # -----------------------------------------------------------------
        # Test 1: Commit on main in primary checkout must be REFUSED
        # -----------------------------------------------------------------
        file1 = repo_dir / "file1.txt"
        file1.write_text("initial on main\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)

        res1 = run_cmd(["git", "commit", "-m", "attempt direct commit on main"], cwd=repo_dir, env=base_env)
        assert res1.returncode != 0, f"Expected commit on main to be refused, but succeeded:\n{res1.stdout}\n{res1.stderr}"
        assert "primary checkout are refused" in res1.stderr or "prohibited" in res1.stderr, (
            f"Expected refusal message in stderr, got:\n{res1.stderr}"
        )
        print("  [OK] Commit on main in primary checkout refused")

        # -----------------------------------------------------------------
        # Test 2: Commit on main in primary checkout with override must SUCCEED
        # -----------------------------------------------------------------
        override_env = base_env.copy()
        override_env["AQ_ALLOW_MAIN_CHECKOUT_COMMIT"] = "1"

        res2 = run_cmd(["git", "commit", "-m", "chore: initial commit on main with override"], cwd=repo_dir, env=override_env)
        assert res2.returncode == 0, f"Expected commit with override to succeed, failed:\n{res2.stdout}\n{res2.stderr}"
        print("  [OK] Commit on main with AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1 allowed")

        # -----------------------------------------------------------------
        # Test 3: Commit on a feature branch must SUCCEED
        # -----------------------------------------------------------------
        subprocess.run(["git", "checkout", "-b", "feat/my-slice"], cwd=repo_dir, check=True, capture_output=True)
        file2 = repo_dir / "file2.txt"
        file2.write_text("feature slice content\n", encoding="utf-8")
        subprocess.run(["git", "add", "file2.txt"], cwd=repo_dir, check=True, capture_output=True)

        res3 = run_cmd(["git", "commit", "-m", "feat: slice commit on feature branch"], cwd=repo_dir, env=base_env)
        assert res3.returncode == 0, f"Expected commit on feature branch to succeed, failed:\n{res3.stdout}\n{res3.stderr}"
        print("  [OK] Commit on feature branch allowed")

        # -----------------------------------------------------------------
        # Test 4: Commit in a linked worktree must SUCCEED (even on main)
        # -----------------------------------------------------------------
        # Switch primary repo to a different branch so main can be checked out in worktree
        subprocess.run(["git", "checkout", "-b", "primary-dev-branch"], cwd=repo_dir, check=True, capture_output=True)

        worktree_dir = temp_dir / "linked-worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_dir), "main"],
            cwd=repo_dir, check=True, capture_output=True,
        )

        file3 = worktree_dir / "file3.txt"
        file3.write_text("content inside linked worktree on main\n", encoding="utf-8")
        subprocess.run(["git", "add", "file3.txt"], cwd=worktree_dir, check=True, capture_output=True)

        res4 = run_cmd(["git", "commit", "-m", "feat: commit in linked worktree"], cwd=worktree_dir, env=base_env)
        assert res4.returncode == 0, f"Expected commit in linked worktree to succeed, failed:\n{res4.stdout}\n{res4.stderr}"
        print("  [OK] Commit in linked worktree (on main) allowed")

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
