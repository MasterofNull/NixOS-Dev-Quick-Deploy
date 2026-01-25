#!/usr/bin/env python3
"""
Code Generation HTTP Wrapper
Provides HTTP API for code generation using llama.cpp directly
Bypasses Aider/LiteLLM to avoid compatibility issues
"""

import os
import sys
import json
import socket
import time
import logging
import requests
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Code Generation Wrapper", version="2.0.0")

# ============================================================================
# Pre-Flight Dependency Validation
# ============================================================================

REQUIRED_DEPENDENCIES: Dict[str, Tuple[str, int]] = {
    "llama-cpp": (os.getenv("LLAMA_CPP_HOST", "llama-cpp"), int(os.getenv("LLAMA_CPP_PORT", "8080"))),
}

def validate_dependencies():
    """Check all required services are reachable before starting"""
    if not os.getenv("STARTUP_DEPENDENCY_CHECK", "true").lower() == "true":
        logger.info("Pre-flight dependency checks DISABLED")
        return

    timeout = int(os.getenv("STARTUP_TIMEOUT_SECONDS", "30"))
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("AIDER-WRAPPER PRE-FLIGHT DEPENDENCY CHECKS")
    logger.info("=" * 60)

    for name, (host, port) in REQUIRED_DEPENDENCIES.items():
        logger.info(f"Checking dependency: {name} at {host}:{port}")

        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.info(f"✓ {name} is reachable at {host}:{port}")
                    break
            except Exception as e:
                logger.debug(f"Connection attempt failed: {e}")

            logger.info(f"  Waiting for {name}... ({int(time.time() - start_time)}s/{timeout}s)")
            time.sleep(2)
        else:
            # Timeout reached
            if os.getenv("STARTUP_FAIL_FAST", "false").lower() == "true":
                logger.critical(f"✗ DEPENDENCY MISSING: {name} at {host}:{port}")
                logger.critical(f"Cannot start without {name}. Exiting.")
                sys.exit(1)
            else:
                logger.warning(f"⚠ {name} not reachable at {host}:{port} - continuing anyway")

    logger.info("=" * 60)
    logger.info("Pre-flight checks complete")
    logger.info("=" * 60)


class TaskRequest(BaseModel):
    """Task request for Aider execution"""
    prompt: str = Field(..., description="Task description for Aider")
    files: List[str] = Field(default_factory=list, description="Files to include in context")
    model: str = Field(default="gpt-4o", description="Model to use")
    max_tokens: int = Field(default=4000, description="Max tokens")
    workspace: str = Field(default="/workspace", description="Working directory")
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
    duration_seconds: float


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    aider_available: bool
    workspace: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    # Check if llama.cpp is available
    aider_available = False
    try:
        response = requests.get("http://llama-cpp:8080/v1/models", timeout=5)
        aider_available = response.status_code == 200
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        version="2.0.0",
        aider_available=aider_available,  # Now represents llama.cpp availability
        workspace="/workspace"
    )


@app.post("/execute", response_model=TaskResponse)
@app.post("/api/execute", response_model=TaskResponse)  # Also support /api/execute for Ralph compatibility
async def execute_task(task: TaskRequest):
    """
    Execute a code generation task using llama.cpp directly

    Bypasses Aider/LiteLLM to avoid compatibility issues
    """
    start_time = datetime.now()

    # Validate workspace exists
    workspace_path = Path(task.workspace)
    if not workspace_path.exists():
        raise HTTPException(status_code=400, detail=f"Workspace does not exist: {task.workspace}")

    # Build prompt for code generation
    system_prompt = """You are a code generation assistant. Generate complete, working code based on the user's request.

CRITICAL: You must respond ONLY with code in a code block. Do not include any explanations, filenames, or other text.
Just output the raw code that should go in the file.

Example:
If asked to create a hello world Python script, respond ONLY with:
```python
def main():
    print("Hello World")

if __name__ == "__main__":
    main()
```
"""

    # Extract filename from prompt if present, otherwise use a default
    filename = "output.txt"
    if ".py" in task.prompt.lower():
        filename = "generated_code.py"
        if "hello" in task.prompt.lower():
            filename = "hello.py"
    elif ".js" in task.prompt.lower():
        filename = "generated_code.js"

    user_prompt = task.prompt

    try:
        # Call llama.cpp completion API directly
        response = requests.post(
            "http://llama-cpp:8080/v1/chat/completions",
            json={
                "model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
                "stream": False
            },
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        duration = (datetime.now() - start_time).total_seconds()

        if response.status_code != 200:
            return {
                "status": "error",
                "output": "",
                "error": f"llama.cpp API error: {response.status_code} - {response.text}",
                "files_modified": [],
                "duration_seconds": duration,
                "exit_code": 1,
                "completed": False
            }

        # Parse llama.cpp response
        llm_response = response.json()
        generated_text = llm_response['choices'][0]['message']['content']

        # Parse code from markdown code blocks
        code_content = generated_text
        if "```" in generated_text:
            # Extract code from markdown code blocks
            lines = generated_text.split('\n')
            code_lines = []
            in_code_block = False

            for line in lines:
                if line.startswith('```'):
                    if in_code_block:
                        # End of code block
                        break
                    else:
                        # Start of code block
                        in_code_block = True
                        continue
                elif in_code_block:
                    code_lines.append(line)

            if code_lines:
                code_content = '\n'.join(code_lines)

        # Save the generated code
        file_path = workspace_path / filename
        file_path.write_text(code_content)

        files_modified = [filename]
        output = f"""Code generation completed in {duration:.2f}s

Generated file: {filename}
File size: {len(code_content)} bytes

Preview (first 500 chars):
{code_content[:500]}
"""

        return {
            "status": "success",
            "output": output,
            "error": None,
            "files_modified": files_modified,
            "duration_seconds": duration,
            # Ralph compatibility fields
            "exit_code": 0,
            "completed": True,
            "git_commits": [],
            "commits": []
        }

    except requests.Timeout:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "status": "error",
            "output": "",
            "error": "LLM request timed out after 2 minutes",
            "files_modified": [],
            "duration_seconds": duration,
            "exit_code": 1,
            "completed": False
        }
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "status": "error",
            "output": "",
            "error": f"Error: {str(e)}",
            "files_modified": [],
            "duration_seconds": duration,
            "exit_code": 1,
            "completed": False
        }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Aider HTTP Wrapper",
        "version": "1.0.0",
        "endpoints": [
            "/health - Health check",
            "/execute - Execute Aider task",
            "/docs - API documentation"
        ]
    }


if __name__ == "__main__":
    # Run pre-flight dependency checks
    validate_dependencies()

    port = int(os.getenv("AIDER_WRAPPER_PORT", "8099"))
    logger.info(f"Starting Aider Wrapper on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
