#!/usr/bin/env python3
"""Regression checks for dashboard orchestration event replay proxy."""

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
    with tempfile.TemporaryDirectory(prefix="dashboard-orchestration-events-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack_module = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack_module = importlib.reload(aistack_module)

        class FakeResponse:
            def __init__(self, payload, status=200):
                self.status = status
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

            async def close(self):
                return None

            @property
            def closed(self):
                return False

            def get(self, url, headers=None, timeout=None):
                self.urls.append(url)
                if url.endswith("/workflow/sessions"):
                    return FakeResponse(
                        {
                            "sessions": [
                                {"session_id": "wf-123", "updated_at": 1775070000},
                                {"session_id": "wf-456", "updated_at": 1775070010},
                            ],
                            "count": 2,
                        }
                    )
                if "/workflow/run/wf-123/replay" in url:
                    return FakeResponse(
                        {
                            "events": [
                                {
                                    "ts": 1775070001,
                                    "event_type": "tool_call",
                                    "phase_id": "phase-0",
                                    "risk_class": "safe",
                                    "approved": True,
                                    "token_delta": 12,
                                    "tool_call_delta": 1,
                                    "tool_name": "rg",
                                    "detail": "searched files",
                                    "profile": "local-tool-calling",
                                    "agent": "codex",
                                    "role": "implementer",
                                }
                            ]
                        }
                    )
                if "/workflow/run/wf-456/replay" in url:
                    return FakeResponse(
                        {
                            "events": [
                                {
                                    "ts": 1775070011,
                                    "event_type": "review",
                                    "phase_id": "phase-1",
                                    "token_delta": 4,
                                    "detail": "review passed",
                                    "agent": "reviewer",
                                }
                            ]
                        }
                    )
                return FakeResponse({"events": []})

        aistack_module.aiohttp.ClientSession = FakeClientSession
        aistack_module._http_session = None

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/aistack/orchestration/events", params={"session_id": "wf-123"})
            assert_true(response.status_code == 200, "orchestration events route should succeed")
            payload = response.json()
            assert_true(payload.get("available") is True, "orchestration events should be available")
            assert_true(payload.get("source") == "workflow-trajectory", "events should identify source")
            assert_true(payload.get("count") == 1, "session-specific replay should return one event")
            event = (payload.get("events") or [{}])[0]
            assert_true(event.get("schema_version") == "maeah.agent-run-event.v1", "event should expose schema version")
            assert_true(event.get("run_id") == "wf-123", "event should map session id to run id")
            assert_true(event.get("event_type") == "tool_call", "event type should be preserved")
            assert_true(event.get("tool_name") == "rg", "tool name should be preserved")
            assert_true((event.get("tokens") or {}).get("total") == 12, "token delta should map to token total")
            assert_true((event.get("payload") or {}).get("risk_class") == "safe", "risk class should be in payload")

            aggregate = client.get("/api/aistack/orchestration/events")
            assert_true(aggregate.status_code == 200, "aggregate orchestration events should succeed")
            aggregate_payload = aggregate.json()
            assert_true(aggregate_payload.get("count") == 2, "aggregate events should merge recent sessions")
            session_ids = {item.get("session_id") for item in aggregate_payload.get("events") or []}
            assert_true({"wf-123", "wf-456"} <= session_ids, "aggregate events should include both sessions")

    print("PASS: dashboard orchestration events proxy normalizes replayable agent events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
