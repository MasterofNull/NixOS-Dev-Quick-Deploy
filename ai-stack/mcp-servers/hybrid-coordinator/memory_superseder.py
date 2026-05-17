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

class MemorySuperseder:
    """
    Orchestrates memory versioning and conflict resolution.
    """

    def __init__(self) -> None:
        pass

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
