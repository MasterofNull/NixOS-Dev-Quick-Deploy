#!/usr/bin/env python3
"""Regression checks for truthful model-probe freshness receipts."""

from __future__ import annotations

import asyncio
import importlib.util
import datetime
import json
import os
import subprocess
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


def cached_payload(module):
    payload = module._default_profile().to_dict()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload.update(probe_model_id="active.gguf", probed_at=now, freshness_max_age_days=50)
    payload["_meta"] = {"reviewed_at": now, "custom_policy": "retained"}
    return payload


async def check_cache_freshness_and_force(module) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        payload = cached_payload(module)
        for stale_field in ("probed_at", "reviewed_at"):
            stale = json.loads(json.dumps(payload))
            old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=51)).isoformat()
            if stale_field == "reviewed_at":
                stale["_meta"][stale_field] = old
            else:
                stale[stale_field] = old
            path.write_text(json.dumps(stale))
            with (
                patch.object(module.httpx, "AsyncClient", return_value=Client()),
                patch.object(module, "_probe_speed", new=AsyncMock(return_value=2.5)) as speed,
            ):
                result = await module.probe("http://llama.invalid", path)
            speed.assert_awaited_once()
            assert result.measured_tps_output == 2.5
            saved = json.loads(path.read_text())
            assert saved["freshness_max_age_days"] == 50
            assert saved["_meta"]["custom_policy"] == "retained"
            assert module._is_cache_fresh(path)

        original = json.dumps(payload)
        path.write_text(original)
        with (
            patch.object(module.httpx, "AsyncClient", return_value=Client()),
            patch.object(module, "_probe_speed", new=AsyncMock(return_value=None)) as speed,
        ):
            await module.probe("http://llama.invalid", path)
            speed.assert_not_awaited()
            await module.probe("http://llama.invalid", path, force=True)
            speed.assert_awaited_once()
        assert path.read_text() == original, "failed forced probe must preserve the existing file byte-for-byte"
        with (
            patch.object(module.httpx, "AsyncClient", return_value=Client()),
            patch.object(module, "_probe_speed", new=AsyncMock(return_value=3.0)) as speed,
        ):
            await module.probe("http://llama.invalid", path, force=True)
            speed.assert_awaited_once()
        saved = json.loads(path.read_text())
        assert saved["freshness_max_age_days"] == 50
        assert saved["_meta"]["custom_policy"] == "retained"
        for bad_stamp in (None, "invalid", "2026-01-01T00:00:00"):
            saved["probed_at"] = bad_stamp
            path.write_text(json.dumps(saved))
            assert not module._is_cache_fresh(path)


def check_registry_reconciliation() -> None:
    spec = importlib.util.spec_from_file_location(
        "model_registry_under_test", MODULE_PATH.parent.parent / "model_registry.py"
    )
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    with tempfile.TemporaryDirectory() as tmp:
        model_dir = Path(tmp)
        current = model_dir / "current.gguf"
        previous = model_dir / "previous.gguf"
        current.touch()
        previous.touch()
        (model_dir / "active.gguf").symlink_to(current)
        models = {
            "current": {"file": current.name, "state": "failed", "local_path": None, "error": "cancelled"},
            "previous": {"file": previous.name, "state": "active", "promoted_at": 123},
            "missing": {"file": "missing.gguf", "state": "active"},
            "failed": {"file": previous.name, "state": "failed", "error": "cancelled"},
        }
        for state in ("downloading", "warming", "retiring"):
            models[state] = {"file": current.name, "state": state}
        with patch.object(registry, "MODEL_DIR", model_dir):
            registry._reconcile_disk_state(models)
            first = json.loads(json.dumps(models))
            registry._reconcile_disk_state(models)
        assert models == first, "repeated reconciliation must not append duplicate audit events"
        assert models["current"]["state"] == "active"
        assert models["current"]["local_path"] == str(current)
        assert models["current"]["error"] is None
        assert models["current"]["promoted_at"]
        assert models["previous"]["state"] == "verified"
        assert models["missing"]["state"] == "available"
        assert models["failed"]["state"] == "verified"
        assert models["failed"]["error"] is None
        for state in ("downloading", "warming", "retiring"):
            assert models[state] == {"file": current.name, "state": state}


def check_llm_domain_status(module) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        path.write_text(json.dumps(cached_payload(module)))
        models = Path(tmp) / "models"
        models.mkdir()
        model = models / "Qwen3.5-9B-Q6_K.gguf"
        model.touch()
        (models / "active.gguf").symlink_to(model)
        (models / "download.gguf.part").touch()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ai/aq-model-eval"),
             "--status", "--json", "--profile-path", str(path)],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "LLAMA_MODELS_DIR": str(models), "LLAMA_CPP_URL": "http://llama.invalid"},
        )
        assert result.returncode == 0, result.stderr
        status = json.loads(result.stdout)
        assert status["domain"] == "llm"
        assert status["profile_fresh"] is True
        assert status["active_profile"] == json.loads(path.read_text())
        assert "qwen3.5-9b" in status["catalog_chat_models"]
        assert "qwen3-embedding-4b" in status["catalog_embedding_models"]
        assert status["coordinator_tiers"]
        inventory = status["models_dir"]
        assert inventory["active_gguf_target"] == str(model)
        assert model.name in inventory["declared_files_present"]
        assert inventory["untracked_or_temp_files"] == ["download.gguf.part"]


def check_llm_domain_status_edges(module) -> None:
    def run_status(models: Path, profile: Path) -> dict:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ai/aq-model-eval"),
             "--status", "--json", "--profile-path", str(profile)],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "LLAMA_MODELS_DIR": str(models), "LLAMA_CPP_URL": "http://llama.invalid"},
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "profile.json"
        profile.write_text(json.dumps(cached_payload(module)))
        missing = run_status(Path(tmp) / "absent", profile)["models_dir"]
        assert missing["declared_files_present"] == []
        assert missing["untracked_or_temp_files"] == []
        assert missing["active_gguf_target"] is None

        models = Path(tmp) / "models"
        models.mkdir()
        (models / "active.gguf").symlink_to(models / "gone.gguf")
        dangling = run_status(models, Path(tmp) / "no-profile.json")
        assert dangling["active_profile"] is None
        assert dangling["models_dir"]["active_gguf_target"] == str(models / "gone.gguf")
        assert dangling["models_dir"]["declared_files_present"] == []


def main() -> int:
    module = load_module()
    asyncio.run(check_failed_measurement_does_not_refresh(module))
    asyncio.run(check_successful_measurement_is_source_labelled(module))
    asyncio.run(check_cache_freshness_and_force(module))
    check_registry_reconciliation()
    check_llm_domain_status(module)
    check_llm_domain_status_edges(module)
    print("PASS: model probe receipts, cache freshness, force preservation, registry reconciliation, and LLM domain status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
