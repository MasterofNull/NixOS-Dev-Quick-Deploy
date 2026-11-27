"""Resolve the shared delegation dir from the repo's MAIN worktree."""
import os
import subprocess
import sys
from pathlib import Path


VOLATILE_ROOTS = ("/tmp", "/var/tmp", "/dev/shm")


def refuse_volatile(path) -> Path:
    """Reject a derived path under a reboot-wiped dir; AQ_ALLOW_VOLATILE_DIR=1 is the test escape."""
    p = Path(path).resolve(strict=False)
    if os.environ.get("AQ_ALLOW_VOLATILE_DIR") != "1" and any(
            str(p) == r or str(p).startswith(r + "/") for r in VOLATILE_ROOTS):
        raise SystemExit(f"ERROR: {p} is under a volatile path (wiped on reboot); place work artifacts under .agents/delegation/ in a durable repo")
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


def validate_durable_artifact_path(
    path: str | Path,
    label: str = "artifact",
    delegation_dir: str | Path | None = None,
    script_dir: str | Path | None = None,
) -> Path:
    """Resolve an artifact and reject volatile or untracked work locations."""
    resolved = Path(path).resolve(strict=False)
    if os.environ.get("AQ_ALLOW_VOLATILE_DIR") == "1":
        return resolved
    scripts = Path(script_dir) if script_dir is not None else Path(__file__).resolve().parent.parent
    delegation = Path(delegation_dir) if delegation_dir is not None else resolve_delegation_dir(scripts)
    roots = (
        delegation,
        resolve_main_root(scripts) / ".agents" / "plans",
        Path(os.environ.get("CLAUDE_CODE_TMPDIR") or Path.home() / ".local/state/claude-code/tmp"),
    )
    volatile = tuple(Path(root) for root in VOLATILE_ROOTS)
    if not any(resolved.is_relative_to(root) for root in volatile):
        for candidate in roots:
            root = candidate.resolve(strict=False)
            if not any(root.is_relative_to(v) for v in volatile) and resolved.is_relative_to(root):
                return resolved
    print(
        f"ERROR: {label} {path} is outside durable work roots (wiped on reboot or untracked); "
        f"place work artifacts under .agents/delegation/ (e.g. {delegation}/outputs/) "
        "or ~/.local/state/claude-code/tmp",
        file=sys.stderr,
    )
    raise SystemExit(1)
