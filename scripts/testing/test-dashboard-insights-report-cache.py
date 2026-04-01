#!/usr/bin/env python3
"""Regression checks for dashboard insights aq-report caching and fallback."""

from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def exercise_shared_refresh(insights_service) -> None:
    service = insights_service.AIInsightsService()
    calls = {"n": 0}

    def fake_run(*args, **kwargs):
        calls["n"] += 1
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=0,
            stdout=json.dumps({"generated_at": "2026-04-01T12:00:00Z", "tool_performance": {}}),
            stderr="",
        )

    original_run = insights_service.subprocess.run
    insights_service.subprocess.run = fake_run
    try:
        results = await asyncio.gather(service.get_full_report(), service.get_full_report(), service.get_full_report())
    finally:
        insights_service.subprocess.run = original_run

    assert_true(calls["n"] == 1, "concurrent insights requests should share one aq-report refresh")
    assert_true(all(item["generated_at"] == "2026-04-01T12:00:00Z" for item in results), "shared refresh should return identical report data")


async def exercise_stale_fallback(insights_service) -> None:
    service = insights_service.AIInsightsService()
    service._cache = {"generated_at": "2026-04-01T11:58:00Z", "tool_performance": {}, "stale": True}
    service._cache_timestamp = insights_service.datetime.now(insights_service.timezone.utc) - timedelta(seconds=120)

    def fake_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "aq-report", timeout=60)

    original_run = insights_service.subprocess.run
    insights_service.subprocess.run = fake_timeout
    try:
        result = await service.get_full_report()
    finally:
        insights_service.subprocess.run = original_run

    assert_true(result.get("stale") is True, "stale cached report should be served when refresh times out")


def main() -> int:
    insights_service = importlib.import_module("api.services.ai_insights")
    insights_service = importlib.reload(insights_service)

    asyncio.run(exercise_shared_refresh(insights_service))
    asyncio.run(exercise_stale_fallback(insights_service))
    print("PASS: dashboard insights report cache shares refreshes and serves stale fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
