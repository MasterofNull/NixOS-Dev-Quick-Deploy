import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


HTTP_SERVER_PATH = Path(__file__).with_name("http_server.py")
TARGET_FUNCTIONS = {
    "_apply_query_response_mode",
}


def _load_helpers() -> Dict[str, Any]:
    source = HTTP_SERVER_PATH.read_text(encoding="utf-8")
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
        "_load_aq_report_status_summary": lambda: {"available": True},
        "_workflow_memory_first_strategy": lambda query, memory_recall_priority, summary: {
            "active": bool(memory_recall_priority),
            "mode": "memory-first" if memory_recall_priority else "standard",
            "reasons": ["route_search_synthesis_hotspot"] if memory_recall_priority else [],
            "evidence": {"memory_recall_share_pct": 8.5},
        },
        "_is_continuation_query": lambda query: "continue" in str(query or "").lower() or "resume" in str(query or "").lower(),
    }
    exec(compile(module, str(HTTP_SERVER_PATH), "exec"), namespace)
    return namespace


def test_apply_query_response_mode_downshifts_resume_style_continuation():
    helpers = _load_helpers()
    request = {"audit_metadata": {}}
    request_context = {"memory_recall": ["resume the deploy fix from yesterday"]}

    effective = helpers["_apply_query_response_mode"](
        "continue from the last deploy fix and show remaining work",
        {"generate_response": True},
        request_context,
        True,
        True,
        request,
    )

    assert effective is False
    assert request_context["response_generation_downshifted"] is True
    assert request_context["response_generation_downshift_reason"] == "continuation_memory_first"
    assert request["audit_metadata"]["retrieval_strategy_mode"] == "memory-first"
    assert request["audit_metadata"]["response_generation_downshifted"] is True


def test_apply_query_response_mode_keeps_explanatory_continuation_synthesis():
    helpers = _load_helpers()
    request = {"audit_metadata": {}}
    request_context = {"memory_recall": ["service watchdog warning context"]}

    effective = helpers["_apply_query_response_mode"](
        "continue from the last incident and explain why the service failed",
        {"generate_response": True},
        request_context,
        True,
        True,
        request,
    )

    assert effective is True
    assert "response_generation_downshifted" not in request_context
    assert request["audit_metadata"]["response_generation_downshifted"] is False


def test_apply_query_response_mode_requires_successful_memory_recall():
    helpers = _load_helpers()
    request = {"audit_metadata": {}}
    request_context: Dict[str, Any] = {}

    effective = helpers["_apply_query_response_mode"](
        "resume the next steps from the last deploy session",
        {"generate_response": True},
        request_context,
        True,
        True,
        request,
    )

    assert effective is True
    assert "response_generation_downshifted" not in request_context
    assert request["audit_metadata"]["response_generation_downshifted"] is False
