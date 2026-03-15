#!/usr/bin/env python3
"""
Online Learning Pipeline

Real-time incremental learning from every interaction.
Part of Phase 10 Batch 10.1: Online Learning Pipeline

Key Features:
- Incremental model updates
- Real-time hint quality adjustment
- Live pattern mining
- Adaptive routing based on recent performance
- Online A/B testing
"""

import asyncio
import hashlib
import json
import logging
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class UpdateStrategy(Enum):
    """Incremental update strategies"""
    IMMEDIATE = "immediate"  # Update on every example
    BATCH = "batch"  # Update on batches
    THRESHOLD = "threshold"  # Update when threshold reached
    SCHEDULED = "scheduled"  # Update on schedule


@dataclass
class LearningExample:
    """Single learning example"""
    example_id: str
    query: str
    response: str
    feedback: float  # 0-1 quality score
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ModelUpdate:
    """Incremental model update"""
    update_id: str
    strategy: UpdateStrategy
    examples_count: int
    improvement: float
    applied_at: datetime = field(default_factory=datetime.now)


class IncrementalLearner:
    """Incremental learning engine"""

    def __init__(self, update_strategy: UpdateStrategy = UpdateStrategy.BATCH):
        self.update_strategy = update_strategy
        self.learning_buffer: deque = deque(maxlen=100)
        self.update_history: List[ModelUpdate] = []

        # Model parameters (simplified - would be actual model in production)
        self.model_weights: Dict[str, float] = {
            "term_overlap": 0.3,
            "semantic_sim": 0.4,
            "context_relevance": 0.2,
            "novelty": 0.1,
        }

        self.learning_rate = 0.01
        self.batch_size = 10

        logger.info(f"Incremental Learner initialized (strategy={update_strategy.value})")

    async def add_example(self, example: LearningExample):
        """Add example to learning buffer"""
        self.learning_buffer.append(example)

        logger.debug(f"Added learning example: {example.example_id}")

        # Trigger update based on strategy
        if self.update_strategy == UpdateStrategy.IMMEDIATE:
            await self._update_model([example])

        elif self.update_strategy == UpdateStrategy.BATCH:
            if len(self.learning_buffer) >= self.batch_size:
                await self._update_model_from_buffer()

        elif self.update_strategy == UpdateStrategy.THRESHOLD:
            avg_quality = sum(e.feedback for e in self.learning_buffer) / len(self.learning_buffer)
            if avg_quality < 0.7 and len(self.learning_buffer) >= 5:
                await self._update_model_from_buffer()

    async def _update_model_from_buffer(self):
        """Update model from accumulated examples"""
        if not self.learning_buffer:
            return

        examples = list(self.learning_buffer)
        self.learning_buffer.clear()

        await self._update_model(examples)

    async def _update_model(self, examples: List[LearningExample]):
        """Apply incremental model update"""
        logger.info(f"Updating model with {len(examples)} examples")

        # Calculate gradients (simplified)
        gradients = self._calculate_gradients(examples)

        # Apply gradients
        old_weights = self.model_weights.copy()

        for param, gradient in gradients.items():
            self.model_weights[param] += self.learning_rate * gradient

        # Normalize weights
        total = sum(self.model_weights.values())
        for param in self.model_weights:
            self.model_weights[param] /= total

        # Calculate improvement
        improvement = self._estimate_improvement(old_weights, self.model_weights)

        # Record update
        update = ModelUpdate(
            update_id=self._generate_update_id(),
            strategy=self.update_strategy,
            examples_count=len(examples),
            improvement=improvement,
        )

        self.update_history.append(update)

        logger.info(f"Model updated: improvement={improvement:.3f}")

    def _calculate_gradients(self, examples: List[LearningExample]) -> Dict[str, float]:
        """Calculate parameter gradients from examples"""
        gradients = defaultdict(float)

        for example in examples:
            # Simple gradient: increase weight if feedback good
            for param in self.model_weights.keys():
                gradient = (example.feedback - 0.5) * 0.1  # Simplified
                gradients[param] += gradient

        # Average gradients
        for param in gradients:
            gradients[param] /= len(examples)

        return dict(gradients)

    def _estimate_improvement(
        self,
        old_weights: Dict[str, float],
        new_weights: Dict[str, float],
    ) -> float:
        """Estimate improvement from weight change"""
        # Simple: sum of absolute changes
        total_change = sum(
            abs(new_weights[k] - old_weights[k])
            for k in old_weights.keys()
        )

        return total_change

    def _generate_update_id(self) -> str:
        """Generate unique update ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]


class HintQualityAdjuster:
    """Real-time hint quality adjustment"""

    def __init__(self):
        self.hint_scores: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.hint_adjustments: Dict[str, float] = {}

        logger.info("Hint Quality Adjuster initialized")

    def record_hint_feedback(self, hint_id: str, quality_score: float):
        """Record feedback for hint"""
        self.hint_scores[hint_id].append({
            "timestamp": datetime.now(),
            "score": quality_score,
        })

        # Adjust hint priority in real-time
        self._adjust_hint_priority(hint_id)

    def _adjust_hint_priority(self, hint_id: str):
        """Adjust hint priority based on recent feedback"""
        scores = self.hint_scores[hint_id]

        if not scores:
            return

        # Calculate recent average
        recent = list(scores)[-10:]  # Last 10
        avg_score = sum(s["score"] for s in recent) / len(recent)

        # Adjustment factor: -0.2 to +0.2
        baseline = 0.7
        adjustment = (avg_score - baseline) * 0.2

        self.hint_adjustments[hint_id] = adjustment

        logger.debug(f"Adjusted hint {hint_id}: {adjustment:+.2f}")

    def get_hint_adjustment(self, hint_id: str) -> float:
        """Get priority adjustment for hint"""
        return self.hint_adjustments.get(hint_id, 0.0)

    def get_top_hints(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get top-rated hints"""
        hint_ratings = []

        for hint_id, scores in self.hint_scores.items():
            if scores:
                recent = list(scores)[-10:]
                avg_score = sum(s["score"] for s in recent) / len(recent)
                hint_ratings.append((hint_id, avg_score))

        hint_ratings.sort(key=lambda x: x[1], reverse=True)

        return hint_ratings[:limit]


class LivePatternMiner:
    """Mine patterns from live interactions"""

    def __init__(self):
        self.interaction_history: deque = deque(maxlen=1000)
        self.patterns: Dict[str, Dict[str, Any]] = {}

        logger.info("Live Pattern Miner initialized")

    async def mine_interaction(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
    ):
        """Mine patterns from interaction"""
        self.interaction_history.append({
            "timestamp": datetime.now(),
            "query": query,
            "response": response,
            "context": context,
        })

        # Extract patterns
        await self._extract_patterns()

    async def _extract_patterns(self):
        """Extract patterns from recent interactions"""
        if len(self.interaction_history) < 10:
            return

        recent = list(self.interaction_history)[-50:]

        # Pattern 1: Query type frequency
        query_types = defaultdict(int)
        for interaction in recent:
            query_type = self._classify_query(interaction["query"])
            query_types[query_type] += 1

        self.patterns["query_types"] = dict(query_types)

        # Pattern 2: Common query terms
        term_freq = defaultdict(int)
        for interaction in recent:
            terms = interaction["query"].lower().split()
            for term in terms:
                if len(term) > 3:  # Skip short words
                    term_freq[term] += 1

        # Top 10 terms
        top_terms = sorted(term_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        self.patterns["common_terms"] = dict(top_terms)

        # Pattern 3: Temporal patterns
        hour_dist = defaultdict(int)
        for interaction in recent:
            hour = interaction["timestamp"].hour
            hour_dist[hour] += 1

        self.patterns["hourly_distribution"] = dict(hour_dist)

        logger.debug(f"Extracted {len(self.patterns)} pattern types")

    def _classify_query(self, query: str) -> str:
        """Classify query type"""
        query_lower = query.lower()

        if any(w in query_lower for w in ["how", "what", "why"]):
            return "question"
        elif any(w in query_lower for w in ["implement", "create", "build"]):
            return "implementation"
        elif any(w in query_lower for w in ["fix", "debug", "error"]):
            return "troubleshooting"
        elif any(w in query_lower for w in ["explain", "describe"]):
            return "explanation"
        else:
            return "other"

    def get_patterns(self) -> Dict[str, Any]:
        """Get discovered patterns"""
        return self.patterns


class AdaptiveRouter:
    """Adaptive routing based on recent performance"""

    def __init__(self):
        self.route_performance: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.route_preferences: Dict[str, float] = {}

        logger.info("Adaptive Router initialized")

    def record_route_performance(
        self,
        route_id: str,
        success: bool,
        latency_ms: float,
        quality_score: float,
    ):
        """Record routing performance"""
        self.route_performance[route_id].append({
            "timestamp": datetime.now(),
            "success": success,
            "latency_ms": latency_ms,
            "quality_score": quality_score,
        })

        # Update preferences
        self._update_preferences()

    def _update_preferences(self):
        """Update route preferences based on performance"""
        for route_id, history in self.route_performance.items():
            if not history:
                continue

            recent = list(history)[-20:]  # Last 20

            # Calculate metrics
            success_rate = sum(1 for r in recent if r["success"]) / len(recent)
            avg_quality = sum(r["quality_score"] for r in recent) / len(recent)
            avg_latency = sum(r["latency_ms"] for r in recent) / len(recent)

            # Preference score (higher is better)
            # Fast + high quality + reliable = high score
            latency_score = max(0, 1.0 - (avg_latency / 5000))  # 5s baseline
            preference = (
                success_rate * 0.4 +
                avg_quality * 0.4 +
                latency_score * 0.2
            )

            self.route_preferences[route_id] = preference

    def select_route(self, available_routes: List[str]) -> str:
        """Select best route based on preferences"""
        if not available_routes:
            raise ValueError("No routes available")

        # Get preferences for available routes
        route_scores = []
        for route in available_routes:
            score = self.route_preferences.get(route, 0.5)  # Default: neutral
            route_scores.append((route, score))

        # Sort by score
        route_scores.sort(key=lambda x: x[1], reverse=True)

        selected = route_scores[0][0]

        logger.debug(
            f"Selected route: {selected} "
            f"(score={route_scores[0][1]:.2f})"
        )

        return selected


class OnlineABTester:
    """Online A/B testing"""

    def __init__(self):
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self.experiment_results: Dict[str, List[Dict]] = defaultdict(list)

        logger.info("Online A/B Tester initialized")

    def create_experiment(
        self,
        experiment_id: str,
        variant_a: str,
        variant_b: str,
        traffic_split: float = 0.5,
    ):
        """Create A/B experiment"""
        self.experiments[experiment_id] = {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "traffic_split": traffic_split,
            "started_at": datetime.now(),
        }

        logger.info(
            f"Created experiment {experiment_id}: "
            f"{variant_a} vs {variant_b} ({traffic_split:.0%} split)"
        )

    def select_variant(self, experiment_id: str) -> str:
        """Select variant for user"""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Random assignment based on traffic split
        if random.random() < experiment["traffic_split"]:
            return experiment["variant_a"]
        else:
            return experiment["variant_b"]

    def record_outcome(
        self,
        experiment_id: str,
        variant: str,
        success: bool,
        metric_value: float,
    ):
        """Record experiment outcome"""
        self.experiment_results[experiment_id].append({
            "timestamp": datetime.now(),
            "variant": variant,
            "success": success,
            "metric_value": metric_value,
        })

    def analyze_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Analyze experiment results"""
        results = self.experiment_results.get(experiment_id, [])
        experiment = self.experiments.get(experiment_id)

        if not results or not experiment:
            return {"status": "insufficient_data"}

        # Separate by variant
        variant_a = experiment["variant_a"]
        variant_b = experiment["variant_b"]

        a_results = [r for r in results if r["variant"] == variant_a]
        b_results = [r for r in results if r["variant"] == variant_b]

        if not a_results or not b_results:
            return {"status": "insufficient_data"}

        # Calculate metrics
        a_success_rate = sum(1 for r in a_results if r["success"]) / len(a_results)
        b_success_rate = sum(1 for r in b_results if r["success"]) / len(b_results)

        a_avg_metric = sum(r["metric_value"] for r in a_results) / len(a_results)
        b_avg_metric = sum(r["metric_value"] for r in b_results) / len(b_results)

        # Determine winner
        if abs(a_success_rate - b_success_rate) < 0.05:
            winner = "tie"
        elif a_success_rate > b_success_rate:
            winner = variant_a
        else:
            winner = variant_b

        return {
            "experiment_id": experiment_id,
            "variant_a": {
                "name": variant_a,
                "success_rate": a_success_rate,
                "avg_metric": a_avg_metric,
                "sample_size": len(a_results),
            },
            "variant_b": {
                "name": variant_b,
                "success_rate": b_success_rate,
                "avg_metric": b_avg_metric,
                "sample_size": len(b_results),
            },
            "winner": winner,
        }


async def main():
    """Test online learning pipeline"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Online Learning Pipeline Test")
    logger.info("=" * 60)

    # Test 1: Incremental learning
    logger.info("\n1. Incremental Learning:")

    learner = IncrementalLearner(update_strategy=UpdateStrategy.BATCH)

    for i in range(15):
        example = LearningExample(
            example_id=f"example_{i}",
            query=f"query {i}",
            response=f"response {i}",
            feedback=0.5 + (i * 0.03),  # Increasing quality
        )

        await learner.add_example(example)

    logger.info(f"  Model updates: {len(learner.update_history)}")
    logger.info(f"  Current weights: {learner.model_weights}")

    # Test 2: Hint quality adjustment
    logger.info("\n2. Hint Quality Adjustment:")

    adjuster = HintQualityAdjuster()

    adjuster.record_hint_feedback("hint_1", 0.9)
    adjuster.record_hint_feedback("hint_1", 0.85)
    adjuster.record_hint_feedback("hint_2", 0.6)
    adjuster.record_hint_feedback("hint_2", 0.55)

    top_hints = adjuster.get_top_hints(limit=2)
    logger.info(f"  Top hints:")
    for hint_id, score in top_hints:
        logger.info(f"    {hint_id}: {score:.2f}")

    # Test 3: Pattern mining
    logger.info("\n3. Live Pattern Mining:")

    miner = LivePatternMiner()

    for i in range(20):
        await miner.mine_interaction(
            query=f"How do I configure nixos module {i % 3}?",
            response="Configuration steps...",
            context={"domain": "nixos"},
        )

    patterns = miner.get_patterns()
    logger.info(f"  Patterns discovered: {list(patterns.keys())}")

    if "query_types" in patterns:
        logger.info(f"  Query types: {patterns['query_types']}")

    # Test 4: Adaptive routing
    logger.info("\n4. Adaptive Routing:")

    router = AdaptiveRouter()

    router.record_route_performance("route_a", True, 1000, 0.9)
    router.record_route_performance("route_a", True, 1200, 0.85)
    router.record_route_performance("route_b", True, 2000, 0.8)
    router.record_route_performance("route_b", False, 3000, 0.5)

    selected = router.select_route(["route_a", "route_b"])
    logger.info(f"  Selected route: {selected}")

    # Test 5: A/B testing
    logger.info("\n5. Online A/B Testing:")

    tester = OnlineABTester()

    tester.create_experiment("test_1", "variant_a", "variant_b", traffic_split=0.5)

    for _ in range(100):
        variant = tester.select_variant("test_1")
        success = random.random() > (0.3 if variant == "variant_a" else 0.4)
        metric = random.uniform(0.5, 1.0)

        tester.record_outcome("test_1", variant, success, metric)

    analysis = tester.analyze_experiment("test_1")
    logger.info(f"  Winner: {analysis.get('winner')}")
    logger.info(f"  Variant A success: {analysis['variant_a']['success_rate']:.2%}")
    logger.info(f"  Variant B success: {analysis['variant_b']['success_rate']:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
