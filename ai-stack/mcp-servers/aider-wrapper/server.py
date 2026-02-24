#!/usr/bin/env python3
"""
Aider-Wrapper MCP Server v3.0
Now actually uses Aider for real file modification!
"""

import os
import sys
import json
import socket
import time
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

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

# Load API key from secret file
def load_api_key() -> Optional[str]:
    """Load API key from runtime secret file only."""
    secret_file = os.environ.get("AIDER_WRAPPER_API_KEY_FILE", "/run/secrets/aider_wrapper_api_key")
    if Path(secret_file).exists():
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return None

# Initialize authentication dependency
api_key = load_api_key()
require_auth = get_api_key_dependency(
    service_name="aider-wrapper",
    expected_key=api_key,
    optional=not api_key  # If no key configured, allow unauthenticated (dev mode)
)

app = FastAPI(
    title="Aider-Wrapper MCP Server v3",
    description="Real Aider integration for autonomous code modification",
    version="3.0.0"
)

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE = os.getenv("AIDER_WORKSPACE", "/workspace")
LLAMA_CPP_URL = f"http://{os.getenv('LLAMA_CPP_HOST', 'llama-cpp')}:{os.getenv('LLAMA_CPP_PORT', '8080')}"
MODEL_NAME = os.getenv("LLAMA_CPP_MODEL", "qwen2.5-coder-7b-instruct-q4_k_m.gguf")

# ============================================================================
# Request/Response Models
# ============================================================================

class TaskRequest(BaseModel):
    """Task request for Aider execution"""
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
    """Task execution response"""
    status: str
    output: str
    error: Optional[str] = None
    files_modified: List[str] = []
    git_commits: List[str] = []
    duration_seconds: float = 0.0
    exit_code: int = 0
    completed: bool = False


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    aider_available: bool
    workspace: str
    llama_cpp_url: str


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    # Check if Aider is available
    aider_available = False
    try:
        result = subprocess.run(["aider", "--version"], capture_output=True, text=True, timeout=5)
        aider_available = result.returncode == 0
    except:
        pass

    return {
        "status": "healthy" if aider_available else "degraded",
        "version": "3.0.0",
        "aider_available": aider_available,
        "workspace": WORKSPACE,
        "llama_cpp_url": LLAMA_CPP_URL
    }


# ============================================================================
# Main Execution Endpoint
# ============================================================================

@app.post("/execute", response_model=TaskResponse)
@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """
    Execute a code modification task using REAL Aider

    Aider will:
    - Modify files in place
    - Create git commits
    - Use proper context from the codebase
    """
    start_time = datetime.now()

    # Validate workspace
    workspace_path = Path(task.workspace)
    if not workspace_path.exists():
        raise HTTPException(status_code=400, detail=f"Workspace does not exist: {task.workspace}")

    logger.info("aider_task_start",
                prompt_length=len(task.prompt),
                files=task.files,
                iteration=task.iteration,
                workspace=task.workspace)

    try:
        # Build Aider command
        cmd = [
            "aider",
            "--yes",  # Auto-approve changes
            "--no-auto-commits",  # We'll handle commits ourselves
            "--model", f"openai/{MODEL_NAME}",  # Use our llama.cpp model
            "--openai-api-base", f"{LLAMA_CPP_URL}/v1",
            "--openai-api-key", "dummy",  # llama.cpp doesn't need real key
        ]

        # Add files to context
        if task.files:
            for file in task.files:
                file_path = workspace_path / file
                if file_path.exists():
                    cmd.extend(["--file", str(file_path)])
                else:
                    logger.warning("file_not_found", file=file)

        # Add the task prompt as a message
        cmd.extend(["--message", task.prompt])

        logger.info("executing_aider", command=" ".join(cmd[:10]))  # Log first 10 args

        # Execute Aider
        result = subprocess.run(
            cmd,
            cwd=task.workspace,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        duration = (datetime.now() - start_time).total_seconds()

        # Parse Aider output
        output = result.stdout
        error = result.stderr if result.returncode != 0 else None

        # Detect modified files from output
        files_modified = []
        for line in output.split('\n'):
            if "modified:" in line.lower() or "created:" in line.lower():
                # Extract filename
                parts = line.split()
                if len(parts) > 1:
                    files_modified.append(parts[-1])

        # Check git log for commits (if Aider made any)
        git_commits = []
        try:
            git_result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                cwd=task.workspace,
                capture_output=True,
                text=True,
                timeout=5
            )
            if git_result.returncode == 0:
                git_commits = [line.strip() for line in git_result.stdout.split('\n') if line.strip()][:3]
        except:
            pass

        # Determine completion status
        completed = result.returncode == 0 and len(files_modified) > 0

        logger.info("aider_task_complete",
                    exit_code=result.returncode,
                    files_modified=len(files_modified),
                    duration=duration,
                    completed=completed)

        return {
            "status": "success" if result.returncode == 0 else "error",
            "output": output,
            "error": error,
            "files_modified": files_modified,
            "git_commits": git_commits,
            "duration_seconds": duration,
            "exit_code": result.returncode,
            "completed": completed
        }

    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error("aider_timeout", duration=duration)
        return {
            "status": "error",
            "output": "",
            "error": "Aider execution timed out after 5 minutes",
            "files_modified": [],
            "git_commits": [],
            "duration_seconds": duration,
            "exit_code": 124,
            "completed": False
        }

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error("aider_exception", error=str(e), duration=duration)
        return {
            "status": "error",
            "output": "",
            "error": f"Exception: {str(e)}",
            "files_modified": [],
            "git_commits": [],
            "duration_seconds": duration,
            "exit_code": 1,
            "completed": False
        }


# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    logger.info("aider_wrapper_starting", version="3.0.0", workspace=WORKSPACE)

    # Validate Aider is installed
    try:
        result = subprocess.run(["aider", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("aider_found", version=result.stdout.strip())
        else:
            logger.error("aider_not_found", message="Aider binary not available!")
            logger.error("install_aider", message="Run: pip install aider-chat==0.16.0")
    except Exception as e:
        logger.error("aider_check_failed", error=str(e))

    port = int(os.getenv("AIDER_WRAPPER_PORT", "8099"))
    uvicorn.run(app, host="0.0.0.0", port=port)
