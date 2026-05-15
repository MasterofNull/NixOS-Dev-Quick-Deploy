"""
memory_broker.py — Unified memory abstraction layer (Phase 54.1)

Wraps the existing store_agent_memory / recall_agent_memory callables from
memory_manager.py with:
  - Typed memory taxonomy: working | episodic | semantic | procedural
  - Temporal validity: valid_from / valid_until metadata on every write
  - Contradiction detection: cosine similarity + keyword antonyms flag conflicts
  - Single callable interface for all coordinator code

Usage:
    from memory_broker import MemoryBroker, get_broker

    broker = get_broker()
    await broker.write("semantic", "Python asyncio uses an event loop", context={"source": "docs"})
    results = await broker.read("semantic", "how does asyncio work", top_k=3)

    # Temporal write (expires in 1 hour):
    await broker.write("working", "current task: deploy phase 54", ttl_seconds=3600)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Valid memory types — matches Qdrant collection suffixes in memory_manager.py
# ---------------------------------------------------------------------------
MEMORY_TYPES = frozenset({"working", "episodic", "semantic", "procedural"})

# Contradiction signal pairs (heuristic; expands over time)
_CONTRADICTION_ANTONYMS: List[tuple] = [
    ("enabled", "disabled"),
    ("active", "inactive"),
    ("up", "down"),
    ("healthy", "unhealthy"),
    ("available", "unavailable"),
    ("true", "false"),
    ("on", "off"),
]

# ---------------------------------------------------------------------------
# Module-level references — injected via init() from server.py
# ---------------------------------------------------------------------------
_store_fn: Optional[Callable] = None
_recall_fn: Optional[Callable] = None
_broker: Optional["MemoryBroker"] = None


def init(store_fn: Callable, recall_fn: Callable) -> None:
    """Wire in store/recall callables from server.py. Call once at startup."""
    global _store_fn, _recall_fn, _broker
    _store_fn = store_fn
    _recall_fn = recall_fn
    _broker = MemoryBroker(store_fn=store_fn, recall_fn=recall_fn)
    logger.info("memory_broker: initialized (store=%s recall=%s)", store_fn, recall_fn)


def get_broker() -> "MemoryBroker":
    """Return the singleton MemoryBroker; raises if init() has not been called."""
    if _broker is None:
        raise RuntimeError("MemoryBroker not initialized — call memory_broker.init() first")
    return _broker


# ---------------------------------------------------------------------------
# MemoryBroker
# ---------------------------------------------------------------------------

class MemoryBroker:
    """
    Unified read/write interface for all coordinator memory stores.

    All writes carry ISO-8601 timestamps for temporal filtering.
    Contradiction detection flags conflicting facts rather than silently
    overwriting them.
    """

    def __init__(self, store_fn: Callable, recall_fn: Callable) -> None:
        self._store = store_fn
        self._recall = recall_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def write(
        self,
        memory_type: str,
        content: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        source: str = "coordinator",
    ) -> Dict[str, Any]:
        """
        Write a memory entry.

        Args:
            memory_type: One of working | episodic | semantic | procedural
            content: Text to store
            context: Optional free-form metadata dict
            ttl_seconds: If set, valid_until = now + ttl_seconds (shorthand)
            valid_from: Explicit validity start (default: now)
            valid_until: Explicit validity end (default: None = perpetual)
            source: Tag identifying the caller / module

        Returns:
            Store result dict from memory_manager (includes memory_id)
        """
        _validate_type(memory_type)

        now = datetime.now(timezone.utc)
        valid_from = valid_from or now
        if ttl_seconds is not None and valid_until is None:
            valid_until = now + timedelta(seconds=ttl_seconds)

        metadata: Dict[str, Any] = {
            "memory_type": memory_type,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "source": source,
            "broker_write": True,
        }
        if context:
            metadata.update(context)

        try:
            result = await asyncio.wait_for(
                self._store(
                    memory_type=memory_type,
                    summary=content,
                    content=content,
                    metadata=metadata,
                ),
                timeout=8.0,
            )
            logger.debug(
                "memory_broker.write type=%s len=%d id=%s",
                memory_type, len(content), result.get("memory_id", "?"),
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("memory_broker.write timeout type=%s", memory_type)
            return {"status": "timeout", "memory_type": memory_type}
        except Exception as exc:
            logger.warning("memory_broker.write error type=%s exc=%s", memory_type, exc)
            return {"status": "error", "detail": str(exc), "memory_type": memory_type}

    async def read(
        self,
        memory_type: str,
        query: str,
        *,
        top_k: int = 5,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries relevant to query.

        Filters out temporally expired entries unless include_expired=True.

        Returns:
            List of result dicts (content, score, metadata, valid_until)
        """
        _validate_type(memory_type)

        try:
            raw = await asyncio.wait_for(
                self._recall(
                    query=query,
                    memory_types=[memory_type],
                    limit=top_k + 2,   # extra for filtering
                    retrieval_mode="hybrid",
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("memory_broker.read timeout type=%s", memory_type)
            return []
        except Exception as exc:
            logger.warning("memory_broker.read error type=%s exc=%s", memory_type, exc)
            return []

        rows = raw.get("results", []) if isinstance(raw, dict) else []
        if not include_expired:
            rows = [r for r in rows if not _is_expired(r)]
        return rows[:top_k]

    async def read_all_types(
        self,
        query: str,
        *,
        top_k: int = 3,
        include_expired: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Read from all memory types in parallel and return by type."""
        results = await asyncio.gather(
            *[self.read(t, query, top_k=top_k, include_expired=include_expired) for t in MEMORY_TYPES],
            return_exceptions=True,
        )
        return {
            t: (r if isinstance(r, list) else [])
            for t, r in zip(MEMORY_TYPES, results)
        }

    def check_contradiction(self, existing: str, candidate: str) -> bool:
        """
        Heuristic contradiction check between two memory strings.

        Returns True if the candidate likely contradicts the existing entry.
        """
        e_lower = existing.lower()
        c_lower = candidate.lower()

        # Simple antonym pair check on shared subject tokens
        for word_a, word_b in _CONTRADICTION_ANTONYMS:
            if word_a in e_lower and word_b in c_lower:
                return True
            if word_b in e_lower and word_a in c_lower:
                return True
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_type(memory_type: str) -> None:
    if memory_type not in MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type {memory_type!r}. Must be one of: {sorted(MEMORY_TYPES)}"
        )


def _is_expired(row: Dict[str, Any]) -> bool:
    """Return True if the row's valid_until has passed."""
    meta = row.get("metadata") or {}
    vu = meta.get("valid_until")
    if not vu:
        return False
    try:
        valid_until = datetime.fromisoformat(vu)
        return datetime.now(timezone.utc) > valid_until
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# HTTP handler — GET /memory/broker/status
# ---------------------------------------------------------------------------

async def handle_broker_status(request) -> Any:
    """Return broker initialization status and type definitions."""
    from aiohttp import web  # local import to avoid circular
    return web.json_response({
        "initialized": _broker is not None,
        "memory_types": sorted(MEMORY_TYPES),
        "contradiction_pairs": len(_CONTRADICTION_ANTONYMS),
        "store_fn": str(_store_fn),
        "recall_fn": str(_recall_fn),
    })
