#!/usr/bin/env python3
"""Targeted checks for route-handler collection narrowing policy."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
ROUTE_HANDLER_PATH = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "route_handler.py"
COORDINATOR_DIR = ROUTE_HANDLER_PATH.parent
MCP_SERVERS_DIR = COORDINATOR_DIR.parent

_TESTING_DIR = Path(__file__).parent
if str(_TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTING_DIR))
import _mock_config as _mc  # noqa: E402


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
                LLAMA_CPP_URL=_mc.LLAMA_URL,
                AI_AUTONOMY_MAX_RETRIEVAL_RESULTS=8,
                AI_ROUTE_KEYWORD_POOL_DEFAULT=60,
                AI_ROUTE_KEYWORD_POOL_COMPACT=24,
                AI_ROUTE_KEYWORD_POOL_SINGLE_COLLECTION=16,
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
    spec = importlib.util.spec_from_file_location("route_handler_test_mod", ROUTE_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    route_handler = load_route_handler()
    route_handler._COLLECTIONS = {
        "best-practices": object(),
        "error-solutions": object(),
        "codebase-context": object(),
        "skills-patterns": object(),
        "interaction-history": object(),
        "agent-memory-default": object(),
    }

    continuation_code = route_handler._select_route_collections(
        "continue fixing the failing nixos service after the last patch",
        route="tree",
        context={"memory_recall": ["last patch changed the service path"]},
        generate_response=True,
    )
    assert_true(
        continuation_code["profile"] in {"continuation-code", "continuation-code-memory-first"},
        "expected continuation-code profile",
    )
    assert_true(len(continuation_code["collections"]) <= 2, "expected continuation code path to stay tightly bounded")
    assert_true("codebase-context" in continuation_code["collections"], "expected codebase context for continuation code path")
    assert_true("interaction-history" not in continuation_code["collections"], "expected interaction-history to stay out when memory recall exists")

    continuation_memory_first = route_handler._select_route_collections(
        "continue fixing the failing nixos service after the last patch",
        route="hybrid",
        context={"memory_recall": ["last patch changed the service path"]},
        generate_response=False,
    )
    assert_true(
        continuation_memory_first["profile"] == "continuation-code-memory-first",
        "expected retrieval-only continuation path to prefer memory-first profile",
    )
    assert_true(
        continuation_memory_first["collections"] == ["codebase-context"],
        "expected retrieval-only continuation path to stay on a single codebase collection",
    )
    continuation_memory_pool = route_handler._select_keyword_pool(
        retrieval_profile=continuation_memory_first,
        keyword_limit=5,
        generate_response=False,
    )
    assert_true(continuation_memory_pool == 16, "expected single-collection continuation retrieval to use the tight keyword pool")

    continuation_without_memory = route_handler._select_route_collections(
        "pick up where the last agent left off on the deployment debugging work",
        route="hybrid",
        context={},
        generate_response=False,
    )
    assert_true(
        continuation_without_memory["profile"] in {"continuation-code-compact", "continuation-compact", "continuation-reasoning-compact"},
        "expected continuation retrieval without memory to stay on a compact profile",
    )
    assert_true(
        len(continuation_without_memory["collections"]) == 1,
        "expected compact continuation retrieval without memory to use a single collection",
    )
    continuation_compact_pool = route_handler._select_keyword_pool(
        retrieval_profile=continuation_without_memory,
        keyword_limit=5,
        generate_response=False,
    )
    assert_true(continuation_compact_pool == 16, "expected compact continuation retrieval to use the single-collection keyword pool")

    route_handler._COLLECTIONS = {"best-practices": object(), "codebase-context": object()}
    auto_continuation_route = "auto"
    token_count = len(route_handler._normalize_tokens("pick up where the last agent left off on the deployment debugging work"))
    if token_count <= 3:
        auto_continuation_route = "keyword"
    elif route_handler.Config.AI_TREE_SEARCH_ENABLED and token_count >= 8 and not route_handler._looks_like_continuation_query(
        "pick up where the last agent left off on the deployment debugging work", {}
    ):
        auto_continuation_route = "tree"
    else:
        auto_continuation_route = "hybrid"
    assert_true(auto_continuation_route == "hybrid", "expected continuation auto routing to avoid the tree path")

    route_handler._COLLECTIONS = {
        "best-practices": object(),
        "error-solutions": object(),
        "codebase-context": object(),
        "skills-patterns": object(),
        "interaction-history": object(),
        "agent-memory-default": object(),
    }

    route_handler.task_classifier.classify = lambda query, context, max_output_tokens=200: SimpleNamespace(task_type="lookup")
    lookup = route_handler._select_route_collections(
        "list the california native plants that tolerate shade",
        route="hybrid",
        context={},
        generate_response=False,
    )
    assert_true(lookup["profile"] in {"lookup-focused", "lookup-focused-compact"}, "expected bounded lookup-focused profile")
    assert_true(len(lookup["collections"]) <= 2, "expected lookup path to stay narrowly bounded")
    assert_true("codebase-context" not in lookup["collections"], "expected non-code lookup to avoid codebase context")
    lookup_pool = route_handler._select_keyword_pool(
        retrieval_profile=lookup,
        keyword_limit=5,
        generate_response=False,
    )
    assert_true(lookup_pool == 24, "expected bounded lookup retrieval to use the compact keyword pool")

    route_handler.task_classifier.classify = lambda query, context, max_output_tokens=200: SimpleNamespace(task_type="reasoning")
    reasoning = route_handler._select_route_collections(
        "explain the tradeoffs between broad retrieval and memory recall for long-running repo tasks",
        route="hybrid",
        context={},
        generate_response=True,
    )
    assert_true(reasoning["profile"] in {"reasoning-focused", "reasoning-focused-detailed", "code-focused", "code-focused-detailed"}, "expected bounded reasoning/code-focused profile")
    assert_true("best-practices" in reasoning["collections"], "expected best-practices in reasoning path")
    assert_true("skills-patterns" in reasoning["collections"], "expected skills-patterns in reasoning path")
    reasoning_pool = route_handler._select_keyword_pool(
        retrieval_profile=reasoning,
        keyword_limit=5,
        generate_response=True,
    )
    assert_true(reasoning_pool == 60, "expected synthesis-oriented reasoning retrieval to keep the broader keyword pool")

    print("PASS: Route-handler collection policy stays bounded by task class and continuation context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
