#!/usr/bin/env python3
"""Regression checks for auto-deployer rollback error-rate verification threshold."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTO_DEPLOYER = ROOT / "ai-stack" / "deployment" / "auto_deployer.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _load_module():
    spec = importlib.util.spec_from_file_location("test_auto_deployer_module", AUTO_DEPLOYER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()
    original_run = module.subprocess.run
    try:
        def fake_run(command, capture_output=True, text=True, timeout=None):
            if command[:2] == ["scripts/ai/aq-qa", "0"]:
                return FakeCompletedProcess(stdout=json.dumps({"passed": 19, "failed": 1}))
            raise AssertionError(f"unexpected command: {command}")

        module.subprocess.run = fake_run
        deployer = module.AutoDeployer(
            config=module.DeploymentConfig(
                verification_timeout_seconds=30,
                rollback_on_error_rate=0.04,
            ),
            dry_run=False,
        )
        result = module.DeploymentResult(
            deployment_id="threshold-test",
            status=module.DeploymentStatus.VERIFYING,
            started_at=module.datetime.now(),
        )
        verified = asyncio.run(deployer._run_verification(result))
        assert_true(verified is False, "verification should fail when failure rate exceeds configured threshold")
        assert_true(
            result.metrics.get("post_deploy_failure_rate") == 0.05,
            "verification should record post-deploy failure rate metric",
        )
        assert_true(
            any("exceeded threshold 0.0400" in entry for entry in result.logs),
            "verification logs should record threshold breach",
        )
        print("PASS: auto-deployer error-rate threshold regression")
        return 0
    finally:
        module.subprocess.run = original_run


if __name__ == "__main__":
    raise SystemExit(main())
