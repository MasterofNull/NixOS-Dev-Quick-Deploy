"""
Phase 4.1 validation tests for deployment -> monitoring -> alerting integration.

These tests keep coverage focused on the new HTTP alert integration surfaces:
- dashboard health routes proxy to the live hybrid alert engine contract
- hybrid coordinator exposes HTTP alert routes needed by validation scripts
"""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

from api.routes import health as health_routes  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_dashboard_get_alerts_uses_hybrid_contract(monkeypatch):
    expected = {
        "alerts": [{"id": "a1", "severity": "warning", "status": "active"}],
        "count": 1,
        "severity_counts": {"critical": 0, "warning": 1, "info": 0, "emergency": 0},
    }

    def fake_request(path, *, method="GET", payload=None, query=None):
        assert path == "/alerts"
        assert method == "GET"
        assert payload is None
        assert query is None
        return expected

    monkeypatch.setattr(health_routes, "_hybrid_request", fake_request)

    result = await health_routes.get_alerts()
    assert result == expected


@pytest.mark.anyio
async def test_dashboard_acknowledge_alert_proxies(monkeypatch):
    expected = {"alert_id": "alert-123", "acknowledged": True}

    def fake_request(path, *, method="GET", payload=None, query=None):
        assert path == "/alerts/alert-123/acknowledge"
        assert method == "POST"
        assert payload == {}
        return expected

    monkeypatch.setattr(health_routes, "_hybrid_request", fake_request)

    result = await health_routes.acknowledge_alert("alert-123")
    assert result == expected


@pytest.mark.anyio
async def test_dashboard_resolve_alert_proxies(monkeypatch):
    expected = {"alert_id": "alert-123", "resolved": True}

    def fake_request(path, *, method="GET", payload=None, query=None):
        assert path == "/alerts/alert-123/resolve"
        assert method == "POST"
        assert payload == {}
        return expected

    monkeypatch.setattr(health_routes, "_hybrid_request", fake_request)

    result = await health_routes.resolve_alert("alert-123")
    assert result == expected


def test_hybrid_http_server_exposes_alert_http_routes():
    source = (ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py").read_text(encoding="utf-8")
    assert 'http_app.router.add_get("/alerts", handle_alerts_list)' in source
    assert 'http_app.router.add_post("/alerts/test", handle_alert_test_create)' in source
    assert 'http_app.router.add_post("/alerts/{alert_id}/acknowledge", handle_alert_acknowledge)' in source
    assert 'http_app.router.add_post("/alerts/{alert_id}/resolve", handle_alert_resolve)' in source
