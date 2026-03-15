#!/usr/bin/env python3
"""
Work Classification & Routing Engine

Intelligent task classification and routing to optimize between local and remote execution.
Part of Phase 6 Batch 6.1: Work Classification & Routing

Key Features:
- Task complexity classification
- Suitability scoring for remote vs local execution
- Routing policy engine with configurable rules
- Cost-benefit analysis for routing decisions
- Quality prediction for routing choices

Reference: Load balancing and task scheduling algorithms
"""

import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""
    TRIVIAL = "trivial"  # <1 min, simple queries
    SIMPLE = "simple"  # 1-5 min, straightforward tasks
    MODERATE = "moderate"  # 5-15 min, requires reasoning
    COMPLEX = "complex"  # 15-60 min, multi-step tasks
    VERY_COMPLEX = "very_complex"  # >60 min, research-heavy


class ExecutionTarget(Enum):
    """Where to execute task"""
    LOCAL_ONLY = "local_only"  # Must run locally
    REMOTE_PREFERRED = "remote_preferred"  # Prefer remote
    REMOTE_ONLY = "remote_only"  # Must run remote
    HYBRID = "hybrid"  # Split across local + remote


@dataclass
class TaskFeatures:
    """Extracted task features for classification"""
    word_count: int
    has_code_generation: bool
    has_code_analysis: bool
    requires_context: bool
    requires_tools: bool
    is_creative: bool
    is_factual: bool
    estimated_tokens: int
    domain: str = "general"


@dataclass
class RoutingDecision:
    """Routing decision result"""
    task_id: str
    target: ExecutionTarget
    complexity: TaskComplexity
    confidence: float  # 0-1
    estimated_cost_usd: float
    estimated_quality: float  # 0-1
    reasoning: str
    features: TaskFeatures
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RoutingPolicy:
    """Routing policy rule"""
    policy_id: str
    name: str
    condition: Callable[[TaskFeatures], bool]
    target: ExecutionTarget
    priority: int  # Higher priority rules checked first
    description: str


class TaskClassifier:
    """Classify tasks by complexity and characteristics"""

    def __init__(self):
        self.complexity_thresholds = {
            TaskComplexity.TRIVIAL: 100,  # tokens
            TaskComplexity.SIMPLE: 500,
            TaskComplexity.MODERATE: 2000,
            TaskComplexity.COMPLEX: 8000,
            TaskComplexity.VERY_COMPLEX: float('inf'),
        }

        logger.info("Task Classifier initialized")

    def classify(self, task_description: str, context: Optional[Dict] = None) -> Tuple[TaskComplexity, TaskFeatures]:
        """Classify task complexity and extract features"""
        features = self._extract_features(task_description, context)
        complexity = self._determine_complexity(features)

        logger.debug(
            f"Task classified: {complexity.value} "
            f"({features.estimated_tokens} tokens, domain={features.domain})"
        )

        return complexity, features

    def _extract_features(self, task_description: str, context: Optional[Dict]) -> TaskFeatures:
        """Extract task features"""
        text = task_description.lower()
        words = text.split()
        word_count = len(words)

        # Code-related keywords
        code_gen_keywords = {"write", "create", "implement", "generate", "build", "code"}
        code_analysis_keywords = {"analyze", "review", "debug", "fix", "refactor", "optimize"}

        has_code_generation = any(kw in text for kw in code_gen_keywords)
        has_code_analysis = any(kw in text for kw in code_analysis_keywords)

        # Context requirements
        requires_context = bool(context and len(context) > 0)

        # Tool usage indicators
        tool_keywords = {"execute", "run", "test", "deploy", "install"}
        requires_tools = any(kw in text for kw in tool_keywords)

        # Creative vs factual
        creative_keywords = {"design", "create", "brainstorm", "propose", "suggest"}
        factual_keywords = {"what", "when", "where", "who", "how many", "list"}

        is_creative = any(kw in text for kw in creative_keywords)
        is_factual = any(kw in text for kw in factual_keywords)

        # Estimate tokens (rough heuristic: 1.3 tokens per word + context)
        estimated_tokens = int(word_count * 1.3)
        if context:
            context_str = json.dumps(context)
            estimated_tokens += int(len(context_str.split()) * 1.3)

        # Determine domain
        domain = self._classify_domain(text)

        return TaskFeatures(
            word_count=word_count,
            has_code_generation=has_code_generation,
            has_code_analysis=has_code_analysis,
            requires_context=requires_context,
            requires_tools=requires_tools,
            is_creative=is_creative,
            is_factual=is_factual,
            estimated_tokens=estimated_tokens,
            domain=domain,
        )

    def _determine_complexity(self, features: TaskFeatures) -> TaskComplexity:
        """Determine task complexity from features"""
        # Base complexity on token estimate
        base_complexity = TaskComplexity.TRIVIAL

        for complexity, threshold in self.complexity_thresholds.items():
            if features.estimated_tokens <= threshold:
                base_complexity = complexity
                break

        # Adjust based on features
        if features.requires_tools:
            # Tool usage increases complexity
            if base_complexity == TaskComplexity.TRIVIAL:
                base_complexity = TaskComplexity.SIMPLE
            elif base_complexity == TaskComplexity.SIMPLE:
                base_complexity = TaskComplexity.MODERATE

        if features.has_code_generation and features.requires_context:
            # Code generation with context is complex
            if base_complexity.value in ["trivial", "simple"]:
                base_complexity = TaskComplexity.MODERATE

        return base_complexity

    def _classify_domain(self, text: str) -> str:
        """Classify task domain"""
        domains = {
            "code": ["code", "function", "class", "python", "javascript", "implementation"],
            "security": ["security", "vulnerability", "authentication", "encryption"],
            "devops": ["deploy", "docker", "kubernetes", "infrastructure"],
            "data": ["data", "database", "sql", "query", "analysis"],
            "documentation": ["document", "readme", "guide", "tutorial"],
        }

        for domain, keywords in domains.items():
            if any(kw in text for kw in keywords):
                return domain

        return "general"


class SuitabilityScorer:
    """Score task suitability for remote vs local execution"""

    def __init__(self):
        # Remote agent strengths
        self.remote_strengths = {
            "creative_writing",
            "general_reasoning",
            "factual_knowledge",
            "simple_code_generation",
        }

        # Local agent strengths
        self.local_strengths = {
            "tool_execution",
            "context_heavy_tasks",
            "iterative_debugging",
            "security_sensitive",
        }

        logger.info("Suitability Scorer initialized")

    def score_remote_suitability(
        self,
        features: TaskFeatures,
        complexity: TaskComplexity,
    ) -> float:
        """Score suitability for remote execution (0-1)"""
        score = 0.5  # Neutral baseline

        # Favor remote for simple, factual tasks
        if complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            score += 0.2

        if features.is_factual:
            score += 0.15

        if features.is_creative:
            score += 0.1

        # Disfavor remote for tool-heavy tasks
        if features.requires_tools:
            score -= 0.3

        # Disfavor remote for context-heavy tasks (token cost)
        if features.requires_context and features.estimated_tokens > 2000:
            score -= 0.2

        # Security-sensitive tasks stay local
        if features.domain == "security":
            score -= 0.4

        # Code analysis can go remote
        if features.has_code_analysis and not features.requires_tools:
            score += 0.1

        return max(0.0, min(1.0, score))

    def score_local_suitability(
        self,
        features: TaskFeatures,
        complexity: TaskComplexity,
    ) -> float:
        """Score suitability for local execution (0-1)"""
        # Inverse of remote score, with adjustments
        remote_score = self.score_remote_suitability(features, complexity)
        local_score = 1.0 - remote_score

        # Boost local for tool usage
        if features.requires_tools:
            local_score += 0.2

        # Boost local for security domain
        if features.domain == "security":
            local_score += 0.3

        return max(0.0, min(1.0, local_score))


class CostBenefitAnalyzer:
    """Analyze cost-benefit of routing decisions"""

    def __init__(
        self,
        local_cost_per_1k_tokens: float = 0.0,  # Free
        remote_free_cost_per_1k_tokens: float = 0.0,  # Free tier
        remote_paid_cost_per_1k_tokens: float = 0.002,  # GPT-3.5 pricing
    ):
        self.local_cost_per_1k = local_cost_per_1k_tokens
        self.remote_free_cost_per_1k = remote_free_cost_per_1k_tokens
        self.remote_paid_cost_per_1k = remote_paid_cost_per_1k_tokens

        logger.info("Cost-Benefit Analyzer initialized")

    def analyze(
        self,
        features: TaskFeatures,
        target: ExecutionTarget,
        use_paid_remote: bool = False,
    ) -> Tuple[float, float]:
        """Analyze cost and estimated quality"""
        # Calculate cost
        tokens = features.estimated_tokens
        cost_usd = 0.0

        if target == ExecutionTarget.LOCAL_ONLY:
            cost_usd = (tokens / 1000) * self.local_cost_per_1k

        elif target in [ExecutionTarget.REMOTE_PREFERRED, ExecutionTarget.REMOTE_ONLY]:
            if use_paid_remote:
                cost_usd = (tokens / 1000) * self.remote_paid_cost_per_1k
            else:
                cost_usd = (tokens / 1000) * self.remote_free_cost_per_1k

        elif target == ExecutionTarget.HYBRID:
            # Split cost
            cost_usd = (tokens / 1000) * (self.local_cost_per_1k + self.remote_free_cost_per_1k) / 2

        # Estimate quality (simplified)
        estimated_quality = self._estimate_quality(features, target)

        return cost_usd, estimated_quality

    def _estimate_quality(self, features: TaskFeatures, target: ExecutionTarget) -> float:
        """Estimate output quality (0-1)"""
        # Baseline quality
        quality = 0.7

        # Remote agents generally better for creative/factual
        if target in [ExecutionTarget.REMOTE_PREFERRED, ExecutionTarget.REMOTE_ONLY]:
            if features.is_creative or features.is_factual:
                quality += 0.15

        # Local better for tool-heavy and context-heavy
        if target == ExecutionTarget.LOCAL_ONLY:
            if features.requires_tools or features.requires_context:
                quality += 0.2

        # Hybrid gets best of both
        if target == ExecutionTarget.HYBRID:
            quality += 0.1

        return min(1.0, quality)


class RoutingPolicyEngine:
    """Apply routing policies to make decisions"""

    def __init__(self):
        self.policies: List[RoutingPolicy] = []
        self._load_default_policies()

        logger.info(f"Routing Policy Engine initialized with {len(self.policies)} policies")

    def _load_default_policies(self):
        """Load default routing policies"""
        # Security-sensitive tasks stay local
        self.add_policy(RoutingPolicy(
            policy_id="security_local",
            name="Security tasks stay local",
            condition=lambda f: f.domain == "security",
            target=ExecutionTarget.LOCAL_ONLY,
            priority=100,
            description="Security-sensitive tasks must run locally",
        ))

        # Tool-heavy tasks stay local
        self.add_policy(RoutingPolicy(
            policy_id="tools_local",
            name="Tool execution local",
            condition=lambda f: f.requires_tools,
            target=ExecutionTarget.LOCAL_ONLY,
            priority=90,
            description="Tasks requiring tools run locally",
        ))

        # Simple factual queries go remote
        self.add_policy(RoutingPolicy(
            policy_id="simple_factual_remote",
            name="Simple factual to remote",
            condition=lambda f: f.is_factual and f.estimated_tokens < 500,
            target=ExecutionTarget.REMOTE_PREFERRED,
            priority=50,
            description="Simple factual queries use free remote agents",
        ))

        # Creative tasks go remote
        self.add_policy(RoutingPolicy(
            policy_id="creative_remote",
            name="Creative tasks remote",
            condition=lambda f: f.is_creative and not f.requires_tools,
            target=ExecutionTarget.REMOTE_PREFERRED,
            priority=60,
            description="Creative tasks benefit from remote flagship models",
        ))

        # Code generation can go remote if simple
        self.add_policy(RoutingPolicy(
            policy_id="simple_codegen_remote",
            name="Simple code generation remote",
            condition=lambda f: f.has_code_generation and f.estimated_tokens < 1000 and not f.requires_tools,
            target=ExecutionTarget.REMOTE_PREFERRED,
            priority=40,
            description="Simple code generation tasks",
        ))

        # Very complex tasks use hybrid
        self.add_policy(RoutingPolicy(
            policy_id="complex_hybrid",
            name="Complex tasks hybrid",
            condition=lambda f: f.estimated_tokens > 5000,
            target=ExecutionTarget.HYBRID,
            priority=30,
            description="Very complex tasks split across local and remote",
        ))

    def add_policy(self, policy: RoutingPolicy):
        """Add routing policy"""
        self.policies.append(policy)
        # Sort by priority (descending)
        self.policies.sort(reverse=True, key=lambda p: p.priority)

    def route(
        self,
        task_id: str,
        complexity: TaskComplexity,
        features: TaskFeatures,
    ) -> RoutingDecision:
        """Make routing decision"""
        # Apply policies in priority order
        for policy in self.policies:
            if policy.condition(features):
                target = policy.target
                reasoning = f"Policy: {policy.name} - {policy.description}"

                logger.info(
                    f"Task {task_id} routed to {target.value} "
                    f"(policy: {policy.name})"
                )

                # Calculate cost and quality
                analyzer = CostBenefitAnalyzer()
                cost, quality = analyzer.analyze(features, target)

                return RoutingDecision(
                    task_id=task_id,
                    target=target,
                    complexity=complexity,
                    confidence=0.9,  # High confidence for policy match
                    estimated_cost_usd=cost,
                    estimated_quality=quality,
                    reasoning=reasoning,
                    features=features,
                )

        # No policy matched - use default routing
        scorer = SuitabilityScorer()
        remote_score = scorer.score_remote_suitability(features, complexity)
        local_score = scorer.score_local_suitability(features, complexity)

        if remote_score > local_score:
            target = ExecutionTarget.REMOTE_PREFERRED
        else:
            target = ExecutionTarget.LOCAL_ONLY

        reasoning = f"No policy match - scores: remote={remote_score:.2f}, local={local_score:.2f}"

        analyzer = CostBenefitAnalyzer()
        cost, quality = analyzer.analyze(features, target)

        return RoutingDecision(
            task_id=task_id,
            target=target,
            complexity=complexity,
            confidence=max(remote_score, local_score),
            estimated_cost_usd=cost,
            estimated_quality=quality,
            reasoning=reasoning,
            features=features,
        )


async def main():
    """Test work classification and routing"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Work Classification & Routing Test")
    logger.info("=" * 60)

    # Initialize components
    classifier = TaskClassifier()
    policy_engine = RoutingPolicyEngine()

    # Test tasks
    test_tasks = [
        ("task_1", "What is the capital of France?", None),
        ("task_2", "Implement a binary search algorithm in Python", None),
        ("task_3", "Analyze this codebase for security vulnerabilities", {"files": 50}),
        ("task_4", "Run the test suite and fix any failing tests", None),
        ("task_5", "Write a creative story about AI", None),
        ("task_6", "Refactor the authentication module using mTLS", {"context": "large"}),
    ]

    logger.info("\nRouting Decisions:\n")

    for task_id, description, context in test_tasks:
        # Classify task
        complexity, features = classifier.classify(description, context)

        # Route task
        decision = policy_engine.route(task_id, complexity, features)

        logger.info(f"Task: {description}")
        logger.info(f"  Complexity: {complexity.value}")
        logger.info(f"  Target: {decision.target.value}")
        logger.info(f"  Confidence: {decision.confidence:.2f}")
        logger.info(f"  Est. Cost: ${decision.estimated_cost_usd:.4f}")
        logger.info(f"  Est. Quality: {decision.estimated_quality:.2f}")
        logger.info(f"  Reasoning: {decision.reasoning}")
        logger.info(f"  Tokens: {features.estimated_tokens}")
        logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
