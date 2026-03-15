#!/usr/bin/env python3
"""
Local Agent Tool Calling Infrastructure

Provides OpenClaw-like tool calling capabilities for local llama.cpp models.

Usage:
    from local_agents import get_registry, initialize_builtin_tools

    # Initialize registry with built-in tools
    registry = get_registry()
    initialize_builtin_tools(registry)

    # Get tools for model
    tools = registry.get_tools_for_model()

    # Execute tool call
    tool_call = registry.parse_tool_call_from_llama(model_output)
    if tool_call:
        result = await registry.execute_tool_call(tool_call)
        formatted = registry.format_tool_result(result)

Part of Phase 11: Local Agent Agentic Capabilities
"""

import logging
from typing import Optional

from .tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolCall,
    ToolRegistry,
    get_registry,
)
from .agent_executor import (
    AgentType,
    Task,
    TaskStatus,
    LocalAgentExecutor,
    get_executor,
)
from .task_router import (
    AgentTarget,
    RoutingDecision,
    TaskRouter,
    get_router,
)
from .monitoring_agent import (
    HealthStatus,
    HealthCheck,
    MonitoringAgent,
)
from .self_improvement import (
    QualityDimension,
    QualityScore,
    ImprovementRecommendation,
    SelfImprovementEngine,
)

logger = logging.getLogger(__name__)


def initialize_builtin_tools(registry: Optional[ToolRegistry] = None) -> ToolRegistry:
    """
    Initialize tool registry with all built-in tools.

    Args:
        registry: Optional registry instance (creates new if None)

    Returns:
        Tool registry with all built-in tools registered
    """
    if registry is None:
        registry = get_registry()

    # Import and register tool modules
    try:
        from .builtin_tools.file_operations import register_file_tools
        register_file_tools(registry)
    except ImportError as e:
        logger.warning(f"Failed to import file_operations tools: {e}")

    try:
        from .builtin_tools.shell_tools import register_shell_tools
        register_shell_tools(registry)
    except ImportError as e:
        logger.warning(f"Failed to import shell_tools: {e}")

    try:
        from .builtin_tools.ai_coordination import register_ai_coordination_tools
        register_ai_coordination_tools(registry)
    except ImportError as e:
        logger.warning(f"Failed to import ai_coordination tools: {e}")

    try:
        from .builtin_tools.computer_use import register_computer_use_tools
        register_computer_use_tools(registry)
    except ImportError as e:
        logger.warning(f"Failed to import computer_use tools: {e}")

    logger.info(f"Initialized tool registry with {len(registry.tools)} built-in tools")

    return registry


__all__ = [
    # Tool registry
    "SafetyPolicy",
    "ToolCategory",
    "ToolDefinition",
    "ToolCall",
    "ToolRegistry",
    "get_registry",
    "initialize_builtin_tools",
    # Agent executor
    "AgentType",
    "Task",
    "TaskStatus",
    "LocalAgentExecutor",
    "get_executor",
    # Task router
    "AgentTarget",
    "RoutingDecision",
    "TaskRouter",
    "get_router",
    # Monitoring agent
    "HealthStatus",
    "HealthCheck",
    "MonitoringAgent",
    # Self-improvement
    "QualityDimension",
    "QualityScore",
    "ImprovementRecommendation",
    "SelfImprovementEngine",
]
