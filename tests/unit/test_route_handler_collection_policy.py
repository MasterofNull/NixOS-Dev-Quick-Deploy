"""
Focused checks for route_search collection selection policy.
"""

from pathlib import Path
import os
import sys
from types import SimpleNamespace
import types


ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda *args, **kwargs: SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        )
    )
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

import route_handler  # noqa: E402


def test_non_generative_hybrid_queries_use_compact_collection_fanout(monkeypatch):
    monkeypatch.setattr(
        route_handler.task_classifier,
        "classify",
        lambda query, context, max_output_tokens=200: SimpleNamespace(task_type="reasoning"),
    )
    monkeypatch.setattr(
        route_handler,
        "_COLLECTIONS",
        {
            "best-practices": {},
            "skills-patterns": {},
            "codebase-context": {},
            "error-solutions": {},
            "interaction-history": {},
            "agent-memory-main": {},
        },
    )

    profile = route_handler._select_route_collections(
        "how do I optimize route_search latency for repeated repo queries",
        route="hybrid",
        context={},
        generate_response=False,
    )

    assert profile["profile"] == "code-focused-compact"
    assert len(profile["collections"]) == 2
    assert profile["collections"] == ["codebase-context", "error-solutions"]


def test_generate_response_queries_keep_detailed_collection_budget(monkeypatch):
    monkeypatch.setattr(
        route_handler.task_classifier,
        "classify",
        lambda query, context, max_output_tokens=200: SimpleNamespace(task_type="reasoning"),
    )
    monkeypatch.setattr(
        route_handler,
        "_COLLECTIONS",
        {
            "best-practices": {},
            "skills-patterns": {},
            "codebase-context": {},
            "error-solutions": {},
            "interaction-history": {},
        },
    )

    profile = route_handler._select_route_collections(
        "explain how to optimize route_search latency for repeated repository retrieval workloads with detailed synthesis",
        route="hybrid",
        context={},
        generate_response=True,
    )

    assert profile["profile"] == "code-focused-detailed"
    assert len(profile["collections"]) >= 3
