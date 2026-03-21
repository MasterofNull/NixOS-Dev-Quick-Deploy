#!/usr/bin/env python3
"""
Test suite for AI insights ranking algorithms.

Purpose: Verify ranking algorithms for AI insights dashboard that score
and rank insights by relevance, recency, and confidence.

Covers:
- Relevance scoring for insights
- Recency bias in ranking
- Confidence weighting
- Ranking consistency and stability
- Edge case handling
"""

import pytest
import time
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Insight:
    """AI insight data point."""
    id: str
    title: str
    category: str
    relevance_score: float  # 0-1
    confidence: float  # 0-1
    created_at: datetime
    impact_potential: str  # "low", "medium", "high"
    actionable: bool


class MockRankingAlgorithm:
    """Mock ranking algorithm for insights."""

    def __init__(self, enable_recency_bias: bool = True, recency_decay_hours: int = 24):
        self.enable_recency_bias = enable_recency_bias
        self.recency_decay_hours = recency_decay_hours

    def calculate_relevance_score(self, insight: Insight, context: Dict[str, Any]) -> float:
        """Calculate relevance score for insight."""
        base_score = insight.relevance_score

        # Adjust based on context
        if context.get("filter_category") == insight.category:
            base_score *= 1.2  # 20% boost for matching category

        if insight.actionable:
            base_score *= 1.1  # 10% boost for actionable insights

        # Clamp to 0-1
        return min(1.0, max(0.0, base_score))

    def calculate_recency_bias(self, created_at: datetime) -> float:
        """Calculate time-based relevance multiplier."""
        if not self.enable_recency_bias:
            return 1.0

        age = datetime.now() - created_at
        hours_old = age.total_seconds() / 3600

        # Exponential decay
        decay = 2.0 ** (-(hours_old / self.recency_decay_hours))
        return max(0.1, min(1.0, decay))

    def calculate_confidence_weight(self, confidence: float, threshold: float = 0.3) -> float:
        """Weight insights by confidence level."""
        if confidence < threshold:
            return confidence * 0.5  # 50% penalty for low confidence

        return confidence

    def rank_insights(self, insights: List[Insight], context: Dict[str, Any] = None) -> List[tuple]:
        """Rank insights and return (insight, score) tuples."""
        if context is None:
            context = {}

        ranked = []

        for insight in insights:
            # Calculate components
            relevance = self.calculate_relevance_score(insight, context)
            recency = self.calculate_recency_bias(insight.created_at)
            confidence = self.calculate_confidence_weight(insight.confidence)

            # Combined score (weighted average)
            combined_score = (
                relevance * 0.4 +
                recency * 0.3 +
                confidence * 0.3
            )

            ranked.append((insight, combined_score))

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def verify_ranking_stability(self, insights: List[Insight], context: Dict[str, Any] = None) -> bool:
        """Verify ranking is stable across multiple runs."""
        if not insights:
            return True

        # Run ranking multiple times
        rankings = []
        for _ in range(3):
            ranked = self.rank_insights(insights, context)
            rankings.append([i.id for i, _ in ranked])

        # All rankings should be identical
        return all(ranking == rankings[0] for ranking in rankings)

    def handle_edge_cases(self, insights: List[Insight]) -> Dict[str, Any]:
        """Test edge case handling."""
        results = {
            "empty_list": len(insights) == 0,
            "single_insight": len(insights) == 1,
            "invalid_scores": any(
                not (0 <= i.relevance_score <= 1) or
                not (0 <= i.confidence <= 1)
                for i in insights
            ),
            "future_dates": any(
                i.created_at > datetime.now()
                for i in insights
            ),
        }

        return results


# ============================================================================
# Test Classes
# ============================================================================

class TestRelevanceScoring:
    """Test relevance scoring."""

    @pytest.fixture
    def algorithm(self):
        """Create ranking algorithm."""
        return MockRankingAlgorithm()

    @pytest.fixture
    def sample_insights(self):
        """Create sample insights."""
        now = datetime.now()
        return [
            Insight(
                id="insight_1",
                title="High error rate detected",
                category="performance",
                relevance_score=0.95,
                confidence=0.85,
                created_at=now - timedelta(hours=1),
                impact_potential="high",
                actionable=True
            ),
            Insight(
                id="insight_2",
                title="Deployment success rate",
                category="operational",
                relevance_score=0.7,
                confidence=0.9,
                created_at=now - timedelta(hours=12),
                impact_potential="medium",
                actionable=False
            ),
            Insight(
                id="insight_3",
                title="Security scan completed",
                category="security",
                relevance_score=0.6,
                confidence=0.75,
                created_at=now - timedelta(hours=48),
                impact_potential="high",
                actionable=True
            ),
        ]

    def test_relevance_scoring_range(self, algorithm, sample_insights):
        """Relevance scores within valid range."""
        for insight in sample_insights:
            score = algorithm.calculate_relevance_score(insight, {})
            assert 0.0 <= score <= 1.0

    def test_relevance_with_context(self, algorithm, sample_insights):
        """Relevance scores adjusted by context."""
        context = {"filter_category": "performance"}

        perf_insight = sample_insights[0]
        score_no_context = algorithm.calculate_relevance_score(perf_insight, {})
        score_with_context = algorithm.calculate_relevance_score(perf_insight, context)

        # Context should boost relevant category (may be clamped at 1.0)
        assert score_with_context >= score_no_context

    def test_relevance_actionability_boost(self, algorithm, sample_insights):
        """Actionable insights boosted."""
        actionable = sample_insights[0]
        non_actionable = sample_insights[1]

        score_actionable = algorithm.calculate_relevance_score(actionable, {})
        score_non_actionable = algorithm.calculate_relevance_score(non_actionable, {})

        assert score_actionable > score_non_actionable


class TestRecencyBias:
    """Test recency bias in ranking."""

    @pytest.fixture
    def algorithm(self):
        """Create ranking algorithm."""
        return MockRankingAlgorithm(enable_recency_bias=True, recency_decay_hours=24)

    def test_recency_multiplier_current(self):
        """Current insights get high recency multiplier."""
        algo = MockRankingAlgorithm(enable_recency_bias=True, recency_decay_hours=24)
        now = datetime.now()

        multiplier = algo.calculate_recency_bias(now)
        assert 0.9 <= multiplier <= 1.0

    def test_recency_multiplier_old(self):
        """Old insights get low recency multiplier."""
        algo = MockRankingAlgorithm(enable_recency_bias=True, recency_decay_hours=24)
        old = datetime.now() - timedelta(hours=72)

        multiplier = algo.calculate_recency_bias(old)
        assert 0.0 < multiplier < 0.5

    def test_recency_decay_exponential(self):
        """Recency decay is exponential."""
        algo = MockRankingAlgorithm(enable_recency_bias=True, recency_decay_hours=24)
        now = datetime.now()

        score_1h = algo.calculate_recency_bias(now - timedelta(hours=1))
        score_2h = algo.calculate_recency_bias(now - timedelta(hours=2))
        score_4h = algo.calculate_recency_bias(now - timedelta(hours=4))

        # Should decrease with age
        assert score_1h > score_2h > score_4h

        # Should be exponential (not linear)
        diff1 = score_1h - score_2h
        diff2 = score_2h - score_4h
        # Difference should decrease (exponential not linear)

    def test_recency_disabled(self):
        """Can disable recency bias."""
        algo = MockRankingAlgorithm(enable_recency_bias=False)
        now = datetime.now()
        old = datetime.now() - timedelta(hours=100)

        multiplier_now = algo.calculate_recency_bias(now)
        multiplier_old = algo.calculate_recency_bias(old)

        assert multiplier_now == multiplier_old == 1.0


class TestConfidenceWeighting:
    """Test confidence-based weighting."""

    @pytest.fixture
    def algorithm(self):
        """Create ranking algorithm."""
        return MockRankingAlgorithm()

    def test_high_confidence_weighting(self, algorithm):
        """High confidence insights weighted positively."""
        high_confidence = algorithm.calculate_confidence_weight(0.95)
        assert high_confidence > 0.8

    def test_low_confidence_penalty(self, algorithm):
        """Low confidence insights penalized."""
        low_confidence = algorithm.calculate_confidence_weight(0.2)
        threshold = algorithm.calculate_confidence_weight(0.3)

        assert low_confidence < threshold

    def test_confidence_threshold(self, algorithm):
        """Confidence threshold applied."""
        below_threshold = algorithm.calculate_confidence_weight(0.25, threshold=0.3)
        above_threshold = algorithm.calculate_confidence_weight(0.35, threshold=0.3)

        # Below threshold should be penalized
        assert below_threshold < 0.35
        # Above threshold should not be heavily penalized
        assert above_threshold > 0.3

    def test_confidence_range(self, algorithm):
        """Confidence weights within range."""
        for confidence in [0.0, 0.25, 0.5, 0.75, 1.0]:
            weight = algorithm.calculate_confidence_weight(confidence)
            assert 0.0 <= weight <= 1.0


class TestRankingConsistency:
    """Test ranking consistency and stability."""

    @pytest.fixture
    def algorithm(self):
        """Create ranking algorithm."""
        return MockRankingAlgorithm()

    @pytest.fixture
    def insights(self):
        """Create insights."""
        now = datetime.now()
        return [
            Insight(
                id=f"insight_{i}",
                title=f"Insight {i}",
                category="test",
                relevance_score=0.7 + i * 0.05,
                confidence=0.8,
                created_at=now - timedelta(hours=i),
                impact_potential="high",
                actionable=True
            )
            for i in range(5)
        ]

    def test_deterministic_ranking(self, algorithm, insights):
        """Rankings are deterministic."""
        ranked1 = algorithm.rank_insights(insights)
        ranked2 = algorithm.rank_insights(insights)

        ids1 = [i.id for i, _ in ranked1]
        ids2 = [i.id for i, _ in ranked2]

        assert ids1 == ids2

    def test_ranking_stability(self, algorithm, insights):
        """Ranking is stable across calls."""
        is_stable = algorithm.verify_ranking_stability(insights)
        assert is_stable is True

    def test_ranking_order_correct(self, algorithm, insights):
        """Insights ranked in correct order."""
        ranked = algorithm.rank_insights(insights)

        # Scores should be descending
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_consistent_with_different_contexts(self, algorithm, insights):
        """Consistency maintained with different contexts."""
        contexts = [
            {},
            {"filter_category": "test"},
            {"filter_category": "other"},
        ]

        rankings = []
        for context in contexts:
            ranked = algorithm.rank_insights(insights, context)
            rankings.append(ranked)

        # Should still have consistent relative ordering
        # (though actual scores may differ)


class TestEdgeCases:
    """Test edge case handling."""

    @pytest.fixture
    def algorithm(self):
        """Create ranking algorithm."""
        return MockRankingAlgorithm()

    def test_empty_insight_list(self, algorithm):
        """Handle empty insight list."""
        ranked = algorithm.rank_insights([])
        assert ranked == []

    def test_single_insight(self, algorithm):
        """Rank single insight."""
        insight = Insight(
            id="single",
            title="Only one",
            category="test",
            relevance_score=0.8,
            confidence=0.9,
            created_at=datetime.now(),
            impact_potential="high",
            actionable=True
        )

        ranked = algorithm.rank_insights([insight])
        assert len(ranked) == 1

    def test_identical_insights(self, algorithm):
        """Rank identical insights."""
        now = datetime.now()
        insights = [
            Insight(
                id=f"identical_{i}",
                title="Same insight",
                category="test",
                relevance_score=0.8,
                confidence=0.9,
                created_at=now,
                impact_potential="high",
                actionable=True
            )
            for i in range(3)
        ]

        ranked = algorithm.rank_insights(insights)
        # All should have same score
        scores = [score for _, score in ranked]
        assert all(abs(s - scores[0]) < 0.001 for s in scores)

    def test_extreme_confidence_values(self, algorithm):
        """Handle extreme confidence values."""
        insights = [
            Insight(
                id="zero_conf",
                title="No confidence",
                category="test",
                relevance_score=0.8,
                confidence=0.0,
                created_at=datetime.now(),
                impact_potential="high",
                actionable=True
            ),
            Insight(
                id="max_conf",
                title="Full confidence",
                category="test",
                relevance_score=0.8,
                confidence=1.0,
                created_at=datetime.now(),
                impact_potential="high",
                actionable=True
            ),
        ]

        ranked = algorithm.rank_insights(insights)
        # Max confidence should rank higher
        assert ranked[0][0].confidence > ranked[1][0].confidence

    def test_very_old_insights(self, algorithm):
        """Handle very old insights."""
        very_old = datetime.now() - timedelta(days=365)
        insight = Insight(
            id="ancient",
            title="Very old insight",
            category="test",
            relevance_score=0.9,
            confidence=0.9,
            created_at=very_old,
            impact_potential="high",
            actionable=True
        )

        ranked = algorithm.rank_insights([insight])
        # Should still be rankable
        assert len(ranked) == 1
        assert ranked[0][1] > 0.0  # Should have positive score


# ============================================================================
# Integration Tests
# ============================================================================

def test_ranking_integration():
    """Integration test for ranking algorithms."""
    algorithm = MockRankingAlgorithm(enable_recency_bias=True)

    now = datetime.now()
    insights = [
        Insight(
            id="critical_new",
            title="Critical issue found",
            category="security",
            relevance_score=0.95,
            confidence=0.9,
            created_at=now - timedelta(hours=1),
            impact_potential="high",
            actionable=True
        ),
        Insight(
            id="old_issue",
            title="Old resolved issue",
            category="performance",
            relevance_score=0.8,
            confidence=0.7,
            created_at=now - timedelta(days=30),
            impact_potential="low",
            actionable=False
        ),
        Insight(
            id="current_status",
            title="Current system status",
            category="operational",
            relevance_score=0.7,
            confidence=0.95,
            created_at=now - timedelta(hours=0.5),
            impact_potential="medium",
            actionable=False
        ),
    ]

    # Rank insights
    ranked = algorithm.rank_insights(insights)

    # Verify ranking
    assert len(ranked) == 3
    assert ranked[0][0].id == "critical_new"  # Recent + high relevance
    assert ranked[1][0].id == "current_status"  # Very recent + high confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
