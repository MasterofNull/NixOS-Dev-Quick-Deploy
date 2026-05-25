import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


WORKFLOW_PLANNING_PATH = Path(__file__).parent.parent / "workflow_planning.py"
TARGET_FUNCTIONS = {
    "_load_aq_report_status_summary",
    "_should_prioritize_memory_recall",
    "_workflow_memory_first_strategy",
    "_build_workflow_plan",
}


def _load_helpers(aq_report_path: Path) -> Dict[str, Any]:
    source = WORKFLOW_PLANNING_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WORKFLOW_PLANNING_PATH))
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
            {"name": "memory_recall", "endpoint": "/memory/recall"},
            {"name": "route_search", "endpoint": "/query"},
            {"name": "feedback", "endpoint": "/feedback"},
            {"name": "learning_stats", "endpoint": "/learning/stats"},
            {"name": "qa_check", "endpoint": "mcp://run_qa_check"},
        ],
        "_compact_prompt_coaching_metadata": lambda payload: {
            "score": 0.5,
            "recommended_agent": "codex",
            "missing_count": 0,
        },
        "_compact_workflow_tool_catalog": lambda catalog: {
            k: {"endpoint": v.get("endpoint")} for k, v in catalog.items()
        },
        "_compact_tool_security": lambda payload: payload,
        "_select_reasoning_pattern": lambda query, prompt_coaching, continuation_query: {
            "phase_recommendations": {
                "discover": "react",
                "plan": "react",
                "execute": "react",
                "validate": "chain_of_verification",
                "handoff": "reflexion",
            }
        },
        "_is_continuation_query": lambda query: False,
    }
    exec(compile(module, str(WORKFLOW_PLANNING_PATH), "exec"), namespace)
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
          "rag_posture": {},
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
          "rag_posture": {},
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
    assert plan["metadata"]["context_strategy"]["mode"] == "progressive-disclosure"
    assert plan["metadata"]["context_strategy"]["recommended_cards"] == ["token-discipline", "harness-first"]


def test_build_workflow_plan_prefers_memory_first_for_continuation_hotspot(tmp_path):
    aq_report_path = tmp_path / "latest-aq-report.json"
    aq_report_path.write_text(
        """
        {
          "generated_at": "2026-04-30T18:12:57Z",
          "continue_editor": {},
          "continue_editor_windows": {"windows": {}},
          "intent_contract_compliance": {},
          "route_retrieval_breadth_windows": {"windows": {"1h": {"calls": 12}}},
          "routing_windows": {"windows": {}},
          "remote_profile_utilization_windows": {"windows": {}},
          "route_search_latency_decomposition": {
            "window": "7d",
            "synthesis_p95_ms": 153234.4,
            "retrieval_only_p95_ms": 438.4,
            "synthesis_calls": 270
          },
          "rag_posture": {
            "available": true,
            "status": "healthy",
            "recent_retrieval_calls": 94,
            "memory_recall_share_pct": 8.5,
            "memory_recall_attempts": 8,
            "memory_recall_miss_pct": 0.0,
            "memory_recall_diagnosis": "unused",
            "memory_recall_actions": [
              "recall prior context before broad route_search on continuation and long-horizon repo tasks"
            ]
          },
          "delegated_prompt_failure_windows": {"windows": {}, "trend": {}},
          "recommendations": [],
          "structured_actions": []
        }
        """.strip(),
        encoding="utf-8",
    )
    helpers = _load_helpers(aq_report_path)
    helpers["_is_continuation_query"] = lambda query: True

    plan = helpers["_build_workflow_plan"]("continue from the last deploy fix")

    assert plan["metadata"]["retrieval_strategy"]["active"] is True
    assert plan["metadata"]["retrieval_strategy"]["mode"] == "memory-first"
    assert "route_search_synthesis_hotspot" in plan["metadata"]["retrieval_strategy"]["reasons"]
    assert plan["metadata"]["context_strategy"]["mode"] == "context-offload"
    assert plan["metadata"]["context_strategy"]["recommended_blueprint_id"] == "long-running-context-offload"
    assert plan["metadata"]["context_strategy"]["recommended_cards"] == [
        "context-offload",
        "token-discipline",
        "harness-first",
    ]
    assert plan["phases"][0]["tools"] == ["hints", "discovery", "memory_recall"]
    assert plan["phases"][1]["tools"] == ["hints", "discovery", "memory_recall"]
    assert plan["phases"][2]["tools"][:2] == ["memory_recall", "route_search"]
