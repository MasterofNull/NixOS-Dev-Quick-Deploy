"""
Workflow Coordinator - Bridge between YAML workflow engine and harness coordinator

This module integrates the declarative YAML workflow engine (parser, validator, executor)
with the existing harness infrastructure (agent routing, memory system, persistence).

Phase 2.4: Coordinator Integration
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import Workflow
from .parser import WorkflowParser
from .validator import WorkflowValidator, ValidationError
from .persistence import WorkflowStateStore
from .graph import DependencyGraph
from .node_dispatcher import WorkflowNodeDispatcher, _write_event as _emit_telemetry

logger = logging.getLogger(__name__)


class WorkflowCoordinator:
    """
    Main coordinator for YAML workflow execution.

    Bridges the declarative workflow engine with the harness infrastructure:
    - Parses and validates YAML workflow definitions
    - Coordinates multi-agent task execution
    - Integrates with memory system (L0-L3 loading)
    - Manages execution state and persistence
    - Provides APIs for dashboard monitoring
    """

    def __init__(
        self,
        parser: Optional[WorkflowParser] = None,
        validator: Optional[WorkflowValidator] = None,
        state_store: Optional[WorkflowStateStore] = None,
    ):
        """
        Initialize workflow coordinator.

        Args:
            parser: YAML workflow parser (defaults to WorkflowParser)
            validator: Workflow validator (defaults to WorkflowValidator)
            state_store: Execution state persistence (defaults to WorkflowStateStore)
        """
        self.parser = parser or WorkflowParser()
        self.validator = validator or WorkflowValidator()
        self.state_store = state_store or WorkflowStateStore()

        # Track active executions in memory
        self.active_executions: Dict[str, Dict[str, Any]] = {}

    def _coerce_workflow(self, workflow_data: Any) -> Workflow:
        """Normalize workflow object or serialized dict into a Workflow."""
        if isinstance(workflow_data, Workflow):
            return workflow_data
        if isinstance(workflow_data, dict):
            return Workflow.from_dict(workflow_data)
        raise ValueError("Workflow data is missing or not deserializable")

    async def execute_workflow(
        self,
        workflow_file: str,
        inputs: Dict[str, Any],
        async_mode: bool = False,
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a YAML workflow from file.

        Args:
            workflow_file: Path to workflow YAML file
            inputs: Input parameters for the workflow
            async_mode: Run in background if True
            execution_id: Optional execution ID (auto-generated if not provided)

        Returns:
            Execution result dict with status, execution_id, and outputs
        """
        # Parse workflow YAML
        try:
            workflow = self.parser.parse_file(workflow_file)
        except Exception as e:
            logger.error(f"Failed to parse workflow {workflow_file}: {e}")
            return {
                "status": "parse_failed",
                "error": str(e),
                "workflow_file": workflow_file,
            }

        # Validate workflow
        errors = self.validator.validate_all(workflow)
        if errors:
            error_messages = [e.message for e in errors]
            logger.error(f"Workflow validation failed: {error_messages}")
            return {
                "status": "validation_failed",
                "errors": error_messages,
                "workflow": workflow.name,
            }

        # Generate execution ID
        if not execution_id:
            execution_id = str(uuid4())

        # Create execution state
        execution_state = {
            "execution_id": execution_id,
            "workflow": workflow,
            "inputs": inputs,
            "status": "pending",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "outputs": {},
            "error": None,
        }

        # Store initial state
        self.active_executions[execution_id] = execution_state
        await self.state_store.save(execution_id, execution_state)

        # Execute workflow
        if async_mode:
            # Start background execution in a dedicated thread so async mode
            # works under both asyncio and anyio/trio test backends.
            threading.Thread(
                target=lambda: asyncio.run(self._execute_async(execution_id, workflow, inputs)),
                daemon=True,
                name=f"workflow-{execution_id[:8]}",
            ).start()
            return {
                "status": "started",
                "execution_id": execution_id,
                "workflow": workflow.name,
                "async_mode": True,
            }
        else:
            # Execute synchronously
            result = await self._execute_sync(execution_id, workflow, inputs)
            return result

    async def _execute_sync(
        self, execution_id: str, workflow: Workflow, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow synchronously and return result."""
        try:
            logger.info("Executing workflow %s (sync mode, execution_id=%s)", workflow.name, execution_id)
            execution_state = self.active_executions[execution_id]
            execution_state["status"] = "running"
            await self.state_store.save(execution_id, execution_state)

            _emit_telemetry(
                "workflow_started", execution_id,
                workflow=workflow.name, node_count=len(workflow.nodes),
            )

            graph = DependencyGraph(workflow)
            batches = graph.get_parallel_batches()
            dispatcher = WorkflowNodeDispatcher(
                execution_id=execution_id,
                coordinator_url=os.getenv("COORDINATOR_URL", "http://127.0.0.1:8003"),
            )
            node_outputs: Dict[str, Any] = dict(inputs)
            failed_nodes: List[str] = []

            for batch_index, batch in enumerate(batches):
                batch_id = f"{execution_id[:8]}-b{batch_index}"
                results = await dispatcher.dispatch_batch(batch, node_outputs, batch_id)
                for node_id, result in results.items():
                    if result.get("status") == "failed":
                        failed_nodes.append(node_id)
                    node_outputs[node_id] = result.get("output", "")

            aggregated = self._aggregate_results(workflow, node_outputs)
            _emit_telemetry(
                "workflow_aggregated", execution_id,
                workflow=workflow.name, node_count=len(workflow.nodes),
                failed_count=len(failed_nodes),
                parallel_speedup_ratio=dispatcher.speedup_ratio(),
            )

            execution_state["status"] = "completed"
            execution_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            execution_state["outputs"] = aggregated
            await self.state_store.save(execution_id, execution_state)

            return {
                "status": "completed",
                "execution_id": execution_id,
                "workflow": workflow.name,
                "outputs": aggregated,
            }
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            execution_state = self.active_executions[execution_id]
            execution_state["status"] = "failed"
            execution_state["error"] = str(e)
            execution_state["completed_at"] = datetime.now(timezone.utc).isoformat()

            await self.state_store.save(execution_id, execution_state)

            return {
                "status": "failed",
                "execution_id": execution_id,
                "workflow": workflow.name,
                "error": str(e),
            }

    async def _execute_async(
        self, execution_id: str, workflow: Workflow, inputs: Dict[str, Any]
    ) -> None:
        """Execute workflow in background (called from a daemon thread via asyncio.run)."""
        try:
            result = await self._execute_sync(execution_id, workflow, inputs)
            if result.get("status") == "failed":
                raise RuntimeError(result.get("error", "workflow failed"))
        except Exception as e:
            logger.error(f"Async workflow execution failed: {e}")
            execution_state = self.active_executions.get(execution_id)
            if execution_state:
                execution_state["status"] = "failed"
                execution_state["error"] = str(e)
                execution_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                await self.state_store.save(execution_id, execution_state)

    @staticmethod
    def _aggregate_results(workflow: Workflow, node_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge per-node outputs into a final result dict.

        Terminal nodes (not depended-upon by any other node) are the primary outputs.
        """
        all_dependencies = {dep for node in workflow.nodes for dep in (node.depends_on or [])}
        terminal_ids = [n.id for n in workflow.nodes if n.id not in all_dependencies]
        return {
            "terminal_outputs": {nid: node_outputs.get(nid, "") for nid in terminal_ids},
            "all_outputs": node_outputs,
            "node_count": len(workflow.nodes),
        }

    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get status of a workflow execution.

        Args:
            execution_id: Execution ID

        Returns:
            Dict with execution status, outputs, and metadata
        """
        # Check active executions first
        if execution_id in self.active_executions:
            state = self.active_executions[execution_id]
            return {
                "status": state["status"],
                "execution_id": execution_id,
                "workflow": state["workflow"].name,
                "started_at": state["started_at"],
                "completed_at": state["completed_at"],
                "outputs": state.get("outputs"),
                "error": state.get("error"),
            }

        # Load from persistence
        state = await self.state_store.load(execution_id)
        if not state:
            return {
                "status": "not_found",
                "execution_id": execution_id,
            }

        return {
            "status": state["status"],
            "execution_id": execution_id,
            "workflow": state["workflow"]["name"] if isinstance(state["workflow"], dict) else state["workflow"].name,
            "started_at": state["started_at"],
            "completed_at": state["completed_at"],
            "outputs": state.get("outputs"),
            "error": state.get("error"),
        }

    async def get_workflow_graph(self, workflow_file: str) -> Dict[str, Any]:
        """
        Get graph payload for a workflow definition file.

        Args:
            workflow_file: Path to workflow YAML file

        Returns:
            Graph export payload with Mermaid and normalized nodes/edges
        """
        workflow = self.parser.parse_file(workflow_file)
        graph = DependencyGraph(workflow)
        return {
            "workflow_file": workflow_file,
            "workflow_name": workflow.name,
            "mermaid": graph.to_mermaid(),
            "graph": graph.to_visualization_payload(),
        }

    async def get_execution_graph(self, execution_id: str) -> Dict[str, Any]:
        """
        Get graph payload for a persisted workflow execution.

        Args:
            execution_id: Execution ID

        Returns:
            Graph export payload enriched with execution-level status
        """
        execution_state = self.active_executions.get(execution_id)
        if not execution_state:
            execution_state = await self.state_store.load(execution_id)
        if not execution_state:
            return {
                "status": "not_found",
                "execution_id": execution_id,
            }

        workflow = self._coerce_workflow(execution_state.get("workflow"))
        graph = DependencyGraph(workflow)
        execution_status = str(execution_state.get("status") or "pending")
        node_statuses = {
            node.id: {"status": execution_status}
            for node in workflow.nodes
        }

        return {
            "execution_id": execution_id,
            "workflow_name": workflow.name,
            "execution_status": execution_status,
            "mermaid": graph.to_mermaid(),
            "graph": graph.to_visualization_payload(node_statuses),
        }

    async def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List workflow executions with optional filtering.

        Args:
            workflow_name: Filter by workflow name
            status: Filter by status (pending, running, completed, failed)
            limit: Maximum number of executions to return

        Returns:
            List of execution summaries
        """
        executions = await self.state_store.list(
            workflow_name=workflow_name,
            status=status,
            limit=limit,
        )

        return [
            {
                "execution_id": exec_id,
                "workflow": exec_data["workflow"]["name"] if isinstance(exec_data["workflow"], dict) else exec_data["workflow"].name,
                "status": exec_data["status"],
                "started_at": exec_data["started_at"],
                "completed_at": exec_data.get("completed_at"),
            }
            for exec_id, exec_data in executions
        ]

    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Cancel a running workflow execution.

        Args:
            execution_id: Execution ID to cancel

        Returns:
            Dict with cancellation result
        """
        execution_state = self.active_executions.get(execution_id)
        if not execution_state:
            # Try loading from persistence
            execution_state = await self.state_store.load(execution_id)
            if not execution_state:
                return {
                    "status": "not_found",
                    "execution_id": execution_id,
                }

        if execution_state["status"] not in ["pending", "running"]:
            return {
                "status": "not_cancellable",
                "execution_id": execution_id,
                "current_status": execution_state["status"],
            }

        # Update state to cancelled
        execution_state["status"] = "cancelled"
        execution_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        await self.state_store.save(execution_id, execution_state)

        if execution_id in self.active_executions:
            del self.active_executions[execution_id]

        return {
            "status": "cancelled",
            "execution_id": execution_id,
        }
