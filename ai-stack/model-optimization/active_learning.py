#!/usr/bin/env python3
"""
Active Learning for Data Selection

Sophisticated active learning strategies for selecting the most valuable
training examples to improve model performance.
Part of Phase 5 Batch 5.1: Training Data Collection & Curation

Key Features:
- Uncertainty sampling (entropy, margin, least confidence)
- Diversity sampling (clustering, core-set selection)
- Query-by-committee ensemble disagreement
- Hybrid acquisition functions
- Budget-aware selection
- Online active learning updates

Reference: Active Learning literature, Core-Set selection
"""

import asyncio
import hashlib
import json
import logging
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

import numpy as np

logger = logging.getLogger(__name__)

# Runtime writable state
ACTIVE_LEARNING_STATE = Path(os.getenv(
    "ACTIVE_LEARNING_STATE",
    "/var/lib/ai-stack/hybrid/active-learning"
))


class AcquisitionStrategy(Enum):
    """Active learning acquisition strategies"""
    UNCERTAINTY = "uncertainty"  # Select most uncertain samples
    DIVERSITY = "diversity"  # Select most diverse samples
    QBC = "qbc"  # Query-by-committee disagreement
    EXPECTED_GRADIENT = "expected_gradient"  # Expected gradient length
    HYBRID = "hybrid"  # Combine multiple strategies


class UncertaintyMetric(Enum):
    """Uncertainty measurement methods"""
    ENTROPY = "entropy"  # Shannon entropy of predictions
    MARGIN = "margin"  # Difference between top-2 predictions
    LEAST_CONFIDENCE = "least_confidence"  # 1 - max(predictions)
    VARIATION_RATIO = "variation_ratio"  # Proportion not in modal class


@dataclass
class CandidateExample:
    """A candidate example for active learning selection"""
    id: str
    prompt: str
    response: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    uncertainty_score: float = 0.0
    diversity_score: float = 0.0
    combined_score: float = 0.0
    metadata: Dict = field(default_factory=dict)
    predictions: Optional[List[float]] = None  # Model predictions for uncertainty


@dataclass
class SelectionResult:
    """Result of active learning selection"""
    selected_ids: List[str]
    total_candidates: int
    selection_budget: int
    strategy: AcquisitionStrategy
    avg_uncertainty: float
    avg_diversity: float
    coverage_estimate: float
    selection_time_ms: float


class UncertaintySampler:
    """Sample based on model uncertainty"""

    def __init__(
        self,
        metric: UncertaintyMetric = UncertaintyMetric.ENTROPY,
        model_fn: Optional[Callable] = None,
    ):
        self.metric = metric
        self.model_fn = model_fn
        logger.info(f"Uncertainty Sampler initialized (metric={metric.value})")

    async def compute_uncertainty(
        self,
        candidates: List[CandidateExample],
    ) -> List[CandidateExample]:
        """Compute uncertainty scores for candidates"""
        for candidate in candidates:
            if candidate.predictions is not None:
                candidate.uncertainty_score = self._compute_score(
                    candidate.predictions
                )
            elif self.model_fn:
                # Get predictions from model
                predictions = await self._get_model_predictions(candidate.prompt)
                candidate.predictions = predictions
                candidate.uncertainty_score = self._compute_score(predictions)
            else:
                # Estimate uncertainty from text features
                candidate.uncertainty_score = self._estimate_from_text(
                    candidate.prompt,
                    candidate.response,
                )

        return candidates

    def _compute_score(self, predictions: List[float]) -> float:
        """Compute uncertainty score from predictions"""
        if not predictions:
            return 0.5

        probs = np.array(predictions)
        probs = probs / probs.sum()  # Normalize

        if self.metric == UncertaintyMetric.ENTROPY:
            # Shannon entropy (higher = more uncertain)
            entropy = -np.sum(probs * np.log(probs + 1e-10))
            max_entropy = np.log(len(probs))
            return entropy / max_entropy if max_entropy > 0 else 0

        elif self.metric == UncertaintyMetric.MARGIN:
            # Margin between top-2 predictions (lower margin = more uncertain)
            sorted_probs = np.sort(probs)[::-1]
            if len(sorted_probs) >= 2:
                margin = sorted_probs[0] - sorted_probs[1]
                return 1.0 - margin
            return 0.5

        elif self.metric == UncertaintyMetric.LEAST_CONFIDENCE:
            # 1 - max probability
            return 1.0 - np.max(probs)

        elif self.metric == UncertaintyMetric.VARIATION_RATIO:
            # Proportion of predictions not equal to the mode
            mode_prob = np.max(probs)
            return 1.0 - mode_prob

        return 0.5

    def _estimate_from_text(
        self,
        prompt: str,
        response: Optional[str],
    ) -> float:
        """Estimate uncertainty from text features when no model available"""
        score = 0.5

        # Longer prompts often indicate more complex/uncertain tasks
        prompt_words = len(prompt.split())
        if prompt_words > 50:
            score += 0.1
        if prompt_words > 100:
            score += 0.1

        # Questions with ambiguous terms
        ambiguous_terms = [
            "best", "optimal", "right", "correct",
            "should", "could", "might", "perhaps",
        ]
        for term in ambiguous_terms:
            if term in prompt.lower():
                score += 0.05

        # Multiple questions in prompt
        question_count = prompt.count("?")
        if question_count > 1:
            score += 0.1

        return min(score, 1.0)

    async def _get_model_predictions(self, prompt: str) -> List[float]:
        """Get model predictions for a prompt"""
        if self.model_fn:
            try:
                return await self.model_fn(prompt)
            except Exception as e:
                logger.warning(f"Model prediction failed: {e}")
        return [0.5, 0.5]  # Default uniform


class DiversitySampler:
    """Sample to maximize diversity in selected set"""

    def __init__(
        self,
        embed_fn: Optional[Callable] = None,
        embedding_dim: int = 384,
    ):
        self.embed_fn = embed_fn
        self.embedding_dim = embedding_dim
        logger.info("Diversity Sampler initialized")

    async def compute_embeddings(
        self,
        candidates: List[CandidateExample],
    ) -> List[CandidateExample]:
        """Compute embeddings for candidates"""
        for candidate in candidates:
            if candidate.embedding is None:
                if self.embed_fn:
                    candidate.embedding = await self.embed_fn(candidate.prompt)
                else:
                    # Simple bag-of-words embedding
                    candidate.embedding = self._simple_embedding(candidate.prompt)

        return candidates

    def _simple_embedding(self, text: str) -> np.ndarray:
        """Create simple embedding when no model available"""
        # Hash-based embedding (deterministic pseudo-random)
        words = text.lower().split()
        embedding = np.zeros(self.embedding_dim)

        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            # Use word hash to determine position and value
            word_hash = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            position = word_hash % self.embedding_dim
            value = (word_hash % 1000) / 1000.0 - 0.5  # -0.5 to 0.5
            embedding[position] += value * (1.0 / (i + 1))  # Decay by position

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def compute_diversity_scores(
        self,
        candidates: List[CandidateExample],
        selected_embeddings: Optional[List[np.ndarray]] = None,
    ) -> List[CandidateExample]:
        """Compute diversity scores (distance from already selected)"""
        if selected_embeddings is None:
            selected_embeddings = []

        for candidate in candidates:
            if candidate.embedding is None:
                candidate.diversity_score = 0.5
                continue

            if not selected_embeddings:
                # If nothing selected yet, use distance from origin as proxy
                candidate.diversity_score = np.linalg.norm(candidate.embedding)
            else:
                # Minimum distance to any selected embedding
                min_distance = float("inf")
                for selected_emb in selected_embeddings:
                    distance = np.linalg.norm(candidate.embedding - selected_emb)
                    min_distance = min(min_distance, distance)

                # Normalize to 0-1 (assuming unit vectors, max distance is 2)
                candidate.diversity_score = min(min_distance / 2.0, 1.0)

        return candidates

    def core_set_selection(
        self,
        candidates: List[CandidateExample],
        budget: int,
        existing_embeddings: Optional[List[np.ndarray]] = None,
    ) -> List[str]:
        """
        Select diverse core-set using greedy furthest-first traversal.
        This ensures maximum coverage of the embedding space.
        """
        if not candidates:
            return []

        selected_ids = []
        selected_embeddings = list(existing_embeddings or [])

        # Start with candidate furthest from existing set (or random if none)
        remaining = list(candidates)

        while len(selected_ids) < budget and remaining:
            if not selected_embeddings:
                # Select random first point
                idx = 0
            else:
                # Select point with maximum minimum distance to selected set
                max_min_dist = -1
                idx = 0

                for i, candidate in enumerate(remaining):
                    if candidate.embedding is None:
                        continue

                    min_dist = min(
                        np.linalg.norm(candidate.embedding - sel_emb)
                        for sel_emb in selected_embeddings
                    )

                    if min_dist > max_min_dist:
                        max_min_dist = min_dist
                        idx = i

            # Add selected candidate
            selected = remaining.pop(idx)
            selected_ids.append(selected.id)
            if selected.embedding is not None:
                selected_embeddings.append(selected.embedding)

        return selected_ids


class QueryByCommittee:
    """Select samples where committee of models disagree"""

    def __init__(
        self,
        committee_models: Optional[List[Callable]] = None,
        num_virtual_models: int = 5,
    ):
        self.committee_models = committee_models or []
        self.num_virtual_models = num_virtual_models
        logger.info(f"Query-by-Committee initialized with {num_virtual_models} models")

    async def compute_disagreement(
        self,
        candidates: List[CandidateExample],
    ) -> List[CandidateExample]:
        """Compute committee disagreement for each candidate"""
        for candidate in candidates:
            if self.committee_models:
                # Real committee predictions
                all_predictions = []
                for model in self.committee_models:
                    preds = await model(candidate.prompt)
                    all_predictions.append(preds)

                disagreement = self._compute_vote_entropy(all_predictions)
            else:
                # Simulate disagreement from text features
                disagreement = self._estimate_disagreement(candidate.prompt)

            # Use disagreement as uncertainty proxy
            candidate.uncertainty_score = disagreement

        return candidates

    def _compute_vote_entropy(self, all_predictions: List[List[float]]) -> float:
        """Compute entropy of committee votes"""
        if not all_predictions:
            return 0.5

        # Get predicted class from each model
        votes = [np.argmax(preds) for preds in all_predictions]

        # Count votes per class
        vote_counts = defaultdict(int)
        for vote in votes:
            vote_counts[vote] += 1

        # Compute entropy of vote distribution
        total = len(votes)
        entropy = 0.0
        for count in vote_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * np.log(p + 1e-10)

        # Normalize by max possible entropy
        max_entropy = np.log(len(vote_counts)) if vote_counts else 1.0
        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _estimate_disagreement(self, prompt: str) -> float:
        """Estimate likely disagreement from prompt features"""
        score = 0.3  # Baseline

        # Complex prompts likely to cause disagreement
        if len(prompt.split()) > 30:
            score += 0.1

        # Multi-part questions
        if prompt.count("?") > 1:
            score += 0.15

        # Subjective or debatable terms
        subjective_terms = [
            "best", "better", "worse", "prefer",
            "recommend", "suggest", "opinion",
        ]
        for term in subjective_terms:
            if term in prompt.lower():
                score += 0.05

        return min(score, 1.0)


class HybridSelector:
    """Combine multiple acquisition strategies"""

    def __init__(
        self,
        uncertainty_weight: float = 0.4,
        diversity_weight: float = 0.4,
        qbc_weight: float = 0.2,
    ):
        self.uncertainty_weight = uncertainty_weight
        self.diversity_weight = diversity_weight
        self.qbc_weight = qbc_weight

        # Ensure weights sum to 1
        total = uncertainty_weight + diversity_weight + qbc_weight
        self.uncertainty_weight /= total
        self.diversity_weight /= total
        self.qbc_weight /= total

        logger.info(
            f"Hybrid Selector: uncertainty={self.uncertainty_weight:.2f}, "
            f"diversity={self.diversity_weight:.2f}, qbc={self.qbc_weight:.2f}"
        )

    def compute_combined_scores(
        self,
        candidates: List[CandidateExample],
        qbc_scores: Optional[Dict[str, float]] = None,
    ) -> List[CandidateExample]:
        """Compute combined acquisition scores"""
        qbc_scores = qbc_scores or {}

        for candidate in candidates:
            qbc_score = qbc_scores.get(candidate.id, candidate.uncertainty_score)

            candidate.combined_score = (
                self.uncertainty_weight * candidate.uncertainty_score
                + self.diversity_weight * candidate.diversity_score
                + self.qbc_weight * qbc_score
            )

        return candidates


class ActiveLearner:
    """
    Main active learning orchestrator.

    Combines uncertainty, diversity, and committee-based selection
    to choose the most informative examples for training.
    """

    def __init__(
        self,
        strategy: AcquisitionStrategy = AcquisitionStrategy.HYBRID,
        model_fn: Optional[Callable] = None,
        embed_fn: Optional[Callable] = None,
        output_dir: Optional[Path] = None,
    ):
        self.strategy = strategy
        self.output_dir = output_dir or ACTIVE_LEARNING_STATE
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize samplers
        self.uncertainty_sampler = UncertaintySampler(model_fn=model_fn)
        self.diversity_sampler = DiversitySampler(embed_fn=embed_fn)
        self.qbc_sampler = QueryByCommittee()
        self.hybrid_selector = HybridSelector()

        # Track selected examples over time
        self.selected_history: List[str] = []
        self.selection_stats: Dict[str, Any] = {
            "total_selections": 0,
            "avg_uncertainty": 0.0,
            "avg_diversity": 0.0,
            "coverage_improvement": [],
        }

        logger.info(f"Active Learner initialized (strategy={strategy.value})")

    async def select(
        self,
        candidates: List[CandidateExample],
        budget: int,
        existing_training_ids: Optional[Set[str]] = None,
    ) -> SelectionResult:
        """Select most valuable examples within budget"""
        import time
        start_time = time.time()

        existing_training_ids = existing_training_ids or set()

        # Filter out already selected
        candidates = [c for c in candidates if c.id not in existing_training_ids]

        if not candidates:
            return SelectionResult(
                selected_ids=[],
                total_candidates=0,
                selection_budget=budget,
                strategy=self.strategy,
                avg_uncertainty=0.0,
                avg_diversity=0.0,
                coverage_estimate=0.0,
                selection_time_ms=0.0,
            )

        # Compute scores based on strategy
        if self.strategy == AcquisitionStrategy.UNCERTAINTY:
            candidates = await self.uncertainty_sampler.compute_uncertainty(candidates)
            selected_ids = self._select_top_k(
                candidates,
                budget,
                key=lambda c: c.uncertainty_score,
            )

        elif self.strategy == AcquisitionStrategy.DIVERSITY:
            candidates = await self.diversity_sampler.compute_embeddings(candidates)
            selected_ids = self.diversity_sampler.core_set_selection(
                candidates,
                budget,
            )

        elif self.strategy == AcquisitionStrategy.QBC:
            candidates = await self.qbc_sampler.compute_disagreement(candidates)
            selected_ids = self._select_top_k(
                candidates,
                budget,
                key=lambda c: c.uncertainty_score,
            )

        elif self.strategy == AcquisitionStrategy.HYBRID:
            # Compute all scores
            candidates = await self.uncertainty_sampler.compute_uncertainty(candidates)
            candidates = await self.diversity_sampler.compute_embeddings(candidates)
            candidates = self.diversity_sampler.compute_diversity_scores(candidates)
            candidates = self.hybrid_selector.compute_combined_scores(candidates)

            selected_ids = self._select_top_k(
                candidates,
                budget,
                key=lambda c: c.combined_score,
            )

        else:
            # Default to random
            import random
            random.shuffle(candidates)
            selected_ids = [c.id for c in candidates[:budget]]

        # Compute metrics
        selected_candidates = [c for c in candidates if c.id in selected_ids]
        avg_uncertainty = np.mean([c.uncertainty_score for c in selected_candidates]) if selected_candidates else 0.0
        avg_diversity = np.mean([c.diversity_score for c in selected_candidates]) if selected_candidates else 0.0

        # Estimate coverage improvement
        coverage = self._estimate_coverage(candidates, selected_ids)

        # Update history
        self.selected_history.extend(selected_ids)
        self.selection_stats["total_selections"] += len(selected_ids)
        self.selection_stats["avg_uncertainty"] = (
            0.9 * self.selection_stats["avg_uncertainty"] + 0.1 * avg_uncertainty
        )
        self.selection_stats["avg_diversity"] = (
            0.9 * self.selection_stats["avg_diversity"] + 0.1 * avg_diversity
        )
        self.selection_stats["coverage_improvement"].append(coverage)

        elapsed_ms = (time.time() - start_time) * 1000

        result = SelectionResult(
            selected_ids=selected_ids,
            total_candidates=len(candidates),
            selection_budget=budget,
            strategy=self.strategy,
            avg_uncertainty=avg_uncertainty,
            avg_diversity=avg_diversity,
            coverage_estimate=coverage,
            selection_time_ms=elapsed_ms,
        )

        logger.info(
            f"Selected {len(selected_ids)}/{len(candidates)} examples "
            f"(uncertainty={avg_uncertainty:.3f}, diversity={avg_diversity:.3f}, "
            f"coverage={coverage:.3f})"
        )

        return result

    def _select_top_k(
        self,
        candidates: List[CandidateExample],
        k: int,
        key: Callable,
    ) -> List[str]:
        """Select top-k by score"""
        sorted_candidates = sorted(candidates, key=key, reverse=True)
        return [c.id for c in sorted_candidates[:k]]

    def _estimate_coverage(
        self,
        all_candidates: List[CandidateExample],
        selected_ids: List[str],
    ) -> float:
        """Estimate how well selected examples cover the candidate space"""
        if not all_candidates or not selected_ids:
            return 0.0

        selected_embeddings = [
            c.embedding for c in all_candidates
            if c.id in selected_ids and c.embedding is not None
        ]

        if not selected_embeddings:
            return 0.5  # Unknown

        # For each candidate, find minimum distance to any selected
        total_coverage = 0.0

        for candidate in all_candidates:
            if candidate.embedding is None:
                continue

            min_dist = min(
                np.linalg.norm(candidate.embedding - sel_emb)
                for sel_emb in selected_embeddings
            )

            # Convert distance to coverage (closer = better covered)
            coverage = max(0, 1.0 - min_dist / 2.0)  # Assuming max dist ~2
            total_coverage += coverage

        return total_coverage / len(all_candidates)

    def get_stats(self) -> Dict[str, Any]:
        """Get selection statistics"""
        return {
            **self.selection_stats,
            "unique_selections": len(set(self.selected_history)),
            "recent_coverage": (
                np.mean(self.selection_stats["coverage_improvement"][-10:])
                if self.selection_stats["coverage_improvement"]
                else 0.0
            ),
        }

    def save_state(self) -> Path:
        """Save learner state for resumption"""
        state_path = self.output_dir / "learner_state.json"

        with open(state_path, "w") as f:
            json.dump({
                "strategy": self.strategy.value,
                "selected_history": self.selected_history[-10000:],  # Keep last 10k
                "selection_stats": self.selection_stats,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

        logger.info(f"Saved learner state to {state_path}")
        return state_path

    @classmethod
    def load_state(cls, state_path: Path) -> "ActiveLearner":
        """Load learner from saved state"""
        with open(state_path) as f:
            state = json.load(f)

        learner = cls(strategy=AcquisitionStrategy(state["strategy"]))
        learner.selected_history = state.get("selected_history", [])
        learner.selection_stats = state.get("selection_stats", learner.selection_stats)

        logger.info(f"Loaded learner state from {state_path}")
        return learner


async def main():
    """Test active learning"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Active Learning Test")
    logger.info("=" * 60)

    # Create test candidates
    candidates = []
    for i in range(50):
        candidate = CandidateExample(
            id=f"candidate_{i}",
            prompt=f"Test prompt {i} with varying complexity and content " * (i % 5 + 1),
            metadata={"index": i},
        )
        candidates.append(candidate)

    # Test different strategies
    strategies = [
        AcquisitionStrategy.UNCERTAINTY,
        AcquisitionStrategy.DIVERSITY,
        AcquisitionStrategy.HYBRID,
    ]

    for strategy in strategies:
        logger.info(f"\n{strategy.value.upper()} Strategy:")

        learner = ActiveLearner(strategy=strategy)
        result = await learner.select(candidates, budget=10)

        logger.info(f"  Selected: {len(result.selected_ids)} examples")
        logger.info(f"  Avg uncertainty: {result.avg_uncertainty:.3f}")
        logger.info(f"  Avg diversity: {result.avg_diversity:.3f}")
        logger.info(f"  Coverage: {result.coverage_estimate:.3f}")
        logger.info(f"  Time: {result.selection_time_ms:.1f}ms")

    # Test incremental selection
    logger.info("\nIncremental Selection Test:")

    learner = ActiveLearner(strategy=AcquisitionStrategy.HYBRID)

    existing = set()
    for batch in range(3):
        result = await learner.select(
            candidates,
            budget=5,
            existing_training_ids=existing,
        )
        existing.update(result.selected_ids)
        logger.info(f"  Batch {batch + 1}: {len(existing)} total selected")

    # Get final stats
    stats = learner.get_stats()
    logger.info(f"\nFinal Stats:")
    logger.info(f"  Total selections: {stats['total_selections']}")
    logger.info(f"  Avg uncertainty: {stats['avg_uncertainty']:.3f}")
    logger.info(f"  Avg diversity: {stats['avg_diversity']:.3f}")

    # Save state
    learner.save_state()


if __name__ == "__main__":
    asyncio.run(main())
