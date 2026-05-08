"""
Local LLM health check and model loading queue module for hybrid-coordinator.

Manages liveness probe state and loading-wait queue for llama.cpp.
Moving these here eliminates 100 lines from server.py.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import model_loader
    model_loader.init(llama_cpp_url=Config.LLAMA_CPP_URL)

    # Access mutable state via module-level attributes:
    local_llm_healthy_ref = lambda: model_loader._local_llm_healthy
    local_llm_loading_ref = lambda: model_loader._local_llm_loading
    queue_depth_ref       = lambda: model_loader._model_loading_queue_depth
    queue_max_ref         = lambda: model_loader._MODEL_QUEUE_MAX

    healthy = await model_loader.check_local_llm_health()
    ready   = await model_loader.wait_for_local_model(timeout=30.0)
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Mutable liveness state (public — accessed via lambda refs from server.py)
# ---------------------------------------------------------------------------

_local_llm_healthy: bool = True
_local_llm_loading: bool = False        # True when llama.cpp returns status="loading"
_local_llm_checked_at: float = 0.0

# Model-loading request queue.
# asyncio.Event is set when the local model is ready; cleared during loading.
_model_load_event: asyncio.Event = asyncio.Event()
_model_load_event.set()                 # starts as "ready"
_model_loading_queue_depth: int = 0
_MODEL_QUEUE_MAX: int = int(os.getenv("MODEL_LOADING_QUEUE_MAX", "10"))

# Injected from server.py
_llama_cpp_url: Optional[str] = None


def init(*, llama_cpp_url: str) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _llama_cpp_url
    _llama_cpp_url = llama_cpp_url


async def check_local_llm_health() -> bool:
    """Check whether the local llama.cpp server is reachable and ready.

    Phase 2.3.1: 500 ms timeout, 10 s cache, logs only on state change.
    Phase 2.4.1: distinguishes 'loading' from 'unreachable'; manages
    _model_load_event so waiting callers are released when load completes.

    Returns True when llama.cpp is reachable (even if still loading).
    Returns False when unreachable/error.
    """
    global _local_llm_healthy, _local_llm_loading, _local_llm_checked_at
    now = time.monotonic()
    if now - _local_llm_checked_at <= 10.0:
        return _local_llm_healthy

    new_healthy = False
    new_loading = False
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(f"{_llama_cpp_url}/health")
            new_healthy = resp.is_success
            if new_healthy:
                try:
                    body = resp.json()
                    new_loading = body.get("status") == "loading"
                except Exception:  # noqa: BLE001
                    new_loading = False
    except Exception:  # noqa: BLE001
        new_healthy = False

    _local_llm_checked_at = now

    # Manage the load event — set when ready, cleared when loading.
    if new_healthy and not new_loading:
        if not _model_load_event.is_set():
            logger.info("local_llm_model_ready queue_depth=%d", _model_loading_queue_depth)
        _model_load_event.set()
    elif new_healthy and new_loading:
        _model_load_event.clear()
    else:
        # Unreachable — also clear so waiters don't block forever.
        _model_load_event.clear()

    if new_healthy != _local_llm_healthy:
        if new_healthy:
            logger.info("local_llm_health_changed healthy=True loading=%s", new_loading)
        else:
            logger.warning("local_llm_fallback_to_remote reason=local_unhealthy")

    if new_loading != _local_llm_loading:
        if new_loading:
            logger.info("local_llm_loading_started model=%s", os.getenv("LLAMA_MODEL_NAME", "unknown"))
        else:
            logger.info("local_llm_loading_finished")

    _local_llm_healthy = new_healthy
    _local_llm_loading = new_loading
    return _local_llm_healthy


async def wait_for_local_model(timeout: float = 30.0) -> bool:
    """Phase 2.4.1 — Wait for the local model to finish loading.

    Enqueues the caller into the loading-wait pool (up to _MODEL_QUEUE_MAX).
    Returns True when the model becomes ready within `timeout` seconds.
    Returns False immediately if the queue is full (caller should return 503).
    Returns False on timeout (caller falls back to remote).
    """
    global _model_loading_queue_depth
    if _model_load_event.is_set():
        return True                         # fast path — already ready
    if _model_loading_queue_depth >= _MODEL_QUEUE_MAX:
        logger.warning(
            "model_loading_queue_full depth=%d max=%d",
            _model_loading_queue_depth, _MODEL_QUEUE_MAX,
        )
        return False
    _model_loading_queue_depth += 1
    try:
        await asyncio.wait_for(_model_load_event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        logger.warning("model_loading_wait_timeout timeout=%.1fs", timeout)
        return False
    finally:
        _model_loading_queue_depth -= 1
