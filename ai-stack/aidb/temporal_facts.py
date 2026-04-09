"""
Temporal Facts Implementation - Phase 1 Slice 1.2

This module implements temporal validity for memory facts, allowing facts to have
start and end dates for validity checking and staleness detection.

Inspired by MemPalace's temporal knowledge graph with adaptations for our use case.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemporalFact:
    """
    A memory fact with temporal validity.

    Facts can be valid for a specific time period, enabling:
    - Historical queries ("what was true in March 2026?")
    - Staleness detection (facts that need updating)
    - Temporal knowledge graph with time-windowed relationships
    """

    # Core content
    content: str
    project: str
    topic: Optional[str] = None
    type: str = "fact"  # decision, preference, discovery, event, advice, fact

    # Temporal validity
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Optional[datetime] = None  # None = ongoing/indefinite

    # Agent ownership (None = shared memory)
    agent_owner: Optional[str] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0-1.0
    source: Optional[str] = None

    # Embeddings (set externally)
    embedding_vector: Optional[List[float]] = None

    # Audit trail
    fact_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    version: int = 1

    def __post_init__(self):
        """Validate and initialize fact after creation"""
        # Validate type
        valid_types = {"decision", "preference", "discovery", "event", "advice", "fact"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid type: {self.type}. Must be one of {valid_types}")

        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

        # Validate temporal consistency
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValueError(
                f"valid_until ({self.valid_until}) cannot be before valid_from ({self.valid_from})"
            )

        # Generate content hash for deduplication
        if not hasattr(self, "_content_hash"):
            self._content_hash = self._generate_content_hash()

        # Generate fact_id if not set
        if not self.fact_id:
            self.fact_id = self._generate_fact_id()

    def _generate_content_hash(self) -> str:
        """Generate SHA256 hash of content for deduplication"""
        content_bytes = self.content.encode("utf-8")
        return hashlib.sha256(content_bytes).hexdigest()

    def _generate_fact_id(self) -> str:
        """Generate unique fact ID"""
        # Combine content hash, project, and timestamp for uniqueness
        unique_str = f"{self._content_hash}:{self.project}:{self.valid_from.isoformat()}"
        return hashlib.sha256(unique_str.encode("utf-8")).hexdigest()[:32]

    @property
    def content_hash(self) -> str:
        """Get content hash for deduplication"""
        return self._content_hash

    def is_valid_at(self, timestamp: datetime) -> bool:
        """
        Check if fact is valid at given timestamp

        Args:
            timestamp: The time to check validity

        Returns:
            True if fact is valid at timestamp, False otherwise
        """
        if timestamp < self.valid_from:
            return False
        if self.valid_until and timestamp > self.valid_until:
            return False
        return True

    def is_stale(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if fact should be updated (past valid_until)

        Args:
            current_time: Time to check against (default: now)

        Returns:
            True if fact is stale, False if still valid or ongoing
        """
        if not self.valid_until:
            return False  # Ongoing fact, not stale

        check_time = current_time or datetime.now(timezone.utc)
        return check_time > self.valid_until

    def is_ongoing(self) -> bool:
        """Check if fact has indefinite validity (no end date)"""
        return self.valid_until is None

    def expire(self, until: datetime, reason: Optional[str] = None):
        """
        Mark fact as no longer valid after given timestamp

        Args:
            until: When fact should expire
            reason: Optional explanation for expiration
        """
        if until < self.valid_from:
            raise ValueError("Cannot expire fact before it became valid")

        self.valid_until = until
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1

        if reason:
            if "expiration_reason" not in self.tags:
                self.tags.append(f"expiration_reason:{reason}")

        logger.info(
            f"Fact {self.fact_id} expired at {until}"
            + (f" reason: {reason}" if reason else "")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "fact_id": self.fact_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "project": self.project,
            "topic": self.topic,
            "type": self.type,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "agent_owner": self.agent_owner,
            "tags": self.tags,
            "confidence": self.confidence,
            "source": self.source,
            "embedding_vector": self.embedding_vector,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemporalFact:
        """Create TemporalFact from dictionary"""
        # Parse datetime fields
        valid_from = datetime.fromisoformat(data["valid_from"])
        valid_until = (
            datetime.fromisoformat(data["valid_until"])
            if data.get("valid_until")
            else None
        )
        created_at = datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat()))
        updated_at = datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))

        return cls(
            fact_id=data.get("fact_id"),
            content=data["content"],
            project=data["project"],
            topic=data.get("topic"),
            type=data.get("type", "fact"),
            valid_from=valid_from,
            valid_until=valid_until,
            agent_owner=data.get("agent_owner"),
            tags=data.get("tags", []),
            confidence=data.get("confidence", 1.0),
            source=data.get("source"),
            embedding_vector=data.get("embedding_vector"),
            created_at=created_at,
            created_by=data.get("created_by"),
            updated_at=updated_at,
            updated_by=data.get("updated_by"),
            version=data.get("version", 1),
        )

    def __repr__(self) -> str:
        """String representation for debugging"""
        validity = f"{self.valid_from.date()}"
        if self.valid_until:
            validity += f" → {self.valid_until.date()}"
        else:
            validity += " → ongoing"

        owner = f" (agent: {self.agent_owner})" if self.agent_owner else ""
        return (
            f"TemporalFact("
            f"{self.project}/{self.topic or 'general'}: "
            f"{self.content[:50]}... "
            f"[{validity}]{owner})"
        )


class TemporalFactStore:
    """
    Storage interface for temporal facts

    This is an abstract interface. Concrete implementations should inherit
    and implement the actual database operations.
    """

    def store(self, fact: TemporalFact) -> str:
        """
        Store a temporal fact

        Args:
            fact: The fact to store

        Returns:
            The fact_id of the stored fact

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement store()")

    def retrieve(self, fact_id: str) -> Optional[TemporalFact]:
        """
        Retrieve a fact by ID

        Args:
            fact_id: The unique fact ID

        Returns:
            TemporalFact if found, None otherwise

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement retrieve()")

    def query_valid_at(
        self,
        timestamp: datetime,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        type: Optional[str] = None,
        agent_owner: Optional[str] = None,
    ) -> List[TemporalFact]:
        """
        Query facts that were valid at a specific timestamp

        Args:
            timestamp: The time to check
            project: Filter by project (optional)
            topic: Filter by topic (optional)
            type: Filter by type (optional)
            agent_owner: Filter by agent owner (optional)

        Returns:
            List of facts valid at timestamp

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement query_valid_at()")

    def get_stale_facts(
        self,
        current_time: Optional[datetime] = None,
        project: Optional[str] = None,
    ) -> List[TemporalFact]:
        """
        Get facts that are past their valid_until date

        Args:
            current_time: Time to check against (default: now)
            project: Filter by project (optional)

        Returns:
            List of stale facts that may need updating

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement get_stale_facts()")


def get_valid_facts(
    facts: List[TemporalFact],
    at_time: Optional[datetime] = None
) -> List[TemporalFact]:
    """
    Filter facts to only those valid at given time

    Args:
        facts: List of facts to filter
        at_time: Time to check (default: now)

    Returns:
        Filtered list of valid facts
    """
    check_time = at_time or datetime.now(timezone.utc)
    return [f for f in facts if f.is_valid_at(check_time)]


def get_stale_facts(
    facts: List[TemporalFact],
    current_time: Optional[datetime] = None
) -> List[TemporalFact]:
    """
    Filter facts to only those that are stale

    Args:
        facts: List of facts to filter
        current_time: Time to check (default: now)

    Returns:
        Filtered list of stale facts
    """
    check_time = current_time or datetime.now(timezone.utc)
    return [f for f in facts if f.is_stale(check_time)]
