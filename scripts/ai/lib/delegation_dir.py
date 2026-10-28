"""Resolve the shared delegation dir from the repo's MAIN worktree."""
import os
import subprocess
import sys
from pathlib import Path


def resolve_delegation_dir(script_dir) -> Path:
    override = os.environ.get("AQ_DELEGATION_DIR")
    if override:
        return Path(override)
    try:
        common = subprocess.run(
            ["git", "-C", str(script_dir), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        if common:
            return Path(common).parent / ".agents" / "delegation"
    except (OSError, subprocess.SubprocessError):
        pass
    print("WARN: git unavailable; delegation dir falls back to script-relative path", file=sys.stderr)
    return Path(script_dir).resolve().parent.parent / ".agents" / "delegation"
