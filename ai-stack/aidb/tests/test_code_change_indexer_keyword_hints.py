from pathlib import Path
from unittest.mock import Mock
import sys


TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))

from code_change_indexer import CodeChangeIndexer


def test_build_keyword_hints_includes_runtime_paths_and_terms():
    indexer = CodeChangeIndexer(
        qdrant_client=Mock(),
        embedding_service_url="http://localhost:8081",
        repo_path=".",
    )

    commit = {
        "subject": "feat: tighten switchboard routing cache behavior",
        "body": "Improve local route latency and cache reuse for hybrid coordinator requests.",
    }
    files = [
        "ai-stack/mcp-servers/hybrid-coordinator/search_router.py",
        "nix/modules/services/switchboard.nix",
    ]
    diff = "+ route cache switchboard hybrid coordinator local query latency"

    hints = indexer.build_keyword_hints(commit, files, diff)

    assert "ai-stack/mcp-servers/hybrid-coordinator/search_router.py" in hints
    assert "switchboard" in hints
    assert "routing" in hints
    assert "cache" in hints
    assert "latency" in hints


def test_build_keyword_hints_filters_doc_paths_and_validation_noise():
    indexer = CodeChangeIndexer(
        qdrant_client=Mock(),
        embedding_service_url="http://localhost:8081",
        repo_path=".",
    )

    commit = {
        "subject": "fix: tighten route handler retrieval quality",
        "body": "Run pytest and tier0-validation-gate --pre-commit after updating ranking.",
    }
    files = [
        ".agent/workflows/advisor-strategy-design.md",
        "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
    ]
    diff = "+ pytest tier0-validation-gate route handler retrieval cache latency"

    hints = indexer.build_keyword_hints(commit, files, diff)

    assert ".agent/workflows/advisor-strategy-design.md" in hints
    assert "route" in hints
    assert "handler" in hints
    assert "tier0-validation-gate" not in hints
    assert "pytest" not in hints
