#!/usr/bin/env python3
"""Static regression checks for command-center graph surfaces."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROUTE = ROOT / "dashboard" / "backend" / "api" / "routes" / "config.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = CONFIG_ROUTE.read_text(encoding="utf-8")

    assert_true(
        'def _build_repo_structure_graph() -> Dict[str, Any]:' in text,
        "expected repo structure graph builder in dashboard config route",
    )
    assert_true(
        'def _build_workflow_blueprint_graph() -> Dict[str, Any]:' in text,
        "expected workflow blueprint graph builder in dashboard config route",
    )
    assert_true(
        'def _graph_stats(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:' in text,
        "expected graph stats helper for command-center payloads",
    )
    assert_true(
        '@router.get("/graphs/repo-structure")' in text,
        "expected repo structure graph API route",
    )
    assert_true(
        '@router.get("/graphs/workflow-blueprints")' in text,
        "expected workflow blueprint graph API route",
    )
    assert_true(
        '"label": "Relational File and Folder Graph"' in text,
        "expected command-center link label for repo graph",
    )
    assert_true(
        '"label": "System Workflow Diagram"' in text,
        "expected command-center link label for workflow diagram",
    )
    assert_true(
        '"surface:/workflow/run/start"' in text and '"surface:/review/acceptance"' in text,
        "expected workflow graph to expose persisted-run and review-gate surfaces",
    )
    assert_true(
        '"stats": _graph_stats(nodes, edges)' in text,
        "expected graph payloads to include node/edge statistics",
    )

    print("PASS: dashboard command-center graph surfaces are wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
