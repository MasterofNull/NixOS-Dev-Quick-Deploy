#!/usr/bin/env python3
"""
Autonomous Agentic Orchestrator

Enables local agents to autonomously orchestrate multi-agent workflows,
delegating work to Claude and other agents with minimal human interaction.

Part of Phase 12: Autonomous Agentic Orchestration
"""

from .delegation_protocol import (
    TaskType,
    AgentPreference,
    TaskStatus,
    TaskContext,
    TaskConstraints,
    DelegatedTask,
    FileChange,
    ValidationResults,
    AgentQuestion,
    TaskResult,
    ClaudeAPIClient,
    DelegationProtocol,
    get_delegation_protocol,
)

__all__ = [
    # Task types and enums
    "TaskType",
    "AgentPreference",
    "TaskStatus",
    # Task structure
    "TaskContext",
    "TaskConstraints",
    "DelegatedTask",
    # Results
    "FileChange",
    "ValidationResults",
    "AgentQuestion",
    "TaskResult",
    # Clients and protocol
    "ClaudeAPIClient",
    "DelegationProtocol",
    "get_delegation_protocol",
]
