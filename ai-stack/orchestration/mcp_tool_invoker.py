#!/usr/bin/env python3
"""
MCP Tool Invocation Interface

Unified interface for invoking MCP tools with:
- Semantic tool search and discovery
- Result caching and deduplication
- Error recovery strategies
- Tool usage analytics
- Permission and rate limiting

Part of Phase 4.2: Multi-Agent Orchestration Enhancements
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    """Tool operational status."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class ErrorRecoveryStrategy(str, Enum):
    """Strategy for recovering from tool errors."""
    FAIL_FAST = "fail_fast"
    RETRY = "retry"
    FALLBACK = "fallback"
    IGNORE = "ignore"


@dataclass
class ToolMetadata:
    """MCP tool metadata."""
    tool_id: str
    name: str
    description: str
    server_id: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    capabilities: Set[str] = field(default_factory=set)
    estimated_cost: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    status: ToolStatus = ToolStatus.AVAILABLE
    requires_approval: bool = False
    rate_limit: Optional[int] = None  # calls per minute
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "server_id": self.server_id,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "capabilities": list(self.capabilities),
            "estimated_cost": self.estimated_cost,
            "avg_latency_ms": self.avg_latency_ms,
            "success_rate": self.success_rate,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "rate_limit": self.rate_limit,
        }


@dataclass
class ToolInvocation:
    """Record of a tool invocation."""
    invocation_id: str
    tool_id: str
    agent_id: str
    params: Dict[str, Any]
    started_at: float
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    success: bool = False
    latency_ms: float = 0.0
    from_cache: bool = False


@dataclass
class CachedResult:
    """Cached tool result."""
    cache_key: str
    tool_id: str
    result: Any
    created_at: float
    ttl_seconds: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_seconds


class ToolCache:
    """LRU cache for tool results with TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600.0) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CachedResult] = {}
        self._access_order: List[str] = []

    def _compute_key(self, tool_id: str, params: Dict[str, Any]) -> str:
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(f"{tool_id}:{param_str}".encode()).hexdigest()[:16]

    def get(self, tool_id: str, params: Dict[str, Any]) -> Optional[Any]:
        key = self._compute_key(tool_id, params)
        cached = self._cache.get(key)

        if cached is None:
            return None

        if cached.is_expired:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        cached.hit_count += 1
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        return cached.result

    def set(
        self,
        tool_id: str,
        params: Dict[str, Any],
        result: Any,
        ttl: Optional[float] = None,
    ) -> None:
        key = self._compute_key(tool_id, params)

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            self._cache.pop(oldest_key, None)

        self._cache[key] = CachedResult(
            cache_key=key,
            tool_id=tool_id,
            result=result,
            created_at=time.time(),
            ttl_seconds=ttl or self.default_ttl,
        )
        self._access_order.append(key)

    def invalidate(self, tool_id: str) -> int:
        """Invalidate all cached results for a tool."""
        keys_to_remove = [
            key for key, cached in self._cache.items()
            if cached.tool_id == tool_id
        ]
        for key in keys_to_remove:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
        return len(keys_to_remove)

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "total_hits": sum(c.hit_count for c in self._cache.values()),
        }


class RateLimiter:
    """Token bucket rate limiter for tool invocations."""

    def __init__(self) -> None:
        self._buckets: Dict[str, Dict[str, Any]] = {}

    def configure(self, tool_id: str, calls_per_minute: int) -> None:
        self._buckets[tool_id] = {
            "tokens": calls_per_minute,
            "max_tokens": calls_per_minute,
            "last_refill": time.time(),
            "refill_rate": calls_per_minute / 60.0,
        }

    def acquire(self, tool_id: str) -> bool:
        if tool_id not in self._buckets:
            return True

        bucket = self._buckets[tool_id]
        now = time.time()

        # Refill tokens
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            bucket["max_tokens"],
            bucket["tokens"] + elapsed * bucket["refill_rate"],
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False

    def get_wait_time(self, tool_id: str) -> float:
        if tool_id not in self._buckets:
            return 0.0

        bucket = self._buckets[tool_id]
        if bucket["tokens"] >= 1:
            return 0.0

        tokens_needed = 1 - bucket["tokens"]
        return tokens_needed / bucket["refill_rate"]


class ToolAnalytics:
    """Analytics collector for tool usage patterns."""

    def __init__(self) -> None:
        self._invocations: List[ToolInvocation] = []
        self._tool_stats: Dict[str, Dict[str, Any]] = {}

    def record(self, invocation: ToolInvocation) -> None:
        self._invocations.append(invocation)

        stats = self._tool_stats.setdefault(invocation.tool_id, {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_latency_ms": 0.0,
            "cache_hits": 0,
            "agents": set(),
        })
        stats["total_calls"] += 1
        if invocation.success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
        stats["total_latency_ms"] += invocation.latency_ms
        if invocation.from_cache:
            stats["cache_hits"] += 1
        stats["agents"].add(invocation.agent_id)

    def get_tool_stats(self, tool_id: str) -> Dict[str, Any]:
        stats = self._tool_stats.get(tool_id, {})
        if not stats:
            return {}

        total = stats.get("total_calls", 0)
        return {
            "total_calls": total,
            "success_rate": stats.get("successful_calls", 0) / max(1, total),
            "avg_latency_ms": stats.get("total_latency_ms", 0) / max(1, total),
            "cache_hit_rate": stats.get("cache_hits", 0) / max(1, total),
            "unique_agents": len(stats.get("agents", set())),
        }

    def get_usage_summary(self) -> Dict[str, Any]:
        return {
            "total_invocations": len(self._invocations),
            "tools_used": len(self._tool_stats),
            "by_tool": {
                tool_id: self.get_tool_stats(tool_id)
                for tool_id in self._tool_stats
            },
        }


class MCPToolInvoker:
    """
    Unified interface for MCP tool invocation.

    Provides tool discovery, caching, rate limiting, and analytics.
    """

    def __init__(
        self,
        executor_fn: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[Any]]] = None,
        cache_enabled: bool = True,
        cache_ttl: float = 3600.0,
        max_retries: int = 3,
        default_timeout: float = 30.0,
    ) -> None:
        self.tools: Dict[str, ToolMetadata] = {}
        self.executor_fn = executor_fn
        self.cache = ToolCache(default_ttl=cache_ttl) if cache_enabled else None
        self.rate_limiter = RateLimiter()
        self.analytics = ToolAnalytics()
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        self._approval_queue: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Tool Registry
    # -------------------------------------------------------------------------

    def register_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        server_id: str,
        input_schema: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Set[str]] = None,
        estimated_cost: float = 0.0,
        requires_approval: bool = False,
        rate_limit: Optional[int] = None,
    ) -> ToolMetadata:
        """Register an MCP tool."""
        tool = ToolMetadata(
            tool_id=tool_id,
            name=name,
            description=description,
            server_id=server_id,
            input_schema=input_schema or {},
            capabilities=capabilities or set(),
            estimated_cost=estimated_cost,
            requires_approval=requires_approval,
            rate_limit=rate_limit,
        )
        self.tools[tool_id] = tool

        if rate_limit:
            self.rate_limiter.configure(tool_id, rate_limit)

        logger.info("Registered tool: %s from server %s", name, server_id)
        return tool

    def update_tool_status(
        self,
        tool_id: str,
        status: ToolStatus,
        success_rate: Optional[float] = None,
        avg_latency_ms: Optional[float] = None,
    ) -> None:
        """Update tool operational status."""
        if tool_id in self.tools:
            self.tools[tool_id].status = status
            if success_rate is not None:
                self.tools[tool_id].success_rate = success_rate
            if avg_latency_ms is not None:
                self.tools[tool_id].avg_latency_ms = avg_latency_ms

    # -------------------------------------------------------------------------
    # Tool Discovery
    # -------------------------------------------------------------------------

    def search_tools(
        self,
        query: str,
        capabilities: Optional[Set[str]] = None,
        max_results: int = 10,
    ) -> List[ToolMetadata]:
        """Search for tools by description or capabilities."""
        query_lower = query.lower()
        matches = []

        for tool in self.tools.values():
            if tool.status == ToolStatus.UNAVAILABLE:
                continue

            # Score based on name/description match
            score = 0.0
            if query_lower in tool.name.lower():
                score += 0.5
            if query_lower in tool.description.lower():
                score += 0.3

            # Capability match
            if capabilities:
                cap_overlap = len(capabilities & tool.capabilities)
                score += 0.2 * (cap_overlap / len(capabilities))

            if score > 0:
                matches.append((tool, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in matches[:max_results]]

    def suggest_for_task(self, task_type: str) -> List[ToolMetadata]:
        """Suggest tools based on task type."""
        task_capabilities = {
            "code_analysis": {"code", "analysis", "lint"},
            "file_operations": {"file", "read", "write"},
            "search": {"search", "query", "find"},
            "transformation": {"transform", "convert", "format"},
            "validation": {"validate", "check", "verify"},
        }

        target_caps = task_capabilities.get(task_type, set())
        if not target_caps:
            return list(self.tools.values())[:5]

        return self.search_tools("", capabilities=target_caps, max_results=5)

    def get_estimated_cost(self, tool_id: str) -> float:
        """Get estimated cost for a tool invocation."""
        tool = self.tools.get(tool_id)
        return tool.estimated_cost if tool else 0.0

    # -------------------------------------------------------------------------
    # Tool Invocation
    # -------------------------------------------------------------------------

    async def invoke(
        self,
        tool_id: str,
        params: Dict[str, Any],
        agent_id: str = "system",
        timeout: Optional[float] = None,
        use_cache: bool = True,
        recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.RETRY,
    ) -> Any:
        """
        Invoke an MCP tool.

        Args:
            tool_id: ID of the tool to invoke
            params: Input parameters for the tool
            agent_id: ID of the invoking agent
            timeout: Timeout in seconds
            use_cache: Whether to use cached results
            recovery_strategy: Strategy for handling errors

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If tool not found or invocation fails
        """
        tool = self.tools.get(tool_id)
        if not tool:
            raise RuntimeError(f"Tool not found: {tool_id}")

        if tool.status == ToolStatus.UNAVAILABLE:
            raise RuntimeError(f"Tool unavailable: {tool_id}")

        # Check approval requirement
        if tool.requires_approval and not self._check_approval(tool_id, params):
            self._request_approval(tool_id, params, agent_id)
            raise RuntimeError(f"Tool requires approval: {tool_id}")

        # Check rate limit
        if not self.rate_limiter.acquire(tool_id):
            wait_time = self.rate_limiter.get_wait_time(tool_id)
            if recovery_strategy == ErrorRecoveryStrategy.FAIL_FAST:
                raise RuntimeError(f"Rate limited: {tool_id}, retry in {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        # Check cache
        if use_cache and self.cache:
            cached = self.cache.get(tool_id, params)
            if cached is not None:
                invocation = ToolInvocation(
                    invocation_id=f"inv-{int(time.time() * 1000)}",
                    tool_id=tool_id,
                    agent_id=agent_id,
                    params=params,
                    started_at=time.time(),
                    completed_at=time.time(),
                    result=cached,
                    success=True,
                    from_cache=True,
                )
                self.analytics.record(invocation)
                return cached

        # Execute with retry
        return await self._execute_with_retry(
            tool=tool,
            params=params,
            agent_id=agent_id,
            timeout=timeout or self.default_timeout,
            recovery_strategy=recovery_strategy,
            use_cache=use_cache,
        )

    async def _execute_with_retry(
        self,
        tool: ToolMetadata,
        params: Dict[str, Any],
        agent_id: str,
        timeout: float,
        recovery_strategy: ErrorRecoveryStrategy,
        use_cache: bool,
    ) -> Any:
        """Execute tool with retry logic."""
        last_error: Optional[Exception] = None
        retries = 0 if recovery_strategy == ErrorRecoveryStrategy.FAIL_FAST else self.max_retries

        for attempt in range(retries + 1):
            invocation = ToolInvocation(
                invocation_id=f"inv-{int(time.time() * 1000)}-{attempt}",
                tool_id=tool.tool_id,
                agent_id=agent_id,
                params=params,
                started_at=time.time(),
            )

            try:
                if self.executor_fn:
                    result = await asyncio.wait_for(
                        self.executor_fn(tool.server_id, tool.tool_id, params),
                        timeout=timeout,
                    )
                else:
                    # Mock execution if no executor
                    result = {"status": "success", "tool_id": tool.tool_id}

                invocation.completed_at = time.time()
                invocation.latency_ms = (invocation.completed_at - invocation.started_at) * 1000
                invocation.result = result
                invocation.success = True
                self.analytics.record(invocation)

                # Update tool stats
                self._update_tool_stats(tool, invocation)

                # Cache result
                if use_cache and self.cache:
                    self.cache.set(tool.tool_id, params, result)

                return result

            except asyncio.TimeoutError:
                last_error = RuntimeError(f"Tool timed out after {timeout}s")
                invocation.error = str(last_error)

            except Exception as e:
                last_error = e
                invocation.error = str(e)

            invocation.completed_at = time.time()
            invocation.latency_ms = (invocation.completed_at - invocation.started_at) * 1000
            self.analytics.record(invocation)

            if attempt < retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        if recovery_strategy == ErrorRecoveryStrategy.IGNORE:
            return None

        raise last_error or RuntimeError(f"Tool invocation failed: {tool.tool_id}")

    def _update_tool_stats(self, tool: ToolMetadata, invocation: ToolInvocation) -> None:
        """Update tool statistics from invocation."""
        stats = self.analytics.get_tool_stats(tool.tool_id)
        if stats:
            tool.success_rate = stats.get("success_rate", 1.0)
            tool.avg_latency_ms = stats.get("avg_latency_ms", 0.0)

    # -------------------------------------------------------------------------
    # Approval Management
    # -------------------------------------------------------------------------

    def _check_approval(self, tool_id: str, params: Dict[str, Any]) -> bool:
        """Check if invocation is approved."""
        # In production, check approval database
        return any(
            a["tool_id"] == tool_id and a.get("approved", False)
            for a in self._approval_queue
        )

    def _request_approval(
        self,
        tool_id: str,
        params: Dict[str, Any],
        agent_id: str,
    ) -> None:
        """Queue approval request."""
        self._approval_queue.append({
            "tool_id": tool_id,
            "params": params,
            "agent_id": agent_id,
            "requested_at": time.time(),
            "approved": False,
        })

    def approve_invocation(self, tool_id: str) -> bool:
        """Approve a pending tool invocation."""
        for request in self._approval_queue:
            if request["tool_id"] == tool_id and not request["approved"]:
                request["approved"] = True
                return True
        return False

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of pending approval requests."""
        return [r for r in self._approval_queue if not r["approved"]]

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    async def invoke_batch(
        self,
        invocations: List[Dict[str, Any]],
        agent_id: str = "system",
        parallel: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Invoke multiple tools in batch.

        Args:
            invocations: List of {"tool_id": str, "params": dict}
            agent_id: ID of the invoking agent
            parallel: Whether to execute in parallel

        Returns:
            List of results with same order as input
        """
        if parallel:
            tasks = [
                self.invoke(
                    tool_id=inv["tool_id"],
                    params=inv.get("params", {}),
                    agent_id=agent_id,
                    recovery_strategy=ErrorRecoveryStrategy.IGNORE,
                )
                for inv in invocations
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [
                {"tool_id": inv["tool_id"], "result": r, "error": str(r) if isinstance(r, Exception) else None}
                for inv, r in zip(invocations, results)
            ]
        else:
            results = []
            for inv in invocations:
                try:
                    result = await self.invoke(
                        tool_id=inv["tool_id"],
                        params=inv.get("params", {}),
                        agent_id=agent_id,
                    )
                    results.append({"tool_id": inv["tool_id"], "result": result, "error": None})
                except Exception as e:
                    results.append({"tool_id": inv["tool_id"], "result": None, "error": str(e)})
            return results

    # -------------------------------------------------------------------------
    # Status & Analytics
    # -------------------------------------------------------------------------

    def get_tool_status(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed tool status."""
        tool = self.tools.get(tool_id)
        if not tool:
            return None

        stats = self.analytics.get_tool_stats(tool_id)
        return {
            **tool.to_dict(),
            "analytics": stats,
            "cache_stats": self.cache.stats() if self.cache else None,
        }

    def get_usage_report(self) -> Dict[str, Any]:
        """Get comprehensive usage report."""
        return {
            "tools_registered": len(self.tools),
            "tools_by_status": {
                status.value: sum(1 for t in self.tools.values() if t.status == status)
                for status in ToolStatus
            },
            "analytics": self.analytics.get_usage_summary(),
            "cache_stats": self.cache.stats() if self.cache else None,
            "pending_approvals": len(self.get_pending_approvals()),
        }
