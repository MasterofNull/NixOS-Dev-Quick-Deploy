"""
Unit tests for Temporal Query API - Phase 1 Slice 1.2

Tests query interface, filtering, and helper functions.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# Add ai-stack to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aidb.temporal_facts import TemporalFact
from aidb.temporal_query import (
    TemporalQueryAPI,
    filter_facts_by_project,
    filter_facts_by_topic,
    filter_facts_by_type,
    filter_facts_by_tags,
    filter_facts_by_confidence,
)


class MockTemporalQueryAPI(TemporalQueryAPI):
    """
    Mock implementation of TemporalQueryAPI for testing.

    Uses in-memory list of facts instead of database.
    """

    def __init__(self, facts: List[TemporalFact] = None):
        super().__init__(connection=None)
        self.facts = facts or []
        self.stored_facts = []

    def _execute_query(
        self,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[TemporalFact]:
        """Filter in-memory facts based on criteria"""
        results = self.facts[:]

        # Filter by valid_at timestamp
        if "valid_at" in filters:
            check_time = filters["valid_at"]
            results = [f for f in results if f.is_valid_at(check_time)]

        # Filter by stale_at timestamp
        if "stale_at" in filters:
            check_time = filters["stale_at"]
            results = [f for f in results if f.is_stale(check_time)]

        # Filter by timerange
        if "timerange_start" in filters and "timerange_end" in filters:
            start = filters["timerange_start"]
            end = filters["timerange_end"]
            results = [
                f for f in results
                if not (f.valid_until and f.valid_until < start) and
                   not (end < f.valid_from)
            ]

        # Filter by project
        if "project" in filters:
            results = [f for f in results if f.project == filters["project"]]

        # Filter by topic
        if "topic" in filters:
            results = [f for f in results if f.topic == filters["topic"]]

        # Filter by type
        if "type" in filters:
            results = [f for f in results if f.type == filters["type"]]

        # Filter by agent_owner
        if "agent_owner" in filters:
            results = [f for f in results if f.agent_owner == filters["agent_owner"]]

        # Filter by tags
        if "tags" in filters:
            required_tags = filters["tags"]
            results = [
                f for f in results
                if all(tag in f.tags for tag in required_tags)
            ]

        return results[:limit]

    def _execute_semantic_search(
        self,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Mock semantic search - just text matching for testing.
        Real implementation would use vector similarity.
        """
        query_text = filters.get("semantic_query", "").lower()
        check_time = filters.get("valid_at", datetime.now(timezone.utc))

        # Get valid facts
        results = [f for f in self.facts if f.is_valid_at(check_time)]

        # Apply metadata filters
        if "project" in filters:
            results = [f for f in results if f.project == filters["project"]]
        if "topic" in filters:
            results = [f for f in results if f.topic == filters["topic"]]
        if "type" in filters:
            results = [f for f in results if f.type == filters["type"]]
        if "agent_owner" in filters:
            results = [f for f in results if f.agent_owner == filters["agent_owner"]]

        # Simple text matching (mock similarity)
        if query_text:
            matches = []
            for fact in results:
                if query_text in fact.content.lower():
                    similarity = 0.9  # High similarity for exact match
                elif any(word in fact.content.lower() for word in query_text.split()):
                    similarity = 0.6  # Medium similarity for partial match
                else:
                    similarity = 0.1  # Low similarity
                matches.append({"fact": fact, "similarity": similarity})

            # Sort by similarity
            matches.sort(key=lambda x: x["similarity"], reverse=True)
            results = matches[:limit]
        else:
            results = [{"fact": f, "similarity": 1.0} for f in results[:limit]]

        return results

    def store_fact(self, fact: TemporalFact) -> str:
        """Store fact in memory"""
        self.stored_facts.append(fact)
        return fact.fact_id

    def update_fact(self, fact_id: str, updates: Dict[str, Any]) -> bool:
        """Update fact in memory"""
        for fact in self.facts:
            if fact.fact_id == fact_id:
                for key, value in updates.items():
                    if hasattr(fact, key):
                        setattr(fact, key, value)
                return True
        return False


class TestTemporalQueryAPI:
    """Test TemporalQueryAPI query methods"""

    def setup_method(self):
        """Create test facts for each test"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        past = datetime(2026, 3, 1, tzinfo=timezone.utc)
        future = datetime(2026, 5, 1, tzinfo=timezone.utc)

        self.facts = [
            # Valid ongoing fact
            TemporalFact(
                content="Ongoing fact about ai-stack",
                project="ai-stack",
                topic="memory",
                type="decision",
                valid_from=past,
                tags=["important"]
            ),
            # Valid bounded fact
            TemporalFact(
                content="Current sprint decision",
                project="ai-stack",
                topic="workflow",
                type="decision",
                valid_from=now - timedelta(days=5),
                valid_until=now + timedelta(days=5)
            ),
            # Expired fact
            TemporalFact(
                content="Old architecture decision",
                project="ai-stack",
                topic="memory",
                type="decision",
                valid_from=past - timedelta(days=30),
                valid_until=past
            ),
            # Future fact
            TemporalFact(
                content="Future planned feature",
                project="dashboard",
                topic="ui",
                type="discovery",
                valid_from=future
            ),
            # Agent diary fact
            TemporalFact(
                content="qwen's personal learning",
                project="agent-qwen",
                topic="coding",
                type="discovery",
                valid_from=past,
                agent_owner="qwen",
                tags=["python", "learning"]
            ),
        ]

        self.api = MockTemporalQueryAPI(self.facts)

    def test_query_valid_at_current(self):
        """Test querying facts valid at current time"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.query_valid_at(timestamp=now)

        # Should get ongoing and current facts, not expired or future
        assert len(results) == 3
        contents = [f.content for f in results]
        assert "Ongoing fact about ai-stack" in contents
        assert "Current sprint decision" in contents
        assert "qwen's personal learning" in contents
        assert "Old architecture decision" not in contents
        assert "Future planned feature" not in contents

    def test_query_valid_at_with_project_filter(self):
        """Test querying with project filter"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.query_valid_at(
            timestamp=now,
            project="ai-stack"
        )

        assert len(results) == 2
        for fact in results:
            assert fact.project == "ai-stack"

    def test_query_valid_at_with_multiple_filters(self):
        """Test querying with multiple filters"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.query_valid_at(
            timestamp=now,
            project="ai-stack",
            topic="memory",
            fact_type="decision"
        )

        assert len(results) == 1
        assert results[0].content == "Ongoing fact about ai-stack"

    def test_query_valid_at_with_tags_filter(self):
        """Test querying with tags filter"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.query_valid_at(
            timestamp=now,
            tags=["important"]
        )

        assert len(results) == 1
        assert "important" in results[0].tags

    def test_query_by_timerange(self):
        """Test querying facts by time range"""
        start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end = datetime(2026, 4, 15, tzinfo=timezone.utc)

        results = self.api.query_by_timerange(start, end)

        # Should include facts that overlap with March-April 2026
        assert len(results) >= 3

    def test_query_by_timerange_with_filters(self):
        """Test timerange query with metadata filters"""
        start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end = datetime(2026, 4, 15, tzinfo=timezone.utc)

        results = self.api.query_by_timerange(
            start, end,
            project="ai-stack",
            fact_type="decision"
        )

        for fact in results:
            assert fact.project == "ai-stack"
            assert fact.type == "decision"

    def test_query_by_timerange_invalid(self):
        """Test that invalid timerange raises error"""
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        end = datetime(2026, 3, 1, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="end_time must be after start_time"):
            self.api.query_by_timerange(start, end)

    def test_get_stale_facts(self):
        """Test getting stale facts"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.get_stale_facts(current_time=now)

        # Only expired fact should be stale
        assert len(results) == 1
        assert results[0].content == "Old architecture decision"

    def test_get_stale_facts_with_project_filter(self):
        """Test getting stale facts for specific project"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.get_stale_facts(
            current_time=now,
            project="ai-stack"
        )

        assert len(results) == 1
        assert results[0].project == "ai-stack"

    def test_get_agent_diary(self):
        """Test retrieving agent-specific diary"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.get_agent_diary("qwen", valid_at=now)

        assert len(results) == 1
        assert results[0].agent_owner == "qwen"
        assert results[0].project == "agent-qwen"

    def test_get_agent_diary_with_filters(self):
        """Test agent diary with topic/type filters"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.get_agent_diary(
            "qwen",
            valid_at=now,
            topic="coding",
            fact_type="discovery"
        )

        assert len(results) == 1
        assert results[0].topic == "coding"
        assert results[0].type == "discovery"

    def test_semantic_search_basic(self):
        """Test basic semantic search"""
        results = self.api.semantic_search(
            query_text="ai-stack",
            limit=5
        )

        assert len(results) > 0
        assert all("fact" in r and "similarity" in r for r in results)
        # Results should be sorted by similarity
        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True)

    def test_semantic_search_with_filters(self):
        """Test semantic search with metadata filters"""
        results = self.api.semantic_search(
            query_text="decision",
            project="ai-stack",
            fact_type="decision",
            limit=5
        )

        for result in results:
            fact = result["fact"]
            assert fact.project == "ai-stack"
            assert fact.type == "decision"

    def test_semantic_search_requires_query(self):
        """Test that semantic search requires query or embedding"""
        with pytest.raises(ValueError, match="Must provide either"):
            self.api.semantic_search(limit=5)

    def test_store_fact(self):
        """Test storing a fact"""
        new_fact = TemporalFact(
            content="Test fact to store",
            project="test"
        )

        fact_id = self.api.store_fact(new_fact)

        assert fact_id == new_fact.fact_id
        assert new_fact in self.api.stored_facts

    def test_update_fact(self):
        """Test updating a fact"""
        fact = self.facts[0]
        original_confidence = fact.confidence

        success = self.api.update_fact(
            fact.fact_id,
            {"confidence": 0.8}
        )

        assert success
        assert fact.confidence == 0.8
        assert fact.confidence != original_confidence

    def test_expire_fact(self):
        """Test expiring a fact"""
        fact = self.facts[0]
        assert fact.is_ongoing()

        expire_time = datetime(2026, 12, 31, tzinfo=timezone.utc)
        success = self.api.expire_fact(
            fact.fact_id,
            until=expire_time,
            reason="test expiration"
        )

        assert success
        assert fact.valid_until == expire_time
        assert not fact.is_ongoing()

    def test_query_limit(self):
        """Test that limit parameter is respected"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        results = self.api.query_valid_at(timestamp=now, limit=2)

        assert len(results) <= 2


class TestHelperFunctions:
    """Test helper filtering functions"""

    def setup_method(self):
        """Create test facts"""
        self.facts = [
            TemporalFact(
                content="Fact 1",
                project="ai-stack",
                topic="memory",
                type="decision",
                tags=["important", "urgent"],
                confidence=0.9
            ),
            TemporalFact(
                content="Fact 2",
                project="dashboard",
                topic="ui",
                type="preference",
                tags=["important"],
                confidence=0.7
            ),
            TemporalFact(
                content="Fact 3",
                project="ai-stack",
                topic="workflow",
                type="decision",
                tags=["urgent"],
                confidence=0.5
            ),
        ]

    def test_filter_by_project(self):
        """Test filtering by project"""
        results = filter_facts_by_project(self.facts, "ai-stack")

        assert len(results) == 2
        for fact in results:
            assert fact.project == "ai-stack"

    def test_filter_by_topic(self):
        """Test filtering by topic"""
        results = filter_facts_by_topic(self.facts, "memory")

        assert len(results) == 1
        assert results[0].topic == "memory"

    def test_filter_by_type(self):
        """Test filtering by type"""
        results = filter_facts_by_type(self.facts, "decision")

        assert len(results) == 2
        for fact in results:
            assert fact.type == "decision"

    def test_filter_by_tags_match_all(self):
        """Test filtering by tags (must have all)"""
        results = filter_facts_by_tags(
            self.facts,
            ["important", "urgent"],
            match_all=True
        )

        assert len(results) == 1
        assert "important" in results[0].tags
        assert "urgent" in results[0].tags

    def test_filter_by_tags_match_any(self):
        """Test filtering by tags (can have any)"""
        results = filter_facts_by_tags(
            self.facts,
            ["important", "urgent"],
            match_all=False
        )

        assert len(results) == 3  # All facts have at least one tag

    def test_filter_by_confidence(self):
        """Test filtering by confidence range"""
        results = filter_facts_by_confidence(
            self.facts,
            min_confidence=0.6,
            max_confidence=0.9
        )

        assert len(results) == 2
        for fact in results:
            assert 0.6 <= fact.confidence <= 0.9

    def test_filter_by_confidence_defaults(self):
        """Test confidence filter with default range"""
        results = filter_facts_by_confidence(self.facts)

        # All facts should pass (default 0.0-1.0)
        assert len(results) == 3
