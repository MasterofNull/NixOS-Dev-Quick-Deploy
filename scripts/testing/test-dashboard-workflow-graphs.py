#!/usr/bin/env python3
"""Offline regression for dashboard workflow graph surfaces."""

from __future__ import annotations

import importlib
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


def _sample_yaml_graph_payload() -> dict:
    return {
        "execution_id": "exec-123",
        "workflow_name": "simple-sequential",
        "execution_status": "completed",
        "mermaid": "graph TD\n    task1 --> task2",
        "graph": {
            "workflow": "simple-sequential",
            "levels": [["task1"], ["task2"]],
            "nodes": [
                {
                    "id": "task1",
                    "label": "task1",
                    "agent": "qwen",
                    "prompt": "Analyze repository",
                    "parallel": False,
                    "status": "completed",
                    "metadata": {"has_memory": False},
                },
                {
                    "id": "task2",
                    "label": "task2",
                    "agent": "codex",
                    "prompt": "Implement patch",
                    "parallel": False,
                    "status": "completed",
                    "metadata": {"has_memory": True},
                },
            ],
            "edges": [
                {"source": "task1", "target": "task2", "relation": "depends_on"},
            ],
            "stats": {"node_count": 2, "edge_count": 1, "level_count": 2, "has_cycles": False},
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-workflow-graphs-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)
        workflows_module = importlib.import_module("api.routes.workflows")
        workflows_module = importlib.reload(workflows_module)

        async def fake_fetch_yaml_execution_graph(execution_id: str):
            payload = _sample_yaml_graph_payload()
            payload["execution_id"] = execution_id
            return payload

        async def fake_fetch_yaml_workflow_graph(workflow_file: str):
            payload = _sample_yaml_graph_payload()
            payload.pop("execution_id", None)
            return payload

        workflows_module._fetch_yaml_execution_graph = fake_fetch_yaml_execution_graph
        workflows_module._fetch_yaml_workflow_graph = fake_fetch_yaml_workflow_graph

        with TestClient(dashboard_main.app) as client:
            execution_response = client.get("/api/workflows/executions/exec-456/graph")
            assert_true(execution_response.status_code == 200, "dashboard execution graph route should succeed")
            execution_payload = execution_response.json()

            assert_true(execution_payload.get("execution_id") == "exec-456", "execution graph should preserve execution id")
            assert_true(execution_payload.get("workflow_name") == "simple-sequential", "execution graph should expose workflow name")
            assert_true(execution_payload.get("source") == "yaml-workflow", "execution graph should identify yaml workflow source")
            assert_true(execution_payload.get("status") == "completed", "execution graph should expose execution status")
            assert_true(execution_payload.get("mermaid", "").startswith("graph TD"), "execution graph should expose Mermaid export")
            assert_true(len(execution_payload.get("nodes") or []) == 2, "execution graph should expose normalized nodes")
            assert_true((execution_payload.get("nodes") or [])[0].get("agent") == "qwen", "execution graph should preserve agent lane")
            assert_true((execution_payload.get("edges") or [])[0].get("type") == "depends_on", "execution graph should normalize edge relation")

            definition_response = client.get(
                "/api/workflows/yaml/graph",
                params={"workflow_file": "ai-stack/workflows/examples/simple-sequential.yaml"},
            )
            assert_true(definition_response.status_code == 200, "dashboard yaml workflow graph route should succeed")
            definition_payload = definition_response.json()

            assert_true(definition_payload.get("workflow_file") == "ai-stack/workflows/examples/simple-sequential.yaml", "definition graph should echo workflow file")
            assert_true(definition_payload.get("source") == "yaml-workflow-definition", "definition graph should identify definition source")
            assert_true(definition_payload.get("status") == "definition", "definition graph should identify definition mode")
            assert_true(definition_payload.get("execution_id") is None, "definition graph should not claim an execution id")
            assert_true(definition_payload.get("stats", {}).get("node_count") == 2, "definition graph should preserve graph stats")

        print("PASS: dashboard workflow graph routes prefer canonical yaml graph payloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
