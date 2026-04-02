#!/usr/bin/env python3
"""Regression coverage for multi-agent orchestration framework."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack"))

from orchestration import (
    AgentHQ,
    AgentStatus,
    DelegationAPI,
    DelegationStatus,
    IsolationMode,
    MCPToolInvoker,
    SessionState,
    ToolStatus,
    WorkspaceManager,
)


async def test_agent_hq() -> None:
    """Test Agent HQ session management."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hq = AgentHQ(persistence_dir=Path(tmpdir))

        # Register agents
        agent1 = hq.register_agent("CodeAgent", capabilities={"code", "review"})
        agent2 = hq.register_agent("TestAgent", capabilities={"test", "validate"})
        assert agent1.agent_id in hq.global_agents
        assert agent2.agent_id in hq.global_agents

        # Create session
        session = hq.create_session("test-session", context={"goal": "test"})
        assert session.state == SessionState.CREATED
        assert session.session_id in hq.sessions

        # Start session
        started = await hq.start_session(session.session_id)
        assert started
        assert session.state == SessionState.RUNNING

        # Submit task
        task = await hq.submit_task(
            session.session_id,
            "Analyze code quality",
            required_capabilities={"code"},
        )
        assert task is not None
        assert task.task_id in session.tasks

        # Create checkpoint
        checkpoint = hq.create_checkpoint(session.session_id, "before-changes")
        assert checkpoint is not None
        assert len(session.checkpoints) == 1

        # Pause session
        paused = await hq.pause_session(session.session_id)
        assert paused
        assert session.state == SessionState.PAUSED

        # Resume session
        resumed = await hq.start_session(session.session_id)
        assert resumed
        assert session.state == SessionState.RUNNING

        # Get session status
        status = hq.get_session_status(session.session_id)
        assert status is not None
        assert "tasks" in status

        # Terminate session
        terminated = await hq.terminate_session(session.session_id)
        assert terminated
        assert session.state == SessionState.TERMINATED


async def test_workspace_isolation() -> None:
    """Test workspace isolation manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = WorkspaceManager(base_dir=Path(tmpdir))

        # Create workspace
        workspace = await manager.create_workspace(
            agent_id="agent-1",
            session_id="session-1",
            mode=IsolationMode.TEMP_DIR,
        )
        assert workspace.workspace_id in manager.workspaces
        assert workspace.root_path.exists()

        # Write file
        success = manager.write_file(workspace.workspace_id, "test.py", "print('hello')")
        assert success

        # Read file
        content = manager.read_file(workspace.workspace_id, "test.py")
        assert content == "print('hello')"

        # Track modification
        assert len(workspace.modifications) == 1
        assert workspace.modifications[0].operation == "create"

        # List files
        files = manager.get_workspace_files(workspace.workspace_id)
        assert "test.py" in files

        # Create second workspace for conflict detection
        workspace2 = await manager.create_workspace(
            agent_id="agent-2",
            session_id="session-1",
            mode=IsolationMode.TEMP_DIR,
        )
        manager.write_file(workspace2.workspace_id, "test.py", "print('world')")

        # Detect conflicts
        conflicts = manager.detect_conflicts("session-1")
        assert len(conflicts) == 1
        assert conflicts[0].file_path == "test.py"

        # Cleanup
        cleaned = await manager.cleanup_workspace(workspace.workspace_id, force=True)
        assert cleaned
        assert workspace.workspace_id not in manager.workspaces


async def test_delegation_api() -> None:
    """Test unified delegation API."""
    api = DelegationAPI()

    # Register agents
    agent1 = api.register_agent(
        "agent-1",
        "CodeReviewer",
        capabilities={"code_review", "security"},
        capability_levels={"code_review": 0.9, "security": 0.8},
    )
    agent2 = api.register_agent(
        "agent-2",
        "Tester",
        capabilities={"testing", "validation"},
    )

    assert "agent-1" in api.agents
    assert "agent-2" in api.agents

    # Check available agents
    available = api.get_available_agents(required_capabilities={"code_review"})
    assert len(available) == 1
    assert available[0].agent_id == "agent-1"

    # Delegate task (no executor, returns immediately)
    result = await api.delegate(
        task_description="Review authentication code",
        required_capabilities={"code_review"},
        priority=3,
    )
    assert result.status == DelegationStatus.COMPLETED
    assert result.assigned_agent == "agent-1"

    # Check queue status
    status = api.get_queue_status()
    assert status["completed_count"] >= 1


async def test_mcp_tool_invoker() -> None:
    """Test MCP tool invocation interface."""
    invoker = MCPToolInvoker(cache_enabled=True)

    # Register tools
    tool1 = invoker.register_tool(
        tool_id="search-code",
        name="Code Search",
        description="Search codebase for patterns",
        server_id="code-server",
        capabilities={"search", "code"},
        estimated_cost=0.01,
    )
    tool2 = invoker.register_tool(
        tool_id="lint-code",
        name="Code Linter",
        description="Run linting on code",
        server_id="lint-server",
        capabilities={"lint", "code"},
        rate_limit=60,
    )

    assert "search-code" in invoker.tools
    assert "lint-code" in invoker.tools

    # Search tools
    results = invoker.search_tools("search", capabilities={"code"})
    assert len(results) >= 1
    assert results[0].tool_id == "search-code"

    # Suggest tools for task
    suggestions = invoker.suggest_for_task("code_analysis")
    assert len(suggestions) >= 1

    # Get estimated cost
    cost = invoker.get_estimated_cost("search-code")
    assert cost == 0.01

    # Invoke tool (no executor, returns mock result)
    result = await invoker.invoke(
        tool_id="search-code",
        params={"pattern": "def main"},
        agent_id="test-agent",
    )
    assert result is not None

    # Check cache hit
    result2 = await invoker.invoke(
        tool_id="search-code",
        params={"pattern": "def main"},
        agent_id="test-agent",
    )
    assert result2 == result

    # Get usage report
    report = invoker.get_usage_report()
    assert report["tools_registered"] == 2


def main() -> int:
    asyncio.run(test_agent_hq())
    asyncio.run(test_workspace_isolation())
    asyncio.run(test_delegation_api())
    asyncio.run(test_mcp_tool_invoker())
    print("PASS: multi-agent orchestration framework is operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
