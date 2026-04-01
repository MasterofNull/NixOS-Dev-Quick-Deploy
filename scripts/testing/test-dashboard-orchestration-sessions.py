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

        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        assert_true('id="orchestrationSessionList"' in html, "dashboard should render orchestration session list container")
        assert_true("function loadOrchestrationSessions()" in html, "dashboard should define orchestration session loader")
        assert_true("function selectOrchestrationSession(sessionId)" in html, "dashboard should support session selection shortcuts")

    print("PASS: dashboard orchestration sessions proxy and UI contract present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
