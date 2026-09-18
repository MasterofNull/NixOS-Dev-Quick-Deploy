#!/usr/bin/env python3
"""CS-4 concurrent-dispatch isolation proof.

.agents/plans/coordination-safety-worktree-isolation/DESIGN.md — CS-4 "validate"
phase. Proves that two concurrently-dispatched delegated worktrees (created via
scripts/ai/lib/worktree-isolation.sh, the same helper delegate-to-codex /
delegate-to-local source) never contend on the SHARED repo's git index or
working tree, that their handed-back patches never cross-contaminate each
other's files, and that both patches apply cleanly and independently onto the
shared base. Also re-proves the single-lane wt_create/wt_handback cycle is
unaffected (regression).

Hermetic: no network, no real LLM — a throwaway git repo in a tempdir, the
isolation helper sourced directly in bash (mirrors
scripts/testing/test-worktree-isolation.py's style: subprocess + tempfile, no
pytest). Deterministic and fast.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/ai/lib/worktree-isolation.sh"
GIT = shutil.which("git")
assert GIT, "git is required for this fixture"


def run(args, *, cwd=None, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError(f"command failed ({result.returncode}): {args}\n{result.stderr}")
    return result


def bash(script, *, check=True):
    return run(["bash", "-c", script], check=check)


def git(repo, *args, check=True):
    return run([GIT, "-C", str(repo), *args], check=check)


run(["bash", "-n", str(HELPER)])

with tempfile.TemporaryDirectory(prefix="concurrent-dispatch-") as temp:
    repo = Path(temp) / "repo"
    git(Path(temp), "init", "-q", str(repo))
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-qm", "base")
    shared_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    print(f"PASS: base repo initialized, shared HEAD={shared_head[:12]}")

    def index_and_tree_clean() -> bool:
        """Shared repo's index has nothing staged, tracked files are
        unmodified, and no lane's file (file-a.txt/file-b.txt/new-*.txt)
        leaked into the shared checkout. `.agents/` is excluded from the
        top-level scan by design: that's where isolated worktrees are
        nested (wt_root), not lane content leaking into the shared tree —
        CS-1's own hermetic test uses the same layout."""
        if git(repo, "diff", "--cached", "--quiet", check=False).returncode != 0:
            return False
        if git(repo, "diff", "--quiet", check=False).returncode != 0:
            return False
        names = sorted(p.name for p in repo.iterdir() if p.name not in (".git", ".agents"))
        if names != ["base.txt"]:
            return False
        if (repo / "base.txt").read_text() != "base\n":
            return False
        for leaked in ("file-a.txt", "file-b.txt", "new-a.txt", "new-b.txt", "solo.txt"):
            if (repo / leaked).exists():
                return False
        return True

    assert index_and_tree_clean(), "shared repo dirty before any dispatch"

    # --- Step 2: two concurrent isolated worktrees -------------------------
    wt_a = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-a').stdout.strip())
    assert index_and_tree_clean(), "shared repo touched by wt_create(task-a)"
    wt_b = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-b').stdout.strip())
    assert index_and_tree_clean(), "shared repo touched by wt_create(task-b)"
    assert wt_a.is_dir() and wt_b.is_dir()
    assert wt_a != wt_b
    print("PASS: two isolated worktrees created (task-a, task-b)")

    base_a = git(repo, "rev-parse", "refs/delegate-base/task-a").stdout.strip()
    base_b = git(repo, "rev-parse", "refs/delegate-base/task-b").stdout.strip()
    assert base_a == shared_head == base_b, "both lanes must dispatch from the same shared HEAD"

    # --- Step 3: interleaved, disjoint edits in each lane -------------------
    # Interleave a/b/a/b to simulate genuine concurrency rather than
    # sequential lane completion.
    (wt_a / "file-a.txt").write_text("lane a, edit 1\n")
    assert index_and_tree_clean(), "shared repo touched by lane-a edit 1"

    (wt_b / "file-b.txt").write_text("lane b, edit 1\n")
    assert index_and_tree_clean(), "shared repo touched by lane-b edit 1"

    (wt_a / "file-a.txt").write_text("lane a, edit 1\nlane a, edit 2\n")
    (wt_a / "new-a.txt").write_text("new file from lane a\n")
    assert index_and_tree_clean(), "shared repo touched by lane-a edit 2"

    (wt_b / "file-b.txt").write_text("lane b, edit 1\nlane b, edit 2\n")
    (wt_b / "new-b.txt").write_text("new file from lane b\n")
    assert index_and_tree_clean(), "shared repo touched by lane-b edit 2"
    print("PASS: interleaved edits (a, b, a, b) never touched the shared index/worktree")

    # --- Step 4: independent handback ---------------------------------------
    # Mirrors production layout: delegate-to-codex/delegate-to-local hand back
    # patches under DELEGATION_DIR/outputs, i.e. nested under .agents/ same as
    # the worktrees themselves — never a bare top-level dir in the shared tree.
    outputs_a = repo / ".agents" / "delegation" / "outputs-a"
    outputs_b = repo / ".agents" / "delegation" / "outputs-b"
    bash(f'source "{HELPER}"; wt_handback "{repo}" "{wt_a}" task-a "{outputs_a}"')
    assert index_and_tree_clean(), "shared repo touched by wt_handback(task-a)"
    bash(f'source "{HELPER}"; wt_handback "{repo}" "{wt_b}" task-b "{outputs_b}"')
    assert index_and_tree_clean(), "shared repo touched by wt_handback(task-b)"

    patch_a_file = outputs_a / "task-a.patch"
    patch_b_file = outputs_b / "task-b.patch"
    assert patch_a_file.exists() and patch_b_file.exists()
    patch_a = patch_a_file.read_text()
    patch_b = patch_b_file.read_text()
    print("PASS: both lanes handed back independent patch files")

    # --- Step 5: shared index/worktree stayed clean throughout -------------
    assert index_and_tree_clean(), "shared repo dirty after both handbacks"
    print("PASS: shared repo index+worktree clean throughout both dispatches")

    # --- Step 6: no cross-contamination between patches ---------------------
    assert "file-a.txt" in patch_a and "new-a.txt" in patch_a
    assert "file-b.txt" not in patch_a and "new-b.txt" not in patch_a
    assert "file-b.txt" in patch_b and "new-b.txt" in patch_b
    assert "file-a.txt" not in patch_b and "new-a.txt" not in patch_b
    print("PASS: patches contain only their own lane's files (no cross-contamination)")

    # --- Step 7: both patches apply cleanly and independently onto shared HEAD
    apply_check = Path(temp) / "apply-check"
    git(Path(temp), "clone", "-q", str(repo), str(apply_check))
    git(apply_check, "checkout", "-q", shared_head)
    git(apply_check, "apply", "--check", "--binary", str(patch_a_file))
    git(apply_check, "apply", "--binary", str(patch_a_file))
    git(apply_check, "apply", "--check", "--binary", str(patch_b_file))
    git(apply_check, "apply", "--binary", str(patch_b_file))
    assert (apply_check / "file-a.txt").exists()
    assert (apply_check / "file-b.txt").exists()
    assert (apply_check / "new-a.txt").exists()
    assert (apply_check / "new-b.txt").exists()
    print("PASS: both patches apply cleanly and independently onto shared HEAD (disjoint files)")

    # --- Step 8: single-lane wt_create/wt_handback cycle regression --------
    wt_solo = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-solo').stdout.strip())
    assert index_and_tree_clean(), "shared repo touched by wt_create(task-solo)"
    (wt_solo / "solo.txt").write_text("solo lane\n")
    outputs_solo = repo / ".agents" / "delegation" / "outputs-solo"
    bash(f'source "{HELPER}"; wt_handback "{repo}" "{wt_solo}" task-solo "{outputs_solo}"')
    assert index_and_tree_clean(), "shared repo touched by wt_handback(task-solo)"
    patch_solo = (outputs_solo / "task-solo.patch").read_text()
    assert "solo.txt" in patch_solo
    print("PASS: single-lane wt_create/wt_handback cycle unaffected (regression clean)")

print("PASS: concurrent-dispatch isolation — zero shared-index contention, zero cross-contamination")
