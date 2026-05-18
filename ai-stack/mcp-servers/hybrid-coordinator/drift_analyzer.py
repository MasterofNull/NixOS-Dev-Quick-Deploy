"""
drift_analyzer.py — Reasoning stability and semantic variance detection (Phase 55.3)

Unified module supporting both:
1. Live Compute: Real-time semantic drift between response and baseline prototypes.
2. Trend Compute: Historical drift analysis over SQL query traces.

Used for Phase 56 homeostasis: automatically downshifting profiles or
triggering self-correction when reasoning drift exceeds a threshold.
"""

from __future__ import annotations

import json
import logging
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
from datetime import datetime, timezone
from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

DEFAULT_DRIFT_THRESHOLD = 0.4
_POLICY_PATH = Path(__file__).resolve().parents[4] / "config" / "runtime-budget-policy.json"

def _load_threshold() -> float:
    try:
        if _POLICY_PATH.exists():
            with _POLICY_PATH.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            return float(payload.get("drift_alert_threshold", DEFAULT_DRIFT_THRESHOLD))
    except Exception:
        pass
    return DEFAULT_DRIFT_THRESHOLD


class DriftAnalyzer:
    """
    Measures semantic divergence in model reasoning.
    """

    def __init__(
        self,
        postgres_client: Optional[Any] = None,
        embed_fn: Optional[Any] = None,
        threshold: Optional[float] = None,
    ) -> None:
        self._pg = postgres_client
        self._embed = embed_fn
        self._threshold = float(threshold) if threshold is not None else _load_threshold()
        self._baseline_embeddings: Dict[str, np.ndarray] = {}
        self._recent_scores: List[float] = []
        self._schema_ready = False

    def set_embed_fn(self, embed_fn: Any) -> None:
        self._embed = embed_fn

    async def ensure_schema(self) -> None:
        """Create reasoning drift table if it doesn't exist."""
        if self._schema_ready or self._pg is None:
            return

        ddl = """
        CREATE TABLE IF NOT EXISTS reasoning_drifts (
            id SERIAL PRIMARY KEY,
            intent TEXT NOT NULL,
            drift_score FLOAT NOT NULL,
            is_stable BOOLEAN NOT NULL,
            recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_drifts_intent ON reasoning_drifts(intent);
        """
        try:
            await self._pg.execute(ddl)
            self._schema_ready = True
            logger.info("drift_analyzer: PostgreSQL schema verified")
        except Exception as exc:
            logger.warning("drift_analyzer: schema init failed: %s", exc)

    async def compute_live_drift(self, response_text: str, intent: str) -> Dict[str, Any]:
        """
        Calculate semantic drift for the CURRENT response (Phase 55.3 - Level 6).
        """
        if not self._embed or not response_text:
            return {"drift_score": 0.0, "status": "skipped"}

        # 1. Get embedding for current response
        resp_embed_list = await self._embed(response_text[:1000])
        if not resp_embed_list:
            return {"drift_score": 0.0, "status": "error"}
        
        resp_embed = np.array(resp_embed_list)

        # 2. Baseline Sync
        if intent not in self._baseline_embeddings:
            self._baseline_embeddings[intent] = resp_embed
            return {"drift_score": 0.0, "status": "baseline_established"}

        baseline = self._baseline_embeddings[intent]
        
        # 3. Calculate Cosine Distance
        similarity = np.dot(resp_embed, baseline) / (np.linalg.norm(resp_embed) * np.linalg.norm(baseline))
        drift_score = float(1.0 - max(0, similarity))

        # 4. Update Prometheus
        try:
            from metrics import REASONING_DRIFT_SCORE
            REASONING_DRIFT_SCORE.labels(intent=intent).observe(drift_score)
        except (ImportError, Exception):
            pass

        # 5. Determine stability
        is_stable = drift_score < self._threshold

        return {
            "drift_score": round(drift_score, 4),
            "is_stable": is_stable,
            "intent": intent,
            "threshold": self._threshold
        }

    async def compute_trend_drift(self, window: int = 20) -> Dict[str, Any]:
        """
        Calculate drift based on SQL TRACE HISTORY (Teammate Logic).
        """
        window = max(2, min(int(window or 20), 200))
        if self._pg is None:
            return {
                "drift_score": None,
                "error": "postgres_unavailable",
                "alert_triggered": False,
            }

        rows = await self._pg.fetch_all(
            """
            SELECT intent, retrieval_hits, total_ms
            FROM query_traces
            ORDER BY trace_at DESC
            LIMIT %s
            """,
            window,
        )
        if len(rows) < 2:
            return {
                "drift_score": 0.0,
                "window_size": len(rows),
                "threshold": self._threshold,
                "alert_triggered": False,
                "breakdown": {"intent_flip_rate": 0.0, "latency_trend": 0.0},
            }

        # Simplified trend logic
        latencies = [float(r["total_ms"]) for r in rows]
        latency_trend = (latencies[0] - latencies[-1]) / max(latencies[-1], 1.0)
        intents = [str(r.get("intent") or "") for r in rows]
        intent_flips = sum(1 for prev, curr in zip(intents, intents[1:]) if prev != curr)
        intent_flip_rate = intent_flips / max(len(intents) - 1, 1)
        drift_score = round(abs(latency_trend), 3)
        
        return {
            "drift_score": drift_score,
            "window_size": len(rows),
            "threshold": self._threshold,
            "alert_triggered": drift_score >= self._threshold,
            "breakdown": {
                "intent_flip_rate": round(intent_flip_rate, 3),
                "latency_trend": round(latency_trend, 3),
            },
        }

    async def compute_drift(self, window: int = 20) -> Dict[str, Any]:
        """Backward-compatible alias for historical callers/tests."""
        return await self.compute_trend_drift(window=window)

# Singleton accessor
_analyzer = DriftAnalyzer()

def init(postgres_client: Optional[Any] = None) -> None:
    global _analyzer
    _analyzer = DriftAnalyzer(postgres_client=postgres_client)
    logger.info("drift_analyzer: initialized (Unified Mode Active)")

def get_analyzer() -> DriftAnalyzer:
    return _analyzer

async def handle_get_drift(request: web.Request) -> web.Response:
    try:
        window = int(request.query.get("window", "20"))
        return web.json_response(await _analyzer.compute_trend_drift(window=window))
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/api/traces/drift", handle_get_drift)
