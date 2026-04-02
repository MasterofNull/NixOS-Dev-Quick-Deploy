"""
Multi-Agent Orchestration Framework

Provides centralized control and coordination for multi-agent systems:
- AgentHQ: Session management with pause/resume/checkpoint
- WorkspaceManager: Per-agent isolated execution environments
- DelegationAPI: Unified task delegation with capability matching
- MCPToolInvoker: MCP tool discovery and invocation

Part of Phase 4.2: Multi-Agent Orchestration Enhancements
"""

from .agent_hq import (
    AgentHQ,
    AgentInfo,
    AgentStatus,
    Checkpoint,
    Session,
    SessionState,
    TaskInfo,
)
from .delegation_api import (
    DelegationAPI,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    DelegationTarget,
    RejectionReason,
    delegate_to,
    require_capability,
)
from .mcp_tool_invoker import (
    ErrorRecoveryStrategy,
    MCPToolInvoker,
    ToolMetadata,
    ToolStatus,
)
from .workspace_isolation import (
    ConflictReport,
    ConflictStrategy,
    IsolationMode,
    Workspace,
    WorkspaceManager,
)

__all__ = [
    # Agent HQ
    "AgentHQ",
    "AgentInfo",
    "AgentStatus",
    "Checkpoint",
    "Session",
    "SessionState",
    "TaskInfo",
    # Delegation
    "DelegationAPI",
    "DelegationRequest",
    "DelegationResult",
    "DelegationStatus",
    "DelegationTarget",
    "RejectionReason",
    "delegate_to",
    "require_capability",
    # MCP Tools
    "ErrorRecoveryStrategy",
    "MCPToolInvoker",
    "ToolMetadata",
    "ToolStatus",
    # Workspace
    "ConflictReport",
    "ConflictStrategy",
    "IsolationMode",
    "Workspace",
    "WorkspaceManager",
]
