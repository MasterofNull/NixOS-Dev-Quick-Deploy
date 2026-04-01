#!/usr/bin/env python3
"""Offline regression checks for runtime deployment execution and approval flows."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeDeploymentStrategy(Enum):
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    IMMEDIATE = "immediate"


class FakeDeploymentStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FakeDeploymentConfig:
    strategy: FakeDeploymentStrategy = FakeDeploymentStrategy.BLUE_GREEN
    require_approval: bool = False
    approval_timeout_seconds: int = 300
    validation_timeout_seconds: int = 60
    verification_timeout_seconds: int = 120
    auto_rollback: bool = True
    canary_percentage: int = 10


@dataclass
class FakeDeploymentResult:
    deployment_id: str
    status: FakeDeploymentStatus
    started_at: datetime
    completed_at: datetime | None = None
    strategy: FakeDeploymentStrategy = FakeDeploymentStrategy.BLUE_GREEN
    validation_passed: bool = True
    deployment_succeeded: bool = True
    verification_passed: bool = True
    rollback_performed: bool = False
    error_message: str | None = None
    metrics: dict = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


class FakeAutoDeployer:
    def __init__(self, config: FakeDeploymentConfig | None = None, dry_run: bool = False):
        self.config = config or FakeDeploymentConfig()
        self.dry_run = dry_run

    async def deploy(self, deployment_id: str | None = None, approval_callback=None):
        deployment_id = deployment_id or "fake-runtime-deploy"
        now = datetime.now(UTC)
        return FakeDeploymentResult(
            deployment_id=deployment_id,
            status=FakeDeploymentStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            strategy=self.config.strategy,
            metrics={"dry_run": 1.0 if self.dry_run else 0.0},
            logs=["fake validation", "fake deployment", "fake verification"],
        )


class FakeAutoDeployerModule:
    DeploymentStrategy = FakeDeploymentStrategy
    DeploymentStatus = FakeDeploymentStatus
    DeploymentConfig = FakeDeploymentConfig
    AutoDeployer = FakeAutoDeployer


def _wait_for_status(client: TestClient, deployment_id: str, expected: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/deployments/{deployment_id}")
        if response.status_code == 200:
            payload = response.json()
            if payload.get("status") == expected:
                return payload
        time.sleep(0.05)
    raise AssertionError(f"deployment {deployment_id} did not reach status {expected}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-deployment-execution-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_MODE"] = "test"

        deployments_module = importlib.import_module("api.routes.deployments")
        deployments_module = importlib.reload(deployments_module)
        deployments_module._AUTO_DEPLOYER_MODULE = FakeAutoDeployerModule
        deployments_module.runtime_deployment_tasks.clear()
        deployments_module.pending_deployment_approvals.clear()
        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            dry_run_id = "runtime-exec-dry-run"
            start = client.post(
                "/api/deployments/execute",
                json={
                    "deployment_id": dry_run_id,
                    "strategy": "blue_green",
                    "dry_run": True,
                    "confirm": True,
                    "user": "codex-test",
                },
            )
            assert_true(start.status_code == 200, "dry-run runtime deployment should start")
            start_data = start.json()
            assert_true(start_data.get("status") == "started", "dry-run runtime deployment should report started")
            assert_true(start_data.get("request", {}).get("dry_run") is True, "dry-run request metadata should be echoed")

            dry_run_detail = _wait_for_status(client, dry_run_id, "success")
            assert_true(dry_run_detail.get("status") == "success", "dry-run runtime deployment should complete successfully")
            assert_true(
                str(dry_run_detail.get("command") or "").startswith("auto-deployer --strategy blue_green"),
                "dry-run runtime deployment should expose the auto-deployer command",
            )
            assert_true(
                dry_run_detail.get("rollback", {}).get("available") is True,
                "dry-run runtime deployment detail should preserve rollback affordance",
            )

            pending_id = "runtime-exec-pending"
            pending = client.post(
                "/api/deployments/execute",
                json={
                    "deployment_id": pending_id,
                    "strategy": "canary",
                    "dry_run": True,
                    "require_approval": True,
                    "confirm": True,
                    "canary_percentage": 15,
                    "user": "codex-test",
                },
            )
            assert_true(pending.status_code == 200, "approval-gated runtime deployment should be accepted")
            pending_data = pending.json()
            assert_true(pending_data.get("status") == "pending_approval", "approval-gated runtime deployment should remain pending approval")

            approvals = client.get("/api/deployments/approvals/pending")
            assert_true(approvals.status_code == 200, "pending approvals route should succeed")
            approvals_data = approvals.json()
            assert_true(any(item.get("deployment_id") == pending_id for item in (approvals_data.get("deployments") or [])), "pending deployment should be listed for approval")

            approved = client.post(
                f"/api/deployments/{pending_id}/approval",
                json={"decision": "approve", "reviewer": "operator-test", "reason": "safe dry-run approved"},
            )
            assert_true(approved.status_code == 200, "approval decision should succeed")
            assert_true(approved.json().get("status") == "approved", "approval endpoint should report approved")

            approved_detail = _wait_for_status(client, pending_id, "success")
            assert_true(approved_detail.get("status") == "success", "approved runtime deployment should complete successfully")
            assert_true(
                str(approved_detail.get("command") or "").startswith("auto-deployer --strategy canary"),
                "approved deployment should preserve canary execution metadata",
            )

            rejected_id = "runtime-exec-rejected"
            rejected_pending = client.post(
                "/api/deployments/execute",
                json={
                    "deployment_id": rejected_id,
                    "strategy": "rolling",
                    "dry_run": True,
                    "require_approval": True,
                    "confirm": True,
                    "user": "codex-test",
                },
            )
            assert_true(rejected_pending.status_code == 200, "rejected test deployment should be accepted")

            rejected = client.post(
                f"/api/deployments/{rejected_id}/approval",
                json={"decision": "reject", "reviewer": "operator-test", "reason": "reject for regression test"},
            )
            assert_true(rejected.status_code == 200, "rejection decision should succeed")
            assert_true(rejected.json().get("status") == "rejected", "rejection endpoint should report rejected")

            rejected_detail = client.get(f"/api/deployments/{rejected_id}")
            assert_true(rejected_detail.status_code == 200, "rejected deployment detail should exist")
            rejected_payload = rejected_detail.json()
            assert_true(rejected_payload.get("status") == "rejected", "rejected deployment should stay rejected")
            assert_true(
                str(rejected_payload.get("command") or "").startswith("auto-deployer --strategy rolling"),
                "rejected deployment should preserve rolling execution metadata",
            )

        print("PASS: dashboard deployment execution regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
