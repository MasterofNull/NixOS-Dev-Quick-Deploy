import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock


sys.modules["config"] = MagicMock()
sys.modules["metrics"] = MagicMock()

Config = MagicMock()
Config.AI_ROUTE_COLLECTION_SEMANTIC_TIMEOUT_SECONDS = 1.0
Config.AI_ROUTE_COLLECTION_KEYWORD_TIMEOUT_SECONDS = 1.0
Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = 20
Config.AI_TREE_SEARCH_MAX_DEPTH = 1
Config.AI_TREE_SEARCH_BRANCH_FACTOR = 1
Config.AI_MEMORY_MAX_RECALL_ITEMS = 5
sys.modules["config"].Config = Config
sys.modules["config"].RoutingConfig = MagicMock()

import search_router


def test_rerank_combined_results_prefers_specific_path_and_title_matches():
    generic = {
        "collection": "best-practices",
        "id": "1",
        "score": 3.0,
        "payload": {
            "commit_subject": "feat(harness): execute local agent teams in parallel",
            "summary": "workflow execution improvements",
            "category": "feature",
        },
        "source": "keyword",
        "sources": ["keyword"],
    }
    specific = {
        "collection": "codebase-context",
        "id": "2",
        "score": 2.0,
        "payload": {
            "title": "Route handler compact prompt assembly",
            "file_path": "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
            "summary": "reduce prompt assembly size for local fallback summaries",
        },
        "source": "semantic",
        "sources": ["semantic"],
    }

    reranked = search_router.rerank_combined_results(
        "reduce prompt assembly size in route handler fallback summaries",
        [generic, specific],
    )

    assert reranked[0]["id"] == "2"
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


class _FakeQdrant:
    def query_points(self, **_kwargs):
        return SimpleNamespace(points=[])

    def scroll(self, **_kwargs):
        return ([], None)


class _StaticRouter(search_router.SearchRouter):
    async def hybrid_search(self, query: str, collections=None, limit=5, keyword_limit=5, score_threshold=0.7, keyword_pool=60):
        if "route handler" in query.lower():
            return {
                "combined_results": [
                    {
                        "collection": "codebase-context",
                        "id": "specific",
                        "score": 1.0,
                        "payload": {
                            "title": "Route handler compact prompt assembly",
                            "file_path": "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
                            "summary": "reduce prompt assembly size for local fallback summaries",
                        },
                        "source": "semantic",
                        "sources": ["semantic"],
                    },
                    {
                        "collection": "best-practices",
                        "id": "generic",
                        "score": 3.0,
                        "payload": {
                            "commit_subject": "feat(harness): execute local agent teams in parallel",
                            "summary": "workflow execution improvements",
                            "category": "feature",
                        },
                        "source": "keyword",
                        "sources": ["keyword"],
                    },
                ],
                "semantic_results": [],
                "keyword_results": [],
            }
        return {
            "combined_results": [],
            "semantic_results": [],
            "keyword_results": [],
        }


def test_tree_search_reuses_reranker_for_final_ranking():
    router = _StaticRouter(
        qdrant_client=_FakeQdrant(),
        embed_fn=MagicMock(),
        call_breaker_fn=lambda _name, fn: fn(),
        check_local_health_fn=MagicMock(),
        wait_for_model_fn=MagicMock(),
        get_local_loading_fn=lambda: False,
        routing_config=MagicMock(),
        record_telemetry_fn=lambda *args, **kwargs: None,
        collections={"codebase-context": {}, "best-practices": {}},
    )

    result = asyncio.run(
        router.tree_search(
            "reduce prompt assembly size in route handler fallback summaries",
            collections=["codebase-context", "best-practices"],
            limit=2,
            keyword_limit=2,
        )
    )

    assert result["combined_results"][0]["id"] == "specific"


def test_rerank_combined_results_uses_files_changed_as_path_signal():
    generic = {
        "collection": "codebase-context",
        "id": "generic",
        "score": 3.0,
        "payload": {
            "commit_subject": "feat(harness): execute local agent teams in parallel",
            "files_changed": [
                "ai-stack/mcp-servers/hybrid-coordinator/http_server.py",
                ".agent/LOCAL-AGENT-HARNESS-PRIMER.md",
            ],
        },
        "source": "keyword",
        "sources": ["keyword"],
    }
    unrelated = {
        "collection": "codebase-context",
        "id": "unrelated",
        "score": 3.0,
        "payload": {
            "commit_subject": "feat(harness): wire local llm client through switchboard",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/llm_client.py"],
        },
        "source": "keyword",
        "sources": ["keyword"],
    }

    reranked = search_router.rerank_combined_results(
        "http_server workflow routing",
        [unrelated, generic],
    )

    assert reranked[0]["id"] == "generic"
