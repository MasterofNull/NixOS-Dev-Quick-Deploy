"""
MCP tool definitions and dispatch for hybrid-coordinator.

Contains the list_tools constant and call_tool dispatch logic.
The app object (@app.list_tools / @app.call_tool) stays in server.py;
server.py wraps these helpers in thin decorator stubs.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import mcp_handlers
    mcp_handlers.init(augment_query_fn=..., ...)

    @app.list_tools()
    async def list_tools():
        return mcp_handlers.TOOL_DEFINITIONS

    @app.call_tool()
    async def call_tool(name, arguments):
        return await mcp_handlers.dispatch_tool(name, arguments)
"""

import hashlib
import json
import logging
import os as _os
import time as _time
from datetime import datetime as _dt
from pathlib import Path as _Path
from typing import Any, Callable, Dict, List, Optional

from mcp.types import TextContent, Tool

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Audit logging configuration
# ---------------------------------------------------------------------------
_audit_log_path = _Path(_os.getenv('TOOL_AUDIT_LOG_PATH', '/var/log/nixos-ai-stack/tool-audit.jsonl'))


def _write_audit(
    tool_name: str,
    outcome: str,
    error_message: str | None,
    latency_ms: float,
    parameters: Dict[str, Any],
) -> None:
    """Write a structured audit log entry for a tool call."""
    try:
        parameters_hash = hashlib.sha256(
            json.dumps(parameters, sort_keys=True).encode()
        ).hexdigest()[:16]
        caller_hash = hashlib.sha256('anonymous'.encode()).hexdigest()[:16]
        
        entry = {
            'timestamp': _dt.utcnow().isoformat() + 'Z',
            'service': 'hybrid-coordinator',
            'tool_name': tool_name,
            'caller_hash': caller_hash,
            'parameters_hash': parameters_hash,
            'risk_tier': 'low',
            'outcome': outcome,
            'error_message': error_message,
            'latency_ms': latency_ms,
        }
        
        parent_dir = _audit_log_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
        
        with open(_audit_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:  # noqa: BLE001 - audit failure must NEVER crash the service
        logger.warning('audit_write_failed', tool_name=tool_name)

# ---------------------------------------------------------------------------
# Injected dependencies (set via init())
# ---------------------------------------------------------------------------
_augment_query: Optional[Callable] = None
_route_search: Optional[Callable] = None
_hybrid_search: Optional[Callable] = None
_store_memory: Optional[Callable] = None
_recall_memory: Optional[Callable] = None
_run_harness_eval: Optional[Callable] = None
_record_learning_feedback: Optional[Callable] = None
_track_interaction: Optional[Callable] = None
_update_outcome: Optional[Callable] = None
_generate_dataset: Optional[Callable] = None
_embed_fn: Optional[Callable] = None
_qdrant: Optional[Any] = None
_HARNESS_STATS: Optional[Dict] = None


def init(
    *,
    augment_query_fn: Callable,
    route_search_fn: Callable,
    hybrid_search_fn: Callable,
    store_memory_fn: Callable,
    recall_memory_fn: Callable,
    run_harness_eval_fn: Callable,
    record_learning_feedback_fn: Callable,
    track_interaction_fn: Callable,
    update_outcome_fn: Callable,
    generate_dataset_fn: Callable,
    embed_fn: Callable,
    qdrant_client: Any,
    harness_stats: Dict,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _augment_query, _route_search, _hybrid_search, _store_memory, _recall_memory
    global _run_harness_eval, _record_learning_feedback, _track_interaction, _update_outcome
    global _generate_dataset, _embed_fn, _qdrant, _HARNESS_STATS
    _augment_query = augment_query_fn
    _route_search = route_search_fn
    _hybrid_search = hybrid_search_fn
    _store_memory = store_memory_fn
    _recall_memory = recall_memory_fn
    _run_harness_eval = run_harness_eval_fn
    _record_learning_feedback = record_learning_feedback_fn
    _track_interaction = track_interaction_fn
    _update_outcome = update_outcome_fn
    _generate_dataset = generate_dataset_fn
    _embed_fn = embed_fn
    _qdrant = qdrant_client
    _HARNESS_STATS = harness_stats


# ---------------------------------------------------------------------------
# Tool definitions (pure data — no dependencies)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name="augment_query",
        description="Augment a query with relevant context from local knowledge base",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to augment with context",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Type of agent requesting context (local or remote)",
                    "enum": ["local", "remote"],
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="track_interaction",
        description="Record an interaction for learning and analysis",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
                "agent_type": {"type": "string"},
                "model_used": {"type": "string"},
                "context_ids": {"type": "array", "items": {"type": "string"}},
                "tokens_used": {"type": "integer"},
                "latency_ms": {"type": "integer"},
            },
            "required": ["query", "response", "agent_type", "model_used"],
        },
    ),
    Tool(
        name="update_outcome",
        description="Update interaction outcome and trigger learning",
        inputSchema={
            "type": "object",
            "properties": {
                "interaction_id": {"type": "string"},
                "outcome": {
                    "type": "string",
                    "enum": ["success", "partial", "failure"],
                },
                "user_feedback": {"type": "integer", "minimum": -1, "maximum": 1},
            },
            "required": ["interaction_id", "outcome"],
        },
    ),
    Tool(
        name="generate_training_data",
        description="Export high-value interactions to JSONL interaction archive",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="search_context",
        description="Search specific collection for relevant context",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collection": {
                    "type": "string",
                    "enum": [
                        "codebase-context",
                        "skills-patterns",
                        "error-solutions",
                        "best-practices",
                    ],
                },
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query", "collection"],
        },
    ),
    Tool(
        name="hybrid_search",
        description="Run hybrid search combining vector similarity and keyword matching",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collections": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 5},
                "keyword_limit": {"type": "integer", "default": 5},
                "score_threshold": {"type": "number", "default": 0.7},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="route_search",
        description="Route a query to SQL, semantic, keyword, tree, or hybrid search",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                    "default": "auto",
                },
                "prefer_local": {"type": "boolean", "default": True},
                "context": {"type": "object"},
                "limit": {"type": "integer", "default": 5},
                "keyword_limit": {"type": "integer", "default": 5},
                "score_threshold": {"type": "number", "default": 0.7},
                "generate_response": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="store_agent_memory",
        description="Store episodic, semantic, or procedural memory items",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": ["episodic", "semantic", "procedural"],
                },
                "summary": {"type": "string"},
                "content": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["memory_type", "summary"],
        },
    ),
    Tool(
        name="recall_agent_memory",
        description="Recall memory using hybrid or tree retrieval mode",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "memory_types": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 8},
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["hybrid", "tree"],
                    "default": "hybrid",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="run_harness_eval",
        description="Run deterministic harness evaluation with scorecard output",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                    "default": "auto",
                },
                "expected_keywords": {"type": "array", "items": {"type": "string"}},
                "max_latency_ms": {"type": "integer"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="harness_stats",
        description="Get cumulative harness evaluation statistics and failure taxonomy",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="learning_feedback",
        description="Store user corrections and feedback for learning",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "correction": {"type": "string"},
                "original_response": {"type": "string"},
                "interaction_id": {"type": "string"},
                "rating": {"type": "integer", "minimum": -1, "maximum": 1},
                "tags": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string"},
                "variant": {"type": "string"},
            },
            "required": ["query", "correction"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def dispatch_tool(name: str, arguments: Any) -> List[TextContent]:
    """Dispatch an MCP tool call by name."""
    _start = _time.time()
    try:
        if name == "augment_query":
            query = arguments.get("query", "")
            agent_type = arguments.get("agent_type", "remote")
            result = await _augment_query(query, agent_type)
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "track_interaction":
            interaction_id = await _track_interaction(
                query=arguments.get("query", ""),
                response=arguments.get("response", ""),
                agent_type=arguments.get("agent_type", "unknown"),
                model_used=arguments.get("model_used", "unknown"),
                context_ids=arguments.get("context_ids", []),
                tokens_used=arguments.get("tokens_used", 0),
                latency_ms=arguments.get("latency_ms", 0),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"interaction_id": interaction_id}))]

        elif name == "update_outcome":
            await _update_outcome(
                interaction_id=arguments.get("interaction_id", ""),
                outcome=arguments.get("outcome", "unknown"),
                user_feedback=arguments.get("user_feedback", 0),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"status": "updated"}))]

        elif name == "generate_training_data":
            dataset_path = await _generate_dataset()
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"dataset_path": dataset_path}))]

        elif name == "search_context":
            query = arguments.get("query", "")
            collection = arguments.get("collection", "codebase-context")
            limit = arguments.get("limit", 5)
            query_embedding = await _embed_fn(query)
            results = _qdrant.query_points(
                collection_name=collection,
                query=query_embedding,
                limit=limit,
                score_threshold=0.7,
            ).points
            formatted = [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(formatted, indent=2))]

        elif name == "hybrid_search":
            result = await _hybrid_search(
                query=arguments.get("query", ""),
                collections=arguments.get("collections"),
                limit=arguments.get("limit", 5),
                keyword_limit=arguments.get("keyword_limit", 5),
                score_threshold=arguments.get("score_threshold", 0.7),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "route_search":
            result = await _route_search(
                query=arguments.get("query", ""),
                mode=arguments.get("mode", "auto"),
                prefer_local=arguments.get("prefer_local", True),
                context=arguments.get("context"),
                limit=arguments.get("limit", 5),
                keyword_limit=arguments.get("keyword_limit", 5),
                score_threshold=arguments.get("score_threshold", 0.7),
                generate_response=arguments.get("generate_response", False),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "store_agent_memory":
            result = await _store_memory(
                memory_type=arguments.get("memory_type", ""),
                summary=arguments.get("summary", ""),
                content=arguments.get("content"),
                metadata=arguments.get("metadata"),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "recall_agent_memory":
            result = await _recall_memory(
                query=arguments.get("query", ""),
                memory_types=arguments.get("memory_types"),
                limit=arguments.get("limit"),
                retrieval_mode=arguments.get("retrieval_mode", "hybrid"),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_harness_eval":
            result = await _run_harness_eval(
                query=arguments.get("query", ""),
                expected_keywords=arguments.get("expected_keywords"),
                mode=arguments.get("mode", "auto"),
                max_latency_ms=arguments.get("max_latency_ms"),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "harness_stats":
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(_HARNESS_STATS, indent=2))]

        elif name == "learning_feedback":
            feedback_id = await _record_learning_feedback(
                query=arguments.get("query", ""),
                correction=arguments.get("correction", ""),
                original_response=arguments.get("original_response"),
                interaction_id=arguments.get("interaction_id"),
                rating=arguments.get("rating"),
                tags=arguments.get("tags"),
                model=arguments.get("model"),
                variant=arguments.get("variant"),
            )
            _write_audit(name, 'success', None, (_time.time() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"feedback_id": feedback_id}))]

        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as exc:
        _write_audit(name, 'error', str(exc), (_time.time() - _start) * 1000, arguments)
        raise
