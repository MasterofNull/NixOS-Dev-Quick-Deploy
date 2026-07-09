#!/usr/bin/env python3
"""Regression: training-loop failures preserve actionable delegation status."""

from __future__ import annotations

import asyncio
import importlib.machinery
import json
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-local-training-loop"


def load_module():
    loader = importlib.machinery.SourceFileLoader("aq_local_training_loop_test", str(MODULE_PATH))
    return loader.load_module()


async def main() -> int:
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="training-loop-timeout-task-id-") as tmp:
        tmpdir = Path(tmp)
        mod.RESULTS_LOG = tmpdir / "training-loop-results.jsonl"
        mod.PROGRESS_FILE = tmpdir / "training-loop-progress.json"
        mod.DELEGATION_DIR = tmpdir
        mod.CHECKPOINT_FILE = tmpdir / "training-loop-checkpoint.json"
        mod.PULSE_LOG = tmpdir / "PULSE.log"

        class FakeIngestor:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, hours=24):
                return {"positive_samples_added": 0, "dataset_total": 1, "top_failures": []}

        submitted: list[str] = []
        fake_training_ingest = types.ModuleType("training_ingest")
        fake_training_ingest.TrainingIngestor = FakeIngestor
        sys.modules["training_ingest"] = fake_training_ingest
        mod._load_eval_pack = lambda _path: [
            {
                "id": "case-timeout",
                "query": "timeout please",
                "mode": "hybrid",
                "expected_keywords": ["ok"],
            },
            {
                "id": "case-submit-failed",
                "query": "submit failure please",
                "mode": "hybrid",
                "expected_keywords": ["ok"],
            },
        ]
        def fake_submit(query, mode="hybrid", http_timeout_secs=0):
            if query == "submit failure please":
                return None
            task_id = "local-test-timeout" if query == "timeout please" else "local-test-improve"
            submitted.append(task_id)
            return task_id

        mod._submit_task = fake_submit

        async def fake_wait(_task_id: str, timeout_s: int):
            return None

        mod._wait_for_task = fake_wait
        mod._generate_improvement_prompt = lambda _failing, _ingest: "improve"
        mod._certify_scorer = lambda: (False, "test uncertified scorer")
        loop = mod.TrainingLoop(eval_pack=Path("unused.json"), task_timeout=1, dry_run=True, verbose=False)
        result = await loop.run_once()

    score = result["scores"][0]
    submit_failed = result["scores"][1]
    assert submitted[0] == "local-test-timeout", submitted
    assert score["task_id"] == "local-test-timeout", result
    assert score["error"] == "timeout_or_failed", result
    assert submit_failed["case_id"] == "case-submit-failed", result
    assert submit_failed["task_id"] is None, result
    assert submit_failed["error"] == "submit_failed", result
    assert result["scorer_certified"] is False, result
    assert result["pass_rate_trusted"] is False, result
    print("PASS: training-loop failures preserve actionable delegation status")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
