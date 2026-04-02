#!/usr/bin/env python3
"""Regression test for continuous-learning watchfile logging noise."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))


class FakeLogger:
    def __init__(self) -> None:
        self.debug_calls = []
        self.info_calls = []

    def debug(self, *args, **kwargs) -> None:
        self.debug_calls.append((args, kwargs))

    def info(self, *args, **kwargs) -> None:
        self.info_calls.append((args, kwargs))

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


fake_logger = FakeLogger()

if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(get_logger=lambda: fake_logger)

import continuous_learning as module  # noqa: E402
from continuous_learning import ContinuousLearningPipeline  # noqa: E402

module.logger = fake_logger


class DummySettings:
    embedding_dimensions = 384


class FakeWatcher:
    def __init__(self, changes):
        self._changes = list(changes)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._changes:
            raise StopAsyncIteration
        return self._changes.pop(0)

    async def aclose(self):
        self.closed = True


async def main_async() -> int:
    with tempfile.TemporaryDirectory(prefix="continuous-learning-watchfiles-") as tmpdir:
        root = Path(tmpdir)
        telemetry_dir = root / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        events_path = telemetry_dir / "hybrid-events.jsonl"
        events_path.write_text("", encoding="utf-8")

        os.environ["DATA_DIR"] = str(root)
        pipeline = ContinuousLearningPipeline(DummySettings(), None, None)
        pipeline.telemetry_paths = [events_path]
        pipeline.watch_enabled = True

        watcher = FakeWatcher([{("modified", str(events_path))}])
        original_awatch = module.awatch
        module.awatch = lambda *args, **kwargs: watcher
        try:
            changed = await pipeline._wait_for_telemetry_change(timeout_seconds=1)
        finally:
            module.awatch = original_awatch

        assert changed is True
        assert watcher.closed is True
        assert any(args and args[0] == "telemetry_change_detected" for args, _ in fake_logger.debug_calls)
        assert not any(args and args[0] == "telemetry_change_detected" for args, _ in fake_logger.info_calls)

    print("PASS: continuous learning watchfile updates log at debug level only")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
