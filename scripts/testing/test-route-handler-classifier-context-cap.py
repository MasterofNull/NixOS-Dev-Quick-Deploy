#!/usr/bin/env python3
"""Regression checks for bounded classifier context in route_handler synthesis routing."""

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
                AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_REASONING=128,
                AI_ROUTE_LOCAL_REASONING_LANE_MIN_TOKENS=360,
                AI_ROUTE_LOCAL_REASONING_LANE_MIN_CONTEXT_TOKENS=850,
                AI_ROUTE_LOCAL_REASONING_LANE_MIN_CONTINUATION_TOKENS=300,
                AI_ROUTE_BOUNDED_REASONING_CONTEXT_CHARS=700,
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
                AI_CONTEXT_COMPRESSION_ENABLED=False,
                AI_CONTEXT_MAX_TOKENS=1200,
                AI_CONTEXT_MAX_TOKENS_LOOKUP=700,
                AI_CONTEXT_MAX_TOKENS_FORMAT=900,
                AI_CONTEXT_MAX_TOKENS_REASONING=1000,
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
    spec = importlib.util.spec_from_file_location("route_handler_classifier_context_cap_mod", ROUTE_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": self.content}}],
            "usage": {"cached_tokens": 8},
        }


class _RecordingClient:
    def __init__(self, content: str = "local reasoning synthesis"):
        self.calls = []
        self.content = content

    async def post(self, path, headers=None, json=None, timeout=None):
        self.calls.append({"path": path, "headers": headers or {}, "json": json or {}, "timeout": timeout})
        return _FakeResponse(self.content)


async def main_async() -> int:
    route_handler = load_route_handler()
    route_handler._COLLECTIONS = {"best-practices": object()}
    route_handler._record_telemetry = lambda *_args, **_kwargs: None
    route_handler._record_query_gap = None
    route_handler._query_expander = None
    route_handler._context_compressor_ref = lambda: None
    route_handler._postgres_client_ref = lambda: None
    route_handler._summarize = lambda _results: "large context summary"
    large_context = "cache reuse keeps repeated local requests cheap. " * 200
    route_handler._hybrid_search = lambda **_kwargs: asyncio.sleep(
        0,
        result={
            "combined_results": [{"score": 0.9, "collection": "best-practices", "content": large_context}],
            "keyword_results": [],
            "semantic_results": [],
        },
    )

    local_client = _RecordingClient(content="generic local synthesis")
    reasoning_client = _RecordingClient(content="reasoning lane synthesis")
    remote_client = _RecordingClient(content="remote synthesis")
    route_handler._llama_cpp_client_ref = lambda: local_client
    route_handler._llama_cpp_reasoning_client_ref = lambda: reasoning_client
    route_handler._switchboard_client_ref = lambda: remote_client

    result = await route_handler.route_search(
        query="explain how cache reuse reduces repeated query latency",
        mode="hybrid",
        prefer_local=True,
        context={"source": "test"},
        limit=3,
        keyword_limit=3,
        score_threshold=0.7,
        generate_response=True,
    )

    assert_true(result.get("backend") == "local", "expected bounded reasoning with large retrieval context to stay local")
    assert_true(result.get("local_inference_lane") == "default", "expected bounded reasoning to demote to the default local lane")
    assert_true(
        result.get("local_inference_lane_reason") == "bounded_reasoning_default_lane",
        "expected bounded reasoning lane demotion reason",
    )
    assert_true(len(reasoning_client.calls) == 0, "expected bounded reasoning to avoid the dedicated reasoning lane")
    assert_true(len(local_client.calls) == 1, "expected generic local client to handle bounded reasoning tasks")
    assert_true(len(remote_client.calls) == 0, "expected no remote synthesis call")
    assert_true(
        int((local_client.calls[0].get("json") or {}).get("max_tokens", 0)) == 128,
        "expected reasoning tasks to use the reduced local reasoning output budget",
    )
    bounded_prompt = str((((local_client.calls[0].get("json") or {}).get("messages") or [])[-1]).get("content", ""))
    assert_true(
        len(bounded_prompt) < 2200,
        "expected bounded reasoning default-lane prompt context to stay compact",
    )
    assert_true(
        "Provide a concise response using only the strongest context." in bounded_prompt,
        "expected bounded reasoning default-lane prompt to use the tighter route-level guidance",
    )
    assert_true(
        "keep the answer under 120 words" in bounded_prompt,
        "expected bounded reasoning default-lane prompt to enforce a compact answer contract",
    )

    continuation_local_client = _RecordingClient(content="continuation local synthesis")
    continuation_reasoning_client = _RecordingClient(content="continuation reasoning lane synthesis")
    route_handler._llama_cpp_client_ref = lambda: continuation_local_client
    route_handler._llama_cpp_reasoning_client_ref = lambda: continuation_reasoning_client
    route_handler._hybrid_search = lambda **_kwargs: asyncio.sleep(
        0,
        result={
            "combined_results": [{"score": 0.9, "collection": "best-practices", "content": "extended cache analysis context " * 220}],
            "keyword_results": [],
            "semantic_results": [],
        },
    )

    continuation_result = await route_handler.route_search(
        query="continue analyzing the current issue using the prior context and explain why the cache is slow",
        mode="hybrid",
        prefer_local=True,
        context={"source": "test"},
        limit=3,
        keyword_limit=3,
        score_threshold=0.7,
        generate_response=True,
    )

    assert_true(continuation_result.get("local_inference_lane") == "reasoning", "expected continuation reasoning to keep the dedicated lane")
    assert_true(
        continuation_result.get("local_inference_lane_reason") == "continuation_reasoning_lane",
        "expected continuation reasoning lane reason",
    )
    assert_true(len(continuation_reasoning_client.calls) == 1, "expected continuation reasoning to use the reasoning lane")
    assert_true(len(continuation_local_client.calls) == 0, "expected continuation reasoning to skip the default lane")

    light_continuation_local_client = _RecordingClient(content="light continuation default synthesis")
    light_continuation_reasoning_client = _RecordingClient(content="light continuation reasoning synthesis")
    route_handler._llama_cpp_client_ref = lambda: light_continuation_local_client
    route_handler._llama_cpp_reasoning_client_ref = lambda: light_continuation_reasoning_client
    route_handler._hybrid_search = lambda **_kwargs: asyncio.sleep(
        0,
        result={
            "combined_results": [{"score": 0.9, "collection": "best-practices", "content": "short cache note " * 3}],
            "keyword_results": [],
            "semantic_results": [],
        },
    )

    light_continuation_result = await route_handler.route_search(
        query="continue analyzing the current cache issue",
        mode="hybrid",
        prefer_local=True,
        context={"source": "test"},
        limit=3,
        keyword_limit=3,
        score_threshold=0.7,
        generate_response=True,
    )

    assert_true(light_continuation_result.get("local_inference_lane") == "default", "expected light continuation to stay on the default lane")
    assert_true(
        light_continuation_result.get("local_inference_lane_reason") == "default_local_lane",
        "expected light continuation lane reason",
    )
    assert_true(len(light_continuation_reasoning_client.calls) == 0, "expected light continuation to avoid the reasoning lane")
    assert_true(len(light_continuation_local_client.calls) == 1, "expected light continuation to use the default local lane")

    print("PASS: route_handler selects the dedicated reasoning lane only for continuation/heavier local reasoning")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
