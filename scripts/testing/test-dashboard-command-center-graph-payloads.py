#!/usr/bin/env python3
"""Offline regression for command-center graph payload structure."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    config_module = importlib.import_module("api.routes.config")
    config_module = importlib.reload(config_module)

    repo_payload = config_module._build_repo_structure_graph()
    assert_true(repo_payload.get("graph_id") == "repo-structure", "repo graph should identify itself")
    assert_true(any(node.get("type") == "root" for node in (repo_payload.get("nodes") or [])), "repo graph should include a root node")
    assert_true(any(edge.get("relation") == "governs" for edge in (repo_payload.get("edges") or [])), "repo graph should expose governance edges")
    assert_true((repo_payload.get("stats") or {}).get("node_count", 0) > 10, "repo graph should expose useful graph stats")

    workflow_payload = config_module._build_workflow_blueprint_graph()
    assert_true(workflow_payload.get("graph_id") == "workflow-blueprints", "workflow graph should identify itself")
    assert_true(any(node.get("type") == "tool" for node in (workflow_payload.get("nodes") or [])), "workflow graph should include tool nodes")
    assert_true(any(node.get("type") == "surface" for node in (workflow_payload.get("nodes") or [])), "workflow graph should include surface nodes")
    assert_true(any(edge.get("relation") == "review_gate" for edge in (workflow_payload.get("edges") or [])), "workflow graph should expose reviewer-gate logic")
    assert_true(any(edge.get("relation") == "invokes" for edge in (workflow_payload.get("edges") or [])), "workflow graph should expose tool-to-surface invocation edges")

    print("PASS: dashboard command-center graph payloads are well-formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
