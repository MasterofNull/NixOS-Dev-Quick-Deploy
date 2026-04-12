"""
Tests for workflow executor

Validates that the executor can process workflow sessions.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from workflow_executor import WorkflowExecutor, WorkflowPhaseExecutor

# Enable pytest-asyncio
pytestmark = pytest.mark.anyio


@pytest.fixture
def temp_sessions_file():
    """Create temporary sessions file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        sessions = {
            "test-session-123": {
                "session_id": "test-session-123",
                "objective": "Test objective",
                "status": "in_progress",
                "current_phase_index": 0,
                "budget": {"token_limit": 1000, "tool_call_limit": 10},
                "usage": {"tokens_used": 0, "tool_calls_used": 0},
                "trajectory": [],
                "created_at": 1234567890.0,
                "updated_at": 1234567890.0,
            }
        }
        json.dump(sessions, f)
        path = f.name

    yield path

    # Cleanup
    Path(path).unlink(missing_ok=True)


def test_executor_finds_pending_sessions(temp_sessions_file):
    """Test that executor finds sessions needing execution"""
    async def run_test():
        executor = WorkflowExecutor(sessions_file=temp_sessions_file, poll_interval=0.1)

        sessions = await executor._load_sessions()
        pending = executor._find_pending_sessions(sessions)

        assert len(pending) == 1
        assert "test-session-123" in pending

    asyncio.run(run_test())


def test_executor_processes_session(temp_sessions_file):
    """Test that executor can process a session"""
    async def run_test():
        executor = WorkflowExecutor(sessions_file=temp_sessions_file, poll_interval=0.1)
        executor.use_llm = False

        async def fake_execute_phase(phase, objective, context):
            return {
                "phase_id": phase.get("id", "unknown"),
                "status": "completed",
                "outputs": ["delegated result"],
                "output": "delegated result",
                "events": [{"event_type": "delegated_phase_execution", "phase_id": phase.get("id", "unknown")}],
                "tokens_used": 11,
                "tool_calls_made": 0,
                "summary": "delegated phase execution completed",
            }

        executor.phase_executor.execute_phase = fake_execute_phase

        # Run executor for a short time
        run_task = asyncio.create_task(executor.run())

        # Wait for processing
        await asyncio.sleep(2.0)

        # Stop executor
        executor.stop()
        await run_task

        # Check session was processed
        sessions = await executor._load_sessions()
        session = sessions["test-session-123"]

        assert session["status"] == "completed"
        assert "completed_at" in session
        assert len(session["trajectory"]) > 0
        assert session["usage"]["tokens_used"] == 11
        assert session["result"] == "delegated result"
        assert any(item.get("event_type") == "phase_execution" for item in session["trajectory"])

    asyncio.run(run_test())


def test_executor_respects_budget():
    """Test that executor respects token budget limits"""
    async def run_test():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            sessions = {
                "over-budget": {
                    "session_id": "over-budget",
                    "objective": "Test",
                    "status": "in_progress",
                    "budget": {"token_limit": 100, "tool_call_limit": 10},
                    "usage": {"tokens_used": 150, "tool_calls_used": 0},
                    "trajectory": [],
                }
            }
            json.dump(sessions, f)
            path = f.name

        try:
            executor = WorkflowExecutor(sessions_file=path, poll_interval=0.1)
            sessions = await executor._load_sessions()
            pending = executor._find_pending_sessions(sessions)

            # Should not execute over-budget session
            assert len(pending) == 0

        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(run_test())


def test_executor_handles_errors():
    """Test that executor handles errors gracefully"""
    async def run_test():
        # Create session with invalid data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            sessions = {
                "error-session": {
                    "session_id": "error-session",
                    "objective": "Test",
                    "status": "in_progress",
                    "budget": {"token_limit": 1000},
                    "usage": {"tokens_used": 0},
                    "trajectory": [],
                }
            }
            json.dump(sessions, f)
            path = f.name

        try:
            executor = WorkflowExecutor(sessions_file=path, poll_interval=0.1)

            # Manually trigger execution to test error handling
            session = (await executor._load_sessions())["error-session"]

            # This should handle errors gracefully
            await executor._execute_session("error-session", session)

            # Session should be marked as completed (mock execution succeeds)
            updated_sessions = await executor._load_sessions()
            assert "error-session" in updated_sessions

        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(run_test())


def test_workflow_phase_executor_uses_delegate_helper():
    """WorkflowPhaseExecutor should return delegated output instead of mock placeholders."""
    async def run_test():
        executor = WorkflowPhaseExecutor(coordinator_url="http://127.0.0.1:8003")

        async def fake_delegate(phase, objective, context):
            return {
                "output": "phase delegate output",
                "tokens_used": 7,
                "tool_calls_made": 1,
                "summary": "Delegated phase execution completed",
                "events": [{"event_type": "delegated_phase_execution", "phase_id": phase.get("id", "unknown")}],
            }

        executor._delegate_phase_execution = fake_delegate
        result = await executor.execute_phase(
            {"id": "discover", "title": "Discover"},
            "Investigate current runtime status",
            {"safety_mode": "plan-readonly", "budget": {"token_limit": 128}},
        )

        assert result["status"] == "completed"
        assert result["output"] == "phase delegate output"
        assert result["tokens_used"] == 7
        assert result["tool_calls_made"] == 1
        assert result["outputs"] == ["phase delegate output"]
        assert result["events"][0]["event_type"] == "delegated_phase_execution"

    asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
