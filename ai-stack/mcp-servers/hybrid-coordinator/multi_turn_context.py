#!/usr/bin/env python3
"""
Multi-Turn Context Manager for Remote LLM Conversations
Enables recursive language model (RLM) patterns with session tracking
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
import redis.asyncio as aioredis
from pydantic import BaseModel, Field

from context_compression import ContextCompressor
from query_expansion import QueryExpansionReranking

logger = logging.getLogger("multi-turn-context")


class ContextResponse(BaseModel):
    """Response from context augmentation request"""
    context: str = Field(..., description="Formatted context within token budget")
    context_ids: List[str] = Field(..., description="IDs of context items sent")
    suggestions: List[str] = Field(default_factory=list, description="Suggested follow-up queries")
    token_count: int = Field(..., description="Approximate token count of context")
    collections_searched: List[str] = Field(..., description="Collections queried")
    session_id: str = Field(..., description="Session identifier")
    turn_number: int = Field(..., description="Turn number in this session")


class SessionState(BaseModel):
    """State of a multi-turn conversation session"""
    session_id: str
    created_at: str
    last_accessed: str
    queries: List[str] = Field(default_factory=list)
    context_sent: List[str] = Field(default_factory=list)
    total_tokens_sent: int = 0
    turn_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiTurnContextManager:
    """
    Manage multi-turn context requests from remote LLMs

    Enables RLM pattern where remote LLMs can query multiple times
    during a single task, building up context progressively.

    Features:
    - Session state persistence in Redis
    - Context deduplication (don't re-send same info)
    - Progressive context deepening
    - Token budget tracking
    - Automatic suggestion generation

    Example usage by remote LLM (Claude):

    # Turn 1: Initial broad search
    response = await manager.get_context(
        session_id="uuid",
        query="NixOS GNOME keyring error",
        context_level="standard",
        max_tokens=1500
    )

    # Turn 2: Deeper specific search based on gaps
    response = await manager.get_context(
        session_id="uuid",
        query="NixOS GNOME keyring service configuration",
        context_level="detailed",
        previous_context_ids=response.context_ids,  # Don't re-send
        max_tokens=2000
    )
    """

    def __init__(
        self,
        qdrant_client,
        redis_url: str = "redis://localhost:6379",
        llama_cpp_url: str = "http://localhost:8080",
        session_ttl: int = 3600  # 1 hour
    ):
        self.qdrant = qdrant_client
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.llama_cpp_url = llama_cpp_url
        self.session_ttl = session_ttl

        # Initialize context compressor and query expansion
        self.compressor = ContextCompressor()
        self.query_expander = QueryExpansionReranking(llama_cpp_url)

        # Context level configurations
        self.context_levels = {
            "standard": {
                "collections": ["error-solutions", "best-practices"],
                "limit_per_collection": 3,
                "detail": "concise"
            },
            "detailed": {
                "collections": ["error-solutions", "best-practices", "codebase-context"],
                "limit_per_collection": 5,
                "detail": "full"
            },
            "comprehensive": {
                "collections": [
                    "error-solutions",
                    "best-practices",
                    "codebase-context",
                    "skills-patterns",
                    "interaction-history"
                ],
                "limit_per_collection": 10,
                "detail": "verbose"
            }
        }

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("✓ Redis connection established for multi-turn sessions")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Multi-turn sessions will not persist across restarts")
            self.redis = None

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    async def get_context(
        self,
        session_id: str,
        query: str,
        context_level: str = "standard",
        previous_context_ids: Optional[List[str]] = None,
        max_tokens: int = 2000,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextResponse:
        """
        Get context for remote LLM with progressive disclosure

        Args:
            session_id: Unique session to track multi-turn conversations
            query: Current query from remote LLM
            context_level: How much detail to return (standard/detailed/comprehensive)
            previous_context_ids: Context already sent (to avoid duplication)
            max_tokens: Budget for this response
            metadata: Optional metadata about the request

        Returns:
            ContextResponse with formatted context, IDs, suggestions, etc.
        """
        start_time = datetime.now(timezone.utc)

        # Load or create session state
        session = await self.load_session(session_id)
        if not session:
            session = SessionState(
                session_id=session_id,
                created_at=start_time.isoformat(),
                last_accessed=start_time.isoformat(),
                metadata=metadata or {}
            )

        # Update session
        session.queries.append(query)
        session.turn_count += 1
        session.last_accessed = start_time.isoformat()

        # Get context level config
        level_config = self.context_levels.get(context_level, self.context_levels["standard"])

        # Search collections for relevant context
        logger.info(f"Session {session_id} Turn {session.turn_count}: Searching {len(level_config['collections'])} collections")

        raw_results = await self.search_all_collections(
            query=query,
            collections=level_config["collections"],
            limit_per_collection=level_config["limit_per_collection"]
        )

        # Filter out previously sent context
        if previous_context_ids:
            logger.info(f"Filtering {len(previous_context_ids)} previously sent context items")
            raw_results = [r for r in raw_results if r.get("id") not in previous_context_ids]

        # Rank by relevance (already sorted by Qdrant score)
        ranked_results = raw_results

        # Compress to fit token budget
        compressed_context, included_ids, token_count = await self.compress_to_budget(
            results=ranked_results,
            max_tokens=max_tokens,
            detail_level=level_config["detail"]
        )

        # Generate suggestions for next turn
        suggestions = await self.generate_suggestions(
            query=query,
            context=compressed_context,
            session=session
        )

        # Update session state
        session.context_sent.extend(included_ids)
        session.total_tokens_sent += token_count
        await self.save_session(session)

        # Get collection names from results
        collections_searched = list(set([r.get("collection", "unknown") for r in ranked_results]))

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"Session {session_id} Turn {session.turn_count}: "
            f"Returned {len(included_ids)} context items, "
            f"{token_count} tokens in {duration:.2f}s"
        )

        return ContextResponse(
            context=compressed_context,
            context_ids=included_ids,
            suggestions=suggestions,
            token_count=token_count,
            collections_searched=collections_searched,
            session_id=session_id,
            turn_number=session.turn_count
        )

    async def search_all_collections(
        self,
        query: str,
        collections: List[str],
        limit_per_collection: int
    ) -> List[Dict[str, Any]]:
        """
        Search multiple collections and merge results

        Returns:
            List of result dicts with payload and metadata
        """
        all_results = []

        # Generate query embedding (if embeddings available)
        query_embedding = await self.embed_text(query)

        for collection in collections:
            try:
                # Check if collection exists
                collection_info = self.qdrant.get_collection(collection)
                if collection_info.points_count == 0:
                    logger.debug(f"Collection {collection} is empty, skipping")
                    continue

                # Search collection
                if query_embedding and len(query_embedding) > 0 and query_embedding[0] != 0.0:
                    # Vector search (if embeddings available)
                    results = self.qdrant.search(
                        collection_name=collection,
                        query_vector=query_embedding,
                        limit=limit_per_collection,
                        score_threshold=0.7
                    )
                else:
                    # Fallback: scroll through collection (no vector search)
                    logger.debug(f"No embeddings available, using scroll for {collection}")
                    scroll_result = self.qdrant.scroll(
                        collection_name=collection,
                        limit=limit_per_collection,
                        with_payload=True,
                        with_vectors=False
                    )
                    results = scroll_result[0] if scroll_result else []

                # Convert to standard format
                for result in results:
                    all_results.append({
                        "id": str(result.id),
                        "score": getattr(result, 'score', 0.5),
                        "payload": result.payload,
                        "collection": collection
                    })

                logger.debug(f"Collection {collection}: {len(results)} results")

            except Exception as e:
                logger.error(f"Error searching collection {collection}: {e}")
                continue

        # Sort by score (highest first)
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return all_results

    async def compress_to_budget(
        self,
        results: List[Dict[str, Any]],
        max_tokens: int,
        detail_level: str
    ) -> Tuple[str, List[str], int]:
        """
        Compress results to fit within token budget

        Args:
            results: Search results to compress
            max_tokens: Maximum tokens allowed
            detail_level: concise/full/verbose

        Returns:
            (formatted_context, included_ids, actual_token_count)
        """
        formatted_parts = []
        included_ids = []
        current_tokens = 0

        for result in results:
            payload = result.get("payload", {})
            collection = result.get("collection", "unknown")

            # Format based on detail level and collection type
            if detail_level == "concise":
                formatted = self.format_concise(payload, collection)
            elif detail_level == "full":
                formatted = self.format_full(payload, collection)
            else:  # verbose
                formatted = self.format_verbose(payload, collection)

            # Estimate token count (rough: ~1.3 tokens per word)
            tokens = int(len(formatted.split()) * 1.3)

            if current_tokens + tokens > max_tokens:
                # Budget exceeded
                logger.debug(f"Token budget exceeded at {len(included_ids)} items")
                break

            formatted_parts.append(formatted)
            included_ids.append(result.get("id"))
            current_tokens += tokens

        # Combine all parts
        if formatted_parts:
            context = "\n\n".join(formatted_parts)
        else:
            context = "No relevant context found in local knowledge base."

        return context, included_ids, current_tokens

    def format_concise(self, payload: Dict[str, Any], collection: str) -> str:
        """Format payload concisely (bullet point summary)"""
        if collection == "error-solutions":
            return f"• {payload.get('error_pattern', 'Unknown error')}: {payload.get('solution', 'No solution')[:100]}"

        elif collection == "best-practices":
            return f"• {payload.get('practice_name', 'Unknown practice')}: {payload.get('description', '')[:100]}"

        elif collection == "codebase-context":
            return f"• {payload.get('file_path', 'Unknown file')}: {payload.get('content', '')[:100]}"

        else:
            return f"• {str(payload)[:100]}"

    def format_full(self, payload: Dict[str, Any], collection: str) -> str:
        """Format payload with full details"""
        if collection == "error-solutions":
            return f"""**Error:** {payload.get('error_pattern', 'Unknown')}
**Context:** {payload.get('context', 'No context')}
**Solution:** {payload.get('solution', 'No solution')}
**Source:** {payload.get('source', 'Unknown')}
**Confidence:** {payload.get('confidence_score', 0):.2f}"""

        elif collection == "best-practices":
            return f"""**Practice:** {payload.get('practice_name', 'Unknown')}
**Category:** {payload.get('category', 'General')}
**Description:** {payload.get('description', '')}
**Implementation:** {payload.get('implementation', 'Not specified')[:200]}"""

        elif collection == "codebase-context":
            return f"""**File:** {payload.get('file_path', 'Unknown')}
**Type:** {payload.get('file_type', 'unknown')}
**Content:**
{payload.get('content', '')[:500]}"""

        else:
            return json.dumps(payload, indent=2)[:500]

    def format_verbose(self, payload: Dict[str, Any], collection: str) -> str:
        """Format payload with maximum detail"""
        return json.dumps(payload, indent=2)

    async def generate_suggestions(
        self,
        query: str,
        context: str,
        session: SessionState
    ) -> List[str]:
        """
        Generate follow-up query suggestions for remote LLM

        Uses local LLM to analyze current query + context and suggest
        what additional information would be helpful.

        Returns:
            List of 2-3 suggested follow-up queries
        """
        # Avoid suggesting on first turn (not enough context)
        if session.turn_count < 1:
            return []

        # Build prompt for suggestion generation
        prompt = f"""Based on this conversation, suggest 2-3 specific follow-up queries that would provide helpful additional information.

Original Query: {query}

Context Provided:
{context[:500]}...

Previous Queries in Session:
{', '.join(session.queries[-3:])}

Generate 2-3 specific, actionable follow-up queries (one per line):"""

        try:
            # Call local LLM for suggestions
            suggestions_text = await self.call_local_llm(prompt, max_tokens=150)

            # Parse suggestions (one per line)
            suggestions = [
                line.strip().lstrip("123456789.-• ")
                for line in suggestions_text.split("\n")
                if line.strip() and len(line.strip()) > 10
            ]

            return suggestions[:3]

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return []

    async def call_local_llm(self, prompt: str, max_tokens: int = 150) -> str:
        """Call local llama.cpp for text generation"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llama_cpp_url}/v1/completions",
                    json={
                        "prompt": prompt,
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                        "stop": ["\n\n", "Query:"]
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["text"].strip()
                else:
                    logger.warning(f"LLM call failed: {response.status_code}")
                    return ""

        except Exception as e:
            logger.error(f"Error calling local LLM: {e}")
            return ""

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding using llama.cpp (if available)"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llama_cpp_url}/v1/embeddings",
                    json={"input": text}
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["data"][0]["embedding"]
                else:
                    # Embeddings not available
                    return []

        except Exception:
            return []

    async def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session state from Redis"""
        if not self.redis:
            return None

        try:
            session_json = await self.redis.get(f"session:{session_id}")
            if session_json:
                return SessionState.parse_raw(session_json)
            return None

        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None

    async def save_session(self, session: SessionState):
        """Save session state to Redis"""
        if not self.redis:
            return

        try:
            await self.redis.setex(
                f"session:{session.session_id}",
                self.session_ttl,
                session.json()
            )

        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}")

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information for debugging/monitoring"""
        session = await self.load_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "last_accessed": session.last_accessed,
            "turn_count": session.turn_count,
            "total_queries": len(session.queries),
            "total_context_items_sent": len(session.context_sent),
            "total_tokens_sent": session.total_tokens_sent,
            "queries": session.queries,
            "metadata": session.metadata
        }

    async def clear_session(self, session_id: str):
        """Clear/end a session"""
        if not self.redis:
            return

        try:
            await self.redis.delete(f"session:{session_id}")
            logger.info(f"Cleared session {session_id}")
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
