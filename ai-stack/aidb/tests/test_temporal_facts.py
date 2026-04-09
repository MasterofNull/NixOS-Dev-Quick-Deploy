"""
Unit tests for Temporal Facts - Phase 1 Slice 1.2

Tests temporal validity, staleness detection, and fact lifecycle management.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add ai-stack to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aidb.temporal_facts import (
    TemporalFact,
    get_valid_facts,
    get_stale_facts,
)


class TestTemporalFactCreation:
    """Test TemporalFact creation and validation"""

    def test_create_minimal_fact(self):
        """Test creating fact with minimal required fields"""
        fact = TemporalFact(
            content="Test fact",
            project="ai-stack"
        )

        assert fact.content == "Test fact"
        assert fact.project == "ai-stack"
        assert fact.type == "fact"  # Default
        assert fact.confidence == 1.0  # Default
        assert fact.valid_until is None  # Ongoing by default
        assert fact.agent_owner is None  # Shared by default

    def test_create_complete_fact(self):
        """Test creating fact with all fields"""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=30)

        fact = TemporalFact(
            content="Complete test fact",
            project="ai-stack",
            topic="testing",
            type="decision",
            valid_from=now,
            valid_until=end,
            agent_owner="qwen",
            tags=["important", "test"],
            confidence=0.9,
            source="unit-test"
        )

        assert fact.content == "Complete test fact"
        assert fact.project == "ai-stack"
        assert fact.topic == "testing"
        assert fact.type == "decision"
        assert fact.valid_from == now
        assert fact.valid_until == end
        assert fact.agent_owner == "qwen"
        assert fact.tags == ["important", "test"]
        assert fact.confidence == 0.9
        assert fact.source == "unit-test"

    def test_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError"""
        with pytest.raises(ValueError, match="Invalid type"):
            TemporalFact(
                content="Test",
                project="test",
                type="invalid_type"
            )

    def test_invalid_confidence_raises_error(self):
        """Test that confidence outside 0-1 range raises error"""
        with pytest.raises(ValueError, match="Confidence must be between"):
            TemporalFact(
                content="Test",
                project="test",
                confidence=1.5
            )

        with pytest.raises(ValueError, match="Confidence must be between"):
            TemporalFact(
                content="Test",
                project="test",
                confidence=-0.1
            )

    def test_invalid_temporal_order_raises_error(self):
        """Test that valid_until before valid_from raises error"""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)

        with pytest.raises(ValueError, match="cannot be before valid_from"):
            TemporalFact(
                content="Test",
                project="test",
                valid_from=now,
                valid_until=past
            )

    def test_fact_id_generated(self):
        """Test that fact_id is auto-generated"""
        fact = TemporalFact(content="Test", project="test")
        assert fact.fact_id is not None
        assert len(fact.fact_id) == 32  # SHA256 truncated to 32 chars

    def test_content_hash_generated(self):
        """Test that content hash is generated"""
        fact = TemporalFact(content="Test", project="test")
        assert fact.content_hash is not None
        assert len(fact.content_hash) == 64  # Full SHA256


class TestTemporalValidity:
    """Test temporal validity checking"""

    def test_is_valid_at_ongoing_fact(self):
        """Test ongoing fact (no end date) is always valid after start"""
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        fact = TemporalFact(
            content="Ongoing fact",
            project="test",
            valid_from=start
        )

        # Valid after start
        assert fact.is_valid_at(datetime(2026, 4, 5, tzinfo=timezone.utc))
        assert fact.is_valid_at(datetime(2026, 12, 31, tzinfo=timezone.utc))

        # Not valid before start
        assert not fact.is_valid_at(datetime(2026, 3, 31, tzinfo=timezone.utc))

    def test_is_valid_at_bounded_fact(self):
        """Test fact with start and end dates"""
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        end = datetime(2026, 4, 30, tzinfo=timezone.utc)

        fact = TemporalFact(
            content="Bounded fact",
            project="test",
            valid_from=start,
            valid_until=end
        )

        # Valid within range
        assert fact.is_valid_at(datetime(2026, 4, 15, tzinfo=timezone.utc))

        # Not valid before start
        assert not fact.is_valid_at(datetime(2026, 3, 31, tzinfo=timezone.utc))

        # Not valid after end
        assert not fact.is_valid_at(datetime(2026, 5, 1, tzinfo=timezone.utc))

    def test_is_ongoing(self):
        """Test is_ongoing method"""
        ongoing_fact = TemporalFact(
            content="Ongoing",
            project="test"
        )
        assert ongoing_fact.is_ongoing()

        bounded_fact = TemporalFact(
            content="Bounded",
            project="test",
            valid_until=datetime(2026, 12, 31, tzinfo=timezone.utc)
        )
        assert not bounded_fact.is_ongoing()


class TestStalenessDetection:
    """Test staleness detection"""

    def test_is_stale_ongoing_fact(self):
        """Test that ongoing facts are never stale"""
        fact = TemporalFact(
            content="Ongoing",
            project="test"
        )

        assert not fact.is_stale()
        assert not fact.is_stale(datetime(2050, 1, 1, tzinfo=timezone.utc))

    def test_is_stale_expired_fact(self):
        """Test that expired facts are stale"""
        start_date = datetime(2026, 2, 1, tzinfo=timezone.utc)
        past_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        fact = TemporalFact(
            content="Expired",
            project="test",
            valid_from=start_date,
            valid_until=past_date
        )

        current = datetime(2026, 4, 9, tzinfo=timezone.utc)
        assert fact.is_stale(current)

    def test_is_stale_future_expiry(self):
        """Test that facts expiring in future are not stale"""
        future_date = datetime(2026, 12, 31, tzinfo=timezone.utc)
        fact = TemporalFact(
            content="Future expiry",
            project="test",
            valid_until=future_date
        )

        current = datetime(2026, 4, 9, tzinfo=timezone.utc)
        assert not fact.is_stale(current)


class TestFactExpiration:
    """Test fact expiration functionality"""

    def test_expire_fact(self):
        """Test expiring a fact"""
        fact = TemporalFact(
            content="To be expired",
            project="test"
        )

        assert fact.is_ongoing()

        expire_date = datetime(2026, 4, 30, tzinfo=timezone.utc)
        fact.expire(expire_date, reason="superseded")

        assert fact.valid_until == expire_date
        assert not fact.is_ongoing()
        assert "expiration_reason:superseded" in fact.tags

    def test_expire_before_start_raises_error(self):
        """Test that expiring before valid_from raises error"""
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        fact = TemporalFact(
            content="Test",
            project="test",
            valid_from=start
        )

        before_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Cannot expire fact before"):
            fact.expire(before_start)

    def test_expire_increments_version(self):
        """Test that expiring fact increments version"""
        fact = TemporalFact(content="Test", project="test")
        original_version = fact.version

        fact.expire(datetime(2026, 12, 31, tzinfo=timezone.utc))

        assert fact.version == original_version + 1


class TestFactSerialization:
    """Test fact serialization to/from dict"""

    def test_to_dict(self):
        """Test converting fact to dictionary"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        fact = TemporalFact(
            content="Test fact",
            project="ai-stack",
            topic="testing",
            type="decision",
            valid_from=now,
            agent_owner="qwen",
            tags=["test"],
            confidence=0.9
        )

        data = fact.to_dict()

        assert data["content"] == "Test fact"
        assert data["project"] == "ai-stack"
        assert data["topic"] == "testing"
        assert data["type"] == "decision"
        assert data["valid_from"] == now.isoformat()
        assert data["agent_owner"] == "qwen"
        assert data["tags"] == ["test"]
        assert data["confidence"] == 0.9
        assert "fact_id" in data
        assert "content_hash" in data

    def test_from_dict(self):
        """Test creating fact from dictionary"""
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        data = {
            "fact_id": "test123",
            "content": "Test fact",
            "project": "ai-stack",
            "topic": "testing",
            "type": "decision",
            "valid_from": now.isoformat(),
            "valid_until": None,
            "agent_owner": "qwen",
            "tags": ["test"],
            "confidence": 0.9,
            "source": "test",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "version": 1
        }

        fact = TemporalFact.from_dict(data)

        assert fact.content == "Test fact"
        assert fact.project == "ai-stack"
        assert fact.topic == "testing"
        assert fact.type == "decision"
        assert fact.valid_from == now
        assert fact.valid_until is None
        assert fact.agent_owner == "qwen"

    def test_roundtrip_serialization(self):
        """Test that to_dict → from_dict preserves data"""
        original = TemporalFact(
            content="Roundtrip test",
            project="test",
            topic="serialization",
            type="discovery",
            tags=["important"],
            confidence=0.95
        )

        data = original.to_dict()
        restored = TemporalFact.from_dict(data)

        assert restored.content == original.content
        assert restored.project == original.project
        assert restored.topic == original.topic
        assert restored.type == original.type
        assert restored.tags == original.tags
        assert restored.confidence == original.confidence


class TestFactFiltering:
    """Test helper functions for filtering facts"""

    def test_get_valid_facts(self):
        """Test filtering to valid facts only"""
        now = datetime(2026, 4, 9, tzinfo=timezone.utc)

        facts = [
            # Valid ongoing fact
            TemporalFact(
                content="Ongoing",
                project="test",
                valid_from=datetime(2026, 3, 1, tzinfo=timezone.utc)
            ),
            # Valid bounded fact
            TemporalFact(
                content="Current",
                project="test",
                valid_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
                valid_until=datetime(2026, 4, 30, tzinfo=timezone.utc)
            ),
            # Expired fact
            TemporalFact(
                content="Expired",
                project="test",
                valid_from=datetime(2026, 2, 1, tzinfo=timezone.utc),
                valid_until=datetime(2026, 3, 31, tzinfo=timezone.utc)
            ),
            # Future fact
            TemporalFact(
                content="Future",
                project="test",
                valid_from=datetime(2026, 5, 1, tzinfo=timezone.utc)
            ),
        ]

        valid = get_valid_facts(facts, at_time=now)

        assert len(valid) == 2
        contents = [f.content for f in valid]
        assert "Ongoing" in contents
        assert "Current" in contents
        assert "Expired" not in contents
        assert "Future" not in contents

    def test_get_stale_facts(self):
        """Test filtering to stale facts only"""
        now = datetime(2026, 4, 9, tzinfo=timezone.utc)

        facts = [
            # Ongoing (not stale)
            TemporalFact(
                content="Ongoing",
                project="test"
            ),
            # Expired (stale)
            TemporalFact(
                content="Stale1",
                project="test",
                valid_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
                valid_until=datetime(2026, 3, 31, tzinfo=timezone.utc)
            ),
            # Also expired (stale)
            TemporalFact(
                content="Stale2",
                project="test",
                valid_from=datetime(2025, 12, 1, tzinfo=timezone.utc),
                valid_until=datetime(2026, 1, 1, tzinfo=timezone.utc)
            ),
            # Future expiry (not stale)
            TemporalFact(
                content="NotStale",
                project="test",
                valid_until=datetime(2026, 12, 31, tzinfo=timezone.utc)
            ),
        ]

        stale = get_stale_facts(facts, current_time=now)

        assert len(stale) == 2
        contents = [f.content for f in stale]
        assert "Stale1" in contents
        assert "Stale2" in contents
        assert "Ongoing" not in contents
        assert "NotStale" not in contents


class TestAgentOwnership:
    """Test agent ownership and isolation"""

    def test_shared_memory_fact(self):
        """Test fact with no agent owner (shared)"""
        fact = TemporalFact(
            content="Shared fact",
            project="common"
        )

        assert fact.agent_owner is None

    def test_agent_owned_fact(self):
        """Test fact owned by specific agent"""
        fact = TemporalFact(
            content="qwen's private fact",
            project="agent-qwen",
            agent_owner="qwen"
        )

        assert fact.agent_owner == "qwen"

    def test_different_agents_different_facts(self):
        """Test that different agents can have separate facts"""
        qwen_fact = TemporalFact(
            content="qwen knowledge",
            project="agent-qwen",
            agent_owner="qwen"
        )

        codex_fact = TemporalFact(
            content="codex knowledge",
            project="agent-codex",
            agent_owner="codex"
        )

        assert qwen_fact.agent_owner != codex_fact.agent_owner
        assert qwen_fact.project != codex_fact.project


class TestFactTypes:
    """Test different fact types"""

    def test_all_valid_types(self):
        """Test creating facts with all valid types"""
        valid_types = ["decision", "preference", "discovery", "event", "advice", "fact"]

        for fact_type in valid_types:
            fact = TemporalFact(
                content=f"Test {fact_type}",
                project="test",
                type=fact_type
            )
            assert fact.type == fact_type

    def test_decision_type(self):
        """Test decision type fact"""
        fact = TemporalFact(
            content="Using JWT with 7-day expiry for authentication",
            project="ai-stack",
            topic="auth",
            type="decision"
        )

        assert fact.type == "decision"

    def test_preference_type(self):
        """Test preference type fact"""
        fact = TemporalFact(
            content="User prefers verbose logging during development",
            project="dashboard",
            type="preference"
        )

        assert fact.type == "preference"

    def test_discovery_type(self):
        """Test discovery type fact"""
        fact = TemporalFact(
            content="Multi-layer loading reduces token usage by 50%",
            project="ai-stack",
            topic="memory",
            type="discovery"
        )

        assert fact.type == "discovery"
