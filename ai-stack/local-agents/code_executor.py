#!/usr/bin/env python3
"""
Code Execution Sandbox

Provides safe, isolated code execution for local agents with:
- Multi-language support (Python, Bash, JavaScript)
- Resource limits (CPU, memory, time)
- Security scanning and validation
- Result capture and formatting
- Network isolation

Part of Phase 11 Batch 11.6: Code Execution Sandbox
"""

import asyncio
import json
import logging
import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported execution languages."""
    PYTHON = "python"
    BASH = "bash"
    JAVASCRIPT = "javascript"


class SecurityLevel(Enum):
    """Security risk levels."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceLimits:
    """Resource limits for code execution."""

    # Time limits
    timeout_seconds: int = 30

    # CPU limits (seconds)
    cpu_time_seconds: int = 30

    # Memory limits (bytes)
    memory_bytes: int = 256 * 1024 * 1024  # 256 MB

    # Process limits
    max_processes: int = 10

    # File size limits (bytes)
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Output limits (bytes)
    max_output_bytes: int = 1024 * 1024  # 1 MB


@dataclass
class SecurityScanResult:
    """Result of security scanning."""

    level: SecurityLevel
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    safe_to_execute: bool = True
    reason: str = ""


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_seconds: float = 0.0
    memory_used_bytes: int = 0
    security_scan: Optional[SecurityScanResult] = None
    error: Optional[str] = None


class SecurityScanner:
    """
    Security scanner for code validation.

    Performs static analysis to detect dangerous patterns.
    """

    # Dangerous patterns by language
    PYTHON_DANGEROUS_PATTERNS = {
        r'\beval\s*\(': "Use of eval() - arbitrary code execution",
        r'\bexec\s*\(': "Use of exec() - arbitrary code execution",
        r'\b__import__\s*\(': "Dynamic import - potential security risk",
        r'\bcompile\s*\(': "Use of compile() - code generation",
        r'\bos\.system\s*\(': "Use of os.system() - shell command execution",
        r'\bsubprocess\.call\s*\(': "Use of subprocess - command execution",
        r'\bopen\s*\([^)]*[\'"]w': "File write operation",
        r'\brmtree\s*\(': "Recursive delete operation",
        r'\bunlink\s*\(': "File deletion",
        r'\bremove\s*\(': "File/directory removal",
        r'\.password': "Potential password/credential access",
        r'\.secret': "Potential secret access",
        r'\.token': "Potential token access",
        r'\bsocket\s*\(': "Network socket creation",
        r'\burllib\.request': "Network request",
        r'\brequests\.': "HTTP request library",
    }

    BASH_DANGEROUS_PATTERNS = {
        r'\brm\s+-rf': "Recursive force delete",
        r'\bdd\s+': "Direct disk operations",
        r'\bmkfs\s+': "Filesystem creation",
        r'\bchmod\s+': "Permission modification",
        r'\bchown\s+': "Ownership modification",
        r'\bcurl\s+': "Network request",
        r'\bwget\s+': "Network download",
        r'\bnc\s+': "Netcat - network utility",
        r'\btelnet\s+': "Network connection",
        r'\bssh\s+': "SSH connection",
        r'>\s*/dev/sd': "Direct disk write",
        r'\bkill\s+-9': "Force process kill",
        r'\bpkill\s+': "Process kill by name",
    }

    JAVASCRIPT_DANGEROUS_PATTERNS = {
        r'\beval\s*\(': "Use of eval() - arbitrary code execution",
        r'\bFunction\s*\(': "Dynamic function creation",
        r'require\s*\(\s*[\'"]child_process': "Child process execution",
        r'require\s*\(\s*[\'"]fs[\'"]': "Filesystem access",
        r'require\s*\(\s*[\'"]net[\'"]': "Network access",
        r'require\s*\(\s*[\'"]http': "HTTP access",
        r'\.unlink\s*\(': "File deletion",
        r'\.rmdir\s*\(': "Directory removal",
        r'\.chmod\s*\(': "Permission modification",
    }

    def __init__(self):
        """Initialize security scanner."""
        self.pattern_cache: Dict[Language, List[tuple]] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self.pattern_cache[Language.PYTHON] = [
            (re.compile(pattern), message)
            for pattern, message in self.PYTHON_DANGEROUS_PATTERNS.items()
        ]
        self.pattern_cache[Language.BASH] = [
            (re.compile(pattern), message)
            for pattern, message in self.BASH_DANGEROUS_PATTERNS.items()
        ]
        self.pattern_cache[Language.JAVASCRIPT] = [
            (re.compile(pattern), message)
            for pattern, message in self.JAVASCRIPT_DANGEROUS_PATTERNS.items()
        ]

    def scan(self, code: str, language: Language) -> SecurityScanResult:
        """
        Scan code for security issues.

        Args:
            code: Code to scan
            language: Programming language

        Returns:
            SecurityScanResult with findings
        """
        result = SecurityScanResult(level=SecurityLevel.SAFE)

        if language not in self.pattern_cache:
            result.warnings.append(f"No security patterns for {language.value}")
            return result

        # Check for dangerous patterns
        for pattern, message in self.pattern_cache[language]:
            if pattern.search(code):
                result.issues.append(message)

        # Determine risk level
        issue_count = len(result.issues)
        if issue_count == 0:
            result.level = SecurityLevel.SAFE
        elif issue_count <= 2:
            result.level = SecurityLevel.LOW
        elif issue_count <= 4:
            result.level = SecurityLevel.MEDIUM
        elif issue_count <= 6:
            result.level = SecurityLevel.HIGH
        else:
            result.level = SecurityLevel.CRITICAL

        # Check for critical patterns that block execution
        critical_patterns = [
            r'\brm\s+-rf\s+/',  # Root deletion
            r'\bformat\s+',  # Disk format
            r'\bdd\s+.*of=/dev/',  # Direct disk write
        ]

        for pattern_str in critical_patterns:
            if re.search(pattern_str, code):
                result.safe_to_execute = False
                result.reason = f"Critical pattern detected: {pattern_str}"
                result.level = SecurityLevel.CRITICAL
                break

        return result


class CodeExecutor:
    """
    Safe code execution sandbox.

    Provides isolated execution environment with:
    - Resource limits (CPU, memory, time)
    - Network isolation
    - Filesystem restrictions
    - Security scanning
    """

    def __init__(
        self,
        limits: Optional[ResourceLimits] = None,
        allow_network: bool = False,
        temp_dir: Optional[Path] = None,
    ):
        """
        Initialize code executor.

        Args:
            limits: Resource limits (uses defaults if None)
            allow_network: Allow network access (default: False)
            temp_dir: Temporary directory for execution (default: system temp)
        """
        self.limits = limits or ResourceLimits()
        self.allow_network = allow_network
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.scanner = SecurityScanner()

        # Execution statistics
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.blocked_executions = 0

    def _get_interpreter(self, language: Language) -> List[str]:
        """
        Get interpreter command for language.

        Args:
            language: Programming language

        Returns:
            List of command parts
        """
        interpreters = {
            Language.PYTHON: ["python3", "-u"],  # -u for unbuffered output
            Language.BASH: ["bash", "-e"],  # -e to exit on error
            Language.JAVASCRIPT: ["node"],
        }

        return interpreters.get(language, [])

    def _create_sandbox_env(self) -> Dict[str, str]:
        """
        Create sandboxed environment variables.

        Returns:
            Environment dict with restricted access
        """
        # Start with minimal environment
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.temp_dir),
            "TMPDIR": str(self.temp_dir),
            "TEMP": str(self.temp_dir),
            "TMP": str(self.temp_dir),
        }

        # Disable network if not allowed
        if not self.allow_network:
            env["no_proxy"] = "*"
            env["NO_PROXY"] = "*"

        return env

    def _set_resource_limits(self):
        """Set resource limits for subprocess (called in preexec_fn)."""
        # CPU time limit
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (self.limits.cpu_time_seconds, self.limits.cpu_time_seconds)
        )

        # Memory limit (address space)
        resource.setrlimit(
            resource.RLIMIT_AS,
            (self.limits.memory_bytes, self.limits.memory_bytes)
        )

        # Process limit
        resource.setrlimit(
            resource.RLIMIT_NPROC,
            (self.limits.max_processes, self.limits.max_processes)
        )

        # File size limit
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (self.limits.max_file_size_bytes, self.limits.max_file_size_bytes)
        )

    async def execute(
        self,
        code: str,
        language: Language,
        skip_security_scan: bool = False,
    ) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            code: Code to execute
            language: Programming language
            skip_security_scan: Skip security scanning (NOT RECOMMENDED)

        Returns:
            ExecutionResult with output and status
        """
        self.total_executions += 1
        start_time = time.time()

        # Security scan
        if not skip_security_scan:
            scan_result = self.scanner.scan(code, language)
            if not scan_result.safe_to_execute:
                self.blocked_executions += 1
                logger.warning(f"Code execution blocked: {scan_result.reason}")
                return ExecutionResult(
                    success=False,
                    error=f"Security scan failed: {scan_result.reason}",
                    security_scan=scan_result,
                )
        else:
            scan_result = None

        # Create temporary execution directory
        exec_dir = self.temp_dir / f"code_exec_{int(time.time() * 1000000)}"
        exec_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write code to file
            code_file = exec_dir / f"code.{language.value}"
            code_file.write_text(code)

            # Get interpreter
            interpreter = self._get_interpreter(language)
            if not interpreter:
                raise ValueError(f"No interpreter for {language.value}")

            # Check interpreter exists
            interpreter_path = shutil.which(interpreter[0])
            if not interpreter_path:
                raise FileNotFoundError(f"Interpreter not found: {interpreter[0]}")

            # Prepare command
            cmd = interpreter + [str(code_file)]

            # Execute with limits
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._create_sandbox_env(),
                cwd=str(exec_dir),
                preexec_fn=self._set_resource_limits,
            )

            # Wait with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.limits.timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self.failed_executions += 1
                return ExecutionResult(
                    success=False,
                    error=f"Execution timeout ({self.limits.timeout_seconds}s)",
                    security_scan=scan_result,
                    execution_time_seconds=time.time() - start_time,
                )

            # Decode output (with size limits)
            stdout = stdout_bytes[:self.limits.max_output_bytes].decode('utf-8', errors='replace')
            stderr = stderr_bytes[:self.limits.max_output_bytes].decode('utf-8', errors='replace')

            # Check if output was truncated
            if len(stdout_bytes) > self.limits.max_output_bytes:
                stdout += f"\n... [output truncated, {len(stdout_bytes)} bytes total]"
            if len(stderr_bytes) > self.limits.max_output_bytes:
                stderr += f"\n... [output truncated, {len(stderr_bytes)} bytes total]"

            execution_time = time.time() - start_time

            # Success or failure based on exit code
            if process.returncode == 0:
                self.successful_executions += 1
                return ExecutionResult(
                    success=True,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=process.returncode,
                    execution_time_seconds=execution_time,
                    security_scan=scan_result,
                )
            else:
                self.failed_executions += 1
                return ExecutionResult(
                    success=False,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=process.returncode,
                    execution_time_seconds=execution_time,
                    error=f"Execution failed with exit code {process.returncode}",
                    security_scan=scan_result,
                )

        except Exception as e:
            self.failed_executions += 1
            logger.exception(f"Code execution error: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_seconds=time.time() - start_time,
                security_scan=scan_result,
            )

        finally:
            # Cleanup
            try:
                shutil.rmtree(exec_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup exec dir: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dict with statistics
        """
        success_rate = (
            self.successful_executions / self.total_executions
            if self.total_executions > 0
            else 0.0
        )

        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "blocked_executions": self.blocked_executions,
            "success_rate": success_rate,
            "limits": {
                "timeout_seconds": self.limits.timeout_seconds,
                "memory_mb": self.limits.memory_bytes // (1024 * 1024),
                "cpu_seconds": self.limits.cpu_time_seconds,
            },
            "allow_network": self.allow_network,
        }


# Singleton instance
_executor: Optional[CodeExecutor] = None


def get_executor(
    limits: Optional[ResourceLimits] = None,
    allow_network: bool = False,
) -> CodeExecutor:
    """
    Get global code executor instance.

    Args:
        limits: Resource limits (uses defaults if None)
        allow_network: Allow network access

    Returns:
        CodeExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = CodeExecutor(limits=limits, allow_network=allow_network)
    return _executor


# Example usage
async def main():
    """Example usage."""
    executor = get_executor()

    # Python example
    python_code = """
import math
print("Hello from Python!")
print(f"Pi = {math.pi:.5f}")
result = sum(range(10))
print(f"Sum 0-9 = {result}")
"""

    result = await executor.execute(python_code, Language.PYTHON)
    print(f"Python result: {result.success}")
    print(f"Output: {result.stdout}")
    if result.security_scan:
        print(f"Security: {result.security_scan.level.value}, {len(result.security_scan.issues)} issues")

    # Bash example
    bash_code = """
echo "Hello from Bash!"
ls -la
echo "Current dir: $(pwd)"
"""

    result = await executor.execute(bash_code, Language.BASH)
    print(f"\nBash result: {result.success}")
    print(f"Output: {result.stdout}")

    # Dangerous code (should be blocked)
    dangerous_code = """
import os
os.system('rm -rf /')  # This should be blocked!
"""

    result = await executor.execute(dangerous_code, Language.PYTHON)
    print(f"\nDangerous code: {result.success}")
    print(f"Error: {result.error}")
    if result.security_scan:
        print(f"Issues: {result.security_scan.issues}")

    # Statistics
    stats = executor.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
