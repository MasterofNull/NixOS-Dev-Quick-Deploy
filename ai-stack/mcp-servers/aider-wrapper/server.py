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
import urllib.request
import urllib.parse
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
AIDER_BIN = os.getenv("AIDER_BIN", "aider")
# Maximum concurrent Aider processes (memory-intensive; default 1)
AIDER_MAX_CONCURRENCY = int(os.getenv("AIDER_MAX_CONCURRENCY", "1"))
AIDER_TASK_TIMEOUT = float(os.getenv("AIDER_TASK_TIMEOUT_SECONDS", "600.0"))
AIDER_TERMINATE_GRACE_SECONDS = float(os.getenv("AIDER_TERMINATE_GRACE_SECONDS", "5.0"))
AIDER_WATCHDOG_INTERVAL_SECONDS = float(os.getenv("AIDER_WATCHDOG_INTERVAL_SECONDS", "10.0"))
AIDER_WATCHDOG_MAX_RUNTIME_SECONDS = float(
    os.getenv("AIDER_WATCHDOG_MAX_RUNTIME_SECONDS", str(min(180.0, AIDER_TASK_TIMEOUT)))
)

# Phase 14.1.1 — bubblewrap filesystem sandbox for Aider subprocess.
# When AI_AIDER_SANDBOX=true: aider runs inside bwrap with /nix/store read-only,
# workspace read-write, isolated /tmp, and full network (loopback for llama.cpp API).
# Network is NOT isolated here; systemd IPAddressDeny at the service level restricts
# egress to loopback only.
AI_AIDER_SANDBOX = os.getenv("AI_AIDER_SANDBOX", "false").lower() == "true"
BWRAP_PATH = os.getenv("BWRAP_PATH", "bwrap")
AI_AIDER_SANDBOX_FALLBACK_UNSAFE = os.getenv(
    "AI_AIDER_SANDBOX_FALLBACK_UNSAFE", "true"
).lower() == "true"

# Phase 19.3.3 — aq-hints injection: prepend top ranked hint to aider --message.
# Fetches from HINTS_URL (hybrid-coordinator /hints), enriching the task with
# context from registry.yaml, query gaps, and CLAUDE.md workflow rules.
AI_HINTS_ENABLED = os.getenv("AI_HINTS_ENABLED", "false").lower() == "true"
AI_TOOLING_PLAN_ENABLED = os.getenv("AI_TOOLING_PLAN_ENABLED", "true").lower() == "true"
HINTS_URL = os.getenv(
    "HINTS_URL",
    f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/hints",
)
WORKFLOW_PLAN_URL = os.getenv(
    "WORKFLOW_PLAN_URL",
    f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/workflow/plan",
)
HYBRID_API_KEY = os.getenv("HYBRID_API_KEY", "")
HYBRID_API_KEY_FILE = os.getenv("HYBRID_API_KEY_FILE", "/run/secrets/hybrid_api_key")


def _load_hybrid_api_key() -> str:
    """Load hybrid API key for authenticated /hints calls."""
    if HYBRID_API_KEY:
        return HYBRID_API_KEY.strip()
    p = Path(HYBRID_API_KEY_FILE)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""

# Phase 19.3.4 — hint adoption tracking: written alongside tool-audit.jsonl.
_audit_dir = Path(os.getenv(
    "TOOL_AUDIT_LOG_PATH", "/var/log/nixos-ai-stack/tool-audit.jsonl"
)).parent
HINT_AUDIT_LOG_PATH = Path(os.getenv("HINT_AUDIT_LOG_PATH", str(_audit_dir / "hint-audit.jsonl")))

# ============================================================================
# In-memory task store
# ============================================================================

_tasks: Dict[str, dict] = {}
_task_semaphore: Optional[asyncio.Semaphore] = None
_task_processes: Dict[str, asyncio.subprocess.Process] = {}
_task_cancel_reasons: Dict[str, str] = {}
_watchdog_task: Optional[asyncio.Task] = None


def _write_hint_audit(task_id: str, hint_id: str, hint_snippet: str, accepted: bool) -> None:
    """Phase 19.3.4 — append a hint adoption record to hint-audit.jsonl."""
    try:
        entry = json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "aider-wrapper",
            "task_id": task_id,
            "hint_id": hint_id,
            "hint_snippet": hint_snippet[:80],
            "hint_accepted": accepted,
        })
        HINT_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HINT_AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as exc:
        logger.debug("hint_audit_write_failed", error=str(exc))


def _apply_bwrap(cmd: List[str], workspace: str) -> List[str]:
    """Phase 14.1.1 — wrap cmd in a bubblewrap filesystem sandbox.

    Security model:
      - /nix/store bound read-only   — all Nix executables/libraries accessible
      - workspace bound read-write   — aider is allowed to modify code files here
      - /tmp as tmpfs                — isolated, cleared after each invocation
      - /etc, /dev, /proc mounted    — needed for git, tty detection, process ops
      - Network NOT isolated         — loopback needed for llama.cpp API on :8080;
                                      systemd IPAddressDeny restricts actual egress
    """
    ws = str(workspace)
    return [
        BWRAP_PATH,
        "--ro-bind", "/nix/store", "/nix/store",   # Nix executables (read-only)
        "--bind", ws, ws,                           # workspace (read-write)
        "--ro-bind", "/etc", "/etc",                # git config, passwd, CA certs
        "--dev", "/dev",                            # /dev/null, /dev/urandom etc.
        "--proc", "/proc",                          # needed by some git operations
        "--tmpfs", "/tmp",                          # isolated temp directory
        "--new-session",                            # detach from controlling tty
        "--die-with-parent",                        # clean up on wrapper exit
        "--",
    ] + cmd


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


class TaskSummaryResponse(BaseModel):
    """Current queue depth and last observed terminal task state."""
    active_tasks: int
    last_task_status: str
    last_task_id: Optional[str] = None


# ============================================================================
# FastAPI startup: initialise semaphore + verify aider binary
# ============================================================================

@app.on_event("startup")
async def _startup() -> None:
    global _task_semaphore, _watchdog_task
    _task_semaphore = asyncio.Semaphore(AIDER_MAX_CONCURRENCY)
    logger.info("aider_wrapper_starting", version="3.1.0", workspace=WORKSPACE,
                max_concurrency=AIDER_MAX_CONCURRENCY)
    try:
        proc = await asyncio.create_subprocess_exec(
            AIDER_BIN, "--version",
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

    _watchdog_task = asyncio.create_task(_task_watchdog_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        _watchdog_task.cancel()
        try:
            await _watchdog_task
        except asyncio.CancelledError:
            pass


def _now_iso() -> str:
    return datetime.now().isoformat()


def _set_terminal_task(
    task_id: str,
    *,
    status: str,
    output: str,
    error: str,
    files_modified: List[str],
    git_commits: List[str],
    duration_seconds: float,
    exit_code: int,
    completed: bool,
) -> None:
    _tasks[task_id].update({
        "status": status,
        "finished_at": _now_iso(),
        "result": {
            "status": status,
            "output": output,
            "error": error,
            "files_modified": files_modified,
            "git_commits": git_commits,
            "duration_seconds": duration_seconds,
            "exit_code": exit_code,
            "completed": completed,
        },
    })


async def _terminate_process(task_id: str, proc: asyncio.subprocess.Process, reason: str) -> None:
    """Graceful terminate with hard kill escalation."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=AIDER_TERMINATE_GRACE_SECONDS)
    except Exception:
        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            pass
    logger.warning("aider_task_process_terminated", task_id=task_id, reason=reason)


async def _task_watchdog_loop() -> None:
    """Kill runaway running tasks that exceed watchdog runtime."""
    while True:
        try:
            await asyncio.sleep(max(1.0, AIDER_WATCHDOG_INTERVAL_SECONDS))
            now = datetime.now().timestamp()
            for task_id, entry in list(_tasks.items()):
                if entry.get("status") != "running":
                    continue
                started_raw = entry.get("started_at")
                if not isinstance(started_raw, str):
                    continue
                try:
                    started_ts = datetime.fromisoformat(started_raw).timestamp()
                except ValueError:
                    continue
                runtime = now - started_ts
                if runtime < AIDER_WATCHDOG_MAX_RUNTIME_SECONDS:
                    continue
                proc = _task_processes.get(task_id)
                if proc is None:
                    continue
                _task_cancel_reasons[task_id] = "watchdog_timeout"
                await _terminate_process(task_id, proc, "watchdog_timeout")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("aider_watchdog_error", error=str(exc))


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    aider_available = False
    try:
        proc = await asyncio.create_subprocess_exec(
            AIDER_BIN, "--version",
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
        if task_id in _task_cancel_reasons:
            _set_terminal_task(
                task_id,
                status="canceled",
                output="",
                error=_task_cancel_reasons.pop(task_id, "Task canceled before execution"),
                files_modified=[],
                git_commits=[],
                duration_seconds=0.0,
                exit_code=130,
                completed=False,
            )
            return
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = _now_iso()
        start_time = datetime.now()

        workspace_path = Path(task.workspace)
        if not workspace_path.exists():
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error=f"Workspace does not exist: {task.workspace}",
                files_modified=[],
                git_commits=[],
                duration_seconds=0.0,
                exit_code=1,
                completed=False,
            )
            return

        logger.info("aider_task_start", task_id=task_id,
                    prompt_length=len(task.prompt), files=task.files,
                    iteration=task.iteration, workspace=task.workspace)

        # Phase 19.3.3 — fetch top aq-hint and prepend to prompt for steered execution.
        hint_id = ""
        hint_snippet = ""
        hint_injected = False
        _tasks[task_id]["tooling"] = {
            "hints_enabled": AI_HINTS_ENABLED,
            "hint_injected": False,
            "hint_id": "",
            "tooling_plan_enabled": AI_TOOLING_PLAN_ENABLED,
            "tooling_plan_injected": False,
            "tooling_plan_phase_count": 0,
        }
        message_for_aider = task.prompt
        if AI_HINTS_ENABLED:
            try:
                params = urllib.parse.urlencode({"q": task.prompt[:100], "max": "1"})
                hints_headers = {"Accept": "application/json"}
                hybrid_key = _load_hybrid_api_key()
                if hybrid_key:
                    hints_headers["X-API-Key"] = hybrid_key
                req = urllib.request.Request(
                    f"{HINTS_URL}?{params}",
                    headers=hints_headers,
                )
                loop = asyncio.get_event_loop()
                def _fetch_hint():
                    with urllib.request.urlopen(req, timeout=2) as r:
                        return json.loads(r.read())
                hints_data = await loop.run_in_executor(None, _fetch_hint)
                top_hints = hints_data.get("hints", [])
                if top_hints:
                    top = top_hints[0]
                    hint_id = top.get("id", "")
                    hint_snippet = top.get("snippet", "")[:150]
                    message_for_aider = f"CONTEXT (aq-hints): {hint_snippet}\n\n{task.prompt}"
                    hint_injected = True
                    _tasks[task_id]["tooling"]["hint_injected"] = True
                    _tasks[task_id]["tooling"]["hint_id"] = hint_id
                    logger.info("hint_injected", task_id=task_id, hint_id=hint_id)
            except Exception as exc:
                logger.debug("hint_fetch_skipped", task_id=task_id, error=str(exc))

        # Semantic tooling plan auto-injection: exposes planned tool phases to
        # aider so task execution can follow the stack's orchestrated tool layer.
        if AI_TOOLING_PLAN_ENABLED:
            try:
                plan_headers = {"Accept": "application/json", "Content-Type": "application/json"}
                hybrid_key = _load_hybrid_api_key()
                if hybrid_key:
                    plan_headers["X-API-Key"] = hybrid_key
                plan_req = urllib.request.Request(
                    WORKFLOW_PLAN_URL,
                    data=json.dumps({"query": task.prompt[:500]}).encode("utf-8"),
                    headers=plan_headers,
                    method="POST",
                )
                loop = asyncio.get_event_loop()
                def _fetch_plan():
                    with urllib.request.urlopen(plan_req, timeout=2) as r:
                        return json.loads(r.read())
                plan_data = await loop.run_in_executor(None, _fetch_plan)
                phases: List[dict] = []
                if isinstance(plan_data, dict):
                    # Prefer current schema: top-level "phases".
                    top_level = plan_data.get("phases", [])
                    if isinstance(top_level, list):
                        phases = [p for p in top_level if isinstance(p, dict)]
                    # Backward-compatible fallback: nested under "plan.phases".
                    if not phases:
                        legacy = plan_data.get("plan", {})
                        legacy_phases = legacy.get("phases", []) if isinstance(legacy, dict) else []
                        if isinstance(legacy_phases, list):
                            phases = [p for p in legacy_phases if isinstance(p, dict)]
                if phases:
                    phase_lines = []
                    for phase in phases[:3]:
                        pid = str(phase.get("id", "phase")).strip()
                        tools = [
                            str(t.get("name", "")).strip()
                            for t in (phase.get("tools", []) if isinstance(phase.get("tools", []), list) else [])
                            if isinstance(t, dict) and str(t.get("name", "")).strip()
                        ]
                        if tools:
                            phase_lines.append(f"- {pid}: {', '.join(tools[:4])}")
                    if phase_lines:
                        plan_prefix = "TOOLING PLAN (auto):\n" + "\n".join(phase_lines) + "\n\n"
                        message_for_aider = plan_prefix + message_for_aider
                        _tasks[task_id]["tooling"]["tooling_plan_injected"] = True
                        _tasks[task_id]["tooling"]["tooling_plan_phase_count"] = len(phase_lines)
                        logger.info("tooling_plan_injected", task_id=task_id, phases=len(phase_lines))
            except Exception as exc:
                logger.debug("tooling_plan_fetch_skipped", task_id=task_id, error=str(exc))

        base_cmd = [
            AIDER_BIN,
            "--yes",
            "--no-auto-commits",
            "--model", f"openai/{MODEL_NAME}",
            "--openai-api-base", f"{LLAMA_CPP_URL}/v1",
            "--openai-api-key", "dummy",
        ]
        for file in (task.files or []):
            file_path = workspace_path / file
            if file_path.exists():
                base_cmd.extend(["--file", str(file_path)])
            else:
                logger.warning("file_not_found", file=file)
        base_cmd.extend(["--message", message_for_aider])

        # Phase 14.1.1 — optionally wrap in bubblewrap filesystem sandbox.
        cmd = list(base_cmd)
        sandbox_applied = False
        if AI_AIDER_SANDBOX:
            cmd = _apply_bwrap(cmd, task.workspace)
            sandbox_applied = True
            logger.info("aider_sandbox_enabled", bwrap=BWRAP_PATH)

        logger.info("executing_aider", command=" ".join(cmd[:10]))

        output = ""
        error_text: Optional[str] = None
        returncode = 1

        async def _run_command(exec_cmd: List[str]) -> tuple[str, str, int]:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                cwd=task.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _task_processes[task_id] = proc
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=AIDER_TASK_TIMEOUT
                )
                return (
                    stdout_bytes.decode("utf-8", errors="replace"),
                    stderr_bytes.decode("utf-8", errors="replace"),
                    int(proc.returncode),
                )
            except asyncio.TimeoutError:
                _task_cancel_reasons[task_id] = "timeout"
                await _terminate_process(task_id, proc, "timeout")
                raise
            finally:
                _task_processes.pop(task_id, None)

        try:
            output, stderr_text, returncode = await _run_command(cmd)
            if returncode != 0:
                error_text = stderr_text
                if (
                    sandbox_applied
                    and AI_AIDER_SANDBOX_FALLBACK_UNSAFE
                    and (
                        "No permissions to creating new namespace" in stderr_text
                        or "unprivileged_userns_clone" in stderr_text
                        or "Operation not permitted" in stderr_text
                    )
                ):
                    logger.warning(
                        "aider_sandbox_fallback_unsandboxed task_id=%s reason=userns_unavailable",
                        task_id,
                    )
                    output, stderr_text, returncode = await _run_command(base_cmd)
                    error_text = stderr_text if returncode != 0 else None

        except asyncio.TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_timeout", task_id=task_id, duration=duration)
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error="Aider execution timed out",
                files_modified=[],
                git_commits=[],
                duration_seconds=duration,
                exit_code=124,
                completed=False,
            )
            return

        except Exception as exc:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_exception", task_id=task_id, error=str(exc), duration=duration)
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error=f"Exception: {exc}",
                files_modified=[],
                git_commits=[],
                duration_seconds=duration,
                exit_code=1,
                completed=False,
            )
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

        cancelled_reason = _task_cancel_reasons.pop(task_id, "")
        cancelled = bool(cancelled_reason)
        completed = (returncode == 0 and len(files_modified) > 0 and not cancelled)
        final_status = "canceled" if cancelled else ("success" if returncode == 0 else "error")
        if cancelled and not error_text:
            error_text = cancelled_reason

        logger.info("aider_task_complete", task_id=task_id, exit_code=returncode,
                    files_modified=len(files_modified), duration=duration, completed=completed)

        # Phase 19.3.4 — record hint adoption outcome.
        # Consider a hint successful when task execution succeeds, even if no
        # file mutation was required (for example, analysis-only or no-op fixes).
        hint_accepted = final_status == "success"
        if hint_injected:
            _write_hint_audit(task_id, hint_id, hint_snippet, accepted=hint_accepted)

        _set_terminal_task(
            task_id,
            status=final_status,
            output=output,
            error=error_text or "",
            files_modified=files_modified,
            git_commits=git_commits,
            duration_seconds=duration,
            exit_code=returncode,
            completed=completed,
        )


# ============================================================================
# Task Submission
# ============================================================================

async def _do_submit(task: TaskRequest) -> TaskSubmitResponse:
    task_id = str(uuid4())
    _tasks[task_id] = {
        "status": "queued",
        "submitted_at": _now_iso(),
        "request": task.model_dump(),
        "tooling": {
            "hints_enabled": AI_HINTS_ENABLED,
            "hint_injected": False,
            "hint_id": "",
            "tooling_plan_enabled": AI_TOOLING_PLAN_ENABLED,
            "tooling_plan_injected": False,
            "tooling_plan_phase_count": 0,
        },
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
    if "tooling" in entry:
        response["tooling"] = entry["tooling"]
    if "result" in entry:
        response["result"] = entry["result"]
    return response


@app.post("/tasks/{task_id}/stop")
@app.post("/tasks/{task_id}/cancel")
async def stop_task(task_id: str, auth: str = Depends(require_auth)):
    """Cancel a queued/waiting/running task with kill escalation."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    entry = _tasks[task_id]
    status = str(entry.get("status", "unknown"))
    if status in {"success", "error", "canceled"}:
        return {"task_id": task_id, "status": status, "message": "Task already terminal"}

    _task_cancel_reasons[task_id] = "canceled_by_user"
    proc = _task_processes.get(task_id)
    if proc is not None:
        await _terminate_process(task_id, proc, "canceled_by_user")
        entry["status"] = "canceling"
        return {"task_id": task_id, "status": "canceling", "message": "Cancellation requested"}

    # queued/waiting state: mark immediately terminal and skip execution
    _set_terminal_task(
        task_id,
        status="canceled",
        output="",
        error="canceled_by_user",
        files_modified=[],
        git_commits=[],
        duration_seconds=0.0,
        exit_code=130,
        completed=False,
    )
    _task_cancel_reasons.pop(task_id, None)
    return {"task_id": task_id, "status": "canceled", "message": "Task canceled"}


@app.get("/tasks/summary", response_model=TaskSummaryResponse)
async def get_task_summary(auth: str = Depends(require_auth)):
    """Return queue summary for dashboard polling."""
    active_states = {"queued", "waiting", "running"}
    terminal_states = {"success", "error", "canceled"}

    active_tasks = 0
    last_task_id: Optional[str] = None
    last_task_status = "none"
    last_finished_epoch = -1.0

    for task_id, entry in _tasks.items():
        status = str(entry.get("status", "unknown"))
        if status in active_states:
            active_tasks += 1
            continue
        if status not in terminal_states:
            continue

        finished_at_raw = entry.get("finished_at")
        finished_epoch = 0.0
        if isinstance(finished_at_raw, str):
            try:
                finished_epoch = datetime.fromisoformat(finished_at_raw).timestamp()
            except ValueError:
                finished_epoch = 0.0
        if finished_epoch >= last_finished_epoch:
            last_finished_epoch = finished_epoch
            last_task_id = task_id
            last_task_status = status

    return TaskSummaryResponse(
        active_tasks=active_tasks,
        last_task_status=last_task_status,
        last_task_id=last_task_id,
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("AIDER_WRAPPER_PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
