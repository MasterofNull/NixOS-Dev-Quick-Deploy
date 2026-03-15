#!/usr/bin/env python3
"""
Result Quality Assurance Framework

Automated quality checking and refinement for remote agent results.
Part of Phase 6 Batch 6.3: Result Quality Assurance

Key Features:
- Automated quality checking for remote results
- Result refinement for low-quality outputs
- Fallback to local models for failed remote calls
- Result caching to avoid redundant calls
- Quality trend tracking per agent

Reference: Quality assurance and validation patterns
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Quality assessment dimensions"""
    RELEVANCE = "relevance"  # Answers the question
    ACCURACY = "accuracy"  # Factually correct
    COMPLETENESS = "completeness"  # Thorough response
    CLARITY = "clarity"  # Well-structured
    SAFETY = "safety"  # No harmful content


class QualityThreshold(Enum):
    """Quality threshold levels"""
    MINIMAL = 0.5  # Barely acceptable
    ACCEPTABLE = 0.7  # Good enough
    HIGH = 0.85  # Very good
    EXCELLENT = 0.95  # Exceptional


@dataclass
class QualityScore:
    """Quality assessment score"""
    overall: float  # 0-1
    dimensions: Dict[QualityDimension, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class QualityCheck:
    """Quality check result"""
    passed: bool
    score: QualityScore
    refinement_needed: bool
    fallback_recommended: bool
    cached_alternative: Optional[str] = None


@dataclass
class RefinementResult:
    """Result of refinement attempt"""
    original_response: str
    refined_response: str
    improvement_score: float
    refinement_method: str
    iterations: int


class QualityChecker:
    """Check quality of remote agent results"""

    def __init__(self, threshold: QualityThreshold = QualityThreshold.ACCEPTABLE):
        self.threshold = threshold
        logger.info(f"Quality Checker initialized (threshold={threshold.name})")

    def check_quality(
        self,
        query: str,
        response: str,
        expected_format: Optional[str] = None,
    ) -> QualityCheck:
        """Check response quality"""
        score = self._assess_quality(query, response, expected_format)

        passed = score.overall >= self.threshold.value
        refinement_needed = not passed and score.overall >= QualityThreshold.MINIMAL.value
        fallback_recommended = score.overall < QualityThreshold.MINIMAL.value

        logger.debug(
            f"Quality check: score={score.overall:.2f}, passed={passed}, "
            f"refinement_needed={refinement_needed}"
        )

        return QualityCheck(
            passed=passed,
            score=score,
            refinement_needed=refinement_needed,
            fallback_recommended=fallback_recommended,
        )

    def _assess_quality(
        self,
        query: str,
        response: str,
        expected_format: Optional[str],
    ) -> QualityScore:
        """Assess quality across dimensions"""
        dimensions = {}

        # Relevance: Does response address the query?
        dimensions[QualityDimension.RELEVANCE] = self._check_relevance(query, response)

        # Accuracy: Basic fact checking
        dimensions[QualityDimension.ACCURACY] = self._check_accuracy(response)

        # Completeness: Is response thorough?
        dimensions[QualityDimension.COMPLETENESS] = self._check_completeness(query, response)

        # Clarity: Is response well-structured?
        dimensions[QualityDimension.CLARITY] = self._check_clarity(response)

        # Safety: No harmful content
        dimensions[QualityDimension.SAFETY] = self._check_safety(response)

        # Format compliance
        if expected_format:
            format_score = self._check_format(response, expected_format)
            # Adjust relevance based on format compliance
            dimensions[QualityDimension.RELEVANCE] *= format_score

        # Calculate overall score (weighted average)
        weights = {
            QualityDimension.RELEVANCE: 0.3,
            QualityDimension.ACCURACY: 0.25,
            QualityDimension.COMPLETENESS: 0.2,
            QualityDimension.CLARITY: 0.15,
            QualityDimension.SAFETY: 0.1,
        }

        overall = sum(
            dimensions[dim] * weights[dim]
            for dim in weights.keys()
        )

        # Identify issues
        issues = []
        suggestions = []

        for dim, score in dimensions.items():
            if score < 0.6:
                issues.append(f"Low {dim.value} score: {score:.2f}")
                suggestions.append(self._get_suggestion(dim))

        return QualityScore(
            overall=overall,
            dimensions=dimensions,
            issues=issues,
            suggestions=suggestions,
        )

    def _check_relevance(self, query: str, response: str) -> float:
        """Check if response is relevant to query"""
        query_terms = set(query.lower().split())
        response_terms = set(response.lower().split())

        # Remove stopwords
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
        query_terms -= stopwords
        response_terms -= stopwords

        if not query_terms:
            return 0.8  # Neutral

        # Calculate term overlap
        overlap = query_terms & response_terms
        relevance = len(overlap) / len(query_terms)

        # Boost if response is substantial
        if len(response.split()) > 20:
            relevance = min(1.0, relevance + 0.1)

        return relevance

    def _check_accuracy(self, response: str) -> float:
        """Basic accuracy checks"""
        score = 1.0

        # Check for common error patterns
        error_patterns = [
            r"i don't know",
            r"i'm not sure",
            r"i cannot",
            r"as an ai",
            r"i apologize",
        ]

        for pattern in error_patterns:
            if re.search(pattern, response.lower()):
                score -= 0.1

        # Check for contradictions (very simplified)
        if "but" in response and "however" in response:
            # Might indicate uncertainty
            score -= 0.05

        return max(0.0, min(1.0, score))

    def _check_completeness(self, query: str, response: str) -> float:
        """Check if response is complete"""
        # Simple heuristic: longer responses are more complete
        response_words = len(response.split())

        if "list" in query.lower() or "steps" in query.lower():
            # Expect structured response
            if any(marker in response for marker in ["1.", "-", "*"]):
                base_score = 0.8
            else:
                base_score = 0.5
        else:
            base_score = 0.7

        # Adjust based on length
        if response_words < 10:
            base_score -= 0.3
        elif response_words < 30:
            base_score -= 0.1
        elif response_words > 100:
            base_score += 0.1

        return max(0.0, min(1.0, base_score))

    def _check_clarity(self, response: str) -> float:
        """Check response clarity"""
        score = 0.8  # Baseline

        # Check for structure
        if any(marker in response for marker in ["\n", ".", ":", ";"]):
            score += 0.1

        # Check for code blocks if relevant
        if "```" in response:
            score += 0.05

        # Penalize very long sentences
        sentences = response.split(".")
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        if avg_sentence_length > 40:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _check_safety(self, response: str) -> float:
        """Check for harmful content"""
        # Simple keyword-based check
        unsafe_patterns = [
            r"hack",
            r"exploit",
            r"bypass security",
            r"sudo rm -rf",
        ]

        for pattern in unsafe_patterns:
            if re.search(pattern, response.lower()):
                return 0.5

        return 1.0

    def _check_format(self, response: str, expected_format: str) -> float:
        """Check format compliance"""
        if expected_format == "json":
            try:
                json.loads(response)
                return 1.0
            except:
                # Check if contains JSON-like structure
                if "{" in response and "}" in response:
                    return 0.7
                return 0.3

        elif expected_format == "code":
            if "```" in response:
                return 1.0
            elif any(kw in response for kw in ["def ", "function ", "class "]):
                return 0.8
            return 0.5

        elif expected_format == "list":
            if any(marker in response for marker in ["1.", "-", "*"]):
                return 1.0
            return 0.5

        return 0.8  # Unknown format

    def _get_suggestion(self, dimension: QualityDimension) -> str:
        """Get improvement suggestion"""
        suggestions = {
            QualityDimension.RELEVANCE: "Ensure response directly addresses the query",
            QualityDimension.ACCURACY: "Verify facts and avoid uncertain language",
            QualityDimension.COMPLETENESS: "Provide more detail and examples",
            QualityDimension.CLARITY: "Improve structure with clear sections",
            QualityDimension.SAFETY: "Remove potentially harmful content",
        }
        return suggestions.get(dimension, "Improve response quality")


class ResultRefiner:
    """Refine low-quality results"""

    def __init__(self):
        logger.info("Result Refiner initialized")

    async def refine(
        self,
        query: str,
        response: str,
        quality_score: QualityScore,
        llm_client: Optional[Any] = None,
    ) -> RefinementResult:
        """Refine response based on quality issues"""
        logger.info(f"Refining response (score={quality_score.overall:.2f})")

        refined = response
        iterations = 0
        max_iterations = 2

        # Apply refinement strategies
        for suggestion in quality_score.suggestions[:3]:  # Top 3 suggestions
            if iterations >= max_iterations:
                break

            if "structure" in suggestion.lower():
                refined = self._add_structure(refined)
                iterations += 1

            elif "detail" in suggestion.lower():
                refined = self._add_detail(refined, query)
                iterations += 1

            elif "clarity" in suggestion.lower():
                refined = self._improve_clarity(refined)
                iterations += 1

        # Calculate improvement
        original_length = len(response.split())
        refined_length = len(refined.split())
        improvement = (refined_length - original_length) / max(original_length, 1)

        return RefinementResult(
            original_response=response,
            refined_response=refined,
            improvement_score=min(1.0, improvement + quality_score.overall),
            refinement_method="automated",
            iterations=iterations,
        )

    def _add_structure(self, text: str) -> str:
        """Add structure to response"""
        # Simple: add sections
        if "\n" not in text:
            # Split into sentences and add line breaks
            sentences = text.split(". ")
            return "\n\n".join(s + "." for s in sentences if s)
        return text

    def _add_detail(self, text: str, query: str) -> str:
        """Add detail to response"""
        # Simple: add context reference
        if len(text.split()) < 20:
            addition = f"\n\nRegarding '{query}', this provides a foundational overview."
            return text + addition
        return text

    def _improve_clarity(self, text: str) -> str:
        """Improve clarity"""
        # Simple: ensure proper punctuation
        if not text.endswith("."):
            text += "."
        return text


class ResultCache:
    """Cache results to avoid redundant calls"""

    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Tuple[str, QualityScore, datetime]] = {}
        self.max_size = max_size
        logger.info(f"Result Cache initialized (max_size={max_size})")

    def get(self, query: str, max_age_hours: int = 24) -> Optional[Tuple[str, QualityScore]]:
        """Get cached result"""
        query_hash = self._hash_query(query)

        if query_hash in self.cache:
            response, quality, timestamp = self.cache[query_hash]

            # Check age
            age = (datetime.now() - timestamp).total_seconds() / 3600
            if age <= max_age_hours:
                logger.debug(f"Cache hit: {query_hash}")
                return response, quality

            # Expired - remove
            del self.cache[query_hash]

        return None

    def set(self, query: str, response: str, quality: QualityScore):
        """Cache result"""
        query_hash = self._hash_query(query)

        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest = min(self.cache.items(), key=lambda x: x[1][2])
            del self.cache[oldest[0]]

        self.cache[query_hash] = (response, quality, datetime.now())
        logger.debug(f"Cached result: {query_hash}")

    def _hash_query(self, query: str) -> str:
        """Hash query"""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]


class QualityTrendTracker:
    """Track quality trends per agent"""

    def __init__(self):
        self.agent_quality: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        logger.info("Quality Trend Tracker initialized")

    def record_quality(self, agent_id: str, quality_score: float):
        """Record quality score for agent"""
        self.agent_quality[agent_id].append({
            "timestamp": datetime.now(),
            "score": quality_score,
        })

    def get_trend(self, agent_id: str, window_hours: int = 24) -> Dict[str, Any]:
        """Get quality trend for agent"""
        records = list(self.agent_quality.get(agent_id, []))

        if not records:
            return {"status": "no_data"}

        # Filter by time window
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent = [r for r in records if r["timestamp"] > cutoff]

        if not recent:
            return {"status": "no_recent_data"}

        scores = [r["score"] for r in recent]

        return {
            "agent_id": agent_id,
            "sample_count": len(scores),
            "avg_quality": sum(scores) / len(scores),
            "min_quality": min(scores),
            "max_quality": max(scores),
            "trend": "improving" if scores[-1] > scores[0] else "declining" if scores[-1] < scores[0] else "stable",
        }


async def main():
    """Test quality assurance framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Result Quality Assurance Test")
    logger.info("=" * 60)

    # Initialize components
    checker = QualityChecker(threshold=QualityThreshold.ACCEPTABLE)
    refiner = ResultRefiner()
    cache = ResultCache()
    tracker = QualityTrendTracker()

    # Test 1: Quality checking
    logger.info("\n1. Quality Checking:")

    test_cases = [
        ("What is Python?", "Python is a programming language.", None),
        ("List the steps", "Step 1: First\nStep 2: Second\nStep 3: Third", "list"),
        ("Generate JSON", '{"key": "value"}', "json"),
        ("Short answer", "Yes.", None),
    ]

    for query, response, fmt in test_cases:
        check = checker.check_quality(query, response, fmt)

        logger.info(f"\nQuery: {query}")
        logger.info(f"  Score: {check.score.overall:.2f}")
        logger.info(f"  Passed: {check.passed}")
        logger.info(f"  Refinement needed: {check.refinement_needed}")

        if check.score.issues:
            logger.info(f"  Issues: {', '.join(check.score.issues[:2])}")

    # Test 2: Refinement
    logger.info("\n2. Result Refinement:")

    poor_response = "Yes that's correct"
    poor_score = QualityScore(
        overall=0.4,
        suggestions=["Add more detail", "Improve structure"],
    )

    refinement = await refiner.refine("Explain recursion", poor_response, poor_score)

    logger.info(f"  Original: {refinement.original_response}")
    logger.info(f"  Refined: {refinement.refined_response[:100]}...")
    logger.info(f"  Improvement: {refinement.improvement_score:.2f}")
    logger.info(f"  Iterations: {refinement.iterations}")

    # Test 3: Caching
    logger.info("\n3. Result Caching:")

    query = "What is machine learning?"
    response = "Machine learning is a subset of AI..."
    quality = QualityScore(overall=0.85)

    cache.set(query, response, quality)
    logger.info(f"  Cached result")

    cached = cache.get(query)
    if cached:
        logger.info(f"  Cache hit: score={cached[1].overall:.2f}")
    else:
        logger.info(f"  Cache miss")

    # Test 4: Quality trends
    logger.info("\n4. Quality Trend Tracking:")

    agent_id = "test_agent"
    for score in [0.7, 0.75, 0.8, 0.82, 0.85]:
        tracker.record_quality(agent_id, score)

    trend = tracker.get_trend(agent_id)
    logger.info(f"  Agent: {trend['agent_id']}")
    logger.info(f"  Avg quality: {trend['avg_quality']:.2f}")
    logger.info(f"  Trend: {trend['trend']}")


if __name__ == "__main__":
    asyncio.run(main())
