import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


WORKFLOW_SESSION_HANDLERS_PATH = Path(__file__).parent.parent / "workflow_session_handlers.py"
TARGET_FUNCTIONS = {
    "_normalize_activation_patterns",
    "_score_blueprint_for_query",
    "_auto_select_workflow_blueprint",
}


def _load_helpers() -> Dict[str, Any]:
    source = WORKFLOW_SESSION_HANDLERS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WORKFLOW_SESSION_HANDLERS_PATH))
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
        "Tuple": Tuple,
    }
    exec(compile(module, str(WORKFLOW_SESSION_HANDLERS_PATH), "exec"), namespace)
    return namespace


def test_auto_select_workflow_blueprint_prefers_context_offload_patterns() -> None:
    helpers = _load_helpers()
    auto_select = helpers["_auto_select_workflow_blueprint"]

    blueprints = {
        "blueprints": [
            {
                "id": "repo-refactor-guarded",
                "activation_patterns": ["refactor", "rename"],
            },
            {
                "id": "long-running-context-offload",
                "activation_patterns": ["token usage", "prompt cache", "context offload", "agentic flow"],
            },
        ]
    }

    selected, selection = auto_select(
        "optimize token usage and agentic flow with prompt cache reuse",
        blueprints,
    )

    assert selected["id"] == "long-running-context-offload"
    assert selection["mode"] == "auto"
    assert "token usage" in selection["matched_patterns"]
    assert "agentic flow" in selection["matched_patterns"]


def test_auto_select_workflow_blueprint_returns_none_without_matches() -> None:
    helpers = _load_helpers()
    auto_select = helpers["_auto_select_workflow_blueprint"]

    selected, selection = auto_select(
        "update dashboard copy",
        {
            "blueprints": [
                {"id": "long-running-context-offload", "activation_patterns": ["token usage", "context offload"]},
            ]
        },
    )

    assert selected is None
    assert selection == {}
