#!/usr/bin/env python3
"""test-hints-feedback-aidb-producer.py — test suite for hints feedback AIDB interaction_history producer.

Validates that:
  1. handle_hints_feedback writes the feedback entry to the local jsonl log.
  2. _publish_hint_feedback_to_aidb builds the payload required by meta_optimizer and
     harness_evolution_tracker (including metadata.hint_template = hint_id, outcome, value_score).
  3. _publish_hint_feedback_to_aidb posts to /history/record and handles connection failures fail-safe.
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

_REPO = Path(__file__).resolve().parents[2]
_HYBRID = _REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
_KNOWLEDGE = _HYBRID / "knowledge"

sys.path.insert(0, str(_HYBRID))
sys.path.insert(0, str(_KNOWLEDGE))

import hints_handlers


class TestHintsFeedbackAidbProducer(unittest.IsolatedAsyncioTestCase):
    async def test_publish_payload_structure_success(self):
        """Verify _publish_hint_feedback_to_aidb constructs correct payload with hint_template."""
        entry = {
            "timestamp": "2026-10-10T12:00:00Z",
            "hint_id": "rag_low_sample_hint",
            "helpful": True,
            "score": 0.9,
            "comment": "Worked well",
            "agent": "codex",
            "task_id": "task_abc_123",
            "source": "agent_feedback",
            "agent_preferences": {"preferred_tools": ["agrep"]},
        }

        posted_payload = None

        async def fake_post(url, json=None, headers=None):
            nonlocal posted_payload
            posted_payload = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        mock_client = AsyncMock()
        mock_client.post = fake_post
        mock_client.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_client):
            await hints_handlers._publish_hint_feedback_to_aidb(entry)

        self.assertIsNotNone(posted_payload, "Expected post to be called")
        self.assertEqual(posted_payload["agent_type"], "codex")
        self.assertEqual(posted_payload["outcome"], "success")
        self.assertEqual(posted_payload["project"], "hint-feedback")
        self.assertEqual(posted_payload["value_score"], 0.9)
        self.assertEqual(posted_payload["metadata"]["hint_template"], "rag_low_sample_hint")
        self.assertEqual(posted_payload["metadata"]["task_id"], "task_abc_123")
        self.assertTrue(posted_payload["metadata"]["helpful"])
        self.assertEqual(posted_payload["metadata"]["score"], 0.9)

    async def test_publish_payload_structure_failure(self):
        """Verify negative feedback yields outcome='failure'."""
        entry = {
            "timestamp": "2026-10-10T12:00:00Z",
            "hint_id": "unhelpful_hint",
            "helpful": False,
            "score": 0.2,
            "comment": "Did not help",
            "agent": "qwen",
            "task_id": "task_xyz_456",
        }

        posted_payload = None

        async def fake_post(url, json=None, headers=None):
            nonlocal posted_payload
            posted_payload = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        mock_client = AsyncMock()
        mock_client.post = fake_post
        mock_client.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_client):
            await hints_handlers._publish_hint_feedback_to_aidb(entry)

        self.assertIsNotNone(posted_payload)
        self.assertEqual(posted_payload["outcome"], "failure")
        self.assertEqual(posted_payload["value_score"], 0.2)
        self.assertEqual(posted_payload["metadata"]["hint_template"], "unhelpful_hint")

    async def test_publish_handles_network_failure_fail_safe(self):
        """Verify network exceptions in _publish_hint_feedback_to_aidb do not raise."""
        entry = {
            "timestamp": "2026-10-10T12:00:00Z",
            "hint_id": "any_hint",
            "helpful": True,
        }

        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionRefusedError("AIDB down")
        mock_client.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Should not raise
            await hints_handlers._publish_hint_feedback_to_aidb(entry)

    async def test_handle_hints_feedback_e2e(self):
        """Verify handle_hints_feedback writes log and schedules background publish."""
        with tempfile.TemporaryDirectory(prefix="test-hints-feedback-") as tmpdir:
            log_file = Path(tmpdir) / "hint-feedback.jsonl"
            with patch("hints_handlers._hint_feedback_log_path", return_value=log_file):
                with patch("hints_handlers._publish_hint_feedback_to_aidb", new_callable=AsyncMock) as mock_pub:
                    # Mock aiohttp Request
                    req = AsyncMock()
                    req.json = AsyncMock(return_value={
                        "hint_id": "test_hint_e2e",
                        "helpful": True,
                        "score": 0.8,
                        "agent": "gemini",
                        "comment": "very useful",
                    })

                    resp = await hints_handlers.handle_hints_feedback(req)
                    self.assertEqual(resp.status, 200)

                    # Verify log file was written
                    self.assertTrue(log_file.exists())
                    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
                    self.assertEqual(len(lines), 1)
                    logged = json.loads(lines[0])
                    self.assertEqual(logged["hint_id"], "test_hint_e2e")
                    self.assertEqual(logged["agent"], "gemini")

                    # Allow event loop tasks to run
                    await asyncio.sleep(0.01)
                    mock_pub.assert_called_once()
                    call_entry = mock_pub.call_args[0][0]
                    self.assertEqual(call_entry["hint_id"], "test_hint_e2e")


if __name__ == "__main__":
    unittest.main()
