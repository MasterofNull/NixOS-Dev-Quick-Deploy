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
from .verification import (
    CheckStatus,
    CheckResult,
    VerificationResult,
    VerificationFramework,
    get_verifier,
)
from .approval import (
    RiskLevel,
    ApprovalTier,
    ApprovalDecision,
    ApprovalWorkflow,
    get_approval_workflow,
)
from .orchestrator import (
    ApprovalMode,
    OrchestrationResult,
    AutonomousOrchestrator,
    get_orchestrator,
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
    # Verification
    "CheckStatus",
    "CheckResult",
    "VerificationResult",
    "VerificationFramework",
    "get_verifier",
    # Approval
    "RiskLevel",
    "ApprovalTier",
    "ApprovalDecision",
    "ApprovalWorkflow",
    "get_approval_workflow",
    # Orchestrator
    "ApprovalMode",
    "OrchestrationResult",
    "AutonomousOrchestrator",
    "get_orchestrator",
]
