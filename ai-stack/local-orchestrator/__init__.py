#!/usr/bin/env python3
"""
Local Orchestrator Agent

Primary AI interface that routes all prompts through the local Gemma model,
uses MCP tools for context, and delegates to remote agents when needed.
"""

from .orchestrator import LocalOrchestrator, get_orchestrator
from routing_contract import RoutingDecision

from .router import TaskRouter, AgentBackend, TaskCategory

# Backward-compatible name retained while callers migrate to the canonical type.
RouteDecision = RoutingDecision
from .mcp_client import MCPClient, get_mcp_client
from .remote_agents import (
    RemoteAgentClient,
    RemoteAgentType,
    RemoteAgentResponse,
    get_remote_client,
    AGENT_CONFIGS,
)

__all__ = [
    # Orchestrator
    "LocalOrchestrator",
    "get_orchestrator",
    # Router
    "TaskRouter",
    "RoutingDecision",
    "RouteDecision",
    "AgentBackend",
    "TaskCategory",
    # MCP Client
    "MCPClient",
    "get_mcp_client",
    # Remote Agents
    "RemoteAgentClient",
    "RemoteAgentType",
    "RemoteAgentResponse",
    "get_remote_client",
    "AGENT_CONFIGS",
]
