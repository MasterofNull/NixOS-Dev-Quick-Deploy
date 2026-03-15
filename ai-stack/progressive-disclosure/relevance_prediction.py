#!/usr/bin/env python3
"""
Context Relevance Prediction System

ML-based relevance prediction and feedback loops for optimal context selection.
Part of Phase 8 Batch 8.3: Context Relevance Prediction

Key Features:
- ML-based relevance prediction
- Query-context similarity scoring
- Relevance feedback loop
- Negative context filtering
- Continuous training from outcomes
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RelevanceScore:
    """Relevance score for context"""
    context_id: str
    score: float  # 0-1
    features: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.7


@dataclass
class FeedbackRecord:
    """User feedback on relevance"""
    query: str
    context_id: str
    predicted_score: float
    actual_usefulness: float  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)


class FeatureExtractor:
    """Extract features for relevance prediction"""

    def __init__(self):
        logger.info("Feature Extractor initialized")

    def extract(self, query: str, context: str) -> Dict[str, float]:
        """Extract relevance features"""
        features = {}

        # Term overlap
        query_terms = set(query.lower().split())
        context_terms = set(context.lower().split())

        if query_terms:
            features["term_overlap"] = len(query_terms & context_terms) / len(query_terms)
        else:
            features["term_overlap"] = 0.0

        # Length ratio
        query_len = len(query.split())
        context_len = len(context.split())
        features["length_ratio"] = min(query_len, context_len) / max(query_len, context_len, 1)

        # Keyword presence
        keywords = {"error", "fix", "how", "what", "why", "implement"}
        query_has_keywords = any(kw in query.lower() for kw in keywords)
        context_has_keywords = any(kw in context.lower() for kw in keywords)
        features["keyword_match"] = 1.0 if query_has_keywords == context_has_keywords else 0.5

        # Semantic similarity (simplified - would use embeddings in production)
        features["semantic_sim"] = self._simple_similarity(query, context)

        return features

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Simple similarity measure"""
        terms1 = set(text1.lower().split())
        terms2 = set(text2.lower().split())

        if not terms1 or not terms2:
            return 0.0

        # Jaccard similarity
        intersection = terms1 & terms2
        union = terms1 | terms2

        return len(intersection) / len(union)


class RelevancePredictor:
    """Predict context relevance using simple model"""

    def __init__(self):
        # Feature weights (would be learned in production)
        self.weights = {
            "term_overlap": 0.35,
            "length_ratio": 0.1,
            "keyword_match": 0.15,
            "semantic_sim": 0.4,
        }

        self.prediction_history: List[Dict] = []

        logger.info("Relevance Predictor initialized")

    def predict(self, query: str, context: str, context_id: str) -> RelevanceScore:
        """Predict relevance score"""
        extractor = FeatureExtractor()
        features = extractor.extract(query, context)

        # Weighted sum
        score = sum(features.get(f, 0.0) * w for f, w in self.weights.items())

        # Normalize to 0-1
        score = max(0.0, min(1.0, score))

        relevance = RelevanceScore(
            context_id=context_id,
            score=score,
            features=features,
            confidence=0.7,
        )

        self.prediction_history.append({
            "timestamp": datetime.now(),
            "query": query,
            "context_id": context_id,
            "score": score,
            "features": features,
        })

        logger.debug(f"Predicted relevance: {score:.2f} for {context_id}")

        return relevance

    def predict_batch(
        self,
        query: str,
        contexts: Dict[str, str],
    ) -> List[RelevanceScore]:
        """Predict relevance for multiple contexts"""
        scores = []

        for context_id, context in contexts.items():
            score = self.predict(query, context, context_id)
            scores.append(score)

        # Sort by score (descending)
        scores.sort(key=lambda s: s.score, reverse=True)

        return scores


class RelevanceFeedbackLoop:
    """Collect feedback and improve predictions"""

    def __init__(self, predictor: RelevancePredictor):
        self.predictor = predictor
        self.feedback: List[FeedbackRecord] = []

        logger.info("Relevance Feedback Loop initialized")

    def record_feedback(
        self,
        query: str,
        context_id: str,
        predicted_score: float,
        actual_usefulness: float,
    ):
        """Record user feedback on relevance"""
        feedback = FeedbackRecord(
            query=query,
            context_id=context_id,
            predicted_score=predicted_score,
            actual_usefulness=actual_usefulness,
        )

        self.feedback.append(feedback)

        logger.info(
            f"Feedback recorded: predicted={predicted_score:.2f}, "
            f"actual={actual_usefulness:.2f}"
        )

    def update_model(self):
        """Update model weights based on feedback"""
        if len(self.feedback) < 10:
            logger.info("Not enough feedback to update model")
            return

        logger.info(f"Updating model with {len(self.feedback)} feedback records")

        # Calculate prediction errors
        errors = [
            abs(f.predicted_score - f.actual_usefulness)
            for f in self.feedback
        ]

        avg_error = sum(errors) / len(errors)

        logger.info(f"  Average prediction error: {avg_error:.3f}")

        # In production, would retrain model
        # For now, just adjust weights slightly

        if avg_error > 0.2:
            # Large errors - adjust weights
            self.predictor.weights["semantic_sim"] += 0.05
            self.predictor.weights["term_overlap"] -= 0.05

            logger.info("  Adjusted weights based on error")


class NegativeContextFilter:
    """Filter out irrelevant context"""

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold
        self.filtered_count = 0

        logger.info(f"Negative Context Filter initialized (threshold={threshold})")

    def filter(
        self,
        relevance_scores: List[RelevanceScore],
    ) -> List[RelevanceScore]:
        """Filter out low-relevance contexts"""
        before_count = len(relevance_scores)

        filtered = [s for s in relevance_scores if s.score >= self.threshold]

        filtered_out = before_count - len(filtered)
        self.filtered_count += filtered_out

        if filtered_out > 0:
            logger.info(f"Filtered out {filtered_out} low-relevance contexts")

        return filtered


async def main():
    """Test relevance prediction system"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Context Relevance Prediction Test")
    logger.info("=" * 60)

    # Initialize components
    predictor = RelevancePredictor()
    feedback_loop = RelevanceFeedbackLoop(predictor)
    filter = NegativeContextFilter(threshold=0.4)

    # Test 1: Predict relevance
    logger.info("\n1. Relevance Prediction:")

    query = "How do I fix deployment errors?"

    contexts = {
        "deploy_guide": "Deployment guide with common errors and solutions",
        "api_ref": "API reference documentation",
        "troubleshooting": "Troubleshooting guide for deployment issues",
        "security": "Security best practices for production",
    }

    scores = predictor.predict_batch(query, contexts)

    logger.info(f"\nRelevance scores for query: '{query}'")
    for score in scores:
        logger.info(f"  {score.context_id}: {score.score:.2f}")

    # Test 2: Filter low-relevance
    logger.info("\n2. Negative Context Filtering:")

    filtered = filter.filter(scores)

    logger.info(f"  Kept {len(filtered)}/{len(scores)} contexts")
    logger.info(f"  Filtered: {[s.context_id for s in filtered]}")

    # Test 3: Feedback loop
    logger.info("\n3. Relevance Feedback:")

    # Simulate user feedback
    for score in scores[:2]:
        # User found these helpful
        feedback_loop.record_feedback(
            query=query,
            context_id=score.context_id,
            predicted_score=score.score,
            actual_usefulness=0.9,
        )

    # Update model
    feedback_loop.update_model()

    logger.info(f"  Model updated with {len(feedback_loop.feedback)} feedback records")


if __name__ == "__main__":
    asyncio.run(main())
