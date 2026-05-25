#!/usr/bin/env python3
"""Unit tests for advisor_detector.py - Decision Point Detection for Advisor Strategy."""

import pytest
from advisor_detector import DecisionPointDetector, DecisionPoint


class TestDecisionPointDetector:
    """Test suite for DecisionPointDetector."""

    def setup_method(self):
        """Setup test fixtures."""
        self.detector = DecisionPointDetector(decision_threshold=0.7)

    def test_architecture_decision_detected(self):
        """Test detection of architecture decisions."""
        task = "Design the authentication system architecture for our microservices"
        context = {"complexity": "complex"}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-arch-1"
        )

        assert decision is not None, "Should detect architecture decision"
        assert decision.decision_type == "architecture"
        assert decision.confidence >= 0.7
        assert "design" in [s.lower() for s in decision.detected_signals] or "PATTERN:design_structure" in decision.detected_signals

    def test_security_decision_detected(self):
        """Test detection of security decisions."""
        task = "Implement authentication with JWT tokens and ensure protection against XSS attacks"
        context = {}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="free",
            task_id="test-sec-1"
        )

        assert decision is not None, "Should detect security decision"
        assert decision.decision_type == "security"
        assert "authentication" in decision.detected_signals or "xss" in decision.detected_signals

    def test_tradeoff_decision_detected(self):
        """Test detection of tradeoff analysis."""
        task = "Compare the pros and cons of PostgreSQL vs MongoDB for our use case"
        context = {}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-trade-1"
        )

        assert decision is not None, "Should detect tradeoff decision"
        assert decision.decision_type == "tradeoff"
        assert any(s in decision.detected_signals for s in ["pros and cons", " vs ", "PATTERN:comparison"])

    def test_ambiguity_decision_detected(self):
        """Test detection of ambiguous requirements."""
        task = "I'm not sure which approach is best - should I use REST or GraphQL?"
        context = {}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="free",
            task_id="test-amb-1"
        )

        assert decision is not None, "Should detect ambiguity"
        assert decision.decision_type == "ambiguity"

    def test_planning_decision_detected(self):
        """Test detection of multi-step planning needs."""
        task = "Create a multi-step migration plan for moving from monolith to microservices"
        context = {"complexity": "complex"}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-plan-1"
        )

        assert decision is not None, "Should detect planning decision"
        assert decision.decision_type == "planning"
        assert "multi-step" in decision.detected_signals or "migration plan" in decision.detected_signals

    def test_straightforward_task_not_detected(self):
        """Test that simple straightforward tasks don't trigger advisor."""
        task = "Add a simple console.log statement to debug this function"
        context = {"complexity": "simple"}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-simple-1"
        )

        assert decision is None, "Should not detect decision point for simple task"

    def test_confidence_threshold_filtering(self):
        """Test that low-confidence detections are filtered out."""
        # Detector with high threshold
        strict_detector = DecisionPointDetector(decision_threshold=0.9)

        # Task with weak signals
        task = "design a simple function"
        context = {"complexity": "simple"}

        decision = strict_detector.detect(
            task=task,
            context=context,
            executor_tier="paid",  # Higher tier reduces confidence further
            task_id="test-threshold-1"
        )

        assert decision is None, "Should filter out low-confidence detections"

    def test_executor_tier_affects_confidence(self):
        """Test that lower-tier executors get higher confidence for advisor."""
        task = "Analyze the security implications of this API design"
        context = {}

        # Local tier (should boost confidence)
        decision_local = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-tier-local"
        )

        # Critical tier (should reduce confidence)
        decision_critical = self.detector.detect(
            task=task,
            context=context,
            executor_tier="critical",
            task_id="test-tier-critical"
        )

        # Local tier should have higher confidence than critical tier
        if decision_local and decision_critical:
            assert decision_local.confidence > decision_critical.confidence
        elif decision_local and not decision_critical:
            # This is also acceptable - critical tier filtered out
            pass
        else:
            pytest.fail("Expected local tier to have higher or same confidence as critical tier")

    def test_user_guidance_request_boosts_confidence(self):
        """Test that explicit user requests for guidance increase confidence."""
        task_explicit = "Help me decide whether to use REST or GraphQL for this API"
        task_implicit = "Implement an API using REST or GraphQL"

        context = {}

        decision_explicit = self.detector.detect(
            task=task_explicit,
            context=context,
            executor_tier="local",
            task_id="test-explicit"
        )

        decision_implicit = self.detector.detect(
            task=task_implicit,
            context=context,
            executor_tier="local",
            task_id="test-implicit"
        )

        # Explicit request should have higher confidence
        assert decision_explicit is not None
        if decision_implicit:
            assert decision_explicit.confidence >= decision_implicit.confidence

    def test_task_length_affects_confidence(self):
        """Test that longer, more complex tasks get higher confidence."""
        short_task = "Design API"
        long_task = (
            "Design a comprehensive API architecture that handles authentication, "
            "authorization, rate limiting, caching, and supports both REST and GraphQL "
            "endpoints with proper error handling and monitoring"
        )

        context = {}

        decision_short = self.detector.detect(
            task=short_task,
            context=context,
            executor_tier="local",
            task_id="test-short"
        )

        decision_long = self.detector.detect(
            task=long_task,
            context=context,
            executor_tier="local",
            task_id="test-long"
        )

        # Long task should have higher confidence
        if decision_short and decision_long:
            assert decision_long.confidence > decision_short.confidence

    def test_question_generation(self):
        """Test that appropriate questions are generated for each decision type."""
        test_cases = [
            ("architecture", "Design the database schema for user management"),
            ("security", "Implement secure password storage"),
            ("tradeoff", "Compare REST vs GraphQL performance"),
            ("ambiguity", "Not sure if we should use microservices"),
            ("planning", "Create a multi-phase rollout plan")
        ]

        for expected_type, task in test_cases:
            decision = self.detector.detect(
                task=task,
                context={},
                executor_tier="local",
                task_id=f"test-question-{expected_type}"
            )

            if decision:
                assert decision.question is not None
                assert len(decision.question) > 0
                assert task[:50] in decision.question  # Question should reference the task

    def test_decision_point_attributes(self):
        """Test that DecisionPoint has all required attributes."""
        task = "Design authentication architecture with security considerations"
        context = {"project": "user-service", "complexity": "complex"}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-attrs-1"
        )

        assert decision is not None
        assert hasattr(decision, "task_id")
        assert hasattr(decision, "decision_type")
        assert hasattr(decision, "question")
        assert hasattr(decision, "context")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "detected_signals")
        assert hasattr(decision, "executor_tier")

        assert decision.task_id == "test-attrs-1"
        assert decision.decision_type in ["architecture", "security", "planning"]
        assert decision.confidence > 0 and decision.confidence <= 1.0
        assert len(decision.detected_signals) > 0
        assert decision.executor_tier == "local"
        assert decision.context == context

    def test_multiple_decision_types(self):
        """Test handling of tasks with multiple decision type signals."""
        task = (
            "Design a secure authentication architecture and compare "
            "OAuth vs SAML tradeoffs for our microservices"
        )
        context = {}

        decision = self.detector.detect(
            task=task,
            context=context,
            executor_tier="local",
            task_id="test-multi-1"
        )

        assert decision is not None
        # Should pick the strongest signal (likely architecture, security, or tradeoff)
        assert decision.decision_type in ["architecture", "security", "tradeoff"]
        # Should have signals from multiple categories
        assert len(decision.detected_signals) >= 2

    def test_pattern_matching(self):
        """Test regex pattern matching for sophisticated detection."""
        # Test architecture pattern
        task_arch = "design the user service component"
        decision = self.detector.detect(task_arch, {}, "local", "test-pattern-1")
        if decision:
            assert "PATTERN:design_structure" in decision.detected_signals or decision.decision_type == "architecture"

        # Test security pattern
        task_sec = "secure the authentication endpoint"
        decision = self.detector.detect(task_sec, {}, "local", "test-pattern-2")
        if decision:
            assert "PATTERN:security_action" in decision.detected_signals or decision.decision_type == "security"

        # Test comparison pattern
        task_comp = "evaluate and compare different caching strategies"
        decision = self.detector.detect(task_comp, {}, "local", "test-pattern-3")
        if decision:
            assert "PATTERN:comparison" in decision.detected_signals or decision.decision_type == "tradeoff"

    def test_context_complexity_affects_confidence(self):
        """Test that context complexity level affects confidence."""
        task = "Design API endpoints"

        # Simple complexity
        decision_simple = self.detector.detect(
            task=task,
            context={"complexity": "simple"},
            executor_tier="local",
            task_id="test-complexity-simple"
        )

        # Complex complexity
        decision_complex = self.detector.detect(
            task=task,
            context={"complexity": "complex"},
            executor_tier="local",
            task_id="test-complexity-complex"
        )

        # Complex should have higher confidence
        if decision_simple and decision_complex:
            assert decision_complex.confidence >= decision_simple.confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
