#!/usr/bin/env python3
"""Regression checks for dashboard Phase 5-7 integration surfaces."""

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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-phase5-7-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack_module = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack_module = importlib.reload(aistack_module)

        class FakeResponse:
            def __init__(self, payload):
                self.status = 200
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def raise_for_status(self):
                return None

            async def json(self):
                return self._payload

        class FakeClientSession:
            def __init__(self, *args, **kwargs):
                self.urls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def get(self, url, headers=None, timeout=None):
                self.urls.append(url)
                if url.endswith("/control/ai-coordinator/model-optimization/readiness"):
                    return FakeResponse(
                        {
                            "readiness": {
                                "data_capture": {"status": "operational", "captured_count": 42},
                                "finetuning_pipeline": {"status": "infrastructure_ready", "pending_jobs": 2},
                                "distillation": {"status": "implementation_exists"},
                            }
                        }
                    )
                return FakeResponse({})

        aistack_module.aiohttp.ClientSession = FakeClientSession

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/aistack/model-optimization/readiness")
            assert_true(response.status_code == 200, "model optimization readiness route should succeed")
            payload = response.json()
            readiness = payload.get("readiness") or {}
            assert_true((readiness.get("data_capture") or {}).get("captured_count") == 42, "readiness route should preserve capture count")
            assert_true((readiness.get("finetuning_pipeline") or {}).get("pending_jobs") == 2, "readiness route should preserve pending jobs")

        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        assert_true("async function fetchAISpecificMetrics()" in html, "dashboard should fetch AI-specific metrics")
        assert_true("async function fetchModelOptimizationReadiness()" in html, "dashboard should fetch model optimization readiness")
        assert_true("/api/insights/metrics/ai-specific" in html, "dashboard should use AI-specific insights metrics endpoint")
        assert_true("/api/aistack/model-optimization/readiness" in html, "dashboard should use model optimization readiness endpoint")
        assert_true('id="hybridPoolAvailability"' in html, "dashboard should expose agent pool availability metric")
        assert_true('id="hybridFreeAgents"' in html, "dashboard should expose free-agent capacity metric")
        assert_true('id="hybridDelegatedQuality"' in html, "dashboard should expose delegated quality metric")
        assert_true('id="hybridModelOptimization"' in html, "dashboard should expose model optimization metric")
        assert_true('id="hybridPromptSavings"' in html, "dashboard should expose prompt savings metric")
        assert_true('id="hybridPromptEnvelope"' in html, "dashboard should expose prompt envelope metric")
        assert_true('id="hybridPoolSummary"' in html, "dashboard should render Phase 6 offloading summary")
        assert_true('id="hybridOptimizationSummary"' in html, "dashboard should render Phase 5 optimization summary")
        assert_true('id="hybridEfficiencySummary"' in html, "dashboard should render Phase 7 efficiency summary")
        assert_true("document.getElementById('hybridPoolAvailability').textContent" in html, "dashboard should populate agent pool availability")
        assert_true("document.getElementById('hybridDelegatedQuality').textContent" in html, "dashboard should populate delegated quality")
        assert_true("document.getElementById('hybridModelOptimization').textContent" in html, "dashboard should populate model optimization status")
        assert_true("document.getElementById('hybridPromptEnvelope').textContent" in html, "dashboard should populate prompt envelope status")
        assert_true("Phase 6 Offloading" in html, "dashboard should label Phase 6 runtime summary")
        assert_true("Phase 5 Optimization" in html, "dashboard should label Phase 5 runtime summary")
        assert_true("Phase 7 Efficiency" in html, "dashboard should label Phase 7 runtime summary")

    print("PASS: dashboard Phase 5-7 integration surfaces present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
