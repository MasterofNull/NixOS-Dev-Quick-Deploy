#!/usr/bin/env python3
"""
Unified Task Delegation API

Provides high-level declarative interface for delegating tasks to agents:
- Capability-based automatic agent selection
- Priority queue for competing delegations
- Delegation feedback loop for learning
- Rejection handling and fallback routing

Part of Phase 4.2: Multi-Agent Orchestration Enhancements
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DelegationStatus(str, Enum):
    """Status of a delegation request."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class RejectionReason(str, Enum):
    """Reasons for delegation rejection."""
    NO_AVAILABLE_AGENTS = "no_available_agents"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    AGENT_DECLINED = "agent_declined"
    TIMEOUT = "timeout"
    DEPENDENCIES_UNMET = "dependencies_unmet"


@dataclass
class AgentCapability:
    """Agent capability with proficiency level."""
    name: str
    proficiency: float = 1.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegationTarget:
    """Target agent for delegation."""
    agent_id: str
    name: str
    capabilities: Set[str] = field(default_factory=set)
    capability_levels: Dict[str, float] = field(default_factory=dict)
    current_load: float = 0.0
    max_concurrent: int = 5
    success_rate: float = 1.0
    avg_completion_time: float = 0.0
    is_available: bool = True

    def can_execute(self, required_capabilities: Set[str]) -> bool:
        """Check if agent can execute task with required capabilities."""
        return required_capabilities.issubset(self.capabilities)

    def capability_score(self, required_capabilities: Set[str]) -> float:
        """Calculate capability match score."""
        if not required_capabilities:
            return 1.0
        scores = [
            self.capability_levels.get(cap, 0.5)
            for cap in required_capabilities
        ]
        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class DelegationRequest:
    """Request to delegate a task."""
    request_id: str
    task_description: str
    required_capabilities: Set[str] = field(default_factory=set)
    preferred_agent: Optional[str] = None
    fallback_agents: List[str] = field(default_factory=list)
    priority: int = 5  # 1 (highest) to 10 (lowest)
    timeout_seconds: float = 300.0
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class DelegationResult:
    """Result of a delegation."""
    request_id: str
    status: DelegationStatus
    assigned_agent: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    reject_reason: Optional[RejectionReason] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "error": self.error,
            "reject_reason": self.reject_reason.value if self.reject_reason else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "execution_time_seconds": self.execution_time_seconds,
        }


class DelegationQueue:
    """Priority queue for delegation requests."""

    def __init__(self) -> None:
        self._queue: List[DelegationRequest] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, request: DelegationRequest) -> None:
        async with self._lock:
            self._queue.append(request)
            self._queue.sort(key=lambda r: (r.priority, r.created_at))

    async def dequeue(self) -> Optional[DelegationRequest]:
        async with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None

    async def peek(self) -> Optional[DelegationRequest]:
        async with self._lock:
            return self._queue[0] if self._queue else None

    async def remove(self, request_id: str) -> bool:
        async with self._lock:
            for i, req in enumerate(self._queue):
                if req.request_id == request_id:
                    self._queue.pop(i)
                    return True
            return False

    def size(self) -> int:
        return len(self._queue)


class DelegationFeedback:
    """Feedback collector for learning from delegation outcomes."""

    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []
        self._agent_stats: Dict[str, Dict[str, float]] = {}

    def record(
        self,
        request: DelegationRequest,
        result: DelegationResult,
    ) -> None:
        """Record delegation outcome for learning."""
        entry = {
            "request_id": request.request_id,
            "capabilities": list(request.required_capabilities),
            "agent_id": result.assigned_agent,
            "success": result.status == DelegationStatus.COMPLETED,
            "execution_time": result.execution_time_seconds,
            "timestamp": time.time(),
        }
        self._history.append(entry)

        # Update agent statistics
        if result.assigned_agent:
            stats = self._agent_stats.setdefault(result.assigned_agent, {
                "total": 0,
                "successful": 0,
                "total_time": 0.0,
            })
            stats["total"] += 1
            if result.status == DelegationStatus.COMPLETED:
                stats["successful"] += 1
            stats["total_time"] += result.execution_time_seconds

    def get_agent_success_rate(self, agent_id: str) -> float:
        """Get historical success rate for an agent."""
        stats = self._agent_stats.get(agent_id)
        if not stats or stats["total"] == 0:
            return 1.0
        return stats["successful"] / stats["total"]

    def get_agent_avg_time(self, agent_id: str) -> float:
        """Get average execution time for an agent."""
        stats = self._agent_stats.get(agent_id)
        if not stats or stats["total"] == 0:
            return 0.0
        return stats["total_time"] / stats["total"]

    def suggest_agent(
        self,
        required_capabilities: Set[str],
        available_agents: List[DelegationTarget],
    ) -> Optional[str]:
        """Suggest best agent based on historical performance."""
        candidates = [
            a for a in available_agents
            if a.can_execute(required_capabilities)
        ]
        if not candidates:
            return None

        # Score based on success rate, capability match, and load
        def score(agent: DelegationTarget) -> float:
            historical_rate = self.get_agent_success_rate(agent.agent_id)
            cap_score = agent.capability_score(required_capabilities)
            load_penalty = agent.current_load / agent.max_concurrent
            return (historical_rate * 0.4 + cap_score * 0.4 + (1 - load_penalty) * 0.2)

        best = max(candidates, key=score)
        return best.agent_id


class DelegationAPI:
    """
    Unified API for task delegation to agents.

    Provides declarative task assignment with automatic agent selection,
    priority handling, and feedback-based learning.
    """

    def __init__(
        self,
        executor_fn: Optional[Callable[[str, DelegationRequest], Awaitable[Any]]] = None,
    ) -> None:
        self.agents: Dict[str, DelegationTarget] = {}
        self.queue = DelegationQueue()
        self.feedback = DelegationFeedback()
        self.executor_fn = executor_fn
        self._pending: Dict[str, DelegationResult] = {}
        self._completed: Dict[str, DelegationResult] = {}

    # -------------------------------------------------------------------------
    # Agent Registry
    # -------------------------------------------------------------------------

    def register_agent(
        self,
        agent_id: str,
        name: str,
        capabilities: Optional[Set[str]] = None,
        capability_levels: Optional[Dict[str, float]] = None,
        max_concurrent: int = 5,
    ) -> DelegationTarget:
        """Register an agent for delegation."""
        agent = DelegationTarget(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or set(),
            capability_levels=capability_levels or {},
            max_concurrent=max_concurrent,
        )
        self.agents[agent_id] = agent
        logger.info("Registered agent %s with capabilities: %s", name, capabilities)
        return agent

    def update_agent_status(
        self,
        agent_id: str,
        is_available: bool,
        current_load: Optional[float] = None,
    ) -> None:
        """Update agent availability status."""
        if agent_id in self.agents:
            self.agents[agent_id].is_available = is_available
            if current_load is not None:
                self.agents[agent_id].current_load = current_load

    def get_available_agents(
        self,
        required_capabilities: Optional[Set[str]] = None,
    ) -> List[DelegationTarget]:
        """Get agents available for delegation."""
        available = []
        for agent in self.agents.values():
            if not agent.is_available:
                continue
            if agent.current_load >= agent.max_concurrent:
                continue
            if required_capabilities and not agent.can_execute(required_capabilities):
                continue
            available.append(agent)
        return available

    # -------------------------------------------------------------------------
    # Delegation Operations
    # -------------------------------------------------------------------------

    async def delegate(
        self,
        task_description: str,
        required_capabilities: Optional[Set[str]] = None,
        preferred_agent: Optional[str] = None,
        fallback_agents: Optional[List[str]] = None,
        priority: int = 5,
        timeout_seconds: float = 300.0,
        context: Optional[Dict[str, Any]] = None,
        wait: bool = True,
    ) -> DelegationResult:
        """
        Delegate a task to an agent.

        Args:
            task_description: Natural language task description
            required_capabilities: Required agent capabilities
            preferred_agent: Preferred agent ID
            fallback_agents: Fallback agent IDs if preferred unavailable
            priority: 1 (highest) to 10 (lowest)
            timeout_seconds: Maximum wait time
            context: Additional context for the task
            wait: If True, wait for result; if False, return immediately

        Returns:
            DelegationResult with status and result/error
        """
        request = DelegationRequest(
            request_id=f"del-{uuid.uuid4().hex[:8]}",
            task_description=task_description,
            required_capabilities=required_capabilities or set(),
            preferred_agent=preferred_agent,
            fallback_agents=fallback_agents or [],
            priority=priority,
            timeout_seconds=timeout_seconds,
            context=context or {},
        )

        result = DelegationResult(
            request_id=request.request_id,
            status=DelegationStatus.PENDING,
        )
        self._pending[request.request_id] = result

        # Try to assign immediately
        assigned_agent = await self._select_agent(request)

        if not assigned_agent:
            # No agent available, queue for later
            await self.queue.enqueue(request)
            result.status = DelegationStatus.PENDING
            result.reject_reason = RejectionReason.NO_AVAILABLE_AGENTS

            if not wait:
                return result

            # Wait for assignment with timeout
            try:
                return await asyncio.wait_for(
                    self._wait_for_completion(request.request_id),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                result.status = DelegationStatus.TIMEOUT
                result.reject_reason = RejectionReason.TIMEOUT
                await self.queue.remove(request.request_id)
                return result

        # Execute immediately
        return await self._execute_delegation(request, assigned_agent, wait)

    async def _select_agent(self, request: DelegationRequest) -> Optional[str]:
        """Select best agent for delegation."""
        # Try preferred agent first
        if request.preferred_agent:
            agent = self.agents.get(request.preferred_agent)
            if agent and agent.is_available and agent.can_execute(request.required_capabilities):
                if agent.current_load < agent.max_concurrent:
                    return request.preferred_agent

        # Try fallback agents
        for agent_id in request.fallback_agents:
            agent = self.agents.get(agent_id)
            if agent and agent.is_available and agent.can_execute(request.required_capabilities):
                if agent.current_load < agent.max_concurrent:
                    return agent_id

        # Use feedback-based suggestion
        available = self.get_available_agents(request.required_capabilities)
        if available:
            suggestion = self.feedback.suggest_agent(request.required_capabilities, available)
            if suggestion:
                return suggestion
            # Fall back to first available
            return available[0].agent_id

        return None

    async def _execute_delegation(
        self,
        request: DelegationRequest,
        agent_id: str,
        wait: bool,
    ) -> DelegationResult:
        """Execute delegation on selected agent."""
        result = self._pending[request.request_id]
        result.status = DelegationStatus.ASSIGNED
        result.assigned_agent = agent_id
        result.started_at = time.time()

        agent = self.agents[agent_id]
        agent.current_load += 1

        if not wait:
            # Start execution in background
            asyncio.create_task(self._run_task(request, result, agent))
            return result

        return await self._run_task(request, result, agent)

    async def _run_task(
        self,
        request: DelegationRequest,
        result: DelegationResult,
        agent: DelegationTarget,
    ) -> DelegationResult:
        """Run the delegated task."""
        result.status = DelegationStatus.EXECUTING

        try:
            if self.executor_fn:
                task_result = await asyncio.wait_for(
                    self.executor_fn(agent.agent_id, request),
                    timeout=request.timeout_seconds,
                )
                result.result = task_result
                result.status = DelegationStatus.COMPLETED
            else:
                # No executor, mark as completed without result
                result.status = DelegationStatus.COMPLETED
                result.result = {"message": "Task delegated (no executor configured)"}

        except asyncio.TimeoutError:
            result.status = DelegationStatus.TIMEOUT
            result.error = f"Execution timed out after {request.timeout_seconds}s"
            result.reject_reason = RejectionReason.TIMEOUT

        except Exception as e:
            result.status = DelegationStatus.FAILED
            result.error = str(e)
            logger.exception("Delegation execution failed: %s", e)

        finally:
            result.completed_at = time.time()
            result.execution_time_seconds = result.completed_at - (result.started_at or result.completed_at)
            agent.current_load = max(0, agent.current_load - 1)

            # Record feedback
            self.feedback.record(request, result)

            # Move to completed
            self._completed[request.request_id] = result
            self._pending.pop(request.request_id, None)

            # Process queued requests
            await self._process_queue()

        return result

    async def _wait_for_completion(self, request_id: str) -> DelegationResult:
        """Wait for a delegation to complete."""
        while request_id in self._pending:
            await asyncio.sleep(0.1)
        return self._completed.get(request_id, DelegationResult(
            request_id=request_id,
            status=DelegationStatus.FAILED,
            error="Request not found",
        ))

    async def _process_queue(self) -> None:
        """Process queued delegation requests."""
        while True:
            request = await self.queue.peek()
            if not request:
                break

            agent_id = await self._select_agent(request)
            if not agent_id:
                break

            # Remove from queue and execute
            await self.queue.dequeue()
            result = self._pending.get(request.request_id)
            if result:
                asyncio.create_task(self._execute_delegation(request, agent_id, wait=False))

    # -------------------------------------------------------------------------
    # Status & Monitoring
    # -------------------------------------------------------------------------

    def get_delegation_status(self, request_id: str) -> Optional[DelegationResult]:
        """Get status of a delegation request."""
        return self._pending.get(request_id) or self._completed.get(request_id)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get delegation queue status."""
        return {
            "queue_size": self.queue.size(),
            "pending_count": len(self._pending),
            "completed_count": len(self._completed),
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "available": agent.is_available,
                    "load": agent.current_load,
                    "max_concurrent": agent.max_concurrent,
                    "success_rate": self.feedback.get_agent_success_rate(agent_id),
                }
                for agent_id, agent in self.agents.items()
            },
        }


# -------------------------------------------------------------------------
# Decorators for declarative delegation
# -------------------------------------------------------------------------

def delegate_to(
    agent_id: Optional[str] = None,
    capabilities: Optional[Set[str]] = None,
    priority: int = 5,
    timeout: float = 300.0,
) -> Callable[[Callable[..., T]], Callable[..., Awaitable[T]]]:
    """
    Decorator to delegate function execution to an agent.

    Usage:
        @delegate_to(capabilities={"code_review"})
        async def review_code(code: str) -> str:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Get the delegation API from context or create new
            api = kwargs.pop("_delegation_api", None)
            if not api:
                logger.warning("No delegation API provided, executing locally")
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result

            # Create task description from function name and args
            task_desc = f"{func.__name__}({', '.join(str(a)[:50] for a in args)})"

            delegation_result = await api.delegate(
                task_description=task_desc,
                required_capabilities=capabilities,
                preferred_agent=agent_id,
                priority=priority,
                timeout_seconds=timeout,
                context={"args": args, "kwargs": kwargs},
            )

            if delegation_result.status == DelegationStatus.COMPLETED:
                return delegation_result.result
            raise RuntimeError(f"Delegation failed: {delegation_result.error}")

        return wrapper
    return decorator


def require_capability(*capabilities: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to mark function as requiring specific capabilities.

    Usage:
        @require_capability("security_audit", "code_analysis")
        def audit_codebase() -> Report:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func._required_capabilities = set(capabilities)  # type: ignore
        return func
    return decorator
