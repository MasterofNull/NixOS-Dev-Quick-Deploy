"""
Tests for Workflow Coordinator

Phase 2.4: Coordinator Integration
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

# Use anyio for async test support (already installed)
pytestmark = pytest.mark.anyio

from ..coordinator import WorkflowCoordinator
from ..persistence import WorkflowStateStore
from ..models import Workflow, WorkflowNode


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def coordinator(temp_storage_dir):
    """Create coordinator with temporary storage."""
    state_store = WorkflowStateStore(storage_dir=temp_storage_dir)
    return WorkflowCoordinator(state_store=state_store)


@pytest.fixture
def sample_workflow_file(tmp_path):
    """Create a sample workflow YAML file."""
    workflow_yaml = """
name: test-workflow
version: 1.0
description: Test workflow for coordinator

inputs:
  test_input:
    type: string
    default: "test value"

agents:
  worker: qwen

nodes:
  - id: task1
    agent: ${agents.worker}
    prompt: "Process: ${inputs.test_input}"
    outputs:
      - result

outputs:
  final_result: ${task1.result}
"""
    workflow_file = tmp_path / "test-workflow.yaml"
    workflow_file.write_text(workflow_yaml)
    return str(workflow_file)


class TestWorkflowCoordinator:
    """Test suite for WorkflowCoordinator."""

    async def test_execute_workflow_sync(self, coordinator, sample_workflow_file):
        """Test synchronous workflow execution."""
        result = await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={"test_input": "hello"},
            async_mode=False,
        )

        assert result["status"] == "completed"
        assert "execution_id" in result
        assert result["workflow"] == "test-workflow"

    @pytest.mark.asyncio
    async def test_execute_workflow_async(self, coordinator, sample_workflow_file):
        """Test asynchronous workflow execution."""
        result = await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={"test_input": "hello"},
            async_mode=True,
        )

        assert result["status"] == "started"
        assert "execution_id" in result
        assert result["async_mode"] is True

        # Wait a bit for async execution
        await asyncio.sleep(2)

        # Check status
        status = await coordinator.get_execution_status(result["execution_id"])
        assert status["status"] in ["running", "completed"]

    @pytest.mark.asyncio
    async def test_execute_invalid_workflow(self, coordinator):
        """Test execution with invalid workflow file."""
        result = await coordinator.execute_workflow(
            workflow_file="/nonexistent/workflow.yaml",
            inputs={},
        )

        assert result["status"] == "parse_failed"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_execution_status(self, coordinator, sample_workflow_file):
        """Test getting execution status."""
        # Execute workflow
        result = await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={},
        )

        execution_id = result["execution_id"]

        # Get status
        status = await coordinator.get_execution_status(execution_id)

        assert status["execution_id"] == execution_id
        assert status["workflow"] == "test-workflow"
        assert "status" in status
        assert "started_at" in status

    @pytest.mark.asyncio
    async def test_get_nonexistent_execution(self, coordinator):
        """Test getting status of nonexistent execution."""
        status = await coordinator.get_execution_status("nonexistent-id")

        assert status["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_executions(self, coordinator, sample_workflow_file):
        """Test listing executions."""
        # Execute multiple workflows
        for i in range(3):
            await coordinator.execute_workflow(
                workflow_file=sample_workflow_file,
                inputs={"test_input": f"test {i}"},
            )

        # List all executions
        executions = await coordinator.list_executions(limit=10)

        assert len(executions) >= 3
        assert all("execution_id" in e for e in executions)
        assert all("workflow" in e for e in executions)
        assert all("status" in e for e in executions)

    @pytest.mark.asyncio
    async def test_list_executions_filtered(self, coordinator, sample_workflow_file):
        """Test listing executions with filters."""
        # Execute workflow
        await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={},
        )

        # List by workflow name
        executions = await coordinator.list_executions(
            workflow_name="test-workflow"
        )

        assert len(executions) >= 1
        assert all(e["workflow"] == "test-workflow" for e in executions)

    @pytest.mark.asyncio
    async def test_cancel_execution(self, coordinator, sample_workflow_file):
        """Test canceling workflow execution."""
        # Start async execution
        result = await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={},
            async_mode=True,
        )

        execution_id = result["execution_id"]

        # Cancel immediately
        cancel_result = await coordinator.cancel_execution(execution_id)

        assert cancel_result["status"] in ["cancelled", "not_cancellable"]
        assert cancel_result["execution_id"] == execution_id

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_execution(self, coordinator):
        """Test canceling nonexistent execution."""
        result = await coordinator.cancel_execution("nonexistent-id")

        assert result["status"] == "not_found"


class TestWorkflowPersistence:
    """Test suite for workflow persistence."""

    @pytest.mark.asyncio
    async def test_state_persistence(self, coordinator, sample_workflow_file):
        """Test that execution state is persisted."""
        # Execute workflow
        result = await coordinator.execute_workflow(
            workflow_file=sample_workflow_file,
            inputs={"test_input": "persist_test"},
        )

        execution_id = result["execution_id"]

        # Create new coordinator instance (simulating restart)
        new_coordinator = WorkflowCoordinator(
            state_store=coordinator.state_store
        )

        # Load execution from persistence
        status = await new_coordinator.get_execution_status(execution_id)

        assert status["execution_id"] == execution_id
        assert status["workflow"] == "test-workflow"
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execution_history(self, coordinator, sample_workflow_file, temp_storage_dir):
        """Test execution history tracking."""
        from ..persistence import WorkflowExecutionHistory

        # Execute multiple workflows
        for i in range(5):
            await coordinator.execute_workflow(
                workflow_file=sample_workflow_file,
                inputs={},
            )

        # Get execution history
        history = WorkflowExecutionHistory(coordinator.state_store)
        recent = await history.get_recent_executions(limit=10)

        assert len(recent) >= 5

        # Get workflow stats
        stats = await history.get_workflow_stats("test-workflow")

        assert stats["workflow"] == "test-workflow"
        assert stats["total_executions"] >= 5
        assert stats["completed"] >= 5
