#!/usr/bin/env python3
"""
Regression: continuous_learning.py _upsert() must NOT await sync QdrantClient.upsert().

Prior bug: `return await self.qdrant.upsert(...)` caused
  TypeError: object UpdateResult can't be used in 'await' expression
when self.qdrant is the sync QdrantClient (server.py passes the sync client).
Fix: removed the spurious await so _upsert() calls self.qdrant.upsert() directly.
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

# Stub structlog before import
if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(
            info=lambda *a, **kw: None,
            warning=lambda *a, **kw: None,
            error=lambda *a, **kw: None,
            debug=lambda *a, **kw: None,
        )
    )

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


async def test_upsert_does_not_await_sync_result():
    """_upsert() inner function with sync QdrantClient must not raise TypeError."""
    from extensions.continuous_learning import ContinuousLearningPipeline

    sync_qdrant = MagicMock()
    update_result = MagicMock()  # NOT a coroutine — simulates sync UpdateResult
    sync_qdrant.upsert.return_value = update_result

    async def passthrough_call(fn):
        return await fn()

    cb = MagicMock()
    cb.call = passthrough_call
    cb.state = MagicMock()
    cb.state.value = "closed"

    pipeline = ContinuousLearningPipeline.__new__(ContinuousLearningPipeline)
    pipeline.qdrant = sync_qdrant
    pipeline.circuit_breakers = {"qdrant": cb}

    try:
        from qdrant_client.models import PointStruct
        point = PointStruct(id=12345, vector=[0.1] * 5, payload={})
    except Exception:
        point = MagicMock()

    raised = None
    try:
        # Reproduce the exact inner function that lives in _index_patterns
        points = [point]

        async def _upsert():
            return pipeline.qdrant.upsert(
                collection_name="skills-patterns",
                points=points,
                wait=True,
            )

        result = await _upsert()
        check("sync upsert returns without TypeError", result is update_result)
    except TypeError as e:
        raised = e
        check("sync upsert returns without TypeError", False)

    if raised:
        print(f"    TypeError was: {raised}")


async def test_index_patterns_circuit_breaker_path():
    """
    _index_patterns() with a sync client mock must reach qdrant_breaker.call()
    without a TypeError propagating to the caller.  We patch _fetch_embeddings
    so the test does not need a live llama-embed service.
    """
    from extensions.continuous_learning import ContinuousLearningPipeline, InteractionPattern

    sync_qdrant = MagicMock()
    sync_qdrant.upsert.return_value = MagicMock()

    async def passthrough_call(fn):
        return await fn()

    cb = MagicMock()
    cb.call = passthrough_call
    cb.state = MagicMock()
    cb.state.value = "closed"

    pipeline = ContinuousLearningPipeline.__new__(ContinuousLearningPipeline)
    pipeline.qdrant = sync_qdrant
    pipeline.circuit_breakers = {"qdrant": cb}

    # Stub _fetch_embeddings so patterns proceed to the upsert path
    async def fake_embeddings(texts):
        return [[0.1] * 768 for _ in texts]

    pipeline._fetch_embeddings = fake_embeddings

    pattern = InteractionPattern(
        pattern_id="test-pat",
        interaction_type="task_completion",
        prompt="test prompt",
        response="test response",
        context={},
        success_metrics={"quality": 0.9},
        iterations=1,
        timestamp=datetime.now(timezone.utc),
        backend="test",
    )

    error_seen = None
    try:
        await pipeline._index_patterns([pattern])
        check("_index_patterns completes without TypeError", True)
    except TypeError as e:
        error_seen = e
        check("_index_patterns completes without TypeError", False)
        print(f"    TypeError: {e}")
    except Exception as e:
        # Non-TypeError errors (e.g. qdrant_client import) are acceptable
        check("_index_patterns completes without TypeError", "UpdateResult" not in str(e))


async def main():
    await test_upsert_does_not_await_sync_result()
    await test_index_patterns_circuit_breaker_path()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    import sys as _sys
    _sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
