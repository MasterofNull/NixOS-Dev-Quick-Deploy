#!/usr/bin/env python3
"""
Quality Consensus

Multiple reviewers validate outputs with weighted voting by agent capability.
Auto-escalates on disagreement.

Part of Phase 4: Advanced Multi-Agent Collaboration
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quality_consensus")


class ReviewVerdict(Enum):
    """Review verdict options"""
    APPROVE = "approve"
    APPROVE_WITH_CHANGES = "approve_with_changes"
    REJECT = "reject"
    NEEDS_REVISION = "needs_revision"
    ABSTAIN = "abstain"


class EscalationReason(Enum):
    """Reasons for escalating decision"""
    NO_MAJORITY = "no_majority"
    TIE_VOTE = "tie_vote"
    HIGH_DISAGREEMENT = "high_disagreement"
    LOW_CONFIDENCE = "low_confidence"
    CRITICAL_DECISION = "critical_decision"


@dataclass
class ReviewCriteria:
    """Criteria for reviewing work"""
    name: str
    description: str
    weight: float = 1.0  # Relative importance
    threshold: float = 0.7  # Minimum acceptable score


@dataclass
class Review:
    """Individual agent review"""
    review_id: str
    reviewer_id: str
    reviewer_capability: float  # Domain expertise 0-1
    reviewer_reliability: float  # Historical accuracy 0-1
    verdict: ReviewVerdict
    overall_score: float  # 0-1
    criteria_scores: Dict[str, float] = field(default_factory=dict)  # criterion_name -> score
    feedback: str = ""
    suggested_improvements: List[str] = field(default_factory=list)
    confidence: float = 0.8  # How confident reviewer is in assessment
    review_time_ms: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['verdict'] = self.verdict.value
        d['created_at'] = self.created_at.isoformat()
        return d

    def weighted_score(self) -> float:
        """Calculate weighted score based on capability and reliability"""
        return self.overall_score * self.reviewer_capability * self.reviewer_reliability


@dataclass
class ConsensusDecision:
    """Final consensus decision"""
    decision_id: str
    item_id: str  # ID of item being reviewed
    final_verdict: ReviewVerdict
    consensus_score: float  # 0-1, how strong the consensus is
    total_reviews: int
    approval_rate: float
    weighted_average_score: float
    reviews: List[Review] = field(default_factory=list)
    escalated: bool = False
    escalation_reason: Optional[EscalationReason] = None
    escalation_details: str = ""
    decided_at: datetime = field(default_factory=datetime.now)
    decision_method: str = "weighted_voting"  # weighted_voting, majority, unanimous, expert_override

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['final_verdict'] = self.final_verdict.value
        if self.escalation_reason:
            d['escalation_reason'] = self.escalation_reason.value
        d['decided_at'] = self.decided_at.isoformat()
        d['reviews'] = [r.to_dict() for r in self.reviews]
        return d


class QualityConsensus:
    """
    Orchestrates multi-agent quality consensus with weighted voting.
    """

    def __init__(
        self,
        consensus_threshold: float = 0.67,  # 2/3 majority
        escalation_threshold: float = 0.5,  # Escalate if score variance > this
        min_reviewers: int = 2,
        max_reviewers: int = 5
    ):
        self.consensus_threshold = consensus_threshold
        self.escalation_threshold = escalation_threshold
        self.min_reviewers = min_reviewers
        self.max_reviewers = max_reviewers

        self.pending_reviews: Dict[str, List[Review]] = defaultdict(list)
        self.decisions: Dict[str, ConsensusDecision] = {}
        self.expert_registry: Dict[str, Set[str]] = defaultdict(set)  # domain -> expert_agent_ids

        logger.info(
            f"QualityConsensus initialized "
            f"(threshold={consensus_threshold}, min_reviewers={min_reviewers})"
        )

    def register_expert(self, domain: str, agent_id: str):
        """Register agent as expert in domain"""
        self.expert_registry[domain].add(agent_id)
        logger.info(f"Registered {agent_id} as expert in {domain}")

    def submit_review(
        self,
        item_id: str,
        reviewer_id: str,
        reviewer_capability: float,
        reviewer_reliability: float,
        verdict: ReviewVerdict,
        overall_score: float,
        criteria_scores: Optional[Dict[str, float]] = None,
        feedback: str = "",
        suggested_improvements: Optional[List[str]] = None,
        confidence: float = 0.8,
        review_time_ms: int = 0
    ) -> str:
        """Submit a review for an item"""
        review = Review(
            review_id=str(uuid4()),
            reviewer_id=reviewer_id,
            reviewer_capability=reviewer_capability,
            reviewer_reliability=reviewer_reliability,
            verdict=verdict,
            overall_score=overall_score,
            criteria_scores=criteria_scores or {},
            feedback=feedback,
            suggested_improvements=suggested_improvements or [],
            confidence=confidence,
            review_time_ms=review_time_ms
        )

        self.pending_reviews[item_id].append(review)

        logger.info(
            f"Review submitted: {reviewer_id} → {item_id} "
            f"({verdict.value}, score={overall_score:.2f})"
        )

        return review.review_id

    def calculate_consensus(
        self,
        item_id: str,
        domain: Optional[str] = None,
        critical: bool = False
    ) -> ConsensusDecision:
        """Calculate consensus from submitted reviews"""
        reviews = self.pending_reviews.get(item_id, [])

        if len(reviews) < self.min_reviewers:
            logger.warning(
                f"Insufficient reviews for {item_id}: {len(reviews)}/{self.min_reviewers}"
            )
            # Return preliminary decision
            return self._create_preliminary_decision(item_id, reviews)

        # Calculate weighted scores
        weighted_scores = []
        total_weight = 0.0

        for review in reviews:
            weight = review.reviewer_capability * review.reviewer_reliability
            weighted_scores.append((review, weight))
            total_weight += weight

        # Calculate weighted average score
        weighted_avg = sum(
            review.overall_score * weight
            for review, weight in weighted_scores
        ) / total_weight if total_weight > 0 else 0.0

        # Count verdicts (weighted)
        verdict_weights = defaultdict(float)
        for review, weight in weighted_scores:
            if review.verdict != ReviewVerdict.ABSTAIN:
                verdict_weights[review.verdict] += weight

        # Determine final verdict
        if not verdict_weights:
            final_verdict = ReviewVerdict.ABSTAIN
            consensus_score = 0.0
        else:
            final_verdict = max(verdict_weights.items(), key=lambda x: x[1])[0]
            consensus_score = verdict_weights[final_verdict] / total_weight

        # Calculate approval rate
        approval_verdicts = {ReviewVerdict.APPROVE, ReviewVerdict.APPROVE_WITH_CHANGES}
        approval_weight = sum(
            weight for review, weight in weighted_scores
            if review.verdict in approval_verdicts
        )
        approval_rate = approval_weight / total_weight if total_weight > 0 else 0.0

        # Check for escalation conditions
        escalated, escalation_reason, escalation_details = self._check_escalation(
            reviews, consensus_score, weighted_avg, critical, domain
        )

        # Override with expert if available and disagreement exists
        if escalated and domain and domain in self.expert_registry:
            expert_review = self._get_expert_review(reviews, domain)
            if expert_review:
                final_verdict = expert_review.verdict
                weighted_avg = expert_review.overall_score
                escalated = False
                decision_method = "expert_override"
                logger.info(
                    f"Expert override applied: {expert_review.reviewer_id} "
                    f"({final_verdict.value})"
                )
            else:
                decision_method = "weighted_voting"
        else:
            decision_method = "weighted_voting"

        # Create decision
        decision = ConsensusDecision(
            decision_id=str(uuid4()),
            item_id=item_id,
            final_verdict=final_verdict,
            consensus_score=consensus_score,
            total_reviews=len(reviews),
            approval_rate=approval_rate,
            weighted_average_score=weighted_avg,
            reviews=reviews,
            escalated=escalated,
            escalation_reason=escalation_reason,
            escalation_details=escalation_details,
            decision_method=decision_method
        )

        self.decisions[item_id] = decision

        # Clear pending reviews
        del self.pending_reviews[item_id]

        logger.info(
            f"Consensus reached for {item_id}: {final_verdict.value} "
            f"(score={weighted_avg:.2f}, consensus={consensus_score:.2f}, "
            f"escalated={escalated})"
        )

        return decision

    def _create_preliminary_decision(
        self,
        item_id: str,
        reviews: List[Review]
    ) -> ConsensusDecision:
        """Create preliminary decision with insufficient reviews"""
        if not reviews:
            verdict = ReviewVerdict.ABSTAIN
            score = 0.0
        else:
            # Use highest capability reviewer's verdict
            best_review = max(reviews, key=lambda r: r.reviewer_capability)
            verdict = best_review.verdict
            score = best_review.overall_score

        return ConsensusDecision(
            decision_id=str(uuid4()),
            item_id=item_id,
            final_verdict=verdict,
            consensus_score=0.0,
            total_reviews=len(reviews),
            approval_rate=0.0,
            weighted_average_score=score,
            reviews=reviews,
            escalated=True,
            escalation_reason=EscalationReason.LOW_CONFIDENCE,
            escalation_details=f"Only {len(reviews)}/{self.min_reviewers} reviews",
            decision_method="preliminary"
        )

    def _check_escalation(
        self,
        reviews: List[Review],
        consensus_score: float,
        weighted_avg: float,
        critical: bool,
        domain: Optional[str]
    ) -> Tuple[bool, Optional[EscalationReason], str]:
        """Check if decision should be escalated"""

        # Critical decisions require unanimous or expert review
        if critical and consensus_score < 1.0:
            return True, EscalationReason.CRITICAL_DECISION, "Critical decision requires unanimous approval or expert review"

        # Check for consensus threshold
        if consensus_score < self.consensus_threshold:
            return True, EscalationReason.NO_MAJORITY, f"Consensus {consensus_score:.2%} below threshold {self.consensus_threshold:.2%}"

        # Check for tie votes
        verdict_counts = defaultdict(int)
        for review in reviews:
            if review.verdict != ReviewVerdict.ABSTAIN:
                verdict_counts[review.verdict] += 1

        if len(verdict_counts) > 1:
            max_count = max(verdict_counts.values())
            tied_verdicts = [v for v, c in verdict_counts.items() if c == max_count]
            if len(tied_verdicts) > 1:
                return True, EscalationReason.TIE_VOTE, f"Tie between {[v.value for v in tied_verdicts]}"

        # Check for high score variance (disagreement)
        scores = [r.overall_score for r in reviews]
        if len(scores) >= 2:
            variance = sum((s - weighted_avg) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5

            if std_dev > self.escalation_threshold:
                return True, EscalationReason.HIGH_DISAGREEMENT, f"High score variance: σ={std_dev:.2f}"

        # Check average confidence
        avg_confidence = sum(r.confidence for r in reviews) / len(reviews)
        if avg_confidence < 0.6:
            return True, EscalationReason.LOW_CONFIDENCE, f"Low average confidence: {avg_confidence:.2%}"

        return False, None, ""

    def _get_expert_review(
        self,
        reviews: List[Review],
        domain: str
    ) -> Optional[Review]:
        """Get expert review if available"""
        expert_ids = self.expert_registry.get(domain, set())
        expert_reviews = [r for r in reviews if r.reviewer_id in expert_ids]

        if not expert_reviews:
            return None

        # Return highest capability expert
        return max(expert_reviews, key=lambda r: r.reviewer_capability)

    def get_decision_summary(self, item_id: str) -> Dict[str, Any]:
        """Get summary of decision"""
        decision = self.decisions.get(item_id)
        if not decision:
            return {"error": "Decision not found"}

        return {
            "item_id": item_id,
            "final_verdict": decision.final_verdict.value,
            "consensus_score": decision.consensus_score,
            "approval_rate": decision.approval_rate,
            "weighted_average_score": decision.weighted_average_score,
            "total_reviews": decision.total_reviews,
            "escalated": decision.escalated,
            "escalation_reason": decision.escalation_reason.value if decision.escalation_reason else None,
            "decision_method": decision.decision_method,
            "decided_at": decision.decided_at.isoformat(),
            "reviewers": [
                {
                    "id": r.reviewer_id,
                    "verdict": r.verdict.value,
                    "score": r.overall_score,
                    "confidence": r.confidence
                }
                for r in decision.reviews
            ]
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall consensus statistics"""
        total_decisions = len(self.decisions)
        if total_decisions == 0:
            return {"total_decisions": 0}

        escalated_count = sum(1 for d in self.decisions.values() if d.escalated)
        avg_consensus = sum(d.consensus_score for d in self.decisions.values()) / total_decisions
        avg_reviews = sum(d.total_reviews for d in self.decisions.values()) / total_decisions

        verdict_counts = defaultdict(int)
        for decision in self.decisions.values():
            verdict_counts[decision.final_verdict] += 1

        return {
            "total_decisions": total_decisions,
            "escalated_count": escalated_count,
            "escalation_rate": escalated_count / total_decisions,
            "average_consensus_score": avg_consensus,
            "average_reviews_per_item": avg_reviews,
            "verdict_distribution": {
                v.value: count for v, count in verdict_counts.items()
            }
        }


async def main():
    """Example usage"""
    consensus = QualityConsensus(consensus_threshold=0.67, min_reviewers=3)

    # Register experts
    consensus.register_expert("security", "security_expert")

    # Submit reviews for an item
    item_id = "pr_12345"

    # Agent 1: High capability security expert
    consensus.submit_review(
        item_id=item_id,
        reviewer_id="security_expert",
        reviewer_capability=0.95,
        reviewer_reliability=0.92,
        verdict=ReviewVerdict.APPROVE_WITH_CHANGES,
        overall_score=0.85,
        criteria_scores={"security": 0.95, "code_quality": 0.80, "performance": 0.80},
        feedback="Good implementation, minor security improvements needed",
        suggested_improvements=["Add input validation", "Sanitize user input"],
        confidence=0.9
    )

    # Agent 2: Backend developer
    consensus.submit_review(
        item_id=item_id,
        reviewer_id="backend_dev",
        reviewer_capability=0.80,
        reviewer_reliability=0.88,
        verdict=ReviewVerdict.APPROVE,
        overall_score=0.90,
        criteria_scores={"security": 0.85, "code_quality": 0.95, "performance": 0.90},
        feedback="Clean code, well tested",
        confidence=0.85
    )

    # Agent 3: Junior reviewer (lower capability)
    consensus.submit_review(
        item_id=item_id,
        reviewer_id="junior_dev",
        reviewer_capability=0.60,
        reviewer_reliability=0.70,
        verdict=ReviewVerdict.APPROVE,
        overall_score=0.95,
        criteria_scores={"security": 0.90, "code_quality": 1.0, "performance": 0.95},
        feedback="Looks great!",
        confidence=0.70
    )

    # Calculate consensus
    decision = consensus.calculate_consensus(item_id, domain="security", critical=False)

    print("\nConsensus Decision:")
    print(json.dumps(consensus.get_decision_summary(item_id), indent=2))

    print("\nStatistics:")
    print(json.dumps(consensus.get_statistics(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
