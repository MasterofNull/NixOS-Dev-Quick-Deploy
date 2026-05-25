import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("AI_STRICT_ENV", "false")

import memory_manager
from multi_turn_context import MultiTurnContextManager


class _LegacyQdrant:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class _ModernQdrant:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=self.results)


def test_memory_dedup_uses_query_points_when_available():
    modern = _ModernQdrant([SimpleNamespace(score=0.98)])
    memory_manager.init(
        qdrant_client=modern,
        embed_fn=None,
        record_telemetry_fn=lambda *args, **kwargs: None,
        hybrid_search_fn=None,
        tree_search_fn=None,
        memory_collections={},
    )

    assert asyncio.run(memory_manager._check_memory_duplicate("episodic-memory", [0.1, 0.2])) is True
    assert modern.calls[0]["collection_name"] == "episodic-memory"
    assert modern.calls[0]["query"] == [0.1, 0.2]


def test_memory_dedup_falls_back_to_legacy_search():
    legacy = _LegacyQdrant([SimpleNamespace(score=0.98)])
    memory_manager.init(
        qdrant_client=legacy,
        embed_fn=None,
        record_telemetry_fn=lambda *args, **kwargs: None,
        hybrid_search_fn=None,
        tree_search_fn=None,
        memory_collections={},
    )

    assert asyncio.run(memory_manager._check_memory_duplicate("episodic-memory", [0.1, 0.2])) is True
    assert legacy.calls[0]["collection_name"] == "episodic-memory"
    assert legacy.calls[0]["query_vector"] == [0.1, 0.2]


def test_multi_turn_context_uses_query_points_when_available():
    modern = _ModernQdrant([SimpleNamespace(id="p1", score=0.91, payload={"summary": "hit"})])
    modern.get_collection = lambda _: SimpleNamespace(points_count=1)
    manager = MultiTurnContextManager(modern)
    async def _embed_text(_: str):
        return [0.2, 0.3]
    manager.embed_text = _embed_text

    results = asyncio.run(manager.search_all_collections("test", ["codebase-context"], 3))

    assert len(results) == 1
    assert results[0]["id"] == "p1"
    assert modern.calls[0]["query"] == [0.2, 0.3]


def test_multi_turn_context_falls_back_to_legacy_search():
    legacy = _LegacyQdrant([SimpleNamespace(id="p1", score=0.91, payload={"summary": "hit"})])
    legacy.get_collection = lambda _: SimpleNamespace(points_count=1)
    manager = MultiTurnContextManager(legacy)
    async def _embed_text(_: str):
        return [0.2, 0.3]
    manager.embed_text = _embed_text

    results = asyncio.run(manager.search_all_collections("test", ["codebase-context"], 3))

    assert len(results) == 1
    assert results[0]["id"] == "p1"
    assert legacy.calls[0]["query_vector"] == [0.2, 0.3]
