#!/usr/bin/env python3
"""Tests for the on-demand frontier context provider (FA-2 pull model)."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIBDIR = REPO / "scripts" / "ai" / "lib"


def load():
    # frontier_context imports frontier_relevance by name.
    sys.path.insert(0, str(LIBDIR))
    for name in ("frontier_relevance", "frontier_context"):
        spec = importlib.util.spec_from_file_location(name, LIBDIR / f"{name}.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules["frontier_context"]


CAT = {"weights": {"core": 3, "supporting": 2, "peripheral": 1}, "concepts": [
    {"id": "local-inference", "tier": "core", "keywords": ["kv cache", "inference", "llama.cpp"], "why": "serving"},
    {"id": "observability", "tier": "supporting", "keywords": ["telemetry", "dashboard"], "why": "monitor"},
]}
NOW = 1_700_000_000.0
DAY = 86400.0


def _iso(ts):
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_surfaces_candidates_and_fresh():
    fc = load()
    backlog = [{"id": "FE-1", "technique": "KV cache compression", "claim": "keeps context",
                "verdict": "monitor", "status": "new", "discovered_at": _iso(NOW - 5 * DAY)}]
    ctx = fc.context_for_topic("kv cache inference", CAT, backlog, now=NOW, stale_days=30)
    assert "local-inference" in ctx["relevant_concepts"]
    li = [p for p in ctx["per_concept"] if p["concept"] == "local-inference"][0]
    assert li["candidates"][0]["id"] == "FE-1"
    assert li["stale"] is False
    assert ctx["refresh_recommended"] is False


def test_gap_topic_is_stale_and_recommends_refresh():
    fc = load()
    # topic hits observability, which has NO candidate in the backlog
    ctx = fc.context_for_topic("telemetry dashboard", CAT, [], now=NOW)
    assert "observability" in ctx["stale_concepts"]
    assert ctx["refresh_recommended"] is True
    assert "scan-topic" in ctx["refresh_cmd"]


def test_old_candidate_is_stale():
    fc = load()
    backlog = [{"id": "FE-1", "technique": "inference", "claim": "x", "verdict": "adopt",
                "status": "approved", "discovered_at": _iso(NOW - 90 * DAY)}]
    ctx = fc.context_for_topic("inference", CAT, backlog, now=NOW, stale_days=30)
    li = [p for p in ctx["per_concept"] if p["concept"] == "local-inference"][0]
    assert li["stale"] is True and ctx["refresh_recommended"] is True


def test_offtopic_has_no_concepts():
    fc = load()
    ctx = fc.context_for_topic("medieval basket weaving", CAT, [], now=NOW)
    assert ctx["relevant_concepts"] == [] and ctx["refresh_recommended"] is False
    assert "no matched concepts" in fc.render(ctx)


def test_render_includes_topic_and_candidate():
    fc = load()
    backlog = [{"id": "FE-1", "technique": "kv cache", "claim": "keeps ctx", "verdict": "monitor",
                "status": "new", "discovered_at": _iso(NOW)}]
    out = fc.render(fc.context_for_topic("kv cache", CAT, backlog, now=NOW))
    assert "kv cache" in out and "FE-1" in out


def main() -> int:
    test_surfaces_candidates_and_fresh()
    test_gap_topic_is_stale_and_recommends_refresh()
    test_old_candidate_is_stale()
    test_offtopic_has_no_concepts()
    test_render_includes_topic_and_candidate()
    print("test-frontier-context: ok 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
