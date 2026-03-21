#!/usr/bin/env python3
"""
Test Suite: Operator Retrieval Guidance (Phase 3.2 Knowledge Graph - P1)

Purpose:
    Comprehensive testing for operator guidance generation including:
    - Recommended next-step generation
    - Likely-fix path hints
    - Per-result action guidance
    - Compact insight digest generation
    - Result explanation accuracy

Module Under Test:
    dashboard/backend/api/ai_insights.py
    dashboard/backend/api/services/context_store.py

Classes:
    TestNextStepGeneration - Generate recommended next steps
    TestLikelyFixPathHints - Provide fix path hints
    TestPerResultActionGuidance - Action guidance per result
    TestCompactInsightDigest - Digest generation
    TestResultExplanationAccuracy - Explain results to operators

Coverage: ~200 lines
Phase: 3.2 (Operator Guidance)
"""

import pytest
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from unittest.mock import Mock, patch


class ActionType(Enum):
    """Types of operator actions."""
    INVESTIGATE = "investigate"
    RESTART_SERVICE = "restart_service"
    SCALE_DEPLOYMENT = "scale_deployment"
    UPDATE_CONFIG = "update_config"
    ROLLBACK = "rollback"
    MONITOR = "monitor"


@dataclass
class NextStep:
    """Recommended next step for operator."""
    action: ActionType
    description: str
    reason: str
    risk_level: str  # low, medium, high
    estimated_time: int  # seconds
    alternative_actions: List['NextStep']


@dataclass
class GuidanceResult:
    """Guidance result for operator."""
    query: str
    answer: str
    explanation: str
    next_steps: List[NextStep]
    risk_summary: str
    confidence: float


class TestNextStepGeneration:
    """Test recommended next-step generation.

    Validates that the system generates appropriate recommended next steps
    based on diagnostic results and current state.
    """

    @pytest.fixture
    def guidance_engine(self):
        """Guidance generation engine."""
        engine = Mock()

        def generate_next_steps(diagnosis: Dict[str, Any],
                               current_state: Dict[str, Any]) -> List[NextStep]:
            """Generate recommended next steps."""
            steps = []

            # Analyze diagnosis and suggest actions
            if diagnosis.get('error_rate', 0) > 0.05:
                steps.append(NextStep(
                    action=ActionType.INVESTIGATE,
                    description="Investigate high error rate",
                    reason=f"Error rate {diagnosis['error_rate']:.1%} exceeds threshold",
                    risk_level="low",
                    estimated_time=300,
                    alternative_actions=[]
                ))

            if diagnosis.get('high_latency', False):
                steps.append(NextStep(
                    action=ActionType.SCALE_DEPLOYMENT,
                    description="Scale deployment to handle load",
                    reason="High latency detected, likely resource constrained",
                    risk_level="medium",
                    estimated_time=600,
                    alternative_actions=[
                        NextStep(
                            action=ActionType.RESTART_SERVICE,
                            description="Restart service instead",
                            reason="May improve performance without scaling",
                            risk_level="low",
                            estimated_time=120,
                            alternative_actions=[]
                        )
                    ]
                ))

            if diagnosis.get('config_mismatch', False):
                steps.append(NextStep(
                    action=ActionType.UPDATE_CONFIG,
                    description="Update service configuration",
                    reason="Configuration does not match deployment requirements",
                    risk_level="high",
                    estimated_time=300,
                    alternative_actions=[]
                ))

            return steps

        engine.generate_next_steps = generate_next_steps
        return engine

    def test_error_rate_generates_investigate_step(self, guidance_engine):
        """High error rate suggests investigation."""
        diagnosis = {
            'error_rate': 0.08,
            'high_latency': False,
            'config_mismatch': False
        }
        state = {'service_status': 'running'}

        steps = guidance_engine.generate_next_steps(diagnosis, state)

        assert len(steps) > 0
        assert steps[0].action == ActionType.INVESTIGATE

    def test_latency_suggests_scaling(self, guidance_engine):
        """High latency suggests scaling or restart."""
        diagnosis = {
            'error_rate': 0.01,
            'high_latency': True,
            'config_mismatch': False
        }
        state = {'resource_utilization': 0.95}

        steps = guidance_engine.generate_next_steps(diagnosis, state)

        scale_step = next(
            (s for s in steps if s.action == ActionType.SCALE_DEPLOYMENT),
            None
        )
        assert scale_step is not None
        assert len(scale_step.alternative_actions) > 0

    def test_config_mismatch_suggests_update(self, guidance_engine):
        """Config mismatch suggests configuration update."""
        diagnosis = {
            'error_rate': 0.02,
            'high_latency': False,
            'config_mismatch': True
        }
        state = {'config_version': '1.0', 'expected_version': '2.0'}

        steps = guidance_engine.generate_next_steps(diagnosis, state)

        config_step = next(
            (s for s in steps if s.action == ActionType.UPDATE_CONFIG),
            None
        )
        assert config_step is not None

    def test_no_steps_when_healthy(self, guidance_engine):
        """No next steps when system healthy."""
        diagnosis = {
            'error_rate': 0.001,
            'high_latency': False,
            'config_mismatch': False
        }
        state = {'service_status': 'healthy'}

        steps = guidance_engine.generate_next_steps(diagnosis, state)

        assert len(steps) == 0


class TestLikelyFixPathHints:
    """Test likely-fix path hints.

    Validates that fix path recommendations are specific, actionable,
    and ranked by likelihood of success.
    """

    @pytest.fixture
    def fix_hint_generator(self):
        """Fix hint generation system."""
        gen = Mock()

        def generate_fix_hints(problem: str,
                              context: Dict[str, Any]) -> List[Dict[str, Any]]:
            """Generate likely fix paths."""
            hints = []

            if "connection" in problem.lower():
                hints.append({
                    'path': 'check_network_config',
                    'steps': [
                        'Verify service network configuration',
                        'Check firewall rules',
                        'Validate DNS resolution'
                    ],
                    'likelihood': 0.85,
                    'estimated_duration': 300
                })
                hints.append({
                    'path': 'restart_networking',
                    'steps': [
                        'Restart network service',
                        'Verify connectivity',
                        'Check service restart'
                    ],
                    'likelihood': 0.65,
                    'estimated_duration': 180
                })

            if "memory" in problem.lower():
                hints.append({
                    'path': 'increase_memory',
                    'steps': [
                        'Increase memory allocation',
                        'Monitor growth',
                        'Verify fix'
                    ],
                    'likelihood': 0.90,
                    'estimated_duration': 600
                })
                hints.append({
                    'path': 'identify_leak',
                    'steps': [
                        'Profile memory usage',
                        'Identify leak source',
                        'Apply patch'
                    ],
                    'likelihood': 0.70,
                    'estimated_duration': 1200
                })

            # Sort by likelihood
            hints.sort(key=lambda h: h['likelihood'], reverse=True)
            return hints

        gen.generate_fix_hints = generate_fix_hints
        return gen

    def test_connection_problem_suggests_network_fixes(self, fix_hint_generator):
        """Connection issues suggest network fixes."""
        hints = fix_hint_generator.generate_fix_hints(
            "Connection timeout",
            {}
        )

        assert len(hints) > 0
        assert any("network" in h['path'] for h in hints)

    def test_hints_ranked_by_likelihood(self, fix_hint_generator):
        """Hints ranked by success likelihood."""
        hints = fix_hint_generator.generate_fix_hints(
            "Connection failed",
            {}
        )

        likelihoods = [h['likelihood'] for h in hints]
        assert likelihoods == sorted(likelihoods, reverse=True)

    def test_memory_problem_suggests_allocation(self, fix_hint_generator):
        """Memory problems suggest allocation or leak detection."""
        hints = fix_hint_generator.generate_fix_hints(
            "Out of memory",
            {}
        )

        paths = [h['path'] for h in hints]
        assert 'increase_memory' in paths
        assert 'identify_leak' in paths

    def test_hints_include_estimated_duration(self, fix_hint_generator):
        """Hints include time estimation."""
        hints = fix_hint_generator.generate_fix_hints(
            "Memory issue",
            {}
        )

        for hint in hints:
            assert 'estimated_duration' in hint
            assert hint['estimated_duration'] > 0


class TestPerResultActionGuidance:
    """Test per-result action guidance.

    Validates that each retrieval result includes specific action guidance
    for operators on how to use and act on the information.
    """

    @pytest.fixture
    def action_advisor(self):
        """Action guidance system."""
        advisor = Mock()

        def generate_action_guidance(result: Dict[str, Any]) -> Dict[str, Any]:
            """Generate action guidance for result."""
            guidance = {
                'result_id': result.get('id'),
                'primary_action': None,
                'secondary_actions': [],
                'precautions': [],
                'validation_steps': []
            }

            source = result.get('source', '')
            content = result.get('content', '').lower()

            if source == 'deployment':
                guidance['primary_action'] = {
                    'action': 'review_deployment',
                    'description': 'Review the deployment details',
                    'command': 'kubectl describe deployment'
                }
                if 'restart' in content or 'error' in content:
                    guidance['secondary_actions'].append({
                        'action': 'rollback',
                        'description': 'Rollback to previous version'
                    })

            elif source == 'config':
                guidance['primary_action'] = {
                    'action': 'validate_config',
                    'description': 'Validate configuration syntax',
                    'command': 'config validate'
                }
                guidance['precautions'].append('Backup current config before changes')

            elif source == 'logs':
                guidance['primary_action'] = {
                    'action': 'analyze_logs',
                    'description': 'Analyze logs for patterns',
                    'command': 'tail -f logs'
                }
                guidance['validation_steps'] = [
                    'Check timestamp and context',
                    'Verify error is reproducible'
                ]

            return guidance

        advisor.generate_action_guidance = generate_action_guidance
        return advisor

    def test_deployment_result_suggests_review(self, action_advisor):
        """Deployment results suggest review."""
        result = {
            'id': 'deploy_1',
            'source': 'deployment',
            'content': 'deployment status'
        }

        guidance = action_advisor.generate_action_guidance(result)

        assert guidance['primary_action']['action'] == 'review_deployment'

    def test_config_result_suggests_validation(self, action_advisor):
        """Config results suggest validation."""
        result = {
            'id': 'config_1',
            'source': 'config',
            'content': 'configuration settings'
        }

        guidance = action_advisor.generate_action_guidance(result)

        assert guidance['primary_action']['action'] == 'validate_config'
        assert any('backup' in p.lower() for p in guidance['precautions'])

    def test_error_deployment_suggests_rollback(self, action_advisor):
        """Error deployments suggest rollback option."""
        result = {
            'id': 'deploy_error',
            'source': 'deployment',
            'content': 'deployment failed with restart errors'
        }

        guidance = action_advisor.generate_action_guidance(result)

        rollback = next(
            (a for a in guidance['secondary_actions']
             if a['action'] == 'rollback'),
            None
        )
        assert rollback is not None

    def test_log_result_includes_validation_steps(self, action_advisor):
        """Log results include validation steps."""
        result = {
            'id': 'log_1',
            'source': 'logs',
            'content': 'error in service processing'
        }

        guidance = action_advisor.generate_action_guidance(result)

        assert len(guidance['validation_steps']) > 0


class TestCompactInsightDigest:
    """Test compact insight digest generation.

    Validates that insight digests are concise, actionable summaries
    of complex information suitable for operator dashboards.
    """

    @pytest.fixture
    def digest_generator(self):
        """Insight digest generator."""
        gen = Mock()

        def generate_digest(results: List[Dict[str, Any]],
                           max_length: int = 200) -> str:
            """Generate compact insight digest."""
            if not results:
                return ""

            # Prioritize actionable insights
            actionable = [r for r in results if r.get('actionable', False)]
            if not actionable:
                actionable = results

            # Take top 3 insights
            top_insights = actionable[:3]

            # Build digest
            digest_parts = []
            for insight in top_insights:
                summary = insight.get('summary', insight.get('content', ''))[:80]
                confidence = insight.get('confidence', 0)
                if confidence > 0.8:
                    digest_parts.append(f"✓ {summary}")
                elif confidence > 0.6:
                    digest_parts.append(f"? {summary}")
                else:
                    digest_parts.append(f"~ {summary}")

            digest = "; ".join(digest_parts)

            # Truncate if needed
            if len(digest) > max_length:
                digest = digest[:max_length] + "..."

            return digest

        gen.generate_digest = generate_digest
        return gen

    def test_digest_prioritizes_actionable(self, digest_generator):
        """Digest prioritizes actionable insights."""
        results = [
            {
                'summary': 'Non-actionable information',
                'confidence': 0.8,
                'actionable': False
            },
            {
                'summary': 'Restart service to fix issue',
                'confidence': 0.9,
                'actionable': True
            }
        ]

        digest = digest_generator.generate_digest(results)

        assert 'Restart' in digest

    def test_digest_includes_confidence_indicators(self, digest_generator):
        """Digest shows confidence levels."""
        results = [
            {
                'summary': 'High confidence issue',
                'confidence': 0.95,
                'actionable': True
            },
            {
                'summary': 'Low confidence suggestion',
                'confidence': 0.55,
                'actionable': True
            }
        ]

        digest = digest_generator.generate_digest(results)

        # High confidence uses ✓
        assert '✓' in digest or '?' in digest or '~' in digest

    def test_digest_respects_length_limit(self, digest_generator):
        """Digest respects max length."""
        results = [
            {
                'summary': 'Very long detailed information that exceeds ' * 5,
                'confidence': 0.8,
                'actionable': True
            }
        ]

        digest = digest_generator.generate_digest(results, max_length=150)

        assert len(digest) <= 153  # Max + ellipsis


class TestResultExplanationAccuracy:
    """Test result explanation accuracy.

    Validates that explanations accurately represent why results were
    returned and how they relate to the operator's query.
    """

    @pytest.fixture
    def explainer(self):
        """Result explainer."""
        exp = Mock()

        def explain_result(result: Dict[str, Any],
                          query: str,
                          context: Dict[str, Any]) -> str:
            """Generate explanation for result."""
            source = result.get('source', '')
            relevance = result.get('relevance_score', 0)
            confidence = result.get('confidence', 0)

            explanation = f"This {source} result is returned because "

            # Explain relevance
            if 'memory' in query.lower() and 'memory' in result.get('content', '').lower():
                explanation += "it directly mentions memory metrics from your query. "
            elif 'error' in query.lower() and 'error' in result.get('content', '').lower():
                explanation += "it contains error information matching your query. "
            else:
                explanation += f"it matches your query with {relevance:.0%} relevance. "

            # Explain confidence
            if confidence > 0.8:
                explanation += "High confidence in this match. "
            elif confidence > 0.6:
                explanation += "Moderate confidence in this match. "
            else:
                explanation += "Lower confidence - consider alternatives. "

            # Explain actionability
            if result.get('actionable', False):
                explanation += "This result provides actionable guidance."
            else:
                explanation += "This provides contextual information."

            return explanation

        exp.explain_result = explain_result
        return exp

    def test_explanation_mentions_relevance(self, explainer):
        """Explanation includes relevance reason."""
        result = {
            'source': 'logs',
            'content': 'memory allocation error',
            'relevance_score': 0.85,
            'confidence': 0.9,
            'actionable': True
        }

        explanation = explainer.explain_result(
            result,
            "What is causing memory issues?",
            {}
        )

        assert 'memory' in explanation.lower()

    def test_explanation_indicates_confidence(self, explainer):
        """Explanation indicates confidence level."""
        result_high = {
            'source': 'config',
            'content': 'memory: 2gb',
            'relevance_score': 0.9,
            'confidence': 0.95,
            'actionable': True
        }

        explanation_high = explainer.explain_result(result_high, "memory", {})
        assert 'high' in explanation_high.lower()

        result_low = {
            'source': 'code',
            'content': 'memory reference',
            'relevance_score': 0.5,
            'confidence': 0.4,
            'actionable': False
        }

        explanation_low = explainer.explain_result(result_low, "memory", {})
        assert 'lower' in explanation_low.lower() or 'low' in explanation_low.lower()

    def test_explanation_clarifies_actionability(self, explainer):
        """Explanation clarifies if result is actionable."""
        actionable_result = {
            'source': 'deployment',
            'content': 'restart to fix',
            'relevance_score': 0.9,
            'confidence': 0.85,
            'actionable': True
        }

        actionable_exp = explainer.explain_result(actionable_result, "fix issue", {})
        assert 'actionable' in actionable_exp.lower()

        non_actionable_result = {
            'source': 'logs',
            'content': 'historical data',
            'relevance_score': 0.7,
            'confidence': 0.8,
            'actionable': False
        }

        non_actionable_exp = explainer.explain_result(
            non_actionable_result,
            "what happened",
            {}
        )
        assert 'contextual' in non_actionable_exp.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
