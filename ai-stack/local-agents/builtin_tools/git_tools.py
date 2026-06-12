#!/usr/bin/env python3
"""
Built-in Git Tools for Local Agents

Provides safe git operations for the local agent coding loop:
- git_status: Show working tree status
- git_diff: Show unstaged or staged diff
- git_add: Stage specific files for commit
- git_commit: Commit staged files with Co-Authored-By injected automatically
- validate_before_commit: Run tier0-validation-gate.sh before committing

All tools enforce repo-boundary safety. git_add/git_commit are WRITE_SAFE.
git_commit automatically appends Co-Authored-By: AQ <noreply@harness.local>.

Part of Phase 32: Local Agent Coding Loop
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Resolved at import time — same for all tools in this session
_REPO_ROOT: Optional[Path] = None


def _find_repo_root() -> Path:
    """Walk up from this file's location to find the git root."""
    global _REPO_ROOT
    if _REPO_ROOT is not None:
        return _REPO_ROOT
    candidate = Path(__file__).resolve()
    for parent in [candidate] + list(candidate.parents):
        if (parent / ".git").exists():
            _REPO_ROOT = parent
            return _REPO_ROOT
    raise RuntimeError("Could not locate git repository root from %s" % __file__)


def _run_git(args: List[str], timeout: int = 15) -> Dict:
    """Run a git command in the repo root. Returns stdout/stderr/returncode."""
    repo = _find_repo_root()
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"git {args[0]} timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _validate_repo_paths(files: List[str]) -> tuple[bool, str]:
    """
    Ensure all paths are inside the repo root and do not escape via traversal.
    Returns (is_valid, reason).
    """
    repo = _find_repo_root()
    for f in files:
        try:
            resolved = (repo / f).resolve()
            resolved.relative_to(repo)  # raises ValueError if outside
        except ValueError:
            return False, f"Path escapes repo root: {f}"
        except Exception as e:
            return False, f"Invalid path {f!r}: {e}"
    return True, "OK"


# ── tool handlers ─────────────────────────────────────────────────────────────


async def git_status_handler() -> Dict:
    """
    Show working tree status (git status --short).

    Returns:
        {
            "success": bool,
            "status": str,   # compact status lines
            "clean": bool,   # True if working tree is clean
        }
    """
    result = _run_git(["status", "--short"])
    if not result.get("success") and "error" in result:
        return result
    return {
        "success": result["success"],
        "status": result["stdout"],
        "clean": result["returncode"] == 0 and result["stdout"].strip() == "",
        "stderr": result["stderr"],
    }


async def git_diff_handler(staged: bool = False, files: Optional[List[str]] = None) -> Dict:
    """
    Show diff for unstaged or staged changes.

    Args:
        staged: If True, show staged (--staged) diff; else show unstaged diff
        files:  Optional list of repo-relative file paths to limit the diff

    Returns:
        {
            "success": bool,
            "diff": str,
            "has_changes": bool,
        }
    """
    args = ["diff"]
    if staged:
        args.append("--staged")
    if files:
        valid, reason = _validate_repo_paths(files)
        if not valid:
            return {"success": False, "error": reason}
        args += ["--"] + files

    result = _run_git(args)
    if not result.get("success") and "error" in result:
        return result
    return {
        "success": result["success"],
        "diff": result["stdout"],
        "has_changes": bool(result["stdout"].strip()),
        "stderr": result["stderr"],
    }


async def git_add_handler(files: List[str]) -> Dict:
    """
    Stage specific files for commit (git add).

    Safety:
        - All paths must be inside the repo root (no ../escape)
        - Empty file list is rejected
        - 'git add -A' / 'git add .' are NOT supported — explicit paths only

    Args:
        files: List of repo-relative paths to stage

    Returns:
        {
            "success": bool,
            "staged": list[str],
            "error": str (if failed)
        }
    """
    if not files:
        return {"success": False, "error": "files list is empty — provide specific paths"}

    valid, reason = _validate_repo_paths(files)
    if not valid:
        return {"success": False, "error": reason}

    result = _run_git(["add", "--"] + files)
    if result.get("success"):
        return {"success": True, "staged": files}
    return {
        "success": False,
        "error": result.get("stderr") or result.get("error") or "git add failed",
    }


async def git_commit_handler(message: str) -> Dict:
    """
    Commit staged files with a formatted commit message.

    Automatically appends:
        Co-Authored-By: AQ <noreply@harness.local>

    Args:
        message: Commit subject + optional body (without Co-Authored-By).
                 Use format: 'type(scope): description'

    Returns:
        {
            "success": bool,
            "message": str,   # full message used (with Co-Authored-By appended)
            "stdout": str,
            "error": str (if failed)
        }
    """
    if not message or not message.strip():
        return {"success": False, "error": "message is required"}

    full_message = message.strip() + "\n\nCo-Authored-By: AQ <noreply@harness.local>"
    result = _run_git(["commit", "-m", full_message], timeout=30)
    if result.get("success"):
        return {
            "success": True,
            "message": full_message,
            "stdout": result.get("stdout", ""),
        }
    return {
        "success": False,
        "error": result.get("stderr") or result.get("error") or "git commit failed",
        "stdout": result.get("stdout", ""),
    }


async def validate_before_commit_handler() -> Dict:
    """
    Run the tier0 validation gate before committing.

    Executes: scripts/governance/tier0-validation-gate.sh --pre-commit

    Returns:
        {
            "success": bool,      # True = gate passed, safe to commit
            "passed": int,
            "failed": int,
            "output": str,
        }
    """
    repo = _find_repo_root()
    gate_script = repo / "scripts" / "governance" / "tier0-validation-gate.sh"

    if not gate_script.exists():
        return {
            "success": False,
            "error": f"Validation gate not found: {gate_script}",
        }

    try:
        result = subprocess.run(
            ["bash", str(gate_script), "--pre-commit"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr

        # Parse summary line
        passed = failed = 0
        for line in output.splitlines():
            if line.startswith("[tier0] Passed:"):
                try:
                    passed = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            elif line.startswith("[tier0] Failed:"):
                try:
                    failed = int(line.split(":")[-1].strip())
                except ValueError:
                    pass

        gate_ok = result.returncode == 0

        return {
            "success": gate_ok,
            "passed": passed,
            "failed": failed,
            "output": output,
            "message": "Tier 0 gate passed — safe to commit." if gate_ok
                       else f"Tier 0 gate FAILED ({failed} checks). Fix before committing.",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Validation gate timed out after 120s"}
    except Exception as e:
        return {"success": False, "error": f"Validation gate error: {e}"}


# ── registration helper ───────────────────────────────────────────────────────

def register_git_tools(registry) -> None:
    """Register all git tools in the provided ToolRegistry."""
    # Import here to avoid circular imports when used standalone
    from tool_registry import SafetyPolicy, ToolCategory, ToolDefinition

    registry.register(ToolDefinition(
        name="git_status",
        description=(
            "Show working tree status (git status --short). "
            "Use before and after edits to understand what changed."
        ),
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=git_status_handler,
    ))

    registry.register(ToolDefinition(
        name="git_diff",
        description=(
            "Show diff for unstaged changes (default) or staged changes (staged=true). "
            "Optionally limit to specific files. Use to verify edits before staging."
        ),
        parameters={
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": "Show staged diff (git diff --staged). Default: false.",
                    "default": False,
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Repo-relative file paths to limit diff. Optional.",
                },
            },
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=git_diff_handler,
    ))

    registry.register(ToolDefinition(
        name="git_add",
        description=(
            "Stage specific files for commit (git add). "
            "ONLY use after validate_before_commit passes. "
            "Provide explicit repo-relative paths — never '.' or '-A'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Repo-relative paths to stage (e.g. ['src/foo.py'])",
                },
            },
            "required": ["files"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=git_add_handler,
        requires_confirmation=False,  # audited via SQLite; orchestrator reviews before commit
    ))

    registry.register(ToolDefinition(
        name="git_commit",
        description=(
            "Commit staged files. Co-Authored-By is added automatically. "
            "ONLY call after git_add succeeds. "
            "message format: 'type(scope): description' — single line, no Co-Authored-By needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message in 'type(scope): description' format.",
                },
            },
            "required": ["message"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=git_commit_handler,
        requires_confirmation=False,
    ))

    registry.register(ToolDefinition(
        name="validate_before_commit",
        description=(
            "Run scripts/governance/tier0-validation-gate.sh --pre-commit. "
            "MUST be called and must pass before staging any files with git_add. "
            "Returns success=true if safe to commit."
        ),
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=validate_before_commit_handler,
    ))

    logger.info("Registered 5 git tools: git_status, git_diff, git_add, git_commit, validate_before_commit")
