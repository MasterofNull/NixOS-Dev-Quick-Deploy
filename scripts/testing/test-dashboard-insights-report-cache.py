#!/usr/bin/env python3
"""Regression checks for dashboard insights aq-report caching and fallback."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
import tempfile
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


async def exercise_persisted_seed_and_fallback(insights_service) -> None:
    with tempfile.TemporaryDirectory(prefix="dashboard-insights-persisted-") as tmp_dir:
        persisted_path = Path(tmp_dir) / "latest-aq-report.json"
        persisted_path.write_text(
            json.dumps({"generated_at": "2026-04-01T11:55:00Z", "tool_performance": {}, "persisted": True}),
            encoding="utf-8",
        )
        os.environ["DASHBOARD_AI_INSIGHTS_REPORT_PATH"] = str(persisted_path)
        insights_service = importlib.reload(insights_service)
        service = insights_service.AIInsightsService()

        assert_true(service._cache is not None, "persisted report should seed the in-memory cache on startup")
        assert_true(service._cache.get("persisted") is True, "seeded cache should come from persisted snapshot")

        service._cache = None
        service._cache_timestamp = None

        def fake_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0] if args else "aq-report", timeout=60)

        original_run = insights_service.subprocess.run
        insights_service.subprocess.run = fake_timeout
        try:
            result = await service.get_full_report()
        finally:
            insights_service.subprocess.run = original_run
            os.environ.pop("DASHBOARD_AI_INSIGHTS_REPORT_PATH", None)

        assert_true(result.get("persisted") is True, "persisted snapshot should be served when no in-memory cache exists")


async def exercise_atomic_persist(insights_service) -> None:
    with tempfile.TemporaryDirectory(prefix="dashboard-insights-atomic-") as tmp_dir:
        persisted_path = Path(tmp_dir) / "latest-aq-report.json"
        os.environ["DASHBOARD_AI_INSIGHTS_REPORT_PATH"] = str(persisted_path)
        insights_service = importlib.reload(insights_service)
        service = insights_service.AIInsightsService()
        report = {"generated_at": "2026-04-01T12:05:00Z", "tool_performance": {}, "persisted": "atomic"}
        service._persist_report(report)
        reloaded = json.loads(persisted_path.read_text(encoding="utf-8"))
        assert_true(reloaded.get("persisted") == "atomic", "persisted report should be atomically replaceable and readable")
        assert_true(not persisted_path.with_name("latest-aq-report.json.tmp").exists(), "temporary file should be cleaned up after atomic replace")
        os.environ.pop("DASHBOARD_AI_INSIGHTS_REPORT_PATH", None)


def main() -> int:
    insights_service = importlib.import_module("api.services.ai_insights")
    insights_service = importlib.reload(insights_service)

    asyncio.run(exercise_shared_refresh(insights_service))
    asyncio.run(exercise_stale_fallback(insights_service))
    asyncio.run(exercise_persisted_seed_and_fallback(insights_service))
    asyncio.run(exercise_atomic_persist(insights_service))
    print("PASS: dashboard insights report cache shares refreshes and serves stale fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
