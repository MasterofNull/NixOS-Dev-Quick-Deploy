#!/usr/bin/env python3
"""Offline regression for AI-specific insights metrics surfaces."""

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


class _FakeResponse:
    def __init__(self, payload: str):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="insights-ai-metrics-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        insights_service = importlib.import_module("api.services.ai_insights")
        dashboard_main = importlib.reload(dashboard_main)
        insights_service = importlib.reload(insights_service)

        report = {
            "generated_at": "2026-04-01T14:30:00Z",
            "window": "7d",
        }
        service = insights_service.get_insights_service()
        service._cache = report
        service._cache_timestamp = insights_service.datetime.now(insights_service.timezone.utc)

        metrics_text = "\n".join(
            [
                'hybrid_delegated_prompt_tokens_before_count{profile="remote-free"} 4',
                'hybrid_delegated_prompt_tokens_before_sum{profile="remote-free"} 1600',
                'hybrid_delegated_prompt_tokens_after_count{profile="remote-free"} 4',
                'hybrid_delegated_prompt_tokens_after_sum{profile="remote-free"} 900',
                'hybrid_delegated_prompt_token_savings_total{profile="remote-free"} 700',
                'hybrid_delegated_quality_score_count{profile="remote-free"} 4',
                'hybrid_delegated_quality_score_sum{profile="remote-free"} 3.2',
                'hybrid_delegated_quality_events_total{profile="remote-free",outcome="accepted"} 4',
                'hybrid_progressive_context_loads_total{category="research",tier="warm",profile="remote-free"} 6',
                'hybrid_capability_gap_detections_total{gap_type="tooling",severity="medium"} 2',
                'hybrid_real_time_learning_events_total{profile="remote-free",event_type="learning_example"} 5',
                'hybrid_meta_learning_adaptations_total{domain="python",method="few_shot"} 3',
                "hybrid_process_memory_bytes 1048576",
            ]
        )

        insights_service.urlopen = lambda request, timeout=10.0: _FakeResponse(metrics_text)

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/insights/metrics/ai-specific")
            assert_true(response.status_code == 200, "AI-specific metrics route should succeed")
            data = response.json()
            assert_true(data.get("available") is True, "AI-specific metrics should be available")
            delegated = data.get("delegated_prompt_optimization") or {}
            assert_true(delegated.get("avg_tokens_before") == 400.0, "should compute average prompt tokens before optimization")
            assert_true(delegated.get("avg_tokens_after") == 225.0, "should compute average prompt tokens after optimization")
            assert_true(delegated.get("tokens_saved_total") == 700, "should expose total prompt token savings")
            quality = data.get("delegated_quality") or {}
            assert_true(quality.get("avg_quality_score") == 0.8, "should compute average delegated quality score")
            learning = data.get("learning_and_adaptation") or {}
            assert_true(learning.get("real_time_learning_events_total") == 5, "should expose learning event totals")
            assert_true(learning.get("meta_learning_adaptations_total") == 3, "should expose meta-learning totals")

        print("PASS: AI-specific insights metrics regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
