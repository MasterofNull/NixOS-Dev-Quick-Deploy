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
import os
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
    # "working" is a conceptual scratch-pad alias for "semantic".
    # The coordinator has no separate working tier — scratch notes live in
    # semantic memory, distinguished by a "working_memory" tag on each entry.
    "working": "semantic",
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
    Delegate a task to a remote agent via the coordinator delegate lane.

    Args:
        task: Task description
        agent_type: Agent type (codex, claude, gemini)
        priority: Task priority (low, normal, high)

    Returns:
        {
            "success": bool,
            "response": str,
            "agent": str,
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{HYBRID_COORDINATOR_URL}/control/ai-coordinator/delegate",
                json={
                    "task": task,
                    "agent": agent_type,
                    "priority": priority,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", data.get("result", "")),
                    "task_id": data.get("task_id", ""),
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
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/recall",
                json={
                    "query": query,
                    "memory_types": ["episodic", "semantic"],
                    "limit": max_results,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                return {
                    "success": True,
                    "contexts": [
                        {"content": r.get("content", ""), "importance": r.get("score", 0.5)}
                        for r in results
                    ],
                    "count": len(results),
                }
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
                f"{HYBRID_COORDINATOR_URL}/workflow/orchestrate/{workflow_id}",
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
    """
    Recommend an agent role for the given task query.

    Uses GET /control/agents/roles for the role catalogue, then scores locally
    via keyword matching — no /federated/recommend route exists in coordinator.
    """
    _ROLE_KEYWORDS: dict = {
        "coordinator": ["orchestrate", "plan", "delegate", "coordinate", "workflow", "multi"],
        "coder": ["code", "implement", "write", "fix", "debug", "refactor", "patch", "function", "class"],
        "reviewer": ["review", "audit", "check", "evaluate", "assess", "verify", "feedback"],
        "researcher": ["research", "find", "search", "gather", "context", "information", "lookup"],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/agents/roles")
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            roles = resp.json().get("roles", [])

        q_lower = query.lower()
        best_role = "agent"
        best_score = 0
        for role_entry in roles:
            role = role_entry.get("role", "")
            keywords = _ROLE_KEYWORDS.get(role, [])
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > best_score:
                best_score = score
                best_role = role

        return {
            "success": True,
            "recommended_agent": best_role,
            "query": query,
            "available_roles": [r.get("role") for r in roles],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _query_qdrant_direct(query: str, collection: str, limit: int) -> Dict:
    """Embed query via llama-embed (8081) then search Qdrant directly (6333).
    Primary path for harness-seeded collections (error-solutions, skills-patterns, etc.).
    Normalises response to the shape expected by agent tool callers."""
    embed_url = os.environ.get("AI_STACK_EMBED_ENDPOINT", "http://127.0.0.1:8081")
    qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    # Port 6333 is Qdrant (seed target). Port 8002 is AIDB pgvector (separate store).
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            er = await client.post(f"{embed_url}/v1/embeddings",
                                   json={"model": "bge-m3", "input": query})
            if er.status_code != 200:
                return {"success": False, "error": f"embed failed {er.status_code}: {er.text[:200]}"}
            vector = er.json()["data"][0]["embedding"]
            sr = await client.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True},
            )
            if sr.status_code != 200:
                return {"success": False, "error": f"qdrant {sr.status_code}: {sr.text[:200]}"}
            hits = sr.json().get("result", [])
            # Deduplicate by title — same pattern seeded across multiple runs
            # produces identical Qdrant points. Keep highest-scored entry per title.
            seen_titles: set = set()
            deduped = []
            for h in hits:
                p = h.get("payload") or {}
                title = p.get("error_type") or p.get("title") or p.get("skill_name", "")
                if title and title in seen_titles:
                    continue
                seen_titles.add(title)
                deduped.append({
                    "title": title,
                    "content": p.get("solution") or p.get("description", ""),
                    "score": h.get("score", 0.0),
                    "source": f"qdrant:{collection}",
                    "payload": p,
                })
            return {
                "success": True,
                "results": deduped,
                "count": len(deduped),
                "fallback": "qdrant-direct",
            }
    except Exception as e:
        return {"success": False, "error": f"qdrant-direct: {e}"}


# Collections seeded directly to Qdrant (port 6333) by seed-rag-knowledge.py and training pipeline.
# These are separate from AIDB's pgvector store (port 8002) which holds document chunks.
# Phase 175: AIDB pgvector returns wrong content for these names (MCP registry entries, not
# harness patterns) — always go direct to Qdrant for harness pattern collections.
_QDRANT_COLLECTIONS: frozenset = frozenset({
    "error-solutions", "skills-patterns", "best-practices", "codebase-context",
    "knowledge", "interaction-history", "agent-memory-episodic", "agent-memory-semantic",
    "agent-memory-procedural", "learning-feedback", "trading-patterns", "mlops-patterns",
    "qa-patterns", "osint-intelligence",
})


async def query_aidb_handler(query: str, collection: str = "error-solutions", limit: int = 5) -> Dict:
    """Search harness pattern collections. Default 'error-solutions' has 66 seeded fix patterns.

    Routes to Qdrant-direct (embed via llama-embed:8081 + search Qdrant:6333) for all
    harness-seeded collections. AIDB pgvector (port 8002) is a separate document store
    with different content — not used for harness pattern queries.
    """
    if collection in _QDRANT_COLLECTIONS:
        return await _query_qdrant_direct(query, collection, limit)
    # Non-harness collections: try AIDB pgvector
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{AIDB_URL}/vector/search",
                json={"query": query, "collection": collection, "limit": limit},
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_working_memory_handler() -> Dict:
    """Proxy for recall_agent_memory (get_working_memory)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/memory/recall", json={"query": "working memory summary", "memory_types": ["semantic"]})
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


async def get_unified_stack_health_handler() -> Dict:
    """Get a comprehensive health snapshot of the local AI stack."""
    try:
        api_key_path = "/run/secrets/hybrid_coordinator_api_key"
        api_key = ""
        if os.path.exists(api_key_path):
            with open(api_key_path, "r") as f:
                api_key = f.read().strip()

        headers = {"X-API-Key": api_key} if api_key else {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Parallel fetch for optimal performance
            status_task = client.get(f"{HYBRID_COORDINATOR_URL}/status", headers=headers)
            rate_limit_task = client.get(f"{HYBRID_COORDINATOR_URL}/admin/v1/policy/rate-limit-stats", headers=headers)
            hardware_task = client.get(f"{HYBRID_COORDINATOR_URL}/api/hardware/state", headers=headers)

            resps = await asyncio.gather(status_task, rate_limit_task, hardware_task, return_exceptions=True)

            results = []
            for r in resps:
                if isinstance(r, httpx.Response):
                    results.append(r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"})
                else:
                    results.append({"error": str(r)})

            return {
                "success": True,
                "status": results[0],
                "rate_limiting": results[1],
                "hardware": results[2],
            }
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

    # get_unified_stack_health
    registry.register(ToolDefinition(
        name="get_unified_stack_health",
        description="Get a comprehensive health snapshot of the local AI stack (status, rate-limits, hardware)",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_unified_stack_health_handler,
    ))

    logger.info("Registered 15 AI coordination tools")
