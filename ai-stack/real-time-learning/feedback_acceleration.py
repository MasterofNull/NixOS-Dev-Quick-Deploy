#!/usr/bin/env python3
"""
Feedback Loop Acceleration

Immediate feedback incorporation for rapid system improvement.
Part of Phase 10 Batch 10.2: Feedback Loop Acceleration

Key Features:
- Immediate feedback incorporation
- Automatic success/failure detection
- Feedback aggregation across sessions
- Feedback-driven prioritization
- Feedback quality scoring
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback"""
    EXPLICIT = "explicit"  # User provided directly
    IMPLICIT = "implicit"  # Inferred from behavior
    AUTOMATED = "automated"  # System-detected


class FeedbackSentiment(Enum):
    """Feedback sentiment"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


@dataclass
class Feedback:
    """User or system feedback"""
    feedback_id: str
    feedback_type: FeedbackType
    sentiment: FeedbackSentiment
    content: str
    score: float  # 0-1
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    # Quality
    quality_score: float = 0.5  # How reliable is this feedback
    confidence: float = 0.7

    # Processing
    processed: bool = False
    actions_taken: List[str] = field(default_factory=list)


@dataclass
class ImprovementAction:
    """Action taken based on feedback"""
    action_id: str
    feedback_ids: List[str]
    description: str
    priority: float
    executed_at: Optional[datetime] = None
    impact_score: float = 0.0


class ImmediateFeedbackProcessor:
    """Process and incorporate feedback immediately"""

    def __init__(self):
        self.feedback_queue: deque = deque(maxlen=1000)
        self.processed_feedback: List[Feedback] = []
        self.pending_actions: List[ImprovementAction] = []

        logger.info("Immediate Feedback Processor initialized")

    async def process_feedback(self, feedback: Feedback) -> List[ImprovementAction]:
        """Process feedback immediately"""
        logger.info(f"Processing feedback: {feedback.feedback_id} ({feedback.sentiment.value})")

        # Add to queue
        self.feedback_queue.append(feedback)

        # Analyze feedback
        actions = await self._analyze_feedback(feedback)

        # Execute high-priority actions immediately
        immediate_actions = [a for a in actions if a.priority > 0.8]

        for action in immediate_actions:
            await self._execute_action(action)

        # Queue lower-priority actions
        deferred_actions = [a for a in actions if a.priority <= 0.8]
        self.pending_actions.extend(deferred_actions)

        # Mark as processed
        feedback.processed = True
        feedback.actions_taken = [a.action_id for a in actions]
        self.processed_feedback.append(feedback)

        logger.info(
            f"  Immediate actions: {len(immediate_actions)}, "
            f"Deferred actions: {len(deferred_actions)}"
        )

        return actions

    async def _analyze_feedback(self, feedback: Feedback) -> List[ImprovementAction]:
        """Analyze feedback and determine actions"""
        actions = []

        # Negative feedback → investigate and fix
        if feedback.sentiment == FeedbackSentiment.NEGATIVE:
            if "slow" in feedback.content.lower():
                actions.append(ImprovementAction(
                    action_id=self._generate_action_id(),
                    feedback_ids=[feedback.feedback_id],
                    description="Investigate and optimize performance",
                    priority=0.9,
                ))

            elif "error" in feedback.content.lower() or "bug" in feedback.content.lower():
                actions.append(ImprovementAction(
                    action_id=self._generate_action_id(),
                    feedback_ids=[feedback.feedback_id],
                    description="Debug and fix reported issue",
                    priority=0.95,
                ))

            elif "unclear" in feedback.content.lower() or "confusing" in feedback.content.lower():
                actions.append(ImprovementAction(
                    action_id=self._generate_action_id(),
                    feedback_ids=[feedback.feedback_id],
                    description="Improve clarity of response",
                    priority=0.7,
                ))

        # Positive feedback → reinforce and learn
        elif feedback.sentiment == FeedbackSentiment.POSITIVE:
            actions.append(ImprovementAction(
                action_id=self._generate_action_id(),
                feedback_ids=[feedback.feedback_id],
                description="Reinforce successful pattern",
                priority=0.6,
            ))

        return actions

    async def _execute_action(self, action: ImprovementAction):
        """Execute improvement action"""
        logger.info(f"Executing action: {action.description}")

        # In production, would actually apply changes
        # For now, just mark as executed
        action.executed_at = datetime.now()

        # Simulate impact
        action.impact_score = 0.5  # Placeholder

    def _generate_action_id(self) -> str:
        """Generate unique action ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]

    def get_pending_actions(self, limit: int = 10) -> List[ImprovementAction]:
        """Get top pending actions"""
        self.pending_actions.sort(key=lambda a: a.priority, reverse=True)
        return self.pending_actions[:limit]


class SuccessFailureDetector:
    """Automatically detect success/failure from interactions"""

    def __init__(self):
        self.detection_patterns = {
            "success": [
                r"thank",
                r"perfect",
                r"exactly what i needed",
                r"great",
                r"helpful",
            ],
            "failure": [
                r"doesn't work",
                r"error",
                r"failed",
                r"wrong",
                r"not what i",
            ],
        }

        logger.info("Success/Failure Detector initialized")

    def detect_outcome(
        self,
        query: str,
        response: str,
        user_followup: Optional[str] = None,
    ) -> Tuple[bool, float]:
        """Detect if interaction was successful"""
        success_indicators = 0
        failure_indicators = 0

        # Check response for failure patterns
        response_lower = response.lower()

        for pattern in self.detection_patterns["failure"]:
            if pattern in response_lower:
                failure_indicators += 1

        # Check user followup
        if user_followup:
            followup_lower = user_followup.lower()

            for pattern in self.detection_patterns["success"]:
                if pattern in followup_lower:
                    success_indicators += 1

            for pattern in self.detection_patterns["failure"]:
                if pattern in followup_lower:
                    failure_indicators += 1

        # Determine outcome
        if success_indicators > failure_indicators:
            success = True
            confidence = min(0.9, 0.5 + (success_indicators * 0.1))
        elif failure_indicators > success_indicators:
            success = False
            confidence = min(0.9, 0.5 + (failure_indicators * 0.1))
        else:
            # Ambiguous - assume neutral success
            success = True
            confidence = 0.5

        logger.debug(
            f"Detected outcome: success={success}, "
            f"confidence={confidence:.2f}"
        )

        return success, confidence

    def create_implicit_feedback(
        self,
        query: str,
        response: str,
        user_followup: Optional[str],
    ) -> Feedback:
        """Create implicit feedback from interaction"""
        success, confidence = self.detect_outcome(query, response, user_followup)

        sentiment = FeedbackSentiment.POSITIVE if success else FeedbackSentiment.NEGATIVE
        score = confidence if success else (1.0 - confidence)

        content = f"Interaction {'succeeded' if success else 'failed'} based on user behavior"

        feedback = Feedback(
            feedback_id=self._generate_feedback_id(),
            feedback_type=FeedbackType.IMPLICIT,
            sentiment=sentiment,
            content=content,
            score=score,
            quality_score=confidence,
            confidence=confidence,
            context={
                "query": query[:100],
                "response_length": len(response),
                "had_followup": user_followup is not None,
            },
        )

        return feedback

    def _generate_feedback_id(self) -> str:
        """Generate unique feedback ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]


class FeedbackAggregator:
    """Aggregate feedback across sessions"""

    def __init__(self):
        self.feedback_by_topic: Dict[str, List[Feedback]] = defaultdict(list)
        self.feedback_by_session: Dict[str, List[Feedback]] = defaultdict(list)
        self.aggregate_insights: Dict[str, Any] = {}

        logger.info("Feedback Aggregator initialized")

    def add_feedback(self, feedback: Feedback, session_id: str, topic: str):
        """Add feedback to aggregation"""
        self.feedback_by_session[session_id].append(feedback)
        self.feedback_by_topic[topic].append(feedback)

        # Trigger re-aggregation if needed
        if len(self.feedback_by_topic[topic]) % 10 == 0:
            self._aggregate_topic(topic)

    def _aggregate_topic(self, topic: str):
        """Aggregate feedback for topic"""
        feedbacks = self.feedback_by_topic[topic]

        if not feedbacks:
            return

        # Calculate aggregate metrics
        total_count = len(feedbacks)
        positive_count = sum(1 for f in feedbacks if f.sentiment == FeedbackSentiment.POSITIVE)
        negative_count = sum(1 for f in feedbacks if f.sentiment == FeedbackSentiment.NEGATIVE)

        avg_score = sum(f.score for f in feedbacks) / total_count
        avg_quality = sum(f.quality_score for f in feedbacks) / total_count

        # Extract common themes
        themes = self._extract_themes(feedbacks)

        self.aggregate_insights[topic] = {
            "total_feedback": total_count,
            "positive_ratio": positive_count / total_count,
            "negative_ratio": negative_count / total_count,
            "avg_score": avg_score,
            "avg_quality": avg_quality,
            "common_themes": themes,
            "updated_at": datetime.now(),
        }

        logger.info(
            f"Aggregated feedback for {topic}: "
            f"{positive_count}+ / {negative_count}- "
            f"(score={avg_score:.2f})"
        )

    def _extract_themes(self, feedbacks: List[Feedback]) -> List[str]:
        """Extract common themes from feedback"""
        # Simplified theme extraction
        word_freq = defaultdict(int)

        for feedback in feedbacks:
            words = feedback.content.lower().split()
            for word in words:
                if len(word) > 4:  # Skip short words
                    word_freq[word] += 1

        # Top themes
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        themes = [word for word, _ in top_words]

        return themes

    def get_topic_insights(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get aggregated insights for topic"""
        return self.aggregate_insights.get(topic)

    def get_cross_session_patterns(self) -> Dict[str, Any]:
        """Get patterns across sessions"""
        if not self.feedback_by_session:
            return {}

        # Calculate cross-session metrics
        total_sessions = len(self.feedback_by_session)
        session_scores = []

        for session_id, feedbacks in self.feedback_by_session.items():
            if feedbacks:
                avg_score = sum(f.score for f in feedbacks) / len(feedbacks)
                session_scores.append(avg_score)

        overall_avg = sum(session_scores) / len(session_scores) if session_scores else 0

        return {
            "total_sessions": total_sessions,
            "avg_session_score": overall_avg,
            "session_count": len(session_scores),
        }


class FeedbackDrivenPrioritizer:
    """Prioritize work based on feedback"""

    def __init__(self):
        self.priority_scores: Dict[str, float] = {}

        logger.info("Feedback-Driven Prioritizer initialized")

    def calculate_priorities(
        self,
        tasks: List[str],
        feedback_insights: Dict[str, Dict[str, Any]],
    ) -> Dict[str, float]:
        """Calculate task priorities based on feedback"""
        for task in tasks:
            # Find related feedback
            related_feedback = self._find_related_feedback(task, feedback_insights)

            if not related_feedback:
                # Default priority
                self.priority_scores[task] = 0.5
                continue

            # Calculate priority from feedback
            negative_ratio = related_feedback.get("negative_ratio", 0)
            total_feedback = related_feedback.get("total_feedback", 0)

            # Higher priority for:
            # - More negative feedback
            # - More total feedback (indicates importance)
            priority = (
                negative_ratio * 0.6 +
                min(1.0, total_feedback / 100) * 0.4
            )

            self.priority_scores[task] = priority

        return self.priority_scores

    def _find_related_feedback(
        self,
        task: str,
        feedback_insights: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Find feedback related to task"""
        task_words = set(task.lower().split())

        for topic, insights in feedback_insights.items():
            topic_words = set(topic.lower().split())

            # Check overlap
            overlap = len(task_words & topic_words)
            if overlap > 0:
                return insights

        return None

    def get_top_priorities(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get top priority tasks"""
        priorities = sorted(
            self.priority_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return priorities[:limit]


class FeedbackQualityScorer:
    """Score feedback quality"""

    def __init__(self):
        logger.info("Feedback Quality Scorer initialized")

    def score_feedback(self, feedback: Feedback) -> float:
        """Score feedback quality"""
        score = 0.5  # Baseline

        # Explicit feedback is generally high quality
        if feedback.feedback_type == FeedbackType.EXPLICIT:
            score += 0.3

        # Longer feedback is often more informative
        content_length = len(feedback.content)
        if content_length > 50:
            score += 0.1

        # Confident feedback is more reliable
        score += feedback.confidence * 0.1

        # Update feedback quality score
        feedback.quality_score = min(1.0, score)

        return feedback.quality_score


async def main():
    """Test feedback acceleration system"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Feedback Loop Acceleration Test")
    logger.info("=" * 60)

    # Test 1: Immediate feedback processing
    logger.info("\n1. Immediate Feedback Processing:")

    processor = ImmediateFeedbackProcessor()

    negative_feedback = Feedback(
        feedback_id="fb1",
        feedback_type=FeedbackType.EXPLICIT,
        sentiment=FeedbackSentiment.NEGATIVE,
        content="The system is too slow and gives errors",
        score=0.2,
    )

    actions = await processor.process_feedback(negative_feedback)

    logger.info(f"  Actions generated: {len(actions)}")
    for action in actions:
        logger.info(f"    - {action.description} (priority={action.priority:.2f})")

    # Test 2: Success/failure detection
    logger.info("\n2. Automatic Success/Failure Detection:")

    detector = SuccessFailureDetector()

    feedback = detector.create_implicit_feedback(
        query="How do I configure nixos?",
        response="Here are the steps...",
        user_followup="Thank you, that's perfect!",
    )

    logger.info(f"  Detected sentiment: {feedback.sentiment.value}")
    logger.info(f"  Confidence: {feedback.confidence:.2f}")

    # Test 3: Feedback aggregation
    logger.info("\n3. Feedback Aggregation:")

    aggregator = FeedbackAggregator()

    for i in range(15):
        fb = Feedback(
            feedback_id=f"fb_{i}",
            feedback_type=FeedbackType.IMPLICIT,
            sentiment=FeedbackSentiment.POSITIVE if i % 3 != 0 else FeedbackSentiment.NEGATIVE,
            content=f"Feedback content {i}",
            score=0.8 if i % 3 != 0 else 0.3,
        )

        aggregator.add_feedback(fb, session_id="session_1", topic="nixos_config")

    insights = aggregator.get_topic_insights("nixos_config")
    if insights:
        logger.info(f"  Total feedback: {insights['total_feedback']}")
        logger.info(f"  Positive ratio: {insights['positive_ratio']:.2%}")
        logger.info(f"  Average score: {insights['avg_score']:.2f}")

    # Test 4: Feedback-driven prioritization
    logger.info("\n4. Feedback-Driven Prioritization:")

    prioritizer = FeedbackDrivenPrioritizer()

    tasks = [
        "improve_nixos_config",
        "add_documentation",
        "optimize_performance",
    ]

    feedback_insights = {
        "nixos_config": insights,
    }

    priorities = prioritizer.calculate_priorities(tasks, feedback_insights)

    logger.info("  Task priorities:")
    for task, priority in sorted(priorities.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"    {task}: {priority:.2f}")

    # Test 5: Feedback quality scoring
    logger.info("\n5. Feedback Quality Scoring:")

    quality_scorer = FeedbackQualityScorer()

    high_quality_fb = Feedback(
        feedback_id="fb_quality",
        feedback_type=FeedbackType.EXPLICIT,
        sentiment=FeedbackSentiment.POSITIVE,
        content="This is very detailed feedback about the system's performance and usability",
        score=0.9,
        confidence=0.95,
    )

    quality = quality_scorer.score_feedback(high_quality_fb)
    logger.info(f"  Feedback quality score: {quality:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
