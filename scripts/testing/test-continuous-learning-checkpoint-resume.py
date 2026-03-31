#!/usr/bin/env python3
"""Regression test for continuous-learning telemetry checkpoint reads."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        )
    )

from continuous_learning import ContinuousLearningPipeline  # noqa: E402


class DummySettings:
    embedding_dimensions = 384


async def main_async() -> int:
    with tempfile.TemporaryDirectory(prefix="continuous-learning-checkpoint-") as tmpdir:
        root = Path(tmpdir)
        telemetry_dir = root / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        events_path = telemetry_dir / "hybrid-events.jsonl"
        rows = [
            {
                "event": "task_completed",
                "task_id": "task-1",
                "status": "completed",
                "total_iterations": 1,
                "task": {"prompt": "test prompt", "output": "ok", "backend": "local", "iteration": 1, "context": {}},
            },
            {"event": "not-relevant"},
        ]
        events_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

        os.environ["DATA_DIR"] = str(root)
        pipeline = ContinuousLearningPipeline(DummySettings(), None, None)
        pipeline.telemetry_paths = [events_path]
        pipeline.checkpoint_interval = 1
        pipeline._filter_quality_patterns = lambda patterns: asyncio.sleep(0, result=patterns)
        pipeline._save_finetuning_examples = lambda _examples: asyncio.sleep(0)
        pipeline._index_patterns = lambda _patterns: asyncio.sleep(0)
        pipeline.generate_finetuning_examples = lambda _patterns: asyncio.sleep(0, result=[])
        pipeline._extract_pattern_from_event = lambda event: asyncio.sleep(
            0,
            result=None if event.get("event") != "task_completed" else object(),
        )

        patterns = await pipeline._process_telemetry_file(events_path)
        assert len(patterns) == 1
        assert pipeline.last_positions[str(events_path)] == events_path.stat().st_size
        assert pipeline.processed_count == 2

    print("PASS: continuous learning telemetry checkpoint reads preserve file offsets")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
