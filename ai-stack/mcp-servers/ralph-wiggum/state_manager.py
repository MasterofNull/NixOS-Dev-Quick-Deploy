#!/usr/bin/env python3
"""
State Manager
Handles persistence of Ralph loop state for context recovery
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()


class StateManager:
    """
    Manages state persistence for Ralph loops

    Features:
    - Task state snapshots
    - Git integration for code state
    - Context recovery after failures
    - State file versioning
    """

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.state: Dict[str, Any] = self._load_state()

        logger.info("state_manager_initialized", state_file=state_file)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        if not self.state_file.exists():
            return {
                "tasks": {},
                "version": "1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                logger.info("state_loaded", task_count=len(state.get("tasks", {})))
                return state
        except Exception as e:
            logger.error("state_load_error", error=str(e))
            # Backup corrupted state
            backup_file = self.state_file.with_suffix(".backup")
            if self.state_file.exists():
                self.state_file.rename(backup_file)
                logger.info("state_backed_up", backup_file=str(backup_file))

            return {
                "tasks": {},
                "version": "1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }

    def _save_state(self):
        """Save state to file"""
        try:
            self.state["last_updated"] = datetime.utcnow().isoformat()

            # Write to temp file first
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=2)

            # Atomic rename
            temp_file.replace(self.state_file)

            logger.debug("state_saved", task_count=len(self.state.get("tasks", {})))

        except Exception as e:
            logger.error("state_save_error", error=str(e))

    async def save_task_state(self, task: Dict[str, Any]):
        """Save task state"""
        task_id = task["task_id"]

        # Store minimal state (avoid huge payloads)
        task_state = {
            "task_id": task_id,
            "status": task["status"],
            "iteration": task["iteration"],
            "backend": task["backend"],
            "started_at": task["started_at"],
            "last_update": task["last_update"],
            "error": task.get("error"),
            # Store only last 10 results to avoid bloat
            "recent_results": task["results"][-10:] if len(task["results"]) > 10 else task["results"],
            "context_summary": {
                "last_error": task["context"].get("last_error"),
                "last_exception": task["context"].get("last_exception")
            }
        }

        self.state["tasks"][task_id] = task_state
        self._save_state()

        logger.info("task_state_saved", task_id=task_id, iteration=task["iteration"])

    async def load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load task state"""
        return self.state["tasks"].get(task_id)

    async def recover_context(self, task_id: str) -> Dict[str, Any]:
        """
        Recover context for a task

        Returns additional context to help the agent understand previous attempts
        """
        task_state = await self.load_task_state(task_id)

        if not task_state:
            return {}

        # Build recovery context
        context = {
            "recovered": True,
            "previous_iteration": task_state["iteration"],
            "previous_status": task_state["status"],
            "previous_error": task_state.get("error"),
            "lessons_learned": self._extract_lessons(task_state)
        }

        logger.info("context_recovered", task_id=task_id, previous_iteration=task_state["iteration"])

        return context

    def _extract_lessons(self, task_state: Dict[str, Any]) -> list[str]:
        """
        Extract lessons learned from previous iterations

        Analyzes errors and patterns to help guide future attempts
        """
        lessons = []

        # Check for repeated errors
        errors = [r.get("result", {}).get("error") for r in task_state.get("recent_results", []) if r.get("result", {}).get("error")]

        if errors:
            unique_errors = set(errors)
            if len(unique_errors) < len(errors):
                lessons.append(f"Repeated error detected: {list(unique_errors)[0]}")

        # Check for context clues
        context_summary = task_state.get("context_summary", {})
        if context_summary.get("last_error"):
            lessons.append(f"Last known error: {context_summary['last_error']}")

        if context_summary.get("last_exception"):
            lessons.append(f"Last exception: {context_summary['last_exception']}")

        return lessons

    async def get_all_tasks(self) -> Dict[str, Any]:
        """Get all task states"""
        return self.state["tasks"]

    async def cleanup_old_tasks(self, days: int = 7):
        """Clean up old task states"""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        tasks_to_remove = [
            task_id
            for task_id, task in self.state["tasks"].items()
            if task.get("last_update", "") < cutoff_iso
        ]

        for task_id in tasks_to_remove:
            del self.state["tasks"][task_id]

        if tasks_to_remove:
            self._save_state()
            logger.info("old_tasks_cleaned", count=len(tasks_to_remove))

        return len(tasks_to_remove)
