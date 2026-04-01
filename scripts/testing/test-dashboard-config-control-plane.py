#!/usr/bin/env python3
"""Offline regression for dashboard config control-plane inventory surfaces."""

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
    with tempfile.TemporaryDirectory(prefix="dashboard-config-control-plane-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)
        config_module = importlib.import_module("api.routes.config")
        config_module = importlib.reload(config_module)

        async def fake_fetch_hybrid_health():
            return {
                "ai_harness": {
                    "enabled": True,
                    "memory_enabled": True,
                    "tree_search_enabled": True,
                    "eval_enabled": True,
                    "capability_discovery_enabled": True,
                }
            }

        config_module._fetch_hybrid_health = fake_fetch_hybrid_health

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/config")
            assert_true(response.status_code == 200, "config inventory route should succeed")
            payload = response.json()

            assert_true(payload.get("dashboard_runtime", {}).get("rate_limit") == 60, "dashboard runtime should expose legacy config values")
            assert_true(payload.get("harness_runtime", {}).get("settings", {}).get("enabled") is True, "live harness state should be exposed")
            assert_true(
                any(item.get("workflow_id") == "bounded-research-review" for item in (payload.get("workflow_blueprints") or [])),
                "workflow blueprints should include bounded-research-review policy",
            )
            assert_true(
                any(item.get("status") == "misleading" for item in (payload.get("control_plane_inventory", {}).get("known_gaps") or [])),
                "control-plane inventory should expose known dashboard gaps",
            )

            update_response = client.post(
                "/api/config",
                json={
                    "rate_limit": 90,
                    "checkpoint_interval": 150,
                    "backpressure_threshold_mb": 120,
                    "log_level": "WARNING",
                },
            )
            assert_true(update_response.status_code == 200, "dashboard runtime config update should succeed")
            updated = update_response.json()
            assert_true(updated.get("scope") == "dashboard-runtime-only", "config update should be explicitly scoped")
            assert_true(
                updated.get("dashboard_runtime", {}).get("log_level") == "WARNING",
                "dashboard runtime config update should persist in response payload",
            )
            assert_true(
                "dashboard-local runtime settings only" in str(updated.get("warning") or ""),
                "config update should warn that harness settings are not changed",
            )

            blueprint_preview = client.get("/api/config/workflow-blueprints.json")
            assert_true(blueprint_preview.status_code == 200, "workflow blueprint preview should succeed")
            preview_data = blueprint_preview.json()
            assert_true(preview_data.get("redeploy_required") is True, "workflow blueprint preview should be marked redeploy-required")
            assert_true("bounded-research-review" in str(preview_data.get("content") or ""), "workflow blueprint preview should expose file contents")

            unsupported = client.put("/api/config/unsupported.json", params={"content": "{}"})
            assert_true(unsupported.status_code == 501, "unsupported config writes should be rejected")

        print("PASS: dashboard config control-plane inventory regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
