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

    async def resolve(self, candidates: List[Dict[str, Any]], strategy: str = "best_of_n", task: str = "") -> Dict[str, Any]:
        """
        Apply consensus strategy to a list of candidate results.
        """
        if not candidates:
            return {"status": "error", "reason": "no_candidates"}
        
        if len(candidates) == 1:
            return {**candidates[0], "consensus_score": 1.0, "strategy": "passthrough"}

        if strategy == "majority_vote":
            result = await self._majority_vote(candidates)
        elif strategy == "synthesis":
            return await self._synthesize(candidates, task)
        else:
            # Default: Best-of-N based on confidence/quality
            result = self._best_of_n(candidates)
            
        # Global Homeostasis: If consensus is too low, escalate to Expert Synthesis
        score = result.get("consensus_score", 1.0)
        if score < self._MIN_CONSENSUS_SCORE and strategy != "synthesis":
            logger.warning("consensus_arbiter: low consensus score (%.3f). Escalating to Expert Synthesis.", score)
            # Phase 103: severe divergence (< 0.5) pushed to attention archive so operators
            # can see which tasks produced contradictory agent outputs without synthesis silently burying them.
            if score < 0.5:
                try:
                    from attention_queue import push
                    push(
                        source="consensus-arbiter",
                        severity="medium",
                        autonomy_boundary="auto_ok",
                        title=f"Consensus divergence (score={score:.2f}): {len(candidates)} agents",
                        detail=(
                            f"Agent outputs diverged significantly (consensus_score={score:.3f} < 0.5). "
                            f"Task: {task[:120]}. Escalated to synthesis. "
                            f"Candidates: {len(candidates)}, strategy={strategy}."
                        ),
                        proposed_action=(
                            "Review synthesis output for accuracy. If agents disagreed on facts, "
                            "check which agent's response was correct and seed the correct answer via aq-commit-facts."
                        ),
                    )
                except Exception:
                    pass
            return await self._synthesize(candidates, task)

        return result

    async def _synthesize(self, candidates: List[Dict[str, Any]], task: str) -> Dict[str, Any]:
        """Use the configured synthesis model to merge and resolve agent outputs."""
        try:
            # Import here to avoid circular dependencies.  Default to the local
            # switchboard ingress, which is provisioned in deployed NixOS
            # environments; remote providers require explicit operator config.
            import os
            from core.llm_client import LLMClient
            from core.config import Config

            provider = os.getenv("CONSENSUS_SYNTHESIS_PROVIDER", "local").strip() or "local"
            expert_client = (
                LLMClient(provider="local", base_url=Config.SWITCHBOARD_URL)
                if provider == "local"
                else LLMClient(provider=provider)
            )
            
            cand_text = "\n\n".join([f"Agent {i} Output:\n{c.get('response','')}" for i, c in enumerate(candidates)])
            
            prompt = f"""You are the Team Arbiter. Multiple agents have worked on the following task:
TASK: {task}

Below are their varying outputs. Your goal is to synthesize a single, optimal, and correct response by merging their strengths and resolving any contradictions.

CANDIDATE OUTPUTS:
{cand_text}

Provide the FINAL SYNTHESIZED SOLUTION:"""

            response = await expert_client.create_message(
                prompt=prompt,
                system="You are the Lead Architect. Resolve conflicts and synthesize a perfect solution.",
                temperature=0.2
            )
            
            return {
                "response": response.content,
                "consensus_score": 0.95, # Expert synthesis represents high human-tier confidence
                "consensus_strategy": "model_synthesis",
                "agreement_count": len(candidates),
                "total_candidates": len(candidates)
            }
        except Exception as exc:
            logger.error("consensus_arbiter: expert synthesis failed: %s", exc)
            # Emergency fallback remains explicit so callers can tell synthesis
            # was requested but unavailable in this runtime.
            fallback = self._best_of_n(candidates)
            fallback["consensus_fallback_reason"] = "expert_synthesis_unavailable"
            return fallback

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

def init(embed_fn: Optional[Any] = None) -> ConsensusArbiter:
    """Initialize the process-wide arbiter with runtime dependencies."""
    global _arbiter
    _arbiter = ConsensusArbiter(embed_fn=embed_fn)
    return _arbiter


def get_arbiter() -> ConsensusArbiter:
    global _arbiter
    if _arbiter is None:
        _arbiter = ConsensusArbiter()
    return _arbiter
