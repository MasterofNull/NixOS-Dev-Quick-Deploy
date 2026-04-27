import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


HTTP_SERVER_PATH = Path(__file__).with_name("http_server.py")
TARGET_FUNCTIONS = {
    "_load_aq_report_status_summary",
    "_should_prioritize_memory_recall",
    "_build_workflow_plan",
}


def _load_helpers(aq_report_path: Path) -> Dict[str, Any]:
    source = HTTP_SERVER_PATH.read_text()
    tree = ast.parse(source, filename=str(HTTP_SERVER_PATH))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGET_FUNCTIONS
    ]
    module = ast.Module(body=selected, type_ignores=[])
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Path": Path,
        "json": __import__("json"),
        "time": __import__("time"),
        "_AQ_REPORT_LATEST_JSON": aq_report_path,
        "Config": type(
            "Config",
            (),
            {
                "AI_CAPABILITY_DISCOVERY_ENABLED": True,
                "AI_CONTEXT_COMPRESSION_ENABLED": True,
            },
        ),
        "_audit_planned_tools": lambda query, catalog: (catalog, {"enabled": True}),
        "workflow_tool_catalog": lambda query, **_: [
            {"name": "hints", "endpoint": "/hints"},
            {"name": "discovery", "endpoint": "/discovery/capabilities"},
            {"name": "route_search", "endpoint": "/query"},
            {"name": "feedback", "endpoint": "/feedback"},
            {"name": "learning_stats", "endpoint": "/learning/stats"},
        ],
        "_compact_prompt_coaching_metadata": lambda payload: {"score": 0.5, "recommended_agent": "codex", "missing_count": 0},
        "_compact_workflow_tool_catalog": lambda catalog: {k: {"endpoint": v.get("endpoint")} for k, v in catalog.items()},
        "_compact_tool_security": lambda payload: payload,
        "_select_reasoning_pattern": lambda query, prompt_coaching, continuation_query: {"phase_recommendations": {"discover": "react", "plan": "react", "execute": "react", "validate": "chain_of_verification", "handoff": "reflexion"}},
        "_is_continuation_query": lambda query: False,
    }
    exec(compile(module, str(HTTP_SERVER_PATH), "exec"), namespace)
    return namespace


def test_load_aq_report_status_summary_includes_optimization_watch(tmp_path):
    aq_report_path = tmp_path / "latest-aq-report.json"
    aq_report_path.write_text(
        """
        {
          "generated_at": "2026-04-18T00:00:00Z",
          "continue_editor": {},
          "continue_editor_windows": {"windows": {}},
          "intent_contract_compliance": {},
          "route_retrieval_breadth_windows": {"windows": {}},
          "routing_windows": {"windows": {}},
          "remote_profile_utilization_windows": {"windows": {}},
          "route_search_latency_decomposition": {},
          "delegated_prompt_failure_windows": {"windows": {}, "trend": {}},
          "recommendations": ["Improve route_search fallback ranking", "Trim generic commit subjects"],
          "structured_actions": [{"type": "routing", "action": "tune_fallback_ranking", "reason": "generic commit hits outrank specific path matches", "confidence": 0.9, "safe": true}]
        }
        """.strip(),
        encoding="utf-8",
    )
    helpers = _load_helpers(aq_report_path)

    summary = helpers["_load_aq_report_status_summary"]()

    assert summary["optimization_watch"]["available"] is True
    assert summary["optimization_watch"]["recommendation_count"] == 2
    assert summary["optimization_watch"]["top_recommendations"][0] == "Improve route_search fallback ranking"
    assert summary["optimization_watch"]["top_actions"][0]["action"] == "tune_fallback_ranking"


def test_build_workflow_plan_includes_optimization_watch_metadata(tmp_path):
    aq_report_path = tmp_path / "latest-aq-report.json"
    aq_report_path.write_text(
        """
        {
          "generated_at": "2026-04-18T00:00:00Z",
          "continue_editor": {},
          "continue_editor_windows": {"windows": {}},
          "intent_contract_compliance": {},
          "route_retrieval_breadth_windows": {"windows": {}},
          "routing_windows": {"windows": {}},
          "remote_profile_utilization_windows": {"windows": {}},
          "route_search_latency_decomposition": {},
          "delegated_prompt_failure_windows": {"windows": {}, "trend": {}},
          "recommendations": ["Prefer direct path/title matches in fallback summaries"],
          "structured_actions": []
        }
        """.strip(),
        encoding="utf-8",
    )
    helpers = _load_helpers(aq_report_path)

    plan = helpers["_build_workflow_plan"]("improve local fallback ranking")

    assert plan["metadata"]["optimization_watch"]["available"] is True
    assert plan["metadata"]["optimization_watch"]["top_recommendations"][0] == "Prefer direct path/title matches in fallback summaries"
