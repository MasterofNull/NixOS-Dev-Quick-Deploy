"""
drift_analyzer.py — Reasoning stability and semantic variance detection (Phase 55.3)

Monitors model output stability by calculating the semantic distance between
current responses and archetypal 'good' responses for a given intent.

Used for Phase 56 homeostasis: automatically downshifting profiles or
triggering self-correction when reasoning drift exceeds a threshold.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Any, Dict, List, Optional
import time

logger = logging.getLogger("hybrid-coordinator")

class DriftAnalyzer:
    """
    Measures semantic divergence in model reasoning.
    """

    def __init__(self, embed_fn: Optional[Any] = None) -> None:
        self._embed = embed_fn
        self._baseline_embeddings: Dict[str, np.ndarray] = {}
        self._recent_scores: List[float] = []

    def set_embed_fn(self, embed_fn: Any) -> None:
        self._embed = embed_fn

    async def compute_drift(self, response_text: str, intent: str) -> Dict[str, Any]:
        """
        Calculate semantic drift score (0.0 = stable, 1.0 = total drift).
        """
        if not self._embed or not response_text:
            return {"drift_score": 0.0, "status": "skipped"}

        # 1. Get embedding for current response
        resp_embed_list = await self._embed(response_text[:1000]) # Sample first 1k chars
        if not resp_embed_list:
            return {"drift_score": 0.0, "status": "error"}
        
        resp_embed = np.array(resp_embed_list)

        # 2. Check if we have a baseline for this intent
        # If not, the first good response becomes the baseline
        if intent not in self._baseline_embeddings:
            self._baseline_embeddings[intent] = resp_embed
            return {"drift_score": 0.0, "status": "baseline_established"}

        baseline = self._baseline_embeddings[intent]
        
        # 3. Calculate Cosine Distance (1 - similarity)
        similarity = np.dot(resp_embed, baseline) / (np.linalg.norm(resp_embed) * np.linalg.norm(baseline))
        drift_score = float(1.0 - max(0, similarity))

        # 4. Update internal tracking
        self._recent_scores.append(drift_score)
        if len(self._recent_scores) > 50:
            self._recent_scores.pop(0)

        # Update Prometheus
        try:
            from metrics import REASONING_DRIFT_SCORE
            REASONING_DRIFT_SCORE.labels(intent=intent).observe(drift_score)
        except (ImportError, Exception):
            pass

        # 5. Determine stability
        # Threshold > 0.4 usually indicates the model is 'hallucinating' or 'looping'
        is_stable = drift_score < 0.4

        return {
            "drift_score": round(drift_score, 4),
            "is_stable": is_stable,
            "intent": intent,
            "mean_drift": round(float(np.mean(self._recent_scores)), 4) if self._recent_scores else 0.0
        }

# Singleton accessor
_analyzer: Optional[DriftAnalyzer] = None

def get_analyzer() -> DriftAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = DriftAnalyzer()
    return _analyzer
