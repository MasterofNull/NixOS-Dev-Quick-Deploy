import asyncio
import logging
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import httpx

# Configure logging
logger = logging.getLogger("ralph_orchestrator")


@dataclass
class TaskResult:
    success: bool
    iterations: int
    output: str
    metadata: Dict[str, Any]


class RalphOrchestrator:
    """
    Layer 1 Orchestrator: Ralph Wiggum
    Manages iterative tasks and delegates to Hybrid Coordinator (Layer 2) and AIDB (Layer 3).
    """

    def __init__(self, hybrid_client, aidb_client, learning_client=None):
        self.hybrid = hybrid_client  # Layer 2: Router
        self.aidb = aidb_client  # Layer 3: Knowledge
        self.learning = learning_client  # Cross-cutting: Telemetry

    async def execute_agent(
        self,
        backend: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        iteration: int = 1,
    ) -> Dict[str, Any]:
        """
        Execute a single agent iteration via nested orchestration.

        1. Retrieve context from AIDB (Layer 3)
        2. Route via Hybrid Coordinator (Layer 2)
        3. Return the combined result

        Returns:
            {
                "exit_code": int,
                "output": str,
                "completed": bool,
                "error": str | None,
                "route": str,
            }
        """
        try:
            # Step 1: Fetch context from AIDB
            aidb_context = {}
            try:
                search_results = await self.aidb.vector_search(
                    query=prompt, collection="documents", limit=3
                )
                aidb_context = {"search_results": search_results}
            except Exception as e:
                logger.warning("aidb_context_fetch_failed", error=str(e))

            # Merge task context with AIDB context
            merged_context = {**(context or {}), **aidb_context, "iteration": iteration}

            # Step 2: Route through Hybrid Coordinator
            routing_result = await self.hybrid.route_search(
                prompt=prompt,
                prefer_local=True,
                context=merged_context,
            )

            route = routing_result.get("backend", "unknown")
            response_text = routing_result.get("response", "")

            logger.info(
                "agent_iteration_completed",
                backend=backend,
                route=route,
                iteration=iteration,
                response_length=len(response_text),
            )

            # Step 3: Telemetry
            if self.learning:
                try:
                    await self.learning.submit_event(
                        layer="ralph",
                        event_type="agent_iteration",
                        data={
                            "backend": backend,
                            "route": route,
                            "iteration": iteration,
                            "prompt_length": len(prompt),
                            "response_length": len(response_text),
                        },
                    )
                except Exception as e:
                    logger.debug("telemetry_submit_failed", error=str(e))

            return {
                "exit_code": 0,
                "output": response_text,
                "completed": bool(response_text),
                "error": None,
                "route": route,
            }

        except httpx.ConnectError as e:
            logger.error("agent_connection_error", backend=backend, error=str(e))
            return {
                "exit_code": 1,
                "output": "",
                "completed": False,
                "error": f"Connection failed: {e}",
            }
        except httpx.TimeoutException as e:
            logger.error("agent_timeout", backend=backend, error=str(e))
            return {
                "exit_code": 1,
                "output": "",
                "completed": False,
                "error": f"Timeout: {e}",
            }
        except Exception as e:
            logger.error("agent_execution_error", backend=backend, error=str(e))
            return {
                "exit_code": 1,
                "output": "",
                "completed": False,
                "error": str(e),
            }

    async def execute_task(
        self, task_description: str, backend: str = "aider", max_iterations: int = 10
    ) -> TaskResult:
        """
        Execute a full task using nested orchestration.
        Iterates calling execute_agent until success or max_iterations.
        """
        task_id = str(uuid.uuid4())
        logger.info("starting_task", task_id=task_id, description=task_description[:50])

        iteration = 0
        final_output = ""
        success = False

        while iteration < max_iterations:
            iteration += 1
            result = await self.execute_agent(
                backend=backend,
                prompt=task_description,
                iteration=iteration,
            )

            if result.get("exit_code") == 0 and result.get("completed"):
                success = True
                final_output = result.get("output", "")
                break

        return TaskResult(
            success=success,
            iterations=iteration,
            output=final_output,
            metadata={"task_id": task_id},
        )
