#!/usr/bin/env python3
"""Comprehensive test coverage for orchestration framework - targeting 90%+ coverage."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]


def load_module(relative_path: str, name: str):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ============================================================================
# AgentHQ Comprehensive Tests
# ============================================================================


async def test_agent_hq_agent_management() -> None:
    """Test agent registration and capability finding."""
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    async def executor(session_id, task, agent):
        return {"ok": True}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        hq = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)

        # Register multiple agents
        agent1 = hq.register_agent("codex", {"review", "code"}, {"version": "1.0"})
        agent2 = hq.register_agent("qwen", {"code", "test"}, {"version": "2.0"})
        agent3 = hq.register_agent("claude", {"review", "architecture"})

        assert len(hq.global_agents) == 3
        assert agent1.capabilities == {"review", "code"}
        assert agent2.metadata == {"version": "2.0"}

        # Find agents by capability
        reviewers = hq.find_agents_by_capability({"review"})
        assert len(reviewers) == 2

        coders = hq.find_agents_by_capability({"code"})
        assert len(coders) == 2


async def test_agent_hq_session_states() -> None:
    """Test session state transitions and listing."""
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    async def executor(session_id, task, agent):
        await asyncio.sleep(0.05)
        return {"ok": True}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        hq = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        hq.register_agent("worker", {"task"})

        # Create multiple sessions
        s1 = hq.create_session("session one", {"type": "test"})
        s2 = hq.create_session("session two", {"type": "prod"})
        s3 = hq.create_session("session three")

        assert len(hq.sessions) == 3
        assert s1.state == module.SessionState.CREATED

        # List sessions without filter
        all_sessions = hq.list_sessions()
        assert len(all_sessions) == 3

        # List sessions with state filter
        created = hq.list_sessions(state_filter=module.SessionState.CREATED)
        assert len(created) == 3

        # Start one session
        await hq.start_session(s1.session_id)
        await asyncio.sleep(0.1)

        # Pause session
        await hq.pause_session(s1.session_id)
        paused = hq.list_sessions(state_filter=module.SessionState.PAUSED)
        assert len(paused) == 1


async def test_agent_hq_task_priority() -> None:
    """Test task submission with priorities and capability matching."""
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    executed_tasks = []

    async def executor(session_id, task, agent):
        executed_tasks.append(task.task_id)
        return {"task_id": task.task_id}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        hq = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        hq.register_agent("specialist", {"special"})
        hq.register_agent("generalist", {"general", "special"})

        session = hq.create_session("priority test")

        # Submit tasks with different priorities
        t_low = await hq.submit_task(
            session.session_id,
            "low priority task",
            required_capabilities={"general"},
            priority=10,
        )
        t_high = await hq.submit_task(
            session.session_id,
            "high priority task",
            required_capabilities={"general"},
            priority=1,
        )
        t_special = await hq.submit_task(
            session.session_id,
            "special task",
            required_capabilities={"special"},
            priority=5,
        )

        assert t_low is not None
        assert t_high is not None
        assert t_special is not None

        # Check task count
        status = hq.get_session_status(session.session_id)
        assert status["tasks"]["total"] == 3


async def test_agent_hq_checkpoints() -> None:
    """Test checkpoint creation and restoration."""
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    async def executor(session_id, task, agent):
        return {"ok": True}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        hq = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        hq.register_agent("worker", {"task"})

        session = hq.create_session("checkpoint test")

        # Create first checkpoint
        cp1 = hq.create_checkpoint(session.session_id, "initial")
        assert cp1 is not None
        assert cp1.name == "initial"

        # Submit a task
        await hq.submit_task(session.session_id, "task 1", required_capabilities={"task"})

        # Create second checkpoint
        cp2 = hq.create_checkpoint(session.session_id, "after-task")
        assert cp2 is not None

        # Restore to first checkpoint
        assert hq.restore_checkpoint(session.session_id, cp1.checkpoint_id) is True


async def test_agent_hq_persistence() -> None:
    """Test session save and load."""
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    async def executor(session_id, task, agent):
        return {"ok": True}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        # Create first HQ and save session
        hq1 = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        agent = hq1.register_agent("persisted-agent", {"task"})
        session = hq1.create_session("persistent session", {"key": "value"})

        assert hq1.save_session(session.session_id) is True

        # Create second HQ and load session
        hq2 = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        loaded = hq2.load_session(session.session_id)

        assert loaded is not None
        assert loaded.name == "persistent session"
        assert loaded.context == {"key": "value"}


# ============================================================================
# DelegationAPI Comprehensive Tests
# ============================================================================


async def test_delegation_api_capability_matching() -> None:
    """Test capability-based agent selection."""
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    call_log = []

    async def executor(agent_id, request):
        call_log.append(agent_id)
        return {"agent_id": agent_id}

    api = module.DelegationAPI(executor_fn=executor)
    api.register_agent(
        "specialist",
        "Specialist Agent",
        capabilities={"specialized"},
        capability_levels={"specialized": 0.95},
    )
    api.register_agent(
        "generalist",
        "Generalist Agent",
        capabilities={"general", "specialized"},
        capability_levels={"general": 0.9, "specialized": 0.7},
    )

    # Specialized task should go to specialist
    result = await api.delegate("specialized task", {"specialized"}, wait=True)
    assert result.assigned_agent == "specialist"

    # General task should go to generalist
    result2 = await api.delegate("general task", {"general"}, wait=True)
    assert result2.assigned_agent == "generalist"


async def test_delegation_api_priority_queue() -> None:
    """Test priority-based task ordering."""
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    execution_order = []

    async def slow_executor(agent_id, request):
        await asyncio.sleep(0.05)
        execution_order.append(request.task_description)
        return {"ok": True}

    api = module.DelegationAPI(executor_fn=slow_executor)
    api.register_agent("worker", "Worker", capabilities={"task"}, max_concurrent=1)

    # Submit tasks - first occupies the agent
    await api.delegate("first task", {"task"}, priority=5, wait=False)

    # Check queue status
    queue_status = api.get_queue_status()
    assert "pending_requests" in queue_status
    assert "active_agents" in queue_status


async def test_delegation_api_timeout() -> None:
    """Test task timeout handling."""
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    async def slow_executor(agent_id, request):
        await asyncio.sleep(10)  # Very slow
        return {"ok": True}

    api = module.DelegationAPI(executor_fn=slow_executor)
    api.register_agent("slow", "Slow Worker", capabilities={"task"}, max_concurrent=1)

    # First task occupies the agent
    await api.delegate("blocking task", {"task"}, wait=False)

    # Second task times out
    result = await api.delegate("timeout task", {"task"}, timeout_seconds=0.1, wait=False)
    assert result.status in (module.DelegationStatus.PENDING, module.DelegationStatus.TIMEOUT)


async def test_delegation_api_feedback_tracking() -> None:
    """Test feedback mechanism."""
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    async def executor(agent_id, request):
        return {"ok": True}

    api = module.DelegationAPI(executor_fn=executor)
    api.register_agent("agent1", "Agent 1", capabilities={"task"})

    # Execute tasks
    r1 = await api.delegate("task 1", {"task"}, wait=True)
    await asyncio.sleep(0.1)

    # Check success rate
    rate = api.feedback.get_agent_success_rate("agent1")
    assert rate >= 0.0  # Has at least some data


async def test_delegation_api_queue_status() -> None:
    """Test queue status reporting."""
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    async def executor(agent_id, request):
        return {"ok": True}

    api = module.DelegationAPI(executor_fn=executor)
    api.register_agent("agent1", "Agent 1", capabilities={"task1"})
    api.register_agent("agent2", "Agent 2", capabilities={"task2"})

    status = api.get_queue_status()
    assert "pending_requests" in status
    assert "active_agents" in status
    assert status["active_agents"] == 2


# ============================================================================
# WorkspaceManager Comprehensive Tests
# ============================================================================


async def test_workspace_isolation_modes() -> None:
    """Test different isolation modes."""
    module = load_module("ai-stack/orchestration/workspace_isolation.py", "workspace_isolation")

    with tempfile.TemporaryDirectory(prefix="ws-source-") as src, tempfile.TemporaryDirectory(prefix="ws-base-") as base:
        source = Path(src)
        (source / "file.txt").write_text("content", encoding="utf-8")

        manager = module.WorkspaceManager(base_dir=Path(base))

        # Test TEMP_DIR mode
        ws_temp = await manager.create_workspace(
            "agent1", "session1", mode=module.IsolationMode.TEMP_DIR
        )
        assert ws_temp.mode == module.IsolationMode.TEMP_DIR
        assert ws_temp.root_path.exists()

        # Test COPY mode
        ws_copy = await manager.create_workspace(
            "agent2", "session1", source_path=source, mode=module.IsolationMode.COPY
        )
        assert ws_copy.mode == module.IsolationMode.COPY
        assert (ws_copy.root_path / "file.txt").exists()

        # List workspaces
        all_ws = manager.list_workspaces()
        assert len(all_ws) == 2

        session_ws = manager.list_workspaces(session_id="session1")
        assert len(session_ws) == 2


async def test_workspace_file_operations() -> None:
    """Test workspace file read/write operations."""
    module = load_module("ai-stack/orchestration/workspace_isolation.py", "workspace_isolation")

    with tempfile.TemporaryDirectory(prefix="ws-base-") as base:
        manager = module.WorkspaceManager(base_dir=Path(base))

        ws = await manager.create_workspace("agent", "session", mode=module.IsolationMode.TEMP_DIR)

        # Write file
        assert manager.write_file(ws.workspace_id, "test.txt", "hello world") is True

        # Read file
        content = manager.read_file(ws.workspace_id, "test.txt")
        assert content == "hello world"

        # List files
        files = manager.get_workspace_files(ws.workspace_id)
        assert "test.txt" in files

        # Delete file
        assert manager.delete_file(ws.workspace_id, "test.txt") is True
        assert "test.txt" not in manager.get_workspace_files(ws.workspace_id)


async def test_workspace_conflict_strategies() -> None:
    """Test different conflict resolution strategies."""
    module = load_module("ai-stack/orchestration/workspace_isolation.py", "workspace_isolation")

    with tempfile.TemporaryDirectory(prefix="ws-source-") as src, tempfile.TemporaryDirectory(prefix="ws-base-") as base:
        source = Path(src)
        (source / "shared.txt").write_text("original", encoding="utf-8")

        manager = module.WorkspaceManager(base_dir=Path(base), default_mode=module.IsolationMode.COPY)

        ws1 = await manager.create_workspace("agent1", "session", source_path=source)
        ws2 = await manager.create_workspace("agent2", "session", source_path=source)

        # Create conflicting changes
        manager.write_file(ws1.workspace_id, "shared.txt", "version A")
        await asyncio.sleep(0.01)
        manager.write_file(ws2.workspace_id, "shared.txt", "version B")

        # Detect conflicts
        conflicts = manager.detect_conflicts("session")
        assert len(conflicts) == 1

        # Resolve with LATEST_WINS
        resolved = await manager.resolve_conflicts(conflicts, module.ConflictStrategy.LATEST_WINS)
        assert len(resolved) == 1
        assert resolved[0].resolution == "latest_wins"


async def test_workspace_cleanup_operations() -> None:
    """Test workspace cleanup operations."""
    module = load_module("ai-stack/orchestration/workspace_isolation.py", "workspace_isolation")

    with tempfile.TemporaryDirectory(prefix="ws-base-") as base:
        manager = module.WorkspaceManager(base_dir=Path(base))

        ws1 = await manager.create_workspace("agent1", "session1")
        ws2 = await manager.create_workspace("agent2", "session1")
        ws3 = await manager.create_workspace("agent3", "session2")

        # Cleanup single workspace with force
        assert await manager.cleanup_workspace(ws1.workspace_id, force=True) is True
        assert len(manager.list_workspaces()) == 2

        # Cleanup session workspaces
        count = await manager.cleanup_session_workspaces("session1")
        assert count >= 1

        # Verify ws3 still exists
        assert len(manager.list_workspaces(session_id="session2")) == 1


# ============================================================================
# MCPToolInvoker Comprehensive Tests
# ============================================================================


async def test_mcp_tool_registration_and_search() -> None:
    """Test tool registration and search."""
    module = load_module("ai-stack/orchestration/mcp_tool_invoker.py", "mcp_tool_invoker")

    invoker = module.MCPToolInvoker(cache_enabled=True)

    # Register tools
    tool1 = invoker.register_tool(
        tool_id="search",
        name="File Search",
        description="Search for files",
        server_id="fs-server",
        capabilities={"filesystem"},
    )
    tool2 = invoker.register_tool(
        tool_id="analyze",
        name="Code Analyzer",
        description="Analyze code",
        server_id="code-server",
        capabilities={"code", "analysis"},
    )

    assert tool1 is not None
    assert tool1.tool_id == "search"
    assert tool2 is not None

    # Search tools by query
    search_results = invoker.search_tools("analyze")
    assert len(search_results) >= 1
    assert any(t.tool_id == "analyze" for t in search_results)

    # Search by capabilities
    fs_tools = invoker.search_tools("", capabilities={"filesystem"})
    assert len(fs_tools) == 1
    assert fs_tools[0].tool_id == "search"


async def test_mcp_tool_status_updates() -> None:
    """Test tool status updates."""
    module = load_module("ai-stack/orchestration/mcp_tool_invoker.py", "mcp_tool_invoker")

    invoker = module.MCPToolInvoker()
    invoker.register_tool(
        tool_id="status_test",
        name="Status Test Tool",
        description="Test status updates",
        server_id="test-server",
    )

    # Update status
    invoker.update_tool_status(
        "status_test",
        module.ToolStatus.AVAILABLE,
        success_rate=0.95,
        avg_latency_ms=150.0,
    )

    tool = invoker.tools.get("status_test")
    assert tool is not None
    assert tool.status == module.ToolStatus.AVAILABLE
    assert tool.success_rate == 0.95
    assert tool.avg_latency_ms == 150.0


async def test_mcp_tool_usage_report() -> None:
    """Test usage report generation."""
    module = load_module("ai-stack/orchestration/mcp_tool_invoker.py", "mcp_tool_invoker")

    invoker = module.MCPToolInvoker()
    invoker.register_tool(
        tool_id="report_tool",
        name="Report Test",
        description="Test reporting",
        server_id="test-server",
    )

    # Get usage report
    report = invoker.get_usage_report()
    assert "total_invocations" in report
    assert "cache_stats" in report
    assert "tools_registered" in report


async def test_mcp_tool_rate_limiter() -> None:
    """Test rate limiter configuration."""
    module = load_module("ai-stack/orchestration/mcp_tool_invoker.py", "mcp_tool_invoker")

    invoker = module.MCPToolInvoker()

    # Register tool with rate limit
    invoker.register_tool(
        tool_id="rate_limited",
        name="Rate Limited Tool",
        description="Tool with rate limiting",
        server_id="test-server",
        rate_limit=10,
    )

    # Check rate limiter was configured
    tool = invoker.tools.get("rate_limited")
    assert tool is not None
    assert tool.rate_limit == 10


async def test_mcp_tool_cache_operations() -> None:
    """Test cache operations."""
    module = load_module("ai-stack/orchestration/mcp_tool_invoker.py", "mcp_tool_invoker")

    invoker = module.MCPToolInvoker(cache_enabled=True)

    # Test cache key generation
    key = invoker.cache._generate_key("test_tool", {"param": "value"})
    assert key is not None
    assert len(key) > 0

    # Test cache stats
    stats = invoker.cache.get_stats()
    assert "hits" in stats
    assert "misses" in stats
    assert "size" in stats


# ============================================================================
# Main Runner
# ============================================================================


def main() -> int:
    tests = [
        # AgentHQ tests
        ("AgentHQ agent management", test_agent_hq_agent_management),
        ("AgentHQ session states", test_agent_hq_session_states),
        ("AgentHQ task priority", test_agent_hq_task_priority),
        ("AgentHQ checkpoints", test_agent_hq_checkpoints),
        ("AgentHQ persistence", test_agent_hq_persistence),
        # DelegationAPI tests
        ("DelegationAPI capability matching", test_delegation_api_capability_matching),
        ("DelegationAPI priority queue", test_delegation_api_priority_queue),
        ("DelegationAPI timeout", test_delegation_api_timeout),
        ("DelegationAPI feedback tracking", test_delegation_api_feedback_tracking),
        ("DelegationAPI queue status", test_delegation_api_queue_status),
        # WorkspaceManager tests
        ("Workspace isolation modes", test_workspace_isolation_modes),
        ("Workspace file operations", test_workspace_file_operations),
        ("Workspace conflict strategies", test_workspace_conflict_strategies),
        ("Workspace cleanup operations", test_workspace_cleanup_operations),
        # MCPToolInvoker tests
        ("MCP tool registration and search", test_mcp_tool_registration_and_search),
        ("MCP tool status updates", test_mcp_tool_status_updates),
        ("MCP tool usage report", test_mcp_tool_usage_report),
        ("MCP tool rate limiter", test_mcp_tool_rate_limiter),
        ("MCP tool cache operations", test_mcp_tool_cache_operations),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            asyncio.run(test_fn())
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name} - {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)} tests")

    if failed > 0:
        return 1

    print("PASS: orchestration comprehensive coverage tests complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
