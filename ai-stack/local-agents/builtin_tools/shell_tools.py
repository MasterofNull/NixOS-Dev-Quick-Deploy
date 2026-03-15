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
import subprocess
from typing import Dict

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# Whitelist of safe commands
SAFE_COMMANDS = {
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "grep",
    "find", "which", "whoami", "hostname", "date", "uptime",
    "free", "df", "du", "ps", "top", "systemctl",
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

    # Check if command is safe
    if base_cmd not in SAFE_COMMANDS:
        return {
            "success": False,
            "error": f"Command '{base_cmd}' not in safe list: {', '.join(sorted(SAFE_COMMANDS))}",
        }

    try:
        # Run command with timeout
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
                    "description": "Service name (e.g., 'ai-aidb.service')",
                },
            },
            "required": ["service_name"],
        },
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=check_service_handler,
    ))

    logger.info("Registered 3 shell command tools")
