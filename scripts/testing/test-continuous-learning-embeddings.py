#!/usr/bin/env python3
"""
Continuous learning embedding fetch regression test.

Purpose: ensure continuous learning uses the OpenAI-compatible embedding path and parses responses safely.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        )
    )

from continuous_learning import ContinuousLearningPipeline  # noqa: E402


class DummySettings:
    pass


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


async def main_async() -> int:
    with tempfile.TemporaryDirectory(prefix="continuous-learning-embeddings-") as tmpdir:
        os.environ["DATA_DIR"] = tmpdir
        pipeline = ContinuousLearningPipeline(DummySettings(), None, None)

        modern_client = FakeClient(
            {
                "data": [
                    {"embedding": [0.1, 0.2]},
                    {"embedding": [0.3, 0.4]},
                ]
            }
        )
        pipeline.embeddings_client = modern_client
        modern = await pipeline._fetch_embeddings(["first", "second"])
        assert modern == [[0.1, 0.2], [0.3, 0.4]]
        assert modern_client.calls[0]["url"].endswith("/v1/embeddings")
        assert modern_client.calls[0]["json"]["input"] == ["first", "second"]

        legacy_client = FakeClient([[0.5, 0.6]])
        pipeline.embeddings_client = legacy_client
        legacy = await pipeline._fetch_embeddings(["legacy"])
        assert legacy == [[0.5, 0.6]]

    print("PASS: continuous learning embedding fetch uses v1 embeddings and parses responses")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
