#!/usr/bin/env python3
"""
Phase 103 regression tests — cross-agent contradiction detection → attention archive.

Tests:
  1. memory_broker blocked contradiction → attention archive entry
  2. memory_broker unblocked (superseded) contradiction → no attention archive entry
  3. consensus_arbiter severe divergence (score < 0.5) → attention archive entry
  4. consensus_arbiter moderate divergence (0.5 ≤ score < 0.7) → no archive entry (synthesis only)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(_REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))


class TestMemoryBrokerContradictionAttention(unittest.IsolatedAsyncioTestCase):

    async def _run_emit(self, old_id: str, new_content: str, blocked: bool, attn_dir: Path) -> None:
        """Helper: run _emit_contradiction_event with patched HTTP and attention dir."""
        os.environ["ATTENTION_QUEUE_DIR"] = str(attn_dir)
        # Re-import to pick up the env var override on _ATTENTION_DIR
        import importlib
        import attention_queue as aq_mod
        importlib.reload(aq_mod)

        from memory_broker import MemoryBroker
        broker = MemoryBroker.__new__(MemoryBroker)

        # Patch aiohttp so HTTP post never fires
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.post = AsyncMock(return_value=AsyncMock())
            mock_session_cls.return_value = mock_session

            await broker._emit_contradiction_event(old_id, new_content, blocked=blocked)

        # Clean up env override
        del os.environ["ATTENTION_QUEUE_DIR"]

    def test_blocked_contradiction_pushes_to_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            attn_dir = Path(tmpdir)
            asyncio.run(self._run_emit("mem-abc123def456", "The sky is green.", blocked=True, attn_dir=attn_dir))

            archive = attn_dir / "ATTENTION_ARCHIVE.jsonl"
            self.assertTrue(archive.exists(), "ATTENTION_ARCHIVE.jsonl should exist after blocked contradiction")
            entries = [json.loads(l) for l in archive.read_text().splitlines() if l.strip()]
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e["source"], "memory-broker")
            self.assertEqual(e["severity"], "medium")
            self.assertEqual(e["autonomy_boundary"], "auto_ok")
            self.assertIn("mem-abc123", e["title"])

    def test_superseded_contradiction_no_archive_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            attn_dir = Path(tmpdir)
            asyncio.run(self._run_emit("mem-xyz789", "The sky is blue.", blocked=False, attn_dir=attn_dir))

            archive = attn_dir / "ATTENTION_ARCHIVE.jsonl"
            entries = []
            if archive.exists():
                entries = [json.loads(l) for l in archive.read_text().splitlines() if l.strip()]
            mb_entries = [e for e in entries if e.get("source") == "memory-broker"]
            self.assertEqual(len(mb_entries), 0, "Superseded (non-blocked) contradiction should NOT push to archive")


class TestConsensusArbiterDivergenceAttention(unittest.IsolatedAsyncioTestCase):

    def _make_candidates(self, n: int) -> list:
        return [{"response": f"Agent {i} response", "intent_classification": {"confidence": 0.5}} for i in range(n)]

    async def _run_resolve_with_low_consensus(self, score: float, attn_dir: Path) -> None:
        os.environ["ATTENTION_QUEUE_DIR"] = str(attn_dir)
        import importlib
        import attention_queue as aq_mod
        importlib.reload(aq_mod)

        from consensus_arbiter import ConsensusArbiter
        arbiter = ConsensusArbiter()
        arbiter._MIN_CONSENSUS_SCORE = 0.7

        # Patch _majority_vote to return a fixed low score
        arbiter._majority_vote = AsyncMock(return_value={
            "response": "agent output",
            "consensus_score": score,
            "consensus_strategy": "majority_vote",
        })
        # Patch _synthesize to avoid LLM call
        arbiter._synthesize = AsyncMock(return_value={
            "response": "synthesized",
            "consensus_score": 0.95,
            "consensus_strategy": "model_synthesis",
        })

        candidates = self._make_candidates(2)
        await arbiter.resolve(candidates, strategy="majority_vote", task="Is the sky blue or green?")
        del os.environ["ATTENTION_QUEUE_DIR"]

    def test_severe_divergence_pushes_to_archive(self):
        """consensus_score < 0.5 → auto_ok archive entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            attn_dir = Path(tmpdir)
            asyncio.run(self._run_resolve_with_low_consensus(0.3, attn_dir))

            archive = attn_dir / "ATTENTION_ARCHIVE.jsonl"
            self.assertTrue(archive.exists(), "ATTENTION_ARCHIVE.jsonl should exist for severe divergence")
            entries = [json.loads(l) for l in archive.read_text().splitlines() if l.strip()]
            cb_entries = [e for e in entries if e.get("source") == "consensus-arbiter"]
            self.assertEqual(len(cb_entries), 1)
            self.assertEqual(cb_entries[0]["severity"], "medium")
            self.assertIn("0.30", cb_entries[0]["title"])

    def test_moderate_divergence_no_archive_entry(self):
        """consensus_score 0.5–0.7 → synthesis only, no archive entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            attn_dir = Path(tmpdir)
            asyncio.run(self._run_resolve_with_low_consensus(0.6, attn_dir))

            archive = attn_dir / "ATTENTION_ARCHIVE.jsonl"
            entries = []
            if archive.exists():
                entries = [json.loads(l) for l in archive.read_text().splitlines() if l.strip()]
            cb_entries = [e for e in entries if e.get("source") == "consensus-arbiter"]
            self.assertEqual(len(cb_entries), 0, "Moderate divergence (0.6) should NOT push to archive")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryBrokerContradictionAttention))
    suite.addTests(loader.loadTestsFromTestCase(TestConsensusArbiterDivergenceAttention))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"\n{passed}/{result.testsRun} tests passed")
    sys.exit(0 if result.wasSuccessful() else 1)
