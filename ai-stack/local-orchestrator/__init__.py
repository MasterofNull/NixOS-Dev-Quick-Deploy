#!/usr/bin/env python3
"""
Local Orchestrator Agent

Primary AI interface that routes all prompts through the local Gemma model,
uses MCP tools for context, and delegates to remote agents when needed.
"""

from .orchestrator import LocalOrchestrator, get_orchestrator
from .router import TaskRouter, RouteDecision, AgentBackend, TaskCategory
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
