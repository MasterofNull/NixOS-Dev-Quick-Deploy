#!/usr/bin/env python3
"""
Multi-Tier Context Loading System

5-tier progressive context loading that minimizes token usage while maintaining quality.
Part of Phase 8 Batch 8.1: Multi-Tier Context Loading

Key Features:
- 5-tier context loading (minimal, brief, standard, detailed, exhaustive)
- Automatic tier selection based on query complexity
- Tier escalation triggers
- Tier de-escalation for resolved queries
- Learning from outcomes to optimize tier selection

Reference: Progressive disclosure patterns, information architecture
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ContextTier(Enum):
    """Context loading tiers"""
    MINIMAL = 1  # Bare minimum (10-50 tokens)
    BRIEF = 2  # Key points only (50-200 tokens)
    STANDARD = 3  # Balanced detail (200-800 tokens)
    DETAILED = 4  # Comprehensive (800-2000 tokens)
    EXHAUSTIVE = 5  # Everything (2000+ tokens)


@dataclass
class ContextChunk:
    """Single chunk of context"""
    chunk_id: str
    content: str
    tier: ContextTier
    category: str
    tokens: int
    priority: int = 0  # Higher priority loaded first
    metadata: Dict = field(default_factory=dict)


@dataclass
class TierLoadResult:
    """Result of tier loading"""
    tier: ContextTier
    chunks_loaded: List[ContextChunk]
    total_tokens: int
    load_time_ms: float
    sufficient: bool  # Was this tier sufficient for the query?


@dataclass
class TierSelectionDecision:
    """Decision on which tier to use"""
    selected_tier: ContextTier
    confidence: float
    reasoning: str
    fallback_tier: Optional[ContextTier] = None


class ContextRepository:
    """Repository of tiered context chunks"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Organized by category and tier
        self.context_chunks: Dict[str, Dict[ContextTier, List[ContextChunk]]] = defaultdict(
            lambda: defaultdict(list)
        )

        self._load_context_data()

        logger.info(f"Context Repository initialized: {data_dir}")

    def _load_context_data(self):
        """Load context chunks from storage"""
        # In production, would load from actual files
        # For now, create some example chunks

        categories = ["architecture", "api", "deployment", "troubleshooting", "security"]

        for category in categories:
            # Minimal tier
            self.add_chunk(ContextChunk(
                chunk_id=f"{category}_minimal",
                content=f"Minimal info about {category}",
                tier=ContextTier.MINIMAL,
                category=category,
                tokens=20,
                priority=10,
            ))

            # Brief tier
            self.add_chunk(ContextChunk(
                chunk_id=f"{category}_brief",
                content=f"Brief overview of {category} with key points",
                tier=ContextTier.BRIEF,
                category=category,
                tokens=100,
                priority=8,
            ))

            # Standard tier
            self.add_chunk(ContextChunk(
                chunk_id=f"{category}_standard",
                content=f"Standard explanation of {category} with examples and details",
                tier=ContextTier.STANDARD,
                category=category,
                tokens=400,
                priority=5,
            ))

            # Detailed tier
            self.add_chunk(ContextChunk(
                chunk_id=f"{category}_detailed",
                content=f"Detailed documentation for {category} including all options and edge cases",
                tier=ContextTier.DETAILED,
                category=category,
                tokens=1200,
                priority=3,
            ))

            # Exhaustive tier
            self.add_chunk(ContextChunk(
                chunk_id=f"{category}_exhaustive",
                content=f"Exhaustive reference for {category} with complete API docs and examples",
                tier=ContextTier.EXHAUSTIVE,
                category=category,
                tokens=3000,
                priority=1,
            ))

    def add_chunk(self, chunk: ContextChunk):
        """Add context chunk to repository"""
        self.context_chunks[chunk.category][chunk.tier].append(chunk)

    def get_chunks(
        self,
        category: str,
        tier: ContextTier,
    ) -> List[ContextChunk]:
        """Get chunks for category and tier"""
        # Get chunks for requested tier and all lower tiers
        chunks = []

        for t in ContextTier:
            if t.value <= tier.value:
                chunks.extend(self.context_chunks[category][t])

        # Sort by priority (higher first)
        chunks.sort(key=lambda c: c.priority, reverse=True)

        return chunks

    def get_categories(self) -> List[str]:
        """Get all available categories"""
        return list(self.context_chunks.keys())


class TierSelector:
    """Select appropriate context tier based on query"""

    def __init__(self):
        self.selection_history: List[Dict] = []
        logger.info("Tier Selector initialized")

    def select_tier(
        self,
        query: str,
        context_budget: Optional[int] = None,
    ) -> TierSelectionDecision:
        """Select appropriate tier for query"""
        # Analyze query complexity
        query_words = len(query.split())
        has_specific_question = any(w in query.lower() for w in ["how", "what", "why", "when", "where"])
        has_troubleshooting = any(w in query.lower() for w in ["error", "fix", "debug", "issue", "problem"])
        has_implementation = any(w in query.lower() for w in ["implement", "create", "build", "add"])

        # Start with standard tier
        selected_tier = ContextTier.STANDARD
        confidence = 0.7
        reasoning = "Default: standard tier for balanced detail"

        # Adjust based on query characteristics
        if query_words < 5 and has_specific_question:
            # Simple question - brief tier sufficient
            selected_tier = ContextTier.BRIEF
            confidence = 0.8
            reasoning = "Simple specific question - brief context sufficient"

        elif has_troubleshooting:
            # Troubleshooting often needs detailed context
            selected_tier = ContextTier.DETAILED
            confidence = 0.75
            reasoning = "Troubleshooting query - detailed context helpful"

        elif has_implementation and query_words > 15:
            # Complex implementation - exhaustive context
            selected_tier = ContextTier.EXHAUSTIVE
            confidence = 0.7
            reasoning = "Complex implementation task - exhaustive context needed"

        elif query_words < 3:
            # Very short query - minimal tier
            selected_tier = ContextTier.MINIMAL
            confidence = 0.6
            reasoning = "Very short query - minimal context to start"

        # Check context budget constraint
        if context_budget:
            tier_tokens = {
                ContextTier.MINIMAL: 50,
                ContextTier.BRIEF: 200,
                ContextTier.STANDARD: 800,
                ContextTier.DETAILED: 2000,
                ContextTier.EXHAUSTIVE: 5000,
            }

            if tier_tokens[selected_tier] > context_budget:
                # Downgrade to fit budget
                for tier in reversed(list(ContextTier)):
                    if tier_tokens[tier] <= context_budget:
                        fallback = selected_tier
                        selected_tier = tier
                        reasoning += f" (downgraded from {fallback.name} due to budget)"
                        confidence -= 0.1
                        break

        decision = TierSelectionDecision(
            selected_tier=selected_tier,
            confidence=confidence,
            reasoning=reasoning,
        )

        logger.info(
            f"Selected tier: {selected_tier.name} "
            f"(confidence={confidence:.2f}, query_words={query_words})"
        )

        return decision

    def should_escalate(
        self,
        current_tier: ContextTier,
        query_satisfied: bool,
        follow_up_questions: int,
    ) -> Tuple[bool, Optional[ContextTier]]:
        """Determine if tier should be escalated"""
        # Don't escalate if already exhaustive
        if current_tier == ContextTier.EXHAUSTIVE:
            return False, None

        # Don't escalate if query was satisfied
        if query_satisfied and follow_up_questions == 0:
            return False, None

        # Escalate if multiple follow-up questions
        if follow_up_questions >= 2:
            next_tier = ContextTier(current_tier.value + 1)
            logger.info(f"Escalating from {current_tier.name} to {next_tier.name}")
            return True, next_tier

        # Escalate if query not satisfied
        if not query_satisfied:
            next_tier = ContextTier(current_tier.value + 1)
            logger.info(f"Escalating due to unsatisfied query")
            return True, next_tier

        return False, None

    def should_deescalate(
        self,
        current_tier: ContextTier,
        query_satisfied: bool,
        excess_context: float,
    ) -> Tuple[bool, Optional[ContextTier]]:
        """Determine if tier should be de-escalated"""
        # Don't de-escalate if already minimal
        if current_tier == ContextTier.MINIMAL:
            return False, None

        # De-escalate if query was quickly satisfied with excess context
        if query_satisfied and excess_context > 0.5:  # >50% unused
            prev_tier = ContextTier(current_tier.value - 1)
            logger.info(f"De-escalating from {current_tier.name} to {prev_tier.name}")
            return True, prev_tier

        return False, None


class MultiTierLoader:
    """Load context progressively across tiers"""

    def __init__(self, repository: ContextRepository):
        self.repository = repository
        self.load_history: List[TierLoadResult] = []

        logger.info("Multi-Tier Loader initialized")

    async def load_context(
        self,
        query: str,
        category: str,
        tier: ContextTier,
    ) -> TierLoadResult:
        """Load context for specified tier"""
        import time

        start_time = time.time()

        logger.info(f"Loading {tier.name} context for {category}")

        # Get chunks for this tier
        chunks = self.repository.get_chunks(category, tier)

        # Calculate total tokens
        total_tokens = sum(c.tokens for c in chunks)

        # Simulate loading time
        await asyncio.sleep(0.01)

        load_time_ms = (time.time() - start_time) * 1000

        # Determine if sufficient (simplified heuristic)
        sufficient = tier.value >= ContextTier.STANDARD.value

        result = TierLoadResult(
            tier=tier,
            chunks_loaded=chunks,
            total_tokens=total_tokens,
            load_time_ms=load_time_ms,
            sufficient=sufficient,
        )

        self.load_history.append(result)

        logger.info(
            f"Loaded {len(chunks)} chunks, {total_tokens} tokens "
            f"in {load_time_ms:.1f}ms"
        )

        return result

    def get_tier_statistics(self) -> Dict[str, Any]:
        """Get statistics on tier usage"""
        tier_counts = defaultdict(int)
        tier_tokens = defaultdict(int)

        for result in self.load_history:
            tier_counts[result.tier.name] += 1
            tier_tokens[result.tier.name] += result.total_tokens

        avg_tokens = {
            tier: tokens / tier_counts[tier] if tier_counts[tier] > 0 else 0
            for tier, tokens in tier_tokens.items()
        }

        return {
            "total_loads": len(self.load_history),
            "tier_distribution": dict(tier_counts),
            "total_tokens_by_tier": dict(tier_tokens),
            "avg_tokens_by_tier": avg_tokens,
        }


class AdaptiveTierLearner:
    """Learn optimal tier selection from outcomes"""

    def __init__(self):
        self.outcome_history: List[Dict] = []
        logger.info("Adaptive Tier Learner initialized")

    def record_outcome(
        self,
        query: str,
        tier_used: ContextTier,
        success: bool,
        tokens_used: int,
        response_quality: float,
    ):
        """Record outcome of tier selection"""
        self.outcome_history.append({
            "timestamp": datetime.now(),
            "query_length": len(query.split()),
            "tier": tier_used.name,
            "success": success,
            "tokens_used": tokens_used,
            "response_quality": response_quality,
        })

    def recommend_tier(self, query_length: int) -> ContextTier:
        """Recommend tier based on historical outcomes"""
        if not self.outcome_history:
            return ContextTier.STANDARD

        # Filter similar queries
        similar = [
            o for o in self.outcome_history
            if abs(o["query_length"] - query_length) <= 5
        ]

        if not similar:
            return ContextTier.STANDARD

        # Find tier with best quality/token ratio
        tier_scores = defaultdict(list)

        for outcome in similar:
            if outcome["tokens_used"] > 0:
                efficiency = outcome["response_quality"] / outcome["tokens_used"]
                tier_scores[outcome["tier"]].append(efficiency)

        # Average efficiency per tier
        avg_efficiency = {
            tier: sum(scores) / len(scores)
            for tier, scores in tier_scores.items()
        }

        # Recommend most efficient tier
        best_tier_name = max(avg_efficiency.items(), key=lambda x: x[1])[0]
        best_tier = ContextTier[best_tier_name]

        logger.info(f"Learned recommendation: {best_tier.name} for query_length={query_length}")

        return best_tier


async def main():
    """Test multi-tier context loading"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Multi-Tier Context Loading Test")
    logger.info("=" * 60)

    # Initialize components
    data_dir = Path(".agents/context-tiers")
    repository = ContextRepository(data_dir)
    selector = TierSelector()
    loader = MultiTierLoader(repository)
    learner = AdaptiveTierLearner()

    # Test 1: Tier selection
    logger.info("\n1. Tier Selection:")

    test_queries = [
        "What is the API?",
        "How do I fix this deployment error?",
        "Implement a complete authentication system with OAuth2 and JWT",
        "Help",
    ]

    for query in test_queries:
        decision = selector.select_tier(query)
        logger.info(f"\nQuery: {query}")
        logger.info(f"  Tier: {decision.selected_tier.name}")
        logger.info(f"  Confidence: {decision.confidence:.2f}")
        logger.info(f"  Reasoning: {decision.reasoning}")

    # Test 2: Load context
    logger.info("\n2. Context Loading:")

    result = await loader.load_context(
        "How do I deploy?",
        "deployment",
        ContextTier.STANDARD,
    )

    logger.info(f"  Loaded: {len(result.chunks_loaded)} chunks")
    logger.info(f"  Tokens: {result.total_tokens}")
    logger.info(f"  Time: {result.load_time_ms:.1f}ms")

    # Test 3: Tier escalation
    logger.info("\n3. Tier Escalation:")

    should_escalate, next_tier = selector.should_escalate(
        current_tier=ContextTier.BRIEF,
        query_satisfied=False,
        follow_up_questions=2,
    )

    logger.info(f"  Should escalate: {should_escalate}")
    if next_tier:
        logger.info(f"  Next tier: {next_tier.name}")

    # Test 4: Learning
    logger.info("\n4. Adaptive Learning:")

    # Record some outcomes
    for i in range(10):
        learner.record_outcome(
            query="test query",
            tier_used=ContextTier.STANDARD,
            success=True,
            tokens_used=500,
            response_quality=0.85,
        )

    recommended = learner.recommend_tier(query_length=5)
    logger.info(f"  Recommended tier: {recommended.name}")

    # Test 5: Statistics
    logger.info("\n5. Usage Statistics:")

    stats = loader.get_tier_statistics()
    logger.info(f"  Total loads: {stats['total_loads']}")
    logger.info(f"  Distribution: {stats['tier_distribution']}")


if __name__ == "__main__":
    asyncio.run(main())
