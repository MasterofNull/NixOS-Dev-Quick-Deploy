#!/usr/bin/env python3
"""
Ralph Loop Hooks
Implements the core hook system for exit blocking and context recovery
"""

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import structlog
from git import Repo

logger = structlog.get_logger()


class Hook:
    """Base hook class"""

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """Execute the hook"""
        raise NotImplementedError


class StopHook(Hook):
    """
    Stop Hook - Blocks agent exit attempts

    This is the core of the Ralph Wiggum technique:
    - Intercepts exit code 2
    - Re-injects the original prompt
    - Forces the loop to continue

    Named after Ralph's persistence despite setbacks
    """

    def __init__(self, loop_engine, exit_code_block: int = 2):
        self.loop_engine = loop_engine
        self.exit_code_block = exit_code_block

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """
        Execute stop hook

        When exit code matches our block code, we:
        1. Log the attempt
        2. Preserve context
        3. Let the loop continue
        """
        exit_code = result.get("exit_code", 0)

        if exit_code == self.exit_code_block:
            logger.info(
                "exit_blocked",
                task_id=task["task_id"],
                iteration=task["iteration"],
                message="I'm helping! (Ralph continues)"
            )

            # Update task context with blocking info
            task["context"]["exit_blocks"] = task["context"].get("exit_blocks", 0) + 1
            task["context"]["last_block_iteration"] = task["iteration"]

            # In Ralph fashion, we don't give up!
            # The loop will continue in the loop_engine


class ContextRecoveryHook(Hook):
    """
    Context Recovery Hook

    Implements deterministic failure recovery:
    - Uses git to track state
    - Saves checkpoints
    - Enables recovery from crashes
    """

    def __init__(self, state_manager, git_integration: bool = True):
        self.state_manager = state_manager
        self.git_integration = git_integration

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """
        Execute context recovery

        Saves state to enable recovery if Ralph crashes
        """
        task_id = task["task_id"]

        logger.info("context_recovery", task_id=task_id, iteration=task["iteration"])

        # Save task state
        await self.state_manager.save_task_state(task)

        # Git checkpoint if enabled
        if self.git_integration:
            await self._create_git_checkpoint(task, result)

    async def _create_git_checkpoint(self, task: Dict[str, Any], result: Dict[str, Any]):
        """
        Create git checkpoint for recovery

        Commits current state with Ralph metadata
        """
        try:
            workspace = Path("/workspace")
            if not workspace.exists():
                return

            # Check if we're in a git repo
            if not (workspace / ".git").exists():
                # Initialize git repo
                repo = Repo.init(workspace)
                logger.info("git_repo_initialized", workspace=str(workspace))
            else:
                repo = Repo(workspace)

            # Check for changes
            if repo.is_dirty(untracked_files=True):
                # Stage all changes
                repo.git.add(A=True)

                # Create checkpoint commit
                commit_message = (
                    f"Ralph checkpoint: Task {task['task_id'][:8]} iteration {task['iteration']}\n\n"
                    f"Status: {task['status']}\n"
                    f"Backend: {task['backend']}\n"
                    f"Exit code: {result.get('exit_code', 'unknown')}\n\n"
                    f"[ralph-wiggum-checkpoint]"
                )

                repo.index.commit(commit_message)

                logger.info(
                    "git_checkpoint_created",
                    task_id=task["task_id"],
                    iteration=task["iteration"]
                )

        except Exception as e:
            logger.warning("git_checkpoint_failed", error=str(e))


class ApprovalHook(Hook):
    """
    Approval Hook

    Implements human-in-the-loop controls:
    - Approval gates before destructive actions
    - Configurable autonomy levels
    - Audit trails
    """

    def __init__(self, approval_threshold: str = "high"):
        self.approval_threshold = approval_threshold
        self.destructive_actions = [
            "delete",
            "drop",
            "rm ",
            "remove",
            "truncate",
            "force push",
            "hard reset"
        ]

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """
        Check if action requires approval

        Based on threshold and action type
        """
        output = result.get("output", "").lower()

        # Check for destructive actions
        is_destructive = any(action in output for action in self.destructive_actions)

        if is_destructive:
            logger.warning(
                "destructive_action_detected",
                task_id=task["task_id"],
                threshold=self.approval_threshold
            )

            if self.approval_threshold in ["medium", "high"]:
                # Request approval
                task["requires_approval"] = True
                task["approval_reason"] = "Destructive action detected"


class TelemetryHook(Hook):
    """
    Telemetry Hook

    Collects metrics for Ralph loop performance
    """

    def __init__(self, telemetry_path: str):
        self.telemetry_path = Path(telemetry_path)
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """Log telemetry data"""
        import json
        from datetime import datetime

        event = {
            "event": "iteration_completed",
            "task_id": task["task_id"],
            "iteration": task["iteration"],
            "backend": task["backend"],
            "exit_code": result.get("exit_code", 0),
            "output_length": len(result.get("output", "")),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        try:
            with open(self.telemetry_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.warning("telemetry_write_failed", error=str(e))


class ResourceLimitHook(Hook):
    """
    Resource Limit Hook

    Prevents runaway loops from consuming excessive resources
    """

    def __init__(self, max_iterations_per_task: int = 100, max_cpu_percent: float = 80.0):
        self.max_iterations_per_task = max_iterations_per_task
        self.max_cpu_percent = max_cpu_percent

    async def execute(self, task: Dict[str, Any], result: Dict[str, Any]):
        """Check resource limits"""
        # Check iteration limit
        if task["iteration"] >= self.max_iterations_per_task:
            logger.warning(
                "iteration_limit_exceeded",
                task_id=task["task_id"],
                iterations=task["iteration"]
            )
            task["status"] = "failed"
            task["error"] = f"Exceeded maximum iterations ({self.max_iterations_per_task})"

        # TODO: Add CPU monitoring if needed
