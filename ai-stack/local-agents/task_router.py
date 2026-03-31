#!/usr/bin/env python3
"""
Task Router - Multi-Agent Delegation

Routes tasks to appropriate agents (local vs remote) based on:
- Task complexity
- Latency requirements
- Quality requirements
- Agent performance history
- Cost optimization

Part of Phase 11 Batch 11.3: Workflow Integration
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AgentTarget(Enum):
    """Agent routing targets"""
    LOCAL_AGENT = "local-agent"
    LOCAL_PLANNER = "local-planner"
    LOCAL_CHAT = "local-chat"
    REMOTE_CODEX = "remote-codex"
    REMOTE_CLAUDE = "remote-claude"
    REMOTE_QWEN = "remote-qwen"


@dataclass
class RoutingDecision:
    """Result of routing decision"""
    target: AgentTarget
    confidence: float  # 0.0-1.0
    reason: str
    fallback: Optional[AgentTarget] = None

    def to_dict(self) -> Dict:
        return {
            "target": self.target.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "fallback": self.fallback.value if self.fallback else None,
        }


class TaskRouter:
    """
    Routes tasks to most appropriate agent based on multiple factors.

    Routing Strategy:
    1. Prefer local agents for cost savings (free)
    2. Use remote for quality-critical or complex tasks
    3. Consider agent performance history
    4. Account for latency requirements
    5. Provide fallback options
    """

    def __init__(
        self,
        local_success_threshold: float = 0.75,
        complexity_threshold: float = 0.6,
        default_to_local: bool = True,
        remote_available: Optional[bool] = None,
        offline_mode: Optional[bool] = None,
        allow_degraded_local: Optional[bool] = None,
    ):
        self.local_success_threshold = local_success_threshold
        self.complexity_threshold = complexity_threshold
        self.default_to_local = default_to_local
        self.offline_mode = (
            _env_flag("LOCAL_AGENT_OFFLINE_MODE", False)
            if offline_mode is None
            else offline_mode
        )
        self.remote_available = (
            _env_flag("LOCAL_AGENT_REMOTE_AVAILABLE", not self.offline_mode)
            if remote_available is None
            else remote_available
        )
        self.allow_degraded_local = (
            _env_flag("LOCAL_AGENT_ALLOW_DEGRADED_LOCAL", True)
            if allow_degraded_local is None
            else allow_degraded_local
        )

        # Performance tracking (injected from executor)
        self.local_success_rate: float = 0.9  # Optimistic default

        logger.info(
            f"Task router initialized: local_threshold={local_success_threshold}, "
            f"complexity_threshold={complexity_threshold}, offline_mode={self.offline_mode}, "
            f"remote_available={self.remote_available}"
        )

    def route(
        self,
        objective: str,
        complexity: float = 0.5,
        latency_critical: bool = False,
        quality_critical: bool = False,
        requires_flagship: bool = False,
        requires_tools: bool = False,
    ) -> RoutingDecision:
        """
        Route task to appropriate agent.

        Args:
            objective: Task objective
            complexity: Estimated complexity (0.0-1.0)
            latency_critical: Whether low latency is critical
            quality_critical: Whether quality is critical
            requires_flagship: Whether flagship model required
            requires_tools: Whether tool use required

        Returns:
            Routing decision with target and reasoning
        """
        remote_routing_available = self.remote_available and not self.offline_mode

        # Rule 1: Flagship requirement → Remote Claude
        if requires_flagship:
            if not remote_routing_available and self.allow_degraded_local:
                return RoutingDecision(
                    target=AgentTarget.LOCAL_AGENT,
                    confidence=0.55,
                    reason="Flagship requested but remote routing unavailable; degrade to local",
                    fallback=None,
                )
            return RoutingDecision(
                target=AgentTarget.REMOTE_CLAUDE,
                confidence=1.0,
                reason="Task requires flagship model",
                fallback=None,
            )

        # Rule 2: Latency critical → Local
        if latency_critical:
            return RoutingDecision(
                target=AgentTarget.LOCAL_AGENT,
                confidence=0.9,
                reason="Latency critical, local agent preferred",
                fallback=AgentTarget.REMOTE_CODEX,
            )

        # Rule 3: Quality critical + high complexity → Remote
        if quality_critical and complexity > self.complexity_threshold:
            if not remote_routing_available and self.allow_degraded_local:
                return RoutingDecision(
                    target=AgentTarget.LOCAL_AGENT,
                    confidence=0.5,
                    reason=f"Quality critical + high complexity ({complexity:.2f}) but remote routing unavailable",
                    fallback=None,
                )
            return RoutingDecision(
                target=AgentTarget.REMOTE_CLAUDE,
                confidence=0.95,
                reason=f"Quality critical + high complexity ({complexity:.2f})",
                fallback=AgentTarget.REMOTE_CODEX,
            )

        # Rule 4: Simple task + tools available → Local
        if complexity < 0.5 and requires_tools:
            return RoutingDecision(
                target=AgentTarget.LOCAL_AGENT,
                confidence=0.85,
                reason=f"Simple task with tools ({complexity:.2f})",
                fallback=AgentTarget.REMOTE_CODEX,
            )

        # Rule 5: Local performance check
        if self.local_success_rate < self.local_success_threshold:
            # Local agents underperforming, prefer remote
            if not remote_routing_available and self.allow_degraded_local:
                return RoutingDecision(
                    target=AgentTarget.LOCAL_AGENT,
                    confidence=0.45,
                    reason=f"Local success rate low ({self.local_success_rate:.1%}) and remote routing unavailable",
                    fallback=None,
                )
            return RoutingDecision(
                target=AgentTarget.REMOTE_CODEX,
                confidence=0.8,
                reason=f"Local success rate below threshold ({self.local_success_rate:.1%})",
                fallback=AgentTarget.LOCAL_AGENT,
            )

        # Rule 6: Complexity-based routing
        if complexity > self.complexity_threshold:
            # High complexity → Remote
            if not remote_routing_available and self.allow_degraded_local:
                return RoutingDecision(
                    target=AgentTarget.LOCAL_AGENT,
                    confidence=0.5,
                    reason=f"High complexity ({complexity:.2f}) but remote routing unavailable",
                    fallback=None,
                )
            return RoutingDecision(
                target=AgentTarget.REMOTE_CODEX,
                confidence=0.75,
                reason=f"High complexity ({complexity:.2f})",
                fallback=AgentTarget.LOCAL_AGENT,
            )

        # Default: Local (cost-efficient)
        if self.default_to_local:
            return RoutingDecision(
                target=AgentTarget.LOCAL_AGENT,
                confidence=0.7,
                reason="Default to local (cost-efficient)",
                fallback=AgentTarget.REMOTE_CODEX if remote_routing_available else None,
            )
        else:
            if not remote_routing_available and self.allow_degraded_local:
                return RoutingDecision(
                    target=AgentTarget.LOCAL_AGENT,
                    confidence=0.5,
                    reason="Default remote unavailable; degrade to local",
                    fallback=None,
                )
            return RoutingDecision(
                target=AgentTarget.REMOTE_CODEX,
                confidence=0.7,
                reason="Default to remote",
                fallback=AgentTarget.LOCAL_AGENT,
            )

    def update_local_performance(self, success_rate: float):
        """Update local agent success rate"""
        self.local_success_rate = success_rate
        logger.info(f"Local success rate updated: {success_rate:.1%}")

    def estimate_complexity(self, objective: str) -> float:
        """
        Estimate task complexity from objective.

        Simple heuristic based on:
        - Objective length
        - Presence of keywords (complex, implement, design, etc.)
        - Number of requirements

        Returns:
            Complexity estimate (0.0-1.0)
        """
        # Length factor (longer = more complex)
        length_score = min(1.0, len(objective) / 500)

        # Keyword factor
        complex_keywords = [
            "implement", "design", "architect", "optimize", "refactor",
            "integrate", "complex", "advanced", "comprehensive",
        ]
        simple_keywords = [
            "get", "list", "show", "check", "read", "find",
        ]

        objective_lower = objective.lower()

        keyword_score = 0.5  # Neutral
        for keyword in complex_keywords:
            if keyword in objective_lower:
                keyword_score = min(1.0, keyword_score + 0.15)

        for keyword in simple_keywords:
            if keyword in objective_lower:
                keyword_score = max(0.0, keyword_score - 0.15)

        # Combine factors
        complexity = (length_score * 0.4) + (keyword_score * 0.6)

        return max(0.0, min(1.0, complexity))


# Global router instance
_ROUTER: Optional[TaskRouter] = None


def get_router() -> TaskRouter:
    """Get global router instance"""
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = TaskRouter()
    return _ROUTER


if __name__ == "__main__":
    # Test task router
    logging.basicConfig(level=logging.INFO)

    router = TaskRouter()

    # Test cases
    test_cases = [
        {
            "objective": "Get system information",
            "complexity": 0.2,
            "latency_critical": True,
        },
        {
            "objective": "Implement comprehensive authentication system with OAuth2",
            "complexity": 0.9,
            "quality_critical": True,
        },
        {
            "objective": "List Python files in directory",
            "complexity": 0.1,
            "requires_tools": True,
        },
        {
            "objective": "Design scalable microservices architecture",
            "complexity": 0.95,
            "requires_flagship": True,
        },
    ]

    print("\nTask Routing Decisions:\n")
    for i, test in enumerate(test_cases, 1):
        decision = router.route(**test)
        print(f"{i}. {test['objective'][:50]}...")
        print(f"   → {decision.target.value}")
        print(f"   Confidence: {decision.confidence:.1%}")
        print(f"   Reason: {decision.reason}")
        print(f"   Fallback: {decision.fallback.value if decision.fallback else 'None'}")
        print()

    # Test complexity estimation
    print("\nComplexity Estimation:\n")
    for test in test_cases:
        estimated = router.estimate_complexity(test["objective"])
        print(f"{test['objective'][:50]}...")
        print(f"   Estimated: {estimated:.2f}, Actual: {test['complexity']:.2f}")
        print()
