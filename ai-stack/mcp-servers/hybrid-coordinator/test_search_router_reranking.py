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


def test_keyword_match_score_penalizes_docs_only_hits_for_technical_queries():
    docs_heavy = {
        "payload": {
            "commit_subject": "docs(agent): add git workflow discipline to local agent primer",
            "files_changed": [".agent/LOCAL-AGENT-HARNESS-PRIMER.md"],
            "diff_preview": "document local workflow discipline and primer guidance",
        },
        "source": "keyword",
    }
    technical = {
        "payload": {
            "commit_subject": "feat(harness): execute local agent teams in parallel",
            "files_changed": [
                "ai-stack/mcp-servers/hybrid-coordinator/http_server.py",
                "ai-stack/mcp-servers/hybrid-coordinator/search_router.py",
            ],
            "diff_preview": "improve local routing and query execution for hybrid coordinator cache behavior",
        },
        "source": "keyword",
    }

    docs_matched, docs_score = search_router.keyword_match_score(
        "local routing cache query latency",
        docs_heavy,
    )
    tech_matched, tech_score = search_router.keyword_match_score(
        "local routing cache query latency",
        technical,
    )

    assert docs_matched is True
    assert tech_matched is True
    assert tech_score > docs_score


def test_keyword_match_score_prefers_keyword_hints_for_runtime_terms():
    matched, score = search_router.keyword_match_score(
        "switchboard routing cache",
        {
            "payload": {
                "commit_subject": "feat: tune runtime behavior",
                "keyword_hints": ["switchboard", "routing", "cache", "hybrid-coordinator"],
                "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/http_server.py"],
            },
            "source": "keyword",
        },
    )

    assert matched is True
    assert score > 1.5


def test_keyword_match_score_penalizes_doc_heavy_mixed_commits():
    mixed = {
        "payload": {
            "commit_subject": "feat(harness): execute local agent teams in parallel",
            "files_changed": [
                ".agent/LOCAL-AGENT-HARNESS-PRIMER.md",
                ".agents/plans/phase-2-workflow-engine.md",
                "ai-stack/mcp-servers/hybrid-coordinator/http_server.py",
            ],
            "diff_preview": "route query cache local latency improvements",
        },
        "source": "keyword",
    }
    focused = {
        "payload": {
            "commit_subject": "feat: improve route search cache behavior",
            "files_changed": [
                "ai-stack/mcp-servers/hybrid-coordinator/search_router.py",
                "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
            ],
            "diff_preview": "route query cache local latency improvements",
        },
        "source": "keyword",
    }

    mixed_matched, mixed_score = search_router.keyword_match_score(
        "local routing cache query latency",
        mixed,
    )
    focused_matched, focused_score = search_router.keyword_match_score(
        "local routing cache query latency",
        focused,
    )

    assert mixed_matched is True
    assert focused_matched is True
    assert focused_score > mixed_score


def test_keyword_match_score_penalizes_validation_noise_for_technical_queries():
    noisy = {
        "payload": {
            "commit_subject": "fix: tune route handler retrieval quality",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/route_handler.py"],
            "diff_preview": "run pytest tier0-validation-gate --pre-commit after route cache change",
        },
        "source": "keyword",
    }
    focused = {
        "payload": {
            "commit_subject": "fix: tune route handler retrieval quality",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/route_handler.py"],
            "diff_preview": "reduce route cache latency by compacting retrieval context",
        },
        "source": "keyword",
    }

    noisy_matched, noisy_score = search_router.keyword_match_score(
        "route cache latency",
        noisy,
    )
    focused_matched, focused_score = search_router.keyword_match_score(
        "route cache latency",
        focused,
    )

    assert noisy_matched is True
    assert focused_matched is True
    assert focused_score > noisy_score


def test_keyword_match_score_boosts_direct_runtime_paths_over_broad_runtime_files():
    broad = {
        "payload": {
            "commit_subject": "feat: improve runtime routing behavior",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py"],
            "diff_preview": "reduce route cache latency in local runtime",
        },
        "source": "keyword",
    }
    direct = {
        "payload": {
            "commit_subject": "fix: compact route search cache prompts",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/route_handler.py"],
            "diff_preview": "reduce route cache latency in local runtime",
        },
        "source": "keyword",
    }

    broad_matched, broad_score = search_router.keyword_match_score(
        "local route cache latency",
        broad,
    )
    direct_matched, direct_score = search_router.keyword_match_score(
        "local route cache latency",
        direct,
    )

    assert broad_matched is True
    assert direct_matched is True
    assert direct_score > broad_score


def test_rerank_combined_results_prefers_direct_route_stack_files():
    broad = {
        "collection": "codebase-context",
        "id": "broad",
        "score": 4.2,
        "payload": {
            "commit_subject": "feat: improve runtime routing behavior",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py"],
            "diff_preview": "reduce route cache latency in local runtime",
        },
        "source": "keyword",
        "sources": ["keyword"],
    }
    direct = {
        "collection": "codebase-context",
        "id": "direct",
        "score": 3.9,
        "payload": {
            "commit_subject": "fix: compact route search cache prompts",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/search_router.py"],
            "diff_preview": "reduce route cache latency in local runtime",
        },
        "source": "keyword",
        "sources": ["keyword"],
    }

    reranked = search_router.rerank_combined_results(
        "what reduces repeated query latency in the local route stack",
        [broad, direct],
    )

    assert reranked[0]["id"] == "direct"


def test_keyword_match_score_penalizes_route_stack_distractors_and_doc_heavy_mixes():
    distractor = {
        "payload": {
            "commit_subject": "feat(harness): wire local llm client through switchboard",
            "files_changed": [
                ".agent/LOCAL-AGENT-HARNESS-PRIMER.md",
                ".agents/plans/ai-harness-enhancement-roadmap.md",
                "ai-stack/mcp-servers/hybrid-coordinator/llm_client.py",
            ],
            "diff_preview": "reduce repeated query latency in the local route stack",
        },
        "source": "keyword",
    }
    owner = {
        "payload": {
            "commit_subject": "fix: compact route search cache prompts",
            "files_changed": [
                "ai-stack/mcp-servers/hybrid-coordinator/search_router.py",
                "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
            ],
            "diff_preview": "reduce repeated query latency in the local route stack",
        },
        "source": "keyword",
    }

    distractor_matched, distractor_score = search_router.keyword_match_score(
        "what reduces repeated query latency in the local route stack",
        distractor,
    )
    owner_matched, owner_score = search_router.keyword_match_score(
        "what reduces repeated query latency in the local route stack",
        owner,
    )

    assert distractor_matched is True
    assert owner_matched is True
    assert owner_score > distractor_score


def test_rerank_combined_results_demotes_route_stack_distractors():
    distractor = {
        "collection": "codebase-context",
        "id": "distractor",
        "score": 4.4,
        "payload": {
            "commit_subject": "feat(harness): wire local llm client through switchboard",
            "files_changed": [
                ".agent/LOCAL-AGENT-HARNESS-PRIMER.md",
                ".agents/plans/ai-harness-enhancement-roadmap.md",
                "ai-stack/mcp-servers/hybrid-coordinator/llm_client.py",
            ],
            "diff_preview": "reduce repeated query latency in the local route stack",
        },
        "source": "keyword",
        "sources": ["keyword"],
    }
    owner = {
        "collection": "codebase-context",
        "id": "owner",
        "score": 3.7,
        "payload": {
            "commit_subject": "fix: compact route search cache prompts",
            "files_changed": ["ai-stack/mcp-servers/hybrid-coordinator/search_router.py"],
            "diff_preview": "reduce repeated query latency in the local route stack",
        },
        "source": "keyword",
        "sources": ["keyword"],
    }

    reranked = search_router.rerank_combined_results(
        "what reduces repeated query latency in the local route stack",
        [distractor, owner],
    )

    assert reranked[0]["id"] == "owner"


def test_expanded_query_for_search_adds_route_stack_owner_hints():
    query = "what reduces repeated query latency in the local route stack"
    expanded = search_router._expanded_query_for_search(
        query,
        search_router.normalize_tokens(query),
    )

    assert "route_handler" in expanded
    assert "search_router" in expanded
    assert "semantic_cache" in expanded


def test_expanded_query_for_search_leaves_non_route_queries_unchanged():
    query = "switchboard auth failure"
    expanded = search_router._expanded_query_for_search(
        query,
        search_router.normalize_tokens(query),
    )

    assert expanded == query
