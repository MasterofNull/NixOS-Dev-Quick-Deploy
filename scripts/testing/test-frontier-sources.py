#!/usr/bin/env python3
"""Tests for the frontier source catalog + source-quality metrics (FA-1b)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "frontier_sources.py"
CATALOG = REPO / ".agents" / "plans" / "frontier-evidence-intake" / "sources.yaml"


def load():
    spec = importlib.util.spec_from_file_location("frontier_sources", LIB)
    m = importlib.util.module_from_spec(spec)
    sys.modules["frontier_sources"] = m
    spec.loader.exec_module(m)
    return m


def _cat(**over):
    base = {"pillars": ["a", "b"], "sources": [
        {"id": "s1", "name": "S1", "kind": "repo", "url": "u", "pillar": "a", "trust_tier": "primary", "cadence": "weekly", "why": "w"},
        {"id": "s2", "name": "S2", "kind": "blog", "url": "u", "pillar": "b", "trust_tier": "secondary", "cadence": "monthly", "why": "w"},
    ]}
    base.update(over)
    return base


def test_validate_flags_bad_fields():
    fs = load()
    bad = _cat(sources=[{"id": "x", "name": "X", "kind": "k", "url": "u", "pillar": "zzz", "trust_tier": "banana", "cadence": "c", "why": "w"}])
    issues = fs.validate(bad)
    assert any("trust_tier" in i for i in issues), issues
    assert any("not in declared pillars" in i for i in issues), issues


def test_validate_catches_duplicate_ids():
    fs = load()
    dup = _cat()
    dup["sources"].append(dict(dup["sources"][0]))  # duplicate id s1
    assert any("duplicate source id" in i for i in fs.validate(dup))


def test_coverage_counts_and_risk():
    fs = load()
    cov = fs.coverage(_cat())
    assert cov["total"] == 2
    assert cov["by_pillar"]["a"] == {"total": 1, "primary": 1}
    assert cov["by_trust"] == {"primary": 1, "secondary": 1}
    # pillar b has only a secondary source -> coverage risk
    assert "b" in cov["pillars_without_primary"]


def test_source_signal_adopt_rate():
    fs = load()
    cat = _cat()
    backlog = [
        {"source_ids": ["s1"], "verdict": "adopt"},
        {"source_ids": ["s1"], "verdict": "monitor"},
        {"source_ids": ["s2"], "verdict": "drop"},
    ]
    rows = {r["source_id"]: r for r in fs.source_signal(cat, backlog)}
    assert rows["s1"]["surfaced"] == 2 and rows["s1"]["adopted"] == 1
    assert rows["s1"]["adopt_rate"] == 0.5
    assert rows["s2"]["adopt_rate"] == 0.0


def test_real_catalog_is_valid():
    fs = load()
    try:
        cat = fs.load_catalog(CATALOG)
    except RuntimeError:
        print("  (PyYAML absent — skipping real-catalog validation)")
        return
    issues = fs.validate(cat)
    assert issues == [], issues
    cov = fs.coverage(cat)
    # every declared pillar must have at least one primary source
    assert cov["pillars_without_primary"] == [], cov["pillars_without_primary"]


def main() -> int:
    test_validate_flags_bad_fields()
    test_validate_catches_duplicate_ids()
    test_coverage_counts_and_risk()
    test_source_signal_adopt_rate()
    test_real_catalog_is_valid()
    print("test-frontier-sources: ok 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
