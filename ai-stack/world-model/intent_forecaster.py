"""
Intent Forecaster — Phase 20: World Model Predictive Warming

Predicts likely next queries from three signal sources:
  1. Recency — last 3 queries in this session (highest weight)
  2. Pattern — follow-on predictions from PatternIndex (medium weight)
  3. Time-of-day — most frequent queries at this hour (fallback)

Returns empty list gracefully if no data is available.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("world-model")


@dataclass
class ForecastResult:
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


class IntentForecaster:
    """Combines recency, pattern, and time-of-day signals into ranked predictions."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        pg_dsn: Optional[str] = None,
    ) -> None:
        self._redis_url = redis_url or os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
        self._pg_dsn = pg_dsn  # passed through to PatternIndex if provided

    def get_recent_queries(self, session_id: Optional[str], limit: int = 3) -> List[str]:
        """Fetch last N queries for session from Redis multi-turn context."""
        if not session_id:
            return []
        try:
            import redis as _r
            client = _r.from_url(self._redis_url, decode_responses=True)
            raw = client.lrange(f"multi_turn:{session_id}", -limit, -1)
            queries = []
            for entry in raw:
                try:
                    msg = json.loads(entry)
                    if msg.get("role") == "user":
                        queries.append(msg.get("content", ""))
                except (json.JSONDecodeError, TypeError):
                    pass
            return [q for q in queries if q]
        except Exception as exc:
            logger.debug("get_recent_queries failed (non-fatal): %s", exc)
            return []

    def forecast(self, session_id: Optional[str] = None) -> ForecastResult:
        """Build a ranked list of predicted next queries."""
        predictions: List[Dict[str, Any]] = []
        sources: List[str] = []

        try:
            from pattern_index import PatternIndex, _query_hash  # noqa: PLC0415
            pi = PatternIndex(dsn=self._pg_dsn)

            # Source 1: recency
            recent = self.get_recent_queries(session_id)
            if recent:
                current_hash = _query_hash(recent[-1])
                pattern_preds = pi.predict_next(current_hash)
                for summary, prob in pattern_preds:
                    predictions.append({
                        "query": summary,
                        "confidence": round(prob * 0.8, 3),
                        "source": "pattern",
                    })
                if pattern_preds:
                    sources.append("recency")
                    sources.append("pattern")

            # Source 2: time-of-day fallback if not enough predictions
            if len(predictions) < 3:
                tod_preds = pi.predict_next("", top_k=3 - len(predictions))
                for summary, prob in tod_preds:
                    if not any(p["query"] == summary for p in predictions):
                        predictions.append({
                            "query": summary,
                            "confidence": round(prob * 0.4, 3),
                            "source": "time_of_day",
                        })
                if tod_preds and "time_of_day" not in sources:
                    sources.append("time_of_day")

        except Exception as exc:
            logger.debug("forecast failed (non-fatal): %s", exc)

        return ForecastResult(
            predictions=predictions[:3],
            sources=sources,
        )
