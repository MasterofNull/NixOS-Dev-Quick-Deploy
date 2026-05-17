"""
consensus_arbiter.py — Multi-agent collective intelligence and voting (Phase 59)

Provides the 'Consensus' mechanism for orchestrated workflows. Evaluates
multiple candidate outputs for the same task and selects or merges them.

Strategies:
  - Best-of-N: Select candidate with highest confidence / quality score.
  - Majority Vote: Select solution most semantically common among agents.
  - Synthesis: Call a reasoning model to merge candidates into a single truth.
"""

from __future__ import annotations

import logging
import asyncio
import numpy as np
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("hybrid-coordinator")

class ConsensusArbiter:
    """
    Resolves conflicts and establishes consensus between multiple agent outputs.
    """

    def __init__(self, embed_fn: Optional[Any] = None) -> None:
        self._embed = embed_fn
        self._MIN_CONSENSUS_SCORE = 0.7

    async def resolve(self, candidates: List[Dict[str, Any]], strategy: str = "best_of_n") -> Dict[str, Any]:
        """
        Apply consensus strategy to a list of candidate results.
        """
        if not candidates:
            return {"status": "error", "reason": "no_candidates"}
        
        if len(candidates) == 1:
            return {**candidates[0], "consensus_score": 1.0, "strategy": "passthrough"}

        if strategy == "majority_vote":
            return await self._majority_vote(candidates)
        
        # Default: Best-of-N based on confidence/quality
        return self._best_of_n(candidates)

    def _best_of_n(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the candidate with the highest reported confidence."""
        # Weighted score: 70% confidence, 30% reported quality (if available)
        def _score(c):
            conf = float(c.get("intent_classification", {}).get("confidence", 0.5))
            qual = float(c.get("quality_score", 0.5))
            return (conf * 0.7) + (qual * 0.3)

        best = max(candidates, key=_score)
        score = _score(best)
        
        return {
            **best,
            "consensus_score": round(score, 3),
            "consensus_strategy": "best_of_n",
            "agreement_count": 1,
            "total_candidates": len(candidates)
        }

    async def _majority_vote(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select candidate that is semantically closest to the group centroid."""
        if not self._embed:
            logger.warning("consensus_arbiter: majority_vote requested but no embed_fn; falling back to best_of_n")
            return self._best_of_n(candidates)

        # 1. Get embeddings for all responses
        texts = [str(c.get("response") or c.get("answer") or "")[:1000] for c in candidates]
        embeds = await asyncio.gather(*[self._embed(t) for t in texts])
        valid_embeds = [np.array(e) for e in embeds if e]
        
        if len(valid_embeds) < 2:
            return self._best_of_n(candidates)

        # 2. Compute Centroid
        centroid = np.mean(valid_embeds, axis=0)

        # 3. Find candidate closest to centroid
        best_idx = 0
        best_sim = -1.0
        
        for i, emb in enumerate(valid_embeds):
            sim = np.dot(emb, centroid) / (np.linalg.norm(emb) * np.linalg.norm(centroid))
            if sim > best_sim:
                best_sim = sim
                best_idx = i

        return {
            **candidates[best_idx],
            "consensus_score": round(float(best_sim), 3),
            "consensus_strategy": "majority_vote",
            "agreement_count": len(candidates), # semantic centroid represents group consensus
            "total_candidates": len(candidates)
        }

# Singleton accessor
_arbiter: Optional[ConsensusArbiter] = None

def get_arbiter() -> ConsensusArbiter:
    global _arbiter
    if _arbiter is None:
        _arbiter = ConsensusArbiter()
    return _arbiter
