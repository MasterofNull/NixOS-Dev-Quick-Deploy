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
import fcntl
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger()
SENSITIVE_FIELD_TOKENS = (
    "prompt",
    "query",
    "response",
    "message",
    "text",
    "input",
    "output",
    "original_response",
    "augmented_prompt",
)


class RalphLoopEngine:
    """
    Core engine for Ralph Wiggum autonomous loops

    Implements:
    - Continuous task iteration
    - Exit code blocking (default: exit code 2)
    - Context recovery from state files
    - Human-in-the-loop approval gates
    - Telemetry and audit logging
    - Adaptive iteration limits (Phase 4)
    - Per-task timeout (Phase 13.2.3)
    - Periodic state persistence (Phase 13.2.5)
    """

    # Complexity keywords for prompt analysis
    COMPLEXITY_KEYWORDS = {
        "simple": ["fix typo", "add comment", "rename", "update version", "format"],
        "moderate": ["add function", "implement", "create", "update", "modify", "test"],
        "complex": ["refactor", "redesign", "migrate", "optimize", "architecture", "integration"],
        "very_complex": ["rewrite", "overhaul", "security audit", "performance tuning", "distributed"]
    }

    # Base iteration limits per complexity level
    BASE_ITERATION_LIMITS = {
        "simple": 3,
        "moderate": 10,
        "complex": 25,
        "very_complex": 50
    }

    def __init__(self, orchestrator, state_manager, config: Dict[str, Any]):
        self.orchestrator = orchestrator
        self.state_manager = state_manager
        self.config = config

        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.hooks: Dict[str, List[Callable]] = {}
        self.is_running = False
        self.telemetry_file = open(config["telemetry_path"], "a") if config.get("audit_log") else None

        # Per-task timeout in seconds (Phase 13.2.3); 0 = no timeout
        self.task_timeout_seconds: int = config.get("task_timeout_seconds", 3600)

        # How often to persist state during iteration (Phase 13.2.5)
        self.state_save_interval: int = config.get("state_save_interval", 5)

        # Adaptive iteration tracking (Phase 4)
        self.task_history: Dict[str, List[Dict[str, Any]]] = {}  # task_type -> [results]
        self.adaptive_enabled = config.get("adaptive_iterations", True)

        logger.info(
            "loop_engine_initialized",
            config=config,
            adaptive_enabled=self.adaptive_enabled,
            task_timeout=self.task_timeout_seconds,
        )

    async def submit_task(
        self,
        prompt: str,
        backend: str,
        max_iterations: int = -1,  # -1 = use adaptive, 0 = infinite, >0 = fixed
        require_approval: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit a new task to the Ralph loop

        Args:
            prompt: Task description to iterate on
            backend: Agent backend to use (aider, continue, goose, etc.)
            max_iterations: Maximum iterations (-1 = adaptive, 0 = infinite, >0 = fixed)
            require_approval: Whether to require human approval
            context: Additional context for the task

        Returns:
            task_id: Unique identifier for the task
        """
        task_id = str(uuid.uuid4())

        # Calculate iteration limit (Phase 4: Adaptive)
        if max_iterations == -1:
            # Use adaptive calculation
            effective_max_iterations = self.calculate_adaptive_limit(prompt, backend)
            iteration_mode = "adaptive"
        elif max_iterations == 0:
            # Infinite mode
            effective_max_iterations = 0
            iteration_mode = "infinite"
        else:
            # Fixed limit
            effective_max_iterations = max_iterations
            iteration_mode = "fixed"

        task = {
            "task_id": task_id,
            "prompt": prompt,
            "backend": backend,
            "max_iterations": effective_max_iterations,
            "iteration_mode": iteration_mode,
            "original_max_iterations": max_iterations,
            "require_approval": require_approval,
            "context": context or {},
            "status": "queued",
            "iteration": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_update": datetime.now(timezone.utc).isoformat(),
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        logger.info("task_submitted", task_id=task_id, backend=backend)

        return task_id

    def calculate_adaptive_limit(self, prompt: str, backend: str) -> int:
        """
        Calculate adaptive iteration limit based on task complexity and history

        Phase 4: Adaptive Iteration Logic

        Args:
            prompt: The task prompt to analyze
            backend: The agent backend being used

        Returns:
            Recommended iteration limit
        """
        if not self.adaptive_enabled:
            return self.config.get("default_iterations", 10)

        # Step 1: Analyze prompt complexity
        complexity = self._analyze_prompt_complexity(prompt)
        base_limit = self.BASE_ITERATION_LIMITS.get(complexity, 10)

        # Step 2: Adjust based on historical success rate
        task_type = self._extract_task_type(prompt)
        history_adjustment = self._get_history_adjustment(task_type, backend)

        # Step 3: Calculate final limit
        adjusted_limit = int(base_limit * history_adjustment)

        # Ensure within bounds
        min_limit = self.config.get("min_iterations", 1)
        max_limit = self.config.get("max_iterations_cap", 100)
        final_limit = max(min_limit, min(adjusted_limit, max_limit))

        # Log the adaptive decision
        self._log_telemetry({
            "event": "adaptive_limit_calculated",
            "prompt_preview": prompt[:100],
            "complexity": complexity,
            "base_limit": base_limit,
            "history_adjustment": history_adjustment,
            "final_limit": final_limit,
            "task_type": task_type,
            "backend": backend,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        logger.info(
            "adaptive_limit_calculated",
            complexity=complexity,
            base_limit=base_limit,
            adjustment=history_adjustment,
            final_limit=final_limit
        )

        return final_limit

    def _analyze_prompt_complexity(self, prompt: str) -> str:
        """
        Analyze prompt to determine task complexity

        Returns: 'simple', 'moderate', 'complex', or 'very_complex'
        """
        prompt_lower = prompt.lower()

        # Count matches for each complexity level
        scores = {}
        for level, keywords in self.COMPLEXITY_KEYWORDS.items():
            scores[level] = sum(1 for kw in keywords if kw in prompt_lower)

        # Also consider prompt length as a factor
        word_count = len(prompt.split())
        if word_count > 500:
            scores["very_complex"] = scores.get("very_complex", 0) + 2
        elif word_count > 200:
            scores["complex"] = scores.get("complex", 0) + 1
        elif word_count < 50:
            scores["simple"] = scores.get("simple", 0) + 1

        # Find highest scoring complexity
        if not any(scores.values()):
            return "moderate"  # Default

        return max(scores.keys(), key=lambda k: scores[k])

    def _extract_task_type(self, prompt: str) -> str:
        """
        Extract a normalized task type from the prompt for history tracking

        Returns a category like: 'refactor', 'implement', 'fix', 'test', etc.
        """
        prompt_lower = prompt.lower()

        task_types = [
            "refactor", "implement", "fix", "test", "add", "update",
            "remove", "optimize", "migrate", "document", "review"
        ]

        for task_type in task_types:
            if task_type in prompt_lower:
                return task_type

        return "general"

    def _get_history_adjustment(self, task_type: str, backend: str) -> float:
        """
        Calculate adjustment factor based on historical success rates

        Returns multiplier: <1.0 for high success rate, >1.0 for low success rate
        """
        history_key = f"{task_type}:{backend}"
        history = self.task_history.get(history_key, [])

        if len(history) < 3:
            # Not enough history, return neutral
            return 1.0

        # Analyze recent history (last 10 tasks)
        recent = history[-10:]

        # Calculate average iterations needed for success
        successful = [h for h in recent if h.get("success", False)]
        if not successful:
            # No successes, increase limit significantly
            return 1.5

        avg_iterations = sum(h.get("iterations", 10) for h in successful) / len(successful)
        success_rate = len(successful) / len(recent)

        # Adjustment logic:
        # - High success rate + low iterations = decrease limit (efficient)
        # - Low success rate = increase limit (needs more tries)
        # - High iterations needed = increase limit
        if success_rate > 0.8 and avg_iterations < 5:
            return 0.8  # Very efficient, reduce iterations
        elif success_rate > 0.6:
            return 1.0  # Normal
        elif success_rate > 0.4:
            return 1.2  # Struggling, increase
        else:
            return 1.5  # Low success, significant increase

    def _record_task_history(self, task: Dict[str, Any]):
        """Record task completion for adaptive learning"""
        task_type = self._extract_task_type(task.get("prompt", ""))
        backend = task.get("backend", "unknown")
        history_key = f"{task_type}:{backend}"

        if history_key not in self.task_history:
            self.task_history[history_key] = []

        record = {
            "task_id": task.get("task_id"),
            "success": task.get("status") == "completed" and task.get("completion_reason") == "success",
            "iterations": task.get("iteration", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.task_history[history_key].append(record)

        # Keep only last 100 records per type
        if len(self.task_history[history_key]) > 100:
            self.task_history[history_key] = self.task_history[history_key][-100:]

    async def run(self):
        """
        Main loop processor

        Continuously processes tasks from the queue.
        On startup, recovers any incomplete tasks from persisted state (Phase 13.2.5).
        """
        self.is_running = True
        logger.info("loop_engine_started")

        # Phase 13.2.5: Recover incomplete tasks from previous run
        await self._recover_queued_tasks()

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

                # Phase 13.2.3: Per-task timeout
                if self.task_timeout_seconds > 0:
                    try:
                        await asyncio.wait_for(
                            self._process_task_with_ralph_loop(task),
                            timeout=self.task_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            "task_timeout",
                            task_id=task_id,
                            timeout_seconds=self.task_timeout_seconds,
                            iterations_completed=task.get("iteration", 0),
                        )
                        task["status"] = "failed"
                        task["error"] = f"Task timed out after {self.task_timeout_seconds}s"
                        task["completion_reason"] = "timeout"
                        await self.state_manager.save_task_state(task)
                        self._record_task_history(task)
                else:
                    await self._process_task_with_ralph_loop(task)

        except asyncio.CancelledError:
            logger.info("loop_engine_cancelled")
        except Exception as e:
            logger.error("loop_engine_error", error=str(e))
        finally:
            self.is_running = False
            logger.info("loop_engine_stopped")

    async def _recover_queued_tasks(self):
        """
        Recover incomplete tasks from persisted state (Phase 13.2.5).

        On startup, loads tasks that were 'running' or 'queued' when the
        previous instance stopped, and re-enqueues them.
        """
        try:
            all_tasks = await self.state_manager.get_all_tasks()
            recovered = 0
            for task_id, task_state in all_tasks.items():
                status = task_state.get("status", "")
                if status in ("running", "queued"):
                    # Rebuild minimal task structure for re-processing
                    task = {
                        "task_id": task_id,
                        "prompt": task_state.get("prompt", ""),
                        "backend": task_state.get("backend", self.config.get("default_backend", "aider")),
                        "max_iterations": task_state.get("max_iterations", self.config.get("max_iterations", 20)),
                        "iteration_mode": task_state.get("iteration_mode", "fixed"),
                        "original_max_iterations": task_state.get("original_max_iterations", -1),
                        "require_approval": task_state.get("require_approval", False),
                        "context": task_state.get("context_summary", {}),
                        "status": "queued",
                        "iteration": 0,  # restart from 0
                        "started_at": task_state.get("started_at", datetime.now(timezone.utc).isoformat()),
                        "last_update": datetime.now(timezone.utc).isoformat(),
                        "results": [],
                        "error": None,
                        "awaiting_approval": False,
                    }
                    self.tasks[task_id] = task
                    await self.task_queue.put(task_id)
                    recovered += 1

            if recovered:
                logger.info("tasks_recovered", count=recovered)
        except Exception as e:
            logger.warning("task_recovery_failed", error=str(e))

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
            task["last_update"] = datetime.now(timezone.utc).isoformat()

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

            # Check if task was stopped externally
            if task["status"] == "stopped":
                logger.info("ralph_task_stopped_externally", task_id=task_id)
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "result": result
                })

                # Phase 13.2.5: Periodic state persistence
                if iteration % self.state_save_interval == 0:
                    await self.state_manager.save_task_state(task)

                # Log telemetry
                self._log_telemetry({
                    "event": "iteration_completed",
                    "task_id": task_id,
                    "iteration": iteration,
                    "backend": task["backend"],
                    "exit_code": result.get("exit_code", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Run iteration hooks (resource limits, etc.)
                await self._run_hooks("iteration", task, result)
                if task["status"] == "failed":
                    logger.warning("ralph_task_failed", task_id=task_id, error=task.get("error"))
                    task["completion_reason"] = "resource_limit"
                    break

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

        # Record history for adaptive learning (Phase 4)
        self._record_task_history(task)

        last_result = {}
        if task["results"]:
            last_result = task["results"][-1].get("result", {})

        self._log_telemetry({
            "event": "task_completed",
            "task_id": task_id,
            "status": task["status"],
            "total_iterations": iteration,
            "iteration_mode": task.get("iteration_mode", "unknown"),
            "adaptive_limit_used": task.get("max_iterations", 0),
            "task": {
                "task_id": task_id,
                "prompt": task.get("prompt", ""),
                "output": last_result.get("output", ""),
                "iteration": task.get("iteration", iteration),
                "backend": task.get("backend", ""),
                "context": task.get("context", {}),
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
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

    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the full result of a completed/failed task (Phase 13.2.6).

        Returns None if the task doesn't exist. Returns partial results
        for tasks still in progress.
        """
        task = self.tasks.get(task_id)
        if not task:
            # Check persisted state as fallback
            persisted = await self.state_manager.load_task_state(task_id)
            if persisted:
                return {
                    "task_id": task_id,
                    "status": persisted.get("status", "unknown"),
                    "iteration": persisted.get("iteration", 0),
                    "completion_reason": persisted.get("completion_reason"),
                    "error": persisted.get("error"),
                    "results": persisted.get("recent_results", []),
                    "output": self._extract_final_output(persisted.get("recent_results", [])),
                }
            return None

        return {
            "task_id": task_id,
            "status": task["status"],
            "iteration": task["iteration"],
            "backend": task["backend"],
            "max_iterations": task["max_iterations"],
            "iteration_mode": task.get("iteration_mode", "unknown"),
            "started_at": task["started_at"],
            "last_update": task["last_update"],
            "completion_reason": task.get("completion_reason"),
            "error": task.get("error"),
            "results": task["results"][-10:],  # last 10 iterations
            "output": self._extract_final_output(task["results"]),
        }

    @staticmethod
    def _extract_final_output(results: List[Dict[str, Any]]) -> str:
        """Extract the final output from the most recent successful iteration."""
        for entry in reversed(results):
            result = entry.get("result", {})
            output = result.get("output", "")
            if output:
                return output
        return ""

    async def stop_task(self, task_id: str) -> bool:
        """Stop a running task"""
        task = self.tasks.get(task_id)
        if not task or task["status"] not in ["running", "queued"]:
            return False

        task["status"] = "stopped"
        task["stopped_at"] = datetime.now(timezone.utc).isoformat()
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
        """Get statistics including adaptive iteration insights"""
        total_tasks = len(self.tasks)
        running = sum(1 for t in self.tasks.values() if t["status"] == "running")
        completed = sum(1 for t in self.tasks.values() if t["status"] == "completed")
        failed = sum(1 for t in self.tasks.values() if t["status"] == "failed")

        total_iterations = sum(t["iteration"] for t in self.tasks.values())

        # Adaptive iteration stats (Phase 4)
        adaptive_stats = self._get_adaptive_stats()

        return {
            "total_tasks": total_tasks,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total_iterations": total_iterations,
            "average_iterations": total_iterations / total_tasks if total_tasks > 0 else 0,
            "adaptive": adaptive_stats
        }

    def _get_adaptive_stats(self) -> Dict[str, Any]:
        """Get adaptive iteration statistics (Phase 4)"""
        if not self.task_history:
            return {
                "enabled": self.adaptive_enabled,
                "history_entries": 0,
                "task_types": []
            }

        # Aggregate stats per task type
        type_stats = {}
        for history_key, records in self.task_history.items():
            task_type, backend = history_key.split(":", 1)

            successful = [r for r in records if r.get("success", False)]
            avg_iterations = sum(r.get("iterations", 0) for r in successful) / len(successful) if successful else 0
            success_rate = len(successful) / len(records) if records else 0

            type_stats[history_key] = {
                "task_type": task_type,
                "backend": backend,
                "total_tasks": len(records),
                "successful": len(successful),
                "success_rate": round(success_rate, 2),
                "avg_iterations": round(avg_iterations, 1),
                "current_adjustment": self._get_history_adjustment(task_type, backend)
            }

        return {
            "enabled": self.adaptive_enabled,
            "history_entries": sum(len(r) for r in self.task_history.values()),
            "task_types": list(type_stats.values())
        }

    @property
    def active_task_count(self) -> int:
        """Get count of active tasks"""
        return sum(1 for t in self.tasks.values() if t["status"] == "running")

    def _log_telemetry(self, event: Dict[str, Any]):
        """Log telemetry event"""
        if not self.config["audit_log"] or self.telemetry_file is None:
            return

        scrubbed = self._scrub_telemetry_event(event)
        try:
            fcntl.flock(self.telemetry_file.fileno(), fcntl.LOCK_EX)
            self.telemetry_file.write(json.dumps(scrubbed) + "\n")
            self.telemetry_file.flush()
        finally:
            fcntl.flock(self.telemetry_file.fileno(), fcntl.LOCK_UN)

    def _scrub_telemetry_event(self, value: Any, parent_key: str = "") -> Any:
        if isinstance(value, dict):
            return {k: self._scrub_telemetry_event(v, parent_key=k) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scrub_telemetry_event(v, parent_key=parent_key) for v in value]
        if isinstance(value, str) and parent_key and any(token in parent_key.lower() for token in SENSITIVE_FIELD_TOKENS):
            return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
        return value

    async def shutdown(self):
        """Shutdown the engine"""
        self.is_running = False
        if self.telemetry_file is not None:
            self.telemetry_file.close()
        logger.info("loop_engine_shutdown")
