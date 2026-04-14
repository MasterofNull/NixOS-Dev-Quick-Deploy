"""
Interaction Log Vectorization System

This module provides batch indexing of interaction logs into vector embeddings
for semantic search. It processes interaction history from PostgreSQL and
creates searchable vectors in Qdrant.

Phase 3.1 Completion - Interaction Log Vector Embeddings
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)


class InteractionIndexer:
    """Indexes interaction logs into vector embeddings for semantic search."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_service_url: str,
        postgres_conn: Optional[Any] = None,
        collection_name: str = "interaction-history",
        embedding_dim: int = 1024,
    ):
        """
        Initialize the interaction indexer.

        Args:
            qdrant_client: Qdrant client for vector storage
            embedding_service_url: URL of the embedding service
            postgres_conn: PostgreSQL connection for reading interaction history
            collection_name: Name of the Qdrant collection
            embedding_dim: Dimension of embedding vectors
        """
        self.qdrant = qdrant_client
        self.embedding_url = embedding_service_url
        self.postgres = postgres_conn
        self.collection = collection_name
        self.embedding_dim = embedding_dim
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def ensure_collection(self) -> None:
        """Ensure the Qdrant collection exists with proper configuration."""
        try:
            self.qdrant.get_collection(self.collection)
            logger.info(f"Collection {self.collection} already exists")
        except Exception:
            logger.info(f"Creating collection {self.collection}")
            self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    def truncate_text(self, text: str, max_tokens: int = 1800) -> str:
        """
        Truncate text to stay within token limit.

        Uses a rough approximation: 1 token ≈ 4 characters.
        Max tokens is set below the batch size to ensure safe margin.

        Args:
            text: Text to truncate
            max_tokens: Maximum token count (default: 1800, well below 2048 batch size)

        Returns:
            Truncated text
        """
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]
        logger.warning(
            f"Text truncated from {len(text)} to {max_chars} chars "
            f"(~{max_tokens} tokens) to fit batch size"
        )
        return truncated

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text using the embedding service.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Truncate text to prevent exceeding batch size
        text = self.truncate_text(text)

        try:
            response = await self.http_client.post(
                f"{self.embedding_url}/v1/embeddings",
                json={"input": text},
            )
            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            if "data" in data:
                return data["data"][0]["embedding"]
            elif "embeddings" in data:
                return data["embeddings"][0]
            else:
                logger.error(f"Unexpected embedding response format: {data.keys()}")
                return [0.0] * self.embedding_dim

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * self.embedding_dim

    def create_interaction_text(self, interaction: Dict[str, Any]) -> str:
        """
        Create searchable text from interaction data.

        Combines query, response, agent type, and outcome into a single
        searchable text representation.

        Args:
            interaction: Interaction data dictionary

        Returns:
            Combined text for embedding
        """
        parts = []

        # Add query (most important)
        if interaction.get("query"):
            parts.append(f"Query: {interaction['query']}")

        # Add response summary
        if interaction.get("response"):
            response = interaction["response"][:500]  # Limit response length
            parts.append(f"Response: {response}")

        # Add agent context
        if interaction.get("agent_type"):
            parts.append(f"Agent: {interaction['agent_type']}")

        # Add outcome
        if interaction.get("outcome"):
            parts.append(f"Outcome: {interaction['outcome']}")

        return " | ".join(parts)

    async def index_interaction(self, interaction: Dict[str, Any]) -> Optional[str]:
        """
        Index a single interaction into the vector database.

        Args:
            interaction: Interaction data with query, response, metadata

        Returns:
            Interaction ID if successful, None otherwise
        """
        interaction_id = interaction.get("id") or str(uuid4())

        # Create searchable text
        text = self.create_interaction_text(interaction)

        # Generate embedding
        vector = await self.embed_text(text)

        if not vector or len(vector) != self.embedding_dim:
            logger.error(f"Invalid embedding vector for interaction {interaction_id}")
            return None

        # Prepare payload
        payload = {
            "query": interaction.get("query", ""),
            "response": interaction.get("response", "")[:1000],  # Truncate long responses
            "agent_type": interaction.get("agent_type", "unknown"),
            "model_used": interaction.get("model_used", "unknown"),
            "outcome": interaction.get("outcome", "unknown"),
            "timestamp": interaction.get("timestamp", int(datetime.now().timestamp())),
            "tokens_used": interaction.get("tokens_used", 0),
            "latency_ms": interaction.get("latency_ms", 0),
            "value_score": interaction.get("value_score", 0.0),
        }

        # Store in Qdrant
        try:
            self.qdrant.upsert(
                collection_name=self.collection,
                points=[PointStruct(id=interaction_id, vector=vector, payload=payload)],
            )
            logger.debug(f"Indexed interaction {interaction_id}")
            return interaction_id
        except Exception as e:
            logger.error(f"Failed to index interaction {interaction_id}: {e}")
            return None

    async def index_batch(
        self,
        interactions: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> Tuple[int, int]:
        """
        Index a batch of interactions.

        Args:
            interactions: List of interaction dictionaries
            batch_size: Number of interactions to process at once

        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0

        for i in range(0, len(interactions), batch_size):
            batch = interactions[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} interactions)")

            for interaction in batch:
                result = await self.index_interaction(interaction)
                if result:
                    successful += 1
                else:
                    failed += 1

            # Small delay between batches to avoid overwhelming the embedding service
            if i + batch_size < len(interactions):
                await asyncio.sleep(0.5)

        logger.info(f"Batch indexing complete: {successful} successful, {failed} failed")
        return successful, failed

    async def index_from_postgres(
        self,
        since_days: int = 30,
        limit: int = 1000,
    ) -> Tuple[int, int]:
        """
        Index interactions from PostgreSQL database.

        Args:
            since_days: Only index interactions from the last N days
            limit: Maximum number of interactions to index

        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not self.postgres:
            logger.error("PostgreSQL connection not configured")
            return 0, 0

        # Query interactions from PostgreSQL
        # Note: This assumes an interaction_history table exists
        # Adjust table name and schema as needed
        query = """
            SELECT
                interaction_id as id,
                query,
                response,
                agent_type,
                model_used,
                outcome,
                EXTRACT(EPOCH FROM created_at)::int as timestamp,
                tokens_used,
                latency_ms,
                value_score
            FROM interaction_history
            WHERE created_at >= NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
            LIMIT %s
        """

        try:
            rows = await self.postgres.fetch_all(query, since_days, limit)
            interactions = [dict(row) for row in rows]
            logger.info(f"Retrieved {len(interactions)} interactions from PostgreSQL")

            if not interactions:
                logger.info("No interactions found to index")
                return 0, 0

            return await self.index_batch(interactions)

        except Exception as e:
            logger.error(f"Failed to retrieve interactions from PostgreSQL: {e}")
            return 0, 0

    async def index_from_jsonl(
        self,
        jsonl_path: str,
        max_interactions: Optional[int] = None,
    ) -> Tuple[int, int]:
        """
        Index interactions from a JSONL file.

        Args:
            jsonl_path: Path to JSONL file with interaction data
            max_interactions: Maximum number of interactions to index

        Returns:
            Tuple of (successful_count, failed_count)
        """
        path = Path(jsonl_path)
        if not path.exists():
            logger.error(f"JSONL file not found: {jsonl_path}")
            return 0, 0

        interactions = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        interaction = json.loads(line)
                        interactions.append(interaction)

                        if max_interactions and len(interactions) >= max_interactions:
                            break
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON line: {e}")
                        continue

            logger.info(f"Loaded {len(interactions)} interactions from {jsonl_path}")

            if not interactions:
                logger.info("No valid interactions found in file")
                return 0, 0

            return await self.index_batch(interactions)

        except Exception as e:
            logger.error(f"Failed to read JSONL file: {e}")
            return 0, 0

    async def search_interactions(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search interactions by semantic similarity.

        Args:
            query: Search query
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            filters: Optional filters (agent_type, outcome, etc.)

        Returns:
            List of matching interactions with scores
        """
        # Generate query embedding
        query_vector = await self.embed_text(query)

        if not query_vector or len(query_vector) != self.embedding_dim:
            logger.error("Failed to generate query embedding")
            return []

        # Build filter if provided
        qdrant_filter = None
        if filters:
            # TODO: Convert filters to Qdrant filter format
            pass

        # Search in Qdrant
        try:
            results = self.qdrant.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
            ).points

            interactions = []
            for hit in results:
                interaction = hit.payload.copy()
                interaction["id"] = hit.id
                interaction["score"] = hit.score
                interactions.append(interaction)

            logger.info(f"Found {len(interactions)} matching interactions")
            return interactions

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the indexed interactions.

        Returns:
            Dictionary with collection stats
        """
        try:
            info = self.qdrant.get_collection(self.collection)
            return {
                "collection": self.collection,
                "total_interactions": info.points_count,
                "status": info.status.value if hasattr(info.status, 'value') else str(info.status),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    async def close(self) -> None:
        """Close HTTP client connections."""
        await self.http_client.aclose()


# Standalone functions for CLI usage

async def index_recent_interactions(
    qdrant_url: str = "http://localhost:6333",
    embedding_url: str = "http://localhost:8081",
    postgres_conn: Optional[Any] = None,
    days: int = 30,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Index recent interactions from PostgreSQL.

    Args:
        qdrant_url: Qdrant server URL
        embedding_url: Embedding service URL
        postgres_conn: PostgreSQL connection
        days: Index interactions from last N days
        limit: Maximum interactions to index

    Returns:
        Indexing results
    """
    qdrant = QdrantClient(url=qdrant_url)
    indexer = InteractionIndexer(
        qdrant_client=qdrant,
        embedding_service_url=embedding_url,
        postgres_conn=postgres_conn,
    )

    await indexer.ensure_collection()
    successful, failed = await indexer.index_from_postgres(since_days=days, limit=limit)
    stats = await indexer.get_stats()
    await indexer.close()

    return {
        "indexed": successful,
        "failed": failed,
        "total": successful + failed,
        "stats": stats,
    }


if __name__ == "__main__":
    # Simple CLI test
    import sys

    async def main():
        qdrant = QdrantClient(url="http://localhost:6333")
        indexer = InteractionIndexer(
            qdrant_client=qdrant,
            embedding_service_url="http://localhost:8081",
        )

        await indexer.ensure_collection()
        stats = await indexer.get_stats()
        print(f"Collection stats: {json.dumps(stats, indent=2)}")
        await indexer.close()

    asyncio.run(main())
