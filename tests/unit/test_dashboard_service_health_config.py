"""Dashboard service-health wiring follows environment-backed endpoint config."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard" / "backend"))


def test_otel_collector_health_endpoint_uses_env(monkeypatch):
    monkeypatch.setenv("SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("OTEL_COLLECTOR_HEALTH_PORT", "18133")

    service_endpoints = importlib.import_module("api.config.service_endpoints")
    service_endpoints = importlib.reload(service_endpoints)

    ai_service_health = importlib.import_module("api.services.ai_service_health")
    ai_service_health = importlib.reload(ai_service_health)

    assert service_endpoints.OTEL_COLLECTOR_HEALTH_PORT == 18133
    assert service_endpoints.OTEL_COLLECTOR_HEALTH_URL == "http://127.0.0.1:18133"
    assert ai_service_health.AI_SERVICES["ai-otel-collector"]["health_url"] == "http://127.0.0.1:18133/"
