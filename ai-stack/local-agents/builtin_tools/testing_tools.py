#!/usr/bin/env python3
"""
Testing tools for local agents — pytest wrappers with structured output.

Provides:
  run_tests           — run a test suite (pytest) and return structured results
  check_test_coverage — run pytest with coverage and return summary

Both tools stream subprocess output, parse pytest JSON report, and return
machine-readable results suitable for agent decision-making.
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool_registry import SafetyPolicy, ToolCategory, ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


async def _run_pytest(
    args: List[str],
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Run pytest with given args, return {success, stdout, stderr, returncode}."""
    pytest_cmd = ["python3", "-m", "pytest"] + args
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *pytest_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"pytest timed out after {timeout}s"}
    except FileNotFoundError:
        return {"success": False, "error": "python3 not found in PATH"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_pytest_json(report_path: str) -> Optional[Dict[str, Any]]:
    """Parse pytest JSON report. Returns None on failure."""
    try:
        with open(report_path) as f:
            data = json.load(f)
        summary = data.get("summary", {})
        tests = data.get("tests", [])
        failures = [
            {
                "nodeid": t["nodeid"],
                "call_longrepr": t.get("call", {}).get("longrepr", ""),
            }
            for t in tests
            if t.get("outcome") in ("failed", "error")
        ]
        return {
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "error": summary.get("error", 0),
            "skipped": summary.get("skipped", 0),
            "total": summary.get("total", 0),
            "duration": data.get("duration", 0),
            "failures": failures[:10],  # cap at 10 to avoid context bloat
        }
    except Exception:
        return None


async def run_tests_handler(
    path: str = ".",
    pattern: Optional[str] = None,
    keyword: Optional[str] = None,
    marker: Optional[str] = None,
    timeout: int = 120,
    extra_args: Optional[List[str]] = None,
) -> Dict:
    """Run pytest on the given path and return structured results."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        report_path = tf.name

    try:
        args = [
            path,
            f"--json-report",
            f"--json-report-file={report_path}",
            "--tb=short",
            "-q",
        ]
        if pattern:
            args += ["-k", pattern]
        if keyword:
            args += ["-k", keyword]
        if marker:
            args += ["-m", marker]
        if extra_args:
            args += extra_args

        result = await _run_pytest(args, timeout=timeout)

        parsed = _parse_pytest_json(report_path)
        if parsed:
            return {
                "success": result["success"],
                "summary": parsed,
                "stdout": result.get("stdout", "")[-3000:],
            }

        # fallback: parse stdout
        stdout = result.get("stdout", "")
        summary_line = ""
        for line in reversed(stdout.splitlines()):
            if "passed" in line or "failed" in line or "error" in line:
                summary_line = line.strip()
                break
        return {
            "success": result["success"],
            "summary_line": summary_line,
            "stdout": stdout[-3000:],
            "stderr": result.get("stderr", "")[-500:],
        }
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass


async def check_test_coverage_handler(
    path: str = ".",
    source: Optional[str] = None,
    min_coverage: Optional[float] = None,
    timeout: int = 180,
) -> Dict:
    """Run pytest with coverage and return per-module coverage summary."""
    args = [
        path,
        "--cov",
        "--cov-report=json",
        "--cov-report=term-missing:skip-covered",
        "-q",
        "--tb=no",
    ]
    if source:
        args += [f"--cov={source}"]
    if min_coverage is not None:
        args += [f"--cov-fail-under={min_coverage}"]

    with tempfile.TemporaryDirectory() as tmpdir:
        cov_json = os.path.join(tmpdir, "coverage.json")
        args += [f"--cov-report=json:{cov_json}"]

        result = await _run_pytest(args, timeout=timeout)

        coverage_data: Dict[str, Any] = {}
        try:
            with open(cov_json) as f:
                raw = json.load(f)
            totals = raw.get("totals", {})
            coverage_data = {
                "total_coverage_pct": totals.get("percent_covered", 0),
                "lines_covered": totals.get("covered_lines", 0),
                "lines_missing": totals.get("missing_lines", 0),
                "num_statements": totals.get("num_statements", 0),
            }
            # top 10 least-covered files
            files = raw.get("files", {})
            sorted_files = sorted(
                [
                    {
                        "file": k,
                        "coverage_pct": v.get("summary", {}).get("percent_covered", 0),
                        "missing": v.get("summary", {}).get("missing_lines", 0),
                    }
                    for k, v in files.items()
                ],
                key=lambda x: x["coverage_pct"],
            )
            coverage_data["least_covered"] = sorted_files[:10]
        except (OSError, json.JSONDecodeError, KeyError):
            pass

        stdout = result.get("stdout", "")
        return {
            "success": result["success"],
            "coverage": coverage_data,
            "stdout": stdout[-2000:],
            "passed_min_threshold": min_coverage is None or (
                coverage_data.get("total_coverage_pct", 0) >= min_coverage
            ),
        }


def register_testing_tools(registry: ToolRegistry) -> None:
    """Register pytest testing tools with the agent tool registry."""

    registry.register(ToolDefinition(
        name="run_tests",
        description=(
            "Run a pytest test suite and return structured pass/fail results. "
            "Returns summary counts (passed/failed/error/skipped), duration, and "
            "failure details (up to 10). Use for validating code changes before commit."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to test file, directory, or module (default: '.')",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "Filter tests by name pattern (pytest -k)",
                },
                "marker": {
                    "type": "string",
                    "description": "Filter by pytest marker (e.g. 'slow', 'integration')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait for test run (default: 120)",
                    "default": 120,
                },
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional pytest arguments",
                },
            },
            "required": [],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=run_tests_handler,
    ))

    registry.register(ToolDefinition(
        name="check_test_coverage",
        description=(
            "Run pytest with coverage analysis. Returns total coverage percentage, "
            "lines covered/missing, and a list of least-covered modules. "
            "Use to identify gaps before submitting code changes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Test path (default: '.')",
                    "default": ".",
                },
                "source": {
                    "type": "string",
                    "description": "Source package/path to measure coverage for",
                },
                "min_coverage": {
                    "type": "number",
                    "description": "Minimum required coverage % (fail if below)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds (default: 180)",
                    "default": 180,
                },
            },
            "required": [],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=check_test_coverage_handler,
    ))

    logger.info("Registered 2 testing tools")
