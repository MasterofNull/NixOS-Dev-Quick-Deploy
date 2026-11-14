"""Resolve the shared delegation dir from the repo's MAIN worktree."""
import os
import subprocess
import sys
from pathlib import Path


VOLATILE_ROOTS = ("/tmp", "/var/tmp", "/dev/shm")


def refuse_volatile(path) -> Path:
    """Reject a derived path under a reboot-wiped dir; AQ_ALLOW_VOLATILE_DIR=1 is the test escape."""
    p = Path(path)
    if os.environ.get("AQ_ALLOW_VOLATILE_DIR") != "1" and any(
            str(p) == r or str(p).startswith(r + "/") for r in VOLATILE_ROOTS):
        raise SystemExit(f"ERROR: {p} is under a volatile path (wiped on reboot); use a repo outside /tmp or set AQ_DELEGATION_DIR")
    return p


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
            return refuse_volatile(Path(common).parent / ".agents" / "delegation")
    except (OSError, subprocess.SubprocessError):
        pass
    print("WARN: git unavailable; delegation dir falls back to script-relative path", file=sys.stderr)
    return refuse_volatile(Path(script_dir).resolve().parent.parent / ".agents" / "delegation")


def resolve_main_root(script_dir) -> Path:
    """Main repo root (parent of git --git-common-dir); independent of AQ_DELEGATION_DIR and path depth."""
    try:
        common = subprocess.run(
            ["git", "-C", str(script_dir), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        if common:
            return Path(common).parent
    except (OSError, subprocess.SubprocessError):
        pass
    return Path(script_dir).resolve().parent.parent
