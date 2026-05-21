#!/usr/bin/env python3
"""Regression tests for GraphRAG knowledge graph search."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from knowledge import graph_search  # noqa: E402


class FakeResponse:
    status_code = 200

    def __init__(self, results):
        self._results = results

    def json(self):
        return {"results": self._results}


class FakeAIDB:
    def __init__(self):
        self.calls = []

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        query = (json or {}).get("query", "")
        if query == "orchestrator":
            return FakeResponse([
                {"id": "1", "metadata": {"subject": "HybridCoordinator", "object": "Qdrant"}},
            ])
        return FakeResponse([
            {"id": f"hop-{query}", "metadata": {"subject": query, "object": "AIDB"}},
        ])


async def main_async() -> int:
    graph_search.init(FakeAIDB(), aidb_api_key="test-key")
    result = await graph_search.graph_search("orchestrator", depth=2, top_k=5)
    assert result["hop_depth"] == 2, result
    assert result["entity_count"] >= 2, result
    assert result["results"], result

    empty = await graph_search.graph_search("", depth=2, top_k=5)
    assert empty.get("error") == "empty_query", empty
    print("PASS: GraphRAG search clamps inputs and expands entity hops")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
