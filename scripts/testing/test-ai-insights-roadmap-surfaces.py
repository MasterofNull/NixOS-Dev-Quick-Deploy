#!/usr/bin/env python3
"""Offline regression for roadmap-facing AI insights surfaces."""

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
    with tempfile.TemporaryDirectory(prefix="insights-roadmap-surfaces-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        report = {
            "generated_at": "2026-04-01T12:30:00Z",
            "window": "7d",
            "intent_contract_compliance": {"available": True, "total_runs": 6, "contract_coverage_pct": 100.0},
            "task_tooling_quality": {"available": True, "plan_total": 8, "plan_success_pct": 87.5},
            "delegated_prompt_failures": {"available": True, "total_failures": 2},
            "delegated_prompt_failure_windows": {"available": True, "trend": {"status": "worsening"}},
            "feedback_acceleration": {
                "available": True,
                "status": "active",
                "trend": "worsening",
                "recent_failure_count": 2,
                "promotable_lessons": 1,
            },
            "route_search_latency_decomposition": {"available": True, "overall_p95_ms": 4200.0, "total_calls": 18},
            "query_gaps": [{"query_text": "home-manager credential helper conflict", "occurrences": 4}],
            "gap_remediation": {
                "available": True,
                "status": "watch",
                "candidate_count": 1,
                "top_strategies": [["extract_pattern", 1]],
                "candidates": [
                    {
                        "topic": "home-manager credential helper conflict",
                        "occurrences": 4,
                        "strategy": "extract_pattern",
                    }
                ],
            },
            "route_retrieval_breadth_windows": {"windows": {"1h": {"avg_collection_count": 2.1}}},
            "rag_posture": {"status": "watch"},
        }

        dashboard_main = importlib.import_module("api.main")
        insights_service = importlib.import_module("api.services.ai_insights")
        dashboard_main = importlib.reload(dashboard_main)
        insights_service = importlib.reload(insights_service)

        service = insights_service.get_insights_service()
        service._cache = report
        service._cache_timestamp = insights_service.datetime.now(insights_service.timezone.utc)

        with TestClient(dashboard_main.app) as client:
            workflow_response = client.get("/api/insights/workflows/compliance")
            assert_true(workflow_response.status_code == 200, "workflow compliance route should succeed")
            workflow_data = workflow_response.json()
            assert_true(
                (workflow_data.get("feedback_acceleration") or {}).get("status") == "active",
                "workflow compliance should expose feedback acceleration",
            )

            complexity_response = client.get("/api/insights/queries/complexity")
            assert_true(complexity_response.status_code == 200, "query complexity route should succeed")
            complexity_data = complexity_response.json()
            assert_true(
                (complexity_data.get("gap_remediation") or {}).get("candidate_count") == 1,
                "query complexity should expose gap remediation summary",
            )
            top_candidate = ((complexity_data.get("gap_remediation") or {}).get("candidates") or [{}])[0]
            assert_true(
                top_candidate.get("strategy") == "extract_pattern",
                "query complexity should preserve classified remediation strategy",
            )

        print("PASS: AI insights exposes roadmap-facing feedback and remediation surfaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
