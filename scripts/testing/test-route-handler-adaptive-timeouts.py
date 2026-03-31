#!/usr/bin/env python3
"""Regression checks for retrieval-only adaptive timeout caps in route_handler."""

from __future__ import annotations

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
    sys.modules.setdefault("capability_discovery", types.SimpleNamespace())
    sys.modules.setdefault(
        "config",
        types.SimpleNamespace(
            Config=types.SimpleNamespace(
                LLAMA_CPP_URL="http://127.0.0.1:8080",
                AI_AUTONOMY_MAX_RETRIEVAL_RESULTS=8,
                AI_ROUTE_KEYWORD_POOL_DEFAULT=60,
                AI_ROUTE_KEYWORD_POOL_COMPACT=24,
                AI_ROUTE_KEYWORD_POOL_SINGLE_COLLECTION=16,
                AI_ROUTE_TIMEOUT_RETRIEVAL_KEYWORD_SECONDS=4.0,
                AI_ROUTE_TIMEOUT_RETRIEVAL_HYBRID_SECONDS=6.0,
                AI_ROUTE_TIMEOUT_RETRIEVAL_COMPLEX_SECONDS=8.0,
                AI_LLM_EXPANSION_ENABLED=False,
                AI_LLM_EXPANSION_TIMEOUT_S=2,
                AI_TREE_SEARCH_ENABLED=True,
                AI_CAPABILITY_DISCOVERY_ON_QUERY=False,
                AI_PROMPT_CACHE_POLICY_ENABLED=False,
                AI_CONTEXT_COMPRESSION_ENABLED=False,
                AI_CONTEXT_MAX_TOKENS=1200,
                LLAMA_CPP_INFERENCE_TIMEOUT=5,
                AI_TASK_CLASSIFICATION_ENABLED=False,
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
    spec = importlib.util.spec_from_file_location("route_handler_adaptive_timeout_mod", ROUTE_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    route_handler = load_route_handler()

    assert_true(
        route_handler.calculate_adaptive_timeout("test", "keyword", 3, generate_response=False) == 4.0,
        "expected retrieval-only keyword route to use the tighter 4s timeout",
    )
    assert_true(
        route_handler.calculate_adaptive_timeout("test query foo bar", "hybrid", 5, generate_response=False) == 6.0,
        "expected retrieval-only hybrid route to use the tighter 6s timeout",
    )
    assert_true(
        route_handler.calculate_adaptive_timeout(
            "very long test query with many tokens for complex analysis",
            "tree",
            10,
            generate_response=False,
        ) == 8.0,
        "expected retrieval-only complex route to use the tighter 8s timeout",
    )
    assert_true(
        route_handler.calculate_adaptive_timeout("test query foo bar", "hybrid", 5, generate_response=True) == 10.0,
        "expected synthesis-enabled hybrid route to keep the 10s timeout",
    )
    assert_true(
        route_handler.calculate_adaptive_timeout(
            "very long test query with many tokens for complex analysis",
            "tree",
            10,
            generate_response=True,
        ) == 15.0,
        "expected synthesis-enabled complex route to keep the 15s timeout",
    )

    print("PASS: route_handler caps retrieval-only adaptive timeouts without changing synthesis budgets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
