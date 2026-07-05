#!/usr/bin/env python3
"""
Built-in Shell Command Tools for Local Agents

Provides safe shell command execution with sandboxing:
- run_command: Execute shell commands (sandboxed)
- get_system_info: Get CPU, memory, disk stats
- check_service: Check systemd service health

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from typing import Dict

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)

# Phase 164 Stage B: RTK (Rust Token Killer) shell output compression.
# When rtk is in PATH (installed as a NixOS system package), run_command wraps
# the command with `rtk <cmd>` so output is compressed before entering LLM context.
# Disable via SWB_RTK_ENABLED=0 or RTK_BIN="".
_RTK_BIN: str = os.environ.get("RTK_BIN", "") or shutil.which("rtk") or ""
_RTK_ENABLED: bool = bool(_RTK_BIN) and os.environ.get("SWB_RTK_ENABLED", "1").strip() not in ("0", "false", "no")


# Whitelist of safe commands
# Extended (2026-05-18) to include aq-* harness tools and common analysis tools
# that agents legitimately need. run_shell_command is an alias registered below
# to handle models that emit the wrong tool name.
class NsjailSandbox:
    """Linux namespace sandbox for SAFE_COMMANDS execution (Phase 62.2, AM-G6).

    Uses nsjail to run commands in a minimal read-only Linux namespace:
    - No network (iface_no_lo)
    - No /proc access (disable_proc)
    - Read-only bind of /nix/store and /run/current-system
    - Writable /tmp (tmpfs, 16 MiB)

    If nsjail is configured as required, startup failures fail closed instead of
    silently downgrading to host subprocess execution.
    """

    def __init__(self) -> None:
        bin_path = os.environ.get("NSJAIL_BIN") or shutil.which("nsjail")
        self.available: bool = bool(bin_path and os.path.isfile(bin_path))
        self.bin: str = bin_path or ""
        self.required: bool = os.environ.get("NSJAIL_REQUIRED", "0").strip().lower() in {"1", "true", "yes"}

    def build_argv(self, command: str, timeout_seconds: int) -> list:
        """Build nsjail argv wrapping the given shell command string."""
        return [
            self.bin,
            "--mode", "once",
            "--time_limit", str(timeout_seconds),
            "--max_cpus", "1",
            "--rlimit_nofile", "64",
            "--disable_proc",
            "--iface_no_lo",
            "--bindmount_ro", "/nix/store",
            "--bindmount_ro", "/run/current-system",
            "--tmpfs", "/tmp:size=16m",
            "--cwd", "/tmp",
            "--",
            "/run/current-system/sw/bin/sh", "-c", command,
        ]


_nsjail = NsjailSandbox()

_SHELL_CONTROL_PATTERN = re.compile(r"(?:;|&&|\|\||`|\$\(|\$\{|\n|\r)")


SAFE_COMMANDS = {
    # System inspection (read-only)
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "grep", "rg",
    "find", "which", "whoami", "hostname", "date", "uptime",
    "free", "df", "du", "ps", "top", "systemctl", "journalctl",
    # Git (read-only ops)
    "git",
    # HTTP — coordinator/RAG/memory API calls (coordinator at :8003 only; :8002 blocked by safe_command_executor.py)
    "curl",
    # Code analysis / validation
    "bash", "python3", "python", "nix-instantiate", "nix",
    "shellcheck", "statix", "deadnix",
    # Harness tools (full suite from LOCAL-AGENT.md)
    "agrep", "als", "acat", "asum",
    "aq-qa", "aq-hints", "aq-report", "aq-session-start",
    "aq-commit-facts", "aq-lesson-promote", "aq-crystallize",
    "aq-agent-loop", "aqd",
    # understand-anything mapping: agents consult subsystem wiki + graph on demand
    # (aq-wiki --section/--list/--status). Without this the agent cannot benefit
    # from the codebase mapping during autonomous runs.
    "aq-wiki",
    # OpenCode CLI (Phase 60 Integration)
    "opencode",
    # JSON/YAML inspection
    "jq", "yq",
    # File utilities
    "fd", "sort", "uniq", "cut", "awk", "sed", "tr", "printf", "tee",
}


async def run_command_handler(
    command: str,
    timeout_seconds: int = 10,
) -> Dict:
    """
    Execute a safe shell command.

    Args:
        command: Shell command to execute
        timeout_seconds: Timeout in seconds (default: 10)

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "error": str (if failed)
        }
    """
    # Parse first word as command
    cmd_parts = command.split()
    if not cmd_parts:
        return {"success": False, "error": "Empty command"}

    base_cmd = cmd_parts[0]

    if _SHELL_CONTROL_PATTERN.search(command):
        return {
            "success": False,
            "error": "Command rejected: shell control/metacharacter sequences are not allowed",
            "safety_reason": "shell_injection_guard",
        }

    # Check if command is safe
    if base_cmd not in SAFE_COMMANDS:
        return {
            "success": False,
            "error": f"Command '{base_cmd}' not in safe list: {', '.join(sorted(SAFE_COMMANDS))}",
        }

    try:
        if _nsjail.available:
            try:
                nsjail_argv = _nsjail.build_argv(command, timeout_seconds)
                result = subprocess.run(
                    nsjail_argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds + 2,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "sandbox": "nsjail",
                }
            except Exception as nsjail_exc:
                logger.warning(
                    "NsjailSandbox: isolation failure: %s",
                    nsjail_exc,
                )
                if _nsjail.required:
                    return {
                        "success": False,
                        "error": f"Sandbox required but nsjail failed: {nsjail_exc}",
                        "sandbox": "nsjail",
                        "safety_reason": "sandbox_required_failed",
                    }

        if _nsjail.required and not _nsjail.available:
            return {
                "success": False,
                "error": "Sandbox required but nsjail is unavailable",
                "sandbox": "unavailable",
                "safety_reason": "sandbox_required_unavailable",
            }

        # Plain subprocess compatibility path. This is only used when nsjail is
        # not configured as required; the shell injection guard above still
        # applies before reaching this path.
        #
        # Phase 164 Stage B: when RTK is available, wrap the command so output
        # is compressed before it enters the LLM context window. RTK handles
        # git, grep, ls, pytest, cargo, docker, kubectl, and 100+ other commands.
        # Falls back to uncompressed execution if RTK fails.
        if _RTK_ENABLED:
            try:
                rtk_argv = [_RTK_BIN] + shlex.split(command)
                result = subprocess.run(
                    rtk_argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "compressed": True,
                }
            except Exception as rtk_exc:
                logger.debug("RTK compression failed (%s), falling back to plain subprocess", rtk_exc)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout_seconds}s",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Command failed: {e}",
        }


async def get_system_info_handler() -> Dict:
    """
    Get system information (CPU, memory, disk).

    Returns:
        {
            "cpu": {...},
            "memory": {...},
            "disk": {...}
        }
    """
    info = {}

    # CPU info
    try:
        result = subprocess.run(
            ["nproc"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["cpu"] = {
            "cores": int(result.stdout.strip()) if result.returncode == 0 else None,
        }
    except:
        info["cpu"] = {"error": "Failed to get CPU info"}

    # Memory info
    try:
        result = subprocess.run(
            ["free", "-m"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                mem_line = lines[1].split()
                info["memory"] = {
                    "total_mb": int(mem_line[1]),
                    "used_mb": int(mem_line[2]),
                    "free_mb": int(mem_line[3]),
                }
    except:
        info["memory"] = {"error": "Failed to get memory info"}

    # Disk info
    try:
        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                disk_line = lines[1].split()
                info["disk"] = {
                    "total": disk_line[1],
                    "used": disk_line[2],
                    "available": disk_line[3],
                    "use_percent": disk_line[4],
                }
    except:
        info["disk"] = {"error": "Failed to get disk info"}

    return info


async def check_service_handler(service_name: str) -> Dict:
    """
    Check systemd service health.

    Args:
        service_name: Service name (e.g., "ai-aidb.service")

    Returns:
        {
            "active": bool,
            "status": str,
            "error": str (if failed)
        }
    """
    try:
        # Check if service is active
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )

        active = result.stdout.strip() == "active"

        # Get status details
        status_result = subprocess.run(
            ["systemctl", "status", service_name, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return {
            "active": active,
            "status": status_result.stdout,
            "service_name": service_name,
        }

    except Exception as e:
        return {
            "active": False,
            "error": f"Failed to check service: {e}",
        }


def register_shell_tools(registry: ToolRegistry):
    """Register all shell command tools in the registry"""

    # run_command
    registry.register(ToolDefinition(
        name="run_command",
        description="Execute a safe shell command (whitelist: ls, pwd, grep, ps, systemctl, etc.)",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 10,
                },
            },
            "required": ["command"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=run_command_handler,
    ))

    # run_shell_command — alias for run_command so models with either instilled tool name succeed.
    # Some LLMs emit "run_shell_command" from training; registering both prevents wasted turns.
    registry.register(ToolDefinition(
        name="run_shell_command",
        description="Alias for run_command. Execute a safe shell command (whitelist enforced).",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 10,
                },
            },
            "required": ["command"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=run_command_handler,
    ))

    # get_system_info
    registry.register(ToolDefinition(
        name="get_system_info",
        description="Get system information (CPU cores, memory usage, disk usage)",
        parameters={
            "type": "object",
            "properties": {},
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_system_info_handler,
    ))

    # check_service
    registry.register(ToolDefinition(
        name="check_service",
        description="Check systemd service health status",
        parameters={
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the systemd service",
                }
            },
            "required": ["service_name"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=check_service_handler,
    ))

    # opencode (Phase 60 Integration)
    registry.register(ToolDefinition(
        name="opencode",
        description="Call the OpenCode CLI for specialized coding and implementation tasks.",
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The coding objective or prompt for OpenCode.",
                },
                "mode": {
                    "type": "string",
                    "description": "Execution mode (e.g., direct, draft, implement).",
                    "default": "direct",
                }
            },
            "required": ["prompt"],
        },
        category=ToolCategory.CODE_EXEC,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=run_command_handler, # Reusing run_command_handler for the CLI
    ))


    logger.info("Registered 4 shell command tools")
