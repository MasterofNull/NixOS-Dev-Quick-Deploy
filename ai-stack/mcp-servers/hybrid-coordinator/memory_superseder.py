"""
memory_superseder.py — Logical fact versioning and temporal supersession (Phase 55.1)

Handles the logic of 'versioning' memories when new, contradicting information
is received. Instead of deleting old data, it creates a chain of truth.

Concepts:
  - Logical Clock: Incremental version for specific facts.
  - Supersession: Closing the validity window of an old fact.
  - Lineage: Tracking the ID of the predecessor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_postgres_client: Optional[Any] = None

def init(postgres_client: Optional[Any] = None) -> None:
    global _postgres_client
    _postgres_client = postgres_client
    logger.info("memory_superseder: initialized (Phase 55.1 Active)")


class MemorySuperseder:
    """
    Orchestrates memory versioning and conflict resolution.
    """

    def __init__(self) -> None:
        pass

    async def ensure_schema(self) -> None:
        """Create supersession lineage table if it doesn't exist."""
        if not _postgres_client:
            return

        ddl = """
        CREATE TABLE IF NOT EXISTS memory_supersessions (
            id SERIAL PRIMARY KEY,
            predecessor_id TEXT NOT NULL,
            successor_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            superseded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            logical_clock FLOAT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_supersessions_successor ON memory_supersessions(successor_id);
        CREATE INDEX IF NOT EXISTS idx_supersessions_predecessor ON memory_supersessions(predecessor_id);
        """
        try:
            await _postgres_client.execute(ddl)
            logger.info("memory_superseder: PostgreSQL schema verified")
        except Exception as exc:
            logger.warning("memory_superseder: schema init failed: %s", exc)

    def resolve_lineage(self, new_fact: str, existing_facts: List[Dict[str, Any]]) -> Optional[str]:
        """
        Identify if the new fact should supersede any existing ones.
        Returns the memory_id of the fact to be superseded, or None.
        """
        if not existing_facts:
            return None

        # Sort by score/relevance
        sorted_existing = sorted(existing_facts, key=lambda x: x.get("score", 0.0), reverse=True)
        
        # In Phase 55.1, we only supersede the top most relevant fact
        # if it logically contradicts the new one.
        top_fact = sorted_existing[0]
        
        # Lineage is established in the broker's check_contradiction logic.
        # This module will later support more complex 'Merge' logic.
        return top_fact.get("memory_id") or top_fact.get("id")

    def prepare_superseded_metadata(self, predecessor_id: str) -> Dict[str, Any]:
        """
        Return metadata required to mark an entry as superseded.
        """
        return {
            "supersedes": predecessor_id,
            "version_update": True,
            "logical_clock": datetime.now(timezone.utc).timestamp()
        }

# Singleton accessor
_instance: Optional[MemorySuperseder] = None

def get_superseder() -> MemorySuperseder:
    global _instance
    if _instance is None:
        _instance = MemorySuperseder()
    return _instance
