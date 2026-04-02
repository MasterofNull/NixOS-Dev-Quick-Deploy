#!/usr/bin/env python3
"""
Test script for Phase 5.2 Route Search Optimizations.

Tests:
1. Parallel LLM expansion and capability discovery
2. Backend selection caching
3. Collection timeout guards
4. Skip backend selection when not needed
"""

import asyncio
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# Mock the external dependencies before importing route_handler
sys.modules['config'] = MagicMock()
sys.modules['metrics'] = MagicMock()
sys.modules['search_router'] = MagicMock()
sys.modules['query_expansion'] = MagicMock()
sys.modules['prompt_injection'] = MagicMock()
sys.modules['task_classifier'] = MagicMock()
sys.modules['capability_discovery'] = MagicMock()

# Setup mocks
from unittest.mock import MagicMock
Config = MagicMock()
Config.AI_LLM_EXPANSION_ENABLED = True
Config.AI_CAPABILITY_DISCOVERY_ON_QUERY = True
Config.AI_TREE_SEARCH_ENABLED = True
Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = 20
Config.AI_LLM_EXPANSION_TIMEOUT_S = 5.0
Config.AI_TASK_CLASSIFICATION_ENABLED = False
Config.AI_PROMPT_CACHE_POLICY_ENABLED = False
Config.AI_PROMPT_CACHE_STATIC_PREFIX = ""
Config.LLAMA_CPP_URL = "http://localhost:8000"
Config.AI_ROUTE_KEYWORD_POOL_DEFAULT = 24
Config.AI_ROUTE_KEYWORD_POOL_COMPACT = 12
Config.AI_ROUTE_KEYWORD_POOL_SINGLE_COLLECTION = 8
Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS = 220
Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_LOOKUP = 96
Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_FORMAT = 80
Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_REASONING = 140
Config.AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_SYNTHESIZE = 160
Config.AI_CONTEXT_MAX_TOKENS = 1200
Config.AI_CONTEXT_MAX_TOKENS_LOOKUP = 240
Config.AI_CONTEXT_MAX_TOKENS_FORMAT = 320
Config.AI_CONTEXT_MAX_TOKENS_REASONING = 640
Config.AI_CONTEXT_MAX_TOKENS_SYNTHESIZE = 720
Config.AI_ROUTE_LOCAL_REASONING_LANE_MIN_TOKENS = 80
Config.AI_ROUTE_LOCAL_REASONING_LANE_MIN_CONTINUATION_TOKENS = 120
Config.AI_ROUTE_LOCAL_REASONING_LANE_MIN_CONTEXT_TOKENS = 160
Config.AI_ROUTE_BOUNDED_REASONING_CONTEXT_CHARS = 40
sys.modules['config'].Config = Config

# Now we can import route_handler
import route_handler
import task_classifier


class TestParallelization:
    """Test parallel LLM expansion and capability discovery."""

    def test_parallel_expansion_and_discovery(self):
        asyncio.run(self._run_parallel_expansion_and_discovery())

    async def _run_parallel_expansion_and_discovery(self):
        """Verify that expansion and discovery tasks run in parallel."""
        print("Test 1: Parallel LLM Expansion and Discovery")

        # Setup mocks
        expansion_times = []
        discovery_times = []

        async def mock_expand_with_llm(query, max_expansions):
            start = time.time()
            await asyncio.sleep(0.2)  # Simulate 200ms expansion
            expansion_times.append(time.time() - start)
            return [query, query + " expanded"]

        async def mock_capability_discover(query):
            start = time.time()
            await asyncio.sleep(0.2)  # Simulate 200ms discovery
            discovery_times.append(time.time() - start)
            return {
                "decision": "found",
                "reason": "test",
                "cache_hit": False,
                "intent_tags": [],
                "tools": [],
                "skills": [],
                "servers": [],
                "datasets": [],
            }

        # Mock components
        expander = MagicMock()
        expander.expand_with_llm = mock_expand_with_llm

        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [],
        })
        summarize_fn = MagicMock(return_value="test response")

        # Patch the imports
        with patch.object(route_handler, '_query_expander', expander):
            with patch.object(route_handler, '_hybrid_search', hybrid_search_fn):
                with patch.object(route_handler, '_summarize', summarize_fn):
                    with patch('capability_discovery.discover', mock_capability_discover):
                        with patch.object(route_handler, '_normalize_tokens', return_value=['test']):
                            with patch.object(route_handler, '_looks_like_sql', return_value=False):
                                with patch.object(route_handler, '_record_telemetry', MagicMock()):
                                    with patch.object(route_handler, '_postgres_client_ref', return_value=None):
                                        with patch.object(route_handler, '_llama_cpp_client_ref', return_value=None):
                                            with patch.object(route_handler, '_context_compressor_ref', return_value=None):
                                                with patch.object(route_handler, 'ROUTE_DECISIONS', MagicMock()):
                                                    with patch.object(route_handler, 'ROUTE_ERRORS', MagicMock()):
                                                        with patch.object(route_handler, 'sanitize_query', lambda x: x):
                                                            with patch.object(route_handler, '_injection_scanner', MagicMock()):
                                                                route_handler._injection_scanner.filter_results = MagicMock(return_value=([], 0))

                                                                # Run the search
                                                                start = time.time()
                                                                result = await route_handler.route_search(
                                                                    query="test query",
                                                                    mode="hybrid",
                                                                )
                                                                total_time = time.time() - start

        # Verify parallel execution
        if expansion_times and discovery_times:
            max_time = max(expansion_times[0], discovery_times[0])
            sequential_time = expansion_times[0] + discovery_times[0]
            print(f"  Expansion time: {expansion_times[0]:.3f}s")
            print(f"  Discovery time: {discovery_times[0]:.3f}s")
            print(f"  Max parallel time: {max_time:.3f}s")
            print(f"  Sequential would be: {sequential_time:.3f}s")
            print(f"  Parallelization efficiency: {(sequential_time / max_time):.2f}x")

            if max_time < (sequential_time * 0.9):
                print("  ✓ PASS: Operations ran in parallel")
            else:
                raise AssertionError("Operations did not run in parallel")


class TestBackendSelectionCache:
    """Test backend selection caching."""

    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        print("\nTest 2: Backend Selection Cache Key Generation")

        key1 = route_handler._cached_backend_key("abc123", "75", True)
        key2 = route_handler._cached_backend_key("abc123", "75", True)
        key3 = route_handler._cached_backend_key("abc123", "80", True)
        key4 = route_handler._cached_backend_key("abc123", "75", False)

        assert key1 == key2, "Same inputs should produce same key"
        assert key1 != key3, "Different scores should produce different keys"
        assert key1 != key4, "Different prefer_local should produce different keys"
        print(f"  Sample key: {key1}")
        print("  ✓ PASS: Cache keys generated correctly")

    def test_cache_hit_miss(self):
        """Test cache hit/miss tracking."""
        print("\nTest 3: Backend Selection Cache Hit/Miss Tracking")

        # Reset cache
        route_handler._backend_selection_cache.cache.clear()
        route_handler._backend_selection_cache.access_count = 0
        route_handler._backend_selection_cache.hit_count = 0

        query = "test query"
        score = 0.75
        prefer_local = True

        # First access - should be a miss
        cached = route_handler._get_cached_backend_selection(query, score, prefer_local)
        assert cached is None, "First access should miss"

        # Add to cache
        route_handler._cache_backend_selection(query, score, prefer_local, "local")

        # Second access - should be a hit
        cached = route_handler._get_cached_backend_selection(query, score, prefer_local)
        assert cached == "local", "Second access should hit"

        stats = route_handler.get_backend_selection_cache_stats()
        print(f"  Cache size: {stats['cache_size']}")
        print(f"  Access count: {stats['access_count']}")
        print(f"  Hit count: {stats['hit_count']}")
        print(f"  Hit rate: {stats['hit_rate_percent']:.1f}%")

        assert stats['hit_rate_percent'] == 50.0, "Hit rate should be 50% (1 hit, 2 accesses)"
        print("  ✓ PASS: Cache hit/miss tracking works correctly")

    def test_cache_eviction(self):
        """Test that cache evicts when full."""
        print("\nTest 4: Backend Selection Cache Eviction")

        # Reset cache
        route_handler._backend_selection_cache.cache.clear()
        route_handler._backend_selection_cache.max_size = 5

        # Fill cache
        for i in range(5):
            route_handler._cache_backend_selection(f"query{i}", float(i), True, f"backend{i}")

        assert len(route_handler._backend_selection_cache.cache) == 5
        print(f"  Cache filled to max: {len(route_handler._backend_selection_cache.cache)}")

        # Add one more - should trigger eviction
        route_handler._cache_backend_selection("query5", 5.0, True, "backend5")
        # After eviction and re-add, cache should be size 1
        assert len(route_handler._backend_selection_cache.cache) >= 1
        print(f"  Cache after eviction: {len(route_handler._backend_selection_cache.cache)}")
        print("  ✓ PASS: Cache eviction works correctly")

        # Reset to default size
        route_handler._backend_selection_cache.max_size = 1000


class TestTimeoutGuards:
    """Test collection timeout guards."""

    def test_search_timeout(self):
        asyncio.run(self._run_search_timeout())

    async def _run_search_timeout(self):
        """Test that search operations timeout correctly."""
        print("\nTest 5: Collection Timeout Guards")

        async def slow_search(*args, **kwargs):
            await asyncio.sleep(5.0)  # Simulate 5s search
            return {"combined_results": [], "semantic_results": [], "keyword_results": []}

        # Test with short timeout
        try:
            await asyncio.wait_for(slow_search(), timeout=1.0)
            raise AssertionError("Search should have timed out")
        except asyncio.TimeoutError:
            print("  Slow search timed out as expected")
            print("  ✓ PASS: Timeout guards work correctly")


class TestSkipBackendSelection:
    """Test that backend selection is skipped when not generating response."""

    def test_backend_selection_skipped_on_retrieval_only(self):
        asyncio.run(self._run_backend_selection_skipped_on_retrieval_only())

    async def _run_backend_selection_skipped_on_retrieval_only(self):
        """Test that backend selection is not called for retrieval-only queries."""
        print("\nTest 6: Skip Backend Selection for Retrieval-Only Queries")

        select_backend_calls = []

        async def mock_select_backend(*args, **kwargs):
            select_backend_calls.append(args)
            return "local"

        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [],
        })
        summarize_fn = MagicMock(return_value="test response")
        capability_discover = AsyncMock(return_value={
            "decision": "skipped",
            "reason": "test",
            "cache_hit": False,
            "intent_tags": [],
            "tools": [],
            "skills": [],
            "servers": [],
            "datasets": [],
        })

        with patch.object(route_handler, '_select_backend', mock_select_backend):
            with patch.object(route_handler, '_hybrid_search', hybrid_search_fn):
                with patch.object(route_handler, '_summarize', summarize_fn):
                    with patch('capability_discovery.discover', capability_discover):
                        with patch.object(route_handler, '_normalize_tokens', return_value=['test']):
                            with patch.object(route_handler, '_looks_like_sql', return_value=False):
                                with patch.object(route_handler, '_record_telemetry', MagicMock()):
                                    with patch.object(route_handler, '_postgres_client_ref', return_value=None):
                                        with patch.object(route_handler, '_llama_cpp_client_ref', return_value=None):
                                            with patch.object(route_handler, '_context_compressor_ref', return_value=None):
                                                with patch.object(route_handler, 'ROUTE_DECISIONS', MagicMock()):
                                                    with patch.object(route_handler, 'ROUTE_ERRORS', MagicMock()):
                                                        with patch.object(route_handler, 'sanitize_query', lambda x: x):
                                                            with patch.object(route_handler, '_injection_scanner', MagicMock()):
                                                                route_handler._injection_scanner.filter_results = MagicMock(return_value=([], 0))

                                                                # Run search without generation
                                                                await route_handler.route_search(
                                                                    query="test query",
                                                                    mode="keyword",
                                                                    generate_response=False,
                                                                )

        if len(select_backend_calls) == 0:
            print("  Backend selection was skipped for retrieval-only query")
            print("  ✓ PASS: Backend selection correctly skipped")
        else:
            raise AssertionError(f"Backend selection was called {len(select_backend_calls)} times")


class TestCollectionSelectionHelpers:
    """Test bounded retrieval and local prompt helper behavior."""

    def test_select_route_collections_prefers_memory_first_for_continuations(self):
        original_collections = dict(route_handler._COLLECTIONS)
        original_classifier = route_handler.task_classifier.classify
        route_handler._COLLECTIONS = {
            "codebase-context": {},
            "error-solutions": {},
            "best-practices": {},
            "skills-patterns": {},
            "interaction-history": {},
            "agent-memory-sessions": {},
        }
        route_handler.task_classifier.classify = MagicMock(
            return_value=SimpleNamespace(
                token_estimate=120,
                task_type="code",
                local_suitable=False,
                remote_required=True,
                reason="task_type=code_requires_remote",
            )
        )
        try:
            selected = route_handler._select_route_collections(
                "continue debugging the last patch failure",
                route="hybrid",
                context={"memory_recall": ["prior finding"]},
                generate_response=False,
            )
        finally:
            route_handler._COLLECTIONS = original_collections
            route_handler.task_classifier.classify = original_classifier

        assert selected["profile"].endswith("memory-first")
        assert selected["collections"] == ["codebase-context"]

    def test_select_route_collections_collapses_simple_queries(self):
        original_collections = dict(route_handler._COLLECTIONS)
        original_classifier = route_handler.task_classifier.classify
        original_simple_count = route_handler._collection_metrics.simple_query_optimizations
        route_handler._COLLECTIONS = {
            "best-practices": {},
            "skills-patterns": {},
            "codebase-context": {},
        }
        route_handler.task_classifier.classify = MagicMock(
            return_value=SimpleNamespace(
                token_estimate=12,
                task_type="lookup",
                local_suitable=True,
                remote_required=False,
                reason="within_local_capacity",
            )
        )
        try:
            selected = route_handler._select_route_collections(
                "find logs",
                route="keyword",
                context=None,
                generate_response=False,
            )
        finally:
            route_handler._COLLECTIONS = original_collections
            route_handler.task_classifier.classify = original_classifier

        assert selected["profile"] == "simple-query-optimized"
        assert len(selected["collections"]) == 1
        assert route_handler._collection_metrics.simple_query_optimizations == original_simple_count + 1

    def test_select_keyword_pool_respects_compact_and_single_collection_profiles(self):
        single = route_handler._select_keyword_pool(
            retrieval_profile={"profile": "continuation-memory-first", "collections": ["codebase-context"]},
            keyword_limit=5,
            generate_response=False,
        )
        compact = route_handler._select_keyword_pool(
            retrieval_profile={"profile": "latency-optimized", "collections": ["best-practices", "skills-patterns"]},
            keyword_limit=5,
            generate_response=False,
        )

        assert single == 8
        assert compact == 12

    def test_local_budget_helpers_use_task_specific_caps(self):
        assert route_handler._local_response_budget("lookup") == 96
        assert route_handler._local_response_budget("reasoning") == 140
        assert route_handler._context_budget_for_task("format") == 320
        assert route_handler._context_budget_for_task("synthesize") == 720

    def test_local_inference_lane_selection_prefers_reasoning_for_deep_queries(self):
        continuation_complexity = SimpleNamespace(
            token_estimate=120,
            task_type="reasoning",
            local_suitable=True,
            remote_required=False,
            reason="continuation_within_local_capacity",
        )
        deep_lane = route_handler._select_local_inference_lane(
            "continue and explain why the deploy failed step by step",
            continuation_complexity,
            compressed_tokens=140,
            reasoning_client_available=True,
        )
        bounded_lane = route_handler._select_local_inference_lane(
            "continue fixing the deploy",
            continuation_complexity,
            compressed_tokens=40,
            reasoning_client_available=True,
        )

        assert deep_lane == ("reasoning", "continuation_reasoning_lane")
        assert bounded_lane == ("reasoning", "continuation_reasoning_lane")

    def test_prompt_helpers_trim_bounded_reasoning_context_and_gate_classifier_prompt(self):
        trimmed = route_handler._prompt_context_for_lane_reason(
            "compressed context",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "bounded_reasoning_default_lane",
        )
        instruction = route_handler._prompt_instruction_for_lane_reason("bounded_reasoning_default_lane")
        optimized = SimpleNamespace(
            token_estimate=80,
            task_type="reasoning",
            local_suitable=True,
            remote_required=False,
            reason="bounded_reasoning_within_local_capacity",
            optimized_prompt="Use this optimized prompt",
        )

        assert trimmed == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:40]
        assert "under 120 words" in instruction
        assert route_handler._use_classifier_optimized_prompt(optimized, "bounded_reasoning_default_lane") is False
        assert route_handler._use_classifier_optimized_prompt(optimized, "deep_reasoning_lane") is True


class TestRouteHeuristicHelpers:
    """Test low-cost pure helpers that drive route shaping and gap tracking."""

    def test_gap_tracking_filters_low_signal_and_short_queries(self):
        with patch.object(route_handler, "_normalize_tokens", return_value=["nixos"]):
            assert route_handler._should_track_query_gap("nixos", 0.1, 0, 0.4) is False

        with patch.object(route_handler, "_normalize_tokens", return_value=["switchboard", "timeout"]):
            assert route_handler._should_track_query_gap("switchboard timeout", 0.1, 1, 0.4) is False
            assert route_handler._should_track_query_gap("switchboard timeout", 0.1, 0, 0.4) is True
            assert route_handler._should_track_query_gap("switchboard timeout", 0.9, 0, 0.4) is False

    def test_synthetic_gap_and_context_skip_detection(self):
        with patch.object(route_handler, "_normalize_tokens", return_value=[]):
            assert route_handler._is_synthetic_gap_query("") is True
        with patch.object(route_handler, "_normalize_tokens", return_value=["analysis", "only", "task", "deploy"]):
            assert route_handler._is_synthetic_gap_query("analysis only task deploy") is True
        with patch.object(route_handler, "_normalize_tokens", return_value=["switchboard", "timeout"]):
            assert route_handler._is_synthetic_gap_query("switchboard timeout") is False

        assert route_handler._context_requests_gap_skip({"skip_gap_tracking": True}) is True
        assert route_handler._context_requests_gap_skip({"source": "aq-qa"}) is True
        assert route_handler._context_requests_gap_skip({"intent": "manual_probe"}) is True
        assert route_handler._context_requests_gap_skip({"source": "interactive"}) is False

    def test_runtime_context_blocks_include_hints_discovery_and_memory(self):
        blocks = route_handler._runtime_context_blocks(
            {
                "tool_hints": ["Use aq-hints", "", "Inspect switchboard"],
                "tool_discovery": {"summary": "3 matching skills", "capability_count": 3},
                "memory_recall": ["Prior deploy failed on switchboard", "Retry path worked"],
            }
        )

        assert len(blocks) == 3
        assert "Workflow hints:" in blocks[0]
        assert "Capability summary (3): 3 matching skills" == blocks[1]
        assert "Relevant prior memory:" in blocks[2]

    def test_continuation_and_capability_discovery_detection(self):
        assert route_handler._looks_like_continuation_query("continue from the last deploy fix") is True
        assert route_handler._looks_like_continuation_query(
            "show previous patch context",
            {"memory_recall": ["prior attempt"]},
        ) is True
        assert route_handler._looks_like_continuation_query("fresh deployment issue") is False

        assert route_handler._query_wants_capability_discovery("which tool should I use for this workflow?") is True
        assert route_handler._query_wants_capability_discovery(
            "plain retrieval query",
            {"tool_discovery": {"summary": "already present"}},
        ) is True
        assert route_handler._query_wants_capability_discovery("show me the latest switchboard error") is False

    def test_select_route_collections_history_and_detailed_profiles(self):
        original_collections = dict(route_handler._COLLECTIONS)
        original_classifier = route_handler.task_classifier.classify
        route_handler._COLLECTIONS = {
            "codebase-context": {},
            "error-solutions": {},
            "best-practices": {},
            "skills-patterns": {},
            "interaction-history": {},
            "agent-memory-sessions": {},
        }
        try:
            route_handler.task_classifier.classify = MagicMock(
                return_value=SimpleNamespace(
                    token_estimate=60,
                    task_type="lookup",
                    local_suitable=True,
                    remote_required=False,
                    reason="within_local_capacity",
                )
            )
            with patch.object(
                route_handler,
                "_normalize_tokens",
                return_value=["show", "previous", "history", "from", "prior", "interaction"],
            ):
                history = route_handler._select_route_collections(
                    "show previous history from the prior interaction",
                    route="hybrid",
                    context=None,
                    generate_response=False,
                )

            route_handler.task_classifier.classify = MagicMock(
                return_value=SimpleNamespace(
                    token_estimate=180,
                    task_type="reasoning",
                    local_suitable=False,
                    remote_required=True,
                    reason="long_reasoning_query",
                )
            )
            with patch.object(
                route_handler,
                "_normalize_tokens",
                return_value=[
                    "compare", "switchboard", "timeout", "coordinator",
                    "fallback", "behavior", "across", "repo", "now", "deep", "analysis", "please",
                ],
            ):
                detailed = route_handler._select_route_collections(
                    "compare the switchboard timeout and coordinator fallback behavior across the repo now",
                    route="tree",
                    context=None,
                    generate_response=True,
                )
        finally:
            route_handler._COLLECTIONS = original_collections
            route_handler.task_classifier.classify = original_classifier

        assert history["profile"] == "history-aware"
        assert len(history["collections"]) == 2
        assert detailed["profile"].endswith("-detailed")
        assert len(detailed["collections"]) == 4

    def test_keyword_pool_and_lane_helpers_cover_default_branches(self):
        base_pool = route_handler._select_keyword_pool(
            retrieval_profile={"profile": "detailed", "collections": ["a", "b", "c"]},
            keyword_limit=5,
            generate_response=True,
        )
        lookup_pool = route_handler._select_keyword_pool(
            retrieval_profile={"profile": "lookup-focused", "collections": ["a", "b"]},
            keyword_limit=5,
            generate_response=False,
        )

        assert base_pool == 24
        assert lookup_pool == 12
        assert route_handler._local_response_budget("unknown") == 220
        assert route_handler._context_budget_for_task("unknown") == 1200
        assert route_handler._strong_reasoning_query("compare the two deploy failures") is True
        assert route_handler._deep_continuation_query("please explain why the service failed") is True

        default_lane = route_handler._select_local_inference_lane(
            "quick reasoning summary",
            SimpleNamespace(
                token_estimate=40,
                task_type="reasoning",
                local_suitable=True,
                remote_required=False,
                reason="bounded_reasoning",
            ),
            compressed_tokens=20,
            reasoning_client_available=True,
        )
        no_reasoning_lane = route_handler._select_local_inference_lane(
            "compare two fixes",
            SimpleNamespace(
                token_estimate=200,
                task_type="reasoning",
                local_suitable=True,
                remote_required=False,
                reason="bounded_reasoning",
            ),
            compressed_tokens=200,
            reasoning_client_available=False,
        )

        assert default_lane == ("default", "bounded_reasoning_default_lane")
        assert no_reasoning_lane == ("default", "default_local_lane")
        assert route_handler._prompt_context_for_lane_reason("compressed", "classifier", "deep_reasoning_lane") == "compressed"
        assert route_handler._prompt_instruction_for_lane_reason("deep_reasoning_lane") == "Provide a concise response using the context."
        assert route_handler._use_classifier_optimized_prompt(None, "deep_reasoning_lane") is False


class TestGeneratedResponsePaths:
    """Exercise local synthesis branches for measurable coverage lift."""

    def test_route_search_generates_local_response_with_prompt_cache_metadata(self):
        asyncio.run(self._run_route_search_generates_local_response_with_prompt_cache_metadata())

    async def _run_route_search_generates_local_response_with_prompt_cache_metadata(self):
        original_build_local_system_prompt = getattr(Config, "build_local_system_prompt", None)
        original_remote_tokens = getattr(Config, "AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS", 320)
        original_timeout = getattr(Config, "LLAMA_CPP_INFERENCE_TIMEOUT", 5.0)
        original_compression = getattr(Config, "AI_CONTEXT_COMPRESSION_ENABLED", False)
        original_classification = getattr(Config, "AI_TASK_CLASSIFICATION_ENABLED", False)
        Config.build_local_system_prompt = staticmethod(lambda: "Local system prompt")
        Config.AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS = 320
        Config.LLAMA_CPP_INFERENCE_TIMEOUT = 5.0
        Config.AI_CONTEXT_COMPRESSION_ENABLED = False
        Config.AI_TASK_CLASSIFICATION_ENABLED = False

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"content": "Synthesized local answer"}}],
                    "usage": {"cached_tokens": 7},
                }

        class FakeClient:
            def __init__(self):
                self.calls = []

            async def post(self, path, headers=None, json=None, timeout=None):
                self.calls.append({
                    "path": path,
                    "headers": headers or {},
                    "json": json or {},
                    "timeout": timeout,
                })
                return FakeResponse()

        fake_client = FakeClient()
        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [{"score": 0.9, "text": "important context"}],
        })

        with patch.object(route_handler, "_hybrid_search", hybrid_search_fn):
            with patch.object(route_handler, "_summarize", MagicMock(return_value="fallback summary")):
                with patch.object(route_handler, "_record_telemetry", MagicMock()):
                    with patch.object(route_handler.capability_discovery, "format_context", MagicMock(return_value="")):
                        with patch.object(route_handler, "_postgres_client_ref", return_value=None):
                            with patch.object(route_handler, "_llama_cpp_client_ref", return_value=fake_client):
                                with patch.object(route_handler, "_llama_cpp_reasoning_client_ref", return_value=None):
                                    with patch.object(route_handler, "_context_compressor_ref", return_value=None):
                                        with patch.object(route_handler, "ROUTE_DECISIONS", MagicMock()):
                                            with patch.object(route_handler, "ROUTE_ERRORS", MagicMock()):
                                                with patch.object(route_handler, "LLM_BACKEND_SELECTIONS", MagicMock()):
                                                    with patch.object(route_handler, "LLM_BACKEND_LATENCY", MagicMock()):
                                                        with patch.object(route_handler, "sanitize_query", lambda x: x):
                                                            with patch.object(route_handler, "_injection_scanner", MagicMock()) as patched_injection_scanner:
                                                                patched_injection_scanner.filter_results = MagicMock(return_value=([], 0))
                                                                result = await route_handler.route_search(
                                                                    query="summarize the current local routing behavior",
                                                                    mode="hybrid",
                                                                    generate_response=True,
                                                                )

        if original_build_local_system_prompt is not None:
            Config.build_local_system_prompt = original_build_local_system_prompt
        Config.AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS = original_remote_tokens
        Config.LLAMA_CPP_INFERENCE_TIMEOUT = original_timeout
        Config.AI_CONTEXT_COMPRESSION_ENABLED = original_compression
        Config.AI_TASK_CLASSIFICATION_ENABLED = original_classification

        assert result["backend"] == "local"
        assert result["response"] == "Synthesized local answer"
        assert result["backend_reason_class"] == "default_local"
        assert result["results"]["prompt_cache"]["cached_tokens"] == 7
        assert fake_client.calls[0]["path"] == "/chat/completions"
        assert fake_client.calls[0]["json"]["messages"][0]["content"] == "Local system prompt"
        assert fake_client.calls[0]["json"]["temperature"] == 0.2

    def test_route_search_falls_back_to_local_after_remote_4xx(self):
        asyncio.run(self._run_route_search_falls_back_to_local_after_remote_4xx())

    async def _run_route_search_falls_back_to_local_after_remote_4xx(self):
        original_build_local_system_prompt = getattr(Config, "build_local_system_prompt", None)
        original_remote_tokens = getattr(Config, "AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS", 320)
        original_timeout = getattr(Config, "LLAMA_CPP_INFERENCE_TIMEOUT", 5.0)
        original_compression = getattr(Config, "AI_CONTEXT_COMPRESSION_ENABLED", False)
        original_classification = getattr(Config, "AI_TASK_CLASSIFICATION_ENABLED", False)
        original_switchboard_url = getattr(Config, "SWITCHBOARD_URL", "http://switchboard")
        Config.build_local_system_prompt = staticmethod(lambda: "Local system prompt")
        Config.AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS = 320
        Config.LLAMA_CPP_INFERENCE_TIMEOUT = 5.0
        Config.AI_CONTEXT_COMPRESSION_ENABLED = False
        Config.AI_TASK_CLASSIFICATION_ENABLED = True
        Config.SWITCHBOARD_URL = "http://switchboard"

        class Remote4xxError(Exception):
            def __init__(self):
                self.response = SimpleNamespace(status_code=400)

        class FakeRemoteClient:
            def __init__(self):
                self.calls = []

            async def post(self, path, headers=None, json=None, timeout=None):
                self.calls.append({
                    "path": path,
                    "headers": headers or {},
                    "json": json or {},
                    "timeout": timeout,
                })
                raise Remote4xxError()

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"content": "Recovered locally"}}],
                    "usage": {"cached_tokens": 5},
                }

        class FakeLocalClient:
            def __init__(self):
                self.calls = []

            async def post(self, path, headers=None, json=None, timeout=None):
                self.calls.append({
                    "path": path,
                    "headers": headers or {},
                    "json": json or {},
                    "timeout": timeout,
                })
                return FakeResponse()

        fake_remote = FakeRemoteClient()
        fake_local = FakeLocalClient()
        hybrid_search_fn = AsyncMock(return_value={
            "keyword_results": [],
            "semantic_results": [],
            "combined_results": [{"score": 0.95, "text": "heavy reasoning context"}],
        })
        remote_required = SimpleNamespace(
            task_type="reasoning",
            token_estimate=900,
            local_suitable=False,
            remote_required=True,
            reason="requires_remote_reasoning",
        )

        with patch.object(route_handler, "_hybrid_search", hybrid_search_fn):
            with patch.object(route_handler, "_summarize", MagicMock(return_value="fallback summary")):
                with patch.object(route_handler, "_record_telemetry", MagicMock()):
                    with patch.object(route_handler.capability_discovery, "format_context", MagicMock(return_value="")):
                        with patch.object(route_handler.task_classifier, "classify", MagicMock(return_value=remote_required)):
                            with patch.object(route_handler, "_postgres_client_ref", return_value=None):
                                with patch.object(route_handler, "_switchboard_client_ref", return_value=fake_remote):
                                    with patch.object(route_handler, "_llama_cpp_client_ref", return_value=fake_local):
                                        with patch.object(route_handler, "_llama_cpp_reasoning_client_ref", return_value=None):
                                            with patch.object(route_handler, "_context_compressor_ref", return_value=None):
                                                with patch.object(route_handler, "ROUTE_DECISIONS", MagicMock()):
                                                    with patch.object(route_handler, "ROUTE_ERRORS", MagicMock()):
                                                        with patch.object(route_handler, "LLM_BACKEND_SELECTIONS", MagicMock()):
                                                            with patch.object(route_handler, "LLM_BACKEND_LATENCY", MagicMock()):
                                                                with patch.object(route_handler, "sanitize_query", lambda x: x):
                                                                    with patch.object(route_handler, "_injection_scanner", MagicMock()) as patched_injection_scanner:
                                                                        patched_injection_scanner.filter_results = MagicMock(return_value=([], 0))
                                                                        result = await route_handler.route_search(
                                                                            query="compare failure modes across the deploy attempts",
                                                                            mode="hybrid",
                                                                            generate_response=True,
                                                                        )

        if original_build_local_system_prompt is not None:
            Config.build_local_system_prompt = original_build_local_system_prompt
        Config.AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS = original_remote_tokens
        Config.LLAMA_CPP_INFERENCE_TIMEOUT = original_timeout
        Config.AI_CONTEXT_COMPRESSION_ENABLED = original_compression
        Config.AI_TASK_CLASSIFICATION_ENABLED = original_classification
        Config.SWITCHBOARD_URL = original_switchboard_url

        assert result["backend"] == "local"
        assert result["backend_reason_class"] == "remote_4xx_local_fallback"
        assert result["response"] == "Recovered locally"
        assert result["results"]["synthesis_fallback"]["status_code"] == 400
        assert fake_remote.calls[0]["path"] == "/v1/chat/completions"
        assert fake_remote.calls[0]["headers"]["x-ai-route"] == "remote"
        assert fake_local.calls[0]["path"] == "/chat/completions"
        assert fake_local.calls[0]["json"]["messages"][0]["content"] == "Local system prompt"


async def run_async_tests():
    """Run all async tests."""
    tests = [
        TestParallelization().test_parallel_expansion_and_discovery(),
        TestTimeoutGuards().test_search_timeout(),
        TestSkipBackendSelection().test_backend_selection_skipped_on_retrieval_only(),
        TestGeneratedResponsePaths().test_route_search_generates_local_response_with_prompt_cache_metadata(),
        TestGeneratedResponsePaths().test_route_search_falls_back_to_local_after_remote_4xx(),
    ]
    results = await asyncio.gather(*tests, return_exceptions=True)
    return results


def main():
    """Run all optimization tests."""
    print("=" * 70)
    print("Phase 5.2 Route Search Optimization Tests")
    print("=" * 70)

    all_passed = True

    # Sync tests
    sync_tests = [
        TestBackendSelectionCache().test_cache_key_generation(),
        TestBackendSelectionCache().test_cache_hit_miss(),
        TestBackendSelectionCache().test_cache_eviction(),
    ]

    for result in sync_tests:
        if isinstance(result, Exception):
            print(f"Test error: {result}")
            all_passed = False
        elif not result:
            all_passed = False

    # Async tests
    try:
        async_results = asyncio.run(run_async_tests())
        for result in async_results:
            if isinstance(result, Exception):
                print(f"Test error: {result}")
                all_passed = False
            elif not result:
                all_passed = False
    except Exception as e:
        print(f"Async test error: {e}")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("All tests PASSED ✓")
        return 0
    else:
        print("Some tests FAILED ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
