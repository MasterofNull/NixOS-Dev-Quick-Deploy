#!/usr/bin/env python3
"""
Ralph Loop Engine
Implements the core while-true loop for continuous agent iteration

The Ralph Wiggum technique philosophy:
- "I'm a software engineer!" - Keep trying despite failures
- Simple bash loop: while true; iterate on task; done
- Block exit codes to prevent premature stopping
- Learn from each iteration to improve next attempt
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class RalphLoopEngine:
    """
    Core engine for Ralph Wiggum autonomous loops

    Implements:
    - Continuous task iteration
    - Exit code blocking (default: exit code 2)
    - Context recovery from state files
    - Human-in-the-loop approval gates
    - Telemetry and audit logging
    """

    def __init__(self, orchestrator, state_manager, config: Dict[str, Any]):
        self.orchestrator = orchestrator
        self.state_manager = state_manager
        self.config = config

        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.hooks: Dict[str, List[Callable]] = {}
        self.is_running = False
        self.telemetry_file = open(config["telemetry_path"], "a")

        logger.info("loop_engine_initialized", config=config)

    async def submit_task(
        self,
        prompt: str,
        backend: str,
        max_iterations: int = 0,
        require_approval: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit a new task to the Ralph loop

        Args:
            prompt: Task description to iterate on
            backend: Agent backend to use (aider, continue, goose, etc.)
            max_iterations: Maximum iterations (0 = infinite)
            require_approval: Whether to require human approval
            context: Additional context for the task

        Returns:
            task_id: Unique identifier for the task
        """
        task_id = str(uuid.uuid4())

        task = {
            "task_id": task_id,
            "prompt": prompt,
            "backend": backend,
            "max_iterations": max_iterations,
            "require_approval": require_approval,
            "context": context or {},
            "status": "queued",
            "iteration": 0,
            "started_at": datetime.utcnow().isoformat(),
            "last_update": datetime.utcnow().isoformat(),
            "results": [],
            "error": None,
            "awaiting_approval": False
        }

        self.tasks[task_id] = task
        await self.task_queue.put(task_id)

        self._log_telemetry({
            "event": "task_submitted",
            "task_id": task_id,
            "backend": backend,
            "prompt_length": len(prompt),
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info("task_submitted", task_id=task_id, backend=backend)

        return task_id

    async def run(self):
        """
        Main loop processor

        Continuously processes tasks from the queue
        """
        self.is_running = True
        logger.info("loop_engine_started")

        try:
            while self.is_running:
                try:
                    # Get next task from queue (with timeout to allow checking is_running)
                    task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                task = self.tasks.get(task_id)
                if not task:
                    logger.warning("task_not_found", task_id=task_id)
                    continue

                # Process the task with Ralph loop
                await self._process_task_with_ralph_loop(task)

        except asyncio.CancelledError:
            logger.info("loop_engine_cancelled")
        except Exception as e:
            logger.error("loop_engine_error", error=str(e))
        finally:
            self.is_running = False
            logger.info("loop_engine_stopped")

    async def _process_task_with_ralph_loop(self, task: Dict[str, Any]):
        """
        Process a single task with the Ralph loop technique

        This implements the core while-true loop:
        1. Execute agent on task
        2. Check exit code
        3. If exit code == 2 (blocked), re-inject prompt and continue
        4. If exit code == 0 (success) and meets completion criteria, exit
        5. Otherwise, learn from iteration and continue
        """
        task_id = task["task_id"]
        max_iterations = task["max_iterations"]

        logger.info("ralph_loop_started", task_id=task_id, max_iterations=max_iterations)

        task["status"] = "running"

        iteration = 0
        while True:
            iteration += 1
            task["iteration"] = iteration
            task["last_update"] = datetime.utcnow().isoformat()

            logger.info("ralph_iteration", task_id=task_id, iteration=iteration)

            # Check if we've hit max iterations (if set)
            if max_iterations > 0 and iteration > max_iterations:
                logger.info("ralph_max_iterations_reached", task_id=task_id, iterations=iteration)
                task["status"] = "completed"
                task["completion_reason"] = "max_iterations"
                break

            # Human approval gate
            if task["require_approval"] and iteration > 1:
                await self._request_approval(task)
                if not task.get("approved", False):
                    logger.info("ralph_task_rejected", task_id=task_id)
                    task["status"] = "rejected"
                    break

            # Execute the agent
            try:
                result = await self.orchestrator.execute_agent(
                    backend=task["backend"],
                    prompt=task["prompt"],
                    context=task["context"],
                    iteration=iteration
                )

                task["results"].append({
                    "iteration": iteration,
                    "timestamp": datetime.utcnow().isoformat(),
                    "result": result
                })

                # Log telemetry
                self._log_telemetry({
                    "event": "iteration_completed",
                    "task_id": task_id,
                    "iteration": iteration,
                    "backend": task["backend"],
                    "exit_code": result.get("exit_code", 0),
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Check exit code
                exit_code = result.get("exit_code", 0)

                if exit_code == self.config["exit_code_block"]:
                    # Exit blocked - this is the Ralph loop magic!
                    # Re-inject the prompt and continue
                    logger.info("ralph_exit_blocked", task_id=task_id, iteration=iteration)

                    # Run stop hook
                    await self._run_hooks("stop", task, result)

                    # Context recovery
                    if self.config["context_recovery"]:
                        await self._run_hooks("recovery", task, result)

                    # Continue to next iteration
                    continue

                elif exit_code == 0:
                    # Success - check if task is actually complete
                    if self._is_task_complete(task, result):
                        logger.info("ralph_task_completed", task_id=task_id, iterations=iteration)
                        task["status"] = "completed"
                        task["completion_reason"] = "success"
                        break
                    else:
                        # Success but not complete - continue iterating
                        logger.info("ralph_partial_progress", task_id=task_id, iteration=iteration)
                        continue

                else:
                    # Other exit code - treat as error but continue (Ralph way!)
                    logger.warning("ralph_iteration_error", task_id=task_id, exit_code=exit_code)
                    # Learn from the error and try again
                    task["context"]["last_error"] = result.get("error", f"Exit code {exit_code}")
                    continue

            except Exception as e:
                logger.error("ralph_iteration_exception", task_id=task_id, error=str(e))
                task["error"] = str(e)

                # In true Ralph fashion, even exceptions don't stop us
                # Learn from the error and try again
                task["context"]["last_exception"] = str(e)
                continue

        # Save final state
        await self.state_manager.save_task_state(task)

        self._log_telemetry({
            "event": "task_completed",
            "task_id": task_id,
            "status": task["status"],
            "total_iterations": iteration,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _is_task_complete(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Determine if task is actually complete

        Uses heuristics:
        - No errors in last 3 iterations
        - Agent reports completion
        - No pending TODOs in output
        - Tests passing (if applicable)
        """
        # Check if agent explicitly reports completion
        if result.get("completed", False):
            return True

        # Check recent iteration history
        recent_results = task["results"][-3:] if len(task["results"]) >= 3 else task["results"]

        # All recent iterations successful
        all_successful = all(r.get("result", {}).get("exit_code", 1) == 0 for r in recent_results)

        # No TODOs or errors in output
        output = result.get("output", "")
        no_todos = "TODO" not in output.upper() and "FIXME" not in output.upper()
        no_errors = "ERROR" not in output.upper() and "FAILED" not in output.upper()

        return all_successful and no_todos and no_errors

    async def _request_approval(self, task: Dict[str, Any]):
        """Request human approval to continue"""
        task["awaiting_approval"] = True
        logger.info("approval_requested", task_id=task["task_id"])

        # Wait for approval (with timeout)
        timeout = 300  # 5 minutes
        start = asyncio.get_event_loop().time()

        while task["awaiting_approval"]:
            if asyncio.get_event_loop().time() - start > timeout:
                logger.warning("approval_timeout", task_id=task["task_id"])
                task["approved"] = False
                task["awaiting_approval"] = False
                break

            await asyncio.sleep(1)

    async def _run_hooks(self, hook_type: str, task: Dict[str, Any], result: Dict[str, Any]):
        """Run registered hooks"""
        hooks = self.hooks.get(hook_type, [])
        for hook in hooks:
            try:
                await hook.execute(task, result)
            except Exception as e:
                logger.error("hook_error", hook_type=hook_type, error=str(e))

    def add_hook(self, hook_type: str, hook: Callable):
        """Add a hook"""
        if hook_type not in self.hooks:
            self.hooks[hook_type] = []
        self.hooks[hook_type].append(hook)

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        return self.tasks.get(task_id)

    async def stop_task(self, task_id: str) -> bool:
        """Stop a running task"""
        task = self.tasks.get(task_id)
        if not task or task["status"] not in ["running", "queued"]:
            return False

        task["status"] = "stopped"
        task["stopped_at"] = datetime.utcnow().isoformat()
        logger.info("task_stopped", task_id=task_id)

        return True

    async def approve_task(self, task_id: str, approved: bool) -> bool:
        """Approve or reject a task"""
        task = self.tasks.get(task_id)
        if not task or not task.get("awaiting_approval", False):
            return False

        task["approved"] = approved
        task["awaiting_approval"] = False
        logger.info("task_approval", task_id=task_id, approved=approved)

        return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        total_tasks = len(self.tasks)
        running = sum(1 for t in self.tasks.values() if t["status"] == "running")
        completed = sum(1 for t in self.tasks.values() if t["status"] == "completed")
        failed = sum(1 for t in self.tasks.values() if t["status"] == "failed")

        total_iterations = sum(t["iteration"] for t in self.tasks.values())

        return {
            "total_tasks": total_tasks,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total_iterations": total_iterations,
            "average_iterations": total_iterations / total_tasks if total_tasks > 0 else 0
        }

    @property
    def active_task_count(self) -> int:
        """Get count of active tasks"""
        return sum(1 for t in self.tasks.values() if t["status"] == "running")

    def _log_telemetry(self, event: Dict[str, Any]):
        """Log telemetry event"""
        if self.config["audit_log"]:
            self.telemetry_file.write(json.dumps(event) + "\n")
            self.telemetry_file.flush()

    async def shutdown(self):
        """Shutdown the engine"""
        self.is_running = False
        self.telemetry_file.close()
        logger.info("loop_engine_shutdown")
