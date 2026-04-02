#!/usr/bin/env python3

"""Focused query-context regression checks for ContextStore search helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dashboard" / "backend"))

from api.services.context_store import ContextStore


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def context_store(temp_db):
    store = ContextStore(db_path=temp_db)
    yield store
    store.close()


class TestRepoAndLogContextSearch:
    def test_search_repo_context_groups_matches_and_classifies_sources(self, context_store, tmp_path):
        repo_root = tmp_path / "repo"
        (repo_root / "config").mkdir(parents=True)
        (repo_root / "dashboard" / "backend").mkdir(parents=True)
        (repo_root / "docs").mkdir(parents=True)

        stdout = "\n".join([
            "config/service-endpoints.sh:12:AI_SWITCHBOARD_URL=http://127.0.0.1:9001",
            "config/service-endpoints.sh:18:SWITCHBOARD_TIMEOUT=30",
            "dashboard/backend/api/routes.py:44:switchboard timeout fallback route",
            "docs/operations/switchboard.md:9:switchboard timeout troubleshooting guide",
        ])

        with patch.object(context_store, "_repo_root", return_value=repo_root), patch(
            "api.services.context_store.shutil.which", return_value="/usr/bin/rg"
        ), patch(
            "api.services.context_store.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
        ):
            results = context_store.search_repo_context("switchboard timeout config", limit=8)

        assert [item["source"] for item in results] == ["config", "code", "code"]
        assert results[0]["metadata"]["match_count"] == 2
        assert results[0]["metadata"]["line_numbers"] == [12, 18]
        assert "switchboard" in results[0]["explanation"]["summary"]
        assert results[0]["explanation"]["action_hint"] == "Adjust canonical dashboard/service endpoint wiring here first"
        assert results[1]["metadata"]["file_path"] == "dashboard/backend/api/routes.py"
        assert results[2]["metadata"]["file_path"] == "docs/operations/switchboard.md"
        assert "Reference documentation context only" in results[2]["explanation"]["action_hint"]

    def test_search_log_context_groups_hits_by_unit(self, context_store):
        def fake_run(command, capture_output, text, check, timeout):
            unit = command[2]
            if unit == "switchboard.service":
                stdout = "\n".join([
                    "Apr 01 switchboard timeout waiting for backend",
                    "Apr 01 switchboard timeout retry succeeded",
                ])
            elif unit == "ai-hybrid-coordinator.service":
                stdout = "Apr 01 coordinator timeout while syncing switchboard status"
            else:
                stdout = ""
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        with patch("api.services.context_store.shutil.which", side_effect=lambda name: "/usr/bin/journalctl" if name == "journalctl" else None), patch(
            "api.services.context_store.subprocess.run", side_effect=fake_run
        ):
            results = context_store.search_log_context("switchboard service timeout status", limit=8)

        by_unit = {item["message"]: item for item in results}
        assert set(by_unit) == {"switchboard.service", "ai-hybrid-coordinator.service"}
        assert by_unit["switchboard.service"]["source"] == "logs"
        assert by_unit["switchboard.service"]["metadata"]["match_count"] == 2
        assert "Inspect live runtime logs" in by_unit["switchboard.service"]["explanation"]["action_hint"]
        assert "timeout" in by_unit["switchboard.service"]["explanation"]["matched_terms"]


class TestServiceAndConfigContextSearch:
    def test_search_service_context_marks_health_issues(self, context_store):
        deployment_id = "deploy-service-001"
        context_store.start_deployment(deployment_id, "check switchboard health", "tester")
        context_store.add_service_state(
            deployment_id,
            "switchboard",
            "failed",
            metadata={"unit": "ai-switchboard.service"},
        )

        results = context_store.search_service_context("switchboard service failed", limit=5)

        assert len(results) == 1
        assert results[0]["source"] == "service"
        assert results[0]["metadata"]["health_issue"] is True
        assert results[0]["message"] == "Service switchboard status: failed"

    def test_search_config_context_marks_validation_failures(self, context_store):
        deployment_id = "deploy-config-001"
        context_store.start_deployment(deployment_id, "adjust switchboard timeout config", "tester")
        context_store.add_config_change(
            deployment_id,
            "switchboard.timeout",
            "15",
            change_type="error",
            metadata={"validator": "nix-eval"},
        )

        results = context_store.search_config_context("switchboard.timeout config", limit=5)

        assert len(results) == 1
        assert results[0]["source"] == "config"
        assert results[0]["metadata"]["validation_failed"] is True
        assert "Change Type: error" in results[0]["snippet"]


class TestDeploymentContextAggregation:
    def test_service_intent_prefers_service_and_runtime_results(self, context_store):
        deployment_results = [
            {
                "id": "dep-1",
                "deployment_id": "dep-1",
                "event_type": "progress",
                "message": "switchboard restart applied",
                "timestamp": None,
                "progress": 100,
                "metadata": {},
                "relevance_score": 1,
                "snippet": "deployment result",
                "source": "deployment",
            },
            {
                "id": "semantic-1",
                "deployment_id": "dep-sem",
                "event_type": "semantic",
                "message": "semantic drift",
                "timestamp": None,
                "progress": None,
                "metadata": {},
                "relevance_score": 0,
                "distance": 1.6,
                "snippet": "weak semantic",
                "source": "semantic",
            },
        ]
        log_results = [
            {
                "id": "log-1",
                "deployment_id": "",
                "event_type": "log",
                "message": "ai-switchboard.service",
                "timestamp": None,
                "progress": None,
                "metadata": {"match_count": 5, "snippets": ["timeout retry exhausted"]},
                "relevance_score": 2,
                "snippet": "timeout retry exhausted",
                "source": "logs",
                "explanation": {"matched_terms": ["switchboard", "timeout"]},
            }
        ]
        repo_results = [
            {
                "id": "docs/operations/switchboard.md",
                "deployment_id": "",
                "event_type": "code",
                "message": "docs/operations/switchboard.md",
                "timestamp": None,
                "progress": None,
                "metadata": {"file_path": "docs/operations/switchboard.md", "match_count": 1},
                "relevance_score": 1,
                "snippet": "documentation only",
                "source": "code",
                "explanation": {"matched_terms": ["switchboard"]},
            },
            {
                "id": "dashboard/backend/api/routes.py",
                "deployment_id": "",
                "event_type": "code",
                "message": "dashboard/backend/api/routes.py",
                "timestamp": None,
                "progress": None,
                "metadata": {"file_path": "dashboard/backend/api/routes.py", "match_count": 1},
                "relevance_score": 1,
                "snippet": "switchboard retry fallback",
                "source": "code",
                "explanation": {"matched_terms": ["switchboard", "retry"]},
            },
        ]
        service_results = [
            {
                "id": "service-1",
                "deployment_id": "dep-1",
                "event_type": "service",
                "message": "Service switchboard status: failed",
                "timestamp": None,
                "progress": None,
                "metadata": {"service_name": "switchboard", "health_issue": True},
                "relevance_score": 1,
                "snippet": "Service: switchboard, Status: failed",
                "source": "service",
                "explanation": {"matched_terms": ["service", "switchboard"]},
            }
        ]

        with patch.object(context_store, "search_deployments_hybrid", return_value=deployment_results), patch.object(
            context_store, "search_log_context", return_value=log_results
        ), patch.object(
            context_store, "search_repo_context", return_value=repo_results
        ) as repo_search, patch.object(
            context_store, "search_service_context", return_value=service_results
        ), patch.object(
            context_store, "search_config_context", return_value=[]
        ), patch.object(
            context_store, "explain_deployment_search_result",
            side_effect=lambda query, item: {} if item.get("source") == "semantic" else {"matched_terms": [item["deployment_id"] or "deployment"]},
        ), patch.object(
            context_store, "build_operator_guidance",
            return_value={"next_step": "inspect switchboard"},
        ):
            response = context_store.search_deployment_context("switchboard service timeout status", limit=8)

        assert response["query_analysis"]["recommended_graph_view"] == "services"
        assert response["sources"] == {"deployment": 1, "logs": 1, "service": 1, "config": 0, "code": 1}
        assert all(item["id"] != "semantic-1" for item in response["results"])
        assert all(item["id"] != "docs/operations/switchboard.md" for item in response["results"])
        repo_search.assert_called_once_with("switchboard service timeout status", limit=4, source_filter="code")

    def test_config_intent_prefers_config_results(self, context_store):
        deployment_results = [
            {
                "id": "dep-2",
                "deployment_id": "dep-2",
                "event_type": "progress",
                "message": "config rollout",
                "timestamp": None,
                "progress": 100,
                "metadata": {},
                "relevance_score": 1,
                "snippet": "deployment config result",
                "source": "deployment",
            }
        ]
        config_results = [
            {
                "id": "config-1",
                "deployment_id": "dep-2",
                "event_type": "config",
                "message": "Config switchboard.timeout changed: 15",
                "timestamp": None,
                "progress": None,
                "metadata": {"config_key": "switchboard.timeout", "validation_failed": True},
                "relevance_score": 1,
                "snippet": "Config: switchboard.timeout, Change Type: error, Value: 15",
                "source": "config",
                "explanation": {"matched_terms": ["config", "switchboard.timeout"]},
            }
        ]

        with patch.object(context_store, "search_deployments_hybrid", return_value=deployment_results), patch.object(
            context_store, "search_log_context", return_value=[]
        ), patch.object(
            context_store, "search_repo_context", return_value=[]
        ) as repo_search, patch.object(
            context_store, "search_service_context", return_value=[]
        ), patch.object(
            context_store, "search_config_context", return_value=config_results
        ), patch.object(
            context_store, "explain_deployment_search_result",
            return_value={"matched_terms": ["config"]},
        ), patch.object(
            context_store, "build_operator_guidance",
            return_value={"next_step": "inspect config"},
        ):
            response = context_store.search_deployment_context("yaml parameter pool.size config value", limit=8)

        assert response["query_analysis"]["recommended_graph_view"] == "configs"
        assert response["sources"]["config"] == 1
        assert response["results"][0]["source"] == "config"
        repo_search.assert_called_once_with("yaml parameter pool.size config value", limit=4, source_filter="all")


class TestDeploymentSearchStatus:
    def test_get_deployment_search_status_summarizes_index_state(self, context_store):
        indexed_id = "deploy-indexed-001"
        error_id = "deploy-error-001"
        pending_id = "deploy-pending-001"

        for deployment_id in [indexed_id, error_id, pending_id]:
            context_store.start_deployment(deployment_id, f"run {deployment_id}", "tester")
            context_store.complete_deployment(deployment_id, success=deployment_id != error_id)

        context_store.conn.execute(
            """
            INSERT INTO deployment_semantic_index
            (deployment_id, document_id, content_hash, indexed_at, last_error)
            VALUES (?, ?, ?, datetime('now'), NULL)
            """,
            (indexed_id, 101, "hash-indexed"),
        )
        context_store.conn.execute(
            """
            INSERT INTO deployment_semantic_index
            (deployment_id, document_id, content_hash, indexed_at, last_error)
            VALUES (?, ?, ?, NULL, ?)
            """,
            (error_id, 202, "hash-error", "aidb unavailable"),
        )
        context_store.conn.commit()

        status = context_store.get_deployment_search_status(recent_limit=5)

        assert status["summary"]["tracked_deployments"] == 3
        assert status["summary"]["indexed_total"] == 1
        assert status["summary"]["error_total"] == 1
        assert status["summary"]["pending_recent"] == 1
        assert status["summary"]["recent_coverage_pct"] == pytest.approx(33.3, rel=0.01)
        assert status["latest_error"]["deployment_id"] == error_id
        assert {item["semantic_state"] for item in status["recent"]} == {"indexed", "error", "pending"}
