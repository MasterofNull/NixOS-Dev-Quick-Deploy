#!/usr/bin/env python3
"""
Aider-Wrapper MCP Server v3.1
Async Aider invocations with a semaphore-gated task queue and status polling.
"""

import asyncio
import os
import sys
import json
import socket
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import uvicorn
import structlog

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.auth_middleware import get_api_key_dependency

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def load_api_key() -> Optional[str]:
    """Load API key from runtime secret file only."""
    secret_file = os.environ.get("AIDER_WRAPPER_API_KEY_FILE", "/run/secrets/aider_wrapper_api_key")
    if Path(secret_file).exists():
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return None


api_key = load_api_key()
require_auth = get_api_key_dependency(
    service_name="aider-wrapper",
    expected_key=api_key,
    optional=not api_key,
)

app = FastAPI(
    title="Aider-Wrapper MCP Server v3",
    description="Real Aider integration for autonomous code modification",
    version="3.1.0",
)

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE = os.getenv("AIDER_WORKSPACE", "/workspace")
LLAMA_CPP_URL = f"http://{os.getenv('LLAMA_CPP_HOST', 'llama-cpp')}:{os.getenv('LLAMA_CPP_PORT', '8080')}"
MODEL_NAME = os.getenv("LLAMA_CPP_MODEL", "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
# Maximum concurrent Aider processes (memory-intensive; default 1)
AIDER_MAX_CONCURRENCY = int(os.getenv("AIDER_MAX_CONCURRENCY", "1"))

# ============================================================================
# In-memory task store
# ============================================================================

_tasks: Dict[str, dict] = {}
_task_semaphore: Optional[asyncio.Semaphore] = None


# ============================================================================
# Request / Response Models
# ============================================================================

class TaskRequest(BaseModel):
    """Task request for Aider execution."""
    prompt: str = Field(..., description="Task description for Aider")
    files: List[str] = Field(default_factory=list, description="Files to include in context")
    model: str = Field(default="openai/gpt-4o", description="Model to use (ignored, uses llama.cpp)")
    max_tokens: int = Field(default=4000, description="Max tokens")
    workspace: str = Field(default=WORKSPACE, description="Working directory")
    # Ralph compatibility fields
    context: Optional[dict] = Field(default=None, description="Additional context from Ralph")
    iteration: Optional[int] = Field(default=1, description="Iteration number from Ralph")
    mode: Optional[str] = Field(default="autonomous", description="Execution mode")


class TaskResponse(BaseModel):
    """Completed task result (nested inside status response)."""
    status: str
    output: str
    error: Optional[str] = None
    files_modified: List[str] = []
    git_commits: List[str] = []
    duration_seconds: float = 0.0
    exit_code: int = 0
    completed: bool = False


class TaskSubmitResponse(BaseModel):
    """Immediate response from task submission."""
    task_id: str
    status: str = "queued"
    message: str = "Task submitted"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    aider_available: bool
    workspace: str
    llama_cpp_url: str


# ============================================================================
# FastAPI startup: initialise semaphore + verify aider binary
# ============================================================================

@app.on_event("startup")
async def _startup() -> None:
    global _task_semaphore
    _task_semaphore = asyncio.Semaphore(AIDER_MAX_CONCURRENCY)
    logger.info("aider_wrapper_starting", version="3.1.0", workspace=WORKSPACE,
                max_concurrency=AIDER_MAX_CONCURRENCY)
    try:
        proc = await asyncio.create_subprocess_exec(
            "aider", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode == 0:
            logger.info("aider_found", version=stdout.decode("utf-8", errors="replace").strip())
        else:
            logger.error("aider_not_found", message="Aider binary not available")
    except asyncio.TimeoutError:
        logger.error("aider_version_check_timeout")
    except Exception as exc:
        logger.error("aider_check_failed", error=str(exc))


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    aider_available = False
    try:
        proc = await asyncio.create_subprocess_exec(
            "aider", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            aider_available = proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
    except Exception:
        pass

    return {
        "status": "healthy" if aider_available else "degraded",
        "version": "3.1.0",
        "aider_available": aider_available,
        "workspace": WORKSPACE,
        "llama_cpp_url": LLAMA_CPP_URL,
    }


# ============================================================================
# Internal: async Aider runner (semaphore-gated)
# ============================================================================

async def _run_aider_task(task_id: str, task: TaskRequest) -> None:
    """Run one Aider task, respecting the concurrency semaphore. Updates _tasks in place."""
    _tasks[task_id]["status"] = "waiting"
    async with _task_semaphore:
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = datetime.now().isoformat()
        start_time = datetime.now()

        workspace_path = Path(task.workspace)
        if not workspace_path.exists():
            _tasks[task_id].update({
                "status": "error",
                "finished_at": datetime.now().isoformat(),
                "result": {
                    "status": "error",
                    "output": "",
                    "error": f"Workspace does not exist: {task.workspace}",
                    "files_modified": [],
                    "git_commits": [],
                    "duration_seconds": 0.0,
                    "exit_code": 1,
                    "completed": False,
                },
            })
            return

        logger.info("aider_task_start", task_id=task_id,
                    prompt_length=len(task.prompt), files=task.files,
                    iteration=task.iteration, workspace=task.workspace)

        cmd = [
            "aider",
            "--yes",
            "--no-auto-commits",
            "--model", f"openai/{MODEL_NAME}",
            "--openai-api-base", f"{LLAMA_CPP_URL}/v1",
            "--openai-api-key", "dummy",
        ]
        for file in (task.files or []):
            file_path = workspace_path / file
            if file_path.exists():
                cmd.extend(["--file", str(file_path)])
            else:
                logger.warning("file_not_found", file=file)
        cmd.extend(["--message", task.prompt])

        logger.info("executing_aider", command=" ".join(cmd[:10]))

        output = ""
        error_text: Optional[str] = None
        returncode = 1

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=task.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=300.0
            )
            output = stdout_bytes.decode("utf-8", errors="replace")
            returncode = proc.returncode
            if returncode != 0:
                error_text = stderr_bytes.decode("utf-8", errors="replace")

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_timeout", task_id=task_id, duration=duration)
            _tasks[task_id].update({
                "status": "error",
                "finished_at": datetime.now().isoformat(),
                "result": {
                    "status": "error",
                    "output": "",
                    "error": "Aider execution timed out after 5 minutes",
                    "files_modified": [],
                    "git_commits": [],
                    "duration_seconds": duration,
                    "exit_code": 124,
                    "completed": False,
                },
            })
            return

        except Exception as exc:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_exception", task_id=task_id, error=str(exc), duration=duration)
            _tasks[task_id].update({
                "status": "error",
                "finished_at": datetime.now().isoformat(),
                "result": {
                    "status": "error",
                    "output": "",
                    "error": f"Exception: {exc}",
                    "files_modified": [],
                    "git_commits": [],
                    "duration_seconds": duration,
                    "exit_code": 1,
                    "completed": False,
                },
            })
            return

        duration = (datetime.now() - start_time).total_seconds()

        # Detect modified files from Aider stdout
        files_modified = []
        for line in output.split("\n"):
            if "modified:" in line.lower() or "created:" in line.lower():
                parts = line.split()
                if len(parts) > 1:
                    files_modified.append(parts[-1])

        # Collect recent git commits
        git_commits = []
        try:
            git_proc = await asyncio.create_subprocess_exec(
                "git", "log", "--oneline", "-5",
                cwd=task.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                git_stdout, _ = await asyncio.wait_for(git_proc.communicate(), timeout=5.0)
                if git_proc.returncode == 0:
                    git_commits = [
                        line.strip()
                        for line in git_stdout.decode("utf-8").split("\n")
                        if line.strip()
                    ][:3]
            except asyncio.TimeoutError:
                git_proc.kill()
        except Exception:
            pass

        completed = returncode == 0 and len(files_modified) > 0
        final_status = "success" if returncode == 0 else "error"

        logger.info("aider_task_complete", task_id=task_id, exit_code=returncode,
                    files_modified=len(files_modified), duration=duration, completed=completed)

        _tasks[task_id].update({
            "status": final_status,
            "finished_at": datetime.now().isoformat(),
            "result": {
                "status": final_status,
                "output": output,
                "error": error_text,
                "files_modified": files_modified,
                "git_commits": git_commits,
                "duration_seconds": duration,
                "exit_code": returncode,
                "completed": completed,
            },
        })


# ============================================================================
# Task Submission
# ============================================================================

async def _do_submit(task: TaskRequest) -> TaskSubmitResponse:
    task_id = str(uuid4())
    _tasks[task_id] = {
        "status": "queued",
        "submitted_at": datetime.now().isoformat(),
        "request": task.dict(),
    }
    asyncio.create_task(_run_aider_task(task_id, task))
    logger.info("aider_task_queued", task_id=task_id, workspace=task.workspace)
    return TaskSubmitResponse(task_id=task_id)


@app.post("/tasks", response_model=TaskSubmitResponse)
async def submit_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """Submit a task. Returns task_id immediately; poll GET /tasks/{task_id}/status."""
    return await _do_submit(task)


@app.post("/execute", response_model=TaskSubmitResponse)
@app.post("/api/execute", response_model=TaskSubmitResponse)
async def execute_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """Legacy alias for POST /tasks."""
    return await _do_submit(task)


# ============================================================================
# Task Status Polling
# ============================================================================

@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str, auth: str = Depends(require_auth)):
    """Poll task status. Terminal states: success, error."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    entry = _tasks[task_id]
    response: dict = {"task_id": task_id, "status": entry["status"]}
    for key in ("submitted_at", "started_at", "finished_at"):
        if key in entry:
            response[key] = entry[key]
    if "result" in entry:
        response["result"] = entry["result"]
    return response


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("AIDER_WRAPPER_PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
