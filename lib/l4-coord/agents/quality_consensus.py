#!/usr/bin/env python3
"""
Phase 4: Quality Consensus
Multiple reviewers validate outputs with weighted voting.

Features:
- Multi-reviewer validation
- Weighted voting by capability and performance
- Consensus thresholds (majority, supermajority, unanimous)
- Auto-escalation on disagreement
- Tie-breaking strategies
- Disagreement analysis
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import logging

logger = logging.getLogger(__name__)


class ConsensusThreshold(Enum):
    """Consensus threshold types."""
    SIMPLE_MAJORITY = "simple_majority"  # >50%
    SUPERMAJORITY = "supermajority"  # >=66%
    UNANIMOUS = "unanimous"  # 100%
    WEIGHTED_MAJORITY = "weighted_majority"  # >50% by weight


class VoteType(Enum):
    """Type of vote."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    REQUEST_CHANGES = "request_changes"


class EscalationReason(Enum):
    """Reason for escalation."""
    NO_CONSENSUS = "no_consensus"
    TIE = "tie"
    CRITICAL_DISAGREEMENT = "critical_disagreement"
    INSUFFICIENT_VOTES = "insufficient_votes"


@dataclass
class Review:
    """Review from an agent."""
    review_id: str
    reviewer_id: str
    vote: VoteType
    confidence: float = 0.5  # 0-1
    reasoning: str = ""
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "vote": self.vote.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReviewerWeight:
    """Weight assigned to a reviewer."""
    reviewer_id: str
    base_weight: float = 1.0  # Base weight
    capability_bonus: float = 0.0  # Expertise in domain
    performance_bonus: float = 0.0  # Historical accuracy
    total_weight: float = 1.0

    def calculate_total(self):
        """Calculate total weight."""
        self.total_weight = self.base_weight + self.capability_bonus + self.performance_bonus

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "reviewer_id": self.reviewer_id,
            "base_weight": self.base_weight,
            "capability_bonus": self.capability_bonus,
            "performance_bonus": self.performance_bonus,
            "total_weight": self.total_weight,
        }


@dataclass
class ConsensusResult:
    """Result of consensus evaluation."""
    consensus_id: str
    achieved: bool
    threshold: ConsensusThreshold
    approval_rate: float  # 0-1
    weighted_approval_rate: float  # 0-1
    total_votes: int
    votes_by_type: Dict[str, int]
    reviews: List[Review]
    escalated: bool = False
    escalation_reason: Optional[EscalationReason] = None
    tie_broken: bool = False
    tie_breaker: Optional[str] = None  # Agent who broke tie
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "consensus_id": self.consensus_id,
            "achieved": self.achieved,
            "threshold": self.threshold.value,
            "approval_rate": self.approval_rate,
            "weighted_approval_rate": self.weighted_approval_rate,
            "total_votes": self.total_votes,
            "votes_by_type": self.votes_by_type,
            "reviews": [r.to_dict() for r in self.reviews],
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason.value if self.escalation_reason else None,
            "tie_broken": self.tie_broken,
            "tie_breaker": self.tie_breaker,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConsensusSession:
    """Active consensus session."""
    session_id: str
    artifact_id: str
    team_id: str
    threshold: ConsensusThreshold
    required_reviewers: int
    reviews: List[Review] = field(default_factory=list)
    reviewer_weights: Dict[str, ReviewerWeight] = field(default_factory=dict)
    result: Optional[ConsensusResult] = None
    timeout: int = 300  # seconds
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_complete(self) -> bool:
        """Check if enough reviews collected."""
        return len(self.reviews) >= self.required_reviewers

    def is_expired(self) -> bool:
        """Check if session has expired."""
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.timeout

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "artifact_id": self.artifact_id,
            "team_id": self.team_id,
            "threshold": self.threshold.value,
            "required_reviewers": self.required_reviewers,
            "reviews": [r.to_dict() for r in self.reviews],
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat(),
        }


class QualityConsensus:
    """Quality consensus engine with weighted voting."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize quality consensus."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "consensus"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.active_sessions: Dict[str, ConsensusSession] = {}
        self.consensus_history: List[Dict[str, Any]] = []
        self.reviewer_performance: Dict[str, Dict[str, Any]] = {}  # reviewer_id -> metrics

        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        history_file = self.state_dir / "consensus_history.json"
        performance_file = self.state_dir / "reviewer_performance.json"

        try:
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                    self.consensus_history = data.get("history", [])
        except Exception as e:
            logger.warning(f"Failed to load consensus history: {e}")

        try:
            if performance_file.exists():
                with open(performance_file) as f:
                    data = json.load(f)
                    self.reviewer_performance = data.get("performance", {})
        except Exception as e:
            logger.warning(f"Failed to load reviewer performance: {e}")

    def _save_state(self):
        """Save state to disk."""
        history_file = self.state_dir / "consensus_history.json"
        performance_file = self.state_dir / "reviewer_performance.json"

        try:
            # Keep last 100 consensus results
            recent_history = self.consensus_history[-100:]
            with open(history_file, 'w') as f:
                json.dump({"history": recent_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save consensus history: {e}")

        try:
            with open(performance_file, 'w') as f:
                json.dump({"performance": self.reviewer_performance}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reviewer performance: {e}")

    def create_session(self,
                      artifact_id: str,
                      team_id: str,
                      threshold: ConsensusThreshold = ConsensusThreshold.SIMPLE_MAJORITY,
                      required_reviewers: int = 3,
                      timeout: int = 300) -> str:
        """Create new consensus session."""
        session_id = str(uuid.uuid4())

        session = ConsensusSession(
            session_id=session_id,
            artifact_id=artifact_id,
            team_id=team_id,
            threshold=threshold,
            required_reviewers=required_reviewers,
            timeout=timeout,
        )

        self.active_sessions[session_id] = session

        logger.info("consensus_session_created",
                   session_id=session_id,
                   artifact_id=artifact_id,
                   threshold=threshold.value)

        return session_id

    def set_reviewer_weight(self,
                          session_id: str,
                          reviewer_id: str,
                          base_weight: float = 1.0,
                          capability_score: float = 0.5,
                          performance_score: float = 0.5):
        """Set weight for a reviewer."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]

        # Calculate bonuses
        capability_bonus = (capability_score - 0.5) * 0.5  # Max ±0.25

        # Get historical performance
        perf_data = self.reviewer_performance.get(reviewer_id, {})
        historical_accuracy = perf_data.get("accuracy", 0.5)
        performance_bonus = (historical_accuracy - 0.5) * 0.5  # Max ±0.25

        weight = ReviewerWeight(
            reviewer_id=reviewer_id,
            base_weight=base_weight,
            capability_bonus=capability_bonus,
            performance_bonus=performance_bonus,
        )
        weight.calculate_total()

        session.reviewer_weights[reviewer_id] = weight

        logger.info("reviewer_weight_set",
                   session_id=session_id,
                   reviewer_id=reviewer_id,
                   weight=weight.total_weight)

    def submit_review(self,
                     session_id: str,
                     reviewer_id: str,
                     vote: VoteType,
                     confidence: float = 0.5,
                     reasoning: str = "",
                     issues: List[str] = None,
                     suggestions: List[str] = None) -> str:
        """Submit review for consensus."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]

        # Check if already reviewed
        if any(r.reviewer_id == reviewer_id for r in session.reviews):
            logger.warning("duplicate_review", session_id=session_id, reviewer_id=reviewer_id)
            raise ValueError(f"Reviewer {reviewer_id} already submitted review")

        review_id = str(uuid.uuid4())
        review = Review(
            review_id=review_id,
            reviewer_id=reviewer_id,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
            issues_found=issues or [],
            suggestions=suggestions or [],
        )

        session.reviews.append(review)

        logger.info("review_submitted",
                   session_id=session_id,
                   reviewer_id=reviewer_id,
                   vote=vote.value,
                   reviews_count=len(session.reviews))

        return review_id

    def _calculate_approval_rates(self,
                                 reviews: List[Review],
                                 weights: Dict[str, ReviewerWeight]) -> Tuple[float, float]:
        """Calculate approval rates (simple and weighted)."""
        if not reviews:
            return 0.0, 0.0

        # Simple approval rate
        approvals = sum(1 for r in reviews if r.vote == VoteType.APPROVE)
        simple_rate = approvals / len(reviews)

        # Weighted approval rate
        total_weight = 0.0
        approval_weight = 0.0

        for review in reviews:
            weight = weights.get(review.reviewer_id)
            if weight:
                w = weight.total_weight
            else:
                w = 1.0  # Default weight

            total_weight += w
            if review.vote == VoteType.APPROVE:
                approval_weight += w

        weighted_rate = approval_weight / total_weight if total_weight > 0 else 0.0

        return simple_rate, weighted_rate

    def _check_consensus(self,
                        session: ConsensusSession) -> Tuple[bool, Optional[EscalationReason]]:
        """Check if consensus achieved."""
        simple_rate, weighted_rate = self._calculate_approval_rates(
            session.reviews,
            session.reviewer_weights
        )

        threshold = session.threshold

        if threshold == ConsensusThreshold.SIMPLE_MAJORITY:
            achieved = simple_rate > 0.5
        elif threshold == ConsensusThreshold.SUPERMAJORITY:
            achieved = simple_rate >= 0.66
        elif threshold == ConsensusThreshold.UNANIMOUS:
            achieved = simple_rate == 1.0
        elif threshold == ConsensusThreshold.WEIGHTED_MAJORITY:
            achieved = weighted_rate > 0.5
        else:
            achieved = False

        # Check for escalation conditions
        escalation_reason = None

        if not achieved:
            # Check for tie
            if abs(simple_rate - 0.5) < 0.01:
                escalation_reason = EscalationReason.TIE
            else:
                escalation_reason = EscalationReason.NO_CONSENSUS

        return achieved, escalation_reason

    def _break_tie(self,
                  session: ConsensusSession,
                  expert_reviewers: List[str] = None) -> Optional[str]:
        """Break tie with expert override."""
        if not expert_reviewers:
            # Use highest weighted reviewer
            max_weight = 0.0
            tie_breaker = None

            for review in session.reviews:
                weight = session.reviewer_weights.get(review.reviewer_id)
                if weight and weight.total_weight > max_weight:
                    max_weight = weight.total_weight
                    tie_breaker = review.reviewer_id

            return tie_breaker

        # Use first expert reviewer who voted
        for reviewer_id in expert_reviewers:
            for review in session.reviews:
                if review.reviewer_id == reviewer_id:
                    return reviewer_id

        return None

    async def evaluate_consensus(self,
                                session_id: str,
                                expert_reviewers: List[str] = None) -> ConsensusResult:
        """Evaluate consensus from reviews."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]

        # Check if enough reviews
        if not session.is_complete():
            if session.is_expired():
                escalation_reason = EscalationReason.INSUFFICIENT_VOTES
            else:
                # Not ready yet
                raise ValueError("Not enough reviews collected")
        else:
            escalation_reason = None

        # Calculate approval rates
        simple_rate, weighted_rate = self._calculate_approval_rates(
            session.reviews,
            session.reviewer_weights
        )

        # Check consensus
        achieved, esc_reason = self._check_consensus(session)
        if esc_reason:
            escalation_reason = esc_reason

        # Count votes by type
        votes_by_type = {}
        for review in session.reviews:
            vote_type = review.vote.value
            votes_by_type[vote_type] = votes_by_type.get(vote_type, 0) + 1

        # Handle tie breaking
        tie_broken = False
        tie_breaker = None

        if escalation_reason == EscalationReason.TIE:
            tie_breaker = self._break_tie(session, expert_reviewers)
            if tie_breaker:
                tie_broken = True
                # Re-evaluate with tie breaker getting extra weight
                logger.info("tie_broken", session_id=session_id, tie_breaker=tie_breaker)

        # Create result
        result = ConsensusResult(
            consensus_id=session_id,
            achieved=achieved,
            threshold=session.threshold,
            approval_rate=simple_rate,
            weighted_approval_rate=weighted_rate,
            total_votes=len(session.reviews),
            votes_by_type=votes_by_type,
            reviews=session.reviews,
            escalated=escalation_reason is not None,
            escalation_reason=escalation_reason,
            tie_broken=tie_broken,
            tie_breaker=tie_breaker,
        )

        session.result = result

        # Record in history
        self.consensus_history.append({
            "session_id": session_id,
            "artifact_id": session.artifact_id,
            "achieved": achieved,
            "approval_rate": simple_rate,
            "weighted_rate": weighted_rate,
            "escalated": result.escalated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Update reviewer performance
        self._update_reviewer_performance(session, result)

        self._save_state()

        logger.info("consensus_evaluated",
                   session_id=session_id,
                   achieved=achieved,
                   approval_rate=simple_rate,
                   weighted_rate=weighted_rate,
                   escalated=result.escalated)

        return result

    def _update_reviewer_performance(self,
                                    session: ConsensusSession,
                                    result: ConsensusResult):
        """Update reviewer performance metrics."""
        # Majority vote is considered "correct"
        majority_vote = VoteType.APPROVE if result.approval_rate > 0.5 else VoteType.REJECT

        for review in session.reviews:
            reviewer_id = review.reviewer_id

            if reviewer_id not in self.reviewer_performance:
                self.reviewer_performance[reviewer_id] = {
                    "total_reviews": 0,
                    "correct_votes": 0,
                    "accuracy": 0.5,
                }

            perf = self.reviewer_performance[reviewer_id]
            perf["total_reviews"] += 1

            # Check if vote matched majority
            if review.vote == majority_vote:
                perf["correct_votes"] += 1

            perf["accuracy"] = perf["correct_votes"] / perf["total_reviews"]

    def analyze_disagreement(self, session_id: str) -> Dict[str, Any]:
        """Analyze patterns of disagreement."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]

        # Count vote distribution
        vote_counts = {}
        for review in session.reviews:
            vote = review.vote.value
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        # Find common issues
        all_issues = []
        for review in session.reviews:
            all_issues.extend(review.issues_found)

        issue_freq = {}
        for issue in all_issues:
            issue_freq[issue] = issue_freq.get(issue, 0) + 1

        # Most common issues
        common_issues = sorted(issue_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        # Confidence distribution
        confidences = [r.confidence for r in session.reviews]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "session_id": session_id,
            "vote_distribution": vote_counts,
            "common_issues": [{"issue": issue, "count": count} for issue, count in common_issues],
            "avg_confidence": round(avg_confidence, 3),
            "total_reviews": len(session.reviews),
        }

    def get_consensus_metrics(self) -> Dict[str, Any]:
        """Get consensus metrics."""
        if not self.consensus_history:
            return {
                "total_sessions": 0,
                "consensus_rate": 0,
                "avg_approval_rate": 0,
                "escalation_rate": 0,
            }

        total = len(self.consensus_history)
        achieved = sum(1 for s in self.consensus_history if s["achieved"])
        escalated = sum(1 for s in self.consensus_history if s["escalated"])

        avg_approval = sum(s["approval_rate"] for s in self.consensus_history) / total

        return {
            "total_sessions": total,
            "active_sessions": len(self.active_sessions),
            "consensus_rate": round(achieved / total, 3) if total > 0 else 0,
            "avg_approval_rate": round(avg_approval, 3),
            "escalation_rate": round(escalated / total, 3) if total > 0 else 0,
            "total_reviewers": len(self.reviewer_performance),
        }
