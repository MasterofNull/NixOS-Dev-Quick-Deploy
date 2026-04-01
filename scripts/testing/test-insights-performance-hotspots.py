#!/usr/bin/env python3
"""Offline regression for the performance hotspots insights endpoint."""

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
    with tempfile.TemporaryDirectory(prefix="insights-performance-hotspots-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"
        os.environ["DASHBOARD_OPTIMIZATION_PROPOSALS_PATH"] = str(tmp_path / "optimization-proposals.jsonl")

        report_path = tmp_path / "latest-aq-report.json"
        proposals_path = tmp_path / "optimization-proposals.jsonl"
        report_path.write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-20T12:30:00Z",
                    "window": "7d",
                    "cache": {"available": True, "hit_pct": 11.8, "hits": 2, "misses": 15},
                    "route_search_latency_decomposition": {
                        "p95_ms": 3565.4,
                        "calls": 42,
                        "breakdown": [
                            {"label": "synthesis_type:reasoning", "calls": 22, "p95_ms": 4120.0},
                            {"label": "collection:agent_memory", "calls": 17, "p95_ms": 1480.0},
                        ],
                    },
                    "route_retrieval_breadth": {"available": True, "avg_collection_count": 2.68, "route_calls": 42},
                    "route_retrieval_breadth_windows": {"windows": {"1h": {"avg_collection_count": 2.68}}},
                    "structured_actions": [
                        {
                            "summary": "Reduce route_search synthesis fan-out for high-latency reasoning queries",
                            "action": "tune_route_search_synthesis",
                            "priority": "high",
                            "category": "latency",
                        }
                    ],
                    "rag_posture": {
                        "status": "watch",
                        "reasons": ["cache hit rate 11.8%", "memory recall is lightly used"],
                        "recent_retrieval_calls": 63,
                        "retrieval_mix": {"recent": {"route_search": 41, "tree_search": 1, "recall_agent_memory": 21}},
                        "memory_recall_share_pct": 33.3,
                        "memory_recall_miss_pct": 12.0,
                        "prewarm_candidates": [{"id": "route_search_synthesis", "name": "Route Search Synthesis"}],
                    },
                }
            ),
            encoding="utf-8",
        )
        proposals_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "proposal_type": "routing_threshold_adjustment",
                            "target_config_key": "routing_threshold",
                            "current_value": 0.62,
                            "proposed_value": 0.58,
                            "confidence": 0.91,
                            "evidence_summary": "Route latency remained above target during the last 7d window",
                            "proposal_hash": "proposal-1",
                        }
                    ),
                    json.dumps(
                        {
                            "proposal_type": "iteration_limit_increase",
                            "target_config_key": "bounded_reasoning_iteration_limit",
                            "current_value": 6,
                            "proposed_value": 8,
                            "confidence": 0.72,
                            "evidence_summary": "Long-tail reasoning tasks are saturating the current limit",
                            "proposal_hash": "proposal-2",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        dashboard_main = importlib.import_module("api.main")
        insights_service = importlib.import_module("api.services.ai_insights")
        dashboard_main = importlib.reload(dashboard_main)
        insights_service = importlib.reload(insights_service)

        service = insights_service.get_insights_service()
        service._cache = json.loads(report_path.read_text(encoding="utf-8"))
        service._cache_timestamp = insights_service.datetime.now(insights_service.timezone.utc)

        with TestClient(dashboard_main.app) as client:
            response = client.get("/api/insights/performance/hotspots")
            assert_true(response.status_code == 200, "performance hotspots route should succeed")
            data = response.json()
            assert_true(len(data.get("hotspots") or []) >= 3, "performance hotspots should summarize core issues")
            assert_true((data.get("hotspots") or [])[0].get("id") == "route_latency", "route latency hotspot should be present")
            assert_true((data.get("cache") or {}).get("hit_pct") == 11.8, "cache posture should be preserved")
            assert_true(
                ((data.get("rag_posture") or {}).get("top_prewarm_candidate") or {}).get("id") == "route_search_synthesis",
                "top prewarm candidate should be exposed",
            )
            top_bottleneck = (data.get("top_bottlenecks") or [{}])[0]
            assert_true(
                top_bottleneck.get("label") == "synthesis_type:reasoning",
                "performance hotspots should expose ranked bottleneck labels",
            )
            recommendation = (data.get("optimization_recommendations") or [{}])[0]
            assert_true(
                recommendation.get("action") == "tune_route_search_synthesis",
                "performance hotspots should expose structured optimization recommendations",
            )
            optimization_history = data.get("optimization_history") or {}
            assert_true(optimization_history.get("available") is True, "optimization history should be exposed when proposal telemetry exists")
            assert_true(
                optimization_history.get("total_recent") == 2,
                "optimization history should report the bounded recent proposal count",
            )
            assert_true(
                (optimization_history.get("types") or {}).get("routing_threshold_adjustment") == 1,
                "optimization history should summarize proposal types",
            )
            most_recent = (optimization_history.get("recent") or [{}])[0]
            assert_true(
                most_recent.get("target_config_key") == "bounded_reasoning_iteration_limit",
                "optimization history should expose recent proposals in reverse chronological order",
            )

        print("PASS: performance hotspots insights regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
