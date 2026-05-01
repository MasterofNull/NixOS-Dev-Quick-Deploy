#!/usr/bin/env python3
"""Offline regression for switchboard details in AI service health monitoring."""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _run() -> None:
    ai_service_health = importlib.import_module("api.services.ai_service_health")
    ai_service_health = importlib.reload(ai_service_health)

    monitor = ai_service_health.AIServiceHealthMonitor()
    monitor._get_systemd_status = lambda service_id: asyncio.sleep(0, result={"active": True, "status": "active", "main_pid": 123})
    monitor._get_process_metrics = lambda service_id: asyncio.sleep(0, result={"cpu_percent": 0.0})
    monitor._check_http_health = lambda url: asyncio.sleep(
        0,
        result={
            "healthy": True,
            "status_code": 200,
            "response_time_ms": 0,
            "payload": {
                "status": "ok",
                "routing_mode": "hybrid",
                "default_provider": "local",
                "remote_configured": False,
                "local_lane_status": "busy-long-running",
                "local_runtime": {
                    "slot_capacity": 1,
                    "slot_available": 0,
                    "slot_busy": True,
                    "source": "switchboard_semaphore+llama_metrics",
                    "active_request": {
                        "profile": "continue-local",
                        "duration_s": 91.2,
                        "long_running": True,
                    },
                },
            },
        },
    )

    result = await monitor._check_service_health("ai-switchboard", ai_service_health.AI_SERVICES["ai-switchboard"])
    details = result.get("details") or {}

    assert_true(result.get("status") == "healthy", "healthy switchboard service should remain healthy")
    assert_true(
        details.get("local_lane_status") == "busy-long-running",
        "switchboard details should expose long-running local lane state distinctly",
    )
    assert_true(
        (details.get("local_runtime") or {}).get("slot_busy") is True,
        "switchboard details should preserve local runtime occupancy payload",
    )
    assert_true(details.get("routing_mode") == "hybrid", "switchboard details should expose routing mode")


def main() -> int:
    asyncio.run(_run())
    print("PASS: ai service health monitor exposes switchboard local lane details")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
