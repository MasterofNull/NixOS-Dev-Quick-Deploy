#!/usr/bin/env python3
"""
Built-in File Operation Tools for Local Agents

Provides safe file operation tools with sandboxing and validation:
- read_file: Read file contents
- write_file: Write file contents
- list_files: Glob file search
- search_files: Content search (grep)
- file_exists: Check file existence

All tools follow safety policies and include audit logging.

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import glob
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# File path validation
ALLOWED_BASE_PATHS = [
    Path.home() / ".local/share/nixos-ai-stack",
    Path.home() / "Documents",
    Path("/tmp"),
]

FORBIDDEN_PATHS = [
    Path.home() / ".ssh",
    Path.home() / ".gnupg",
    Path("/etc/shadow"),
    Path("/etc/passwd"),
]


def validate_file_path(file_path: str, allow_write: bool = False) -> tuple[bool, str]:
    """
    Validate file path for safety.

    Args:
        file_path: Path to validate
        allow_write: Whether write access is needed

    Returns:
        (is_valid, reason)
    """
    try:
        path = Path(file_path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Check forbidden paths
    for forbidden in FORBIDDEN_PATHS:
        if path == forbidden or forbidden in path.parents:
            return False, f"Access to {forbidden} is forbidden"

    # Check allowed base paths
    if allow_write:
        allowed = False
        for base in ALLOWED_BASE_PATHS:
            if path == base or base in path.parents:
                allowed = True
                break

        if not allowed:
            return False, f"Write access not allowed outside: {', '.join(str(p) for p in ALLOWED_BASE_PATHS)}"

    return True, "OK"


# Tool handlers

async def read_file_handler(
    file_path: str,
    max_size_kb: int = 1024,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> Dict:
    """
    Read contents of a file with optional line-range chunking.

    Args:
        file_path: Absolute path to file
        max_size_kb: Maximum file size in KB (default: 1MB)
        start_line: 1-based start line (optional)
        end_line: 1-based end line (optional)

    Returns:
        {
            "success": bool,
            "content": str (if success),
            "error": str (if failed),
            "metadata": {size_bytes, lines, start_line, end_line}
        }
    """
    # Validate path
    is_valid, reason = validate_file_path(file_path, allow_write=False)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    path = Path(file_path)

    # Check file exists
    if not path.exists():
        return {"success": False, "error": f"File does not exist: {file_path}"}

    if not path.is_file():
        return {"success": False, "error": f"Path is not a file: {file_path}"}

    # Check file size (only if reading the whole file)
    size_bytes = path.stat().st_size
    if start_line is None and end_line is None:
        if size_bytes > max_size_kb * 1024:
            return {
                "success": False,
                "error": f"File too large: {size_bytes / 1024:.1f}KB > {max_size_kb}KB. Use start_line/end_line for chunking.",
            }

    # Read file
    try:
        if start_line is not None or end_line is not None:
            # Chunked read
            lines_content = []
            s = (start_line or 1) - 1
            e = end_line or 1000000 # default to "rest of file"
            
            with path.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= s and i < e:
                        lines_content.append(line)
                    if i >= e:
                        break
            
            content = "".join(lines_content)
            actual_lines = len(lines_content)
        else:
            # Full read
            content = path.read_text(encoding="utf-8")
            actual_lines = content.count("\n") + 1

        return {
            "success": True,
            "content": content,
            "metadata": {
                "size_bytes": size_bytes,
                "lines": actual_lines,
                "path": str(path),
                "start_line": start_line,
                "end_line": end_line,
            },
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}


async def write_file_handler(
    file_path: str,
    content: str,
    mode: str = "w",
    create_dirs: bool = True,
) -> Dict:
    """
    Write contents to a file.

    Args:
        file_path: Absolute path to file
        content: Content to write
        mode: Write mode ('w' or 'a')
        create_dirs: Create parent directories if needed

    Returns:
        {
            "success": bool,
            "bytes_written": int,
            "error": str (if failed)
        }
    """
    # Validate path (write access)
    is_valid, reason = validate_file_path(file_path, allow_write=True)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    if mode not in ("w", "a"):
        return {"success": False, "error": f"Invalid mode: {mode} (must be 'w' or 'a')"}

    path = Path(file_path)

    # Create parent directories if needed
    if create_dirs:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"success": False, "error": f"Failed to create directories: {e}"}

    # Write file
    try:
        encoded = content.encode("utf-8")
        if mode == "w":
            path.write_bytes(encoded)
        else:  # append
            with path.open("ab") as f:
                f.write(encoded)

        sha256 = hashlib.sha256(encoded).hexdigest()[:16]

        return {
            "success": True,
            "bytes_written": len(encoded),
            "sha256_prefix": sha256,  # audit trail: non-repudiation without re-reading
            "path": str(path),
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to write file: {e}"}


async def list_files_handler(
    pattern: str,
    recursive: bool = True,
    max_results: int = 1000,
) -> Dict:
    """
    List files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.md")
        recursive: Enable recursive search
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "files": [str],  # List of matching file paths
            "count": int,
            "truncated": bool
        }
    """
    try:
        # Use glob
        if recursive and "**" not in pattern:
            pattern = f"**/{pattern}"

        matches = glob.glob(pattern, recursive=recursive)

        # Filter out forbidden paths
        safe_matches = []
        for match in matches:
            is_valid, _ = validate_file_path(match, allow_write=False)
            if is_valid:
                safe_matches.append(match)

        # Sort and limit
        safe_matches.sort()
        truncated = len(safe_matches) > max_results
        safe_matches = safe_matches[:max_results]

        return {
            "success": True,
            "files": safe_matches,
            "count": len(safe_matches),
            "truncated": truncated,
        }

    except Exception as e:
        return {"success": False, "error": f"Glob failed: {e}"}


async def search_files_handler(
    pattern: str,
    path: str = ".",
    file_pattern: Optional[str] = None,
    max_results: int = 100,
) -> Dict:
    """
    Search file contents for a pattern (grep).

    Args:
        pattern: Regular expression pattern to search
        path: Directory to search in
        file_pattern: Optional file glob pattern (e.g., "*.py")
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "matches": [
                {"file": str, "line": int, "text": str}
            ],
            "count": int,
            "truncated": bool
        }
    """
    # Validate path
    is_valid, reason = validate_file_path(path, allow_write=False)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    try:
        # Build grep command
        cmd = ["grep", "-rn", pattern, path]

        if file_pattern:
            cmd.extend(["--include", file_pattern])

        # Run grep
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
        )

        # Parse results
        matches = []
        for line in result.stdout.splitlines():
            # Format: file:line:text
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "text": parts[2],
                })

        # Limit results
        truncated = len(matches) > max_results
        matches = matches[:max_results]

        return {
            "success": True,
            "matches": matches,
            "count": len(matches),
            "truncated": truncated,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Search timed out (>10s)"}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


async def file_exists_handler(file_path: str) -> Dict:
    """
    Check if a file exists.

    Args:
        file_path: Path to check

    Returns:
        {
            "exists": bool,
            "is_file": bool,
            "is_dir": bool,
            "size_bytes": int (if file exists)
        }
    """
    path = Path(file_path)

    exists = path.exists()
    is_file = path.is_file() if exists else False
    is_dir = path.is_dir() if exists else False

    result = {
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
    }

    if is_file:
        try:
            result["size_bytes"] = path.stat().st_size
        except:
            pass

    return result


async def edit_file_handler(file_path: str, old_string: str, new_string: str) -> Dict:
    """
    Surgically replace old_string with new_string in a file (first occurrence).

    Preferred over write_file for targeted changes — the model only needs to supply
    the strings to change, not regenerate the entire file.  Fails with a clear error
    if old_string is not found so the model can self-correct.

    Args:
        file_path:   Relative or absolute path to the file to edit.
        old_string:  Exact text to replace (must be unique enough to identify the site).
        new_string:  Replacement text.

    Returns:
        {"success": True, "replacements": 1}          on success
        {"success": False, "error": "<reason>"}        on failure
    """
    try:
        # Finding 2 (CRITICAL, codex-review-local-agent-batch-20260821 #2): unlike
        # write_file, edit_file never validated the target path — any existing
        # writable file (including forbidden paths, or targets reached via a
        # symlink out of the workspace) could be modified. Reuse write_file's exact
        # boundary (validate_file_path) rather than inventing a weaker one.
        is_valid, reason = validate_file_path(file_path, allow_write=True)
        if not is_valid:
            return {"success": False, "error": f"Path validation failed: {reason}"}

        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        content = path.read_text(encoding="utf-8")
        if old_string not in content:
            # Provide a snippet of the file to help the model self-correct its old_string
            snippet = content[:400] + ("..." if len(content) > 400 else "")
            return {
                "success": False,
                "error": f"old_string not found in {file_path}. File starts with:\n{snippet}",
            }
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")
        return {"success": True, "replacements": 1}
    except OSError as exc:
        return {"success": False, "error": str(exc)}


# AQ_WRITE_REGION: kill switch for the write_region tool (default ON). Set to "0"/"false"
# to hide the tool from the registry entirely — falls back to edit_file/write_file only.
def _write_region_enabled() -> bool:
    return os.environ.get("AQ_WRITE_REGION", "1").strip().lower() not in ("0", "false", "no", "off")


async def write_region_handler(
    file_path: str,
    start_line: int,
    end_line: int,
    new_text: str,
    expected_text: Optional[str] = None,
    expected_region_sha: Optional[str] = None,
) -> Dict:
    """
    Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path with new_text.
    No old_string matching — deterministic line-range rewrite.

    Research motivation (Aider per-model edit-format data): search/replace (edit_file's
    old_string) is the HARDEST edit format for weak/quantized models — they cannot
    reliably reproduce a byte-exact anchor, so they churn on 'old_string not found'.
    Aider defaults local/weak models to whole-unit rewrite instead. We front-load code
    to local WITH line-number citations (e.g. '[file:271-290]'), so a line-range rewrite
    needs no matching at all — just the line numbers already shown.

    Safety (2026-08-21 Codex + Antigravity independent review, findings 2 & 9):
      - file_path is validated with the exact same workspace boundary write_file uses
        (validate_file_path, allow_write=True) — resolves `..`/symlinks via realpath
        and fails closed on any target outside the allowlist or under a forbidden path.
      - expected_text / expected_region_sha are an OPTIONAL stale-line-drift guard: if
        the caller's line-number citation is stale (an intervening edit shifted lines),
        the current region content won't match what the caller expects and the write is
        rejected instead of silently clobbering the wrong block. Omit both for the prior
        (unguarded) behavior — fully backward compatible.
      - The write is atomic (temp file in the same directory + os.replace()) so a crash
        mid-write cannot truncate the file.

    Args:
        file_path:   Relative or absolute path to the file to edit.
        start_line:  1-indexed first line to replace (inclusive).
        end_line:    1-indexed last line to replace (inclusive). May equal
                     len(lines)+1 (with start_line == end_line) to insert at EOF
                     without replacing anything.
        new_text:    Replacement text for the region (may be multi-line).
        expected_text: Optional. Current [start_line, end_line] text must match this
                     exactly, or the write is rejected (stale-line-drift guard).
        expected_region_sha: Optional. sha256 hex digest of the current
                     [start_line, end_line] text — alternative to expected_text when
                     the caller only carries a hash (e.g. from a front-loaded
                     citation). Checked the same way; if both are given, both must pass.

    Returns:
        {"success": True, "start_line": int, "end_line": int, "lines_written": int}
        {"success": False, "error": "<reason>", "current_line_count": int, ...}
    """
    try:
        # Finding 2 (CRITICAL, codex-review-local-agent-batch-20260821 #2): unlike
        # write_file, write_region never validated the target path — any existing
        # writable file (including forbidden paths, or targets reached via a symlink
        # out of the workspace) could be modified. Reuse write_file's exact boundary
        # (validate_file_path resolves realpath, so a symlink chain that escapes the
        # allowlist is rejected) rather than inventing a weaker one.
        is_valid, reason = validate_file_path(file_path, allow_write=True)
        if not is_valid:
            return {"success": False, "error": f"Path validation failed: {reason}"}

        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        if not path.is_file():
            return {"success": False, "error": f"Path is not a file: {file_path}"}

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        line_count = len(lines)
        max_bound = line_count + 1  # +1 slot allows a pure EOF insert

        try:
            start_line = int(start_line)
            end_line = int(end_line)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": f"start_line/end_line must be integers (got {start_line!r}, {end_line!r})",
                "current_line_count": line_count,
            }

        if not (1 <= start_line <= end_line <= max_bound):
            # Finding 5 (MEDIUM): truthful error — do NOT present a silently-clamped
            # guess at the target region as if it were real. Report the actual current
            # line count and, for orientation only, an explicitly-labeled tail preview
            # of the real file (not a clamp of the caller's bogus range).
            tail_preview = "".join(lines[-5:]) if lines else ""
            return {
                "success": False,
                "error": (
                    f"Out-of-range region [start_line={start_line}, end_line={end_line}] for "
                    f"{file_path} — file currently has {line_count} lines. Valid range is "
                    f"1 <= start_line <= end_line <= {max_bound} ({max_bound} = insert-at-EOF)."
                ),
                "current_line_count": line_count,
                "file_tail_preview": tail_preview,
            }

        # Finding 9 (HIGH): stale-line-drift guard — optional, backward compatible.
        # Compare the ACTUAL current region content against what the caller expected
        # (from an earlier read/citation) before writing.
        current_region_text = "".join(lines[start_line - 1:end_line])
        if expected_text is not None and expected_text != current_region_text:
            return {
                "success": False,
                "error": (
                    f"expected_text does not match the current content of "
                    f"[{start_line},{end_line}] in {file_path} — the file changed since "
                    f"your last read (stale-line-drift guard). Re-read and retry."
                ),
                "current_line_count": line_count,
                "current_region_text": current_region_text,
            }
        if expected_region_sha is not None:
            actual_sha = hashlib.sha256(current_region_text.encode("utf-8")).hexdigest()
            if actual_sha != expected_region_sha:
                return {
                    "success": False,
                    "error": (
                        f"expected_region_sha mismatch for [{start_line},{end_line}] in "
                        f"{file_path} — the file changed since your last read "
                        f"(stale-line-drift guard). actual_sha256={actual_sha}. Re-read and "
                        f"retry."
                    ),
                    "current_line_count": line_count,
                    "current_region_text": current_region_text,
                }

        new_lines = new_text.splitlines(keepends=True) if new_text else []
        prefix = lines[:start_line - 1]
        suffix = lines[end_line:]

        # Finding 3 (HIGH): EOF/mid-file merge guard. Only insert a separator where a
        # merge would actually occur — do NOT forcibly newline-terminate new_text
        # itself (that mutates the caller's payload even when no merge risk exists,
        # e.g. a true trailing-content EOF insert with no suffix). "Join safely",
        # don't "mutate the payload."
        if prefix and new_lines and not prefix[-1].endswith("\n"):
            prefix[-1] = prefix[-1] + "\n"
        if new_lines and suffix and not new_lines[-1].endswith("\n"):
            new_lines = new_lines[:-1] + [new_lines[-1] + "\n"]

        spliced = prefix + new_lines + suffix
        new_content = "".join(spliced)

        # Finding 4 (MEDIUM): atomic write — temp file in the same directory +
        # os.replace(), so a crash mid-write cannot truncate/corrupt the target file.
        orig_mode = path.stat().st_mode
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            os.chmod(tmp_name, orig_mode)
            os.replace(tmp_name, str(path))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        return {
            "success": True,
            "start_line": start_line,
            "end_line": start_line + len(new_lines) - 1 if new_lines else start_line - 1,
            "lines_written": len(new_lines),
        }
    except OSError as exc:
        return {"success": False, "error": str(exc)}


def register_file_tools(registry: ToolRegistry):
    """Register all file operation tools in the registry"""

    # read_file
    registry.register(ToolDefinition(
        name="read_file",
        description="Read the contents of a file with optional line-range chunking.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read",
                },
                "max_size_kb": {
                    "type": "integer",
                    "description": "Maximum file size in KB (default: 1024)",
                    "default": 1024,
                },
                "start_line": {
                    "type": "integer",
                    "description": "1-based start line (optional)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "1-based end line (optional)",
                },
            },
            "required": ["file_path"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=read_file_handler,
    ))

    # write_file
    registry.register(ToolDefinition(
        name="write_file",
        description="Write content to a file",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "mode": {
                    "type": "string",
                    "description": "Write mode: 'w' (overwrite) or 'a' (append)",
                    "enum": ["w", "a"],
                    "default": "w",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": True,
                },
            },
            "required": ["file_path", "content"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=write_file_handler,
        requires_confirmation=False,  # Agent loop is autonomous; git review is the safety gate
    ))

    # list_files
    registry.register(ToolDefinition(
        name="list_files",
        description="List files matching a glob pattern",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '*.py', '**/*.md')",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Enable recursive search",
                    "default": True,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 1000,
                },
            },
            "required": ["pattern"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=list_files_handler,
    ))

    # search_files
    registry.register(ToolDefinition(
        name="search_files",
        description="Search file contents for a pattern (grep)",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in",
                    "default": ".",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional file glob pattern (e.g., '*.py')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 100,
                },
            },
            "required": ["pattern"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=search_files_handler,
    ))

    # file_exists
    registry.register(ToolDefinition(
        name="file_exists",
        description="Check if a file or directory exists",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to check",
                },
            },
            "required": ["file_path"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=file_exists_handler,
    ))

    # edit_file
    registry.register(ToolDefinition(
        name="edit_file",
        description=(
            "Surgically replace old_string with new_string in a file (first occurrence). "
            "Preferred over write_file for targeted changes — does not require regenerating "
            "the whole file. Fails with a clear error if old_string is not found."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact text to replace (must uniquely identify the edit site)",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=edit_file_handler,
    ))

    # write_region — gated by AQ_WRITE_REGION (default ON). Not registered at all when
    # disabled, so it is absent from both the model-visible tool schema AND the GBNF
    # grammar's function enum (which derives from the registry's enabled tools).
    _registered = 6
    if _write_region_enabled():
        registry.register(ToolDefinition(
            name="write_region",
            description=(
                "Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path "
                "with new_text. No old_string matching required — use the line numbers "
                "already shown in code citations (e.g. '[file:271-290]'). Preferred over "
                "edit_file for any change beyond a tiny single-line tweak: deterministic, "
                "no byte-exact anchor needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "1-indexed first line to replace (inclusive)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": (
                            "1-indexed last line to replace (inclusive). May equal "
                            "line_count+1 with start_line==end_line to insert at EOF."
                        ),
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text for the line range (may be multi-line)",
                    },
                    "expected_text": {
                        "type": "string",
                        "description": (
                            "Optional stale-line-drift guard: the current text of "
                            "[start_line, end_line] must match this exactly or the write "
                            "is rejected. Omit for prior (unguarded) behavior."
                        ),
                    },
                    "expected_region_sha": {
                        "type": "string",
                        "description": (
                            "Optional stale-line-drift guard: sha256 hex digest of the "
                            "current [start_line, end_line] text. Alternative to "
                            "expected_text when only a hash is available."
                        ),
                    },
                },
                "required": ["file_path", "start_line", "end_line", "new_text"],
            },
            category=ToolCategory.FILE_OPS,
            safety_policy=SafetyPolicy.WRITE_SAFE,
            handler=write_region_handler,
        ))
        _registered += 1

    logger.info("Registered %d file operation tools", _registered)


if __name__ == "__main__":
    # Test file tools
    logging.basicConfig(level=logging.INFO)

    async def test():
        from tool_registry import ToolRegistry

        registry = ToolRegistry()
        register_file_tools(registry)

        # Test read_file
        call_id = "test-read"
        from tool_registry import ToolCall

        read_call = ToolCall(
            id=call_id,
            tool_name="read_file",
            arguments={"file_path": __file__},
            model_id="test",
            session_id="test",
        )

        result = await registry.execute_tool_call(read_call)
        print(f"\nread_file result:")
        print(f"  Status: {result.status}")
        if result.result:
            content = result.result.get("content", "")[:200]
            print(f"  Content preview: {content}...")
        print(f"  Time: {result.execution_time_ms:.1f}ms")

        # Test list_files
        list_call = ToolCall(
            id="test-list",
            tool_name="list_files",
            arguments={"pattern": "*.py", "max_results": 10},
            model_id="test",
            session_id="test",
        )

        result = await registry.execute_tool_call(list_call)
        print(f"\nlist_files result:")
        print(f"  Status: {result.status}")
        if result.result:
            print(f"  Files found: {result.result.get('count', 0)}")

        # Get statistics
        stats = registry.get_statistics()
        print(f"\nRegistry statistics:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
