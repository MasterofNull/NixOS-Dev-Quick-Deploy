"""
consensus_manager.py — Cross-agent knowledge sharing and fact promotion (Phase 57)

Manages the 'Consensus' layer of the AI OSI model. Ensures that high-confidence
discoveries made by one agent (e.g. Gemini) are promoted to Institutional Memory
where other agents (e.g. Qwen, Codex) can access them.

Concepts:
  - Fact Promotion: Moving volatile session facts to global semantic storage.
  - Verification: Requiring high confidence (0.9+) or cross-agent agreement.
  - Institutional Collection: The 'institutional-knowledge' vector store.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_memory_broker: Optional[Any] = None

def init(broker: Any) -> None:
    global _memory_broker
    _memory_broker = broker
    logger.info("consensus_manager: initialized (Phase 57 Active)")


class ConsensusManager:
    """
    Orchestrates the promotion of facts to Institutional Memory.
    """

    def __init__(self, confidence_threshold: float = 0.9) -> None:
        self._threshold = confidence_threshold
        self._promotion_history: List[Dict[str, Any]] = []

    async def evaluate_for_promotion(self, memory_type: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if a memory entry qualifies for Institutional promotion.
        """
        if memory_type == "semantic" and metadata.get("crystalline") is True:
            # Crystalline facts from Phase 55.2 are high-priority candidates
            return await self.promote(content, metadata, reason="crystalline_distillation")

        confidence = float(metadata.get("confidence", 1.0))
        if confidence >= self._threshold:
            return await self.promote(content, metadata, reason="high_confidence_match")

        return {"status": "pending_consensus", "confidence": confidence}

    async def promote(self, content: str, metadata: Dict[str, Any], reason: str = "consensus") -> Dict[str, Any]:
        """
        Promote a fact to the global 'institutional-knowledge' collection.
        """
        if not _memory_broker:
            return {"status": "error", "reason": "broker_not_initialized"}

        logger.info("consensus: promoting fact to institutional memory. Reason: %s", reason)
        
        # Add institutional metadata
        promo_meta = metadata.copy()
        promo_meta.update({
            "institutional": True,
            "promotion_reason": reason,
            "promotion_date": datetime.now(timezone.utc).isoformat(),
            "original_id": metadata.get("memory_id") or metadata.get("id")
        })

        # Write to semantic store but with 'institutional' flag 
        # (Real implementation might write to a separate Qdrant collection)
        res = await _memory_broker.write(
            memory_type="semantic",
            content=content,
            context=promo_meta,
            source="consensus_manager",
            check_contradictions=True, # Critical for institutional stability
            supersede=True
        )

        if res.get("status") in ["stored", "success", "superseded"]:
            promotion_record = {
                "content": content[:100] + "...",
                "date": promo_meta["promotion_date"],
                "reason": reason
            }
            self._promotion_history.append(promotion_record)
            if len(self._promotion_history) > 50:
                self._promotion_history.pop(0)

            # Update metrics
            try:
                from metrics import INSTITUTIONAL_FACTS_PROMOTED
                INSTITUTIONAL_FACTS_PROMOTED.inc()
            except (ImportError, Exception):
                pass

            return {"status": "promoted", "id": res.get("memory_id")}

        return {"status": "promotion_failed", "detail": res.get("detail")}

    def get_institutional_stats(self) -> Dict[str, Any]:
        return {
            "total_promoted": len(self._promotion_history),
            "recent_promotions": self._promotion_history[-5:],
            "threshold": self._threshold
        }

# Singleton accessor
_manager: Optional[ConsensusManager] = None

def get_manager() -> ConsensusManager:
    global _manager
    if _manager is None:
        _manager = ConsensusManager()
    return _manager
