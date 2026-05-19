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

import memory_superseder
import consensus_manager

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Valid memory types — matches Qdrant collection suffixes in memory_manager.py
# ---------------------------------------------------------------------------
MEMORY_TYPES = frozenset({"working", "episodic", "semantic", "procedural", "error_solutions", "interaction_history"})

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
    _broker = MemoryBroker(
        store_fn=store_fn, 
        recall_fn=recall_fn,
        superseder=memory_superseder.get_superseder(),
        consensus_manager=consensus_manager.get_manager()
    )
    consensus_manager.init(broker=_broker)
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

    def __init__(self, store_fn: Callable, recall_fn: Callable, superseder: Optional[Any] = None, consensus_manager: Optional[Any] = None) -> None:
        self._store = store_fn
        self._recall = recall_fn
        self._superseder = superseder
        self._consensus = consensus_manager

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
        check_contradictions: bool = True,
        supersede: bool = True,
        promote: bool = True,
    ) -> Dict[str, Any]:
        """
        Write a memory entry with automatic contradiction detection and supersession.
        """
        _validate_type(memory_type)

        superseded_id = None
        # Phase 55.1 — Memory Supersession (Logical Versioning)
        if check_contradictions:
            existing = await self.read(memory_type, content, top_k=2, include_superseded=True)
            for entry in existing:
                if self.check_contradiction(entry.get("content", ""), content):
                    if supersede and self._superseder:
                        superseded_id = self._superseder.resolve_lineage(content, [entry])
                        logger.info(
                            "memory_broker.superseding: old_id=%s content=%r -> new_content=%r",
                            superseded_id, entry.get("content"), content
                        )
                        break # Only supersede the most relevant match
                    else:
                        logger.warning(
                            "memory_broker.contradiction detected type=%s content=%r existing=%r",
                            memory_type, content, entry.get("content")
                        )
                        return {
                            "status": "contradiction_blocked",
                            "memory_type": memory_type,
                            "conflicting_entry": entry.get("id"),
                            "reason": "New entry contradicts existing memory"
                        }

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
        
        if superseded_id and self._superseder:
            metadata.update(self._superseder.prepare_superseded_metadata(superseded_id))
            
        if context:
            metadata.update(context)

        try:
            start_time = time.perf_counter()
            result = await asyncio.wait_for(
                self._store(
                    memory_type=memory_type,
                    summary=content,
                    content=content,
                    metadata=metadata,
                ),
                timeout=8.0,
            )
            latency = time.perf_counter() - start_time
            logger.debug(
                "memory_broker.write type=%s len=%d id=%s supersedes=%s",
                memory_type, len(content), result.get("memory_id", "?"), superseded_id
            )
            status = "superseded" if superseded_id else "success"
            
            if superseded_id:
                try:
                    from metrics import MEMORY_SUPERSESSIONS_TOTAL
                    MEMORY_SUPERSESSIONS_TOTAL.labels(memory_type=memory_type).inc()
                except (ImportError, Exception):
                    pass

            _record_broker_metrics("write", memory_type, status, latency)
            
            # Phase 57 — Global Consensus: Evaluate for Institutional Promotion
            if result.get("status") in ["stored", "success"] and promote and self._consensus:
                # Do not re-promote institutional facts to avoid infinite loops
                if not metadata.get("institutional"):
                    asyncio.create_task(self._consensus.evaluate_for_promotion(
                        memory_type=memory_type,
                        content=content,
                        metadata=metadata
                    ))

            return result
        except asyncio.TimeoutError:
            logger.warning("memory_broker.write timeout type=%s", memory_type)
            _record_broker_metrics("write", memory_type, "timeout", 8.0)
            return {"status": "timeout", "memory_type": memory_type}
        except Exception as exc:
            logger.warning("memory_broker.write error type=%s exc=%s", memory_type, exc)
            _record_broker_metrics("write", memory_type, "error", 0.0)
            return {"status": "error", "detail": str(exc), "memory_type": memory_type}

    async def read(
        self,
        memory_type: str,
        query: str,
        *,
        top_k: int = 5,
        include_expired: bool = False,
        include_superseded: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries relevant to query.

        Filters out temporally expired entries and superseded facts.

        Returns:
            List of result dicts (content, score, metadata, valid_until)
        """
        _validate_type(memory_type)

        try:
            start_time = time.perf_counter()
            raw = await asyncio.wait_for(
                self._recall(
                    query=query,
                    memory_types=[memory_type],
                    limit=top_k * 2,   # extra for filtering
                    retrieval_mode="hybrid",
                ),
                timeout=5.0,
            )
            latency = time.perf_counter() - start_time
            _record_broker_metrics("read", memory_type, "success", latency)
        except asyncio.TimeoutError:
            logger.warning("memory_broker.read timeout type=%s", memory_type)
            _record_broker_metrics("read", memory_type, "timeout", 5.0)
            return []
        except Exception as exc:
            logger.warning("memory_broker.read error type=%s exc=%s", memory_type, exc)
            _record_broker_metrics("read", memory_type, "error", 0.0)
            return []

        rows = raw.get("results", []) if isinstance(raw, dict) else []
        
        # 1. Temporal Filter
        if not include_expired:
            rows = [r for r in rows if not _is_expired(r)]
            
        # 2. Supersession Filter (Phase 55.1)
        if not include_superseded:
            # Map of ID -> Row for quick lookup
            row_map = { (r.get("memory_id") or r.get("id")): r for r in rows if (r.get("memory_id") or r.get("id")) }
            superseded_ids = set()
            for r in rows:
                meta = r.get("metadata") or {}
                sid = meta.get("supersedes")
                if sid:
                    superseded_ids.add(sid)
            
            rows = [r for r in rows if (r.get("memory_id") or r.get("id")) not in superseded_ids]

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
            if (word_a in e_lower and word_b in c_lower) or (word_b in e_lower and word_a in c_lower):
                try:
                    from metrics import MEMORY_CONTRADICTIONS_DETECTED
                    MEMORY_CONTRADICTIONS_DETECTED.labels(memory_type="unknown").inc()
                except (ImportError, Exception):
                    pass
                return True
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_broker_metrics(operation: str, memory_type: str, status: str, latency: float) -> None:
    """Record Memory Broker metrics to Prometheus."""
    try:
        from metrics import MEMORY_BROKER_OPERATIONS, MEMORY_BROKER_LATENCY
        MEMORY_BROKER_OPERATIONS.labels(
            operation=operation,
            memory_type=memory_type,
            status=status
        ).inc()
        if status == "success" and latency > 0:
            MEMORY_BROKER_LATENCY.labels(
                operation=operation,
                memory_type=memory_type
            ).observe(latency)
    except (ImportError, Exception):
        pass


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
