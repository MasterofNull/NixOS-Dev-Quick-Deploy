#!/usr/bin/env python3
"""Offline regression for the security compliance insights endpoint."""

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
    with tempfile.TemporaryDirectory(prefix="insights-security-compliance-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_RATE_LIMIT_ENABLED"] = "true"
        os.environ["DASHBOARD_RATE_LIMIT_DEFAULT_RPM"] = "20"
        os.environ["DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM"] = "5"
        os.environ["DASHBOARD_RATE_LIMIT_SEARCH_RPM"] = "10"
        os.environ["DASHBOARD_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            client.post(
                "/api/deployments/start",
                params={"deployment_id": "compliance-test", "command": "deploy test", "user": "codex"},
            )
            response = client.get("/api/insights/security/compliance")
            assert_true(response.status_code == 200, "security compliance route should succeed")
            data = response.json()
            assert_true(data.get("controls", {}).get("content_security_policy") is True, "CSP control should be reported")
            assert_true(data.get("controls", {}).get("rate_limiting") is True, "rate limiting control should be reported")
            assert_true(data.get("controls", {}).get("operator_audit_log") is True, "audit log control should be reported")
            assert_true(
                data.get("controls", {}).get("tamper_evident_audit_sealing") is True,
                "tamper-evident audit sealing should be reported",
            )
            assert_true(
                data.get("controls", {}).get("dashboard_security_scan_automation") is True,
                "dashboard security scan automation should be reported",
            )
            assert_true(
                data.get("controls", {}).get("secrets_rotation_planning") is True,
                "secrets rotation planning should be reported",
            )
            assert_true((data.get("audit") or {}).get("total_events", 0) >= 1, "audit summary should include events")
            assert_true((data.get("audit_integrity") or {}).get("valid") is True, "audit integrity should validate")
            assert_true(
                "external security scan automation still pending" in (data.get("gaps") or []),
                "remaining external scan gap should still be reported",
            )
            assert_true(
                "live secrets rotation execution still requires explicit operator approval" in (data.get("gaps") or []),
                "rotation execution boundary should still be reported",
            )

        print("PASS: security compliance insights regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
