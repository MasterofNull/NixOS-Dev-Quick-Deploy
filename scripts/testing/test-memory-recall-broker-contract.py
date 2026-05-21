#!/usr/bin/env python3
"""Targeted checks for MemoryBroker recall/facts contracts."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import os
os.environ.setdefault("AI_STRICT_ENV", "false")
HC = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(HC))
sys.path.insert(0, str(HC / "knowledge"))

# The extracted handler imports mcp_handlers for unrelated routes. Keep this
# contract test local by stubbing the optional MCP package surface it needs.
mcp_module = types.ModuleType("mcp")
mcp_types_module = types.ModuleType("mcp.types")
class _McpStub:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

mcp_types_module.TextContent = _McpStub
mcp_types_module.Tool = _McpStub
sys.modules.setdefault("mcp", mcp_module)
sys.modules.setdefault("mcp.types", mcp_types_module)

import memory_context_handlers  # noqa: E402
import memory_manager  # noqa: E402


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class FakeBroker:
    def __init__(self):
        self.calls = []

    async def read(self, memory_type, query, top_k=5, include_expired=False, include_superseded=False):
        self.calls.append(memory_type)
        if memory_type == "semantic":
            return [{"memory_id": "sem", "content": "semantic fact", "score": 0.4, "metadata": {"scope": "scripts"}}]
        if memory_type == "procedural":
            return [{"memory_id": "proc", "content": "procedural fact", "score": 0.9, "metadata": {"scope": "procedural"}}]
        return []


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def check_recall_handler_searches_all_types() -> None:
    broker = FakeBroker()
    memory_context_handlers._memory_broker = broker
    memory_context_handlers._PERFORMANCE_PROFILER = type("Profiler", (), {"record_metric": lambda *args, **kwargs: None})()
    response = await memory_context_handlers.handle_memory_recall(
        FakeRequest({"query": "how to run aq-qa", "memory_types": None, "limit": 2})
    )
    payload = response.text
    assert_true('"count": 2' in payload, "expected combined semantic + procedural rows")
    assert_true(broker.calls[:2] == ["semantic", "procedural"], "expected default recall to start with semantic and procedural")
    assert_true('"memory_types"' in payload, "expected response to expose searched memory types")


async def check_memory_rows_preserve_metadata() -> None:
    memory_manager.Config.AI_MEMORY_ENABLED = True
    memory_manager._memory_collections = {"semantic": "agent-memory-semantic"}
    memory_manager._record_telemetry = lambda *args, **kwargs: None

    async def fake_hybrid_search(**kwargs):
        return {
            "combined_results": [
                {
                    "id": "row1",
                    "score": 0.88,
                    "sources": ["qdrant", "lexical"],
                    "payload": {
                        "memory_id": "row1",
                        "memory_type": "semantic",
                        "summary": "aq-report fact",
                        "content": "aq-report uses hybrid telemetry for route_search breadth",
                        "scope": "scripts",
                        "source": "contract-test",
                        "source_agent": "codex",
                        "event_time": "2026-05-20T00:00:00+00:00",
                        "ingestion_time": "2026-05-21T00:00:00+00:00",
                        "supersedes": "row0",
                        "schema_version": "memory.v1",
                        "valid_until": 0,
                    },
                }
            ]
        }

    memory_manager._hybrid_search = fake_hybrid_search
    result = await memory_manager.recall_agent_memory("aq-report telemetry", memory_types=["semantic"], limit=1)
    row = result["results"][0]
    assert_true(row["metadata"]["scope"] == "scripts", "expected payload metadata to be preserved")
    assert_true(row["context"]["scope"] == "scripts", "expected context alias for facts endpoint")
    assert_true(row["source"] == "contract-test", "expected source to be promoted to trace field")
    assert_true(row["source_agent"] == "codex", "expected source_agent to be promoted to trace field")
    assert_true(row["event_time"].startswith("2026-05-20"), "expected event_time trace field")
    assert_true(row["ingestion_time"].startswith("2026-05-21"), "expected ingestion_time trace field")
    assert_true(row["supersedes"] == "row0", "expected supersession trace field")
    assert_true(row["schema_version"] == "memory.v1", "expected schema version trace field")


async def check_retrieval_plan_contract() -> None:
    memory_manager.Config.AI_MEMORY_ENABLED = True
    memory_manager._memory_collections = {"semantic": "agent-memory-semantic"}
    telemetry = []
    memory_manager._record_telemetry = lambda event, payload: telemetry.append((event, payload))

    async def fake_hybrid_search(**kwargs):
        return {
            "combined_results": [
                {
                    "id": "row-plan",
                    "score": 0.77,
                    "payload": {
                        "memory_id": "row-plan",
                        "memory_type": "semantic",
                        "summary": "retrieval plan fact",
                        "content": "retrieval plans expose collections, filters, candidates, and final_k",
                        "valid_from": "2020-01-01T00:00:00+00:00",
                        "valid_until": None,
                    },
                }
            ]
        }

    memory_manager._hybrid_search = fake_hybrid_search
    result = await memory_manager.recall_agent_memory("retrieval plan", memory_types=["semantic"], limit=1)
    plan = result["retrieval_plan"]
    assert_true(plan["schema_version"] == "retrieval_plan.v1", "expected retrieval plan schema")
    assert_true(plan["memory_types"] == ["semantic"], "expected requested memory types")
    assert_true(plan["collections"] == ["agent-memory-semantic"], "expected concrete collection names")
    assert_true(plan["strategies"] == ["hybrid"], "expected hybrid strategy")
    assert_true(plan["filters"]["exclude_expired"] is True, "expected default expiry filter")
    assert_true(plan["candidate_count"] == 1 and plan["final_count"] == 1, "expected candidate/final counts")
    assert_true(plan["final_k"] == 1, "expected final_k")
    assert_true(telemetry[-1][1]["retrieval_plan"]["schema_version"] == "retrieval_plan.v1", "expected telemetry retrieval plan")


async def check_iso_temporal_fields_are_recallable() -> None:
    memory_manager.Config.AI_MEMORY_ENABLED = True
    memory_manager._memory_collections = {"semantic": "agent-memory-semantic"}
    memory_manager._record_telemetry = lambda *args, **kwargs: None

    async def fake_hybrid_search(**kwargs):
        return {
            "combined_results": [
                {
                    "id": "row2",
                    "score": 0.91,
                    "payload": {
                        "memory_id": "row2",
                        "memory_type": "semantic",
                        "summary": "MemoryBroker temporal validity fact",
                        "content": "MemoryBroker accepts ISO valid_from timestamps and recall coerces them to epoch seconds.",
                        "valid_from": "2020-01-01T00:00:00+00:00",
                        "valid_until": None,
                    },
                }
            ]
        }

    memory_manager._hybrid_search = fake_hybrid_search
    result = await memory_manager.recall_agent_memory("MemoryBroker temporal validity", memory_types=["semantic"], limit=1)
    assert_true(len(result["results"]) == 1, "expected ISO valid_from row to survive temporal filtering")
    assert_true(isinstance(result["results"][0]["valid_from"], int), "expected valid_from to be normalized to epoch seconds")


async def main_async() -> int:
    await check_recall_handler_searches_all_types()
    await check_memory_rows_preserve_metadata()
    await check_retrieval_plan_contract()
    await check_iso_temporal_fields_are_recallable()
    print("PASS: MemoryBroker recall contract preserves all-type search and metadata")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
