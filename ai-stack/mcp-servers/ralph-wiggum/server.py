#!/usr/bin/env python3
"""
Ralph Wiggum Loop MCP Server
Continuous self-referential AI orchestration for autonomous development

Based on the Ralph Wiggum technique:
- Named after Ralph Wiggum from The Simpsons
- Implements while-true loop for iterative AI development
- Uses exit code 2 to block and re-inject prompts
- Enables context recovery through git and state files
- Provides human-in-the-loop controls

Version: 1.0.0 (December 2025)
"""

import asyncio
import os
import sys
import signal
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from loop_engine import RalphLoopEngine
from orchestrator import AgentOrchestrator
from state_manager import StateManager
from hooks import StopHook, ContextRecoveryHook

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configuration from environment
CONFIG = {
    "port": int(os.getenv("RALPH_MCP_SERVER_PORT", "8098")),
    "loop_enabled": os.getenv("RALPH_LOOP_ENABLED", "true").lower() == "true",
    "exit_code_block": int(os.getenv("RALPH_EXIT_CODE_BLOCK", "2")),
    "max_iterations": int(os.getenv("RALPH_MAX_ITERATIONS", "0")),
    "context_recovery": os.getenv("RALPH_CONTEXT_RECOVERY", "true").lower() == "true",
    "git_integration": os.getenv("RALPH_GIT_INTEGRATION", "true").lower() == "true",
    "state_file": os.getenv("RALPH_STATE_FILE", "/data/ralph-state.json"),
    "telemetry_path": os.getenv("RALPH_TELEMETRY_PATH", "/data/telemetry/ralph-events.jsonl"),
    "require_approval": os.getenv("RALPH_REQUIRE_APPROVAL", "false").lower() == "true",
    "approval_threshold": os.getenv("RALPH_APPROVAL_THRESHOLD", "high"),
    "audit_log": os.getenv("RALPH_AUDIT_LOG", "true").lower() == "true",
    "agent_backends": os.getenv("RALPH_AGENT_BACKENDS", "aider,continue-server,goose,autogpt,langchain").split(","),
    "default_backend": os.getenv("RALPH_DEFAULT_BACKEND", "aider"),
}

# Global instances
loop_engine: Optional[RalphLoopEngine] = None
orchestrator: Optional[AgentOrchestrator] = None
state_manager: Optional[StateManager] = None


# Request/Response models
class TaskRequest(BaseModel):
    """Request to start a Ralph loop task"""
    prompt: str = Field(..., description="Task prompt to iterate on")
    backend: Optional[str] = Field(None, description="Agent backend to use")
    max_iterations: Optional[int] = Field(None, description="Max iterations (0=infinite)")
    require_approval: Optional[bool] = Field(None, description="Require human approval")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class TaskResponse(BaseModel):
    """Response from task submission"""
    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    """Status of a running task"""
    task_id: str
    status: str
    iteration: int
    backend: str
    started_at: str
    last_update: str
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    loop_enabled: bool
    active_tasks: int
    backends: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the application"""
    global loop_engine, orchestrator, state_manager

    logger.info("ralph_startup", config=CONFIG)

    # Initialize components
    state_manager = StateManager(CONFIG["state_file"])
    orchestrator = AgentOrchestrator(
        backends=CONFIG["agent_backends"],
        default_backend=CONFIG["default_backend"]
    )

    loop_engine = RalphLoopEngine(
        orchestrator=orchestrator,
        state_manager=state_manager,
        config=CONFIG
    )

    # Setup hooks
    if CONFIG["loop_enabled"]:
        stop_hook = StopHook(loop_engine, CONFIG["exit_code_block"])
        recovery_hook = ContextRecoveryHook(state_manager, CONFIG["git_integration"])

        loop_engine.add_hook("stop", stop_hook)
        if CONFIG["context_recovery"]:
            loop_engine.add_hook("recovery", recovery_hook)

    # Start background loop processor
    loop_task = asyncio.create_task(loop_engine.run())

    logger.info("ralph_ready", port=CONFIG["port"])

    yield

    # Shutdown
    logger.info("ralph_shutdown")
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    await loop_engine.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Ralph Wiggum Loop MCP Server",
    description="Continuous autonomous agent orchestration",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if loop_engine and loop_engine.is_running else "degraded",
        version="1.0.0",
        loop_enabled=CONFIG["loop_enabled"],
        active_tasks=loop_engine.active_task_count if loop_engine else 0,
        backends=CONFIG["agent_backends"]
    )


@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskRequest):
    """
    Create a new Ralph loop task

    The task will continuously iterate until completion criteria are met.
    """
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    if not CONFIG["loop_enabled"]:
        raise HTTPException(status_code=503, detail="Ralph loop is disabled")

    try:
        task_id = await loop_engine.submit_task(
            prompt=task.prompt,
            backend=task.backend or CONFIG["default_backend"],
            max_iterations=task.max_iterations or CONFIG["max_iterations"],
            require_approval=task.require_approval if task.require_approval is not None else CONFIG["require_approval"],
            context=task.context
        )

        logger.info("task_created", task_id=task_id, backend=task.backend or CONFIG["default_backend"])

        return TaskResponse(
            task_id=task_id,
            status="queued",
            message=f"Task {task_id} queued for Ralph loop processing"
        )

    except Exception as e:
        logger.error("task_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get status of a Ralph loop task"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    status = await loop_engine.get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatus(**status)


@app.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running Ralph loop task"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    success = await loop_engine.stop_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found or already stopped")

    return {"task_id": task_id, "status": "stopped"}


@app.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, approved: bool = True):
    """Approve or reject a task waiting for human approval"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    success = await loop_engine.approve_task(task_id, approved)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found or not awaiting approval")

    return {"task_id": task_id, "approved": approved}


@app.get("/stats")
async def get_stats():
    """Get Ralph loop statistics"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    return await loop_engine.get_stats()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("signal_received", signal=signum)
    sys.exit(0)


def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("ralph_starting", config=CONFIG)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=CONFIG["port"],
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
