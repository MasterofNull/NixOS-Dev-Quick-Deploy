#!/usr/bin/env python3
"""Regression checks for bounded per-collection search timeouts."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROUTER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "search_router.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_search_router():
    config_module = types.ModuleType("config")

    class DummyConfig:
        AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = 8
        AI_ROUTE_COLLECTION_SEMANTIC_TIMEOUT_SECONDS = 0.02
        AI_ROUTE_COLLECTION_KEYWORD_TIMEOUT_SECONDS = 0.02

    class DummyRoutingConfig:
        async def get_threshold(self) -> float:
            return 0.5

    config_module.Config = DummyConfig
    config_module.RoutingConfig = DummyRoutingConfig
    sys.modules["config"] = config_module

    metrics_module = types.ModuleType("metrics")

    class DummyCounter:
        def labels(self, **_kwargs):
            return self

        def inc(self):
            return None

    metrics_module.AUTONOMY_BUDGET_EXCEEDED = DummyCounter()
    metrics_module.LLM_BACKEND_SELECTIONS = DummyCounter()
    metrics_module.ROUTE_DECISIONS = DummyCounter()
    metrics_module.ROUTE_ERRORS = DummyCounter()
    sys.modules["metrics"] = metrics_module

    spec = importlib.util.spec_from_file_location("search_router_under_test", SEARCH_ROUTER)
    module = importlib.util.module_from_spec(spec)
    assert_true(spec is not None and spec.loader is not None, "failed to load search_router module")
    spec.loader.exec_module(module)
    return module


class SlowQdrant:
    def query_points(self, **_kwargs):
        time_module = __import__("time")
        time_module.sleep(0.05)
        return types.SimpleNamespace(points=[])

    def scroll(self, **_kwargs):
        time_module = __import__("time")
        time_module.sleep(0.05)
        return ([], None)


async def main() -> int:
    module = load_search_router()

    async def embed_fn(_query: str):
        return [0.1, 0.2, 0.3]

    router = module.SearchRouter(
        qdrant_client=SlowQdrant(),
        embed_fn=embed_fn,
        call_breaker_fn=lambda _name, fn: fn(),
        check_local_health_fn=lambda: True,
        wait_for_model_fn=lambda timeout=30.0: True,
        get_local_loading_fn=lambda: False,
        routing_config=module.RoutingConfig(),
        record_telemetry_fn=lambda *_args, **_kwargs: None,
        collections={"codebase-context": {}},
    )

    result = await router.hybrid_search(
        query="slow query timeout regression",
        collections=["codebase-context"],
        limit=5,
        keyword_limit=5,
        score_threshold=0.7,
    )

    assert_true(result["semantic_results"] == [], "semantic timeout should degrade to empty results")
    assert_true(result["keyword_results"] == [], "keyword timeout should degrade to empty results")
    assert_true(result["combined_results"] == [], "combined results should remain empty on per-collection timeout")
    print("PASS: search router bounds slow per-collection searches")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
