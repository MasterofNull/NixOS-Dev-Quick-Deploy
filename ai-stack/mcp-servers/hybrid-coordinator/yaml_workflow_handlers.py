"""
HTTP handlers for YAML-based declarative workflows.

Integrates the Phase 2 workflow engine (parser, validator, coordinator)
into the hybrid coordinator's HTTP API.

Phase 2.4: Coordinator Integration
"""

import logging
from typing import Any, Dict

from aiohttp import web

try:
    from workflows import WorkflowCoordinator, WorkflowExecutionHistory
    WORKFLOWS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"YAML workflows not available: {e}")
    WORKFLOWS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global coordinator instance (initialized by init())
_workflow_coordinator: WorkflowCoordinator | None = None
_execution_history: WorkflowExecutionHistory | None = None


def init(workflows_dir: str = "ai-stack/workflows/examples"):
    """
    Initialize YAML workflow system.

    Args:
        workflows_dir: Directory containing workflow YAML files
    """
    global _workflow_coordinator, _execution_history

    if not WORKFLOWS_AVAILABLE:
        logger.warning("YAML workflows not available - skipping initialization")
        return

    try:
        _workflow_coordinator = WorkflowCoordinator()
        _execution_history = WorkflowExecutionHistory(_workflow_coordinator.state_store)
        logger.info(f"YAML workflow system initialized (workflows_dir={workflows_dir})")
    except Exception as e:
        logger.error(f"Failed to initialize YAML workflow system: {e}")


# HTTP Handlers

async def handle_yaml_workflow_execute(request: web.Request) -> web.Response:
    """
    POST /yaml-workflow/execute
    Execute a YAML workflow file.

    Request body:
    {
        "workflow_file": "path/to/workflow.yaml",
        "inputs": {...},
        "async_mode": true|false
    }
    """
    if not _workflow_coordinator:
        return web.json_response(
            {"error": "YAML workflows not initialized"},
            status=503,
        )

    try:
        data = await request.json()
    except Exception as e:
        return web.json_response(
            {"error": f"Invalid JSON: {e}"},
            status=400,
        )

    workflow_file = data.get("workflow_file")
    if not workflow_file:
        return web.json_response(
            {"error": "workflow_file is required"},
            status=400,
        )

    inputs = data.get("inputs", {})
    async_mode = data.get("async_mode", False)

    try:
        result = await _workflow_coordinator.execute_workflow(
            workflow_file=workflow_file,
            inputs=inputs,
            async_mode=async_mode,
        )

        return web.json_response(result)
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Execution failed: {e}"},
            status=500,
        )


async def handle_yaml_workflow_status(request: web.Request) -> web.Response:
    """
    GET /yaml-workflow/{execution_id}/status
    Get status of a workflow execution.
    """
    if not _workflow_coordinator:
        return web.json_response(
            {"error": "YAML workflows not initialized"},
            status=503,
        )

    execution_id = request.match_info.get("execution_id")
    if not execution_id:
        return web.json_response(
            {"error": "execution_id is required"},
            status=400,
        )

    try:
        status = await _workflow_coordinator.get_execution_status(execution_id)
        return web.json_response(status)
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Status check failed: {e}"},
            status=500,
        )


async def handle_yaml_workflow_list(request: web.Request) -> web.Response:
    """
    GET /yaml-workflow/executions
    List workflow executions with optional filtering.

    Query params:
    - workflow_name: Filter by workflow name
    - status: Filter by status
    - limit: Max results (default 50)
    """
    if not _workflow_coordinator:
        return web.json_response(
            {"error": "YAML workflows not initialized"},
            status=503,
        )

    workflow_name = request.query.get("workflow_name")
    status = request.query.get("status")
    try:
        limit = int(request.query.get("limit", "50"))
    except ValueError:
        limit = 50

    try:
        executions = await _workflow_coordinator.list_executions(
            workflow_name=workflow_name,
            status=status,
            limit=limit,
        )

        return web.json_response({
            "executions": executions,
            "count": len(executions),
        })
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        return web.json_response(
            {"error": f"List failed: {e}"},
            status=500,
        )


async def handle_yaml_workflow_cancel(request: web.Request) -> web.Response:
    """
    POST /yaml-workflow/{execution_id}/cancel
    Cancel a running workflow execution.
    """
    if not _workflow_coordinator:
        return web.json_response(
            {"error": "YAML workflows not initialized"},
            status=503,
        )

    execution_id = request.match_info.get("execution_id")
    if not execution_id:
        return web.json_response(
            {"error": "execution_id is required"},
            status=400,
        )

    try:
        result = await _workflow_coordinator.cancel_execution(execution_id)
        return web.json_response(result)
    except Exception as e:
        logger.error(f"Failed to cancel workflow: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Cancel failed: {e}"},
            status=500,
        )


async def handle_yaml_workflow_stats(request: web.Request) -> web.Response:
    """
    GET /yaml-workflow/stats
    Get workflow execution statistics.

    Query params:
    - workflow_name: Get stats for specific workflow
    """
    if not _execution_history:
        return web.json_response(
            {"error": "YAML workflows not initialized"},
            status=503,
        )

    workflow_name = request.query.get("workflow_name")

    try:
        if workflow_name:
            stats = await _execution_history.get_workflow_stats(workflow_name)
        else:
            # Get recent executions summary
            recent = await _execution_history.get_recent_executions(limit=20)
            stats = {
                "recent_executions": recent,
                "count": len(recent),
            }

        return web.json_response(stats)
    except Exception as e:
        logger.error(f"Failed to get workflow stats: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Stats failed: {e}"},
            status=500,
        )


def register_routes(app: web.Application) -> None:
    """Register YAML workflow routes with the web application."""
    if not WORKFLOWS_AVAILABLE:
        logger.warning("YAML workflows not available - skipping route registration")
        return

    app.router.add_post("/yaml-workflow/execute", handle_yaml_workflow_execute)
    app.router.add_get("/yaml-workflow/{execution_id}/status", handle_yaml_workflow_status)
    app.router.add_get("/yaml-workflow/executions", handle_yaml_workflow_list)
    app.router.add_post("/yaml-workflow/{execution_id}/cancel", handle_yaml_workflow_cancel)
    app.router.add_get("/yaml-workflow/stats", handle_yaml_workflow_stats)

    logger.info("YAML workflow routes registered")
