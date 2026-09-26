#!/usr/bin/env python3
"""Regression checks for truthful model-probe freshness receipts."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "ai-stack"
    / "mcp-servers"
    / "hybrid-coordinator"
    / "extensions"
    / "model_probe.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("model_probe_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("model_probe import spec should load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url):
        if url.endswith("/v1/models"):
            return Response({"data": [{"id": "active.gguf", "meta": {"n_ctx_train": 8192}}]})
        return Response(
            {
                "model_path": "/models/active.gguf",
                "chat_template_caps": {"supports_tools": True},
            }
        )


async def check_failed_measurement_does_not_refresh(module) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "profile.json"
        with (
            patch.object(module.httpx, "AsyncClient", return_value=Client()),
            patch.object(module, "_probe_speed", new=AsyncMock(return_value=None)),
        ):
            result = await module.probe("http://llama.invalid", profile_path)
        assert result.throughput_source == "fallback"
        assert not profile_path.exists(), "failed throughput probe must not mint a fresh receipt"


async def check_successful_measurement_is_source_labelled(module) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "profile.json"
        with (
            patch.object(module.httpx, "AsyncClient", return_value=Client()),
            patch.object(module, "_probe_speed", new=AsyncMock(return_value=1.7)),
        ):
            result = await module.probe("http://llama.invalid", profile_path)
        assert result.throughput_source == "live_probe"
        assert result.measured_tps_output == 1.7
        assert profile_path.exists(), "successful throughput probe must persist its receipt"
        payload = profile_path.read_text(encoding="utf-8")
        assert '"throughput_source": "live_probe"' in payload
        assert '"reviewed_at"' in payload


def main() -> int:
    module = load_module()
    asyncio.run(check_failed_measurement_does_not_refresh(module))
    asyncio.run(check_successful_measurement_is_source_labelled(module))
    print("PASS: model probe only refreshes receipts after live throughput measurement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
