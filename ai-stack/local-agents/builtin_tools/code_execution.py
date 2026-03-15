#!/usr/bin/env python3
"""
Code Execution Tools

Provides safe code execution tools for local agents:
- run_python: Execute Python code
- run_bash: Execute Bash script
- run_javascript: Execute JavaScript code
- validate_code: Static security analysis

Part of Phase 11 Batch 11.6: Code Execution Sandbox
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from ..code_executor import (
    CodeExecutor,
    Language,
    ResourceLimits,
    get_executor,
)
from ..tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


async def run_python_impl(
    code: str,
    timeout: Optional[int] = None,
    memory_mb: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute Python code in sandbox.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (default: 30)
        memory_mb: Memory limit in MB (default: 256)

    Returns:
        Execution result with stdout, stderr, and status
    """
    # Get executor with custom limits if specified
    limits = None
    if timeout is not None or memory_mb is not None:
        limits = ResourceLimits(
            timeout_seconds=timeout or 30,
            memory_bytes=(memory_mb or 256) * 1024 * 1024,
        )

    executor = get_executor(limits=limits)

    # Execute code
    result = await executor.execute(code, Language.PYTHON)

    # Format response
    response = {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "execution_time_seconds": result.execution_time_seconds,
    }

    if result.error:
        response["error"] = result.error

    if result.security_scan:
        response["security"] = {
            "level": result.security_scan.level.value,
            "issues": result.security_scan.issues,
            "warnings": result.security_scan.warnings,
        }

    return response


async def run_bash_impl(
    script: str,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute Bash script in sandbox.

    Args:
        script: Bash script to execute
        timeout: Execution timeout in seconds (default: 30)

    Returns:
        Execution result with stdout, stderr, and status
    """
    limits = None
    if timeout is not None:
        limits = ResourceLimits(timeout_seconds=timeout)

    executor = get_executor(limits=limits)
    result = await executor.execute(script, Language.BASH)

    response = {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "execution_time_seconds": result.execution_time_seconds,
    }

    if result.error:
        response["error"] = result.error

    if result.security_scan:
        response["security"] = {
            "level": result.security_scan.level.value,
            "issues": result.security_scan.issues,
            "warnings": result.security_scan.warnings,
        }

    return response


async def run_javascript_impl(
    code: str,
    timeout: Optional[int] = None,
    memory_mb: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute JavaScript code in sandbox.

    Args:
        code: JavaScript code to execute
        timeout: Execution timeout in seconds (default: 30)
        memory_mb: Memory limit in MB (default: 256)

    Returns:
        Execution result with stdout, stderr, and status
    """
    limits = None
    if timeout is not None or memory_mb is not None:
        limits = ResourceLimits(
            timeout_seconds=timeout or 30,
            memory_bytes=(memory_mb or 256) * 1024 * 1024,
        )

    executor = get_executor(limits=limits)
    result = await executor.execute(code, Language.JAVASCRIPT)

    response = {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "execution_time_seconds": result.execution_time_seconds,
    }

    if result.error:
        response["error"] = result.error

    if result.security_scan:
        response["security"] = {
            "level": result.security_scan.level.value,
            "issues": result.security_scan.issues,
            "warnings": result.security_scan.warnings,
        }

    return response


async def validate_code_impl(
    code: str,
    language: str,
) -> Dict[str, Any]:
    """
    Validate code without executing (security scan only).

    Args:
        code: Code to validate
        language: Programming language (python, bash, javascript)

    Returns:
        Security scan results
    """
    # Map language string to enum
    language_map = {
        "python": Language.PYTHON,
        "bash": Language.BASH,
        "javascript": Language.JAVASCRIPT,
        "js": Language.JAVASCRIPT,
    }

    lang = language_map.get(language.lower())
    if not lang:
        return {
            "valid": False,
            "error": f"Unsupported language: {language}",
        }

    # Get executor and scanner
    executor = get_executor()
    scan_result = executor.scanner.scan(code, lang)

    return {
        "valid": scan_result.safe_to_execute,
        "security_level": scan_result.level.value,
        "issues": scan_result.issues,
        "warnings": scan_result.warnings,
        "reason": scan_result.reason if not scan_result.safe_to_execute else "",
    }


def register_code_execution_tools(registry: ToolRegistry):
    """
    Register code execution tools with registry.

    Args:
        registry: Tool registry to register with
    """
    # Tool 1: run_python
    registry.register_tool(
        ToolDefinition(
            name="run_python",
            description="Execute Python code in isolated sandbox with resource limits",
            category=ToolCategory.CODE_EXECUTION,
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30, max: 60)",
                        "minimum": 1,
                        "maximum": 60,
                    },
                    "memory_mb": {
                        "type": "integer",
                        "description": "Memory limit in MB (default: 256, max: 512)",
                        "minimum": 64,
                        "maximum": 512,
                    },
                },
                "required": ["code"],
            },
            implementation=run_python_impl,
            safety_policy=SafetyPolicy.SYSTEM_MODIFY,
            require_confirmation=True,
            rate_limit_per_minute=5,
            rate_limit_per_hour=30,
        )
    )

    # Tool 2: run_bash
    registry.register_tool(
        ToolDefinition(
            name="run_bash",
            description="Execute Bash script in isolated sandbox with resource limits",
            category=ToolCategory.CODE_EXECUTION,
            parameters={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Bash script to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30, max: 60)",
                        "minimum": 1,
                        "maximum": 60,
                    },
                },
                "required": ["script"],
            },
            implementation=run_bash_impl,
            safety_policy=SafetyPolicy.SYSTEM_MODIFY,
            require_confirmation=True,
            rate_limit_per_minute=5,
            rate_limit_per_hour=30,
        )
    )

    # Tool 3: run_javascript
    registry.register_tool(
        ToolDefinition(
            name="run_javascript",
            description="Execute JavaScript code in isolated sandbox with resource limits",
            category=ToolCategory.CODE_EXECUTION,
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "JavaScript code to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30, max: 60)",
                        "minimum": 1,
                        "maximum": 60,
                    },
                    "memory_mb": {
                        "type": "integer",
                        "description": "Memory limit in MB (default: 256, max: 512)",
                        "minimum": 64,
                        "maximum": 512,
                    },
                },
                "required": ["code"],
            },
            implementation=run_javascript_impl,
            safety_policy=SafetyPolicy.SYSTEM_MODIFY,
            require_confirmation=True,
            rate_limit_per_minute=5,
            rate_limit_per_hour=30,
        )
    )

    # Tool 4: validate_code
    registry.register_tool(
        ToolDefinition(
            name="validate_code",
            description="Validate code security without executing (static analysis)",
            category=ToolCategory.CODE_EXECUTION,
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to validate",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "enum": ["python", "bash", "javascript", "js"],
                    },
                },
                "required": ["code", "language"],
            },
            implementation=validate_code_impl,
            safety_policy=SafetyPolicy.READ_ONLY,
            require_confirmation=False,
            rate_limit_per_minute=30,
            rate_limit_per_hour=200,
        )
    )

    logger.info("Registered 4 code execution tools")
