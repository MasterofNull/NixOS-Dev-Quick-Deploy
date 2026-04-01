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
        os.environ["DASHBOARD_IMPROVEMENT_CANDIDATES_PATH"] = str(tmp_path / "improvement-candidates.json")
        os.environ["DASHBOARD_CODE_REVIEW_RESULTS_PATH"] = str(tmp_path / "code-review.json")

        (tmp_path / "improvement-candidates.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-01T11:55:00Z",
                    "total_candidates": 2,
                    "candidates": [
                        {
                            "title": "Fix performance regression in route_search",
                            "category": "performance",
                            "priority": 1,
                            "estimated_impact": "high",
                            "effort": "medium",
                            "related_files": ["ai-stack/mcp-servers/hybrid-coordinator/route_handler.py"],
                        },
                        {
                            "title": "Address broad_exception issues (3 occurrences)",
                            "category": "quality",
                            "priority": 3,
                            "estimated_impact": "medium",
                            "effort": "medium",
                            "related_files": ["dashboard/backend/api/services/ai_insights.py"],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "code-review.json").write_text(
            json.dumps(
                {
                    "reviewed_at": "2026-04-01T12:05:00Z",
                    "reviewer": "qwen-4b",
                    "total_files": 1,
                    "files": [
                        {
                            "file_path": "ai-stack/self-improvement/improvement_detector.py",
                            "overall_quality": 0.7,
                            "comments_count": 2,
                            "summary": "Mostly solid, but broad exception handling remains.",
                            "recommendations": ["Tighten exception handling around file parsing."],
                            "comments": [
                                {
                                    "line": 88,
                                    "severity": "major",
                                    "category": "logic",
                                    "message": "Broad exception handling obscures parse failures.",
                                    "suggestion": "Catch syntax and file errors explicitly.",
                                },
                                {
                                    "line": 145,
                                    "severity": "minor",
                                    "category": "documentation",
                                    "message": "Detector thresholds need inline rationale.",
                                    "suggestion": "Add a short threshold comment.",
                                },
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

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
            "agent_lessons": {
                "available": True,
                "registry": {"active_count": 2},
            },
            "routing": {"available": True, "local_pct": 100.0, "remote_n": 0},
            "continue_editor": {"status": "healthy"},
            "route_search_latency_decomposition": {
                "available": True,
                "overall_p95_ms": 4200.0,
                "synthesis_p95_ms": 6100.0,
                "retrieval_only_p95_ms": 850.0,
                "total_calls": 18,
                "breakdown": [
                    {"label": "local_lane_reason:bounded_reasoning_default_lane", "calls": 5, "p95_ms": 11200.0},
                    {"label": "synthesis_type:reasoning", "calls": 5, "p95_ms": 11200.0},
                ],
            },
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

            readiness_response = client.get("/api/insights/roadmap/readiness")
            assert_true(readiness_response.status_code == 200, "roadmap readiness route should succeed")
            readiness = readiness_response.json()
            phase1 = (readiness.get("phases") or {}).get("phase1") or {}
            phase3 = (readiness.get("phases") or {}).get("phase3") or {}
            phase4 = (readiness.get("phases") or {}).get("phase4") or {}
            phase10 = (readiness.get("phases") or {}).get("phase10") or {}
            phase11 = (readiness.get("phases") or {}).get("phase11") or {}
            assert_true(
                phase1.get("status") == "watch",
                "roadmap readiness should surface active profiling bottlenecks for phase 1",
            )
            top_hotspot = (phase1.get("top_hotspots") or [{}])[0]
            assert_true(
                top_hotspot.get("label") == "local_lane_reason:bounded_reasoning_default_lane",
                "roadmap readiness should preserve the top profiling hotspot label",
            )
            assert_true(
                phase3.get("status") == "watch",
                "roadmap readiness should surface active improvement candidate pressure for phase 3",
            )
            assert_true(
                phase3.get("candidate_count") == 2,
                "roadmap readiness should expose improvement candidate counts",
            )
            top_phase3_candidate = (phase3.get("top_candidates") or [{}])[0]
            assert_true(
                top_phase3_candidate.get("title") == "Fix performance regression in route_search",
                "roadmap readiness should expose the top improvement candidate title",
            )
            assert_true(
                ((phase3.get("code_review") or {}).get("reviewer")) == "qwen-4b",
                "roadmap readiness should expose the persisted code review summary",
            )
            assert_true(
                phase10.get("promotable_lessons") == 1,
                "roadmap readiness should expose feedback acceleration lesson counts",
            )
            assert_true(
                phase11.get("local_routing_pct") == 100.0,
                "roadmap readiness should surface local routing health for phase 11",
            )
            assert_true(
                (phase4.get("a2a_readiness") or {}).get("status") in {"healthy", "ready", "unavailable"},
                "roadmap readiness should include A2A readiness context",
            )

            candidates_response = client.get("/api/insights/improvements/candidates")
            assert_true(candidates_response.status_code == 200, "improvement candidates route should succeed")
            candidates_data = candidates_response.json()
            assert_true(
                candidates_data.get("total_candidates") == 2,
                "improvement candidates route should expose persisted candidate counts",
            )
            assert_true(
                (candidates_data.get("categories") or {}).get("performance") == 1,
                "improvement candidates route should summarize candidate categories",
            )

            review_response = client.get("/api/insights/improvements/reviews")
            assert_true(review_response.status_code == 200, "code review summary route should succeed")
            review_data = review_response.json()
            assert_true(
                review_data.get("reviewer") == "qwen-4b",
                "code review summary route should expose the reviewer id",
            )
            assert_true(
                (review_data.get("severity_counts") or {}).get("major") == 1,
                "code review summary route should summarize review severities",
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
