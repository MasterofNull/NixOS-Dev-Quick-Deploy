#!/usr/bin/env python3
"""Regression tests for aq-qa delegate SLO windowing."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.testing.harness_qa.phases import phase0
from scripts.testing.harness_qa.core.result import Status


@dataclass
class FakeContext:
    hybrid_coordinator_url: str = "http://127.0.0.1:8003"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    original_age = phase0._service_active_age_seconds
    original_http_json = phase0.http_json
    seen_urls: list[str] = []

    try:
        phase0._service_active_age_seconds = lambda unit: 123  # type: ignore[assignment]

        def fake_current_window(url: str, timeout: int = 5, headers=None):
            seen_urls.append(url)
            return {"total": 0, "ok": 0, "success_rate": None, "window_s": 123, "skipped_probes": 0}

        phase0.http_json = fake_current_window  # type: ignore[assignment]
        result = phase0._check_delegate_rate(FakeContext())[0]
        assert_true("window_s=123" in seen_urls[-1], "delegate check should use current service activation window")
        assert_true(result.status == Status.SKIP, "low current-generation sample should skip, not fail")
        assert_true("current coordinator activation" in (result.reason or ""), "skip reason should name activation scope")

        phase0._service_active_age_seconds = lambda unit: None  # type: ignore[assignment]
        seen_urls.clear()
        phase0._check_delegate_rate(FakeContext())
        assert_true("window_s=86400" in seen_urls[-1], "delegate check should fall back to 24h when uptime unavailable")
    finally:
        phase0._service_active_age_seconds = original_age  # type: ignore[assignment]
        phase0.http_json = original_http_json  # type: ignore[assignment]

    print("PASS: aq-qa delegate SLO uses current activation window")


if __name__ == "__main__":
    main()
