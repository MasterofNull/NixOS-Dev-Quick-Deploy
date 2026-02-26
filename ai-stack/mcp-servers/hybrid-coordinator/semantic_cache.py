"""
Semantic cache / context augmentation module for the hybrid-coordinator.

Provides SemanticCache: combines Qdrant vector search with capability
discovery to build an augmented prompt context.

Extracted from server.py (Phase 6.1 decomposition).

Usage:
    from semantic_cache import SemanticCache
    cache = SemanticCache(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        discovery_fn=capability_discovery.discover,
        format_context_fn=capability_discovery.format_context,
        record_telemetry_fn=record_telemetry_event,
        record_stats_fn=record_query_stats,
        tracer=TRACER,
        collections=COLLECTIONS,
    )
    result = await cache.augment(query, agent_type="remote")
"""

import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")


class SemanticCache:
    """Context augmentation via Qdrant vector search + capability discovery."""

    def __init__(
        self,
        *,
        qdrant_client: Any,
        embed_fn: Callable,
        discovery_fn: Callable,
        format_context_fn: Callable,
        record_telemetry_fn: Callable,
        record_stats_fn: Callable,
        tracer: Any,
        collections: Dict[str, Any],
    ) -> None:
        self._qdrant = qdrant_client
        self._embed = embed_fn
        self._discover = discovery_fn
        self._format_context = format_context_fn
        self._record_telemetry = record_telemetry_fn
        self._record_stats = record_stats_fn
        self._tracer = tracer
        self._collections = collections

    async def augment(self, query: str, agent_type: str = "remote") -> Dict[str, Any]:
        """Enhance *query* with relevant local context from Qdrant and capability discovery."""
        with self._tracer.start_as_current_span(
            "hybrid.augment_query",
            attributes={"agent_type": agent_type, "query_length": len(query)},
        ) as span:
            query_embedding = await self._embed(query)
            context_ids: List[str] = []
            results_text: List[str] = []

            # Codebase context
            try:
                with self._tracer.start_as_current_span(
                    "hybrid.qdrant.search", attributes={"collection": "codebase-context"},
                ):
                    codebase_results = self._qdrant.query_points(
                        collection_name="codebase-context",
                        query=query_embedding,
                        limit=5,
                        score_threshold=0.7,
                    ).points
                if codebase_results:
                    results_text.append("## Relevant Code Context\n")
                    for result in codebase_results:
                        context_ids.append(str(result.id))
                        payload = result.payload
                        results_text.append(
                            f"- **{payload.get('file_path', 'Unknown')}** ({payload.get('language', 'unknown')})\n"
                        )
                        results_text.append(f"  {payload.get('purpose', 'No description')}\n")
                        snippet = payload.get("code_snippet", "")
                        if snippet:
                            results_text.append(
                                f"  ```{payload.get('language', '')}\n  {snippet[:200]}...\n  ```\n"
                            )
            except Exception as e:
                logger.warning("Error searching codebase-context: %s", e)

            # Skills/patterns
            try:
                with self._tracer.start_as_current_span(
                    "hybrid.qdrant.search", attributes={"collection": "skills-patterns"},
                ):
                    skills_results = self._qdrant.query_points(
                        collection_name="skills-patterns",
                        query=query_embedding,
                        limit=3,
                        score_threshold=0.75,
                    ).points
                if skills_results:
                    results_text.append("\n## Related Skills & Patterns\n")
                    for result in skills_results:
                        context_ids.append(str(result.id))
                        payload = result.payload
                        results_text.append(f"- **{payload.get('skill_name', 'Unknown Skill')}**\n")
                        results_text.append(f"  {payload.get('description', 'No description')}\n")
            except Exception as e:
                logger.warning("Error searching skills-patterns: %s", e)

            # Error solutions
            try:
                with self._tracer.start_as_current_span(
                    "hybrid.qdrant.search", attributes={"collection": "error-solutions"},
                ):
                    error_results = self._qdrant.query_points(
                        collection_name="error-solutions",
                        query=query_embedding,
                        limit=2,
                        score_threshold=0.8,
                    ).points
                if error_results:
                    results_text.append("\n## Similar Error Solutions\n")
                    for result in error_results:
                        context_ids.append(str(result.id))
                        payload = result.payload
                        results_text.append(f"- **Error**: {payload.get('error_type', 'Unknown')}\n")
                        results_text.append(
                            f"  **Solution**: {payload.get('solution', 'No solution')[:200]}...\n"
                        )
                        confidence = payload.get("confidence_score", 0)
                        results_text.append(f"  **Confidence**: {confidence:.2f}\n")
            except Exception as e:
                logger.warning("Error searching error-solutions: %s", e)

            # Best practices
            try:
                with self._tracer.start_as_current_span(
                    "hybrid.qdrant.search", attributes={"collection": "best-practices"},
                ):
                    bp_results = self._qdrant.query_points(
                        collection_name="best-practices",
                        query=query_embedding,
                        limit=2,
                        score_threshold=0.75,
                    ).points
                if bp_results:
                    results_text.append("\n## Best Practices\n")
                    for result in bp_results:
                        context_ids.append(str(result.id))
                        payload = result.payload
                        results_text.append(
                            f"- **{payload.get('title', 'Unknown')}** ({payload.get('category', 'general')})\n"
                        )
                        results_text.append(f"  {payload.get('description', 'No description')}\n")
            except Exception as e:
                logger.warning("Error searching best-practices: %s", e)

            discovery = await self._discover(query)
            discovery_context = self._format_context(discovery)
            if discovery_context:
                results_text.append(discovery_context)

            span.set_attribute("context_found", bool(results_text))
            span.set_attribute("capability_discovery.decision", discovery.get("decision", "unknown"))
            span.set_attribute("capability_discovery.reason", discovery.get("reason", "unknown"))
            span.set_attribute("capability_discovery.cache_hit", bool(discovery.get("cache_hit", False)))

        context_text = (
            "".join(results_text) if results_text
            else "No relevant context found in local knowledge base."
        )
        augmented_prompt = (
            f"Query: {query}\n\n"
            f"Relevant Context from Local Knowledge Base:\n{context_text}\n\n"
            "Please use this context to provide a more accurate and efficient response.\n"
        )

        self._record_telemetry(
            "context_augmented",
            {
                "agent_type": agent_type,
                "context_count": len(context_ids),
                "collections": list(self._collections.keys()),
                "capability_discovery": {
                    "decision": discovery.get("decision", "unknown"),
                    "reason": discovery.get("reason", "unknown"),
                    "cache_hit": bool(discovery.get("cache_hit", False)),
                    "intent_tags": discovery.get("intent_tags", []),
                    "tool_count": len(discovery.get("tools", [])),
                    "skill_count": len(discovery.get("skills", [])),
                    "server_count": len(discovery.get("servers", [])),
                    "dataset_count": len(discovery.get("datasets", [])),
                },
            },
        )
        self._record_stats(agent_type, len(context_ids) > 0)

        return {
            "augmented_prompt": augmented_prompt,
            "context_ids": context_ids,
            "original_query": query,
            "context_count": len(context_ids),
            "capability_discovery": {
                "decision": discovery.get("decision", "unknown"),
                "reason": discovery.get("reason", "unknown"),
                "cache_hit": bool(discovery.get("cache_hit", False)),
                "intent_tags": discovery.get("intent_tags", []),
                "tools": [
                    {"name": item.get("name"), "description": item.get("description")}
                    for item in discovery.get("tools", [])
                ],
                "skills": [
                    {"name": item.get("name", item.get("slug")), "description": item.get("description")}
                    for item in discovery.get("skills", [])
                ],
                "servers": [
                    {"name": item.get("name"), "description": item.get("description")}
                    for item in discovery.get("servers", [])
                ],
                "datasets": [
                    {"title": item.get("title", item.get("relative_path")), "project": item.get("project")}
                    for item in discovery.get("datasets", [])
                ],
            },
        }
