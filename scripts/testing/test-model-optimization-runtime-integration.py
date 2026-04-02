#!/usr/bin/env python3
"""Regression checks for Phase 5 runtime model-optimization integration."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakePoint:
    def __init__(self, payload):
        self.payload = payload


class FakeQdrant:
    def __init__(self, payload):
        self.payload = payload
        self.updated = None

    def retrieve(self, collection_name, ids):
        return [FakePoint(dict(self.payload))]

    def set_payload(self, collection_name, payload, points):
        self.updated = {
            "collection_name": collection_name,
            "payload": payload,
            "points": points,
        }


async def _run_check() -> None:
    with tempfile.TemporaryDirectory(prefix="model-optimization-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["MODEL_OPTIMIZATION_STATE"] = str(tmp_path / "model-optimization")

        interaction_tracker = importlib.import_module("interaction_tracker")
        interaction_tracker = importlib.reload(interaction_tracker)

        model_optimization = importlib.import_module("model_optimization")
        model_optimization = importlib.reload(model_optimization)

        captured_calls = []
        performance_calls = []

        async def fake_capture_training_example(**kwargs):
            captured_calls.append(kwargs)
            return {"captured": True}

        async def fake_record_model_performance(**kwargs):
            performance_calls.append(kwargs)
            return {"recorded": True}

        model_optimization.capture_training_example = fake_capture_training_example
        model_optimization.record_model_performance = fake_record_model_performance

        payload = {
            "query": "How do I configure NixOS services safely?",
            "response": "Use declarative modules and validate before deploy.",
            "agent_type": "documentation",
            "model_used": "qwen-coder",
            "context_provided": [],
            "outcome": "unknown",
            "user_feedback": 0,
            "latency_ms": 245,
        }
        fake_qdrant = FakeQdrant(payload)
        interaction_tracker._qdrant = fake_qdrant
        interaction_tracker._llama_cpp = None
        interaction_tracker._store_memory = None

        await interaction_tracker.update_interaction_outcome(
            interaction_id="int-123",
            outcome="success",
            user_feedback=1,
        )

        assert_true(fake_qdrant.updated is not None, "interaction outcome should still update qdrant payload")
        assert_true(len(captured_calls) == 1, "successful interaction should be captured for model training")
        assert_true(captured_calls[0]["metadata"]["interaction_id"] == "int-123", "captured training example should include interaction metadata")
        assert_true(captured_calls[0]["outcome"] == "success", "captured training example should preserve outcome")
        assert_true(len(performance_calls) == 1, "successful interaction should record model performance")
        assert_true(performance_calls[0]["model_id"] == "qwen-coder", "model performance should be attributed to the interaction model")
        assert_true(performance_calls[0]["accuracy"] == 1.0, "successful outcome should map to perfect accuracy")
        assert_true(performance_calls[0]["quality_score"] > 0.0, "model performance should use computed value score")


def main() -> int:
    asyncio.run(_run_check())
    print("PASS: model optimization runtime integration regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
