"""
Federated Learning MCP Tool Handlers

Provides MCP tools for capability-based agent routing and cross-agent learning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from mcp.types import TextContent, Tool

from federated_integration import FederatedIntegration

logger = logging.getLogger("federated_mcp_handlers")

# Global reference to federated integration (initialized by server)
_federated_integration: Optional[FederatedIntegration] = None


def set_federated_integration(integration: FederatedIntegration):
    """Set the global federated integration instance."""
    global _federated_integration
    _federated_integration = integration
    logger.info("Federated integration initialized")


FEDERATED_TOOL_DEFINITIONS = [
    Tool(
        name="recommend_agent_for_task",
        description=(
            "Get the best agent recommendation for a task based on cross-agent "
            "capability matrix. Returns agent name, capability score, and reasoning. "
            "Use this before routing complex tasks to select the most capable agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The task query to analyze for agent recommendation"
                },
                "available_agents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of available agent names to choose from (claude, qwen, codex, gemini, etc.)"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="get_agent_recommendations",
        description=(
            "Get cross-agent pattern recommendations for a specific agent. "
            "Returns patterns discovered by other agents that might benefit this agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent name to get recommendations for (claude, qwen, etc.)"
                },
                "domain": {
                    "type": "string",
                    "description": "Optional task domain to filter recommendations (nixos, python, debugging, etc.)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recommendations to return (default: 3)"
                }
            },
            "required": ["agent"]
        }
    ),
    Tool(
        name="track_task_completion",
        description=(
            "Track a task completion for federated learning. Records the pattern "
            "for future cross-agent learning and capability matrix updates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent that completed the task (claude, qwen, etc.)"
                },
                "query": {
                    "type": "string",
                    "description": "The original task query"
                },
                "response": {
                    "type": "string",
                    "description": "The generated response/solution"
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the task completed successfully"
                },
                "completion_time_ms": {
                    "type": "integer",
                    "description": "Time taken to complete in milliseconds"
                },
                "token_usage": {
                    "type": "integer",
                    "description": "Number of tokens used"
                }
            },
            "required": ["agent", "query", "response", "success", "completion_time_ms", "token_usage"]
        }
    ),
    Tool(
        name="get_federated_stats",
        description=(
            "Get federated learning statistics including pattern counts, "
            "recommendation effectiveness, and capability matrix coverage."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


async def handle_recommend_agent_for_task(
    query: str,
    available_agents: Optional[List[str]] = None
) -> List[TextContent]:
    """Handle recommend_agent_for_task tool call."""
    if not _federated_integration:
        return [TextContent(
            type="text",
            text="Error: Federated integration not initialized"
        )]

    try:
        agent_name, score, reasoning = await _federated_integration.get_best_agent_for_task(
            query, available_agents
        )

        if agent_name:
            result = {
                "recommended_agent": agent_name,
                "capability_score": score,
                "reasoning": reasoning,
                "domain": _federated_integration.detect_task_domain(query)
            }
        else:
            result = {
                "recommended_agent": None,
                "reasoning": reasoning,
                "domain": _federated_integration.detect_task_domain(query)
            }

        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in recommend_agent_for_task: {e}")
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_get_agent_recommendations(
    agent: str,
    domain: Optional[str] = None,
    limit: int = 3
) -> List[TextContent]:
    """Handle get_agent_recommendations tool call."""
    if not _federated_integration:
        return [TextContent(
            type="text",
            text="Error: Federated integration not initialized"
        )]

    try:
        recommendations = await _federated_integration.get_recommendations_for_agent(
            agent, domain, limit
        )

        if not recommendations:
            return [TextContent(
                type="text",
                text=f"No recommendations available for {agent}" +
                     (f" in domain '{domain}'" if domain else "")
            )]

        # Format recommendations
        formatted_recs = []
        for rec in recommendations:
            formatted_recs.append({
                "source_agent": rec["source_agent"],
                "confidence": rec["confidence"],
                "reason": rec["reason"],
                "domain": rec["domain"],
                "pattern_summary": {
                    "success_rate": f"{rec['success_rate']:.0%}",
                    "usage_count": rec["usage_count"]
                }
            })

        import json
        return [TextContent(
            type="text",
            text=json.dumps({
                "agent": agent,
                "domain": domain,
                "recommendations": formatted_recs
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in get_agent_recommendations: {e}")
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_track_task_completion(
    agent: str,
    query: str,
    response: str,
    success: bool,
    completion_time_ms: int,
    token_usage: int
) -> List[TextContent]:
    """Handle track_task_completion tool call."""
    if not _federated_integration:
        return [TextContent(
            type="text",
            text="Error: Federated integration not initialized"
        )]

    try:
        tracked = await _federated_integration.track_success_pattern(
            agent=agent,
            query=query,
            response=response,
            success=success,
            completion_time_ms=completion_time_ms,
            token_usage=token_usage
        )

        domain = _federated_integration.detect_task_domain(query)

        if tracked:
            return [TextContent(
                type="text",
                text=f"✓ Tracked pattern: {agent}/{domain}, success={success}"
            )]
        else:
            return [TextContent(
                type="text",
                text="⚠ Pattern tracking failed (non-fatal)"
            )]

    except Exception as e:
        logger.error(f"Error in track_task_completion: {e}")
        return [TextContent(
            type="text",
            text=f"Warning: Pattern tracking error (non-fatal): {str(e)}"
        )]


async def handle_get_federated_stats() -> List[TextContent]:
    """Handle get_federated_stats tool call."""
    if not _federated_integration:
        return [TextContent(
            type="text",
            text="Error: Federated integration not initialized"
        )]

    try:
        stats = await _federated_integration.get_statistics()

        import json
        return [TextContent(
            type="text",
            text=json.dumps(stats, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in get_federated_stats: {e}")
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def dispatch_federated_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Dispatch federated learning tool calls."""
    if name == "recommend_agent_for_task":
        return await handle_recommend_agent_for_task(**arguments)

    elif name == "get_agent_recommendations":
        return await handle_get_agent_recommendations(**arguments)

    elif name == "track_task_completion":
        return await handle_track_task_completion(**arguments)

    elif name == "get_federated_stats":
        return await handle_get_federated_stats()

    else:
        return [TextContent(
            type="text",
            text=f"Unknown federated learning tool: {name}"
        )]
