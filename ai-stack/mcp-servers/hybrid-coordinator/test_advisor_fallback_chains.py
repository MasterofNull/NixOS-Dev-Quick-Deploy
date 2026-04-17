#!/usr/bin/env python3
"""Unit tests for advisor ranked fallback chains."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from advisor_detector import DecisionPoint
from llm_router import LLMRouter


class TestAdvisorFallbackChains:
    """Test suite for ranked fallback chain functionality."""

    def test_get_advisor_model_chain_architecture(self):
        """Test that architecture decisions get proper fallback chain."""
        router = LLMRouter()

        chain = router._get_advisor_model_chain("architecture")

        # Should have 3-4 models
        assert len(chain) >= 3
        assert len(chain) <= 6  # Including global fallbacks

        # First should be high-quality model
        assert chain[0] in ["claude-opus-4-5", "gpt-4o", "claude-sonnet"]

    def test_get_advisor_model_chain_security(self):
        """Test that security decisions prioritize best models."""
        router = LLMRouter()

        chain = router._get_advisor_model_chain("security")

        # Should have 3-4 models
        assert len(chain) >= 3

        # First should be highest quality for security
        assert chain[0] in ["claude-opus-4-5", "gpt-4o"]

    def test_get_advisor_model_chain_planning(self):
        """Test that planning decisions can use thinking models."""
        router = LLMRouter()

        chain = router._get_advisor_model_chain("planning")

        # Should have 3-4 models
        assert len(chain) >= 3

        # Gemini thinking is good for planning
        assert any("gemini" in model.lower() for model in chain)

    def test_get_advisor_model_chain_deduplication(self):
        """Test that duplicate models are removed from chain."""
        router = LLMRouter()

        chain = router._get_advisor_model_chain("security")

        # No duplicates
        assert len(chain) == len(set(chain)), f"Chain has duplicates: {chain}"

    def test_get_advisor_model_chain_fallback_to_defaults(self):
        """Test that chain has fallbacks even without specific config."""
        with patch("llm_router.Config", None):
            router = LLMRouter()
            chain = router._get_advisor_model_chain("unknown_type")

            # Should have default chain
            assert len(chain) >= 3
            assert "claude-opus-4-5" in chain or "claude-sonnet" in chain

    @pytest.mark.asyncio
    async def test_consult_advisor_fallback_on_error(self):
        """Test that advisor consultation tries fallback models on error."""
        router = LLMRouter()

        decision_point = DecisionPoint(
            task_id="test-fallback-1",
            decision_type="security",
            question="Test security question",
            context={},
            confidence=0.8,
            detected_signals=["security", "authentication"],
            executor_tier="local"
        )

        # Mock the coordinator call to fail for first model, succeed for second
        call_count = [0]

        async def mock_advisor_call(prompt, model, max_tokens):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call fails
                raise Exception("Model unavailable")
            else:
                # Second call succeeds
                return "1. Recommended approach: Use OAuth2\n2. Key considerations: Token security\n3. Action: proceed"

        with patch.object(router, '_advisor_via_coordinator', side_effect=mock_advisor_call):
            with patch.object(router, '_record_advisor_consultation'):
                result = await router._consult_advisor(decision_point, "local", "llama-cpp")

                # Should have succeeded with fallback
                assert result["guidance"] is not None
                assert result["action"] in ["proceed", "modify", "stop"]
                assert result["fallback_rank"] == 1  # Used first fallback (rank 1)
                assert call_count[0] == 2  # Tried twice

    @pytest.mark.asyncio
    async def test_consult_advisor_all_fallbacks_exhausted(self):
        """Test that all fallback exhaustion raises exception."""
        router = LLMRouter()

        decision_point = DecisionPoint(
            task_id="test-exhaust-1",
            decision_type="planning",
            question="Test planning question",
            context={},
            confidence=0.9,
            detected_signals=["multi-step", "roadmap"],
            executor_tier="local"
        )

        # Mock all calls to fail
        async def mock_advisor_fail(prompt, model, max_tokens):
            raise Exception(f"Model {model} unavailable")

        with patch.object(router, '_advisor_via_coordinator', side_effect=mock_advisor_fail):
            with patch.object(router, '_get_advisor_model_chain', return_value=["model-1", "model-2", "model-3"]):
                with pytest.raises(Exception) as exc_info:
                    await router._consult_advisor(decision_point, "local", "llama-cpp")

                # Should mention that all models failed
                assert "all" in str(exc_info.value).lower()
                assert "model" in str(exc_info.value).lower()

    def test_fallback_rank_in_metrics(self):
        """Test that fallback rank is included in advisor metrics."""
        router = LLMRouter()

        # Create test db with sample data
        import sqlite3
        conn = sqlite3.connect(router.metrics_db)

        # Insert test consultations with different fallback ranks
        test_data = [
            ("task-1", "security", "local", "llama", "claude-opus-4-5", 500, 0.0075, 1200, "Q1", "G1", None, 0),
            ("task-2", "planning", "free", "qwen", "gemini-2.0-flash-thinking", 600, 0.009, 1000, "Q2", "G2", None, 0),
            ("task-3", "security", "local", "llama", "gpt-4o", 550, 0.00825, 1100, "Q3", "G3", None, 1),  # Fallback
            ("task-4", "architecture", "paid", "sonnet", "claude-sonnet", 480, 0.0072, 950, "Q4", "G4", None, 1),  # Fallback
            ("task-5", "tradeoff", "local", "llama", "qwen-max", 520, 0.0078, 890, "Q5", "G5", None, 2),  # Second fallback
        ]

        for row in test_data:
            conn.execute("""
                INSERT INTO advisor_consultations
                (task_id, decision_type, executor_tier, executor_model, advisor_model,
                 advisor_tokens, advisor_cost, time_to_consult_ms, question, guidance_summary,
                 task_success, fallback_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
        conn.commit()
        conn.close()

        # Get metrics
        metrics = router.get_advisor_metrics()

        # Verify fallback tracking
        assert "fallback_usage" in metrics
        assert "primary_success_rate_percent" in metrics
        assert "fallback_rate_percent" in metrics

        fallback_usage = metrics["fallback_usage"]
        assert "rank_0" in fallback_usage  # Primary
        assert fallback_usage["rank_0"] == 2  # 2 primary successes

        # 3 fallback uses total (2 rank_1 + 1 rank_2)
        total_fallbacks = sum(v for k, v in fallback_usage.items() if k != "rank_0")
        assert total_fallbacks == 3

        # Primary success rate should be 40% (2 out of 5)
        assert metrics["primary_success_rate_percent"] == pytest.approx(40.0, abs=0.1)

        # Fallback rate should be 60% (3 out of 5)
        assert metrics["fallback_rate_percent"] == pytest.approx(60.0, abs=0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
