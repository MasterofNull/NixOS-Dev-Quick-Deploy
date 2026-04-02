#!/usr/bin/env python3
"""Regression checks for dashboard advanced runtime summary integration."""

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
    with tempfile.TemporaryDirectory(prefix="dashboard-advanced-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "context.db")
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
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def get(self, url, headers=None, timeout=None):
                if url.endswith("/control/ai-coordinator/advanced-features/readiness"):
                    return FakeResponse(
                        {
                            "readiness": {
                                "phase_6_offloading": {
                                    "status": "implementation_exists",
                                    "quality_assessments": 14,
                                    "benchmarked_profiles": 3,
                                    "local_fallback_mode": "default",
                                },
                                "phase_7_efficiency": {
                                    "status": "implementation_exists",
                                    "ab_variants": 5,
                                    "compressions": 21,
                                    "tokens_saved": 830,
                                    "context_reuse_ready": True,
                                },
                                "phase_9_capability_gap": {
                                    "status": "implementation_exists",
                                    "remediation_artifacts_recorded": True,
                                },
                                "phase_10_learning": {
                                    "status": "implementation_exists",
                                },
                            }
                        }
                    )
                if url.endswith("/control/ai-coordinator/advanced-features/offloading/quality-profiles"):
                    return FakeResponse({"profiles": [{"agent_id": "a"}, {"agent_id": "b"}]})
                if url.endswith("/control/ai-coordinator/advanced-features/context/tier-stats"):
                    return FakeResponse({"total_selections": 17})
                if url.endswith("/control/ai-coordinator/advanced-features/capability-gap/stats"):
                    return FakeResponse({"total_gaps": 4, "failure_patterns": {"tool_missing": 2, "knowledge_missing": 1}})
                if url.endswith("/control/ai-coordinator/advanced-features/learning/stats"):
                    return FakeResponse({"total_signals": 11, "recommendation_count": 3, "high_confidence_recommendations": 1})
                raise AssertionError(f"unexpected URL: {url}")

        aistack_module.aiohttp.ClientSession = FakeClientSession

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/aistack/advanced/runtime-summary")
            assert_true(response.status_code == 200, "advanced runtime summary route should succeed")
            payload = response.json()
            summary = payload.get("summary") or {}
            assert_true((summary.get("offloading") or {}).get("quality_profiles") == 2, "summary should count quality profiles")
            assert_true((summary.get("context_efficiency") or {}).get("tier_selections") == 17, "summary should preserve context tier selections")
            assert_true((summary.get("capability_gap") or {}).get("failure_patterns") == 2, "summary should count failure patterns")
            assert_true((summary.get("learning") or {}).get("signals_recorded") == 11, "summary should preserve learning signals")

        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        assert_true("async function fetchAdvancedRuntimeSummary()" in html, "dashboard should fetch advanced runtime summary")
        assert_true("/api/aistack/advanced/runtime-summary" in html, "dashboard should call advanced runtime summary route")
        assert_true('id="hybridQualityProfiles"' in html, "dashboard should expose advanced offloading profiles metric")
        assert_true('id="hybridContextTiers"' in html, "dashboard should expose advanced context tier metric")
        assert_true('id="hybridRemediationArtifacts"' in html, "dashboard should expose remediation artifact metric")
        assert_true('id="hybridLearningSignals"' in html, "dashboard should expose advanced learning signal metric")
        assert_true('id="hybridAdvancedSummary"' in html, "dashboard should expose advanced runtime summary text")
        assert_true("document.getElementById('hybridQualityProfiles').textContent" in html, "dashboard should populate advanced offloading profiles")
        assert_true("document.getElementById('hybridContextTiers').textContent" in html, "dashboard should populate advanced context tiers")
        assert_true("document.getElementById('hybridRemediationArtifacts').textContent" in html, "dashboard should populate remediation artifacts")
        assert_true("document.getElementById('hybridLearningSignals').textContent" in html, "dashboard should populate advanced learning signals")

    print("PASS: dashboard advanced runtime summary integration present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
