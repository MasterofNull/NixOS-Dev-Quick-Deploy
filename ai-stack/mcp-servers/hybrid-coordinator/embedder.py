"""
Embedding functions for hybrid-coordinator.

Provides embed_text() (cached) and embed_text_uncached() backed by
embeddings-service → AIDB → llama.cpp fallback chain.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import embedder
    embedder.init(
        embedding_client=embedding_client,
        embedding_cache_ref=lambda: embedding_cache,
    )
    vector = await embedder.embed_text("some text")
"""

import logging
import random
from typing import Any, Callable, Dict, List, Optional

from config import Config
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("hybrid-coordinator")
TRACER = trace.get_tracer("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------
_embedding_client: Optional[Any] = None
_embedding_cache_ref: Optional[Callable] = None


def init(*, embedding_client: Any, embedding_cache_ref: Callable) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _embedding_client, _embedding_cache_ref
    _embedding_client = embedding_client
    _embedding_cache_ref = embedding_cache_ref


async def embed_text_uncached(text: str) -> List[float]:
    """Generate embedding via HTTP — no caching.

    Fallback chain: embeddings-service → AIDB → llama.cpp.
    Returns zero vector on all failures.
    """
    with TRACER.start_as_current_span(
        "hybrid.embed_text",
        attributes={"text_length": len(text)},
    ) as span:
        try:
            def _extract_embedding(payload: Dict[str, Any]) -> List[float]:
                if "data" in payload:
                    return payload.get("data", [{}])[0].get("embedding", [])
                if "embeddings" in payload:
                    embeddings = payload.get("embeddings") or []
                    return embeddings[0] if embeddings else []
                if isinstance(payload, list):
                    return payload[0] if payload else []
                return []

            async def _request_embedding(
                url: str,
                body: Dict[str, Any],
                headers: Optional[Dict[str, str]] = None,
            ) -> List[float]:
                response = await _embedding_client.post(url, json=body, headers=headers or {}, timeout=30.0)
                response.raise_for_status()
                embedding = _extract_embedding(response.json())
                if not embedding:
                    raise ValueError("No embedding returned")
                return embedding

            if Config.EMBEDDING_SERVICE_URL:
                headers: Dict[str, str] = {}
                if Config.EMBEDDING_API_KEY:
                    headers["X-API-Key"] = Config.EMBEDDING_API_KEY
                try:
                    return await _request_embedding(
                        f"{Config.EMBEDDING_SERVICE_URL}/v1/embeddings",
                        {"input": text},
                        headers=headers,
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("Embedding service failed, falling back", exc_info=True)

            if Config.AIDB_URL:
                try:
                    return await _request_embedding(
                        f"{Config.AIDB_URL}/vector/embed",
                        {"texts": [text]},
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("AIDB embedding fallback failed, using llama.cpp", exc_info=True)

            response = await _embedding_client.post(
                f"{Config.LLAMA_CPP_URL}/v1/embeddings",
                json={"model": "nomic-embed-text", "input": text},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [{}])[0].get("embedding", [])

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Embedding error: {e}")
            return [0.0] * Config.EMBEDDING_DIM


async def embed_text(text: str, variant_tag: str = "") -> List[float]:
    """Public embedding entry point with Redis cache.

    Cache hit: returns in < 5 ms. Cache miss: delegates to embed_text_uncached().
    Zero-vector error fallbacks are not cached.

    variant_tag: optional A/B test tag included in the cache key so that
                 variant A and B never share cached embeddings.
    """
    embedding_cache = _embedding_cache_ref() if _embedding_cache_ref else None

    if not variant_tag:
        fraction = Config.AB_TEST_VARIANT_B_FRACTION
        variant_tag = "B" if (fraction > 0.0 and random.random() < fraction) else "A"
        if variant_tag == "B":
            logger.info("embed_text ab_variant=B fraction=%.2f", fraction)

    if embedding_cache:
        cached = await embedding_cache.get(text, variant_tag=variant_tag)
        if cached is not None:
            logger.info("embed_text cache_hit text_len=%d variant=%s", len(text), variant_tag)
            return cached

    vector = await embed_text_uncached(text)

    if embedding_cache and vector and any(v != 0.0 for v in vector[:8]):
        await embedding_cache.set(text, vector, variant_tag=variant_tag)

    return vector
