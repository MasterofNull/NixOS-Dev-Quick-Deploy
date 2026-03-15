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
import json
import logging
import os
import re
import subprocess
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

async def read_file_handler(file_path: str, max_size_kb: int = 1024) -> Dict:
    """
    Read contents of a file.

    Args:
        file_path: Absolute path to file
        max_size_kb: Maximum file size in KB (default: 1MB)

    Returns:
        {
            "success": bool,
            "content": str (if success),
            "error": str (if failed),
            "metadata": {size_bytes, lines}
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

    # Check file size
    size_bytes = path.stat().st_size
    if size_bytes > max_size_kb * 1024:
        return {
            "success": False,
            "error": f"File too large: {size_bytes / 1024:.1f}KB > {max_size_kb}KB",
        }

    # Read file
    try:
        content = path.read_text()
        lines = content.count("\n") + 1

        return {
            "success": True,
            "content": content,
            "metadata": {
                "size_bytes": size_bytes,
                "lines": lines,
                "path": str(path),
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
        if mode == "w":
            path.write_text(content)
        else:  # append
            with path.open("a") as f:
                f.write(content)

        bytes_written = len(content.encode("utf-8"))

        return {
            "success": True,
            "bytes_written": bytes_written,
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


def register_file_tools(registry: ToolRegistry):
    """Register all file operation tools in the registry"""

    # read_file
    registry.register(ToolDefinition(
        name="read_file",
        description="Read the contents of a file",
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
        requires_confirmation=True,  # Require confirmation for writes
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

    logger.info("Registered 5 file operation tools")


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
