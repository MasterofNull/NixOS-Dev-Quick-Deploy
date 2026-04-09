"""
Temporal Query API - Phase 1 Slice 1.2

Database query interface for temporal facts with metadata filtering
and semantic search capabilities.

Provides high-level query functions that integrate:
- Temporal validity filtering
- Metadata taxonomy (project/topic/type)
- Vector similarity search
- Agent ownership isolation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging

from .temporal_facts import TemporalFact

logger = logging.getLogger(__name__)


class TemporalQueryAPI:
    """
    Query interface for temporal facts database.

    This is an abstract interface - concrete implementations should
    inherit and provide actual database connectivity.
    """

    def __init__(self, connection=None):
        """
        Initialize query API with database connection.

        Args:
            connection: Database connection object (implementation-specific)
        """
        self.connection = connection

    def query_valid_at(
        self,
        timestamp: Optional[datetime] = None,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        fact_type: Optional[str] = None,
        agent_owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[TemporalFact]:
        """
        Query facts that are valid at a specific timestamp.

        Args:
            timestamp: Time to check (default: now)
            project: Filter by project
            topic: Filter by topic
            fact_type: Filter by type (decision, preference, etc.)
            agent_owner: Filter by agent owner (None = shared memory)
            tags: Filter by tags (must contain all listed tags)
            limit: Maximum number of results

        Returns:
            List of valid TemporalFact objects

        Example:
            # Get all valid decisions for ai-stack project
            facts = api.query_valid_at(
                project="ai-stack",
                fact_type="decision",
                limit=50
            )
        """
        check_time = timestamp or datetime.now(timezone.utc)

        # Build filter criteria
        filters = {"valid_at": check_time}
        if project:
            filters["project"] = project
        if topic:
            filters["topic"] = topic
        if fact_type:
            filters["type"] = fact_type
        if agent_owner is not None:  # Allow explicit None for shared memory
            filters["agent_owner"] = agent_owner
        if tags:
            filters["tags"] = tags

        logger.debug(f"Querying facts valid at {check_time} with filters: {filters}")

        # Subclass must implement _execute_query
        return self._execute_query(filters, limit)

    def query_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        fact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TemporalFact]:
        """
        Query facts that overlap with a time range.

        Returns facts where the validity period overlaps with [start_time, end_time].

        Args:
            start_time: Start of query range
            end_time: End of query range
            project: Filter by project
            topic: Filter by topic
            fact_type: Filter by type
            limit: Maximum number of results

        Returns:
            List of TemporalFact objects with overlapping validity

        Example:
            # Get all facts that were valid during March 2026
            facts = api.query_by_timerange(
                start_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
                end_time=datetime(2026, 3, 31, tzinfo=timezone.utc),
                project="ai-stack"
            )
        """
        if end_time < start_time:
            raise ValueError("end_time must be after start_time")

        filters = {
            "timerange_start": start_time,
            "timerange_end": end_time,
        }
        if project:
            filters["project"] = project
        if topic:
            filters["topic"] = topic
        if fact_type:
            filters["type"] = fact_type

        logger.debug(f"Querying facts in range {start_time} to {end_time}")

        return self._execute_query(filters, limit)

    def get_stale_facts(
        self,
        current_time: Optional[datetime] = None,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[TemporalFact]:
        """
        Get facts that are past their valid_until date.

        Useful for finding facts that may need updating or archival.

        Args:
            current_time: Time to check against (default: now)
            project: Filter by project
            topic: Filter by topic
            limit: Maximum number of results

        Returns:
            List of stale TemporalFact objects

        Example:
            # Find all stale facts for ai-stack project
            stale = api.get_stale_facts(project="ai-stack")
        """
        check_time = current_time or datetime.now(timezone.utc)

        filters = {"stale_at": check_time}
        if project:
            filters["project"] = project
        if topic:
            filters["topic"] = topic

        logger.info(f"Finding stale facts as of {check_time}")

        return self._execute_query(filters, limit)

    def semantic_search(
        self,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        fact_type: Optional[str] = None,
        valid_at: Optional[datetime] = None,
        agent_owner: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with vector similarity and metadata filtering.

        Combines vector similarity search with temporal validity and
        metadata filtering for high-precision retrieval.

        Args:
            query_text: Text query for embedding (if query_embedding not provided)
            query_embedding: Pre-computed embedding vector (1536 dims)
            project: Filter by project
            topic: Filter by topic
            fact_type: Filter by type
            valid_at: Only return facts valid at this time (default: now)
            agent_owner: Filter by agent owner
            limit: Maximum number of results
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            List of dicts with 'fact' (TemporalFact) and 'similarity' (float)

        Example:
            # Search for authentication-related decisions
            results = api.semantic_search(
                query_text="JWT token authentication",
                project="ai-stack",
                fact_type="decision",
                limit=5
            )
            for result in results:
                print(f"{result['similarity']:.3f}: {result['fact'].content}")
        """
        if not query_embedding and not query_text:
            raise ValueError("Must provide either query_embedding or query_text")

        check_time = valid_at or datetime.now(timezone.utc)

        filters = {
            "semantic_query": query_text,
            "query_embedding": query_embedding,
            "valid_at": check_time,
            "min_confidence": min_confidence,
        }
        if project:
            filters["project"] = project
        if topic:
            filters["topic"] = topic
        if fact_type:
            filters["type"] = fact_type
        if agent_owner is not None:
            filters["agent_owner"] = agent_owner

        logger.debug(
            f"Semantic search: query='{query_text[:50] if query_text else 'embedding'}', "
            f"filters={project}/{topic}/{fact_type}"
        )

        # Subclass implements _execute_semantic_search
        return self._execute_semantic_search(filters, limit)

    def get_agent_diary(
        self,
        agent_name: str,
        valid_at: Optional[datetime] = None,
        topic: Optional[str] = None,
        fact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TemporalFact]:
        """
        Get facts from a specific agent's private diary.

        Agent diaries are private memory spaces for individual agents
        to accumulate expertise and working memory.

        Args:
            agent_name: Agent identifier (qwen, codex, claude, gemini)
            valid_at: Time to check (default: now)
            topic: Filter by topic
            fact_type: Filter by type
            limit: Maximum number of results

        Returns:
            List of agent-owned TemporalFact objects

        Example:
            # Get qwen's recent discoveries
            facts = api.get_agent_diary(
                agent_name="qwen",
                fact_type="discovery",
                limit=20
            )
        """
        check_time = valid_at or datetime.now(timezone.utc)

        # Agent diary facts have agent_owner set and project = agent-{name}
        filters = {
            "agent_owner": agent_name,
            "project": f"agent-{agent_name}",
            "valid_at": check_time,
        }
        if topic:
            filters["topic"] = topic
        if fact_type:
            filters["type"] = fact_type

        logger.debug(f"Retrieving diary for agent {agent_name}")

        return self._execute_query(filters, limit)

    def store_fact(self, fact: TemporalFact) -> str:
        """
        Store a new temporal fact.

        Args:
            fact: TemporalFact to store

        Returns:
            The fact_id of the stored fact

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        logger.info(f"Storing fact: {fact.project}/{fact.topic} - {fact.content[:50]}...")
        raise NotImplementedError("Subclass must implement store_fact()")

    def update_fact(self, fact_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing fact.

        Note: Prefer creating new facts over updating content.
        Updates should primarily be used for expiring facts.

        Args:
            fact_id: ID of fact to update
            updates: Dictionary of field updates

        Returns:
            True if updated successfully

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        logger.info(f"Updating fact {fact_id}: {updates}")
        raise NotImplementedError("Subclass must implement update_fact()")

    def expire_fact(
        self,
        fact_id: str,
        until: datetime,
        reason: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> bool:
        """
        Mark a fact as expired (no longer valid after timestamp).

        Args:
            fact_id: ID of fact to expire
            until: When fact should expire
            reason: Optional explanation
            updated_by: Agent/user making the change

        Returns:
            True if expired successfully

        Example:
            # Expire a decision that was superseded
            api.expire_fact(
                fact_id="abc123",
                until=datetime.now(timezone.utc),
                reason="superseded",
                updated_by="claude"
            )
        """
        updates = {
            "valid_until": until,
            "updated_by": updated_by,
        }
        if reason:
            updates["expiration_reason"] = reason

        logger.info(f"Expiring fact {fact_id} at {until}" + (f": {reason}" if reason else ""))

        return self.update_fact(fact_id, updates)

    def get_fact_history(self, fact_id: str) -> List[Dict[str, Any]]:
        """
        Get audit history for a fact.

        Returns all changes made to the fact over time.

        Args:
            fact_id: ID of fact to query

        Returns:
            List of audit entries with field_changed, old_value, new_value, timestamp

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        logger.debug(f"Retrieving history for fact {fact_id}")
        raise NotImplementedError("Subclass must implement get_fact_history()")

    # Protected methods - subclasses must implement

    def _execute_query(
        self,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[TemporalFact]:
        """
        Execute a filtered query against the database.

        Subclass must implement database-specific query logic.

        Args:
            filters: Dictionary of filter criteria
            limit: Maximum results

        Returns:
            List of matching TemporalFact objects
        """
        raise NotImplementedError("Subclass must implement _execute_query()")

    def _execute_semantic_search(
        self,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic search with vector similarity.

        Subclass must implement vector search logic.

        Args:
            filters: Dictionary including semantic query and filters
            limit: Maximum results

        Returns:
            List of {fact: TemporalFact, similarity: float} dicts
        """
        raise NotImplementedError("Subclass must implement _execute_semantic_search()")


# Helper functions for simple filtering

def filter_facts_by_project(
    facts: List[TemporalFact],
    project: str,
) -> List[TemporalFact]:
    """Filter facts to specific project"""
    return [f for f in facts if f.project == project]


def filter_facts_by_topic(
    facts: List[TemporalFact],
    topic: str,
) -> List[TemporalFact]:
    """Filter facts to specific topic"""
    return [f for f in facts if f.topic == topic]


def filter_facts_by_type(
    facts: List[TemporalFact],
    fact_type: str,
) -> List[TemporalFact]:
    """Filter facts to specific type"""
    return [f for f in facts if f.type == fact_type]


def filter_facts_by_tags(
    facts: List[TemporalFact],
    tags: List[str],
    match_all: bool = True,
) -> List[TemporalFact]:
    """
    Filter facts by tags.

    Args:
        facts: List of facts to filter
        tags: Tags to match
        match_all: If True, fact must have all tags; if False, any tag

    Returns:
        Filtered list
    """
    if match_all:
        return [f for f in facts if all(tag in f.tags for tag in tags)]
    else:
        return [f for f in facts if any(tag in f.tags for tag in tags)]


def filter_facts_by_confidence(
    facts: List[TemporalFact],
    min_confidence: float = 0.0,
    max_confidence: float = 1.0,
) -> List[TemporalFact]:
    """Filter facts by confidence score range"""
    return [
        f for f in facts
        if min_confidence <= f.confidence <= max_confidence
    ]
