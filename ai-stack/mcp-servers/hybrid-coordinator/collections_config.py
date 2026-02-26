"""
Qdrant collection schemas and initialization for hybrid-coordinator.

Defines COLLECTIONS, MEMORY_COLLECTIONS, and initialize_collections().

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import collections_config
    COLLECTIONS = collections_config.COLLECTIONS
    MEMORY_COLLECTIONS = collections_config.MEMORY_COLLECTIONS
    await collections_config.initialize_collections(qdrant_client)
"""

import logging
from typing import Any, Dict, Optional

from config import Config
from qdrant_client.models import (
    CollectionInfo,
    Distance,
    HnswConfigDiff,
    VectorParams,
)

logger = logging.getLogger("hybrid-coordinator")

COLLECTIONS: Dict[str, Any] = {
    "codebase-context": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "file_path": "string",
            "code_snippet": "text",
            "language": "string",
            "framework": "string",
            "purpose": "text",
            "last_accessed": "integer",
            "access_count": "integer",
            "success_rate": "float",
        },
    },
    "skills-patterns": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "skill_name": "string",
            "description": "text",
            "usage_pattern": "text",
            "success_examples": "array",
            "failure_examples": "array",
            "prerequisites": "array",
            "related_skills": "array",
            "value_score": "float",
            "last_updated": "integer",
        },
    },
    "error-solutions": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "error_message": "text",
            "error_type": "string",
            "context": "text",
            "solution": "text",
            "solution_verified": "boolean",
            "success_count": "integer",
            "failure_count": "integer",
            "first_seen": "integer",
            "last_used": "integer",
            "confidence_score": "float",
        },
    },
    "interaction-history": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "query": "text",
            "agent_type": "string",
            "model_used": "string",
            "context_provided": "array",
            "response": "text",
            "outcome": "string",
            "user_feedback": "integer",
            "tokens_used": "integer",
            "latency_ms": "integer",
            "timestamp": "integer",
            "value_score": "float",
        },
    },
    "best-practices": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "category": "string",
            "title": "string",
            "description": "text",
            "examples": "array",
            "anti_patterns": "array",
            "references": "array",
            "endorsement_count": "integer",
            "last_validated": "integer",
        },
    },
    "learning-feedback": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "feedback_id": "string",
            "interaction_id": "string",
            "query": "text",
            "original_response": "text",
            "correction": "text",
            "rating": "integer",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-episodic": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "query": "text",
            "response": "text",
            "outcome": "string",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-semantic": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "content": "text",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-procedural": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "procedure": "text",
            "trigger": "text",
            "tags": "array",
            "timestamp": "integer",
        },
    },
}

MEMORY_COLLECTIONS: Dict[str, str] = {
    "episodic": "agent-memory-episodic",
    "semantic": "agent-memory-semantic",
    "procedural": "agent-memory-procedural",
}


async def initialize_collections(qdrant_client: Any) -> None:
    """Initialize Qdrant collections if they don't exist."""

    def _extract_vector_size(info: CollectionInfo) -> Optional[int]:
        try:
            vectors = info.config.params.vectors
            if hasattr(vectors, "size"):
                return int(vectors.size)
            if isinstance(vectors, dict) and vectors:
                first = next(iter(vectors.values()))
                if hasattr(first, "size"):
                    return int(first.size)
                if isinstance(first, dict) and "size" in first:
                    return int(first["size"])
        except Exception:
            return None
        return None

    for collection_name, schema in COLLECTIONS.items():
        try:
            collections = qdrant_client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                logger.info(f"Creating collection: {collection_name}")
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=schema["vector_size"],
                        distance=schema["distance"],
                        hnsw_config=HnswConfigDiff(
                            m=Config.QDRANT_HNSW_M,
                            ef_construct=Config.QDRANT_HNSW_EF_CONSTRUCT,
                            full_scan_threshold=Config.QDRANT_HNSW_FULL_SCAN_THRESHOLD,
                        ),
                    ),
                )
                logger.info(f"✓ Collection created: {collection_name}")
            else:
                info = qdrant_client.get_collection(collection_name)
                current_size = _extract_vector_size(info)
                expected_size = schema["vector_size"]
                points_count = getattr(info, "points_count", 0) or 0
                if current_size is not None and current_size != expected_size:
                    if points_count > 0:
                        logger.error(
                            "Collection dimension mismatch",
                            extra={
                                "collection": collection_name,
                                "current": current_size,
                                "expected": expected_size,
                                "points": points_count,
                            },
                        )
                    else:
                        logger.warning(
                            "Recreating collection due to dimension mismatch",
                            extra={
                                "collection": collection_name,
                                "current": current_size,
                                "expected": expected_size,
                            },
                        )
                        qdrant_client.delete_collection(collection_name=collection_name)
                        qdrant_client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=expected_size,
                                distance=schema["distance"],
                                hnsw_config=HnswConfigDiff(
                                    m=Config.QDRANT_HNSW_M,
                                    ef_construct=Config.QDRANT_HNSW_EF_CONSTRUCT,
                                    full_scan_threshold=Config.QDRANT_HNSW_FULL_SCAN_THRESHOLD,
                                ),
                            ),
                        )
                        logger.info(f"✓ Collection recreated: {collection_name}")
                else:
                    logger.info(f"✓ Collection exists: {collection_name}")

        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")
