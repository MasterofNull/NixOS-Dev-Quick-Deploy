"""Runtime testing control routes for Phase 3.2 execution plumbing."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter()

REPO_ROOT = Path(os.getenv("REPO_ROOT", Path(__file__).resolve().parents[4]))
BASH_BIN = os.getenv("BASH_BIN", "bash")

TEST_SUITES: Dict[str, Dict[str, Any]] = {
    "property_based": {
        "id": "property_based",
        "title": "Property-Based Tests",
        "command": ["python3", "ai-stack/testing/property_based_tests.py"],
        "timeout_seconds": 90,
        "phase": "3.2",
    },
    "chaos_smoke": {
        "id": "chaos_smoke",
        "title": "Chaos Smoke",
        "command": ["bash", "scripts/testing/chaos-harness-smoke.sh"],
        "timeout_seconds": 120,
        "phase": "3.2",
    },
    "performance_benchmarks": {
        "id": "performance_benchmarks",
        "title": "Performance Benchmarks",
        "command": ["python3", "ai-stack/testing/performance_benchmarks.py"],
        "timeout_seconds": 180,
        "phase": "3.2",
    },
    "canary_suite": {
        "id": "canary_suite",
        "title": "PRSI Canary Suite",
        "command": ["bash", "scripts/automation/run-prsi-canary-suite.sh"],
        "timeout_seconds": 120,
        "phase": "3.2",
    },
}

testing_tasks: Dict[str, asyncio.Task[Any]] = {}
testing_processes: Dict[str, asyncio.subprocess.Process] = {}
testing_runs: Dict[str, Dict[str, Any]] = {}
testing_lock = asyncio.Lock()


class TestingExecutionRequest(BaseModel):
    suite_id: str = Field(..., pattern="^(property_based|chaos_smoke|performance_benchmarks|canary_suite)$")
    dry_run: bool = True
    confirm: bool = False
    user: str = "dashboard-operator"


async def _create_process(command: List[str]) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        *command,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _terminate_testing_process(execution_id: str) -> None:
    process = testing_processes.get(execution_id)
    if process is None or process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def _run_testing_suite(execution_id: str, suite: Dict[str, Any], request: TestingExecutionRequest) -> None:
    process: Optional[asyncio.subprocess.Process] = None
    try:
        if request.dry_run:
            testing_runs[execution_id].update(
                {
                    "status": "success",
                    "completed_at": _timestamp(),
                    "returncode": 0,
                    "output": "DRY RUN: execution plan accepted",
                }
            )
            return

        process = await _create_process(list(suite["command"]))
        testing_processes[execution_id] = process
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=int(suite["timeout_seconds"]))
        output = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).strip()
        if len(output) > 4000:
            output = "...[truncated]...\n" + output[-4000:]
        testing_runs[execution_id].update(
            {
                "status": "success" if process.returncode == 0 else "failed",
                "completed_at": _timestamp(),
                "returncode": process.returncode,
                "output": output,
            }
        )
    except asyncio.TimeoutError:
        await _terminate_testing_process(execution_id)
        testing_runs[execution_id].update(
            {
                "status": "failed",
                "completed_at": _timestamp(),
                "returncode": 124,
                "output": "Testing suite timed out",
            }
        )
    except asyncio.CancelledError:
        await _terminate_testing_process(execution_id)
        testing_runs[execution_id].update(
            {
                "status": "cancelled",
                "completed_at": _timestamp(),
                "returncode": -15,
                "output": "Testing suite cancelled during shutdown",
            }
        )
        raise
    finally:
        async with testing_lock:
            testing_tasks.pop(execution_id, None)
            testing_processes.pop(execution_id, None)


async def shutdown_testing_runner() -> None:
    async with testing_lock:
        tasks = list(testing_tasks.items())
    for execution_id, task in tasks:
        task.cancel()
        await _terminate_testing_process(execution_id)
    for _, task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


@router.get("/suites")
async def list_testing_suites() -> Dict[str, Any]:
    return {"suites": list(TEST_SUITES.values()), "count": len(TEST_SUITES)}


@router.get("/executions")
async def list_testing_executions() -> Dict[str, Any]:
    items = sorted(testing_runs.values(), key=lambda item: str(item.get("requested_at") or ""), reverse=True)
    return {"executions": items[:25], "count": len(items)}


@router.get("/executions/{execution_id}")
async def get_testing_execution(execution_id: str) -> Dict[str, Any]:
    execution = testing_runs.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Testing execution not found")
    return execution


@router.post("/execute")
async def execute_testing_suite(request: TestingExecutionRequest) -> Dict[str, Any]:
    suite = TEST_SUITES.get(request.suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="Testing suite not found")
    if not request.dry_run and not request.confirm:
        raise HTTPException(status_code=400, detail="Live testing execution requires explicit confirmation")

    execution_id = f"test-{uuid4()}"
    run = {
        "execution_id": execution_id,
        "suite_id": suite["id"],
        "title": suite["title"],
        "phase": suite["phase"],
        "status": "running" if not request.dry_run else "planned",
        "requested_at": _timestamp(),
        "completed_at": None,
        "dry_run": request.dry_run,
        "confirm": request.confirm,
        "user": request.user,
        "command": suite["command"],
        "timeout_seconds": suite["timeout_seconds"],
        "returncode": None,
        "output": "Execution queued" if not request.dry_run else "DRY RUN: execution plan accepted",
    }
    testing_runs[execution_id] = run

    if request.dry_run:
        run["status"] = "success"
        run["completed_at"] = _timestamp()
        run["returncode"] = 0
        return run

    async with testing_lock:
        task = asyncio.create_task(_run_testing_suite(execution_id, suite, request))
        testing_tasks[execution_id] = task
    return run
