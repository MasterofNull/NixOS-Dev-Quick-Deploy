#!/usr/bin/env python3
"""
Local Agent Executor - Workflow Integration

Enables local llama.cpp agents to execute tasks with tool use:
- Tool-augmented inference
- Multi-step task execution
- Result validation
- Performance tracking
- Automatic failover to remote agents

Part of Phase 11 Batch 11.3: Workflow Integration
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from tool_registry import ToolCall, ToolRegistry, get_registry

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean environment flag."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    """Parse a float environment setting with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %.2f", name, value, default)
        return default


class AgentType(Enum):
    """Local agent types"""
    AGENT = "agent"  # Task execution
    PLANNER = "planner"  # Strategy/planning
    CHAT = "chat"  # User interaction
    EMBEDDED = "embedded"  # Retrieval


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    FALLBACK = "fallback"  # Fell back to remote agent


@dataclass
class Task:
    """Task for agent execution"""
    id: str
    objective: str
    context: Dict[str, Any] = field(default_factory=dict)

    # Routing factors
    complexity: float = 0.5  # 0.0-1.0
    latency_critical: bool = False
    quality_critical: bool = False
    requires_flagship: bool = False

    # Execution state
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    degraded_reason: Optional[str] = None
    execution_time_ms: float = 0.0

    # Agent tracking
    assigned_agent: Optional[str] = None
    tool_calls_made: List[ToolCall] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "objective": self.objective,
            "context": self.context,
            "complexity": self.complexity,
            "latency_critical": self.latency_critical,
            "quality_critical": self.quality_critical,
            "requires_flagship": self.requires_flagship,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "degraded_reason": self.degraded_reason,
            "execution_time_ms": self.execution_time_ms,
            "assigned_agent": self.assigned_agent,
            "tool_calls_count": len(self.tool_calls_made),
        }


@dataclass
class AgentPerformance:
    """Performance tracking for an agent"""
    agent_type: AgentType

    # Counters
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    fallback_tasks: int = 0

    # Timing
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0

    # Quality
    avg_result_quality: float = 0.0  # 0.0-1.0
    quality_samples: int = 0

    # Tool use
    total_tool_calls: int = 0
    successful_tool_calls: int = 0

    def update(self, task: Task):
        """Update performance metrics from completed task"""
        self.total_tasks += 1

        if task.status == TaskStatus.COMPLETED:
            self.successful_tasks += 1
        elif task.status == TaskStatus.FAILED:
            self.failed_tasks += 1
        elif task.status == TaskStatus.FALLBACK:
            self.fallback_tasks += 1

        self.total_execution_time_ms += task.execution_time_ms
        self.avg_execution_time_ms = self.total_execution_time_ms / self.total_tasks

        self.total_tool_calls += len(task.tool_calls_made)
        self.successful_tool_calls += len([
            tc for tc in task.tool_calls_made if tc.status == "completed"
        ])

    def get_success_rate(self) -> float:
        """Get success rate (0.0-1.0)"""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    def get_tool_success_rate(self) -> float:
        """Get tool call success rate"""
        if self.total_tool_calls == 0:
            return 0.0
        return self.successful_tool_calls / self.total_tool_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_type": self.agent_type.value,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "fallback_tasks": self.fallback_tasks,
            "success_rate": self.get_success_rate(),
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "total_tool_calls": self.total_tool_calls,
            "tool_success_rate": self.get_tool_success_rate(),
            "avg_result_quality": self.avg_result_quality,
        }


class LocalAgentExecutor:
    """
    Executes tasks using local llama.cpp agents with tool use.

    Features:
    - Tool-augmented inference
    - Multi-step task execution
    - Performance tracking
    - Automatic failover to remote agents
    """

    def __init__(
        self,
        llama_endpoint: str = "http://127.0.0.1:8080",
        tool_registry: Optional[ToolRegistry] = None,
        enable_fallback: bool = True,
        fallback_endpoint: str = "http://127.0.0.1:8003",
        offline_mode: Optional[bool] = None,
        allow_degraded_local_execution: Optional[bool] = None,
        remote_timeout_seconds: Optional[float] = None,
        remote_probe_timeout_seconds: Optional[float] = None,
    ):
        self.llama_endpoint = llama_endpoint
        self.tool_registry = tool_registry or get_registry()
        self.enable_fallback = enable_fallback
        self.fallback_endpoint = fallback_endpoint
        self.offline_mode = (
            _env_flag("LOCAL_AGENT_OFFLINE_MODE", False)
            if offline_mode is None
            else offline_mode
        )
        self.allow_degraded_local_execution = (
            _env_flag("LOCAL_AGENT_ALLOW_DEGRADED_LOCAL", True)
            if allow_degraded_local_execution is None
            else allow_degraded_local_execution
        )
        self.remote_timeout_seconds = (
            _env_float("LOCAL_AGENT_REMOTE_TIMEOUT_SECONDS", 60.0)
            if remote_timeout_seconds is None
            else remote_timeout_seconds
        )
        self.remote_probe_timeout_seconds = (
            _env_float("LOCAL_AGENT_REMOTE_PROBE_TIMEOUT_SECONDS", 2.0)
            if remote_probe_timeout_seconds is None
            else remote_probe_timeout_seconds
        )
        self._remote_endpoint_healthy: Optional[bool] = None
        self._remote_endpoint_checked_at: float = 0.0

        # Performance tracking per agent type
        self.performance: Dict[AgentType, AgentPerformance] = {
            agent_type: AgentPerformance(agent_type)
            for agent_type in AgentType
        }

        logger.info(
            f"Local agent executor initialized: llama={llama_endpoint}, "
            f"fallback={enable_fallback}, offline_mode={self.offline_mode}, "
            f"allow_degraded_local={self.allow_degraded_local_execution}"
        )

    def route_task(self, task: Task) -> Tuple[bool, str]:
        """
        Route task to local or remote agent.

        Returns:
            (use_local, reason)
        """
        remote_routing_available = self.enable_fallback and not self.offline_mode

        # Always use remote for flagship-required tasks
        if task.requires_flagship:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Flagship requested but remote routing unavailable; degrading to local"
            return False, "Task requires flagship model"

        # Use local for simple, non-critical tasks
        if task.complexity < 0.5 and not task.quality_critical:
            return True, "Simple task, local agent capable"

        # Use local for latency-critical tasks
        if task.latency_critical:
            return True, "Latency critical, local preferred"

        # Use remote for quality-critical tasks
        if task.quality_critical:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Quality critical task degraded to local because remote routing is unavailable"
            return False, "Quality critical, remote preferred"

        # Check local agent performance
        agent_perf = self.performance[AgentType.AGENT]
        if agent_perf.total_tasks > 10:
            success_rate = agent_perf.get_success_rate()

            # Fallback to remote if local success rate too low
            if success_rate < 0.7:
                if not remote_routing_available and self.allow_degraded_local_execution:
                    return True, f"Local success rate low ({success_rate:.1%}) but remote routing unavailable"
                return False, f"Local success rate low ({success_rate:.1%})"

        # Default to local
        return True, "Default to local (cost-efficient)"

    async def execute_task(
        self,
        task: Task,
        agent_type: AgentType = AgentType.AGENT,
        max_tool_calls: int = 10,
    ) -> Task:
        """
        Execute a task using local agent with tool use.

        Args:
            task: Task to execute
            agent_type: Type of agent to use
            max_tool_calls: Maximum tool calls allowed

        Returns:
            Updated task with result or error
        """
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.assigned_agent = f"local-{agent_type.value}"

        # Route task
        use_local, route_reason = self.route_task(task)

        if not use_local:
            if self.enable_fallback:
                if not await self._remote_fallback_available():
                    if self.allow_degraded_local_execution:
                        use_local = True
                        task.degraded_reason = (
                            f"{route_reason}; remote fallback unavailable, executing locally"
                        )
                        logger.warning("Task %s degraded to local execution: %s", task.id, task.degraded_reason)
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = f"{route_reason}; remote fallback unavailable"
                        task.execution_time_ms = (time.time() - start_time) * 1000
                        self.performance[agent_type].update(task)
                        return task
                else:
                    logger.info(f"Task {task.id} routed to remote: {route_reason}")
                    return await self._fallback_to_remote(task)
            elif self.allow_degraded_local_execution:
                use_local = True
                task.degraded_reason = f"{route_reason}; remote fallback disabled, executing locally"
            else:
                task.status = TaskStatus.FAILED
                task.error = f"{route_reason}; remote fallback disabled"
                task.execution_time_ms = (time.time() - start_time) * 1000
                self.performance[agent_type].update(task)
                return task

        if task.degraded_reason is None and "degrading to local" in route_reason.lower():
            task.degraded_reason = route_reason

        logger.info(f"Task {task.id} executing locally: {route_reason}")

        # Execute with tool use loop
        try:
            result = await self._execute_with_tools(
                task,
                agent_type,
                max_tool_calls,
            )

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Task {task.id} completed: {task.execution_time_ms:.1f}ms, "
                f"{len(task.tool_calls_made)} tool calls"
            )

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.execution_time_ms = (time.time() - start_time) * 1000

            logger.error(f"Task {task.id} failed: {e}")

            # Fallback to remote on failure
            if self.enable_fallback and await self._remote_fallback_available():
                logger.info(f"Falling back to remote for task {task.id}")
                return await self._fallback_to_remote(task)
            if self.enable_fallback and task.error:
                task.error = f"{task.error}; remote fallback unavailable"

        # Update performance tracking
        self.performance[agent_type].update(task)

        return task

    async def _execute_with_tools(
        self,
        task: Task,
        agent_type: AgentType,
        max_tool_calls: int,
    ) -> Any:
        """
        Execute task with tool use loop.

        Tool use loop:
        1. Send prompt + tools to model
        2. Parse response for tool calls
        3. Execute tool calls
        4. Append results to context
        5. Repeat until no more tool calls or max reached
        """
        # Get tools for model
        tools = self.tool_registry.get_tools_for_model()

        # Build initial prompt
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(agent_type, tools),
            },
            {
                "role": "user",
                "content": task.objective,
            },
        ]

        # Add context if provided
        if task.context:
            messages.append({
                "role": "system",
                "content": f"Context: {json.dumps(task.context)}",
            })

        # Tool use loop
        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            # Call model
            response = await self._call_llama(messages)

            # Parse tool call
            tool_call = self.tool_registry.parse_tool_call_from_llama(response)

            if not tool_call:
                # No tool call, return response as final answer
                return response

            # Execute tool call
            tool_call.model_id = f"local-{agent_type.value}"
            tool_call.session_id = task.id

            result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Format result for model
            formatted_result = self.tool_registry.format_tool_result(result)

            # Append to messages
            messages.append({
                "role": "assistant",
                "content": response,
            })
            messages.append({
                "role": "function",
                "name": result.tool_name,
                "content": formatted_result,
            })

        # Max tool calls reached, return current state
        logger.warning(f"Task {task.id} reached max tool calls ({max_tool_calls})")
        return f"Task incomplete: reached max tool calls ({max_tool_calls})"

    async def _call_llama(self, messages: List[Dict]) -> str:
        """
        Call local llama.cpp server.

        Args:
            messages: Conversation messages

        Returns:
            Model response
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.llama_endpoint}/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(f"llama.cpp error: {response.status_code} {response.text}")

            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _fallback_to_remote(self, task: Task) -> Task:
        """
        Fallback to remote agent (hybrid coordinator).

        Args:
            task: Task to execute remotely

        Returns:
            Updated task with remote result
        """
        start_time = time.time()
        task.status = TaskStatus.FALLBACK
        task.assigned_agent = "remote-fallback"
        task.degraded_reason = None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.fallback_endpoint}/query",
                    json={
                        "query": task.objective,
                        "context": task.context,
                    },
                    timeout=self.remote_timeout_seconds,
                )

                if response.status_code == 200:
                    data = response.json()
                    task.result = data.get("response", "")
                    task.status = TaskStatus.COMPLETED
                else:
                    task.error = f"Remote fallback failed: {response.status_code} {response.text}"
                    task.status = TaskStatus.FAILED

        except Exception as e:
            task.error = f"Remote fallback error: {e}"
            task.status = TaskStatus.FAILED

        task.execution_time_ms = (time.time() - start_time) * 1000

        return task

    def _get_system_prompt(self, agent_type: AgentType, tools: List[Dict]) -> str:
        """Get system prompt for agent type with tool descriptions"""
        base_prompt = {
            AgentType.AGENT: "You are a helpful AI agent that can use tools to complete tasks.",
            AgentType.PLANNER: "You are a planning agent that breaks down complex tasks into steps.",
            AgentType.CHAT: "You are a friendly chat agent that helps users.",
            AgentType.EMBEDDED: "You are a retrieval agent that finds relevant information.",
        }

        tools_desc = "\n\nAvailable tools:\n" + json.dumps(tools, indent=2)

        return base_prompt[agent_type] + tools_desc

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all agents"""
        return {
            agent_type.value: perf.to_dict()
            for agent_type, perf in self.performance.items()
        }

    async def _remote_fallback_available(self) -> bool:
        """Check whether the remote fallback path should be used."""
        if not self.enable_fallback or self.offline_mode:
            return False
        if time.time() - self._remote_endpoint_checked_at < 15 and self._remote_endpoint_healthy is not None:
            return self._remote_endpoint_healthy
        healthy = await self._probe_remote_fallback()
        self._remote_endpoint_healthy = healthy
        self._remote_endpoint_checked_at = time.time()
        return healthy

    async def _probe_remote_fallback(self) -> bool:
        """Probe the remote fallback endpoint with a short timeout."""
        health_url = f"{self.fallback_endpoint.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=self.remote_probe_timeout_seconds)
            return response.status_code < 500
        except Exception as exc:
            logger.info("Remote fallback probe failed for %s: %s", health_url, exc)
            return False


# Global executor instance
_EXECUTOR: Optional[LocalAgentExecutor] = None


def get_executor() -> LocalAgentExecutor:
    """Get global executor instance"""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = LocalAgentExecutor()
    return _EXECUTOR


if __name__ == "__main__":
    # Test agent executor
    logging.basicConfig(level=logging.INFO)

    async def test():
        from tool_registry import initialize_builtin_tools

        # Initialize tools
        registry = get_registry()
        initialize_builtin_tools(registry)

        # Create executor
        executor = LocalAgentExecutor(tool_registry=registry)

        # Test task
        task = Task(
            id="test-123",
            objective="Get system information and list Python files in current directory",
            complexity=0.3,
            latency_critical=True,
        )

        # Execute task
        result = await executor.execute_task(task)

        print(f"\nTask result:")
        print(f"  Status: {result.status.value}")
        print(f"  Result: {result.result}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
        print(f"  Tool calls: {len(result.tool_calls_made)}")

        # Get performance stats
        stats = executor.get_performance_stats()
        print(f"\nPerformance stats:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
