"""
Workflow State Persistence

Handles storage and retrieval of workflow execution state.
Supports multiple backends: JSON files, SQLite, PostgreSQL.

Phase 2.4: Coordinator Integration
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WorkflowStateStore:
    """
    Persistence layer for workflow execution state.

    Stores execution history, state snapshots, and outputs.
    Default backend: JSON files in .workflow-executions/
    """

    def __init__(
        self,
        storage_dir: str = ".workflow-executions",
        backend: str = "json",
    ):
        """
        Initialize state store.

        Args:
            storage_dir: Directory for storing execution state
            backend: Storage backend ("json", "sqlite", "postgres")
        """
        self.storage_dir = Path(storage_dir)
        self.backend = backend

        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Workflow state store initialized (backend={backend}, dir={storage_dir})")

    async def save(self, execution_id: str, state: Dict[str, Any]) -> None:
        """
        Save execution state.

        Args:
            execution_id: Unique execution ID
            state: Execution state dict
        """
        if self.backend == "json":
            await self._save_json(execution_id, state)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    async def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution state.

        Args:
            execution_id: Unique execution ID

        Returns:
            Execution state dict or None if not found
        """
        if self.backend == "json":
            return await self._load_json(execution_id)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    async def list(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        List executions with optional filtering.

        Args:
            workflow_name: Filter by workflow name
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of (execution_id, state) tuples
        """
        if self.backend == "json":
            return await self._list_json(workflow_name, status, limit)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    async def delete(self, execution_id: str) -> bool:
        """
        Delete execution state.

        Args:
            execution_id: Unique execution ID

        Returns:
            True if deleted, False if not found
        """
        if self.backend == "json":
            state_file = self.storage_dir / f"{execution_id}.json"
            if state_file.exists():
                state_file.unlink()
                logger.info(f"Deleted execution state: {execution_id}")
                return True
            return False
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    # JSON backend implementation
    async def _save_json(self, execution_id: str, state: Dict[str, Any]) -> None:
        """Save state to JSON file."""
        state_file = self.storage_dir / f"{execution_id}.json"

        # Serialize workflow object if present
        serialized_state = state.copy()
        if "workflow" in serialized_state and hasattr(serialized_state["workflow"], "to_dict"):
            serialized_state["workflow"] = serialized_state["workflow"].to_dict()

        with open(state_file, "w") as f:
            json.dump(serialized_state, f, indent=2, default=str)

        logger.debug(f"Saved execution state to {state_file}")

    async def _load_json(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load state from JSON file."""
        state_file = self.storage_dir / f"{execution_id}.json"

        if not state_file.exists():
            return None

        with open(state_file, "r") as f:
            state = json.load(f)

        logger.debug(f"Loaded execution state from {state_file}")
        return state

    async def _list_json(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """List executions from JSON files."""
        executions = []

        # Scan all JSON files in storage directory
        for state_file in sorted(self.storage_dir.glob("*.json"), reverse=True):
            if len(executions) >= limit:
                break

            execution_id = state_file.stem
            state = await self._load_json(execution_id)

            if not state:
                continue

            # Apply filters
            if workflow_name:
                workflow = state.get("workflow", {})
                workflow_name_match = (
                    workflow.get("name") == workflow_name
                    if isinstance(workflow, dict)
                    else False
                )
                if not workflow_name_match:
                    continue

            if status and state.get("status") != status:
                continue

            executions.append((execution_id, state))

        return executions


class WorkflowExecutionHistory:
    """
    Track workflow execution history and analytics.

    Provides aggregated views of execution patterns, success rates,
    and performance metrics.
    """

    def __init__(self, state_store: WorkflowStateStore):
        """
        Initialize execution history tracker.

        Args:
            state_store: Workflow state store
        """
        self.state_store = state_store

    async def get_workflow_stats(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific workflow.

        Args:
            workflow_name: Workflow name

        Returns:
            Dict with execution stats (total, success rate, avg duration, etc.)
        """
        executions = await self.state_store.list(workflow_name=workflow_name, limit=1000)

        total_executions = len(executions)
        if total_executions == 0:
            return {
                "workflow": workflow_name,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
            }

        completed = sum(1 for _, state in executions if state["status"] == "completed")
        failed = sum(1 for _, state in executions if state["status"] == "failed")

        # Calculate average duration
        durations = []
        for _, state in executions:
            if state.get("started_at") and state.get("completed_at"):
                try:
                    start = datetime.fromisoformat(state["started_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(state["completed_at"].replace("Z", "+00:00"))
                    duration = (end - start).total_seconds()
                    durations.append(duration)
                except Exception:
                    pass

        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "workflow": workflow_name,
            "total_executions": total_executions,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total_executions if total_executions > 0 else 0.0,
            "avg_duration_seconds": avg_duration,
        }

    async def get_recent_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent executions across all workflows.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List of execution summaries
        """
        executions = await self.state_store.list(limit=limit)

        return [
            {
                "execution_id": exec_id,
                "workflow": state["workflow"]["name"] if isinstance(state["workflow"], dict) else state.get("workflow", {}).get("name", "unknown"),
                "status": state["status"],
                "started_at": state["started_at"],
                "completed_at": state.get("completed_at"),
            }
            for exec_id, state in executions
        ]
