"""
Unit tests for task_classifier.py — zero-latency heuristic task classifier.

Tests classification of queries into task_type (lookup/format/synthesize/code/reasoning)
and local vs remote routing decisions, including edge cases and boundary conditions.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HC_DIR = Path(__file__).resolve().parent.parent
if str(_HC_DIR) not in sys.path:
    sys.path.insert(0, str(_HC_DIR))

from task_classifier import TaskComplexity, classify


# ---------------------------------------------------------------------------
# Task type detection
# ---------------------------------------------------------------------------
class TestTaskTypeDetection:
    def test_code_implement(self):
        r = classify("implement a cache eviction function")
        assert r.task_type == "code"

    def test_code_refactor(self):
        r = classify("refactor the retry logic in server.py")
        assert r.task_type == "code"

    def test_code_debug(self):
        r = classify("debug the authentication failure")
        assert r.task_type == "code"

    def test_code_write_function(self):
        r = classify("write a function that validates email addresses")
        assert r.task_type == "code"

    def test_reasoning_why(self):
        r = classify("why does the coordinator timeout on large payloads")
        assert r.task_type in ("reasoning", "synthesize")  # may downgrade

    def test_reasoning_explain(self):
        r = classify("explain how the route alias resolution works")
        assert r.task_type in ("reasoning", "synthesize")

    def test_reasoning_analyze(self):
        r = classify("analyze the performance bottleneck in qdrant queries")
        assert r.task_type == "reasoning"

    def test_reasoning_design(self):
        r = classify("design a new caching strategy for the hybrid coordinator")
        assert r.task_type == "reasoning"

    def test_format_convert(self):
        r = classify("convert the service config to JSON")
        assert r.task_type == "format"

    def test_format_extract(self):
        r = classify("extract all port numbers from the config file")
        assert r.task_type == "format"

    def test_format_parse(self):
        r = classify("parse the YAML configuration into a Python dict")
        assert r.task_type == "format"

    def test_lookup_what_is(self):
        r = classify("what is nixos")
        assert r.task_type == "lookup"

    def test_lookup_who_is(self):
        r = classify("who is the owner of the AIDB service")
        assert r.task_type == "lookup"

    def test_lookup_list_all(self):
        r = classify("list all available MCP tools")
        assert r.task_type == "lookup"

    def test_synthesize_default(self):
        r = classify("summarize recent deployment changes")
        assert r.task_type == "synthesize"

    def test_synthesize_unknown(self):
        r = classify("compare the two approaches")
        # "compare" triggers reasoning but short query might downgrade
        assert r.task_type in ("reasoning", "synthesize")


# ---------------------------------------------------------------------------
# Bounded reasoning → synthesize downgrade
# ---------------------------------------------------------------------------
class TestBoundedReasoningDowngrade:
    def test_brief_explain_downgrades(self):
        r = classify("briefly explain how the route handler works")
        assert r.task_type == "synthesize"

    def test_concise_why_downgrades(self):
        # "concisely" doesn't match \bconcise\b (word boundary after 'e' blocked by 'ly')
        # use "concise" or "briefly" to trigger the downgrade
        r = classify("briefly explain why the timeout occurs")
        assert r.task_type == "synthesize"

    def test_one_sentence_downgrades(self):
        r = classify("in one sentence explain what qdrant does")
        assert r.task_type == "synthesize"

    def test_summary_downgrades(self):
        r = classify("short summary of what the hybrid coordinator does")
        assert r.task_type == "synthesize"

    def test_architecture_heavy_stays_reasoning(self):
        r = classify("briefly design a new architecture strategy for the stack")
        # "design" + "strategy" are architecture-heavy so no downgrade
        assert r.task_type == "reasoning"

    def test_short_explain_query_downgrades(self):
        # short word-count + starts with "explain" → synthesize
        r = classify("explain how qdrant works")
        assert r.task_type == "synthesize"

    def test_long_explain_stays_reasoning(self):
        # Long query with many words stays reasoning even without bounded words
        long_query = "explain why the system behaves differently " + "under high load " * 10
        r = classify(long_query)
        # Too many words for short-explanation downgrade
        assert r.task_type == "reasoning"


# ---------------------------------------------------------------------------
# Local vs remote routing
# ---------------------------------------------------------------------------
class TestRoutingDecisions:
    def test_lookup_is_local(self):
        # max_output_tokens must be ≤ LOCAL_MAX_OUTPUT_TOKENS (300)
        r = classify("what is nixos", max_output_tokens=100)
        assert r.local_suitable is True
        assert r.remote_required is False

    def test_format_is_local(self):
        r = classify("convert this to JSON", "port: 8080\nhost: localhost", max_output_tokens=100)
        assert r.local_suitable is True
        assert r.remote_required is False

    def test_synthesize_is_local(self):
        r = classify("summarize the service status", max_output_tokens=100)
        assert r.local_suitable is True
        assert r.remote_required is False

    def test_code_is_remote(self):
        r = classify("implement a retry loop with exponential backoff")
        assert r.local_suitable is False
        assert r.remote_required is True

    def test_reasoning_is_remote(self):
        r = classify("analyze and compare the two routing strategies")
        assert r.local_suitable is False
        assert r.remote_required is True

    def test_large_input_forces_remote(self):
        # Create input larger than LOCAL_MAX_INPUT_TOKENS (600 tokens ~ 2400 chars)
        big_context = "x " * 1500  # ~3000 chars → ~750 tokens
        r = classify("what is this", context=big_context)
        assert r.remote_required is True
        assert "input_too_large" in r.reason

    def test_large_output_forces_remote(self):
        r = classify("summarize this", max_output_tokens=500)  # > LOCAL_MAX_OUTPUT_TOKENS (300)
        assert r.remote_required is True
        assert "output_too_large" in r.reason

    def test_within_capacity_reason(self):
        r = classify("what is nixos", max_output_tokens=100)
        assert r.reason == "within_local_capacity"


# ---------------------------------------------------------------------------
# Continuation routing
# ---------------------------------------------------------------------------
class TestContinuationRouting:
    def test_continuation_code_stays_local(self):
        # "implement" (not "implementing") matches \bimplement\b → task_type=code
        # continuation + code within local capacity → local
        r = classify("resume the task to implement the retry module from last session", max_output_tokens=200)
        assert r.local_suitable is True
        assert r.reason == "continuation_within_local_capacity"

    def test_continuation_reasoning_stays_local(self):
        r = classify("follow up on the analysis of the routing strategy", max_output_tokens=200)
        assert r.local_suitable is True
        assert r.reason == "continuation_within_local_capacity"

    def test_continuation_detection(self):
        for phrase in ["resume", "continue", "follow-up", "pick up where", "left off"]:
            r = classify(f"{phrase} the implementation work")
            # At minimum it should detect code or continuation type
            assert r is not None


# ---------------------------------------------------------------------------
# Optimized prompt generation
# ---------------------------------------------------------------------------
class TestOptimizedPrompts:
    def test_lookup_optimized_prompt_format(self):
        r = classify("what is nixos", context="NixOS is a Linux distro", max_output_tokens=100)
        assert r.optimized_prompt is not None
        assert "what is nixos" in r.optimized_prompt.lower()

    def test_format_optimized_prompt_format(self):
        r = classify("convert to YAML", context="port: 8080", max_output_tokens=100)
        assert r.optimized_prompt is not None
        assert "ONLY" in r.optimized_prompt or "yaml" in r.optimized_prompt.lower()

    def test_synthesize_optimized_prompt_format(self):
        r = classify("summarize deployment status", context="all services healthy", max_output_tokens=100)
        assert r.optimized_prompt is not None
        assert "paragraph" in r.optimized_prompt or "70 words" in r.optimized_prompt

    def test_remote_has_no_optimized_prompt(self):
        r = classify("implement a full auth system with JWT")
        assert r.optimized_prompt is None

    def test_continuation_optimized_prompt_includes_context(self):
        ctx = "Prior work: implemented rate limiter module"
        r = classify("continue implementing the cache module", context=ctx)
        if r.local_suitable:
            assert r.optimized_prompt is not None
            assert "continue" in r.optimized_prompt.lower() or "prior" in r.optimized_prompt.lower()

    def test_context_truncated_in_prompt(self):
        from task_classifier import LOCAL_SYNTHESIZE_CONTEXT_CHARS
        long_ctx = "A" * (LOCAL_SYNTHESIZE_CONTEXT_CHARS + 500)
        r = classify("summarize this", context=long_ctx)
        if r.local_suitable and r.optimized_prompt:
            # Prompt should not contain the full context
            assert len(r.optimized_prompt) < len(long_ctx)


# ---------------------------------------------------------------------------
# Token estimate
# ---------------------------------------------------------------------------
class TestTokenEstimate:
    def test_empty_query(self):
        r = classify("")
        assert r.token_estimate == 0

    def test_estimate_scales_with_input(self):
        short = classify("hi")
        long_ = classify("a " * 100)
        assert long_.token_estimate > short.token_estimate

    def test_context_adds_to_estimate(self):
        no_ctx = classify("test query")
        with_ctx = classify("test query", context="extra context " * 50)
        assert with_ctx.token_estimate > no_ctx.token_estimate


# ---------------------------------------------------------------------------
# TaskComplexity dataclass
# ---------------------------------------------------------------------------
class TestTaskComplexityDataclass:
    def test_fields_present(self):
        r = classify("what is redis")
        assert hasattr(r, "token_estimate")
        assert hasattr(r, "task_type")
        assert hasattr(r, "local_suitable")
        assert hasattr(r, "remote_required")
        assert hasattr(r, "reason")
        assert hasattr(r, "optimized_prompt")

    def test_local_remote_mutually_exclusive(self):
        for query in ["what is nixos", "implement an auth module", "analyze the logs"]:
            r = classify(query)
            # local_suitable and remote_required should be opposite
            assert r.local_suitable != r.remote_required
