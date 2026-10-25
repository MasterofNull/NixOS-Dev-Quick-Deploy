#!/usr/bin/env python3
"""
Test suite verifying aq-durable-sweeper's ingestion of SOTA taxonomy sources
and vectorization readiness into Qdrant/AIDB collections.
"""

import sys
import unittest
import tempfile
import json
from pathlib import Path
import importlib.machinery
import importlib.util

sweeper_path = Path(__file__).resolve().parents[1] / "ai" / "aq-durable-sweeper"
loader = importlib.machinery.SourceFileLoader("aq_durable_sweeper", str(sweeper_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
sweeper = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = sweeper
loader.exec_module(sweeper)

class TestSweeperTaxonomy(unittest.TestCase):
    def test_classify_heuristic_signal(self):
        title = "IndyDevDan: Durable Agent Execution & State Checkpointing"
        content = "Deep dive into building durable agents that persist execution state across restarts using event logs and subagent orchestration."
        res = sweeper.classify_heuristic(title, content)
        self.assertEqual(res["category"], "signal")
        self.assertGreaterEqual(res["confidence"], 0.8)
        self.assertIn(res["target_rag_collection"], ["skills-patterns", "best-practices"])

    def test_classify_heuristic_hype(self):
        title = "This Insane AI Replaces All Humans!"
        content = "Game-changer! It will blow your mind and is 100x faster than everything!"
        res = sweeper.classify_heuristic(title, content)
        self.assertEqual(res["category"], "hype")
        self.assertEqual(res["target_rag_collection"], "none")

    def test_classify_heuristic_facts(self):
        title = "Security Advisory CVE-2026-1029: Linux Kernel Timing Vulnerability"
        content = "Patch released for kernel page table isolation to address side-channel leaks."
        res = sweeper.classify_heuristic(title, content)
        self.assertEqual(res["category"], "facts")
        self.assertIn("best-practices", res["target_rag_collection"])

    def test_state_tracking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = sweeper.load_state(state_file)
            res1 = sweeper.process_item(state, "Test Architecture", "unit-test", "durable agent pattern")
            self.assertEqual(res1["status"], "processed")

            # Idempotency check
            res2 = sweeper.process_item(state, "Test Architecture", "unit-test", "durable agent pattern")
            self.assertEqual(res2["status"], "skipped")

if __name__ == "__main__":
    unittest.main()
