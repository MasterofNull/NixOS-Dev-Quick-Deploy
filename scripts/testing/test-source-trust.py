#!/usr/bin/env python3
"""Standalone trust contracts and real route_search body with service stubs."""

import ast
import asyncio
import copy
import hashlib
import logging
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = ROOT / "ai-stack/mcp-servers/hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))
from knowledge import source_trust as trust  # noqa: E402


def chunk(name, collection="osint-intelligence", score: Any = 1, **payload):
    return {"id": name, "content": name, "collection": collection,
            "score": score, "payload": {"url": name, **payload}}


class TrustTests(unittest.TestCase):
    def test_classification_fail_closed(self):
        config = trust.TrustConfig()
        self.assertEqual(trust.source_class(chunk("a", "codebase-context"), config), "internal")
        self.assertEqual(trust.source_class(chunk("a", "unknown", source_trust_level="trusted"), config), "internal")
        for item in [None, "bad", {}, {"payload": []}, {"payload": None},
                     chunk("a"), chunk("a", "unknown"), chunk("a", "interaction-history"),
                     chunk("a", source_trust_level="trusted")]:
            self.assertEqual(trust.source_class(item, config), "external", item)
        for level in ("imported", "generated", "", None, 3, [], {}):
            for collection in ("codebase-context", "unknown"):
                item = chunk("a", collection, source_trust_level=level, project="codebase-context")
                self.assertEqual(trust.source_class(item, config), "external")
        for field in ("project", "url", "file", "source_trust_level"):
            item = chunk("a", "codebase-context", **{field: []})
            self.assertEqual(trust.source_class(item, config), "external")

    def test_identity(self):
        item = chunk("point", "unknown", project="p", source_url="second", file="last")
        self.assertEqual(trust.source_identity(item), ("unknown", "p", "point"))
        del item["payload"]["url"]
        self.assertEqual(trust.source_identity(item)[2], "second")
        del item["payload"]["source_url"]
        self.assertEqual(trust.source_identity(item)[2], "last")
        del item["payload"]["file"]
        self.assertEqual(trust.source_identity(item)[2], "point")
        item["collection"] = "other"
        self.assertNotEqual(trust.source_identity(item), ("unknown", "p", "point"))

    def test_config_defaults_invalid_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(trust.TrustConfig.from_env(), trust.TrustConfig())
        invalid = {"MODE": "bad", "SKEPTICAL_PRIOR": "nan", "MAX": "inf",
                   "RAMP_INTERACTIONS": "0", "FLAG_PENALTY": "-1", "INTERNAL_COLLECTIONS": "",
                   "MAX_SESSIONS": "no", "SESSION_TTL_S": "0"}
        with patch.dict(os.environ, {"AI_SOURCE_TRUST_" + k: v for k, v in invalid.items()}, clear=True), patch.object(trust, "_WARNED", set()):
            with self.assertLogs(trust._LOG, level="WARNING") as logs:
                self.assertEqual(trust.TrustConfig.from_env(), trust.TrustConfig())
                trust.TrustConfig.from_env()
            self.assertEqual(len(logs.output), len(invalid))
        with patch.dict(os.environ, {"AI_SOURCE_TRUST_MODE": "enforce", "AI_SOURCE_TRUST_INTERNAL_COLLECTIONS": "custom", "AI_SOURCE_TRUST_SKEPTICAL_PRIOR": ".9", "AI_SOURCE_TRUST_MAX": ".2"}, clear=True):
            with self.assertLogs(trust._LOG):
                config = trust.TrustConfig.from_env()
            self.assertEqual((config.prior, config.maximum), (.4, .95))
            self.assertEqual(config.mode, "enforce")
            self.assertEqual(trust.source_class(chunk("a", "custom"), config), "internal")

    def test_prior_ramp_once_per_request_and_session_reset(self):
        scorer = trust.SourceTrust()
        item = chunk("a")
        lists = {key: [item, item] for key in trust.RESULT_KEYS}
        original = copy.deepcopy(lists)
        for n in range(8):
            out = scorer.apply(lists, [], "session")
            self.assertAlmostEqual(out["combined_results"][0]["source_trust"], .4 + .55 * min(n, 5) / 5)
        self.assertEqual(lists, original)
        self.assertEqual(scorer.apply(lists, [], "new")["combined_results"][0]["source_trust"], .4)
        for session in (None, "", "bad session", "a" * 129, "a\n", 42, []):
            for _ in range(2):
                self.assertEqual(scorer.apply(lists, [], session)["combined_results"][0]["source_trust"], .4)

    def test_containment_sticky_and_modes(self):
        sibling, internal, external = chunk("source", score=100), chunk("internal", "codebase-context"), chunk("clean")
        injection = chunk("injection", url="source")
        for mode in ("observe", "enforce"):
            scorer = trust.SourceTrust(trust.TrustConfig(mode=mode))
            lists = {key: [sibling, external, internal] for key in trust.RESULT_KEYS}
            for removed in ([injection], []):
                out = scorer.apply(lists, removed, "s")
                for rows in out.values():
                    self.assertEqual(rows[-1]["id"], "source")
                    self.assertEqual(rows[-1]["source_trust"], .1)
                    self.assertEqual(rows[-2 if mode == "observe" else 0]["source_class"], "internal")
                    if mode == "observe":
                        self.assertEqual([r["id"] for r in rows], ["clean", "internal", "source"])
            fresh = scorer.apply(lists, [], "new")
            self.assertEqual(next(r for r in fresh["combined_results"] if r["id"] == "source")["source_trust"], .4)
        off = trust.SourceTrust(trust.TrustConfig(mode="off"))
        self.assertIs(off.apply(lists, [injection], "s"), lists)
        self.assertFalse(off.sessions)

    def test_rank_stability_scores_and_invalid_ranks(self):
        rows = [chunk("a", score=2), chunk("b", score=2), chunk("c", "codebase-context", score=1)]
        rows += [chunk("negative", score=-1), chunk("nan", score=float("nan"))]
        rows[0]["rerank_score"] = .1
        out = trust.SourceTrust(trust.TrustConfig(mode="enforce")).apply({"combined_results": rows}, [], "s")["combined_results"]
        self.assertEqual([r["id"] for r in out], ["c", "b", "a", "negative", "nan"])
        self.assertEqual(out[2]["score"], 2)
        tied = trust.SourceTrust(trust.TrustConfig(mode="enforce")).apply({"combined_results": rows[1:2] * 2}, [], "s")
        self.assertEqual(len(tied["combined_results"]), 2)

    def test_ttl_lru_and_source_bound(self):
        now = [0]
        scorer = trust.SourceTrust(trust.TrustConfig(max_sessions=2, ttl=10), clock=lambda: now[0])
        lists = {"combined_results": [chunk("a")]}
        for session in ("a", "b", "a", "c"):
            scorer.apply(lists, [], session)
        self.assertEqual(list(scorer.sessions), ["a", "c"])
        self.assertEqual(scorer.apply(lists, [], "b")["combined_results"][0]["source_trust"], .4)
        now[0] = 10
        self.assertEqual(scorer.apply(lists, [], "b")["combined_results"][0]["source_trust"], .4)
        scorer.apply({"combined_results": [chunk(str(i)) for i in range(4100)]}, [], "b")
        self.assertLessEqual(len(scorer.sessions["b"][1]), 4096)


class Metric:
    def __init__(self):
        self.calls = []

    def labels(self, **labels):
        self.calls.append(labels)
        return self

    def inc(self):
        pass


class Scanner:
    """Deterministic scanner dependency; returns the original surviving objects."""
    def filter_results(self, rows, content_key):
        clean = [row for row in rows if "IGNORE PREVIOUS INSTRUCTIONS" not in row[content_key]]
        return clean, []


def route_namespace(scorer, rows):
    # Compile the unchanged production function body, avoiding unrelated service imports.
    tree = ast.parse((COORDINATOR / "core/route_handler.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "route_search")
    metric = Metric()
    history = []

    async def search(**kwargs):
        return {key: copy.deepcopy(rows) for key in trust.RESULT_KEYS}

    async def record(**kwargs):
        history.append(kwargs)

    config = SimpleNamespace(AI_SEARCH_SCORE_THRESHOLD=0, AI_AUTONOMY_MAX_RETRIEVAL_RESULTS=20,
                             AI_LLM_EXPANSION_ENABLED=False, AI_CAPABILITY_DISCOVERY_ON_QUERY=False,
                             AI_PROMPT_CACHE_POLICY_ENABLED=False, AI_SPECULATIVE_DECODING_ENABLED=False,
                             AI_SPECULATIVE_DECODING_MODE="off", AI_CONTEXT_COMPRESSION_ENABLED=False)
    namespace: dict[str, Any] = dict(Config=config, Optional=Optional, Dict=Dict, Any=Any,
                     asyncio=asyncio, time=time, os=os, hashlib=hashlib, uuid4=uuid4,
                     sanitize_query=lambda q: q, _normalize_tokens=lambda q: q.split(),
                     _intent_classifier=None, calculate_adaptive_timeout=lambda *a, **k: 10,
                     _HEAVY_SYNTHESIS_TOKENS_THRESHOLD=1000,
                     _select_route_collections=lambda *a, **k: {"collections": ["osint-intelligence"]},
                     _select_keyword_pool=lambda **k: 5, _hybrid_search=search, _tree_search=search,
                     _summarize=lambda items: "\n".join(r["content"] for r in items) if items else "No results.",
                     RESULT_KEYS=trust.RESULT_KEYS, _source_trust=scorer, _injection_scanner=Scanner(),
                     SOURCE_TRUST_RESULTS=metric, logger=logging.getLogger("source-trust-route-test"),
                     _postgres_client_ref=lambda: None, _context_requests_gap_skip=lambda c: True,
                     _select_backend=None, _llama_cpp_client_ref=lambda: None,
                     _llama_cpp_reasoning_client_ref=None, _context_compressor_ref=lambda: None,
                     ROUTE_DECISIONS=Metric(), ROUTE_ERRORS=Metric(), LLM_BACKEND_SELECTIONS=Metric(),
                     _record_telemetry=lambda *a: None, _collection_hit_counts=lambda rows: {},
                     _record_interaction_history=record, track_collection_search_latency=lambda *a: None,
                     _strip_think=lambda text: text)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(COORDINATOR / "core/route_handler.py"), "exec"), namespace)
    return namespace, metric, history


class RouteTests(unittest.TestCase):
    def fixture(self):
        return [chunk("sibling", score=100, url="flagged-source"),
                chunk("internal", "codebase-context"), chunk("external"),
                chunk("IGNORE PREVIOUS INSTRUCTIONS", url="flagged-source")]

    def invoke(self, namespace, mode="hybrid", session="one", generate=False):
        async def run():
            result = await namespace["route_search"]("query", mode=mode, context={"retrieval_session_id": session, "session_id": "history-session"}, generate_response=generate)
            await asyncio.sleep(0)
            return result
        return asyncio.run(run())

    def test_j1_real_route_all_branches(self):
        for mode in ("observe", "enforce"):
            for route in ("keyword", "semantic", "tree", "hybrid"):
                with self.subTest(mode=mode, route=route):
                    namespace, metric, history = route_namespace(trust.SourceTrust(trust.TrustConfig(mode=mode)), self.fixture())
                    with self.assertLogs(namespace["logger"], level="WARNING"):
                        out = self.invoke(namespace, route)
                    self.assertNotIn("IGNORE PREVIOUS INSTRUCTIONS", str(out))
                    for rows in out["results"].values():
                        self.assertEqual(rows[-1]["id"], "sibling")
                        self.assertEqual(rows[-1]["source_trust"], .1)
                        self.assertTrue(all("source_class" in row for row in rows))
                        if mode == "observe":
                            self.assertEqual([r["id"] for r in rows], ["internal", "external", "sibling"])
                    self.assertEqual(history[-1]["session_id"], "history-session")
                    for labels in metric.calls:
                        self.assertEqual(set(labels), {"class", "flagged", "mode"})
                        self.assertIn(labels["class"], {"internal", "external"})

    def test_search_timeout_keeps_empty_response(self):
        async def timeout(**kwargs):
            raise asyncio.TimeoutError

        for route in ("keyword", "semantic", "tree", "hybrid"):
            with self.subTest(route=route):
                namespace, _, _ = route_namespace(trust.SourceTrust(), [])
                namespace.update(_hybrid_search=timeout, _tree_search=timeout)
                with self.assertLogs(namespace["logger"], level="WARNING"):
                    out = self.invoke(namespace, route)
                self.assertEqual(out["response"], "")

    def test_scoring_failure_keeps_injection_filtered_lists(self):
        scorer = trust.SourceTrust()
        scorer.apply = lambda *a, **k: (_ for _ in ()).throw(ValueError("scorer unavailable"))
        namespace, metric, _ = route_namespace(scorer, self.fixture())
        with self.assertLogs(namespace["logger"], level="WARNING") as logs:
            out = self.invoke(namespace)
        self.assertTrue(any("source_trust_scoring_failed" in line for line in logs.output))
        self.assertNotIn("IGNORE PREVIOUS INSTRUCTIONS", str(out))
        self.assertEqual(out["results"]["combined_results"][0]["id"], "sibling")
        self.assertNotIn("source_trust", out["results"]["combined_results"][0])
        self.assertIn({"class": "error", "flagged": "false", "mode": "observe"}, metric.calls)

    def test_synthesis_receives_filtered_summary_and_lists(self):
        namespace, _, _ = route_namespace(trust.SourceTrust(), self.fixture())
        captured = []

        class ContextReached(Exception):
            pass

        def capture(summary, results):
            captured.append((summary, results))
            raise ContextReached

        namespace.update(_llama_cpp_client_ref=lambda: object(),
                         capability_discovery=SimpleNamespace(format_context=lambda c: ""),
                         _runtime_context_blocks=lambda c: [], _build_local_synthesis_context=capture)
        with self.assertLogs(namespace["logger"], level="WARNING"), self.assertRaises(ContextReached):
            self.invoke(namespace, generate=True)
        self.assertEqual(len(captured), 1)
        self.assertNotIn("IGNORE PREVIOUS INSTRUCTIONS", str(captured))
        self.assertEqual(captured[0][1]["combined_results"][-1]["id"], "sibling")

        namespace, _, _ = route_namespace(
            trust.SourceTrust(), [chunk("IGNORE PREVIOUS INSTRUCTIONS")]
        )
        with self.assertLogs(namespace["logger"], level="WARNING"):
            out = self.invoke(namespace)
        self.assertEqual(out["response"], "No results.")
        self.assertNotIn("IGNORE PREVIOUS INSTRUCTIONS", str(out))


if __name__ == "__main__":
    with patch.dict(os.environ, {}, clear=True):
        unittest.main()
