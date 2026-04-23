#!/usr/bin/env python3
"""Regression checks for route_search backend audit classification."""

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
    sys.modules.setdefault("capability_discovery", types.SimpleNamespace(discover=lambda *_a, **_k: {}))
    sys.modules.setdefault(
        "config",
        types.SimpleNamespace(
            Config=types.SimpleNamespace(
                LLAMA_CPP_URL=_mc.LLAMA_URL,
                AI_AUTONOMY_MAX_RETRIEVAL_RESULTS=8,
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
        def __init__(self):
            self.calls = []

        def labels(self, **kwargs):
            self.calls.append(kwargs)
            return self

        def inc(self):
            return None

        def observe(self, _value):
            return None

    metrics = types.SimpleNamespace(
        ROUTE_DECISIONS=_Metric(),
        ROUTE_ERRORS=_Metric(),
        LLM_BACKEND_SELECTIONS=_Metric(),
        LLM_BACKEND_LATENCY=_Metric(),
    )
    sys.modules.setdefault("metrics", metrics)
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
    spec = importlib.util.spec_from_file_location("route_handler_backend_audit_mod", ROUTE_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, metrics


async def _run() -> None:
    route_handler, metrics = load_route_handler()
    route_handler._COLLECTIONS = {"best-practices": object()}
    async def _fake_hybrid_search(*_args, **_kwargs):
        return {
            "combined_results": [
                {"score": 0.82, "collection": "best-practices", "payload": {"content": "stubbed result"}}
            ]
        }

    route_handler._hybrid_search = _fake_hybrid_search
    route_handler._semantic_search = _fake_hybrid_search
    route_handler._keyword_search = _fake_hybrid_search
    route_handler._record_telemetry = lambda *_args, **_kwargs: None
    route_handler._select_backend = None
    route_handler._qdrant_client_ref = lambda: object()
    route_handler._embed_text = lambda _text: [0.1, 0.2]
    route_handler._summarize = lambda results: "stubbed retrieval summary"
    route_handler._record_query_gap = None
    route_handler._postgres_client_ref = lambda: None
    route_handler._llama_cpp_client_ref = lambda: None
    route_handler._switchboard_client_ref = lambda: None
    route_handler._context_compressor_ref = lambda: None
    route_handler._query_expander = None

    result = await route_handler.route_search(
        query="list nixos module options for networking",
        mode="hybrid",
        prefer_local=True,
        context={"source": "test"},
        limit=3,
        keyword_limit=3,
        score_threshold=0.7,
        generate_response=False,
    )

    assert_true(result.get("backend") == "local", "expected retrieval-only route_search to classify as local")
    assert_true(
        any(call.get("backend") == "local" and call.get("reason_class") == "retrieval_only_local" for call in metrics.LLM_BACKEND_SELECTIONS.calls),
        "expected retrieval-only route_search to increment local backend selection metric",
    )


def main() -> int:
    asyncio.run(_run())
    print("PASS: route_search retrieval-only requests record local backend for audit/reporting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
