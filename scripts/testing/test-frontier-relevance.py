#!/usr/bin/env python3
"""Tests for frontier relevance scoring + concept coverage (FA-1c)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "frontier_relevance.py"
CONCEPTS = REPO / ".agents" / "plans" / "frontier-evidence-intake" / "concepts.yaml"


def load():
    spec = importlib.util.spec_from_file_location("frontier_relevance", LIB)
    m = importlib.util.module_from_spec(spec)
    sys.modules["frontier_relevance"] = m
    spec.loader.exec_module(m)
    return m


def _cat():
    return {"weights": {"core": 3, "supporting": 2, "peripheral": 1}, "concepts": [
        {"id": "local-inference", "tier": "core", "keywords": ["llama.cpp", "quantization", "moe"], "why": "serving"},
        {"id": "prompt-optimization", "tier": "supporting", "keywords": ["dspy", "gepa"], "why": "prompts"},
        {"id": "speculative-decoding", "tier": "peripheral", "keywords": ["speculative decoding", "draft model"], "why": "latency"},
    ]}


def test_core_weighs_more_than_peripheral():
    fr = load()
    cat = _cat()
    core = fr.score_text(cat, "a new quantization method for llama.cpp moe models")
    periph = fr.score_text(cat, "speculative decoding with a draft model")
    assert core["core_matched"] is True
    assert core["relevance"] > periph["relevance"]  # 3 core hits*3 > 2 periph*1
    assert core["top_concept"] == "local-inference"


def test_irrelevant_text_scores_zero():
    fr = load()
    res = fr.score_text(_cat(), "a paper about medieval basket weaving")
    assert res["relevance"] == 0 and res["matched_concepts"] == [] and res["top_concept"] is None


def test_word_boundary_avoids_false_positive():
    fr = load()
    # "moe" must not match inside "smoenixon"; "gepa" must not match "gepard"
    res = fr.score_text(_cat(), "smoenixon gepard")
    assert res["relevance"] == 0, res


def test_hyphenated_paper_terms_match_spaced_keywords():
    # Regression (found by dogfooding CompressKV): papers write "KV-cache" and
    # "long-context" with hyphens; keywords use spaces. They must still match.
    fr = load()
    cat = {"weights": {"core": 3}, "concepts": [
        {"id": "context-engineering", "tier": "core",
         "keywords": ["kv cache compression", "long context"], "why": "ctx"}]}
    res = fr.score_text(cat, "Semantic-retrieval-guided KV-cache compression for long-context inference")
    assert res["relevance"] > 0 and res["top_concept"] == "context-engineering", res


def test_coverage_flags_gaps():
    fr = load()
    cat = _cat()
    sources = [{"name": "llama.cpp", "why": "our engine", "pillar": "local-inference"}]
    backlog = [{"technique": "GEPA", "claim": "dspy optimizer", "aqos_mapping": "prompts"}]
    cov = fr.concept_coverage(cat, sources, backlog)
    rows = {r["concept"]: r for r in cov["concepts"]}
    # local-inference: source yes, candidate no -> gap (core)
    assert rows["local-inference"]["sources_tracking"] == 1
    assert rows["local-inference"]["candidates_found"] == 0
    assert rows["local-inference"]["gap"] is True
    # prompt-optimization: candidate yes, source no -> gap (supporting)
    assert rows["prompt-optimization"]["candidates_found"] == 1
    assert rows["prompt-optimization"]["gap"] is True
    # peripheral with nothing -> NOT a gap (breadth, low priority)
    assert rows["speculative-decoding"]["gap"] is False


def test_validate_and_real_taxonomy():
    fr = load()
    bad = {"weights": {"core": 3}, "concepts": [{"id": "x", "tier": "nope", "keywords": []}]}
    issues = fr.validate(bad)
    assert any("tier" in i for i in issues) and any("keywords" in i for i in issues)
    try:
        real = fr.load_concepts(CONCEPTS)
    except RuntimeError:
        print("  (PyYAML absent — skipping real-taxonomy validation)")
        return
    assert fr.validate(real) == [], fr.validate(real)
    # a real frontier abstract should light up core concepts
    res = fr.score_text(real, "Process reward models and test-time compute for agent verification with tier0 gates")
    assert res["core_matched"] and res["relevance"] > 0


def main() -> int:
    test_core_weighs_more_than_peripheral()
    test_irrelevant_text_scores_zero()
    test_word_boundary_avoids_false_positive()
    test_hyphenated_paper_terms_match_spaced_keywords()
    test_coverage_flags_gaps()
    test_validate_and_real_taxonomy()
    print("test-frontier-relevance: ok 6/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
