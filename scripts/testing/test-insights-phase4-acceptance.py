#!/usr/bin/env python3
"""Offline regression for the Phase 4 consolidated acceptance insights endpoint."""

from __future__ import annotations

import importlib
import json
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
    with tempfile.TemporaryDirectory(prefix="insights-phase4-acceptance-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["PHASE4_ACCEPTANCE_REPORT_PATH"] = str(tmp_path / "phase-4-acceptance-report.json")
        os.environ["DASHBOARD_MODE"] = "test"

        report = {
            "generated_at": "2026-03-20T12:00:00Z",
            "phase": "4",
            "status": "passed",
            "flows": {
                "deployment_monitoring_alerting": {
                    "label": "Phase 4.1 deployment -> monitoring -> alerting",
                    "status": "passed",
                    "script": "scripts/testing/smoke-deployment-monitoring-alerting.sh",
                    "ended_at": "2026-03-20T12:00:01Z",
                },
                "query_agent_storage_learning": {
                    "label": "Phase 4.2 query -> agent -> storage -> learning",
                    "status": "passed",
                    "script": "scripts/testing/smoke-query-agent-storage-learning.sh",
                    "ended_at": "2026-03-20T12:00:02Z",
                },
                "security_audit_compliance": {
                    "label": "Phase 4.3 security -> audit -> compliance",
                    "status": "passed",
                    "script": "scripts/testing/smoke-security-audit-compliance.sh",
                    "ended_at": "2026-03-20T12:00:03Z",
                },
            },
        }
        Path(os.environ["PHASE4_ACCEPTANCE_REPORT_PATH"]).write_text(
            json.dumps(report),
            encoding="utf-8",
        )

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/insights/workflows/phase-4-acceptance")
            assert_true(response.status_code == 200, "phase 4 acceptance route should succeed")
            data = response.json()
            assert_true(data.get("available") is True, "phase 4 acceptance report should be available")
            assert_true(data.get("status") == "passed", "phase 4 acceptance should report pass")
            assert_true((data.get("summary") or {}).get("total_flows") == 3, "phase 4 acceptance should summarize all flows")
            assert_true((data.get("summary") or {}).get("failed_flows") == 0, "phase 4 acceptance should have zero failed flows")
            assert_true(
                (data.get("flows") or {}).get("deployment_monitoring_alerting", {}).get("status") == "passed",
                "phase 4.1 status should be preserved",
            )
            assert_true(
                (data.get("flows") or {}).get("security_audit_compliance", {}).get("script") == "scripts/testing/smoke-security-audit-compliance.sh",
                "phase 4.3 script path should be preserved",
            )

        print("PASS: phase 4 acceptance insights regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
