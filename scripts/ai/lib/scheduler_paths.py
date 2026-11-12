"""Where the slot queue keeps its state: one location for every reader and writer (shells, the
ai-prsi-rsi-dispatch unit, the dashboard, aq-local-training-loop).

Dependency-free on purpose: long-lived readers import this without pulling slot_queue's models.
The directory is a subdirectory of the MAIN checkout's .agents/delegation (a worktree resolves to
its main checkout), so the unit needs write access to this one directory only, and the flock in
it excludes unit-launched and shell-launched jobs against each other.
"""
from __future__ import annotations

import shutil
from pathlib import Path

STATE_NAME = "scheduler-state.json"
LOCK_NAME = "scheduler-state.lock"
RESERVATION_DIRNAME = "scheduler-lease-reservations"
SUBDIR = "scheduler"


def main_root(repo_root) -> Path:
    root = Path(repo_root)
    git = root / ".git"
    if git.is_file():  # linked worktree: "gitdir: <main>/.git/worktrees/<name>"
        try:
            gitdir = Path(git.read_text().split("gitdir:", 1)[1].strip())
            if gitdir.parent.name == "worktrees":
                return gitdir.parent.parent.parent
        except (OSError, IndexError):
            pass
    return root


def scheduler_dir(repo_root) -> Path:
    return main_root(repo_root) / ".agents" / "delegation" / SUBDIR


def state_file(repo_root) -> Path:
    return scheduler_dir(repo_root) / STATE_NAME


def legacy_state_file(repo_root) -> Path:
    return main_root(repo_root) / ".agents" / "delegation" / STATE_NAME


def read_path(repo_root) -> Path:
    """Path a reader should open: the shared file, or the pre-migration one until a writer has migrated it."""
    new = state_file(repo_root)
    if new.exists():
        return new
    old = legacy_state_file(repo_root)
    return old if old.exists() else new


def migrate_legacy(repo_root) -> None:
    """One-time: copy the old scheduler-state.json into the shared dir when the new file is absent. Call under the lock."""
    new, old = state_file(repo_root), legacy_state_file(repo_root)
    if not new.exists() and old.exists():
        tmp = new.with_suffix(".migrating")
        shutil.copyfile(old, tmp)
        tmp.replace(new)
