#!/usr/bin/env python3
"""
Workflow Executor - Execute workflows with DAG orchestration.

This module provides workflow execution capabilities including DAG execution,
parallel task execution, agent dispatch, and telemetry collection.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TaskExecution:
    """Represents a task execution."""
    task_id: str
    execution_id: str
    workflow_execution_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    agent_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: int = 0  # seconds
    retry_count: int = 0
    error_message: Optional[str] = None
    output: Optional[Any] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "workflow_execution_id": self.workflow_execution_id,
            "status": self.status.value,
            "agent_id": self.agent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "output": self.output,
            "telemetry": self.telemetry,
        }


@dataclass
class WorkflowExecution:
    """Represents a workflow execution."""
    execution_id: str
    workflow_id: str
    workflow: Any  # Workflow object
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_duration: int = 0
    task_executions: Dict[str, TaskExecution] = field(default_factory=dict)
    progress: float = 0.0  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration": self.total_duration,
            "task_executions": {
                task_id: execution.to_dict()
                for task_id, execution in self.task_executions.items()
            },
            "progress": self.progress,
            "metadata": self.metadata,
        }


class AgentDispatcher:
    """Dispatches tasks to agents."""

    def __init__(self):
        """Initialize agent dispatcher."""
        # In a real implementation, this would connect to agent pool
        self.available_agents: Dict[str, List[str]] = {
            "orchestrator": ["orchestrator-1"],
            "developer": ["dev-1", "dev-2"],
            "tester": ["test-1"],
            "deployer": ["deploy-1"],
            "monitor": ["monitor-1"],
            "analyst": ["analyst-1"],
            "reviewer": ["review-1"],
            "documenter": ["doc-1"],
        }

    async def dispatch(
        self,
        task: Any,
        task_execution: TaskExecution
    ) -> Any:
        """
        Dispatch task to appropriate agent.

        Args:
            task: Task object
            task_execution: Task execution record

        Returns:
            Task result
        """
        agent_role = task.agent_role.value

        # Get available agent
        agents = self.available_agents.get(agent_role, [])
        if not agents:
            raise ValueError(f"No agents available for role: {agent_role}")

        agent_id = agents[0]  # Simple round-robin (could be more sophisticated)
        task_execution.agent_id = agent_id

        logger.info(f"Dispatching task {task.id} to agent {agent_id}")

        # Simulate task execution
        # In a real implementation, this would call actual agent
        result = await self._simulate_task_execution(task)

        return result

    async def _simulate_task_execution(self, task: Any) -> Dict[str, Any]:
        """Simulate task execution."""
        # Simulate work
        duration = min(task.estimated_duration / 60, 2)  # Max 2 seconds for simulation
        await asyncio.sleep(duration)

        # Simulate result
        return {
            "status": "success",
            "message": f"Completed {task.name}",
            "task_type": task.task_type.value,
        }


class RetryPolicy:
    """Handles task retry logic."""

    def __init__(self, max_retries: int = 3, backoff_multiplier: float = 2.0):
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retries
            backoff_multiplier: Exponential backoff multiplier
        """
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier

    def should_retry(self, execution: TaskExecution) -> bool:
        """Check if task should be retried."""
        return execution.retry_count < self.max_retries

    def get_retry_delay(self, execution: TaskExecution) -> float:
        """Get delay before retry in seconds."""
        return pow(self.backoff_multiplier, execution.retry_count)


class TelemetryCollector:
    """Collects execution telemetry."""

    def __init__(self):
        """Initialize telemetry collector."""
        self.telemetry: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []

    def record_task_start(self, task_execution: TaskExecution):
        """Record task start."""
        self.telemetry.append({
            "event": "task_start",
            "task_id": task_execution.task_id,
            "execution_id": task_execution.execution_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def record_task_end(self, task_execution: TaskExecution):
        """Record task end."""
        self.telemetry.append({
            "event": "task_end",
            "task_id": task_execution.task_id,
            "execution_id": task_execution.execution_id,
            "status": task_execution.status.value,
            "duration": task_execution.duration,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def record_workflow_start(self, workflow_execution: WorkflowExecution):
        """Record workflow start."""
        self.telemetry.append({
            "event": "workflow_start",
            "workflow_id": workflow_execution.workflow_id,
            "execution_id": workflow_execution.execution_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def record_workflow_end(self, workflow_execution: WorkflowExecution):
        """Record workflow end."""
        self.telemetry.append({
            "event": "workflow_end",
            "workflow_id": workflow_execution.workflow_id,
            "execution_id": workflow_execution.execution_id,
            "status": workflow_execution.status.value,
            "duration": workflow_execution.total_duration,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_telemetry(self) -> List[Dict[str, Any]]:
        """Get collected telemetry."""
        return self.telemetry

    def log(
        self,
        execution_id: str,
        task_id: str,
        workflow_execution_id: str,
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Record a log message.

        Args:
            execution_id: Task execution ID
            task_id: Task ID
            workflow_execution_id: Workflow execution ID
            level: Log level (DEBUG, INFO, WARN, ERROR)
            message: Log message
            context: Optional context metadata
        """
        log_entry = {
            "execution_id": execution_id,
            "task_id": task_id,
            "workflow_execution_id": workflow_execution_id,
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
        }
        self.logs.append(log_entry)

    def get_logs(self) -> List[Dict[str, Any]]:
        """Get collected logs."""
        return self.logs


class StateManager:
    """Manages workflow execution state."""

    def __init__(self, state_dir: str = "/tmp/workflow-state"):
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state persistence
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, workflow_execution: WorkflowExecution):
        """Save workflow execution state."""
        state_file = self.state_dir / f"{workflow_execution.execution_id}.json"

        try:
            with open(state_file, 'w') as f:
                json.dump(workflow_execution.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def load_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow execution state."""
        state_file = self.state_dir / f"{execution_id}.json"

        if not state_file.exists():
            return None

        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return None

    def delete_state(self, execution_id: str):
        """Delete workflow execution state."""
        state_file = self.state_dir / f"{execution_id}.json"

        if state_file.exists():
            state_file.unlink()


class WorkflowExecutor:
    """Main workflow executor orchestrator."""

    def __init__(
        self,
        state_dir: str = "/tmp/workflow-state",
        max_parallel_tasks: int = 5,
        default_timeout: int = 3600,  # 1 hour
    ):
        """
        Initialize workflow executor.

        Args:
            state_dir: Directory for state persistence
            max_parallel_tasks: Maximum parallel tasks
            default_timeout: Default task timeout in seconds
        """
        self.agent_dispatcher = AgentDispatcher()
        self.retry_policy = RetryPolicy()
        self.telemetry_collector = TelemetryCollector()
        self.state_manager = StateManager(state_dir)

        self.max_parallel_tasks = max_parallel_tasks
        self.default_timeout = default_timeout

        self.active_executions: Dict[str, WorkflowExecution] = {}

    async def execute(
        self,
        workflow: Any,
        execution_id: Optional[str] = None
    ) -> WorkflowExecution:
        """
        Execute a workflow.

        Args:
            workflow: Workflow object
            execution_id: Optional execution ID (for resuming)

        Returns:
            Workflow execution result
        """
        # Create or resume execution
        if execution_id and execution_id in self.active_executions:
            workflow_execution = self.active_executions[execution_id]
            logger.info(f"Resuming workflow execution {execution_id}")
        else:
            execution_id = execution_id or self._generate_execution_id(workflow.id)
            workflow_execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow=workflow,
            )

            # Create task executions
            for task in workflow.tasks:
                task_execution = TaskExecution(
                    task_id=task.id,
                    execution_id=self._generate_execution_id(task.id),
                    workflow_execution_id=execution_id,
                )
                workflow_execution.task_executions[task.id] = task_execution

            self.active_executions[execution_id] = workflow_execution

        # Start execution
        workflow_execution.status = ExecutionStatus.RUNNING
        workflow_execution.start_time = datetime.utcnow().isoformat()

        self.telemetry_collector.record_workflow_start(workflow_execution)

        try:
            # Execute workflow
            await self._execute_workflow(workflow_execution)

            # Mark as success if all tasks succeeded
            all_success = all(
                execution.status == ExecutionStatus.SUCCESS
                for execution in workflow_execution.task_executions.values()
            )

            if all_success:
                workflow_execution.status = ExecutionStatus.SUCCESS
            else:
                workflow_execution.status = ExecutionStatus.FAILURE

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            workflow_execution.status = ExecutionStatus.FAILURE
            workflow_execution.metadata["error"] = str(e)

        # Finalize
        workflow_execution.end_time = datetime.utcnow().isoformat()
        workflow_execution.total_duration = self._calculate_duration(
            workflow_execution.start_time,
            workflow_execution.end_time
        )
        workflow_execution.progress = 1.0

        self.telemetry_collector.record_workflow_end(workflow_execution)

        # Save final state
        self.state_manager.save_state(workflow_execution)

        # Remove from active executions
        if execution_id in self.active_executions:
            del self.active_executions[execution_id]

        logger.info(
            f"Workflow execution {execution_id} completed with status: "
            f"{workflow_execution.status.value}"
        )

        return workflow_execution

    async def _execute_workflow(self, workflow_execution: WorkflowExecution):
        """Execute workflow tasks in DAG order."""
        workflow = workflow_execution.workflow

        # Get execution order
        batches = workflow.get_execution_order()

        logger.info(f"Executing workflow in {len(batches)} batches")

        completed_tasks = set()

        for i, batch in enumerate(batches):
            logger.info(f"Executing batch {i+1}/{len(batches)} with {len(batch)} tasks")

            # Execute batch in parallel
            tasks_to_execute = []

            for task_id in batch:
                task = next((t for t in workflow.tasks if t.id == task_id), None)
                if not task:
                    continue

                task_execution = workflow_execution.task_executions[task_id]
                tasks_to_execute.append(
                    self._execute_task(task, task_execution)
                )

            # Wait for batch to complete
            await asyncio.gather(*tasks_to_execute)

            # Update progress
            completed_tasks.update(batch)
            workflow_execution.progress = len(completed_tasks) / len(workflow.tasks)

            # Save state after each batch
            self.state_manager.save_state(workflow_execution)

            # Check if any task failed
            for task_id in batch:
                task_execution = workflow_execution.task_executions[task_id]
                if task_execution.status == ExecutionStatus.FAILURE:
                    logger.warning(
                        f"Task {task_id} failed, stopping workflow execution"
                    )
                    return

    async def _execute_task(
        self,
        task: Any,
        task_execution: TaskExecution
    ):
        """Execute a single task with retry logic."""
        while True:
            try:
                # Start execution
                task_execution.status = ExecutionStatus.RUNNING
                task_execution.start_time = datetime.utcnow().isoformat()

                self.telemetry_collector.record_task_start(task_execution)

                # Dispatch to agent
                result = await asyncio.wait_for(
                    self.agent_dispatcher.dispatch(task, task_execution),
                    timeout=self.default_timeout
                )

                # Success
                task_execution.status = ExecutionStatus.SUCCESS
                task_execution.output = result
                break

            except asyncio.TimeoutError:
                logger.error(f"Task {task.id} timed out")
                task_execution.status = ExecutionStatus.TIMEOUT
                task_execution.error_message = "Task execution timed out"

                # Retry if allowed
                if self.retry_policy.should_retry(task_execution):
                    task_execution.retry_count += 1
                    delay = self.retry_policy.get_retry_delay(task_execution)
                    logger.info(
                        f"Retrying task {task.id} (attempt {task_execution.retry_count}) "
                        f"after {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    break

            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                task_execution.status = ExecutionStatus.FAILURE
                task_execution.error_message = str(e)

                # Retry if allowed
                if self.retry_policy.should_retry(task_execution):
                    task_execution.retry_count += 1
                    delay = self.retry_policy.get_retry_delay(task_execution)
                    logger.info(
                        f"Retrying task {task.id} (attempt {task_execution.retry_count}) "
                        f"after {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    break

        # Finalize
        task_execution.end_time = datetime.utcnow().isoformat()
        task_execution.duration = self._calculate_duration(
            task_execution.start_time,
            task_execution.end_time
        )

        self.telemetry_collector.record_task_end(task_execution)

        logger.info(
            f"Task {task.id} completed with status: {task_execution.status.value}"
        )

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID."""
        # Check active executions
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]

        # Try to load from state
        state = self.state_manager.load_state(execution_id)
        if state:
            # Reconstruct execution object (simplified)
            return state

        return None

    def cancel_execution(self, execution_id: str):
        """Cancel a workflow execution."""
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            execution.status = ExecutionStatus.CANCELLED
            logger.info(f"Cancelled workflow execution {execution_id}")

    def get_telemetry(self) -> List[Dict[str, Any]]:
        """Get collected telemetry."""
        return self.telemetry_collector.get_telemetry()

    def _generate_execution_id(self, prefix: str) -> str:
        """Generate execution ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"{prefix}_{timestamp}"

    def _calculate_duration(self, start_time: str, end_time: str) -> int:
        """Calculate duration in seconds."""
        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            return int((end - start).total_seconds())
        except:
            return 0


async def main():
    """Test workflow executor."""
    logging.basicConfig(level=logging.INFO)

    # This would use a real workflow
    print("Workflow executor initialized successfully")


if __name__ == "__main__":
    asyncio.run(main())
