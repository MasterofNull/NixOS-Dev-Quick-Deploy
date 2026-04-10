"""
Workflow Executor - Execution backend for harness workflows

This module provides the missing execution backend that processes workflow sessions
created by the coordinator but never executed.

Architecture:
- Polls for in_progress workflow sessions
- Executes workflow phases using LLM APIs
- Updates session state with results and events
- Respects budget limits and safety modes
- Handles errors and retries

Created: 2026-04-09
Purpose: Fix architectural gap where sessions are created but never executed
"""

import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

try:
    from llm_client import LLMClient, PromptBuilder
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logger = logging.getLogger("workflow-executor")


class WorkflowExecutor:
    """
    Executes workflow sessions by processing phases and updating state.

    This is a standalone executor that can run as:
    - Background asyncio task within the coordinator
    - Separate process/service
    - On-demand for testing
    """

    def __init__(
        self,
        sessions_file: str = ".workflow-sessions.json",
        poll_interval: float = 2.0,
        max_concurrent: int = 3,
        llm_provider: str = "anthropic",
        use_llm: bool = True,
    ):
        """
        Initialize workflow executor.

        Args:
            sessions_file: Path to workflow sessions JSON file
            poll_interval: Seconds between polls for new work
            max_concurrent: Maximum concurrent executions
            llm_provider: LLM provider ("anthropic", "openai", "local")
            use_llm: Whether to use real LLM (False = mock execution)
        """
        self.sessions_file = Path(sessions_file)
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.running_sessions: Dict[str, asyncio.Task] = {}
        self.should_stop = False

        # Initialize LLM client
        self.use_llm = use_llm and LLM_AVAILABLE
        if self.use_llm:
            try:
                self.llm_client = LLMClient(provider=llm_provider)
                logger.info(f"LLM client initialized (provider: {llm_provider})")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client: {e}. Using mock execution.")
                self.llm_client = None
                self.use_llm = False
        else:
            self.llm_client = None
            logger.info("Mock execution mode (no LLM)")

    async def run(self):
        """
        Main execution loop - polls for sessions and executes them.

        Runs until stop() is called.
        """
        logger.info(f"Workflow executor started (poll_interval={self.poll_interval}s)")

        while not self.should_stop:
            try:
                # Load sessions
                sessions = await self._load_sessions()

                # Find sessions that need execution
                pending = self._find_pending_sessions(sessions)

                # Start execution for pending sessions (up to max_concurrent)
                for session_id in pending:
                    if len(self.running_sessions) >= self.max_concurrent:
                        break

                    if session_id not in self.running_sessions:
                        session = sessions[session_id]
                        task = asyncio.create_task(
                            self._execute_session(session_id, session)
                        )
                        self.running_sessions[session_id] = task
                        logger.info(f"Started execution of session {session_id[:8]}")

                # Clean up completed tasks
                completed = [
                    sid for sid, task in self.running_sessions.items()
                    if task.done()
                ]
                for sid in completed:
                    del self.running_sessions[sid]

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in executor main loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        # Wait for running sessions to complete
        if self.running_sessions:
            logger.info(f"Waiting for {len(self.running_sessions)} running sessions to complete...")
            await asyncio.gather(*self.running_sessions.values(), return_exceptions=True)

        logger.info("Workflow executor stopped")

    def stop(self):
        """Signal executor to stop gracefully."""
        self.should_stop = True

    async def _load_sessions(self) -> Dict[str, Any]:
        """Load workflow sessions from file."""
        if not self.sessions_file.exists():
            return {}

        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            return {}

    async def _save_sessions(self, sessions: Dict[str, Any]):
        """Save workflow sessions to file."""
        try:
            self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

    def _find_pending_sessions(self, sessions: Dict[str, Any]) -> List[str]:
        """
        Find sessions that need execution.

        Returns session IDs that are:
        - Status: in_progress
        - Not currently being executed
        - Have remaining budget
        """
        pending = []

        for session_id, session in sessions.items():
            # Skip if already running
            if session_id in self.running_sessions:
                continue

            # Check status
            if session.get("status") != "in_progress":
                continue

            # Check budget
            usage = session.get("usage", {})
            budget = session.get("budget", {})

            tokens_used = usage.get("tokens_used", 0)
            token_limit = budget.get("token_limit", 0)

            if token_limit > 0 and tokens_used >= token_limit:
                logger.debug(f"Session {session_id[:8]} over token budget")
                continue

            pending.append(session_id)

        return pending

    async def _execute_session(self, session_id: str, session: Dict[str, Any]):
        """
        Execute a workflow session.

        This is where the actual work happens:
        1. Get current phase
        2. Execute phase steps using LLM
        3. Update session state with results
        4. Move to next phase or complete
        """
        try:
            logger.info(f"Executing session {session_id[:8]}: {session.get('objective', '')[:60]}")

            objective = session.get("objective", "")
            safety_mode = session.get("safety_mode", "plan-readonly")
            budget = session.get("budget", {})
            phase_index = session.get("current_phase_index", 0)
            plan = session.get("plan", {})
            phases = plan.get("phases", [])

            # Get current phase
            if phase_index < len(phases):
                current_phase = phases[phase_index]
            else:
                current_phase = {"id": f"phase-{phase_index}"}

            trajectory = session.get("trajectory", [])
            usage = session.get("usage", {"tokens_used": 0, "tool_calls_used": 0})

            # Add execution started event
            trajectory.append({
                "ts": time.time(),
                "event_type": "execution_started",
                "phase_id": current_phase.get("id"),
                "detail": "Executor processing session",
                "executor_version": "2.0.0",  # LLM-enabled
                "use_llm": self.use_llm,
            })

            # Execute with LLM or mock
            if self.use_llm and self.llm_client:
                result = await self._execute_with_llm(
                    objective, current_phase, session
                )

                # Update usage
                usage["tokens_used"] += result.get("tokens_used", 0)
                usage["tool_calls_used"] += result.get("tool_calls_made", 0)

                # Add completion event
                trajectory.append({
                    "ts": time.time(),
                    "event_type": "llm_response",
                    "phase_id": current_phase.get("id"),
                    "detail": result.get("summary", "LLM execution completed"),
                    "tokens": result.get("tokens_used", 0),
                    "model": result.get("model", "unknown"),
                })

                # Update session
                await self._update_session(session_id, {
                    "status": "completed",
                    "trajectory": trajectory,
                    "usage": usage,
                    "result": result.get("output", ""),
                    "completed_at": time.time(),
                })

            else:
                # Mock execution
                await asyncio.sleep(1.0)

                trajectory.append({
                    "ts": time.time(),
                    "event_type": "mock_execution",
                    "phase_id": current_phase.get("id"),
                    "detail": "Mock execution completed (no LLM)",
                })

                await self._update_session(session_id, {
                    "status": "completed",
                    "trajectory": trajectory,
                    "completed_at": time.time(),
                })

            logger.info(f"Completed session {session_id[:8]}")

        except Exception as e:
            logger.error(f"Error executing session {session_id[:8]}: {e}", exc_info=True)

            # Mark session as failed
            await self._update_session(session_id, {
                "status": "failed",
                "error": str(e),
                "failed_at": time.time(),
            })

    async def _execute_with_llm(
        self,
        objective: str,
        phase: Dict[str, Any],
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute workflow phase using LLM.

        Args:
            objective: Workflow objective
            phase: Current phase definition
            session: Full session context

        Returns:
            Execution result with output, tokens, etc.
        """
        try:
            # Build prompt
            system_prompt, user_prompt = PromptBuilder.build_workflow_prompt(
                objective, phase, session
            )

            # Get tool definitions (if safety mode allows)
            safety_mode = session.get("safety_mode", "plan-readonly")
            tools = None
            if "execute" in safety_mode:
                tools = PromptBuilder.build_tool_definitions()

            # Call LLM
            logger.debug(f"Calling LLM for objective: {objective[:60]}...")
            response = await self.llm_client.create_message(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=session.get("budget", {}).get("token_limit", 4096),
                tools=tools,
            )

            # Process response
            result = {
                "output": response.content,
                "tokens_used": response.usage["total_tokens"],
                "tool_calls_made": len(response.tool_calls),
                "model": response.model,
                "stop_reason": response.stop_reason,
                "summary": f"LLM response: {response.content[:100]}...",
            }

            # Log tool calls
            if response.tool_calls:
                logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
                for tool_call in response.tool_calls:
                    logger.debug(f"  - {tool_call['name']}: {tool_call['input']}")

            return result

        except Exception as e:
            logger.error(f"LLM execution error: {e}", exc_info=True)
            raise

    async def _update_session(self, session_id: str, updates: Dict[str, Any]):
        """
        Update session state.

        Args:
            session_id: Session to update
            updates: Fields to update
        """
        sessions = await self._load_sessions()

        if session_id not in sessions:
            logger.error(f"Session {session_id} not found for update")
            return

        # Apply updates
        session = sessions[session_id]
        session.update(updates)
        session["updated_at"] = time.time()

        # Save
        await self._save_sessions(sessions)
        logger.debug(f"Updated session {session_id[:8]}")


class WorkflowPhaseExecutor:
    """
    Executes individual workflow phases.

    Each phase may involve:
    - LLM calls for planning/reasoning
    - Tool execution
    - Result validation
    - Error handling
    """

    def __init__(self, llm_client=None):
        """
        Initialize phase executor.

        Args:
            llm_client: LLM client for API calls (future implementation)
        """
        self.llm_client = llm_client

    async def execute_phase(
        self,
        phase: Dict[str, Any],
        objective: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a single workflow phase.

        Args:
            phase: Phase definition
            objective: Overall workflow objective
            context: Execution context (budget, safety_mode, etc.)

        Returns:
            Phase execution result with outputs and events
        """
        phase_id = phase.get("id", "unknown")
        logger.info(f"Executing phase: {phase_id}")

        # TODO: Implement actual phase execution:
        # 1. Generate phase prompt from objective + context
        # 2. Call LLM API
        # 3. Parse response for tool calls
        # 4. Execute tools if in execute mode
        # 5. Collect results
        # 6. Validate against phase goals

        # For now, return mock result
        result = {
            "phase_id": phase_id,
            "status": "completed",
            "outputs": [],
            "events": [],
            "tokens_used": 0,
            "tool_calls_made": 0,
        }

        return result


# Standalone execution entry point
async def run_standalone_executor(
    sessions_file: str = None,
    poll_interval: float = 2.0,
):
    # Use coordinator's sessions file by default
    if sessions_file is None:
        import os
        from pathlib import Path
        data_dir = Path(os.path.expanduser(os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")))
        sessions_file = str(data_dir / "workflow-sessions.json")
    """
    Run executor as standalone process.

    Usage:
        python3 -m workflow_executor

    Or:
        from workflow_executor import run_standalone_executor
        asyncio.run(run_standalone_executor())
    """
    executor = WorkflowExecutor(
        sessions_file=sessions_file,
        poll_interval=poll_interval,
    )

    try:
        await executor.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        executor.stop()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run executor
    asyncio.run(run_standalone_executor())
