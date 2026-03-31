#!/usr/bin/env python3
"""Regression checks for aq-report prompt-cache fallback when Prometheus cache metrics are empty."""

from __future__ import annotations

import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_aq_report():
    os.environ.setdefault("AI_STRICT_ENV", "false")
    spec = importlib.util.spec_from_loader(
        "aq_report_prompt_cache_fallback",
        SourceFileLoader("aq_report_prompt_cache_fallback", str(AQ_REPORT_PATH)),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load aq-report")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    aq_report = load_aq_report()

    def fake_prom_query(_metric: str):
        return 0.0

    aq_report.prom_query = fake_prom_query
    audit_entries = [
        {
            "tool_name": "route_search",
            "metadata": {
                "generate_response": True,
                "prompt_cache_cached_tokens": 42,
            },
        },
        {
            "tool_name": "route_search",
            "metadata": {
                "generate_response": True,
                "prompt_cache_cached_tokens": 0,
            },
        },
        {
            "tool_name": "route_search",
            "metadata": {
                "generate_response": False,
                "prompt_cache_cached_tokens": 99,
            },
        },
    ]

    cache = aq_report.cache_hit_rate(audit_entries)
    assert_true(cache.get("source") == "route_prompt_cache_audit", "expected prompt-cache audit fallback source")
    assert_true(cache.get("hits") == 1, "expected one prompt-cache hit sample")
    assert_true(cache.get("misses") == 1, "expected one prompt-cache miss sample")
    assert_true(cache.get("hit_pct") == 50.0, "expected 50% prompt-cache hit rate")

    rag = aq_report.rag_posture(
        tool_stats={"route_search": {"calls": 4}, "tree_search": {"calls": 0}, "recall_agent_memory": {"calls": 0}},
        recent_tool_stats={"route_search": {"calls": 4}, "tree_search": {"calls": 0}, "recall_agent_memory": {"calls": 0}},
        recent_audit_entries=audit_entries,
        cache=cache,
        gaps=[],
        top_prompts=[{"id": "route_search_synthesis", "name": "Route Search Synthesis", "mean_score": 0.9}],
        route_latency={"overall_p95_ms": 2800.0},
        retrieval_breadth={"avg_collection_count": 1.5},
    )
    assert_true(rag.get("cache_hit_pct") == 50.0, "expected rag posture to use prompt-cache fallback hit rate")
    assert_true("prompt" in str(cache.get("source", "")).lower(), "expected explicit cache source labelling")

    print("PASS: aq-report falls back to prompt-cache audit samples when Prometheus cache counters are empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
