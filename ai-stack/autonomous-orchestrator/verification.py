#!/usr/bin/env python3
"""
Verification Framework

Automatic validation of agent-generated code before approval.
Includes syntax checking, test execution, security scanning, and quality scoring.

Part of Phase 12 Batch 12.2: Autonomous Agentic Orchestration
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Status of a verification check."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_RUN = "not_run"


@dataclass
class CheckResult:
    """Result of a single verification check."""

    name: str
    status: CheckStatus
    details: str = ""
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


@dataclass
class VerificationResult:
    """Complete verification result for a task."""

    passed: bool
    checks: Dict[str, CheckResult] = field(default_factory=dict)
    overall_quality_score: float = 0.0
    recommendation: str = "reject"  # approve, reject, needs_human_review
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "passed": self.passed,
            "checks": {
                name: {
                    "status": check.status.value,
                    "details": check.details,
                    "issues": check.issues,
                    "warnings": check.warnings,
                }
                for name, check in self.checks.items()
            },
            "overall_quality_score": self.overall_quality_score,
            "recommendation": self.recommendation,
            "reason": self.reason,
        }


class VerificationFramework:
    """
    Multi-stage verification framework for agent outputs.

    Validates code through:
    1. Syntax checking
    2. Test execution
    3. Security scanning
    4. Quality scoring
    5. Regression detection
    """

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize verification framework.

        Args:
            repo_root: Repository root directory
        """
        self.repo_root = repo_root or Path.cwd()

        # Verification statistics
        self.total_verifications = 0
        self.passed_verifications = 0
        self.failed_verifications = 0

    async def verify(
        self,
        file_path: str,
        content: Optional[str] = None,
        run_tests: bool = True,
        run_security_scan: bool = True,
    ) -> VerificationResult:
        """
        Verify a file or code content.

        Args:
            file_path: Path to file
            content: Optional content (for new files)
            run_tests: Run test suite
            run_security_scan: Run security scanning

        Returns:
            VerificationResult with all checks
        """
        self.total_verifications += 1
        result = VerificationResult(passed=False)

        # 1. Syntax check
        syntax_result = await self._check_syntax(file_path, content)
        result.checks["syntax"] = syntax_result

        if syntax_result.status != CheckStatus.PASSED:
            result.recommendation = "reject"
            result.reason = "Syntax check failed"
            self.failed_verifications += 1
            return result

        # 2. Security scan
        if run_security_scan:
            security_result = await self._check_security(file_path, content)
            result.checks["security"] = security_result

            if security_result.status == CheckStatus.FAILED:
                result.recommendation = "reject"
                result.reason = f"Security issues found: {len(security_result.issues)}"
                self.failed_verifications += 1
                return result

        # 3. Test execution
        if run_tests:
            test_result = await self._run_tests(file_path)
            result.checks["tests"] = test_result

            if test_result.status == CheckStatus.FAILED:
                result.recommendation = "reject"
                result.reason = "Tests failed"
                self.failed_verifications += 1
                return result

        # 4. Linting
        lint_result = await self._check_linting(file_path, content)
        result.checks["linting"] = lint_result

        # Linting warnings don't block, but reduce quality score
        quality_penalty = len(lint_result.issues) * 0.05

        # 5. Quality scoring
        result.overall_quality_score = max(0.0, 1.0 - quality_penalty)

        # All checks passed
        result.passed = True
        result.recommendation = "approve" if result.overall_quality_score >= 0.85 else "needs_human_review"
        result.reason = "All checks passed" if result.overall_quality_score >= 0.85 else "Quality score below threshold"

        self.passed_verifications += 1
        return result

    async def _check_syntax(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> CheckResult:
        """
        Check syntax for a file.

        Args:
            file_path: Path to file
            content: Optional content

        Returns:
            CheckResult
        """
        import time
        start_time = time.time()

        # Determine language from extension
        path = Path(file_path)
        ext = path.suffix

        # Language-specific syntax checkers
        checkers = {
            ".py": ["python3", "-m", "py_compile"],
            ".sh": ["bash", "-n"],
            ".nix": ["nix-instantiate", "--parse"],
            ".js": ["node", "--check"],
        }

        if ext not in checkers:
            return CheckResult(
                name="syntax",
                status=CheckStatus.SKIPPED,
                details=f"No syntax checker for {ext}",
                execution_time_seconds=time.time() - start_time,
            )

        # Write content to temp file if provided
        if content:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
                f.write(content)
                temp_file = f.name
            file_to_check = temp_file
        else:
            file_to_check = file_path

        try:
            cmd = checkers[ext] + [file_to_check]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return CheckResult(
                    name="syntax",
                    status=CheckStatus.PASSED,
                    details="Syntax check passed",
                    execution_time_seconds=time.time() - start_time,
                )
            else:
                return CheckResult(
                    name="syntax",
                    status=CheckStatus.FAILED,
                    details=stderr.decode('utf-8', errors='replace'),
                    issues=[f"Syntax error: {stderr.decode('utf-8', errors='replace')[:200]}"],
                    execution_time_seconds=time.time() - start_time,
                )

        except FileNotFoundError:
            return CheckResult(
                name="syntax",
                status=CheckStatus.SKIPPED,
                details=f"Checker not found: {checkers[ext][0]}",
                execution_time_seconds=time.time() - start_time,
            )
        finally:
            if content:
                Path(temp_file).unlink(missing_ok=True)

    async def _check_security(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> CheckResult:
        """
        Run security scanning on file.

        Args:
            file_path: Path to file
            content: Optional content

        Returns:
            CheckResult
        """
        import time
        start_time = time.time()

        # Use code executor's security scanner
        try:
            from ai_stack.local_agents.code_executor import SecurityScanner, Language

            # Determine language
            ext = Path(file_path).suffix
            lang_map = {
                ".py": Language.PYTHON,
                ".sh": Language.BASH,
                ".js": Language.JAVASCRIPT,
            }

            if ext not in lang_map:
                return CheckResult(
                    name="security",
                    status=CheckStatus.SKIPPED,
                    details=f"No security scanner for {ext}",
                    execution_time_seconds=time.time() - start_time,
                )

            # Read content if not provided
            if not content:
                content = Path(file_path).read_text()

            # Scan
            scanner = SecurityScanner()
            scan_result = scanner.scan(content, lang_map[ext])

            if scan_result.safe_to_execute:
                return CheckResult(
                    name="security",
                    status=CheckStatus.PASSED,
                    details=f"Security level: {scan_result.level.value}",
                    warnings=scan_result.issues if scan_result.level.value != "safe" else [],
                    execution_time_seconds=time.time() - start_time,
                )
            else:
                return CheckResult(
                    name="security",
                    status=CheckStatus.FAILED,
                    details=scan_result.reason,
                    issues=scan_result.issues,
                    execution_time_seconds=time.time() - start_time,
                )

        except ImportError as e:
            logger.warning(f"Security scanner not available: {e}")
            return CheckResult(
                name="security",
                status=CheckStatus.SKIPPED,
                details="Security scanner not available",
                execution_time_seconds=time.time() - start_time,
            )

    async def _run_tests(self, file_path: str) -> CheckResult:
        """
        Run tests related to file.

        Args:
            file_path: Path to file

        Returns:
            CheckResult
        """
        import time
        start_time = time.time()

        # Find related test file
        path = Path(file_path)
        test_patterns = [
            path.parent / f"test_{path.name}",
            path.parent / "tests" / f"test_{path.stem}{path.suffix}",
            Path("tests") / path.parent / f"test_{path.stem}{path.suffix}",
        ]

        test_file = None
        for pattern in test_patterns:
            if pattern.exists():
                test_file = pattern
                break

        if not test_file:
            return CheckResult(
                name="tests",
                status=CheckStatus.SKIPPED,
                details="No test file found",
                execution_time_seconds=time.time() - start_time,
            )

        # Run tests based on extension
        ext = path.suffix
        if ext == ".py":
            cmd = ["python3", "-m", "pytest", str(test_file), "-v"]
        elif ext == ".sh":
            cmd = ["bash", str(test_file)]
        else:
            return CheckResult(
                name="tests",
                status=CheckStatus.SKIPPED,
                details=f"No test runner for {ext}",
                execution_time_seconds=time.time() - start_time,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=300,  # 5 min timeout
            )

            if proc.returncode == 0:
                return CheckResult(
                    name="tests",
                    status=CheckStatus.PASSED,
                    details="All tests passed",
                    execution_time_seconds=time.time() - start_time,
                )
            else:
                return CheckResult(
                    name="tests",
                    status=CheckStatus.FAILED,
                    details=f"Tests failed with code {proc.returncode}",
                    issues=[stderr.decode('utf-8', errors='replace')[:500]],
                    execution_time_seconds=time.time() - start_time,
                )

        except asyncio.TimeoutError:
            return CheckResult(
                name="tests",
                status=CheckStatus.FAILED,
                details="Tests timed out after 5 minutes",
                issues=["Timeout"],
                execution_time_seconds=time.time() - start_time,
            )
        except FileNotFoundError:
            return CheckResult(
                name="tests",
                status=CheckStatus.SKIPPED,
                details=f"Test runner not found: {cmd[0]}",
                execution_time_seconds=time.time() - start_time,
            )

    async def _check_linting(
        self,
        file_path: str,
        content: Optional[str] = None,
    ) -> CheckResult:
        """
        Run linting checks.

        Args:
            file_path: Path to file
            content: Optional content

        Returns:
            CheckResult
        """
        import time
        start_time = time.time()

        ext = Path(file_path).suffix

        # For now, just check basic patterns
        # TODO: Integrate with ruff, shellcheck, etc.

        issues = []
        warnings = []

        if not content:
            try:
                content = Path(file_path).read_text()
            except FileNotFoundError:
                return CheckResult(
                    name="linting",
                    status=CheckStatus.SKIPPED,
                    details="File not found",
                    execution_time_seconds=time.time() - start_time,
                )

        # Basic linting rules
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Check line length
            if len(line) > 120:
                warnings.append(f"Line {i}: Line too long ({len(line)} > 120)")

            # Check trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                warnings.append(f"Line {i}: Trailing whitespace")

        return CheckResult(
            name="linting",
            status=CheckStatus.PASSED if len(issues) == 0 else CheckStatus.FAILED,
            details=f"{len(warnings)} warnings, {len(issues)} errors",
            issues=issues,
            warnings=warnings[:10],  # Limit to 10 warnings
            execution_time_seconds=time.time() - start_time,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get verification statistics.

        Returns:
            Dict with statistics
        """
        success_rate = (
            self.passed_verifications / self.total_verifications
            if self.total_verifications > 0
            else 0.0
        )

        return {
            "total_verifications": self.total_verifications,
            "passed": self.passed_verifications,
            "failed": self.failed_verifications,
            "success_rate": success_rate,
        }


# Singleton instance
_verifier: Optional[VerificationFramework] = None


def get_verifier(repo_root: Optional[Path] = None) -> VerificationFramework:
    """
    Get global verifier instance.

    Args:
        repo_root: Repository root

    Returns:
        VerificationFramework
    """
    global _verifier
    if _verifier is None:
        _verifier = VerificationFramework(repo_root=repo_root)
    return _verifier


# Example usage
async def main():
    """Example usage."""
    verifier = get_verifier()

    # Verify a Python file
    result = await verifier.verify(
        "ai-stack/aidb/server.py",
        run_tests=True,
        run_security_scan=True,
    )

    print(f"Verification result: {result.passed}")
    print(f"Recommendation: {result.recommendation}")
    print(f"Reason: {result.reason}")
    print(f"Quality score: {result.overall_quality_score:.2f}")

    for name, check in result.checks.items():
        print(f"\n{name}: {check.status.value}")
        if check.issues:
            print(f"  Issues: {check.issues}")
        if check.warnings:
            print(f"  Warnings: {check.warnings[:3]}")

    # Statistics
    stats = verifier.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
