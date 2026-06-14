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

MEMORY_TYPES = ("episodic", "semantic", "procedural", "working", "error_solutions", "interaction_history")
MEMORY_TYPE_ALIASES = {
    "note": "semantic",
    "observation": "episodic",
    "context": "episodic",
    "event": "episodic",
    "milestone": "episodic",
    "decision": "procedural",
    "procedure": "procedural",
    "error": "error_solutions",
    "error_solution": "error_solutions",
    "interaction": "interaction_history",
}


def normalize_store_memory_type(context_type: str) -> str:
    """Map local-agent store_memory aliases onto coordinator memory tiers."""
    normalized = str(context_type or "").strip().lower()
    return MEMORY_TYPE_ALIASES.get(normalized, normalized or "semantic")


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
    context_type: str = "semantic",
    importance: float = 0.5,
    tags: Optional[list] = None,
) -> Dict:
    """
    Store information in context memory.

    Args:
        content: Content to store
        context_type: Memory tier. Canonical values are episodic, semantic,
            procedural, working, error_solutions, interaction_history. Legacy
            aliases like note, decision, observation, and milestone are accepted.
        importance: Importance score (0.0-1.0)
        tags: Optional tags

    Returns:
        {
            "success": bool,
            "context_id": str,
            "error": str (if failed)
        }
    """
    try:
        memory_type = normalize_store_memory_type(context_type)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/store",
                json={
                    "content": content,
                    "memory_type": memory_type,
                    "importance": importance,
                    "tags": tags or [],
                    "source": "local-agent",
                },
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


async def harness_health_handler(phase: str = "0") -> Dict:
    """Proxy for run_qa_check (harness_health)"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/qa/check", json={"phase": phase})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_prsi_pending_handler() -> Dict:
    """Proxy for get_prsi_pending"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/prsi/pending")
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def prsi_orchestrate_handler(action: str, action_id: Optional[str] = None, note: Optional[str] = None) -> Dict:
    """Proxy for prsi_orchestrate"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"action": action, "action_id": action_id, "note": note}
            # Note: The coordinator might use different endpoints for different actions
            if action == "execute":
                resp = await client.post(f"{HYBRID_COORDINATOR_URL}/control/prsi/actions/execute", json=payload)
            else:
                resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/prsi/actions", params=payload)
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def recommend_agent_for_task_handler(query: str) -> Dict:
    """Proxy for recommend_agent_for_task (federated)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/federated/recommend", json={"query": query})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def query_aidb_handler(query: str, limit: int = 5) -> Dict:
    """Proxy for hybrid_search (query_aidb)"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/search/tree", json={"query": query, "limit": limit})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_working_memory_handler() -> Dict:
    """Proxy for recall_agent_memory (get_working_memory)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/memory/recall", json={"query": "working memory summary", "memory_types": ["working"]})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def mesh_discovery_handler() -> Dict:
    """Get active agents, teams, and capabilities from the mesh."""
    try:
        from collective_memory import CollectiveMemory
        mem = CollectiveMemory()
        active_teams = mem.get_active_teams()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/discovery/capabilities")
            capabilities = resp.json() if resp.status_code == 200 else {}
            
        return {
            "success": True,
            "active_teams": active_teams,
            "team_count": len(active_teams),
            "capabilities": capabilities.get("capabilities", []),
            "redis_connected": mem.is_redis_connected(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def collective_memory_search_handler(query: str, limit: int = 5) -> Dict:
    """Search historical collaboration records in the collective memory (AIDB)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{AIDB_URL}/vector/search",
                json={
                    "query": query,
                    "collection": "knowledge",
                    "limit": limit,
                },
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
        description="Store information in agent memory using canonical memory tiers",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to store",
                },
                "context_type": {
                    "type": "string",
                    "description": (
                        "Memory tier. Use episodic for events/milestones, semantic for facts, "
                        "procedural for decisions/procedures, working for active scratch memory, "
                        "error_solutions for bug fixes, interaction_history for conversations."
                    ),
                    "enum": list(MEMORY_TYPES),
                    "default": "semantic",
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

    # harness_health
    registry.register(ToolDefinition(
        name="harness_health",
        description="Run AI stack health checks (qa_check)",
        parameters={
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "description": "QA phase to run (0-10)",
                    "default": "0",
                },
            },
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=harness_health_handler,
    ))

    # get_prsi_pending
    registry.register(ToolDefinition(
        name="get_prsi_pending",
        description="Get list of pending PRSI optimization actions",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_prsi_pending_handler,
    ))

    # prsi_orchestrate
    registry.register(ToolDefinition(
        name="prsi_orchestrate",
        description="Approve, reject, or execute PRSI actions",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["approve", "reject", "sync", "execute"],
                },
                "action_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["action"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.SYSTEM_MODIFY,
        handler=prsi_orchestrate_handler,
    ))

    # recommend_agent_for_task
    registry.register(ToolDefinition(
        name="recommend_agent_for_task",
        description="Get recommendation for the best agent to handle a task (agent mesh)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=recommend_agent_for_task_handler,
    ))

    # query_aidb
    registry.register(ToolDefinition(
        name="query_aidb",
        description="Search the AI stack knowledge base (hybrid_search)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=query_aidb_handler,
    ))

    # get_working_memory
    registry.register(ToolDefinition(
        name="get_working_memory",
        description="Retrieve recent session facts and decisions",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_working_memory_handler,
    ))

    # mesh_discovery
    registry.register(ToolDefinition(
        name="mesh_discovery",
        description="Discover active agents, teams, and capabilities in the mesh",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=mesh_discovery_handler,
    ))

    # collective_memory_search
    registry.register(ToolDefinition(
        name="collective_memory_search",
        description="Search past agent collaborations and lessons learned",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=collective_memory_search_handler,
    ))

    logger.info("Registered 14 AI coordination tools")
