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
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from qdrant_client.models import PointStruct

from config import Config
from rag_reflection import (
    reflect_on_retrieval,
    should_reflect,
    get_reflection_stats,
)
from shared.telemetry_privacy import redact_secrets, scrub_telemetry_payload

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

MAX_MEMORY_SUMMARY_CHARS = 2000
MAX_MEMORY_CONTENT_CHARS = 8000
MAX_MEMORY_METADATA_JSON_CHARS = 12000


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


def _sanitize_memory_text(value: Optional[str], *, field_name: str, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    redacted, detected = redact_secrets(text)
    if detected:
        logger.warning("memory_secret_redacted field=%s secret_types=%s", field_name, ",".join(detected))
    return redacted[:max_chars]


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    scrubbed = scrub_telemetry_payload(metadata)
    try:
        encoded = json.dumps(scrubbed, sort_keys=True)
    except TypeError:
        encoded = json.dumps(scrub_telemetry_payload({"value": str(metadata)}), sort_keys=True)
        scrubbed = json.loads(encoded)["value"]
        return {"value": str(scrubbed)[:MAX_MEMORY_METADATA_JSON_CHARS]}
    if len(encoded) > MAX_MEMORY_METADATA_JSON_CHARS:
        logger.warning("memory_metadata_truncated size=%d", len(encoded))
        return {"truncated_metadata": encoded[:MAX_MEMORY_METADATA_JSON_CHARS]}
    return scrubbed


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
    normalized_summary = _sanitize_memory_text(
        coerce_memory_summary(summary, content),
        field_name="summary",
        max_chars=MAX_MEMORY_SUMMARY_CHARS,
    )
    if not normalized_summary:
        raise ValueError("summary or content required")
    collection = _memory_collections.get(normalized_type)
    if not collection:
        raise ValueError("memory_type must be episodic|semantic|procedural")
    sanitized_content = _sanitize_memory_text(
        content or normalized_summary,
        field_name="content",
        max_chars=MAX_MEMORY_CONTENT_CHARS,
    )
    sanitized_metadata = _sanitize_metadata(metadata)
    memory_id = str(uuid4())
    payload = {
        "memory_id": memory_id,
        "memory_type": normalized_type,
        "summary": normalized_summary,
        "content": sanitized_content,
        "timestamp": int(datetime.now().timestamp()),
    }
    if sanitized_metadata:
        payload.update(sanitized_metadata)
    embedding = await _embed(f"{normalized_type}\n{normalized_summary}\n{sanitized_content}")
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
    sanitized_query = _sanitize_memory_text(query, field_name="query", max_chars=512)

    if use_tree:
        search_result = await _tree_search(
            query=sanitized_query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )
    else:
        search_result = await _hybrid_search(
            query=sanitized_query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )

    raw_results = search_result.get("combined_results", [])

    # Batch 9.1: Reflection loop for RAG quality improvement
    reflection_metadata = None
    if should_reflect(sanitized_query):
        # Helper function for retry
        async def _retry_search(expanded_query: str):
            if use_tree:
                return await _tree_search(
                    query=expanded_query,
                    collections=collections,
                    limit=limit_value,
                    keyword_limit=limit_value,
                    score_threshold=0.6,
                )
            else:
                return await _hybrid_search(
                    query=expanded_query,
                    collections=collections,
                    limit=limit_value,
                    keyword_limit=limit_value,
                    score_threshold=0.6,
                )

        # Apply reflection loop
        final_results, reflection_metadata = await reflect_on_retrieval(
            query=sanitized_query,
            results=raw_results,
            retrieval_func=_retry_search,
            min_confidence=0.6,
            max_retries=2,
        )
        raw_results = final_results

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
            "query": sanitized_query[:200],
            "results": len(memory_rows),
            "mode": "tree" if use_tree else "hybrid",
            "memory_types": requested_types,
            "reflection_applied": reflection_metadata is not None,
            "reflection_retries": reflection_metadata.get("retry_count", 0) if reflection_metadata else 0,
        },
    )

    result = {
        "status": "ok",
        "query": sanitized_query,
        "mode": "tree" if use_tree else "hybrid",
        "results": memory_rows,
    }

    # Include reflection metadata if applied
    if reflection_metadata:
        result["reflection"] = reflection_metadata

    return result
