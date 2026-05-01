"""
Reciprocity Tracker — Phase 19: Values Signals

Redis-backed give/receive accounting with a rolling TTL window.
Falls back to in-memory counters if Redis is unavailable.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger("affective-engine")

_TTL_DAYS: int = int(os.environ.get("AFFECTIVE_RECIPROCITY_TTL_DAYS", "30"))
_TTL_SECONDS: int = _TTL_DAYS * 86400

_KEY_PREFIX = "affective:reciprocity"

# In-memory fallback (not persistent, but safe)
_MEM_GIVE: Dict[str, float] = {}
_MEM_RECEIVE: Dict[str, float] = {}


class ReciprocityTracker:
    """Tracks give/receive balance per session.

    Redis keys:
      affective:reciprocity:<session_id>:give    (INCRBYFLOAT)
      affective:reciprocity:<session_id>:receive (INCRBYFLOAT)

    Debt = receive - give. Negative means system owes the user.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._redis_url = (
            redis_url
            or os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
        )
        self._redis: Optional[object] = None

    def _get_redis(self):
        if self._redis is None:
            import redis as _r
            self._redis = _r.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _give_key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}:{session_id}:give"

    def _receive_key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}:{session_id}:receive"

    def record_give(self, session_id: str, value: float = 1.0) -> None:
        """Record that the system provided value to the user."""
        try:
            r = self._get_redis()
            r.incrbyfloat(self._give_key(session_id), value)
            r.expire(self._give_key(session_id), _TTL_SECONDS)
        except Exception:
            _MEM_GIVE[session_id] = _MEM_GIVE.get(session_id, 0.0) + value

    def record_receive(self, session_id: str, value: float = 1.0) -> None:
        """Record that the user provided value to the system (feedback, correction)."""
        try:
            r = self._get_redis()
            r.incrbyfloat(self._receive_key(session_id), value)
            r.expire(self._receive_key(session_id), _TTL_SECONDS)
        except Exception:
            _MEM_RECEIVE[session_id] = _MEM_RECEIVE.get(session_id, 0.0) + value

    def get_debt(self, session_id: str) -> float:
        """Return receive - give. Negative = system owes user."""
        try:
            r = self._get_redis()
            give = float(r.get(self._give_key(session_id)) or 0.0)
            receive = float(r.get(self._receive_key(session_id)) or 0.0)
            return receive - give
        except Exception:
            give = _MEM_GIVE.get(session_id, 0.0)
            receive = _MEM_RECEIVE.get(session_id, 0.0)
            return receive - give
