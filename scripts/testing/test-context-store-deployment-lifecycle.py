#!/usr/bin/env python3

"""Focused deployment lifecycle and semantic-index regression checks for ContextStore."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import sys

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


class TestDeploymentLifecycle:
    def test_deployment_lifecycle_summary_and_timeline(self, context_store):
        deployment_id = "deploy-lifecycle-001"

        assert context_store.start_deployment(deployment_id, "nixos-rebuild switch", "tester")
        context_store.add_event(
            deployment_id,
            "progress",
            "Build phase completed",
            progress=45,
            metadata={"phase": "build"},
        )
        context_store.update_deployment_status(
            deployment_id,
            "validating",
            progress=80,
            exit_code=0,
            completed=False,
        )
        assert context_store.complete_deployment(
            deployment_id,
            success=True,
            exit_code=0,
            message="Deployment finished cleanly",
        )

        summary = context_store.get_deployment_summary(deployment_id)
        assert summary is not None
        assert summary["status"] == "success"
        assert summary["progress"] == 100
        assert summary["exit_code"] == 0
        assert summary["event_counts"]["started"] == 1
        assert summary["event_counts"]["progress"] == 1
        assert summary["event_counts"]["success"] == 1
        assert summary["context_saved"] is True

        timeline = context_store.get_deployment_timeline(deployment_id)
        assert [item["event_type"] for item in timeline] == ["started", "progress", "success"]
        assert timeline[1]["metadata"]["phase"] == "build"

        recent = context_store.get_recent_deployments(limit=5)
        assert recent[0]["deployment_id"] == deployment_id
        assert context_store.count_deployments() == 1
        assert context_store.count_deployments(status="success") == 1

    def test_error_only_git_and_file_tracking(self, context_store):
        deployment_id = "deploy-errors-001"
        context_store.start_deployment(deployment_id, "nixos-rebuild test", "tester")
        context_store.add_event(deployment_id, "progress", "Starting preflight", progress=10)
        context_store.add_event(
            deployment_id,
            "error",
            "Validation error: missing secret",
            progress=25,
            metadata={"secret": "aidb_api_key"},
        )
        context_store.complete_deployment(
            deployment_id,
            success=False,
            exit_code=1,
            message="Deployment failed after validation error",
        )

        git_id = context_store.track_git_operation(
            deployment_id,
            "commit",
            branch="main",
            commit_hash="abc123",
            files_changed=["nix/modules/services/example.nix"],
        )
        file_id = context_store.track_file_edit(
            deployment_id,
            "nix/modules/services/example.nix",
            "update",
            size_before=120,
            size_after=148,
        )

        assert git_id > 0
        assert file_id > 0

        errors = context_store.get_deployment_errors_only(deployment_id)
        assert len(errors) == 2
        assert any("Validation error" in item["message"] for item in errors)
        assert any("Deployment failed" in item["message"] for item in errors)


class TestDeploymentSearchAndSemanticIndex:
    def test_keyword_search_and_hybrid_dedup(self, context_store):
        deployment_id = "deploy-search-001"
        context_store.start_deployment(deployment_id, "switchboard fix rollout", "tester")
        context_store.add_event(
            deployment_id,
            "progress",
            "Switchboard service fix applied and validated",
            progress=55,
            metadata={"service": "ai-switchboard"},
        )
        context_store.complete_deployment(deployment_id, success=True)

        keyword = context_store.search_deployments("switchboard validated", limit=5)
        assert keyword, "keyword search should return indexed deployment events"
        assert keyword[0]["deployment_id"] == deployment_id

        with patch.object(
            ContextStore,
            "search_deployments_semantic",
            return_value=[
                {
                    "id": 999,
                    "deployment_id": deployment_id,
                    "event_type": "semantic",
                    "message": "switchboard fix rollout",
                    "timestamp": None,
                    "progress": 100,
                    "metadata": {},
                    "relevance_score": 0.01,
                    "distance": 0.2,
                    "snippet": "semantic result",
                    "source": "semantic",
                }
            ],
        ):
            hybrid = context_store.search_deployments_hybrid("switchboard validated", limit=5)
        assert hybrid, "hybrid search should merge semantic and keyword results"
        assert len(hybrid) <= 2

    def test_semantic_sync_success_error_and_unchanged_paths(self, context_store):
        deployment_id = "deploy-semantic-001"
        context_store.start_deployment(deployment_id, "deploy semantic path", "tester")
        context_store.add_event(deployment_id, "progress", "Semantic sync candidate", progress=60)
        context_store.complete_deployment(deployment_id, success=True)

        calls = []

        def fake_aidb_request(path, method="GET", payload=None, query=None, timeout=30.0):
            calls.append((path, method, payload, query))
            if path == "/documents" and method == "POST":
                return {"status": "ok"}
            if path == "/documents" and method == "GET":
                return {
                    "documents": [
                        {
                            "id": 321,
                            "relative_path": f"deployments/{deployment_id}.md",
                        }
                    ]
                }
            if path == "/vector/index" and method == "POST":
                return {"status": "ok"}
            raise AssertionError(f"Unexpected AIDB request: {path} {method}")

        with patch.object(context_store, "_aidb_request", side_effect=fake_aidb_request):
            indexed = context_store.sync_deployment_to_semantic_index(deployment_id)
            unchanged = context_store.sync_deployment_to_semantic_index(deployment_id)

        assert indexed["status"] == "indexed"
        assert indexed["document_id"] == 321
        assert unchanged["status"] == "unchanged"
        assert any(path == "/vector/index" for path, _, _, _ in calls)

        with patch.object(context_store, "_aidb_request", side_effect=RuntimeError("aidb unavailable")):
            failed = context_store.sync_deployment_to_semantic_index("missing-semantic-deploy")
        assert failed["status"] == "missing"

        broken_id = "deploy-semantic-error-001"
        context_store.start_deployment(broken_id, "deploy semantic error", "tester")
        context_store.complete_deployment(broken_id, success=False)
        with patch.object(context_store, "_aidb_request", side_effect=RuntimeError("aidb unavailable")):
            errored = context_store.sync_deployment_to_semantic_index(broken_id)
        assert errored["status"] == "error"
        row = context_store.conn.execute(
            "SELECT last_error FROM deployment_semantic_index WHERE deployment_id = ?",
            (broken_id,),
        ).fetchone()
        assert row is not None
        assert "aidb unavailable" in row["last_error"]

    def test_cleanup_old_deployments_removes_stale_rows(self, context_store):
        old_id = "deploy-old-001"
        fresh_id = "deploy-fresh-001"

        context_store.start_deployment(old_id, "legacy deploy", "tester")
        context_store.start_deployment(fresh_id, "fresh deploy", "tester")
        context_store.add_event(old_id, "progress", "Old event", progress=15)
        context_store.add_event(fresh_id, "progress", "Fresh event", progress=25)

        context_store.conn.execute(
            "UPDATE deployments SET started_at = datetime('now', '-90 days') WHERE deployment_id = ?",
            (old_id,),
        )
        context_store.conn.execute(
            """
            UPDATE deployment_events
            SET timestamp = CASE event_type
                WHEN 'started' THEN datetime('now', '-90 days')
                ELSE datetime('now', '-89 days')
            END
            WHERE deployment_id = ?
            """,
            (old_id,),
        )
        context_store.conn.commit()

        removed = context_store.cleanup_old_deployments(days=30)
        assert removed >= 2
        assert context_store.get_deployment_summary(old_id) is None
        assert context_store.get_deployment_summary(fresh_id) is not None
