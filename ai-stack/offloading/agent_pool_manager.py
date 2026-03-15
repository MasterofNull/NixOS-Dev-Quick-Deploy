#!/usr/bin/env python3
"""
Free Agent Pool Management

Manages pool of free remote agents (OpenRouter free tier) with availability tracking.
Part of Phase 6 Batch 6.2: Free Agent Pool Management

Key Features:
- OpenRouter free tier monitoring
- Agent availability tracking
- Agent quality profiling
- Failover to paid agents when needed
- Agent performance benchmarking

Reference: OpenRouter API, load balancer patterns
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AgentTier(Enum):
    """Agent pricing tiers"""
    FREE = "free"
    PAID_CHEAP = "paid_cheap"  # <$0.001/1k tokens
    PAID_STANDARD = "paid_standard"  # $0.001-0.01/1k tokens
    PAID_PREMIUM = "paid_premium"  # >$0.01/1k tokens


class AgentStatus(Enum):
    """Agent availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


@dataclass
class RemoteAgent:
    """Remote agent definition"""
    agent_id: str
    name: str
    provider: str  # openrouter, anthropic, openai, etc.
    model_id: str
    tier: AgentTier
    cost_per_1k_tokens: float
    max_tokens: int
    context_window: int

    # Status tracking
    status: AgentStatus = AgentStatus.AVAILABLE
    current_load: int = 0
    max_concurrent: int = 5

    # Performance metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    avg_quality_score: float = 0.0

    # Rate limiting
    requests_per_minute: int = 0
    request_history: deque = field(default_factory=lambda: deque(maxlen=100))
    last_rate_limit: Optional[datetime] = None

    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def is_available(self) -> bool:
        """Check if agent is available"""
        return (
            self.status == AgentStatus.AVAILABLE and
            self.current_load < self.max_concurrent
        )

    def is_rate_limited(self) -> bool:
        """Check if currently rate limited"""
        if self.status == AgentStatus.RATE_LIMITED:
            # Check if rate limit expired (typically 1 minute)
            if self.last_rate_limit:
                if datetime.now() - self.last_rate_limit > timedelta(minutes=1):
                    self.status = AgentStatus.AVAILABLE
                    return False
            return True
        return False


@dataclass
class AgentPoolStats:
    """Agent pool statistics"""
    total_agents: int = 0
    available_agents: int = 0
    free_agents_available: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0


class AgentPoolManager:
    """Manage pool of free and paid remote agents"""

    def __init__(self):
        self.agents: Dict[str, RemoteAgent] = {}
        self.agent_history: Dict[str, List[Dict]] = defaultdict(list)

        self._initialize_default_agents()

        logger.info(f"Agent Pool Manager initialized with {len(self.agents)} agents")

    def _initialize_default_agents(self):
        """Initialize default free agents from OpenRouter"""
        # Free agents (OpenRouter free tier examples)
        free_agents = [
            {
                "agent_id": "free_qwen_32b",
                "name": "Qwen 32B Chat",
                "provider": "openrouter",
                "model_id": "qwen/qwen-32b-chat",
                "tier": AgentTier.FREE,
                "cost_per_1k_tokens": 0.0,
                "max_tokens": 8192,
                "context_window": 32768,
                "max_concurrent": 3,
            },
            {
                "agent_id": "free_mistral_7b",
                "name": "Mistral 7B Instruct",
                "provider": "openrouter",
                "model_id": "mistralai/mistral-7b-instruct",
                "tier": AgentTier.FREE,
                "cost_per_1k_tokens": 0.0,
                "max_tokens": 8192,
                "context_window": 8192,
                "max_concurrent": 5,
            },
            {
                "agent_id": "free_llama3_8b",
                "name": "Llama 3 8B Instruct",
                "provider": "openrouter",
                "model_id": "meta-llama/llama-3-8b-instruct",
                "tier": AgentTier.FREE,
                "cost_per_1k_tokens": 0.0,
                "max_tokens": 8192,
                "context_window": 8192,
                "max_concurrent": 5,
            },
        ]

        # Paid agents (fallback)
        paid_agents = [
            {
                "agent_id": "paid_gpt35",
                "name": "GPT-3.5 Turbo",
                "provider": "openai",
                "model_id": "gpt-3.5-turbo",
                "tier": AgentTier.PAID_CHEAP,
                "cost_per_1k_tokens": 0.0015,
                "max_tokens": 4096,
                "context_window": 16385,
                "max_concurrent": 10,
            },
            {
                "agent_id": "paid_claude_haiku",
                "name": "Claude 3 Haiku",
                "provider": "anthropic",
                "model_id": "claude-3-haiku-20240307",
                "tier": AgentTier.PAID_STANDARD,
                "cost_per_1k_tokens": 0.0025,
                "max_tokens": 4096,
                "context_window": 200000,
                "max_concurrent": 10,
            },
        ]

        # Register all agents
        for agent_data in free_agents + paid_agents:
            agent = RemoteAgent(**agent_data)
            self.register_agent(agent)

    def register_agent(self, agent: RemoteAgent):
        """Register an agent"""
        self.agents[agent.agent_id] = agent
        logger.info(
            f"Registered agent: {agent.name} "
            f"(tier={agent.tier.value}, cost=${agent.cost_per_1k_tokens}/1k)"
        )

    def get_available_agent(
        self,
        prefer_free: bool = True,
        min_context_window: Optional[int] = None,
        max_cost_per_1k: Optional[float] = None,
    ) -> Optional[RemoteAgent]:
        """Get available agent matching criteria"""
        candidates = []

        for agent in self.agents.values():
            # Check availability
            if not agent.is_available():
                continue

            # Check rate limiting
            if agent.is_rate_limited():
                continue

            # Check context window requirement
            if min_context_window and agent.context_window < min_context_window:
                continue

            # Check cost constraint
            if max_cost_per_1k is not None and agent.cost_per_1k_tokens > max_cost_per_1k:
                continue

            candidates.append(agent)

        if not candidates:
            logger.warning("No available agents matching criteria")
            return None

        # Sort candidates
        if prefer_free:
            # Prefer free, then by success rate
            candidates.sort(
                key=lambda a: (
                    a.tier != AgentTier.FREE,  # Free first
                    -a.success_rate(),  # Then by success rate
                    a.current_load,  # Then by load
                )
            )
        else:
            # Prefer by quality and cost
            candidates.sort(
                key=lambda a: (
                    -a.avg_quality_score,  # Quality first
                    a.cost_per_1k_tokens,  # Then cost
                    a.current_load,  # Then load
                )
            )

        selected = candidates[0]

        logger.info(
            f"Selected agent: {selected.name} "
            f"(tier={selected.tier.value}, load={selected.current_load}/{selected.max_concurrent})"
        )

        return selected

    def acquire_agent(self, agent_id: str) -> bool:
        """Acquire agent for use"""
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if not agent.is_available():
            return False

        agent.current_load += 1
        if agent.current_load >= agent.max_concurrent:
            agent.status = AgentStatus.BUSY

        logger.debug(f"Acquired agent {agent_id} (load: {agent.current_load})")
        return True

    def release_agent(self, agent_id: str, success: bool, latency_ms: float, quality_score: float = 0.0):
        """Release agent and update metrics"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        # Update load
        agent.current_load = max(0, agent.current_load - 1)
        if agent.current_load < agent.max_concurrent and agent.status == AgentStatus.BUSY:
            agent.status = AgentStatus.AVAILABLE

        # Update metrics
        agent.total_requests += 1
        if success:
            agent.successful_requests += 1
        else:
            agent.failed_requests += 1

        # Update latency (exponential moving average)
        if agent.avg_latency_ms == 0:
            agent.avg_latency_ms = latency_ms
        else:
            agent.avg_latency_ms = 0.9 * agent.avg_latency_ms + 0.1 * latency_ms

        # Update quality score
        if quality_score > 0:
            if agent.avg_quality_score == 0:
                agent.avg_quality_score = quality_score
            else:
                agent.avg_quality_score = 0.9 * agent.avg_quality_score + 0.1 * quality_score

        # Record request
        agent.request_history.append({
            "timestamp": datetime.now(),
            "success": success,
            "latency_ms": latency_ms,
            "quality_score": quality_score,
        })

        logger.debug(
            f"Released agent {agent_id} "
            f"(success={success}, latency={latency_ms:.1f}ms, quality={quality_score:.2f})"
        )

    def mark_rate_limited(self, agent_id: str):
        """Mark agent as rate limited"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        agent.status = AgentStatus.RATE_LIMITED
        agent.last_rate_limit = datetime.now()

        logger.warning(f"Agent {agent_id} rate limited")

    def get_pool_stats(self) -> AgentPoolStats:
        """Get pool statistics"""
        stats = AgentPoolStats()

        stats.total_agents = len(self.agents)
        stats.available_agents = sum(1 for a in self.agents.values() if a.is_available())
        stats.free_agents_available = sum(
            1 for a in self.agents.values()
            if a.is_available() and a.tier == AgentTier.FREE
        )

        stats.total_requests = sum(a.total_requests for a in self.agents.values())
        stats.successful_requests = sum(a.successful_requests for a in self.agents.values())

        # Calculate average latency
        total_latency = sum(
            a.avg_latency_ms * a.total_requests
            for a in self.agents.values()
            if a.total_requests > 0
        )
        if stats.total_requests > 0:
            stats.avg_latency_ms = total_latency / stats.total_requests

        return stats

    def benchmark_agent(self, agent_id: str) -> Dict[str, Any]:
        """Benchmark agent performance"""
        agent = self.agents.get(agent_id)
        if not agent:
            return {}

        recent_requests = list(agent.request_history)[-20:]  # Last 20 requests

        if not recent_requests:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }

        # Calculate metrics
        success_count = sum(1 for r in recent_requests if r["success"])
        avg_latency = sum(r["latency_ms"] for r in recent_requests) / len(recent_requests)
        avg_quality = sum(r["quality_score"] for r in recent_requests if r["quality_score"] > 0)
        if avg_quality > 0:
            quality_count = sum(1 for r in recent_requests if r["quality_score"] > 0)
            avg_quality /= quality_count

        return {
            "agent_id": agent_id,
            "name": agent.name,
            "tier": agent.tier.value,
            "total_requests": agent.total_requests,
            "success_rate": success_count / len(recent_requests),
            "avg_latency_ms": avg_latency,
            "avg_quality_score": avg_quality,
            "current_load": agent.current_load,
            "status": agent.status.value,
        }

    def get_failover_agent(
        self,
        failed_agent_id: str,
        allow_paid: bool = True,
    ) -> Optional[RemoteAgent]:
        """Get failover agent after failure"""
        failed_agent = self.agents.get(failed_agent_id)

        logger.info(f"Finding failover for {failed_agent_id}")

        # Try to find alternative free agent first
        for agent in self.agents.values():
            if agent.agent_id == failed_agent_id:
                continue

            if agent.tier == AgentTier.FREE and agent.is_available():
                logger.info(f"Failover to free agent: {agent.name}")
                return agent

        # If no free agents available, try paid (if allowed)
        if allow_paid:
            for agent in self.agents.values():
                if agent.agent_id == failed_agent_id:
                    continue

                if agent.tier in [AgentTier.PAID_CHEAP, AgentTier.PAID_STANDARD] and agent.is_available():
                    logger.info(f"Failover to paid agent: {agent.name} (${agent.cost_per_1k_tokens}/1k)")
                    return agent

        logger.warning("No failover agents available")
        return None


async def main():
    """Test agent pool management"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Agent Pool Management Test")
    logger.info("=" * 60)

    # Initialize manager
    manager = AgentPoolManager()

    # Test 1: Get available agent
    logger.info("\n1. Getting Available Agents:")

    # Prefer free
    agent = manager.get_available_agent(prefer_free=True)
    if agent:
        logger.info(f"  Got free agent: {agent.name}")

        # Acquire and release
        if manager.acquire_agent(agent.agent_id):
            logger.info(f"  Acquired agent: {agent.agent_id}")

            # Simulate work
            await asyncio.sleep(0.1)

            # Release with metrics
            manager.release_agent(
                agent.agent_id,
                success=True,
                latency_ms=150.5,
                quality_score=0.85,
            )
            logger.info(f"  Released agent")

    # Test 2: Pool statistics
    logger.info("\n2. Pool Statistics:")
    stats = manager.get_pool_stats()

    logger.info(f"  Total agents: {stats.total_agents}")
    logger.info(f"  Available: {stats.available_agents}")
    logger.info(f"  Free available: {stats.free_agents_available}")
    logger.info(f"  Total requests: {stats.total_requests}")
    logger.info(f"  Success rate: {stats.successful_requests / stats.total_requests * 100:.1f}%")

    # Test 3: Benchmark agents
    logger.info("\n3. Agent Benchmarks:")

    for agent_id in list(manager.agents.keys())[:3]:
        benchmark = manager.benchmark_agent(agent_id)
        if benchmark.get("status") != "no_data":
            logger.info(f"  {benchmark['name']}:")
            logger.info(f"    Tier: {benchmark['tier']}")
            logger.info(f"    Success rate: {benchmark['success_rate']:.1%}")
            logger.info(f"    Avg latency: {benchmark['avg_latency_ms']:.1f}ms")

    # Test 4: Failover
    logger.info("\n4. Failover Test:")

    # Simulate failure
    primary_agent = list(manager.agents.values())[0]
    manager.mark_rate_limited(primary_agent.agent_id)

    failover_agent = manager.get_failover_agent(primary_agent.agent_id, allow_paid=True)
    if failover_agent:
        logger.info(f"  Failover successful: {failover_agent.name}")
    else:
        logger.info(f"  No failover available")


if __name__ == "__main__":
    asyncio.run(main())
