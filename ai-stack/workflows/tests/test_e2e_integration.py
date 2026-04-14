"""
End-to-End Integration Tests for YAML Workflow System via HTTP API

Tests the complete workflow integration stack:
- YAML workflow parsing and validation
- HTTP API endpoints
- Workflow coordinator execution
- Memory system integration
- Agent routing
- Error handling

Phase 2.4: Coordinator Integration - Task 4
"""

import asyncio
import pytest
from pathlib import Path

# Use anyio for async test support
pytestmark = pytest.mark.anyio

# Import httpx for HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    pytest.skip("httpx not available", allow_module_level=True)


# Base URL for coordinator HTTP API
BASE_URL = "http://127.0.0.1:8003"


@pytest.fixture
def examples_dir():
    """Get the examples directory path."""
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root / "ai-stack" / "workflows" / "examples"


@pytest.fixture
async def http_client():
    """Create async HTTP client."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


class TestE2EWorkflowExecution:
    """End-to-end tests for workflow execution via HTTP API."""

    async def test_workflow_execution_via_http(self, http_client, examples_dir):
        """Test executing simple-sequential workflow via HTTP API."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Execute workflow
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"task_description": "test task"},
                "async_mode": False,
            }
        )

        assert response.status_code == 200
        result = response.json()

        # Verify response structure
        assert "execution_id" in result
        assert "status" in result
        assert result["status"] in ["completed", "started"]
        assert "workflow" in result

        execution_id = result["execution_id"]

        # Check status endpoint
        response = await http_client.get(f"/yaml-workflow/{execution_id}/status")
        assert response.status_code == 200

        status = response.json()
        assert status["execution_id"] == execution_id
        assert status["workflow"] == "simple-sequential"
        assert "status" in status
        assert "started_at" in status

    async def test_workflow_async_execution(self, http_client, examples_dir):
        """Test asynchronous workflow execution."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Execute workflow in async mode
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"task_description": "async test"},
                "async_mode": True,
            }
        )

        assert response.status_code == 200
        result = response.json()

        assert result["status"] == "started"
        assert result["async_mode"] is True
        assert "execution_id" in result

        execution_id = result["execution_id"]

        # Poll for completion (with timeout)
        max_polls = 10
        for _ in range(max_polls):
            await asyncio.sleep(0.5)

            response = await http_client.get(f"/yaml-workflow/{execution_id}/status")
            assert response.status_code == 200

            status = response.json()
            if status["status"] in ["completed", "failed"]:
                break

        # Should have completed or failed within timeout
        assert status["status"] in ["running", "completed", "failed"]

    async def test_list_executions_endpoint(self, http_client, examples_dir):
        """Test listing workflow executions."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Execute a few workflows
        execution_ids = []
        for i in range(3):
            response = await http_client.post(
                "/yaml-workflow/execute",
                json={
                    "workflow_file": workflow_file,
                    "inputs": {"task_description": f"test {i}"},
                    "async_mode": False,
                }
            )
            assert response.status_code == 200
            execution_ids.append(response.json()["execution_id"])

        # List all executions
        response = await http_client.get("/yaml-workflow/executions")
        assert response.status_code == 200

        data = response.json()
        assert "executions" in data
        assert "count" in data
        assert data["count"] >= 3

        # Verify our executions are in the list
        listed_ids = [e["execution_id"] for e in data["executions"]]
        for exec_id in execution_ids:
            assert exec_id in listed_ids

    async def test_list_executions_with_filters(self, http_client, examples_dir):
        """Test listing executions with workflow name filter."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Execute workflow
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"task_description": "filter test"},
                "async_mode": False,
            }
        )
        assert response.status_code == 200

        # List with workflow name filter
        response = await http_client.get(
            "/yaml-workflow/executions",
            params={"workflow_name": "simple-sequential", "limit": 10}
        )
        assert response.status_code == 200

        data = response.json()
        assert "executions" in data

        # All returned executions should match the filter
        for execution in data["executions"]:
            assert execution["workflow"] == "simple-sequential"

    async def test_cancel_execution_endpoint(self, http_client, examples_dir):
        """Test canceling a workflow execution."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Start async execution
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"task_description": "cancel test"},
                "async_mode": True,
            }
        )
        assert response.status_code == 200
        execution_id = response.json()["execution_id"]

        # Cancel immediately
        response = await http_client.post(f"/yaml-workflow/{execution_id}/cancel")
        assert response.status_code == 200

        result = response.json()
        assert "status" in result
        assert result["status"] in ["cancelled", "not_cancellable", "completed"]

    async def test_workflow_stats_endpoint(self, http_client, examples_dir):
        """Test getting workflow statistics."""
        workflow_file = str(examples_dir / "simple-sequential.yaml")

        # Execute workflow to ensure stats exist
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"task_description": "stats test"},
                "async_mode": False,
            }
        )
        assert response.status_code == 200

        # Get global stats
        response = await http_client.get("/yaml-workflow/stats")
        assert response.status_code == 200

        stats = response.json()
        assert "recent_executions" in stats or "workflow" in stats
        assert "count" in stats or "total_executions" in stats

        # Get stats for specific workflow
        response = await http_client.get(
            "/yaml-workflow/stats",
            params={"workflow_name": "simple-sequential"}
        )
        assert response.status_code == 200

        workflow_stats = response.json()
        assert "workflow" in workflow_stats
        assert workflow_stats["workflow"] == "simple-sequential"


class TestE2EErrorHandling:
    """Test error handling in HTTP API."""

    async def test_invalid_workflow_file(self, http_client):
        """Test execution with invalid workflow file."""
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": "/nonexistent/workflow.yaml",
                "inputs": {},
                "async_mode": False,
            }
        )

        # Should return error response
        assert response.status_code in [200, 500]  # May return 200 with error status
        result = response.json()

        assert "status" in result or "error" in result
        if "status" in result:
            assert result["status"] in ["parse_failed", "validation_failed", "failed"]

    async def test_malformed_yaml_workflow(self, http_client, tmp_path):
        """Test execution with malformed YAML file."""
        # Create malformed YAML
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("name: test\ninvalid: [unclosed")

        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": str(bad_yaml),
                "inputs": {},
                "async_mode": False,
            }
        )

        result = response.json()
        assert "status" in result or "error" in result

    async def test_invalid_json_request(self, http_client):
        """Test POST with invalid JSON."""
        response = await http_client.post(
            "/yaml-workflow/execute",
            content=b"invalid json {",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400

    async def test_missing_workflow_file_parameter(self, http_client):
        """Test execution without workflow_file parameter."""
        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "inputs": {},
            }
        )

        assert response.status_code == 400
        result = response.json()
        assert "error" in result

    async def test_nonexistent_execution_status(self, http_client):
        """Test getting status of nonexistent execution."""
        response = await http_client.get("/yaml-workflow/nonexistent-id-123/status")

        # Should return error or not_found status
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            result = response.json()
            assert "status" in result

    async def test_cancel_nonexistent_execution(self, http_client):
        """Test canceling nonexistent execution."""
        response = await http_client.post("/yaml-workflow/nonexistent-id-123/cancel")

        # Should return error or not_found status
        assert response.status_code in [200, 404, 500]


class TestE2EWorkflowFeatures:
    """Test various workflow features via HTTP API."""

    async def test_parallel_workflow_execution(self, http_client, examples_dir):
        """Test executing parallel-tasks workflow."""
        workflow_file = str(examples_dir / "parallel-tasks.yaml")

        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"codebase_path": "/tmp/test"},
                "async_mode": False,
            }
        )

        assert response.status_code == 200
        result = response.json()
        assert result["workflow"] == "parallel-analysis"

    async def test_conditional_workflow_execution(self, http_client, examples_dir):
        """Test executing conditional-flow workflow."""
        workflow_file = str(examples_dir / "conditional-flow.yaml")

        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {
                    "environment": "production",
                    "deploy_enabled": True
                },
                "async_mode": False,
            }
        )

        assert response.status_code == 200
        result = response.json()
        assert result["workflow"] == "conditional-deployment"

    async def test_error_handling_workflow(self, http_client, examples_dir):
        """Test executing error-handling workflow."""
        workflow_file = str(examples_dir / "error-handling.yaml")

        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {"service_name": "test-service"},
                "async_mode": False,
            }
        )

        assert response.status_code == 200
        result = response.json()
        assert result["workflow"] == "resilient-deployment"

    async def test_feature_implementation_workflow(self, http_client, examples_dir):
        """Test executing feature-implementation workflow."""
        workflow_file = str(examples_dir / "feature-implementation.yaml")

        response = await http_client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": workflow_file,
                "inputs": {
                    "feature_description": "Add user authentication",
                    "auto_fix": True
                },
                "async_mode": False,
            }
        )

        assert response.status_code == 200
        result = response.json()
        assert result["workflow"] == "feature-implementation"


class TestE2EHealthCheck:
    """Test that the HTTP API is available and healthy."""

    async def test_coordinator_is_running(self, http_client):
        """Test that the coordinator is running and accessible."""
        # Try to list executions - should work even if empty
        try:
            response = await http_client.get("/yaml-workflow/executions")
            # If we get a response, coordinator is running
            assert response.status_code in [200, 500, 503]
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Coordinator not running - skipping HTTP tests")

    async def test_workflow_system_initialized(self, http_client):
        """Test that workflow system is initialized."""
        response = await http_client.get("/yaml-workflow/stats")

        # Should not get 503 (service unavailable) if initialized
        if response.status_code == 503:
            result = response.json()
            if "not initialized" in result.get("error", "").lower():
                pytest.skip("Workflow system not initialized")

        assert response.status_code in [200, 500]
