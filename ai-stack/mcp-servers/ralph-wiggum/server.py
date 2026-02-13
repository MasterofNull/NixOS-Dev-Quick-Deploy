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
import socket
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from pathlib import Path

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from loop_engine import RalphLoopEngine
try:
    from orchestrator import AgentOrchestrator  # legacy name
except ImportError:
    from orchestrator import RalphOrchestrator as AgentOrchestrator
from state_manager import StateManager
from hooks import StopHook, ContextRecoveryHook, ResourceLimitHook

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.auth_middleware import get_api_key_dependency
from shared.hybrid_client import HybridClient, AIDBClient

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

# ============================================================================
# Prometheus Metrics
# ============================================================================

RALPH_TASKS_TOTAL = Counter(
    "ralph_tasks_total",
    "Total number of tasks submitted",
    ["backend", "status"]
)

RALPH_ACTIVE_TASKS = Gauge(
    "ralph_active_tasks",
    "Number of currently active tasks"
)

RALPH_ITERATIONS_TOTAL = Counter(
    "ralph_iterations_total",
    "Total number of loop iterations",
    ["backend"]
)

RALPH_TASK_DURATION_SECONDS = Histogram(
    "ralph_task_duration_seconds",
    "Task completion time in seconds",
    ["backend"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

RALPH_PROCESS_MEMORY_BYTES = Gauge(
    "ralph_process_memory_bytes",
    "Process memory usage in bytes"
)

RALPH_LOOP_ENABLED = Gauge(
    "ralph_loop_enabled",
    "Whether the Ralph loop is enabled (1=enabled, 0=disabled)"
)

# ============================================================================
# Pre-Flight Dependency Validation
# ============================================================================

REQUIRED_DEPENDENCIES: Dict[str, Tuple[str, int]] = {
    "aider-wrapper": (os.getenv("AIDER_WRAPPER_HOST", "aider-wrapper"), int(os.getenv("AIDER_WRAPPER_PORT", "8099"))),
}

def validate_dependencies():
    """Check all required services are reachable before starting"""
    if not os.getenv("STARTUP_DEPENDENCY_CHECK", "true").lower() == "true":
        logger.info("pre_flight_checks_disabled")
        return

    timeout = int(os.getenv("STARTUP_TIMEOUT_SECONDS", "30"))
    start_time = time.time()

    logger.info("pre_flight_checks_start", service="ralph-wiggum")

    for name, (host, port) in REQUIRED_DEPENDENCIES.items():
        logger.info("checking_dependency", dependency=name, host=host, port=port)

        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.info("dependency_ok", dependency=name, host=host, port=port)
                    break
            except Exception as e:
                logger.debug("connection_attempt_failed", error=str(e))

            elapsed = int(time.time() - start_time)
            logger.info("waiting_for_dependency", dependency=name, elapsed=elapsed, timeout=timeout)
            time.sleep(2)
        else:
            # Timeout reached
            if os.getenv("STARTUP_FAIL_FAST", "false").lower() == "true":
                logger.critical("dependency_missing", dependency=name, host=host, port=port)
                sys.exit(1)
            else:
                logger.warning("dependency_not_reachable", dependency=name, host=host, port=port)

    logger.info("pre_flight_checks_complete")

# Configuration from environment
CONFIG = {
    "port": int(os.getenv("RALPH_MCP_SERVER_PORT", "8098")),
    "loop_enabled": os.getenv("RALPH_LOOP_ENABLED", "true").lower() == "true",
    "exit_code_block": int(os.getenv("RALPH_EXIT_CODE_BLOCK", "2")),
    # NEW: Adaptive iteration limits from .env
    "max_iterations": int(os.getenv("RALPH_MAX_ITERATIONS_DEFAULT", "20")),
    "max_iterations_simple": int(os.getenv("RALPH_MAX_ITERATIONS_SIMPLE", "10")),
    "max_iterations_complex": int(os.getenv("RALPH_MAX_ITERATIONS_COMPLEX", "50")),
    "adaptive_iterations": os.getenv("RALPH_ADAPTIVE_ITERATIONS", "true").lower() == "true",
    # Per-task timeout in seconds (Phase 13.2.3); 0 = no timeout
    "task_timeout_seconds": int(os.getenv("RALPH_TASK_TIMEOUT_SECONDS", "3600")),
    # How often (in iterations) to persist state during task execution (Phase 13.2.5)
    "state_save_interval": int(os.getenv("RALPH_STATE_SAVE_INTERVAL", "5")),
    "max_cpu_percent": float(os.getenv("RALPH_MAX_CPU_PERCENT", "85.0")),
    # Existing config
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
    hybrid_url = os.getenv("RALPH_COORDINATOR_URL", "http://hybrid-coordinator:8092")
    aidb_url = os.getenv("RALPH_AIDB_URL", "http://aidb:8091")
    hybrid_client = HybridClient(base_url=hybrid_url)
    aidb_client = AIDBClient(base_url=aidb_url)
    orchestrator = AgentOrchestrator(
        hybrid_client=hybrid_client,
        aidb_client=aidb_client,
        learning_client=None
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
        resource_hook = ResourceLimitHook(
            max_iterations_per_task=CONFIG["max_iterations"],
            max_cpu_percent=CONFIG["max_cpu_percent"],
        )

        loop_engine.add_hook("stop", stop_hook)
        loop_engine.add_hook("iteration", resource_hook)
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


# Load API key from secret file
def load_api_key() -> Optional[str]:
    """Load API key from Docker secret file"""
    secret_file = os.environ.get("RALPH_WIGGUM_API_KEY_FILE", "/run/secrets/ralph_wiggum_api_key")
    if Path(secret_file).exists():
        return Path(secret_file).read_text().strip()
    # Fallback to environment variable for development
    return os.environ.get("RALPH_WIGGUM_API_KEY")

# Initialize authentication dependency
api_key = load_api_key()
require_auth = get_api_key_dependency(
    service_name="ralph-wiggum",
    expected_key=api_key,
    optional=not api_key  # If no key configured, allow unauthenticated (dev mode)
)

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
async def create_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """
    Create a new Ralph loop task

    The task will continuously iterate until completion criteria are met.
    """
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    if not CONFIG["loop_enabled"]:
        raise HTTPException(status_code=503, detail="Ralph loop is disabled")

    try:
        backend_name = task.backend or CONFIG["default_backend"]
        task_id = await loop_engine.submit_task(
            prompt=task.prompt,
            backend=backend_name,
            max_iterations=task.max_iterations or CONFIG["max_iterations"],
            require_approval=task.require_approval if task.require_approval is not None else CONFIG["require_approval"],
            context=task.context
        )

        # Update Prometheus metrics
        RALPH_TASKS_TOTAL.labels(backend=backend_name, status="queued").inc()
        RALPH_ACTIVE_TASKS.inc()

        logger.info("task_created", task_id=task_id, backend=backend_name)

        return TaskResponse(
            task_id=task_id,
            status="queued",
            message=f"Task {task_id} queued for Ralph loop processing"
        )

    except Exception as e:
        RALPH_TASKS_TOTAL.labels(backend=task.backend or CONFIG["default_backend"], status="failed").inc()
        logger.error("task_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str, auth: str = Depends(require_auth)):
    """Get status of a Ralph loop task"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    status = await loop_engine.get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatus(**status)


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str, auth: str = Depends(require_auth)):
    """
    Get full result of a task (Phase 13.2.6).

    Returns iteration history, final output, and completion details.
    Works for in-progress, completed, and failed tasks.
    Also returns results from persisted state for tasks from previous runs.
    """
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    result = await loop_engine.get_task_result(task_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return result


@app.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, auth: str = Depends(require_auth)):
    """Stop a running Ralph loop task"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    success = await loop_engine.stop_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found or already stopped")

    return {"task_id": task_id, "status": "stopped"}


@app.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, approved: bool = True, auth: str = Depends(require_auth)):
    """Approve or reject a task waiting for human approval"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    success = await loop_engine.approve_task(task_id, approved)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found or not awaiting approval")

    return {"task_id": task_id, "approved": approved}


@app.get("/stats")
async def get_stats(auth: str = Depends(require_auth)):
    """Get Ralph loop statistics"""
    if not loop_engine:
        raise HTTPException(status_code=503, detail="Loop engine not initialized")

    return await loop_engine.get_stats()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    import resource
    # Update process memory metric
    usage = resource.getrusage(resource.RUSAGE_SELF)
    RALPH_PROCESS_MEMORY_BYTES.set(usage.ru_maxrss * 1024)  # Convert KB to bytes

    # Update loop enabled metric
    RALPH_LOOP_ENABLED.set(1 if CONFIG["loop_enabled"] else 0)

    # Update active tasks gauge
    if loop_engine:
        RALPH_ACTIVE_TASKS.set(loop_engine.active_task_count)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


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

    # Run pre-flight dependency checks
    validate_dependencies()

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
