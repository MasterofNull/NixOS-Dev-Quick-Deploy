"""
Phase 4.3 validation tests for security -> audit -> compliance integration.

These checks pin the dashboard contract used by the live smoke validation:
- the dashboard serves a stable `/index.html` entrypoint
- security and compliance reads are captured by the operator audit log
- the new smoke script exercises the expected endpoints
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

SMOKE_SCRIPT = ROOT / "scripts" / "testing" / "smoke-security-audit-compliance.sh"


def test_dashboard_serves_index_html_entrypoint():
    with tempfile.TemporaryDirectory(prefix="phase4-3-index-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            root_response = client.get("/")
            index_response = client.get("/index.html")
            assert root_response.status_code == 200
            assert index_response.status_code == 200
            assert root_response.headers.get("content-type") == index_response.headers.get("content-type")


def test_security_and_compliance_reads_are_audited():
    with tempfile.TemporaryDirectory(prefix="phase4-3-audit-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_RATE_LIMIT_ENABLED"] = "true"
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["AI_SECURITY_AUDIT_DIR"] = str(tmp_path / "security")
        os.environ["DASHBOARD_MODE"] = "test"

        audit_dir = tmp_path / "security"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "latest-security-audit.json").write_text(
            '{"status":"ok","generated_at":"2026-03-20T00:00:00Z","summary":{}}',
            encoding="utf-8",
        )
        (audit_dir / "latest-dashboard-security-scan.json").write_text(
            '{"status":"ok","summary":{"audit_integrity_valid":true}}',
            encoding="utf-8",
        )
        (audit_dir / "latest-secrets-rotation-plan.json").write_text(
            '{"rotation_ready":true,"summary":{"total_managed_secrets":1}}',
            encoding="utf-8",
        )

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            security = client.get("/api/security/audit")
            compliance = client.get("/api/insights/security/compliance")
            events = client.get("/api/audit/operator/events", params={"limit": 20})
            integrity = client.get("/api/audit/operator/integrity", params={"limit": 20})

            assert security.status_code == 200
            assert compliance.status_code == 200
            assert events.status_code == 200
            assert integrity.status_code == 200

            event_paths = {event.get("path") for event in events.json().get("events", [])}
            assert "/api/security/audit" in event_paths
            assert "/api/insights/security/compliance" in event_paths
            assert integrity.json().get("valid") is True


def test_phase_4_3_smoke_script_checks_expected_endpoints():
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "/index.html" in script
    assert "/api/security/audit" in script
    assert "/api/insights/security/compliance" in script
    assert "/api/audit/operator/summary" in script
    assert "/api/audit/operator/events" in script
    assert "/api/audit/operator/integrity" in script
