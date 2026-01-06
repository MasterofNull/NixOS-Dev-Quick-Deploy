#!/usr/bin/env python3
"""
Agent Orchestrator
Routes tasks to different agent backends (Aider, Continue, Goose, AutoGPT, LangChain)
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger()


class AgentOrchestrator:
    """
    Orchestrates multiple agent backends

    Supports:
    - Aider: AI pair programming with git integration
    - Continue: Open-source autopilot for IDEs
    - Goose: Autonomous coding agent with file system access
    - AutoGPT: Goal decomposition and planning
    - LangChain: Agent framework with memory
    """

    BACKEND_URLS = {
        "aider": "http://localhost:8099",  # Aider HTTP wrapper
        "continue": "http://continue-server:8080",  # TODO: create wrapper
        "goose": "http://goose:8080",  # TODO: create wrapper
        "autogpt": "http://autogpt:8080",  # TODO: create wrapper
        "langchain": "http://langchain:8080",  # TODO: create wrapper
    }

    def __init__(self, backends: List[str], default_backend: str):
        self.backends = backends
        self.default_backend = default_backend
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout

        logger.info("orchestrator_initialized", backends=backends, default=default_backend)

    async def execute_agent(
        self,
        backend: str,
        prompt: str,
        context: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Execute an agent backend with the given prompt

        Args:
            backend: Agent backend name
            prompt: Task prompt
            context: Additional context
            iteration: Current iteration number

        Returns:
            Result dictionary with exit_code, output, completed status
        """
        if backend not in self.backends:
            logger.warning("unknown_backend", backend=backend, using_default=self.default_backend)
            backend = self.default_backend

        url = self.BACKEND_URLS.get(backend)
        if not url:
            raise ValueError(f"Unknown backend: {backend}")

        logger.info("executing_agent", backend=backend, iteration=iteration)

        try:
            # Prepare request payload
            payload = {
                "prompt": prompt,
                "context": context,
                "iteration": iteration,
                "mode": "autonomous"  # Request autonomous execution
            }

            # Execute based on backend type
            if backend == "aider":
                return await self._execute_aider(url, payload)
            elif backend == "continue":
                return await self._execute_continue(url, payload)
            elif backend == "goose":
                return await self._execute_goose(url, payload)
            elif backend == "autogpt":
                return await self._execute_autogpt(url, payload)
            elif backend == "langchain":
                return await self._execute_langchain(url, payload)
            else:
                raise ValueError(f"Unsupported backend: {backend}")

        except httpx.TimeoutException:
            logger.error("agent_timeout", backend=backend)
            return {
                "exit_code": 1,
                "output": "Agent execution timed out",
                "completed": False,
                "error": "timeout"
            }
        except Exception as e:
            logger.error("agent_execution_error", backend=backend, error=str(e))
            return {
                "exit_code": 1,
                "output": str(e),
                "completed": False,
                "error": str(e)
            }

    async def _execute_aider(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Aider agent"""
        # Aider API endpoint
        response = await self.client.post(f"{url}/api/execute", json=payload)
        response.raise_for_status()

        result = response.json()

        return {
            "exit_code": result.get("exit_code", 0),
            "output": result.get("output", ""),
            "completed": result.get("completed", False),
            "git_commits": result.get("commits", []),
            "files_modified": result.get("files_modified", [])
        }

    async def _execute_continue(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Continue agent"""
        response = await self.client.post(f"{url}/api/task", json=payload)
        response.raise_for_status()

        result = response.json()

        return {
            "exit_code": result.get("status_code", 0),
            "output": result.get("response", ""),
            "completed": result.get("task_complete", False),
            "suggestions": result.get("suggestions", [])
        }

    async def _execute_goose(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Goose agent"""
        response = await self.client.post(f"{url}/api/run", json=payload)
        response.raise_for_status()

        result = response.json()

        return {
            "exit_code": 0 if result.get("success", False) else 1,
            "output": result.get("output", ""),
            "completed": result.get("completed", False),
            "debug_info": result.get("debug", {}),
            "file_operations": result.get("file_ops", [])
        }

    async def _execute_autogpt(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute AutoGPT agent"""
        response = await self.client.post(f"{url}/api/agent/tasks", json={
            "input": payload["prompt"],
            "additional_input": payload.get("context", {})
        })
        response.raise_for_status()

        result = response.json()
        task_id = result.get("task_id")

        # Poll for completion
        max_wait = 300  # 5 minutes
        interval = 5
        elapsed = 0

        while elapsed < max_wait:
            status_response = await self.client.get(f"{url}/api/agent/tasks/{task_id}")
            status_response.raise_for_status()
            status = status_response.json()

            if status.get("status") in ["completed", "failed"]:
                return {
                    "exit_code": 0 if status.get("status") == "completed" else 1,
                    "output": status.get("output", ""),
                    "completed": status.get("status") == "completed",
                    "artifacts": status.get("artifacts", [])
                }

            await asyncio.sleep(interval)
            elapsed += interval

        # Timeout
        return {
            "exit_code": 1,
            "output": "AutoGPT task timed out",
            "completed": False,
            "error": "timeout"
        }

    async def _execute_langchain(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LangChain agent"""
        response = await self.client.post(f"{url}/invoke", json={
            "input": payload["prompt"],
            "config": {
                "metadata": payload.get("context", {}),
                "tags": ["ralph-wiggum", f"iteration-{payload['iteration']}"]
            }
        })
        response.raise_for_status()

        result = response.json()

        return {
            "exit_code": 0 if result.get("output") else 1,
            "output": result.get("output", ""),
            "completed": result.get("metadata", {}).get("completed", False),
            "intermediate_steps": result.get("intermediate_steps", [])
        }

    async def health_check(self, backend: str) -> bool:
        """Check if backend is healthy"""
        url = self.BACKEND_URLS.get(backend)
        if not url:
            return False

        try:
            response = await self.client.get(f"{url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def shutdown(self):
        """Cleanup"""
        await self.client.aclose()
