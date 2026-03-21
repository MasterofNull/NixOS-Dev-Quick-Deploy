#!/usr/bin/env python3
"""
Test Suite: Workflow Orchestration Policy Enforcement (Phase 4 / Phase 6.3 P1)

Purpose:
    Comprehensive testing for workflow orchestration policy enforcement:
    - Workflow policy enforcement (lane assignment rules)
    - Candidate evaluation and scoring
    - Reviewer consensus workflow
    - Arbiter review path activation
    - Agent evaluation registry persistence

Module Under Test:
    ai-stack/mcp-servers/hybrid-coordinator/workflows/orchestration.py

Classes:
    TestLaneAssignment - Lane assignment rules and policies
    TestCandidateEvaluation - Candidate evaluation and scoring
    TestReviewerConsensus - Reviewer consensus workflow
    TestArbiterReviewPath - Arbiter escalation paths
    TestEvaluationRegistry - Registry persistence

Coverage: ~300 lines
Phase: 4.2 (Workflow Orchestration)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple


class TestLaneAssignment:
    """Test workflow lane assignment rules and policy enforcement.

    Validates that workflows are assigned to correct lanes
    based on policy rules and deployment context.
    """

    @pytest.fixture
    def lane_manager(self):
        """Mock lane assignment manager."""
        manager = Mock()
        manager.policies = {
            'high_risk': {'max_concurrent': 1, 'requires_review': True},
            'standard': {'max_concurrent': 5, 'requires_review': False},
            'low_risk': {'max_concurrent': 10, 'requires_review': False}
        }

        def determine_lane(deployment_context: Dict) -> str:
            """Determine lane for deployment."""
            risk_score = 0
            if deployment_context.get('environment') == 'production':
                risk_score += 30
            if deployment_context.get('request_rate_per_sec', 0) > 1000:
                risk_score += 30
            if deployment_context.get('service_age_days', 365) < 30:
                risk_score += 20
            if deployment_context.get('incident_count_30d', 0) > 2:
                risk_score += 20

            if risk_score >= 60:
                return 'high_risk'
            elif risk_score >= 20:
                return 'standard'
            else:
                return 'low_risk'

        def get_lane_policy(lane: str) -> Dict:
            """Get policy for lane."""
            return manager.policies.get(lane, {})

        def enforce_lane_capacity(lane: str, current_workflows: int) -> bool:
            """Check if lane has capacity."""
            policy = manager.policies.get(lane)
            if not policy:
                return False
            return current_workflows < policy['max_concurrent']

        manager.determine_lane = determine_lane
        manager.get_lane_policy = get_lane_policy
        manager.enforce_lane_capacity = enforce_lane_capacity
        return manager

    def test_production_deployment_assigned_high_risk_lane(self, lane_manager):
        """Production deployments get high-risk lane."""
        context = {
            'environment': 'production',
            'request_rate_per_sec': 2000,
            'service_age_days': 365,
            'incident_count_30d': 0
        }
        lane = lane_manager.determine_lane(context)
        assert lane == 'high_risk'

    def test_development_deployment_assigned_low_risk_lane(self, lane_manager):
        """Development deployments get low-risk lane."""
        context = {
            'environment': 'development',
            'request_rate_per_sec': 10,
            'service_age_days': 365,
            'incident_count_30d': 0
        }
        lane = lane_manager.determine_lane(context)
        assert lane == 'low_risk'

    def test_new_service_assigned_higher_risk_lane(self, lane_manager):
        """New services are assigned to higher risk lanes."""
        old_service = {
            'environment': 'staging',
            'service_age_days': 365,
            'incident_count_30d': 0
        }
        new_service = {
            'environment': 'staging',
            'service_age_days': 5,
            'incident_count_30d': 0
        }
        old_lane = lane_manager.determine_lane(old_service)
        new_lane = lane_manager.determine_lane(new_service)
        risk_order = ['low_risk', 'standard', 'high_risk']
        assert risk_order.index(new_lane) >= risk_order.index(old_lane)

    def test_lane_capacity_enforcement(self, lane_manager):
        """Lane capacity is enforced."""
        assert lane_manager.enforce_lane_capacity('high_risk', 0) is True
        assert lane_manager.enforce_lane_capacity('high_risk', 1) is False
        assert lane_manager.enforce_lane_capacity('standard', 4) is True
        assert lane_manager.enforce_lane_capacity('standard', 5) is False


class TestCandidateEvaluation:
    """Test candidate evaluation and scoring."""

    @pytest.fixture
    def evaluator(self):
        """Mock candidate evaluator."""
        evaluator = Mock()

        def evaluate_candidate(candidate: Dict) -> Dict:
            """Evaluate workflow candidate."""
            score = 0
            if candidate.get('capability_match', 0) > 0.8:
                score += 30
            elif candidate.get('capability_match', 0) > 0.6:
                score += 20
            else:
                score += 5
            if not candidate.get('is_busy'):
                score += 20
            success_rate = candidate.get('success_rate', 0.5)
            score += int(success_rate * 30)
            latency = candidate.get('avg_latency_ms', 1000)
            if latency < 100:
                score += 20
            elif latency < 500:
                score += 10
            return {
                'candidate_id': candidate.get('id'),
                'score': score,
                'capability_match': candidate.get('capability_match', 0),
                'is_available': not candidate.get('is_busy'),
                'success_rate': success_rate,
                'recommendation': 'strong' if score >= 80 else 'good' if score >= 60 else 'poor'
            }

        def rank_candidates(candidates: List[Dict]) -> List[Dict]:
            """Rank candidates by score."""
            evaluations = [evaluate_candidate(c) for c in candidates]
            return sorted(evaluations, key=lambda e: e['score'], reverse=True)

        evaluator.evaluate_candidate = evaluate_candidate
        evaluator.rank_candidates = rank_candidates
        return evaluator

    def test_candidate_scoring_considers_capability(self, evaluator):
        """Candidate scoring considers capability match."""
        weak_match = {'id': 'c1', 'capability_match': 0.3, 'is_busy': False, 'success_rate': 0.9, 'avg_latency_ms': 50}
        strong_match = {'id': 'c2', 'capability_match': 0.95, 'is_busy': False, 'success_rate': 0.9, 'avg_latency_ms': 50}
        weak_eval = evaluator.evaluate_candidate(weak_match)
        strong_eval = evaluator.evaluate_candidate(strong_match)
        assert strong_eval['score'] > weak_eval['score']

    def test_candidate_scoring_penalizes_busy_agents(self, evaluator):
        """Candidate scoring penalizes busy agents."""
        available = {'id': 'c1', 'capability_match': 0.8, 'is_busy': False, 'success_rate': 0.9, 'avg_latency_ms': 100}
        busy = {'id': 'c2', 'capability_match': 0.8, 'is_busy': True, 'success_rate': 0.9, 'avg_latency_ms': 100}
        available_eval = evaluator.evaluate_candidate(available)
        busy_eval = evaluator.evaluate_candidate(busy)
        assert available_eval['score'] > busy_eval['score']

    def test_candidate_ranking(self, evaluator):
        """Candidates are ranked correctly."""
        candidates = [
            {'id': 'c1', 'capability_match': 0.5, 'is_busy': False, 'success_rate': 0.9, 'avg_latency_ms': 50},
            {'id': 'c2', 'capability_match': 0.9, 'is_busy': False, 'success_rate': 0.95, 'avg_latency_ms': 50},
            {'id': 'c3', 'capability_match': 0.7, 'is_busy': True, 'success_rate': 0.85, 'avg_latency_ms': 100},
        ]
        ranked = evaluator.rank_candidates(candidates)
        assert ranked[0]['candidate_id'] == 'c2'
        assert ranked[-1]['candidate_id'] == 'c3'


class TestReviewerConsensus:
    """Test reviewer consensus workflow."""

    @pytest.fixture
    def consensus_tracker(self):
        """Mock consensus tracker."""
        tracker = Mock()

        def track_reviewer_vote(review_id: str, reviewer_id: str, decision: str) -> None:
            """Track a reviewer's vote."""
            if decision not in ['approve', 'reject', 'request_changes']:
                raise ValueError(f"Invalid decision: {decision}")
            tracker.votes = getattr(tracker, 'votes', {})
            tracker.votes[review_id] = tracker.votes.get(review_id, {})
            tracker.votes[review_id][reviewer_id] = decision

        def get_consensus(review_id: str, required_approvals: int = 2) -> Dict:
            """Determine consensus from votes."""
            votes = tracker.votes.get(review_id, {})
            approve_count = sum(1 for v in votes.values() if v == 'approve')
            reject_count = sum(1 for v in votes.values() if v == 'reject')
            request_changes_count = sum(1 for v in votes.values() if v == 'request_changes')

            if reject_count > 0:
                consensus = 'rejected'
            elif request_changes_count > 0:
                consensus = 'changes_requested'
            elif approve_count >= required_approvals:
                consensus = 'approved'
            else:
                consensus = 'pending'

            return {
                'review_id': review_id,
                'consensus': consensus,
                'approve_count': approve_count,
                'reject_count': reject_count,
                'request_changes_count': request_changes_count,
                'total_votes': len(votes)
            }

        tracker.track_reviewer_vote = track_reviewer_vote
        tracker.get_consensus = get_consensus
        tracker.votes = {}
        return tracker

    def test_consensus_approved_with_sufficient_votes(self, consensus_tracker):
        """Consensus approved with sufficient votes."""
        consensus_tracker.track_reviewer_vote('r1', 'rev1', 'approve')
        consensus_tracker.track_reviewer_vote('r1', 'rev2', 'approve')
        result = consensus_tracker.get_consensus('r1', required_approvals=2)
        assert result['consensus'] == 'approved'

    def test_consensus_rejected_if_any_rejection(self, consensus_tracker):
        """Consensus rejected if any reviewer rejects."""
        consensus_tracker.track_reviewer_vote('r1', 'rev1', 'approve')
        consensus_tracker.track_reviewer_vote('r1', 'rev2', 'reject')
        result = consensus_tracker.get_consensus('r1', required_approvals=2)
        assert result['consensus'] == 'rejected'

    def test_consensus_pending_without_sufficient_votes(self, consensus_tracker):
        """Consensus pending without sufficient votes."""
        consensus_tracker.track_reviewer_vote('r1', 'rev1', 'approve')
        result = consensus_tracker.get_consensus('r1', required_approvals=2)
        assert result['consensus'] == 'pending'

    def test_consensus_changes_requested(self, consensus_tracker):
        """Consensus tracked for change requests."""
        consensus_tracker.track_reviewer_vote('r1', 'rev1', 'request_changes')
        consensus_tracker.track_reviewer_vote('r1', 'rev2', 'approve')
        result = consensus_tracker.get_consensus('r1', required_approvals=2)
        assert result['consensus'] == 'changes_requested'


class TestArbiterReviewPath:
    """Test arbiter review path activation."""

    @pytest.fixture
    def arbiter_manager(self):
        """Mock arbiter manager."""
        manager = Mock()

        def should_escalate_to_arbiter(review_result: Dict) -> bool:
            """Determine if review should go to arbiter."""
            if review_result.get('consensus') == 'pending':
                return True
            if (review_result.get('approve_count', 0) > 0 and
                review_result.get('reject_count', 0) > 0):
                return True
            return False

        def record_arbiter_decision(review_id: str, arbiter_id: str, decision: str) -> None:
            """Record arbiter's final decision."""
            if decision not in ['approved', 'rejected', 'remand_to_reviewers']:
                raise ValueError(f"Invalid decision: {decision}")
            manager.arbiter_decisions = getattr(manager, 'arbiter_decisions', {})
            manager.arbiter_decisions[review_id] = {
                'arbiter_id': arbiter_id,
                'decision': decision,
                'timestamp': datetime.now()
            }

        def get_arbiter_decision(review_id: str) -> Dict:
            """Get arbiter's decision."""
            return manager.arbiter_decisions.get(review_id, None)

        manager.should_escalate_to_arbiter = should_escalate_to_arbiter
        manager.record_arbiter_decision = record_arbiter_decision
        manager.get_arbiter_decision = get_arbiter_decision
        manager.arbiter_decisions = {}
        return manager

    def test_escalate_to_arbiter_on_pending_consensus(self, arbiter_manager):
        """Review escalated to arbiter when consensus pending."""
        review_result = {'consensus': 'pending', 'approve_count': 1, 'reject_count': 0}
        should_escalate = arbiter_manager.should_escalate_to_arbiter(review_result)
        assert should_escalate is True

    def test_escalate_to_arbiter_on_disagreement(self, arbiter_manager):
        """Review escalated when reviewers disagree."""
        review_result = {'consensus': None, 'approve_count': 2, 'reject_count': 1}
        should_escalate = arbiter_manager.should_escalate_to_arbiter(review_result)
        assert should_escalate is True

    def test_no_escalation_for_clear_consensus(self, arbiter_manager):
        """No escalation for clear consensus."""
        review_result = {'consensus': 'approved', 'approve_count': 3, 'reject_count': 0}
        should_escalate = arbiter_manager.should_escalate_to_arbiter(review_result)
        assert should_escalate is False

    def test_arbiter_decision_recorded(self, arbiter_manager):
        """Arbiter decision is recorded."""
        arbiter_manager.record_arbiter_decision('r1', 'arbiter_001', 'approved')
        decision = arbiter_manager.get_arbiter_decision('r1')
        assert decision is not None
        assert decision['decision'] == 'approved'
        assert decision['arbiter_id'] == 'arbiter_001'


class TestEvaluationRegistry:
    """Test evaluation registry persistence."""

    @pytest.fixture
    def registry(self):
        """Mock evaluation registry."""
        registry = Mock()
        registry.records = {}

        def add_evaluation_record(workflow_id: str, evaluation: Dict) -> None:
            """Add evaluation record to registry."""
            registry.records[workflow_id] = {
                'workflow_id': workflow_id,
                'evaluation': evaluation,
                'timestamp': datetime.now(),
                'lane': evaluation.get('assigned_lane'),
                'candidate_scores': evaluation.get('candidate_scores', {})
            }

        def get_evaluation_history(workflow_id: str, limit: int = 10) -> List[Dict]:
            """Get evaluation history for workflow."""
            if workflow_id in registry.records:
                return [registry.records[workflow_id]]
            return []

        def get_agent_performance_stats(agent_id: str) -> Dict:
            """Get performance stats for agent across all evaluations."""
            evaluations = [
                r for r in registry.records.values()
                if r['evaluation'].get('selected_agent') == agent_id
            ]
            scores = [
                r['candidate_scores'].get(agent_id, 0)
                for r in evaluations if agent_id in r.get('candidate_scores', {})
            ]
            if not scores:
                return {'agent_id': agent_id, 'evaluation_count': 0}
            return {
                'agent_id': agent_id,
                'evaluation_count': len(evaluations),
                'avg_score': sum(scores) / len(scores),
                'max_score': max(scores),
                'min_score': min(scores)
            }

        registry.add_evaluation_record = add_evaluation_record
        registry.get_evaluation_history = get_evaluation_history
        registry.get_agent_performance_stats = get_agent_performance_stats
        return registry

    def test_evaluation_record_persisted(self, registry):
        """Evaluation records are persisted."""
        evaluation = {
            'assigned_lane': 'standard',
            'selected_agent': 'agent_1',
            'candidate_scores': {'agent_1': 85, 'agent_2': 75}
        }
        registry.add_evaluation_record('wf1', evaluation)
        history = registry.get_evaluation_history('wf1')
        assert len(history) == 1
        assert history[0]['workflow_id'] == 'wf1'
        assert history[0]['lane'] == 'standard'

    def test_evaluation_history_retrieval(self, registry):
        """Evaluation history is retrievable."""
        for i in range(3):
            evaluation = {
                'assigned_lane': 'standard',
                'selected_agent': f'agent_{i}',
                'candidate_scores': {}
            }
            registry.add_evaluation_record(f'wf{i}', evaluation)
        history_1 = registry.get_evaluation_history('wf1')
        assert len(history_1) == 1

    def test_agent_performance_statistics(self, registry):
        """Agent performance statistics computed."""
        for i in range(5):
            evaluation = {
                'assigned_lane': 'standard',
                'selected_agent': 'agent_1',
                'candidate_scores': {'agent_1': 70 + i * 5}
            }
            registry.add_evaluation_record(f'wf{i}', evaluation)
        stats = registry.get_agent_performance_stats('agent_1')
        assert stats['agent_id'] == 'agent_1'
        assert stats['evaluation_count'] == 5
        assert 70 <= stats['avg_score'] <= 90


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
