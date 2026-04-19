"""Unit tests for workflow store log functionality."""

import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workflows.workflow_store import WorkflowStore


def test_save_log():
    """Test saving a log entry."""
    store = WorkflowStore(":memory:")

    store.save_log(
        execution_id="exec-123",
        task_id="task-1",
        workflow_execution_id="wf-123",
        level="INFO",
        message="Test log message",
        timestamp=datetime.utcnow().isoformat(),
    )

    logs = store.get_task_logs("exec-123")
    assert len(logs) == 1
    assert logs[0]["message"] == "Test log message"
    assert logs[0]["level"] == "INFO"
    assert logs[0]["task_id"] == "task-1"


def test_filter_logs_by_level():
    """Test filtering logs by level."""
    store = WorkflowStore(":memory:")

    # Save logs with different levels
    ts = datetime.utcnow().isoformat()
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Info message", ts)
    store.save_log("exec-123", "task-1", "wf-123", "ERROR", "Error message", ts)
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Another info", ts)

    # Filter by ERROR
    logs = store.get_task_logs("exec-123", level="ERROR")
    assert len(logs) == 1
    assert logs[0]["level"] == "ERROR"
    assert logs[0]["message"] == "Error message"

    # Filter by INFO
    logs = store.get_task_logs("exec-123", level="INFO")
    assert len(logs) == 2


def test_search_logs():
    """Test searching logs."""
    store = WorkflowStore(":memory:")

    ts = datetime.utcnow().isoformat()
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Starting deployment", ts)
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Deployment completed", ts)
    store.save_log("exec-123", "task-1", "wf-123", "ERROR", "Connection failed", ts)

    # Search for "deployment"
    logs = store.get_task_logs("exec-123", search="deployment")
    assert len(logs) == 2
    assert all("deployment" in log["message"].lower() for log in logs)

    # Search for "failed"
    logs = store.get_task_logs("exec-123", search="failed")
    assert len(logs) == 1
    assert "failed" in logs[0]["message"].lower()


def test_pagination():
    """Test log pagination."""
    store = WorkflowStore(":memory:")

    # Create 50 logs
    for i in range(50):
        store.save_log(
            "exec-123",
            "task-1",
            "wf-123",
            "INFO",
            f"Log {i}",
            datetime.utcnow().isoformat()
        )

    # Get first page
    page1 = store.get_task_logs("exec-123", limit=10, offset=0)
    assert len(page1) == 10

    # Get second page
    page2 = store.get_task_logs("exec-123", limit=10, offset=10)
    assert len(page2) == 10
    assert page1[0]["id"] != page2[0]["id"]

    # Get all logs
    all_logs = store.get_task_logs("exec-123", limit=100)
    assert len(all_logs) == 50


def test_count_task_logs():
    """Test counting logs."""
    store = WorkflowStore(":memory:")

    # Create logs
    for i in range(25):
        level = "ERROR" if i % 5 == 0 else "INFO"
        store.save_log(
            "exec-123",
            "task-1",
            "wf-123",
            level,
            f"Log {i}",
            datetime.utcnow().isoformat()
        )

    # Count all logs
    total = store.count_task_logs("exec-123")
    assert total == 25

    # Count ERROR logs
    errors = store.count_task_logs("exec-123", level="ERROR")
    assert errors == 5

    # Count INFO logs
    info = store.count_task_logs("exec-123", level="INFO")
    assert info == 20


def test_log_with_context():
    """Test saving log with context metadata."""
    store = WorkflowStore(":memory:")

    context = {"agent": "qwen", "retry_count": 2, "error_code": "TIMEOUT"}
    store.save_log(
        "exec-123",
        "task-1",
        "wf-123",
        "ERROR",
        "Task failed",
        datetime.utcnow().isoformat(),
        context=context
    )

    logs = store.get_task_logs("exec-123")
    assert len(logs) == 1
    assert logs[0]["context"] == context
    assert logs[0]["context"]["agent"] == "qwen"
    assert logs[0]["context"]["retry_count"] == 2


def test_filter_by_task_id():
    """Test filtering logs by task ID."""
    store = WorkflowStore(":memory:")

    ts = datetime.utcnow().isoformat()
    # Create logs for different tasks
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Task 1 log", ts)
    store.save_log("exec-456", "task-2", "wf-123", "INFO", "Task 2 log", ts)
    store.save_log("exec-789", "task-1", "wf-123", "INFO", "Another task 1 log", ts)

    # Filter by task-1
    logs = store.get_task_logs("wf-123", task_id="task-1")
    assert len(logs) == 2
    assert all(log["task_id"] == "task-1" for log in logs)


def test_combined_filters():
    """Test combining multiple filters."""
    store = WorkflowStore(":memory:")

    ts = datetime.utcnow().isoformat()
    # Create varied logs
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Starting deployment", ts)
    store.save_log("exec-123", "task-1", "wf-123", "ERROR", "Deployment failed", ts)
    store.save_log("exec-123", "task-2", "wf-123", "ERROR", "Connection error", ts)
    store.save_log("exec-123", "task-1", "wf-123", "INFO", "Deployment completed", ts)

    # Filter by task_id and level
    logs = store.get_task_logs("exec-123", task_id="task-1", level="ERROR")
    assert len(logs) == 1
    assert logs[0]["task_id"] == "task-1"
    assert logs[0]["level"] == "ERROR"

    # Filter by level and search
    logs = store.get_task_logs("exec-123", level="ERROR", search="deployment")
    assert len(logs) == 1
    assert "Deployment failed" in logs[0]["message"]


def test_query_by_workflow_execution_id():
    """Test querying logs by workflow execution ID."""
    store = WorkflowStore(":memory:")

    ts = datetime.utcnow().isoformat()
    # Create logs for tasks in the same workflow
    store.save_log("exec-task1", "task-1", "wf-123", "INFO", "Task 1 log", ts)
    store.save_log("exec-task2", "task-2", "wf-123", "INFO", "Task 2 log", ts)
    store.save_log("exec-task3", "task-3", "wf-456", "INFO", "Different workflow", ts)

    # Query by workflow execution ID
    logs = store.get_task_logs("wf-123")
    assert len(logs) == 2
    assert all(log["workflow_execution_id"] == "wf-123" for log in logs)

    # Count by workflow execution ID
    count = store.count_task_logs("wf-123")
    assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
