"""Vector-store routing/hygiene: knowledge routing, GC absence tolerance, stable ids, prune selector."""

import asyncio
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
MCP = ROOT / "ai-stack" / "mcp-servers"
HC = MCP / "hybrid-coordinator"
os.environ.setdefault("AI_STRICT_ENV", "false")
if "structlog" not in sys.modules:
    try:
        import structlog  # noqa: F401
    except ImportError:
        _noop = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                error=lambda *a, **k: None, debug=lambda *a, **k: None)
        sys.modules["structlog"] = types.SimpleNamespace(get_logger=lambda *a, **k: _noop)
for p in (MCP, HC, ROOT / "ai-stack" / "offloading"):
    sys.path.insert(0, str(p))

from core import route_handler  # noqa: E402

ALL = ["best-practices", "skills-patterns", "codebase-context", "error-solutions",
       "interaction-history", "knowledge", "wiki-sections", "agent-memory-episodic"]


def _select(monkeypatch, query, task_type, generate_response=False):
    monkeypatch.setattr(route_handler, "_COLLECTIONS", {k: {} for k in ALL})
    monkeypatch.setattr(
        route_handler.task_classifier, "classify",
        lambda q, c, max_output_tokens=200: SimpleNamespace(task_type=task_type),
    )
    return route_handler._select_route_collections(
        query, route="hybrid", context={}, generate_response=generate_response
    )["collections"]


def test_code_query_without_error_signal_routes_knowledge(monkeypatch):
    cols = _select(monkeypatch, "where is the llama module option defined in the repo", "code")
    assert "knowledge" in cols and cols[0] == "codebase-context"


def test_error_query_keeps_error_solutions_and_adds_knowledge_when_room(monkeypatch):
    cols = _select(monkeypatch, "why does the nixos service config fail with a timeout error on restart", "code", True)
    assert "error-solutions" in cols and "knowledge" in cols


def test_architecture_query_routes_wiki_sections_then_knowledge(monkeypatch):
    cols = _select(monkeypatch, "explain the architecture of the switchboard service and its components", "code", True)
    assert cols.index("wiki-sections") < cols.index("knowledge")
    assert len(cols) <= 4


def test_collection_hit_counts():
    assert route_handler._collection_hit_counts(
        [{"collection": "knowledge"}, {"collection": "knowledge"}, {"collection": "x"}, {}, "junk"]
    ) == {"knowledge": 2, "x": 1, "unknown": 1}


def test_garbage_collector_tolerates_missing_collection():
    for mod in ("asyncpg", "qdrant_client", "qdrant_client.models", "prometheus_client"):
        try:
            importlib.import_module(mod)
        except ImportError:
            m = MagicMock()
            m.Histogram.return_value.labels.return_value.time.return_value.__enter__ = lambda *a: None
            m.Histogram.return_value.labels.return_value.time.return_value.__exit__ = lambda *a: False
            sys.modules[mod] = m
    spec = importlib.util.spec_from_file_location("gc_mod", HC / "extensions" / "garbage_collector.py")
    gc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gc_mod)
    for qdrant in (
        MagicMock(**{"collection_exists.return_value": False}),
        MagicMock(**{"collection_exists.side_effect": AttributeError(),
                     "scroll.side_effect": Exception("Collection `solved_issues` doesn't exist!")}),
    ):
        gc = gc_mod.GarbageCollector.__new__(gc_mod.GarbageCollector)
        gc.qdrant = qdrant
        gc.db_pool = MagicMock()
        assert asyncio.run(gc.cleanup_qdrant_orphans()) == 0
        assert asyncio.run(gc.cleanup_qdrant_orphans()) == 0  # repeat: still quiet, no raise
        qdrant.delete.assert_not_called()


def test_continuous_learning_ids_stable_across_processes():
    code = (
        "import sys,re,hashlib;"
        "src=open(sys.argv[1]).read();"
        "m=re.search(r'def _stable_point_id.*?\\n\\n\\n',src,re.S);"
        "ns={'hashlib':hashlib};exec(m.group(0),ns);"
        "print(ns['_stable_point_id']('pattern-abc'))"
    )
    target = str(HC / "extensions" / "continuous_learning.py")
    outs = {
        subprocess.check_output([sys.executable, "-c", code, target],
                                env={**os.environ, "PYTHONHASHSEED": seed}, text=True).strip()
        for seed in ("1", "2", "random")
    }
    assert len(outs) == 1


def test_prune_script_selects_only_test_collections():
    path = ROOT / "scripts" / "ai" / "aq-qdrant-prune-test-collections"
    loader = importlib.machinery.SourceFileLoader("prune_mod", str(path))
    spec = importlib.util.spec_from_loader("prune_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    names = ["agent-ctx-test-task-large-live-rfgate-1", "agent-ctx-test-x", "agent-ctx-real-1",
             "knowledge", "error-solutions", "xagent-ctx-test-y", "agent-memory-episodic"]
    assert mod.select_test_collections(names) == [
        "agent-ctx-test-task-large-live-rfgate-1", "agent-ctx-test-x"]
