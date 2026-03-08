"""
Agent memory store/recall module for hybrid-coordinator.

Provides store_agent_memory and recall_agent_memory backed by Qdrant.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import memory_manager
    memory_manager.init(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        record_telemetry_fn=record_telemetry_event,
        hybrid_search_fn=hybrid_search,
        tree_search_fn=tree_search,
        memory_collections=MEMORY_COLLECTIONS,
    )
    result = await memory_manager.store_agent_memory("episodic", "summary...")
    result = await memory_manager.recall_agent_memory("query")
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from qdrant_client.models import PointStruct

from config import Config

logger = logging.getLogger("hybrid-coordinator")

LEGACY_MEMORY_TYPE_ALIASES = {
    "fact": "semantic",
    "decision": "procedural",
    "context": "episodic",
}

# Injected from server.py
_qdrant: Optional[Any] = None
_embed: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_hybrid_search: Optional[Callable] = None
_tree_search: Optional[Callable] = None
_memory_collections: Dict[str, str] = {}


def normalize_memory_type(memory_type: str) -> str:
    """Map legacy caller aliases onto canonical memory tiers."""
    normalized = str(memory_type or "").strip().lower()
    return LEGACY_MEMORY_TYPE_ALIASES.get(normalized, normalized)


def coerce_memory_summary(summary: Optional[str], content: Optional[str]) -> str:
    """Prefer explicit summary, but fall back to content for legacy callers."""
    summary_text = str(summary or "").strip()
    if summary_text:
        return summary_text
    return str(content or "").strip()


def init(
    *,
    qdrant_client: Any,
    embed_fn: Callable,
    record_telemetry_fn: Callable,
    hybrid_search_fn: Callable,
    tree_search_fn: Callable,
    memory_collections: Dict[str, str],
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _qdrant, _embed, _record_telemetry, _hybrid_search, _tree_search, _memory_collections
    _qdrant = qdrant_client
    _embed = embed_fn
    _record_telemetry = record_telemetry_fn
    _hybrid_search = hybrid_search_fn
    _tree_search = tree_search_fn
    _memory_collections = memory_collections


async def store_agent_memory(
    memory_type: str,
    summary: str,
    *,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store agent memory in typed collections."""
    if not Config.AI_MEMORY_ENABLED:
        return {"status": "disabled"}
    normalized_type = normalize_memory_type(memory_type)
    normalized_summary = coerce_memory_summary(summary, content)
    if not normalized_summary:
        raise ValueError("summary or content required")
    collection = _memory_collections.get(normalized_type)
    if not collection:
        raise ValueError("memory_type must be episodic|semantic|procedural")
    memory_id = str(uuid4())
    payload = {
        "memory_id": memory_id,
        "memory_type": normalized_type,
        "summary": normalized_summary,
        "content": content or normalized_summary,
        "timestamp": int(datetime.now().timestamp()),
    }
    if metadata:
        payload.update(metadata)
    embedding = await _embed(f"{normalized_type}\n{normalized_summary}\n{content or ''}")
    try:
        _qdrant.upsert(
            collection_name=collection,
            points=[PointStruct(id=memory_id, vector=embedding, payload=payload)],
        )
    except Exception as exc:
        error_text = str(exc)
        if "Vector dimension error" in error_text:
            logger.warning(
                "Agent memory storage disabled due to embedding/collection dimension mismatch",
                extra={
                    "memory_type": normalized_type,
                    "collection": collection,
                    "memory_id": memory_id,
                },
            )
            return {
                "status": "disabled",
                "reason": "embedding_dimension_mismatch",
                "memory_type": normalized_type,
            }
        raise
    _record_telemetry(
        "agent_memory_store",
        {"memory_id": memory_id, "memory_type": normalized_type, "collection": collection},
    )
    return {"status": "stored", "memory_id": memory_id, "memory_type": normalized_type}


async def recall_agent_memory(
    query: str,
    memory_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    retrieval_mode: str = "hybrid",
) -> Dict[str, Any]:
    """Recall memories using hybrid/tree retrieval."""
    if not Config.AI_MEMORY_ENABLED:
        return {"status": "disabled", "results": []}

    requested_types = [normalize_memory_type(item) for item in (memory_types or list(_memory_collections.keys()))]
    collections = [_memory_collections[m] for m in requested_types if m in _memory_collections]
    if not collections:
        return {"status": "ok", "results": []}

    limit_value = max(1, int(limit or Config.AI_MEMORY_MAX_RECALL_ITEMS))
    use_tree = retrieval_mode == "tree" and Config.AI_TREE_SEARCH_ENABLED

    if use_tree:
        search_result = await _tree_search(
            query=query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )
    else:
        search_result = await _hybrid_search(
            query=query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )

    raw_results = search_result.get("combined_results", [])
    memory_rows = []
    for item in raw_results[:limit_value]:
        payload = item.get("payload") or {}
        memory_rows.append(
            {
                "memory_id": payload.get("memory_id") or item.get("id"),
                "memory_type": payload.get("memory_type"),
                "summary": payload.get("summary"),
                "content": payload.get("content"),
                "score": item.get("score"),
                "sources": item.get("sources"),
            }
        )

    _record_telemetry(
        "agent_memory_recall",
        {
            "query": query[:200],
            "results": len(memory_rows),
            "mode": "tree" if use_tree else "hybrid",
            "memory_types": requested_types,
        },
    )
    return {
        "status": "ok",
        "query": query,
        "mode": "tree" if use_tree else "hybrid",
        "results": memory_rows,
    }
