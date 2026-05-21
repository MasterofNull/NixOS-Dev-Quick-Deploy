#!/usr/bin/env python3
"""Regression tests for aq-index-knowledge-graph safe defaults."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "aq-index-knowledge-graph"


def load_module():
    loader = importlib.machinery.SourceFileLoader("aq_index_knowledge_graph", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    sample = "HybridCoordinator uses Qdrant\nmySystem.aiStack.enable = true"
    triples = list(module._extract_regex(sample, "sample.md", 0))
    assert triples, "regex fallback should extract at least one triple"

    text = SCRIPT.read_text(encoding="utf-8")
    assert "--ingest" in text, "indexer must require explicit --ingest for writes"
    assert "if not args.ingest" in text, "indexer default must be dry-run"
    assert "AIDB_API_KEY_FILE" in text, "indexer env var should be explicit and contract-backed"
    assert "--max-triples" in text, "indexer must cap extraction/ingest volume"
    print("PASS: aq-index-knowledge-graph has safe dry-run default and regex fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
