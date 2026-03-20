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

        report_path = tmp_path / "latest-aq-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-20T12:30:00Z",
                    "window": "7d",
                    "cache": {"available": True, "hit_pct": 11.8, "hits": 2, "misses": 15},
                    "route_search_latency_decomposition": {"p95_ms": 3565.4, "calls": 42},
                    "route_retrieval_breadth": {"available": True, "avg_collection_count": 2.68, "route_calls": 42},
                    "route_retrieval_breadth_windows": {"windows": {"1h": {"avg_collection_count": 2.68}}},
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

        print("PASS: performance hotspots insights regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
