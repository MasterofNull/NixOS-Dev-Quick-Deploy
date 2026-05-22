#!/usr/bin/env python3
"""
Built-in AI Coordination Tools for Local Agents

Provides tools for local agents to interact with the AI stack:
- get_hint: Query hints engine
- delegate_to_remote: Send task to remote agent
- query_context: Query context memory
- store_memory: Store in context memory

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import json
import logging
from typing import Dict, Optional

import httpx

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# Service endpoints
HYBRID_COORDINATOR_URL = "http://127.0.0.1:8003"
AIDB_URL = "http://127.0.0.1:8002"


async def get_hint_handler(
    query: str,
    max_hints: int = 5,
) -> Dict:
    """
    Query the hints engine for relevant hints.

    Args:
        query: Query string
        max_hints: Maximum hints to return

    Returns:
        {
            "success": bool,
            "hints": [str],
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HYBRID_COORDINATOR_URL}/hints",
                params={"q": query, "max": max_hints},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "hints": data.get("hints", []),
                    "count": len(data.get("hints", [])),
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to query hints: {e}",
        }


async def delegate_to_remote_handler(
    task: str,
    agent_type: str = "codex",
    priority: str = "normal",
) -> Dict:
    """
    Delegate a task to a remote agent.

    Args:
        task: Task description
        agent_type: Agent type (codex, claude, qwen)
        priority: Task priority (low, normal, high)

    Returns:
        {
            "success": bool,
            "task_id": str,
            "agent": str,
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HYBRID_COORDINATOR_URL}/query",
                json={
                    "query": task,
                    "agent_type": agent_type,
                    "context": {"priority": priority},
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "agent": agent_type,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delegate task: {e}",
        }


async def query_context_handler(
    query: str,
    max_results: int = 10,
) -> Dict:
    """
    Query context memory for relevant information.

    Args:
        query: Query string
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "contexts": [{"content": str, "importance": float}],
            "error": str (if failed)
        }
    """
    # Placeholder - will integrate with context memory when implemented
    return {
        "success": False,
        "error": "Context memory integration not yet implemented",
    }


async def store_memory_handler(
    content: str,
    context_type: str = "note",
    importance: float = 0.5,
    tags: Optional[list] = None,
) -> Dict:
    """
    Store information in context memory.

    Args:
        content: Content to store
        context_type: Type of context (note, decision, observation)
        importance: Importance score (0.0-1.0)
        tags: Optional tags

    Returns:
        {
            "success": bool,
            "context_id": str,
            "error": str (if failed)
        }
    """
    # Placeholder - will integrate with context memory when implemented
    return {
        "success": False,
        "error": "Context memory integration not yet implemented",
    }


async def get_workflow_status_handler(workflow_id: str) -> Dict:
    """
    Get status of a running workflow.

    Args:
        workflow_id: Workflow ID

    Returns:
        {
            "success": bool,
            "status": str,
            "progress": float,
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HYBRID_COORDINATOR_URL}/workflow/status/{workflow_id}",
                timeout=5.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "progress": data.get("progress", 0.0),
                    "workflow_id": workflow_id,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get workflow status: {e}",
        }


async def run_opencode_handler(
    prompt: str,
    model: Optional[str] = None,
) -> Dict:
    """
    Invoke the opencode CLI coding agent with the given prompt.

    The model is resolved from the SWB_REMOTE_MODEL_ALIAS_OPENCODE env var
    when not explicitly provided, falling back to the configured remote-free
    alias so free capacity is used by default.

    Args:
        prompt: Coding task description passed to opencode
        model:  Override model id (OpenRouter format, e.g. qwen/qwen3-235b-a22b:free)

    Returns:
        {
            "success": bool,
            "output": str,
            "model": str,
            "error": str (if failed)
        }
    """
    import asyncio
    import shutil

    opencode_bin = shutil.which("opencode")
    if not opencode_bin:
        return {"success": False, "error": "opencode not found in PATH"}

    resolved_model = (
        model
        or os.getenv("SWB_REMOTE_MODEL_ALIAS_OPENCODE")
        or os.getenv("SWB_REMOTE_MODEL_ALIAS_FREE")
        or ""
    )

    cmd = [opencode_bin, "run", "--print", prompt]
    env = {**os.environ}
    if resolved_model:
        env["OPENCODE_MODEL"] = resolved_model

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        if proc.returncode == 0:
            return {
                "success": True,
                "output": stdout.decode().strip(),
                "model": resolved_model,
            }
        return {
            "success": False,
            "error": stderr.decode().strip() or f"exit code {proc.returncode}",
            "model": resolved_model,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": "opencode timed out after 120s", "model": resolved_model}
    except Exception as e:
        return {"success": False, "error": str(e), "model": resolved_model}


def register_ai_coordination_tools(registry: ToolRegistry):
    """Register all AI coordination tools in the registry"""

    # get_hint
    registry.register(ToolDefinition(
        name="get_hint",
        description="Query the hints engine for relevant hints and guidance",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query string",
                },
                "max_hints": {
                    "type": "integer",
                    "description": "Maximum hints to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_hint_handler,
    ))

    # delegate_to_remote
    registry.register(ToolDefinition(
        name="delegate_to_remote",
        description="Delegate a task to a remote agent (codex, claude, qwen)",
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Agent type",
                    "enum": ["codex", "claude", "qwen", "opencode"],
                    "default": "codex",
                },
                "priority": {
                    "type": "string",
                    "description": "Task priority",
                    "enum": ["low", "normal", "high"],
                    "default": "normal",
                },
            },
            "required": ["task"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=delegate_to_remote_handler,
    ))

    # query_context
    registry.register(ToolDefinition(
        name="query_context",
        description="Query context memory for relevant information",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=query_context_handler,
    ))

    # store_memory
    registry.register(ToolDefinition(
        name="store_memory",
        description="Store information in context memory",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to store",
                },
                "context_type": {
                    "type": "string",
                    "description": "Type of context",
                    "enum": ["note", "decision", "observation"],
                    "default": "note",
                },
                "importance": {
                    "type": "number",
                    "description": "Importance score (0.0-1.0)",
                    "default": 0.5,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags",
                },
            },
            "required": ["content"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=store_memory_handler,
    ))

    # get_workflow_status
    registry.register(ToolDefinition(
        name="get_workflow_status",
        description="Get status of a running workflow",
        parameters={
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID",
                },
            },
            "required": ["workflow_id"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_workflow_status_handler,
    ))

    # run_opencode
    registry.register(ToolDefinition(
        name="run_opencode",
        description=(
            "Invoke the opencode CLI coding agent for file-editing, refactoring, or "
            "code-generation tasks. Routes through the free remote model lane by default "
            "(SWB_REMOTE_MODEL_ALIAS_OPENCODE). Use for concrete implementation work to "
            "preserve paid-tier budget."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Coding task description",
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Override model id in OpenRouter format "
                        "(e.g. qwen/qwen3-235b-a22b:free). "
                        "Defaults to SWB_REMOTE_MODEL_ALIAS_OPENCODE env var."
                    ),
                },
            },
            "required": ["prompt"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        sandbox_profile="execute-guarded",
        network_policy="loopback",
        timeout_seconds=120,
        handler=run_opencode_handler,
    ))

    logger.info("Registered 6 AI coordination tools")
