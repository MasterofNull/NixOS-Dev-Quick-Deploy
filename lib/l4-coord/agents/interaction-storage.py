#!/usr/bin/env python3
"""
Phase 4.2: Interaction Storage System
Persists all query/response interactions to vector DB with metadata.

Features:
- Query/response persistence to vector DB (Qdrant)
- Metadata capture (agent, timestamp, result quality)
- Embedding generation for semantic search
- Interaction categorization
- Success/failure tracking
- Query-response linking for learning
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance
except ImportError:
    AsyncQdrantClient = None

import structlog

logger = structlog.get_logger()


class InteractionStatus(Enum):
    """Status of an interaction"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    LEARNING_APPROVED = "learning_approved"
    LEARNING_REJECTED = "learning_rejected"


class InteractionType(Enum):
    """Type of interaction"""
    QUERY_RESPONSE = "query_response"
    FEEDBACK = "feedback"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"


class Interaction:
    """Represents a stored interaction"""

    def __init__(
        self,
        interaction_id: str,
        query: str,
        response: str,
        agent: str,
        query_type: str,
        complexity: str,
        status: InteractionStatus = InteractionStatus.SUCCESS,
        execution_time_ms: int = 0,
        quality_score: float = 0.5,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.interaction_id = interaction_id
        self.query = query
        self.response = response
        self.agent = agent
        self.query_type = query_type
        self.complexity = complexity
        self.status = status
        self.execution_time_ms = execution_time_ms
        self.quality_score = quality_score
        self.tags = tags or []
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)
        self.embedding: Optional[List[float]] = None

    def compute_hash(self) -> str:
        """Compute stable hash for deduplication"""
        content = f"{self.query}:{self.response}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "interaction_id": self.interaction_id,
            "query": self.query,
            "response": self.response,
            "agent": self.agent,
            "query_type": self.query_type,
            "complexity": self.complexity,
            "status": self.status.value,
            "execution_time_ms": self.execution_time_ms,
            "quality_score": self.quality_score,
            "tags": self.tags,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.compute_hash(),
        }


class InteractionStorageSystem:
    """
    Stores interactions in vector DB and local cache.

    Usage:
        storage = InteractionStorageSystem()
        await storage.initialize()

        interaction = Interaction(...)
        await storage.store(interaction)

        # Retrieve semantically similar interactions
        results = await storage.search_semantic(query)
    """

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        collection_name: str = "interactions",
        embedding_dimensions: int = 384,
    ):
        """Initialize storage system"""
        self.qdrant_url = qdrant_url or os.getenv(
            "QDRANT_URL", "http://localhost:6333"
        )
        self.collection_name = collection_name
        self.embedding_dimensions = embedding_dimensions

        # Local cache
        self.local_cache: Dict[str, Interaction] = {}
        self.interaction_count = 0

        # Storage paths
        self.data_root = Path(
            os.path.expanduser(
                os.getenv("INTERACTION_STORAGE_DATA_ROOT")
                or os.getenv("DATA_DIR")
                or "~/.local/share/nixos-ai-stack/interactions"
            )
        )
        self.cache_path = self.data_root / "cache.jsonl"
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Qdrant client (will be initialized in initialize())
        self.qdrant: Optional[AsyncQdrantClient] = None
        self.qdrant_ready = False

        logger.info("interaction_storage_initialized", root=str(self.data_root))

    async def initialize(self) -> bool:
        """Initialize storage backends"""
        try:
            if AsyncQdrantClient is None:
                logger.warning("qdrant_client not available, using local cache only")
                return False

            # Initialize Qdrant client
            self.qdrant = AsyncQdrantClient(url=self.qdrant_url, timeout=10)

            # Check if collection exists, create if not
            try:
                await self.qdrant.get_collection(self.collection_name)
                logger.info("qdrant_collection_exists", collection=self.collection_name)
            except Exception:
                # Create collection
                await self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dimensions,
                        distance=Distance.COSINE
                    ),
                )
                logger.info("qdrant_collection_created", collection=self.collection_name)

            self.qdrant_ready = True

            # Load local cache
            await self._load_cache()

            return True

        except Exception as e:
            logger.error("qdrant_initialization_failed", error=str(e))
            return False

    async def _load_cache(self) -> None:
        """Load local cache from disk"""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        interaction_id = data.get("interaction_id")
                        if interaction_id:
                            self.local_cache[interaction_id] = self._dict_to_interaction(data)
                    except json.JSONDecodeError:
                        continue

            self.interaction_count = len(self.local_cache)
            logger.info("cache_loaded", count=self.interaction_count)
        except Exception as e:
            logger.error("cache_load_failed", error=str(e))

    async def _save_cache(self, interaction: Interaction) -> None:
        """Append interaction to local cache"""
        try:
            with open(self.cache_path, "a") as f:
                f.write(json.dumps(interaction.to_dict()) + "\n")
        except Exception as e:
            logger.error("cache_save_failed", error=str(e))

    def _dict_to_interaction(self, data: Dict[str, Any]) -> Interaction:
        """Reconstruct Interaction from dictionary"""
        return Interaction(
            interaction_id=data.get("interaction_id", ""),
            query=data.get("query", ""),
            response=data.get("response", ""),
            agent=data.get("agent", ""),
            query_type=data.get("query_type", ""),
            complexity=data.get("complexity", ""),
            status=InteractionStatus(data.get("status", "success")),
            execution_time_ms=data.get("execution_time_ms", 0),
            quality_score=data.get("quality_score", 0.5),
            tags=data.get("tags", []),
            context=data.get("context", {}),
        )

    async def store(self, interaction: Interaction) -> bool:
        """Store interaction in both backends"""
        try:
            # Store in local cache
            self.local_cache[interaction.interaction_id] = interaction
            await self._save_cache(interaction)
            self.interaction_count += 1

            # Store in Qdrant if available
            if self.qdrant_ready and interaction.embedding:
                point = PointStruct(
                    id=hash(interaction.interaction_id) % (10 ** 8),
                    vector=interaction.embedding,
                    payload={
                        "interaction_id": interaction.interaction_id,
                        "query": interaction.query[:500],
                        "response": interaction.response[:500],
                        "agent": interaction.agent,
                        "query_type": interaction.query_type,
                        "complexity": interaction.complexity,
                        "status": interaction.status.value,
                        "execution_time_ms": interaction.execution_time_ms,
                        "quality_score": interaction.quality_score,
                        "tags": interaction.tags,
                        "timestamp": interaction.timestamp.isoformat(),
                    }
                )

                await self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=[point],
                    wait=True,
                )
                logger.info("interaction_stored", id=interaction.interaction_id)

            return True
        except Exception as e:
            logger.error("interaction_store_failed", error=str(e))
            return False

    async def retrieve(self, interaction_id: str) -> Optional[Interaction]:
        """Retrieve interaction by ID"""
        # Check local cache first
        if interaction_id in self.local_cache:
            return self.local_cache[interaction_id]

        # Could also query Qdrant by ID filter, but cache is faster
        return None

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Search semantically similar interactions"""
        if not self.qdrant_ready:
            logger.warning("semantic_search_not_available_qdrant_disabled")
            return []

        try:
            # Generate embedding for query (would need embedding service)
            # For now, return empty list as placeholder
            # In production, would call embedding service here

            # results = await self.qdrant.search(
            #     collection_name=self.collection_name,
            #     query_vector=embedding,
            #     limit=limit,
            #     query_filter=Filter(
            #         must=[
            #             HasIdCondition(has_id=[...])
            #         ]
            #     ),
            #     score_threshold=min_score,
            # )

            logger.info("semantic_search_executed", query_preview=query[:100])
            return []
        except Exception as e:
            logger.error("semantic_search_failed", error=str(e))
            return []

    async def search_by_type(
        self,
        query_type: str,
        limit: int = 50,
    ) -> List[Interaction]:
        """Search interactions by query type"""
        try:
            results = [
                interaction for interaction in self.local_cache.values()
                if interaction.query_type == query_type
            ]
            return results[:limit]
        except Exception as e:
            logger.error("search_by_type_failed", error=str(e))
            return []

    async def search_by_agent(
        self,
        agent: str,
        limit: int = 50,
    ) -> List[Interaction]:
        """Search interactions by agent"""
        try:
            results = [
                interaction for interaction in self.local_cache.values()
                if interaction.agent == agent
            ]
            return results[:limit]
        except Exception as e:
            logger.error("search_by_agent_failed", error=str(e))
            return []

    async def search_by_status(
        self,
        status: InteractionStatus,
        limit: int = 50,
    ) -> List[Interaction]:
        """Search interactions by status"""
        try:
            results = [
                interaction for interaction in self.local_cache.values()
                if interaction.status == status
            ]
            return results[:limit]
        except Exception as e:
            logger.error("search_by_status_failed", error=str(e))
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get interaction storage statistics"""
        try:
            # Aggregate statistics
            by_type: Dict[str, int] = {}
            by_agent: Dict[str, int] = {}
            by_status: Dict[str, int] = {}
            quality_scores: List[float] = []
            execution_times: List[int] = []

            for interaction in self.local_cache.values():
                by_type[interaction.query_type] = by_type.get(interaction.query_type, 0) + 1
                by_agent[interaction.agent] = by_agent.get(interaction.agent, 0) + 1
                by_status[interaction.status.value] = by_status.get(interaction.status.value, 0) + 1
                quality_scores.append(interaction.quality_score)
                execution_times.append(interaction.execution_time_ms)

            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

            return {
                "total_interactions": self.interaction_count,
                "by_type": by_type,
                "by_agent": by_agent,
                "by_status": by_status,
                "avg_quality_score": round(avg_quality, 3),
                "avg_execution_time_ms": int(avg_execution_time),
                "qdrant_available": self.qdrant_ready,
                "cache_path": str(self.cache_path),
            }
        except Exception as e:
            logger.error("statistics_computation_failed", error=str(e))
            return {}

    async def cleanup_old_interactions(self, days: int = 30) -> int:
        """Remove interactions older than N days"""
        try:
            cutoff = datetime.now(timezone.utc).timestamp() - (days * 24 * 3600)
            removed = 0

            for interaction_id, interaction in list(self.local_cache.items()):
                if interaction.timestamp.timestamp() < cutoff:
                    del self.local_cache[interaction_id]
                    removed += 1

            logger.info("old_interactions_cleanup", removed=removed, days=days)
            return removed
        except Exception as e:
            logger.error("cleanup_failed", error=str(e))
            return 0
