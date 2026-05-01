#!/usr/bin/env python3
"""Offline regression for switchboard local runtime surfacing in /api/ai/metrics."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fake_fetch_with_fallback(url: str, fallback=None, headers=None):
    del headers
    if "aidb" in url and url.endswith("/health"):
        return {"status": "online"}
    if "8003" in url and url.endswith("/health"):
        return {"status": "healthy"}
    if "8080" in url and url.endswith("/health"):
        return {"status": "ok"}
    if "11435" in url and url.endswith("/health"):
        return {"status": "ok", "model": "nomic-embed-text", "dimensions": 768}
    if "8085" in url and url.endswith("/health"):
        return {
            "status": "ok",
            "routing_mode": "hybrid",
            "default_provider": "local",
            "remote_configured": False,
            "local_runtime": {
                "slot_capacity": 1,
                "slot_available": 0,
                "slot_busy": True,
                "source": "switchboard_semaphore+llama_metrics",
                "llama_metrics_available": True,
                "active_request": {
                    "profile": "continue-local",
                    "duration_s": 91.2,
                    "long_running": True,
                },
            },
        }
    if "7534" in url and url.endswith("/health"):
        return {"status": "ok"}
    if "8080" in url and url.endswith("/v1/models"):
        return {"data": [{"id": "Qwen3-30B-A3B-Q4_K_M.gguf"}]}
    if "11435" in url and url.endswith("/v1/models"):
        return {"data": [{"id": "nomic-embed-text"}]}
    if url.endswith("/collections"):
        return {"result": {"collections": []}}
    return fallback


async def _fake_fetch_text_with_fallback(url: str, fallback=None):
    if url.endswith("/healthz"):
        return "ok"
    return fallback


async def _empty_dict(*args, **kwargs):
    del args, kwargs
    return {}


async def _zero_points(*args, **kwargs):
    del args, kwargs
    return {}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-ai-metrics-switchboard-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack = importlib.reload(aistack)

        aistack._AI_METRICS_CACHE["ts"] = 0.0
        aistack._AI_METRICS_CACHE["payload"] = None
        aistack.fetch_with_fallback = _fake_fetch_with_fallback
        aistack.fetch_text_with_fallback = _fake_fetch_text_with_fallback
        aistack._fetch_aidb_prometheus_summary = _empty_dict
        aistack._redis_ping_probe = _empty_dict
        aistack._postgres_select1_probe = _empty_dict
        aistack._redis_runtime_probe = _empty_dict
        aistack._postgres_runtime_probe = _empty_dict
        aistack._aider_wrapper_task_summary = _empty_dict
        aistack._fetch_prsi_stats = _empty_dict
        aistack._fetch_qdrant_collection_points = _zero_points
        aistack._fetch_discovery_trends = _empty_dict
        aistack.get_harness_stats = _empty_dict
        aistack.get_harness_scorecard = _empty_dict
        aistack.get_harness_overview = _empty_dict
        aistack._build_feedback_pipeline_stats = lambda: {}
        aistack._list_model_inventory = lambda: {"available": False, "llama_cpp": [], "embeddings": [], "error": None}
        aistack._systemd_memory_current_bytes = lambda unit: None

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/ai/metrics")
            assert_true(response.status_code == 200, "ai metrics route should succeed")
            payload = response.json()
            switchboard = ((payload.get("services") or {}).get("switchboard") or {})
            local_runtime = switchboard.get("local_runtime") or {}
            assert_true(
                switchboard.get("local_lane_status") == "busy-long-running",
                "long-running local switchboard lane should surface as busy-long-running",
            )
            assert_true(local_runtime.get("slot_busy") is True, "switchboard local runtime should preserve busy semaphore state")
            assert_true(
                local_runtime.get("source") == "switchboard_semaphore+llama_metrics",
                "switchboard local runtime should expose the combined occupancy source",
            )

        print("PASS: dashboard ai metrics exposes switchboard local runtime status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
