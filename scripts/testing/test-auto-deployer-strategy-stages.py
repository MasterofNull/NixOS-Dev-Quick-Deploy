#!/usr/bin/env python3
"""Regression checks for staged auto-deployer rollout strategies."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTO_DEPLOYER = ROOT / "ai-stack" / "deployment" / "auto_deployer.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_module():
    spec = importlib.util.spec_from_file_location("test_auto_deployer_stages_module", AUTO_DEPLOYER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


async def _exercise_strategy(module, strategy, canary_percentage=10):
    deployer = module.AutoDeployer(
        config=module.DeploymentConfig(
            strategy=strategy,
            canary_percentage=canary_percentage,
        ),
        dry_run=True,
    )
    result = await deployer.deploy(deployment_id=f"stage-{strategy.value}")
    return result


def main() -> int:
    module = _load_module()

    blue_green = asyncio.run(_exercise_strategy(module, module.DeploymentStrategy.BLUE_GREEN))
    blue_green_logs = "\n".join(blue_green.logs)
    assert_true("[stage] prepare_green (0% rollout)" in blue_green_logs, "blue-green should prepare green environment")
    assert_true("[stage] switch_traffic (100% rollout)" in blue_green_logs, "blue-green should switch traffic explicitly")

    canary = asyncio.run(_exercise_strategy(module, module.DeploymentStrategy.CANARY, canary_percentage=15))
    canary_logs = "\n".join(canary.logs)
    assert_true("[stage] rollout_15_percent (15% rollout)" in canary_logs, "canary should record initial canary percentage")
    assert_true("[stage] full_verification (100% rollout)" in canary_logs, "canary should record final verification stage")

    rolling = asyncio.run(_exercise_strategy(module, module.DeploymentStrategy.ROLLING))
    rolling_logs = "\n".join(rolling.logs)
    assert_true("[stage] batch_update_1 (33% rollout)" in rolling_logs, "rolling should record first batch update")
    assert_true("[stage] finalize_rollout (100% rollout)" in rolling_logs, "rolling should record rollout finalization")

    assert_true(blue_green.metrics.get("strategy_stage_count", 0) >= 4, "blue-green should track stage count")
    assert_true(canary.metrics.get("rollout_percentage") == 100.0, "canary should end at full rollout")
    assert_true(rolling.metrics.get("strategy_stage_count", 0) >= 5, "rolling should track multiple stages")

    print("PASS: auto-deployer staged strategies regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
