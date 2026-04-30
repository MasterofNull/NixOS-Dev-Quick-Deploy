#!/usr/bin/env python3
"""Regression checks for aq-report continuation downshift summaries."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
TARGET_FUNCTIONS = {
    "route_search_latency_decomposition",
    "rag_posture",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_helpers() -> Dict[str, Any]:
    source = AQ_REPORT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(AQ_REPORT_PATH))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGET_FUNCTIONS
    ]
    module = ast.Module(body=selected, type_ignores=[])
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "_percentile": lambda values, pct: (
            None if not values else sorted(values)[max(0, min(len(values) - 1, round((len(values) - 1) * pct / 100)))]
        ),
        "_na": lambda value, fmt="", suffix="": (
            "n/a" if value is None else (format(float(value), fmt) + suffix if fmt else f"{value}{suffix}")
        ),
        "_cache_sample_context": lambda cache: None,
        "_memory_recall_quality": lambda entries: {"attempts": 2, "misses": 0, "miss_pct": 0.0},
        "_rag_prewarm_candidates": lambda *args, **kwargs: [],
        "_is_synthetic_gap": lambda query: False,
        "_is_curated_stale_gap": lambda query: False,
    }
    exec(compile(module, str(AQ_REPORT_PATH), "exec"), namespace)
    return namespace


def main() -> int:
    helpers = load_helpers()

    entries = [
        {
            "tool_name": "route_search",
            "service": "ai-hybrid-coordinator",
            "latency_ms": 120000.0,
            "outcome": "success",
            "metadata": {
                "backend": "local",
                "http_status": 200,
                "generate_response": True,
                "generate_response_requested": True,
                "task_complexity_type": "synthesize",
            },
        },
        {
            "tool_name": "route_search",
            "service": "ai-hybrid-coordinator",
            "latency_ms": 350.0,
            "outcome": "success",
            "metadata": {
                "backend": "local",
                "http_status": 200,
                "generate_response": False,
                "generate_response_requested": True,
                "response_generation_downshifted": True,
                "response_generation_downshift_reason": "continuation_memory_first",
                "retrieval_strategy_mode": "memory-first",
            },
        },
    ]

    route_latency = helpers["route_search_latency_decomposition"](entries, window="1h")
    downshift = route_latency.get("continuation_downshift", {})
    assert_true(downshift.get("downshifted_calls") == 1, "expected one continuation downshifted call")
    assert_true(downshift.get("candidate_calls") == 2, "expected two response-request candidates")
    assert_true(downshift.get("estimated_synthesis_ms_avoided") == 119650.0, "expected avoided latency estimate")

    rag_posture = helpers["rag_posture"](
        {"route_search": {"calls": 10}, "recall_agent_memory": {"calls": 3}, "tree_search": {"calls": 0}},
        {"route_search": {"calls": 8}, "recall_agent_memory": {"calls": 2}, "tree_search": {"calls": 0}},
        entries,
        {"available": True, "sample_total": 80, "hit_pct": 90.0},
        [],
        [],
        route_latency=route_latency,
        retrieval_breadth={"avg_collection_count": 1.2},
    )
    continuation = rag_posture.get("continuation_downshift", {})
    assert_true(continuation.get("downshifted_calls") == 1, "rag posture should expose continuation downshift count")
    assert_true(
        any("continuation downshift avoided synthesis on 1 recent calls" in str(reason) for reason in rag_posture.get("reasons", [])),
        "rag posture reasons should mention the downshift savings",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
