#!/usr/bin/env python3
"""
Remediation Learning Loop

Tracks remediation outcomes and optimizes strategies over time.
Part of Phase 9 Batch 9.3: Remediation Learning Loop

Key Features:
- Remediation outcome tracking
- Remediation strategy optimization
- Remediation playbook library
- Remediation reuse for similar gaps
- Remediation quality improvement
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from gap_detection import CapabilityGap, GapType
from gap_remediation import RemediationPlan, RemediationResult, RemediationStrategy, RemediationStatus

logger = logging.getLogger(__name__)


@dataclass
class RemediationOutcome:
    """Outcome of remediation attempt"""
    gap_id: str
    plan_id: str
    strategy: RemediationStrategy
    success: bool
    duration_seconds: float
    validation_passed: bool
    timestamp: datetime = field(default_factory=datetime.now)

    # Quality metrics
    completeness_score: float = 0.0
    effectiveness_score: float = 0.0
    efficiency_score: float = 0.0

    # Learning
    lessons_learned: List[str] = field(default_factory=list)
    improvements_suggested: List[str] = field(default_factory=list)


@dataclass
class RemediationPlaybook:
    """Reusable remediation playbook"""
    playbook_id: str
    name: str
    gap_type: GapType
    strategy: RemediationStrategy

    # Steps
    steps: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)

    # Metadata
    success_rate: float = 0.0
    usage_count: int = 0
    avg_duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Optimization
    optimization_history: List[Dict] = field(default_factory=list)


class OutcomeTracker:
    """Track remediation outcomes"""

    def __init__(self):
        self.outcomes: List[RemediationOutcome] = []
        self.outcomes_by_strategy: Dict[RemediationStrategy, List[RemediationOutcome]] = defaultdict(list)
        self.outcomes_by_gap_type: Dict[GapType, List[RemediationOutcome]] = defaultdict(list)

        logger.info("Outcome Tracker initialized")

    def record_outcome(
        self,
        gap: CapabilityGap,
        plan: RemediationPlan,
        result: RemediationResult,
        duration_seconds: float,
    ) -> RemediationOutcome:
        """Record remediation outcome"""
        # Calculate quality scores
        completeness = self._calculate_completeness(result)
        effectiveness = self._calculate_effectiveness(result)
        efficiency = self._calculate_efficiency(duration_seconds, plan)

        # Extract lessons
        lessons = self._extract_lessons(gap, plan, result)

        # Generate improvement suggestions
        improvements = self._suggest_improvements(gap, plan, result)

        outcome = RemediationOutcome(
            gap_id=gap.gap_id,
            plan_id=plan.plan_id,
            strategy=plan.strategy,
            success=result.success,
            duration_seconds=duration_seconds,
            validation_passed=result.validation_passed,
            completeness_score=completeness,
            effectiveness_score=effectiveness,
            efficiency_score=efficiency,
            lessons_learned=lessons,
            improvements_suggested=improvements,
        )

        # Store outcome
        self.outcomes.append(outcome)
        self.outcomes_by_strategy[plan.strategy].append(outcome)
        self.outcomes_by_gap_type[gap.gap_type].append(outcome)

        logger.info(
            f"Outcome recorded: strategy={plan.strategy.value}, "
            f"success={result.success}, efficiency={efficiency:.2f}"
        )

        return outcome

    def get_strategy_success_rate(self, strategy: RemediationStrategy) -> float:
        """Get success rate for strategy"""
        outcomes = self.outcomes_by_strategy.get(strategy, [])
        if not outcomes:
            return 0.0

        successes = sum(1 for o in outcomes if o.success)
        return successes / len(outcomes)

    def get_avg_duration(self, strategy: RemediationStrategy) -> float:
        """Get average duration for strategy"""
        outcomes = self.outcomes_by_strategy.get(strategy, [])
        if not outcomes:
            return 0.0

        total_duration = sum(o.duration_seconds for o in outcomes)
        return total_duration / len(outcomes)

    def _calculate_completeness(self, result: RemediationResult) -> float:
        """Calculate how complete the remediation was"""
        score = 0.5  # Baseline

        # Check if actions were taken
        if result.actions_taken:
            score += 0.2

        # Check if artifacts were created
        if result.artifacts_created:
            score += 0.2

        # Check if validation passed
        if result.validation_passed:
            score += 0.1

        return min(1.0, score)

    def _calculate_effectiveness(self, result: RemediationResult) -> float:
        """Calculate how effective the remediation was"""
        if not result.success:
            return 0.0

        score = 0.5  # Baseline for success

        # Higher if validation passed
        if result.validation_passed:
            score += 0.3

        # Higher if artifacts created
        if result.artifacts_created:
            score += 0.2

        return min(1.0, score)

    def _calculate_efficiency(self, duration: float, plan: RemediationPlan) -> float:
        """Calculate efficiency (faster is better)"""
        # Expected durations by effort level
        expected_durations = {
            "low": 60,  # 1 minute
            "medium": 300,  # 5 minutes
            "high": 900,  # 15 minutes
        }

        expected = expected_durations.get(plan.estimated_effort, 300)

        # Efficiency = expected / actual (capped at 1.0)
        if duration <= 0:
            return 1.0

        efficiency = expected / duration
        return min(1.0, efficiency)

    def _extract_lessons(
        self,
        gap: CapabilityGap,
        plan: RemediationPlan,
        result: RemediationResult,
    ) -> List[str]:
        """Extract lessons learned"""
        lessons = []

        if not result.success:
            lessons.append(f"Strategy {plan.strategy.value} failed for {gap.gap_type.value}")

            if result.error_message:
                lessons.append(f"Error: {result.error_message}")

        elif result.validation_passed:
            lessons.append(f"Strategy {plan.strategy.value} effective for {gap.gap_type.value}")

        return lessons

    def _suggest_improvements(
        self,
        gap: CapabilityGap,
        plan: RemediationPlan,
        result: RemediationResult,
    ) -> List[str]:
        """Suggest improvements"""
        improvements = []

        if not result.success:
            improvements.append(f"Consider alternative strategy for {gap.gap_type.value}")

        if not result.validation_passed and result.success:
            improvements.append("Add stronger validation checks")

        if not result.artifacts_created:
            improvements.append("Ensure artifact creation for traceability")

        return improvements


class StrategyOptimizer:
    """Optimize remediation strategies based on outcomes"""

    def __init__(self, outcome_tracker: OutcomeTracker):
        self.tracker = outcome_tracker
        self.strategy_rankings: Dict[GapType, List[Tuple[RemediationStrategy, float]]] = {}

        logger.info("Strategy Optimizer initialized")

    def optimize_for_gap_type(self, gap_type: GapType) -> List[RemediationStrategy]:
        """Get optimized strategy ordering for gap type"""
        outcomes = self.tracker.outcomes_by_gap_type.get(gap_type, [])

        if not outcomes:
            # Return default ordering
            return self._default_strategy_order(gap_type)

        # Calculate scores for each strategy
        strategy_scores: Dict[RemediationStrategy, List[float]] = defaultdict(list)

        for outcome in outcomes:
            # Combined score: effectiveness * efficiency
            score = outcome.effectiveness_score * outcome.efficiency_score
            strategy_scores[outcome.strategy].append(score)

        # Calculate average scores
        avg_scores = {}
        for strategy, scores in strategy_scores.items():
            avg_scores[strategy] = sum(scores) / len(scores)

        # Sort strategies by average score
        sorted_strategies = sorted(
            avg_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Store rankings
        self.strategy_rankings[gap_type] = sorted_strategies

        logger.info(
            f"Optimized strategies for {gap_type.value}: "
            f"{[s.value for s, _ in sorted_strategies]}"
        )

        return [strategy for strategy, _ in sorted_strategies]

    def _default_strategy_order(self, gap_type: GapType) -> List[RemediationStrategy]:
        """Default strategy ordering by gap type"""
        defaults = {
            GapType.TOOL: [
                RemediationStrategy.INSTALL_PACKAGE,
                RemediationStrategy.CREATE_INTEGRATION,
                RemediationStrategy.MANUAL_INTERVENTION,
            ],
            GapType.KNOWLEDGE: [
                RemediationStrategy.IMPORT_KNOWLEDGE,
                RemediationStrategy.SYNTHESIZE_SKILL,
                RemediationStrategy.MANUAL_INTERVENTION,
            ],
            GapType.SKILL: [
                RemediationStrategy.SYNTHESIZE_SKILL,
                RemediationStrategy.EXTRACT_PATTERN,
                RemediationStrategy.MANUAL_INTERVENTION,
            ],
            GapType.PATTERN: [
                RemediationStrategy.EXTRACT_PATTERN,
                RemediationStrategy.SYNTHESIZE_SKILL,
                RemediationStrategy.MANUAL_INTERVENTION,
            ],
            GapType.INTEGRATION: [
                RemediationStrategy.CREATE_INTEGRATION,
                RemediationStrategy.INSTALL_PACKAGE,
                RemediationStrategy.MANUAL_INTERVENTION,
            ],
        }

        return defaults.get(gap_type, [RemediationStrategy.MANUAL_INTERVENTION])


class PlaybookLibrary:
    """Library of reusable remediation playbooks"""

    def __init__(self, playbooks_dir: Path):
        self.playbooks_dir = playbooks_dir
        self.playbooks_dir.mkdir(parents=True, exist_ok=True)

        self.playbooks: Dict[str, RemediationPlaybook] = {}
        self.playbooks_by_type: Dict[GapType, List[RemediationPlaybook]] = defaultdict(list)

        self._load_playbooks()

        logger.info(f"Playbook Library initialized: {len(self.playbooks)} playbooks")

    def _load_playbooks(self):
        """Load existing playbooks from disk"""
        for playbook_file in self.playbooks_dir.glob("*.json"):
            try:
                with open(playbook_file) as f:
                    data = json.load(f)

                playbook = RemediationPlaybook(
                    playbook_id=data["playbook_id"],
                    name=data["name"],
                    gap_type=GapType(data["gap_type"]),
                    strategy=RemediationStrategy(data["strategy"]),
                    steps=data.get("steps", []),
                    preconditions=data.get("preconditions", []),
                    postconditions=data.get("postconditions", []),
                    success_rate=data.get("success_rate", 0.0),
                    usage_count=data.get("usage_count", 0),
                    avg_duration_seconds=data.get("avg_duration_seconds", 0.0),
                )

                self.playbooks[playbook.playbook_id] = playbook
                self.playbooks_by_type[playbook.gap_type].append(playbook)

            except Exception as e:
                logger.warning(f"Failed to load playbook {playbook_file}: {e}")

    def create_playbook(
        self,
        name: str,
        gap: CapabilityGap,
        plan: RemediationPlan,
        outcome: RemediationOutcome,
    ) -> RemediationPlaybook:
        """Create new playbook from successful remediation"""
        playbook_id = f"{gap.gap_type.value}_{plan.strategy.value}_{len(self.playbooks)}"

        playbook = RemediationPlaybook(
            playbook_id=playbook_id,
            name=name,
            gap_type=gap.gap_type,
            strategy=plan.strategy,
            steps=plan.steps,
            success_rate=1.0 if outcome.success else 0.0,
            usage_count=1,
            avg_duration_seconds=outcome.duration_seconds,
        )

        # Save playbook
        self._save_playbook(playbook)

        self.playbooks[playbook_id] = playbook
        self.playbooks_by_type[gap.gap_type].append(playbook)

        logger.info(f"Created playbook: {playbook_id}")

        return playbook

    def find_similar_playbook(self, gap: CapabilityGap) -> Optional[RemediationPlaybook]:
        """Find playbook for similar gap"""
        candidates = self.playbooks_by_type.get(gap.gap_type, [])

        if not candidates:
            return None

        # Sort by success rate
        candidates.sort(key=lambda p: p.success_rate, reverse=True)

        # Return best playbook
        if candidates[0].success_rate > 0.5:
            return candidates[0]

        return None

    def update_playbook(
        self,
        playbook_id: str,
        outcome: RemediationOutcome,
    ):
        """Update playbook with new outcome"""
        playbook = self.playbooks.get(playbook_id)
        if not playbook:
            return

        # Update statistics
        playbook.usage_count += 1

        # Update success rate (exponential moving average)
        success_value = 1.0 if outcome.success else 0.0
        playbook.success_rate = (
            0.9 * playbook.success_rate + 0.1 * success_value
        )

        # Update average duration
        playbook.avg_duration_seconds = (
            0.9 * playbook.avg_duration_seconds + 0.1 * outcome.duration_seconds
        )

        playbook.updated_at = datetime.now()

        # Record optimization
        playbook.optimization_history.append({
            "timestamp": datetime.now().isoformat(),
            "success_rate": playbook.success_rate,
            "usage_count": playbook.usage_count,
        })

        # Save updated playbook
        self._save_playbook(playbook)

        logger.info(
            f"Updated playbook {playbook_id}: "
            f"success_rate={playbook.success_rate:.2f}, "
            f"usage={playbook.usage_count}"
        )

    def _save_playbook(self, playbook: RemediationPlaybook):
        """Save playbook to disk"""
        playbook_file = self.playbooks_dir / f"{playbook.playbook_id}.json"

        data = {
            "playbook_id": playbook.playbook_id,
            "name": playbook.name,
            "gap_type": playbook.gap_type.value,
            "strategy": playbook.strategy.value,
            "steps": playbook.steps,
            "preconditions": playbook.preconditions,
            "postconditions": playbook.postconditions,
            "success_rate": playbook.success_rate,
            "usage_count": playbook.usage_count,
            "avg_duration_seconds": playbook.avg_duration_seconds,
            "created_at": playbook.created_at.isoformat(),
            "updated_at": playbook.updated_at.isoformat(),
            "optimization_history": playbook.optimization_history,
        }

        with open(playbook_file, "w") as f:
            json.dump(data, f, indent=2)


class QualityImprover:
    """Improve remediation quality over time"""

    def __init__(self, tracker: OutcomeTracker):
        self.tracker = tracker
        self.improvement_suggestions: List[str] = []

        logger.info("Quality Improver initialized")

    def analyze_quality_trends(self) -> Dict[str, Any]:
        """Analyze quality trends"""
        if not self.tracker.outcomes:
            return {"status": "insufficient_data"}

        recent = self.tracker.outcomes[-100:]  # Last 100

        # Calculate trend metrics
        avg_effectiveness = sum(o.effectiveness_score for o in recent) / len(recent)
        avg_efficiency = sum(o.efficiency_score for o in recent) / len(recent)
        success_rate = sum(1 for o in recent if o.success) / len(recent)

        # Detect trends
        if len(recent) >= 20:
            recent_20 = recent[-20:]
            prev_20 = recent[-40:-20] if len(recent) >= 40 else recent[:20]

            recent_success = sum(1 for o in recent_20 if o.success) / len(recent_20)
            prev_success = sum(1 for o in prev_20 if o.success) / len(prev_20)

            trend = "improving" if recent_success > prev_success else "declining" if recent_success < prev_success else "stable"
        else:
            trend = "unknown"

        return {
            "avg_effectiveness": avg_effectiveness,
            "avg_efficiency": avg_efficiency,
            "success_rate": success_rate,
            "trend": trend,
            "sample_size": len(recent),
        }

    def generate_improvement_recommendations(self) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []

        trends = self.analyze_quality_trends()

        if trends.get("success_rate", 0) < 0.7:
            recommendations.append("Success rate below 70% - review strategy selection")

        if trends.get("avg_efficiency", 0) < 0.5:
            recommendations.append("Low efficiency detected - optimize remediation steps")

        if trends.get("trend") == "declining":
            recommendations.append("Quality trend declining - investigate recent changes")

        # Collect suggestions from outcomes
        recent_outcomes = self.tracker.outcomes[-50:]
        all_suggestions = []
        for outcome in recent_outcomes:
            all_suggestions.extend(outcome.improvements_suggested)

        # Find most common suggestions
        suggestion_counts = defaultdict(int)
        for suggestion in all_suggestions:
            suggestion_counts[suggestion] += 1

        # Add frequent suggestions
        for suggestion, count in suggestion_counts.items():
            if count >= 3:
                recommendations.append(f"{suggestion} (mentioned {count} times)")

        self.improvement_suggestions = recommendations

        return recommendations


async def main():
    """Test remediation learning loop"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Remediation Learning Loop Test")
    logger.info("=" * 60)

    # Initialize components
    tracker = OutcomeTracker()
    optimizer = StrategyOptimizer(tracker)
    library = PlaybookLibrary(Path(".agents/playbooks"))
    improver = QualityImprover(tracker)

    # Simulate some outcomes
    logger.info("\n1. Recording Outcomes:")

    from gap_detection import GapSeverity

    # Create sample gap
    gap = CapabilityGap(
        gap_id="test_gap_1",
        gap_type=GapType.TOOL,
        severity=GapSeverity.HIGH,
        description="Missing jq tool",
    )

    # Create sample plan
    plan = RemediationPlan(
        plan_id="plan_1",
        gap_id="test_gap_1",
        strategy=RemediationStrategy.INSTALL_PACKAGE,
        steps=["Search for package", "Add to configuration", "Rebuild"],
        estimated_effort="low",
    )

    # Create sample result
    result = RemediationResult(
        plan_id="plan_1",
        gap_id="test_gap_1",
        status=RemediationStatus.SUCCESSFUL,
        success=True,
        actions_taken=["Added jq to configuration.nix"],
        artifacts_created=["configuration.nix"],
        validation_passed=True,
    )

    # Record outcome
    outcome = tracker.record_outcome(gap, plan, result, duration_seconds=45.0)

    logger.info(f"  Effectiveness: {outcome.effectiveness_score:.2f}")
    logger.info(f"  Efficiency: {outcome.efficiency_score:.2f}")

    # Test 2: Strategy optimization
    logger.info("\n2. Strategy Optimization:")

    strategies = optimizer.optimize_for_gap_type(GapType.TOOL)
    logger.info(f"  Optimized strategies for TOOL gaps:")
    for strategy in strategies:
        logger.info(f"    - {strategy.value}")

    # Test 3: Playbook creation
    logger.info("\n3. Playbook Management:")

    playbook = library.create_playbook(
        "Install Package via Nix",
        gap,
        plan,
        outcome,
    )

    logger.info(f"  Created: {playbook.name}")
    logger.info(f"  Success rate: {playbook.success_rate:.2f}")

    # Test 4: Quality analysis
    logger.info("\n4. Quality Analysis:")

    trends = improver.analyze_quality_trends()
    logger.info(f"  Success rate: {trends.get('success_rate', 0):.2f}")
    logger.info(f"  Trend: {trends.get('trend', 'unknown')}")

    recommendations = improver.generate_improvement_recommendations()
    if recommendations:
        logger.info("  Recommendations:")
        for rec in recommendations[:3]:
            logger.info(f"    - {rec}")


if __name__ == "__main__":
    asyncio.run(main())
