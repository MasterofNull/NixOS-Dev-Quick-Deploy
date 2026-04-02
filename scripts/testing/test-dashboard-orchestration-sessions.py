#!/usr/bin/env python3
"""Regression checks for dashboard orchestration session listing proxy and UI."""

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
    with tempfile.TemporaryDirectory(prefix="dashboard-orchestration-sessions-") as tmp_dir:
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
                return FakeResponse(
                    {
                        "sessions": [
                            {
                                "session_id": "wf-123",
                                "status": "in_progress",
                                "objective": "Investigate orchestration visibility",
                                "current_phase": "discover",
                                "reasoning_pattern": {
                                    "selected_pattern": "react",
                                    "boost_multiplier": 1.15,
                                },
                                "orchestration_runtime": {
                                    "framework_status": "integrated",
                                    "workspace": {"mode": "temp_dir"},
                                },
                                "updated_at": 1775070000,
                            }
                        ],
                        "count": 1,
                    }
                )

        aistack_module.aiohttp.ClientSession = FakeClientSession

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/aistack/orchestration/sessions")
            assert_true(response.status_code == 200, "orchestration sessions route should succeed")
            payload = response.json()
            assert_true(payload.get("count") == 1, "orchestration sessions route should proxy count")
            first = (payload.get("sessions") or [{}])[0]
            assert_true(first.get("session_id") == "wf-123", "orchestration sessions should preserve session ids")
            assert_true(first.get("current_phase") == "discover", "orchestration sessions should preserve phase metadata")
            assert_true(
                (first.get("reasoning_pattern") or {}).get("selected_pattern") == "react",
                "orchestration sessions should preserve reasoning pattern metadata",
            )
            assert_true(
                (first.get("orchestration_runtime") or {}).get("framework_status") == "integrated",
                "orchestration sessions should preserve orchestration runtime integration metadata",
            )

        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        assert_true('id="orchestrationSessionList"' in html, "dashboard should render orchestration session list container")
        assert_true("function loadOrchestrationSessions()" in html, "dashboard should define orchestration session loader")
        assert_true("function selectOrchestrationSession(sessionId)" in html, "dashboard should support session selection shortcuts")
        assert_true("Pattern: ${escapeHtml(String(session.reasoning_pattern?.selected_pattern || '--'))}" in html, "dashboard should render reasoning pattern in orchestration session cards")
        assert_true('id="orchFormationMode"' in html, "dashboard should expose orchestration formation mode metric")
        assert_true('id="orchRequiredSlots"' in html, "dashboard should expose orchestration required slot metric")
        assert_true('id="orchOptionalCapacity"' in html, "dashboard should expose orchestration optional capacity metric")
        assert_true('id="orchDeferredSlots"' in html, "dashboard should expose orchestration deferred slot metric")
        assert_true('id="orchRuntimeStatus"' in html, "dashboard should expose orchestration runtime status metric")
        assert_true('id="orchCurrentPhase"' in html, "dashboard should expose orchestration current phase metric")
        assert_true('id="orchSafetyMode"' in html, "dashboard should expose orchestration safety mode metric")
        assert_true('id="orchTokenBudget"' in html, "dashboard should expose orchestration token budget metric")
        assert_true('id="orchToolBudget"' in html, "dashboard should expose orchestration tool budget metric")
        assert_true('id="orchUsageSummary"' in html, "dashboard should expose orchestration usage summary metric")
        assert_true('id="orchReasoningPattern"' in html, "dashboard should expose orchestration reasoning pattern metric")
        assert_true('id="orchPatternBoost"' in html, "dashboard should expose orchestration pattern boost metric")
        assert_true('id="orchObjectiveSummary"' in html, "dashboard should expose orchestration objective summary")
        assert_true('id="orchPatternGuidanceList"' in html, "dashboard should render orchestration pattern guidance list")
        assert_true('id="deferredMembersList"' in html, "dashboard should render deferred collaborator container")
        assert_true("document.getElementById('orchDeferredSlots').textContent" in html, "dashboard should populate deferred slot metric")
        assert_true("document.getElementById('orchRuntimeStatus').textContent" in html, "dashboard should populate runtime status metric")
        assert_true("document.getElementById('orchReasoningPattern').textContent" in html, "dashboard should populate reasoning pattern metric")
        assert_true("document.getElementById('orchPatternBoost').textContent" in html, "dashboard should populate pattern boost metric")
        assert_true("document.getElementById('orchObjectiveSummary').textContent" in html, "dashboard should populate objective summary")
        assert_true("phase guidance" in html, "dashboard should label orchestration phase guidance output")
        assert_true("document.getElementById('deferredMembersList')" in html, "dashboard should populate deferred collaborator list")

    print("PASS: dashboard orchestration sessions proxy and UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
