"""
rag_augmentor.py — Active RAG pipeline (Phase 54.3)

Makes retrieval augmentation the default for every coordinator query.
Wraps the AIDB /vector/search call with:
  - Project selection by intent (from IntentClassifier)
  - 500ms hard timeout (skip augmentation, don't block)
  - Hit/miss tracking for aq-report posture detection
  - Injection of top-k docs as [CONTEXT] block in request_context

L6 health gate:
    L6 = healthy iff last 5 queries had rag_skipped=False
    Checked by GET /api/health/layered

Usage:
    from rag_augmentor import RagAugmentor, get_augmentor

    aug = get_augmentor()
    aug_result = await aug.augment(query="how does asyncio work", intent="knowledge_lookup")
    # aug_result = {"augmented": True, "hits": 5, "context_text": "...", "latency_ms": 42}
    if aug_result["augmented"]:
        request_context["rag_context"] = aug_result["context_text"]
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# L6 health: rolling window of last 5 augmentation results
_L6_WINDOW_SIZE = 5
_augmentation_window: deque = deque(maxlen=_L6_WINDOW_SIZE)

# Module-level references — injected via init()
_aidb_client: Optional[Any] = None  # httpx.AsyncClient pointing at AIDB
_aidb_key: str = ""
_augmentor: Optional["RagAugmentor"] = None

RAG_TIMEOUT_S = 0.5  # hard cap — skip augmentation on timeout


def init(aidb_client: Any, aidb_api_key: str = "") -> None:
    """Wire in AIDB client. Call once from server.py startup."""
    global _aidb_client, _aidb_key, _augmentor
    _aidb_client = aidb_client
    _aidb_key = aidb_api_key
    _augmentor = RagAugmentor(aidb_client=aidb_client, aidb_api_key=aidb_api_key)
    logger.info("rag_augmentor: initialized (aidb_client=%s)", aidb_client)


def get_augmentor() -> "RagAugmentor":
    global _augmentor
    if _augmentor is None:
        _augmentor = RagAugmentor(aidb_client=_aidb_client, aidb_api_key=_aidb_key)
    return _augmentor


def get_l6_status() -> Dict[str, Any]:
    """Return L6 (Cognitive/Semantic) layer health based on recent augmentations."""
    window = list(_augmentation_window)
    if not window:
        return {"status": "unknown", "reason": "no_queries_yet", "window_size": 0}
    augmented = sum(1 for v in window if v)
    total = len(window)
    healthy = augmented == total  # all recent queries augmented = healthy
    return {
        "status": "healthy" if healthy else "degraded",
        "augmented": augmented,
        "total": total,
        "window_size": _L6_WINDOW_SIZE,
        "posture": "active" if healthy else "historical",
    }


class RagAugmentor:
    """
    Augments queries with retrieved AIDB context before LLM inference.

    Designed to be called on every /query request with <500ms budget.
    On timeout or error: returns augmented=False (safe degradation).
    """

    def __init__(
        self,
        aidb_client: Optional[Any] = None,
        aidb_api_key: str = "",
        top_k: int = 5,
    ) -> None:
        self._client = aidb_client
        self._key = aidb_api_key
        self._top_k = top_k

    async def augment(
        self,
        query: str,
        intent: str = "unknown",
        rag_project: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant docs from one or more AIDB projects.

        Args:
            query: The user query
            intent: Classified intent (used for scaling/selection)
            rag_project: Optional AIDB project(s). Can be comma-separated list.
                         If None, uses intent-based default.
            top_k: Number of results (overrides default)

        Returns:
            Standard augmentation result dict
        """
        k = top_k or self._top_k
        
        # Phase 54.3 — Active RAG: Dynamic project selection
        # projects can be a single string or a list/comma-separated string
        project_raw = rag_project or "semantic"
        projects = [p.strip() for p in project_raw.split(",") if p.strip()]

        if self._client is None:
            _augmentation_window.append(False)
            return _skip_result("no_aidb_client", ",".join(projects))

        start = time.perf_counter()
        try:
            # Search all requested projects in parallel
            search_tasks = [self._search(query, p, k) for p in projects]
            results = await asyncio.wait_for(
                asyncio.gather(*search_tasks),
                timeout=RAG_TIMEOUT_S,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            # Merge and rerank results (simple score-based sort)
            all_hits = []
            for res in results:
                all_hits.extend(res.get("hits", []))
            
            all_hits.sort(key=lambda h: h.get("score", 0.0), reverse=True)
            hits = all_hits[:k]

            if not hits:
                _augmentation_window.append(False)
                return {**_skip_result("no_hits", ",".join(projects), len(projects)), "latency_ms": latency_ms}

            context_parts = []
            for i, hit in enumerate(hits, 1):
                content = (hit.get("content") or hit.get("text") or "").strip()
                p_origin = hit.get("project", "unknown")
                if content:
                    context_parts.append(f"[{i}] (Source: {p_origin}) {content[:800]}")

            context_text = "\n\n".join(context_parts)
            _augmentation_window.append(True)

            logger.debug(
                "rag_augmentor.augment projects=%s hits=%d latency_ms=%d",
                projects, len(hits), latency_ms,
            )
            res = {
                "augmented": True,
                "skipped": False,
                "hits": len(hits),
                "context_text": context_text,
                "latency_ms": latency_ms,
                "projects": projects,
                "collection_count": len(projects),
                "project": projects[0], # for backward compat
            }
            _record_metrics(res)
            return res

        except asyncio.TimeoutError:
            _augmentation_window.append(False)
            res = {**_skip_result("timeout", project), "latency_ms": int(RAG_TIMEOUT_S * 1000)}
            _record_metrics(res)
            return res
        except Exception as exc:
            _augmentation_window.append(False)
            logger.debug("rag_augmentor.augment error project=%s: %s", project, exc)
            res = _skip_result("error", project)
            _record_metrics(res)
            return res

    async def _search(self, query: str, project: str, top_k: int) -> Dict[str, Any]:
        """Call AIDB /vector/search."""
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["X-API-Key"] = self._key

        resp = await self._client.post(
            "/vector/search",
            json={"query": query, "project": project, "limit": top_k},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_metrics(result: Dict[str, Any]) -> None:
    """Record RAG metrics to Prometheus."""
    try:
        from metrics import RAG_AUGMENTATIONS, RAG_AUGMENTATION_HITS, RAG_AUGMENTATION_LATENCY
        status = "augmented" if result.get("augmented") else result.get("skip_reason", "skipped")
        project = result.get("project", "unknown")
        RAG_AUGMENTATIONS.labels(status=status, project=project).inc()
        
        if result.get("augmented"):
            RAG_AUGMENTATION_HITS.labels(project=project).observe(result.get("hits", 0))
            latency_ms = result.get("latency_ms", 0)
            RAG_AUGMENTATION_LATENCY.labels(project=project).observe(latency_ms / 1000.0)
    except (ImportError, Exception):
        pass


def _skip_result(reason: str, project: str, collection_count: int = 0) -> Dict[str, Any]:
    return {
        "augmented": False,
        "skipped": True,
        "hits": 0,
        "context_text": "",
        "latency_ms": 0,
        "project": project,
        "collection_count": collection_count,
        "skip_reason": reason,
    }


# ---------------------------------------------------------------------------
# HTTP handler — GET /api/health/rag
# ---------------------------------------------------------------------------

async def handle_rag_health(request) -> Any:
    """GET /api/health/rag — return L6 posture and augmentation window."""
    from aiohttp import web
    return web.json_response(get_l6_status())
