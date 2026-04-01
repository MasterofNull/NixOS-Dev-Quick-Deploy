#!/usr/bin/env python3
"""Regression checks for task-scoped context compression budgets in route_handler."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE_HANDLER_PATH = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "route_handler.py"
COORDINATOR_DIR = ROUTE_HANDLER_PATH.parent
MCP_SERVERS_DIR = COORDINATOR_DIR.parent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_route_handler():
    os.environ.setdefault("AI_STRICT_ENV", "false")
    if str(COORDINATOR_DIR) not in sys.path:
        sys.path.insert(0, str(COORDINATOR_DIR))
    if str(MCP_SERVERS_DIR) not in sys.path:
        sys.path.insert(0, str(MCP_SERVERS_DIR))
    sys.modules.setdefault(
        "capability_discovery",
        types.SimpleNamespace(format_context=lambda _data: ""),
    )
    sys.modules.setdefault(
        "config",
        types.SimpleNamespace(
            Config=types.SimpleNamespace(
                LLAMA_CPP_URL="http://127.0.0.1:8080",
                SWITCHBOARD_URL="http://127.0.0.1:8085",
                AI_AUTONOMY_MAX_RETRIEVAL_RESULTS=8,
                AI_ROUTE_KEYWORD_POOL_DEFAULT=60,
                AI_ROUTE_KEYWORD_POOL_COMPACT=24,
                AI_ROUTE_KEYWORD_POOL_SINGLE_COLLECTION=16,
                AI_ROUTE_CLASSIFIER_CONTEXT_CHARS=1200,
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS=240,
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_LOOKUP=96,
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_FORMAT=160,
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_REASONING=192,
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_SYNTHESIZE=160,
                AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS=400,
                AI_ROUTE_TIMEOUT_RETRIEVAL_KEYWORD_SECONDS=4.0,
                AI_ROUTE_TIMEOUT_RETRIEVAL_HYBRID_SECONDS=6.0,
                AI_ROUTE_TIMEOUT_RETRIEVAL_COMPLEX_SECONDS=8.0,
                AI_LLM_EXPANSION_ENABLED=False,
                AI_LLM_EXPANSION_TIMEOUT_S=2,
                AI_TREE_SEARCH_ENABLED=True,
                AI_CAPABILITY_DISCOVERY_ON_QUERY=False,
                AI_PROMPT_CACHE_POLICY_ENABLED=False,
                AI_PROMPT_CACHE_STATIC_PREFIX="",
                AI_CONTEXT_COMPRESSION_ENABLED=True,
                AI_CONTEXT_MAX_TOKENS=1200,
                AI_CONTEXT_MAX_TOKENS_LOOKUP=700,
                AI_CONTEXT_MAX_TOKENS_FORMAT=900,
                AI_CONTEXT_MAX_TOKENS_REASONING=1600,
                AI_CONTEXT_MAX_TOKENS_SYNTHESIZE=1200,
                LLAMA_CPP_INFERENCE_TIMEOUT=5,
                AI_TASK_CLASSIFICATION_ENABLED=True,
                AI_SPECULATIVE_DECODING_ENABLED=False,
                AI_SPECULATIVE_DECODING_MODE="off",
                build_local_system_prompt=lambda: "",
            )
        ),
    )

    class _Metric:
        def labels(self, **_kwargs):
            return self

        def inc(self):
            return None

        def observe(self, _value):
            return None

    sys.modules.setdefault(
        "metrics",
        types.SimpleNamespace(
            ROUTE_DECISIONS=_Metric(),
            ROUTE_ERRORS=_Metric(),
            LLM_BACKEND_SELECTIONS=_Metric(),
            LLM_BACKEND_LATENCY=_Metric(),
        ),
    )
    sys.modules.setdefault(
        "search_router",
        types.SimpleNamespace(
            looks_like_sql=lambda _query: False,
            normalize_tokens=lambda text: [token for token in str(text).lower().split() if token],
        ),
    )
    sys.modules.setdefault("query_expansion", types.SimpleNamespace(QueryExpander=lambda _url: object()))
    sys.modules.setdefault(
        "prompt_injection",
        types.SimpleNamespace(
            PromptInjectionScanner=lambda: types.SimpleNamespace(filter_results=lambda results, content_key="content": (results, 0)),
            sanitize_query=lambda text: text,
        ),
    )
    spec = importlib.util.spec_from_file_location("route_handler_context_budget_mod", ROUTE_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": "lookup synthesis"}}],
            "usage": {"cached_tokens": 4},
        }


class _RecordingClient:
    async def post(self, path, headers=None, json=None, timeout=None):
        return _FakeResponse()


class _RecordingCompressor:
    def __init__(self):
        self.calls = []

    def compress_to_budget(self, *, contexts, max_tokens, strategy):
        self.calls.append({"max_tokens": max_tokens, "strategy": strategy, "contexts": contexts})
        return ("compressed lookup context", ["route-results"], max_tokens)


async def main_async() -> int:
    route_handler = load_route_handler()
    route_handler._COLLECTIONS = {"best-practices": object()}
    route_handler._record_telemetry = lambda *_args, **_kwargs: None
    route_handler._record_query_gap = None
    route_handler._query_expander = None
    route_handler._postgres_client_ref = lambda: None
    route_handler._summarize = lambda _results: ("lookup context " * 400)
    route_handler._hybrid_search = lambda **_kwargs: asyncio.sleep(
        0,
        result={
            "combined_results": [{"score": 0.9, "collection": "best-practices", "content": "lookup context " * 400}],
            "keyword_results": [],
            "semantic_results": [],
        },
    )
    route_handler._llama_cpp_client_ref = lambda: _RecordingClient()
    route_handler._switchboard_client_ref = lambda: _RecordingClient()
    compressor = _RecordingCompressor()
    route_handler._context_compressor_ref = lambda: compressor

    result = await route_handler.route_search(
        query="what is the local cache hit rate target",
        mode="hybrid",
        prefer_local=True,
        context={"source": "test"},
        limit=3,
        keyword_limit=3,
        score_threshold=0.7,
        generate_response=True,
    )

    context_compression = result.get("results", {}).get("context_compression") or {}
    assert_true(compressor.calls, "expected context compressor to run for oversized lookup synthesis")
    assert_true(compressor.calls[-1]["max_tokens"] == 700, "expected lookup synthesis to use the tighter lookup context budget")
    assert_true(context_compression.get("token_budget") == 700, "expected reported context budget to match lookup compression budget")

    print("PASS: route_handler uses tighter context budgets for lookup synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
