"""
graph_search.py — GraphRAG knowledge extraction via AIDB (Phase 63.2).

Provides hybrid vector + BFS-2 graph hop search over the 'knowledge-graph'
AIDB collection.  BFS expansion uses entity names (subject/object metadata)
from seed results to find related triples at up to 2 hops depth.

HTTP handler: POST /api/knowledge/graph/search
    Body: {"query": str, "depth": int (1-2, default 2), "top_k": int (default 5)}
    Returns: {"results": [...], "entity_count": int, "hop_depth": int, "latency_ms": int}
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("hybrid-coordinator")

# Module-level references — injected via init()
_aidb_client: Optional[Any] = None
_aidb_key: str = ""

GRAPH_PROJECT = "knowledge-graph"
GRAPH_TIMEOUT_S = 2.0


def init(aidb_client: Any, aidb_api_key: str = "") -> None:
    """Wire in AIDB client. Call once from server.py startup."""
    global _aidb_client, _aidb_key
    _aidb_client = aidb_client
    _aidb_key = aidb_api_key


# ---------------------------------------------------------------------------
# Core search logic
# ---------------------------------------------------------------------------


async def _vector_search(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Vector search in AIDB knowledge-graph project."""
    if _aidb_client is None:
        return []
    try:
        resp = await _aidb_client.post(
            "/vector/search",
            json={"query": query, "project": GRAPH_PROJECT, "top_k": top_k},
            headers={"X-API-Key": _aidb_key},
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])
    except Exception as exc:
        logger.debug("graph_search._vector_search error: %s", exc)
    return []


def _extract_entities(results: List[Dict[str, Any]]) -> Set[str]:
    """Extract subject and object entities from triple results."""
    entities: Set[str] = set()
    for r in results:
        meta = r.get("metadata", {})
        subj = (meta.get("subject") or "").strip()
        obj = (meta.get("object") or "").strip()
        if subj and len(subj) > 2:
            entities.add(subj.lower())
        if obj and len(obj) > 2:
            entities.add(obj.lower())
    return entities


async def graph_search(query: str, depth: int = 2, top_k: int = 5) -> Dict[str, Any]:
    """
    BFS-2 graph hop search.

    1. Seed: vector search for query → seed_results (top_k hits)
    2. Depth-1: for each entity in seed results, vector search that entity name
    3. Depth-2: for each entity in depth-1 results, vector search that entity name
    4. Merge and deduplicate all results
    """
    t0 = time.monotonic()
    query = str(query or "").strip()[:500]
    depth = max(1, min(depth, 2))
    top_k = max(1, min(int(top_k), 20))

    if _aidb_client is None:
        return {"results": [], "entity_count": 0, "hop_depth": 0, "latency_ms": 0, "error": "no_aidb_client"}
    if not query:
        return {"results": [], "entity_count": 0, "hop_depth": 0, "latency_ms": 0, "error": "empty_query"}

    try:
        async with asyncio.timeout(GRAPH_TIMEOUT_S):
            # Seed search
            seed_results = await _vector_search(query, top_k)
            seen_keys: Set[str] = {r.get("id", r.get("relative_path", "")) for r in seed_results}
            all_results = list(seed_results)
            all_entities: Set[str] = _extract_entities(seed_results)

            # BFS expansion at each depth
            frontier_entities = set(all_entities)
            for _ in range(depth):
                if not frontier_entities:
                    break
                hop_results_lists = await asyncio.gather(
                    *[_vector_search(entity, top_k=3) for entity in list(frontier_entities)[:8]],
                    return_exceptions=True,
                )
                new_entities: Set[str] = set()
                for hop_results in hop_results_lists:
                    if isinstance(hop_results, Exception):
                        continue
                    for r in hop_results:
                        key = r.get("id", r.get("relative_path", ""))
                        if key and key not in seen_keys:
                            seen_keys.add(key)
                            all_results.append(r)
                new_entities.update(_extract_entities(
                    [r for res in hop_results_lists
                     if not isinstance(res, Exception) for r in res]  # type: ignore[union-attr]
                ))
                frontier_entities = new_entities - all_entities
                all_entities.update(new_entities)

    except TimeoutError:
        all_results = []
        all_entities = set()
        logger.debug("graph_search timeout query=%r depth=%s top_k=%s", query[:80], depth, top_k)

    latency_ms = int((time.monotonic() - t0) * 1000)
    return {
        "results": all_results[:top_k * (depth + 1)],
        "entity_count": len(all_entities),
        "hop_depth": depth,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

try:
    from aiohttp import web as _web

    async def handle_graph_search(request: _web.Request) -> _web.Response:
        """POST /api/knowledge/graph/search — GraphRAG BFS-2 search."""
        try:
            data = await request.json()
        except Exception:
            return _web.json_response({"error": "invalid JSON"}, status=400)

        query = data.get("query", "").strip()
        if not query:
            return _web.json_response({"error": "query required"}, status=400)

        try:
            depth = int(data.get("depth", 2))
            top_k = int(data.get("top_k", 5))
        except (TypeError, ValueError):
            return _web.json_response({"error": "depth and top_k must be integers"}, status=400)

        result = await graph_search(query, depth=depth, top_k=top_k)
        return _web.json_response(result)

    def register_routes(http_app: _web.Application) -> None:
        http_app.router.add_post("/api/knowledge/graph/search", handle_graph_search)

except ImportError:
    # aiohttp not available (e.g., in test context)
    def register_routes(http_app: Any) -> None:  # type: ignore[misc]
        pass
