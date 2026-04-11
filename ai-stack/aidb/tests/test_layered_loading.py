#!/usr/bin/env python3
"""
Tests for Multi-Layer Memory Loading System

Phase 1.5 Slice 1.7: Test layered memory loading (L0-L3)
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aidb.layered_loading import LayeredMemory, load_memory_with_budget
from aidb.temporal_facts import TemporalFact


class MockFactStore:
    """Mock fact store for testing"""

    def __init__(self):
        self.facts = []

    def add(self, fact):
        self.facts.append(fact)
        return fact.fact_id

    def get_all(self):
        return self.facts


class TestLayeredMemory:
    """Test suite for LayeredMemory"""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            yield {
                "identity": tmpdir / "identity.txt",
                "critical_facts": tmpdir / "critical_facts.json"
            }

    @pytest.fixture
    def fact_store(self):
        """Create mock fact store with test data"""
        store = MockFactStore()

        # Add some test facts
        now = datetime.now(timezone.utc)

        store.add(TemporalFact(
            content="Use JWT with 7-day expiry for authentication",
            project="ai-stack",
            topic="auth",
            type="decision",
            valid_from=now - timedelta(days=30)
        ))

        store.add(TemporalFact(
            content="Always validate user input at API boundaries",
            project="ai-stack",
            topic="security",
            type="preference",
            valid_from=now - timedelta(days=60)
        ))

        store.add(TemporalFact(
            content="Use PostgreSQL for AIDB storage with pgvector extension",
            project="ai-stack",
            topic="database",
            type="decision",
            valid_from=now - timedelta(days=90)
        ))

        return store

    def test_load_l0_default(self, temp_files):
        """Test L0 loading with default identity"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        l0 = memory.load_l0()

        assert isinstance(l0, str)
        assert len(l0) > 0
        assert "AI agent" in l0 or "orchestrator" in l0
        # Approximate token limit: 50 tokens * 4 chars = 200 chars
        assert len(l0) <= 210  # Some tolerance

    def test_load_l0_custom_identity(self, temp_files):
        """Test L0 loading with custom identity"""
        # Write custom identity
        identity_text = (
            "I am Claude, AI coordinator for NixOS-Dev-Quick-Deploy. "
            "My role: orchestrate local agents. "
            "Focus: local-first AI, cost optimization."
        )
        temp_files["identity"].write_text(identity_text)

        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        l0 = memory.load_l0()

        assert "Claude" in l0
        assert "coordinator" in l0

    def test_load_l0_truncation(self, temp_files):
        """Test L0 truncates long identity text"""
        # Write very long identity
        long_identity = "A" * 1000
        temp_files["identity"].write_text(long_identity)

        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        l0 = memory.load_l0()

        # Should be truncated to ~50 tokens (200 chars)
        assert len(l0) <= 210
        assert l0.endswith("...")

    def test_load_l1_empty(self, temp_files):
        """Test L1 loading with no critical facts"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        l1 = memory.load_l1()

        assert isinstance(l1, str)
        assert "No critical facts" in l1

    def test_load_l1_with_facts(self, temp_files):
        """Test L1 loading with critical facts"""
        # Write critical facts
        critical_facts = [
            {
                "content": "Always use progressive disclosure",
                "project": "ai-stack"
            },
            {
                "content": "Prefer local agents over remote",
                "project": "ai-stack"
            }
        ]
        temp_files["critical_facts"].write_text(json.dumps(critical_facts))

        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        l1 = memory.load_l1()

        assert "progressive disclosure" in l1
        assert "local agents" in l1
        assert "[ai-stack]" in l1

    def test_load_l2_with_topic(self, temp_files, fact_store):
        """Test L2 loading with topic filter"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        l2 = memory.load_l2(topic="auth")

        assert isinstance(l2, str)
        assert "JWT" in l2 or "authentication" in l2

    def test_load_l2_with_multiple_topics(self, temp_files, fact_store):
        """Test L2 loading with multiple topics"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        l2 = memory.load_l2(topics=["auth", "security"])

        assert isinstance(l2, str)
        # Should contain facts from both topics
        assert len(l2) > 0

    def test_load_l2_no_fact_store(self, temp_files):
        """Test L2 with no fact store"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=None
        )

        l2 = memory.load_l2(topic="auth")

        assert l2 == ""

    def test_load_l3_search(self, temp_files, fact_store):
        """Test L3 semantic search"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        l3 = memory.load_l3(query="JWT authentication")

        assert isinstance(l3, str)
        assert "Search results" in l3
        # Should find the JWT fact
        assert "JWT" in l3 or "authentication" in l3

    def test_progressive_load_budget(self, temp_files, fact_store):
        """Test progressive loading with token budget"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        # Set up some critical facts
        critical_facts = [{"content": "Test fact", "project": "test"}]
        temp_files["critical_facts"].write_text(json.dumps(critical_facts))

        context = memory.progressive_load(
            query="authentication JWT",
            max_tokens=500
        )

        assert isinstance(context, str)
        assert "# Identity" in context
        assert "# Critical Facts" in context

        # Estimate tokens (rough)
        estimated_tokens = len(context) // 4
        # Should be under budget (with some tolerance)
        assert estimated_tokens <= 600

    def test_progressive_load_layers(self, temp_files, fact_store):
        """Test progressive loading includes multiple layers"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        # Set up critical facts
        critical_facts = [{"content": "Test fact", "project": "test"}]
        temp_files["critical_facts"].write_text(json.dumps(critical_facts))

        context = memory.progressive_load(
            query="authentication JWT",
            max_tokens=1000
        )

        # Should include multiple layers
        assert "# Identity" in context
        assert "# Critical Facts" in context
        assert "# Topic-Specific Memory" in context

    def test_progressive_load_tight_budget(self, temp_files):
        """Test progressive loading with very tight budget"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        context = memory.progressive_load(
            query="test",
            max_tokens=100
        )

        # Should at least include L0
        assert "# Identity" in context

        estimated_tokens = len(context) // 4
        # Should respect tight budget
        assert estimated_tokens <= 150

    def test_extract_topics(self, temp_files):
        """Test topic extraction from query"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        topics = memory._extract_topics("How do I implement JWT authentication?")

        assert isinstance(topics, list)
        assert "auth" in topics or "security" in topics

    def test_set_identity(self, temp_files):
        """Test setting identity"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        memory.set_identity("Test identity text")

        # File should be created
        assert temp_files["identity"].exists()

        # Should be loadable
        l0 = memory.load_l0()
        assert "Test identity" in l0

    def test_add_critical_fact(self, temp_files):
        """Test adding critical fact"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        memory.add_critical_fact("Test critical fact", project="test-project")

        # File should be created
        assert temp_files["critical_facts"].exists()

        # Should be loadable
        l1 = memory.load_l1()
        assert "Test critical fact" in l1
        assert "[test-project]" in l1

    def test_cache(self, temp_files):
        """Test layer caching"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        # Load L0 twice
        l0_first = memory.load_l0()
        l0_second = memory.load_l0()

        # Should return same content (from cache)
        assert l0_first == l0_second
        assert len(memory._cache) > 0

    def test_clear_cache(self, temp_files):
        """Test cache clearing"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"])
        )

        # Load L0 to populate cache
        memory.load_l0()
        assert len(memory._cache) > 0

        # Clear cache
        memory.clear_cache()
        assert len(memory._cache) == 0

    def test_get_layer_stats(self, temp_files, fact_store):
        """Test layer statistics"""
        memory = LayeredMemory(
            identity_file=str(temp_files["identity"]),
            critical_facts_file=str(temp_files["critical_facts"]),
            fact_store=fact_store
        )

        # Load some layers
        memory.load_l0()
        memory.load_l1()

        stats = memory.get_layer_stats()

        assert isinstance(stats, dict)
        assert "identity" in stats
        assert "critical" in stats
        assert stats["identity"] > 0
        assert stats["critical"] >= 0


def test_load_memory_with_budget_convenience(tmp_path):
    """Test convenience function"""
    identity_file = tmp_path / "identity.txt"
    identity_file.write_text("Test identity")

    # Can't fully test without modifying global paths
    # But verify it doesn't crash
    context = load_memory_with_budget("test query", max_tokens=200)
    assert isinstance(context, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
