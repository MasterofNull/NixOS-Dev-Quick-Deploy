#!/usr/bin/env python3
"""
GitHub tools for local agents — thin wrappers over the `gh` CLI.

Provides:
  github_search_code   — search code across GitHub repos
  github_list_issues   — list/search issues in a repo
  github_create_pr     — open a pull request from the current branch
  github_get_file      — fetch a specific file from any public repo

All tools use `gh` (GitHub CLI) subprocess. They work without API keys when
`gh auth status` shows a valid token (OAuth or PAT stored by `gh auth login`).
"""
import asyncio
import json
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from tool_registry import SafetyPolicy, ToolCategory, ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)

_GH = shutil.which("gh") or "gh"


async def _gh(*args: str, input_text: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Run a gh command and return {success, stdout, stderr, returncode}."""
    try:
        proc = await asyncio.create_subprocess_exec(
            _GH, *args,
            stdin=asyncio.subprocess.PIPE if input_text else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input_text.encode() if input_text else None),
            timeout=timeout,
        )
        rc = proc.returncode
        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        return {"success": rc == 0, "stdout": out, "stderr": err, "returncode": rc}
    except asyncio.TimeoutError:
        return {"success": False, "error": f"gh command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"success": False, "error": "gh CLI not found — install with: nix-env -iA nixpkgs.gh"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def github_search_code_handler(
    query: str,
    language: Optional[str] = None,
    repo: Optional[str] = None,
    limit: int = 10,
) -> Dict:
    """Search code on GitHub using gh search code."""
    args = ["search", "code", query, "--json", "path,repository,url,textMatches", f"--limit={limit}"]
    if language:
        args += ["--language", language]
    if repo:
        args += ["--repo", repo]
    result = await _gh(*args, timeout=30)
    if result["success"] and result["stdout"]:
        try:
            items = json.loads(result["stdout"])
            return {"success": True, "count": len(items), "results": items}
        except json.JSONDecodeError:
            return {"success": True, "raw": result["stdout"]}
    return result


async def github_list_issues_handler(
    repo: str,
    state: str = "open",
    search: Optional[str] = None,
    limit: int = 20,
    label: Optional[str] = None,
) -> Dict:
    """List issues in a GitHub repository."""
    args = [
        "issue", "list",
        "--repo", repo,
        "--state", state,
        "--json", "number,title,state,labels,body,url,createdAt",
        f"--limit={limit}",
    ]
    if search:
        args += ["--search", search]
    if label:
        args += ["--label", label]
    result = await _gh(*args, timeout=30)
    if result["success"] and result["stdout"]:
        try:
            items = json.loads(result["stdout"])
            return {"success": True, "count": len(items), "issues": items}
        except json.JSONDecodeError:
            return {"success": True, "raw": result["stdout"]}
    return result


async def github_create_pr_handler(
    title: str,
    body: str,
    base: str = "main",
    draft: bool = False,
    labels: Optional[List[str]] = None,
) -> Dict:
    """Create a pull request from the current branch."""
    args = [
        "pr", "create",
        "--title", title,
        "--body", body,
        "--base", base,
        "--json", "number,url,title,state",
    ]
    if draft:
        args.append("--draft")
    if labels:
        for lbl in labels:
            args += ["--label", lbl]
    result = await _gh(*args, timeout=30)
    if result["success"] and result["stdout"]:
        try:
            pr = json.loads(result["stdout"])
            return {"success": True, "pr": pr, "url": pr.get("url", "")}
        except json.JSONDecodeError:
            return {"success": True, "raw": result["stdout"]}
    return result


async def github_get_file_handler(
    repo: str,
    path: str,
    ref: str = "HEAD",
) -> Dict:
    """Fetch the contents of a specific file from a GitHub repository."""
    args = ["api", f"repos/{repo}/contents/{path}", "--jq", ".content", "-f", f"ref={ref}"]
    result = await _gh(*args, timeout=20)
    if result["success"] and result["stdout"]:
        import base64
        try:
            content = base64.b64decode(result["stdout"].replace("\\n", "")).decode(errors="replace")
            return {"success": True, "repo": repo, "path": path, "ref": ref, "content": content}
        except Exception:
            return {"success": True, "raw": result["stdout"]}
    # fallback: gh api without jq
    args2 = ["api", f"repos/{repo}/contents/{path}"]
    result2 = await _gh(*args2, timeout=20)
    if result2["success"]:
        try:
            import base64
            data = json.loads(result2["stdout"])
            content = base64.b64decode(data.get("content", "").replace("\n", "")).decode(errors="replace")
            return {"success": True, "repo": repo, "path": path, "ref": ref, "content": content}
        except Exception:
            pass
    return result2


async def github_pr_status_handler(repo: Optional[str] = None) -> Dict:
    """Get the status of the current branch's PR (checks, reviews, merge state)."""
    args = ["pr", "status", "--json", "currentBranch,createdBy,needsReview"]
    if repo:
        args += ["--repo", repo]
    result = await _gh(*args, timeout=20)
    if result["success"] and result["stdout"]:
        try:
            return {"success": True, "status": json.loads(result["stdout"])}
        except json.JSONDecodeError:
            return {"success": True, "raw": result["stdout"]}
    return result


def register_github_tools(registry: ToolRegistry) -> None:
    """Register GitHub CLI tools with the agent tool registry."""

    registry.register(ToolDefinition(
        name="github_search_code",
        description=(
            "Search code across GitHub repositories. "
            "Returns file paths, repo names, and matched text snippets. "
            "Use for finding reference implementations, API usage examples, or similar code."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub code search query"},
                "language": {"type": "string", "description": "Filter by language (e.g. python, nix, rust)"},
                "repo": {"type": "string", "description": "Restrict to a single repo (owner/name)"},
                "limit": {"type": "integer", "description": "Max results (default 10, max 100)", "default": 10},
            },
            "required": ["query"],
        },
        category=ToolCategory.READ_ONLY if hasattr(ToolCategory, "READ_ONLY") else ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=github_search_code_handler,
    ))

    registry.register(ToolDefinition(
        name="github_list_issues",
        description="List or search issues in a GitHub repository.",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository in owner/name format"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                "search": {"type": "string", "description": "Full-text search within issues"},
                "label": {"type": "string", "description": "Filter by label name"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["repo"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=github_list_issues_handler,
    ))

    registry.register(ToolDefinition(
        name="github_create_pr",
        description=(
            "Create a GitHub pull request from the current branch. "
            "The branch must already be pushed. Returns PR URL and number."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description (markdown)"},
                "base": {"type": "string", "description": "Target branch (default: main)", "default": "main"},
                "draft": {"type": "boolean", "description": "Open as draft PR", "default": False},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply"},
            },
            "required": ["title", "body"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.SYSTEM_MODIFY,
        handler=github_create_pr_handler,
    ))

    registry.register(ToolDefinition(
        name="github_get_file",
        description="Fetch the raw contents of a file from any public GitHub repository.",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository in owner/name format"},
                "path": {"type": "string", "description": "File path within the repo"},
                "ref": {"type": "string", "description": "Branch, tag, or commit SHA (default: HEAD)", "default": "HEAD"},
            },
            "required": ["repo", "path"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=github_get_file_handler,
    ))

    registry.register(ToolDefinition(
        name="github_pr_status",
        description="Get the status of the current branch's open PR including CI checks and review state.",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository in owner/name format (optional, inferred from git remote)"},
            },
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=github_pr_status_handler,
    ))

    logger.info("Registered 5 GitHub tools")
