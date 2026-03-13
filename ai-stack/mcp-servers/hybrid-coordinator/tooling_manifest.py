"""
Helpers for compact, code-execution-friendly tooling manifests.

The goal is to expose a small, on-demand tool catalog that clients can import
or call as needed without stuffing large tool schemas into every prompt.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _clip_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3].rstrip() + "..."


def _normalize_runtime(value: str) -> str:
    runtime = str(value or "").strip().lower()
    if runtime in {"typescript", "ts", "javascript", "js", "node"}:
        return "typescript"
    return "python"


def workflow_tool_catalog(query: str) -> List[Dict[str, str]]:
    """Heuristic tool assignment for structured execution plans and manifests."""
    q = (query or "").lower()
    tools: List[Dict[str, str]] = []
    seen = set()

    def add(name: str, endpoint: str, reason: str) -> None:
        if name in seen:
            return
        seen.add(name)
        tools.append({"name": name, "endpoint": endpoint, "reason": reason})

    add("hints", "/hints", "Ranked workflow hints and known pitfalls for the query.")
    add("discovery", "/discovery/capabilities", "Progressive disclosure of available stack capabilities.")

    if any(k in q for k in ("find", "search", "retrieve", "context", "rag", "semantic", "lexical")):
        add("route_search", "/query", "Hybrid retrieval path for context and grounded answers.")
        add("memory_recall", "/memory/recall", "Recall prior procedural or semantic memory for similar tasks.")

    if any(
        k in q
        for k in (
            "web",
            "website",
            "page",
            "scrape",
            "scraping",
            "fetch url",
            "extract from",
            "research lane",
            "native plant",
            "plants for my area",
        )
    ):
        add(
            "web_research_fetch",
            "/research/web/fetch",
            "Bounded polite web fetch -> extract for explicit public URLs with robots-aware pacing.",
        )

    if any(k in q for k in ("nixos", "service", "systemd", "deploy", "boot", "shutdown")):
        add("route_search", "/query", "Search indexed NixOS docs, policies, and prior fixes.")
        add("tree_search", "/search/tree", "Broader branch-and-aggregate retrieval for infra issues.")

    if any(k in q for k in ("test", "validate", "verify", "smoke", "check")):
        add("qa_check", "mcp://run_qa_check", "Run aq-qa phases for bounded repo-aware validation evidence.")
        add("harness_eval", "/harness/eval", "Deterministic eval scorecard for acceptance checks.")
        add("health", "/health", "Runtime stack health and capability flags.")

    if any(k in q for k in ("feedback", "learn", "improve", "regression", "quality")):
        add("feedback", "/feedback", "Capture outcome and correction data.")
        add("learning_stats", "/learning/stats", "Inspect learning pipeline health and backlog.")

    if any(
        k in q
        for k in (
            "agentic",
            "autonomous",
            "delegate",
            "delegation",
            "long-running",
            "long running",
            "loop",
            "multi-agent",
            "multi step",
            "multi-step",
            "orchestrate",
            "orchestration",
            "workflow",
            "openrouter",
            "remote agent",
            "delegate",
        )
    ):
        add(
            "ai_coordinator_delegate",
            "/control/ai-coordinator/delegate",
            "Route a bounded delegated task through the ai-coordinator runtime lanes.",
        )
        add(
            "loop_orchestrate",
            "/workflow/orchestrate",
            "Submit long-running or multi-agent work to the Ralph loop through the harness.",
        )
        add(
            "loop_status",
            "/workflow/orchestrate/{task_id}",
            "Poll Ralph loop execution state and optionally fetch final results.",
        )

    if "route_search" not in seen:
        add("route_search", "/query", "Default execution path for response generation with retrieval.")

    return tools


_TOOL_RUNTIME_SPECS: Dict[str, Dict[str, Any]] = {
    "hints": {
        "method": "GET",
        "mcp_tool": "get_workflow_hints",
        "args": ["q", "limit"],
        "output_focus": "Top hints, pitfalls, and prompt snippets only.",
    },
    "discovery": {
        "method": "GET",
        "mcp_tool": "",
        "args": ["level", "category"],
        "output_focus": "Capability summary, not full inventories.",
    },
    "route_search": {
        "method": "POST",
        "mcp_tool": "hybrid_search",
        "args": ["query", "mode", "limit", "generate_response"],
        "output_focus": "Top retrieved evidence and short synthesized answer.",
    },
    "tree_search": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["query", "depth"],
        "output_focus": "Branch summaries, not raw full branches.",
    },
    "memory_recall": {
        "method": "POST",
        "mcp_tool": "recall_memory",
        "args": ["query", "agent_id", "limit"],
        "output_focus": "Short memory summaries relevant to the task.",
    },
    "workflow_plan": {
        "method": "POST",
        "mcp_tool": "workflow_plan",
        "args": ["query"],
        "output_focus": "Phase ids, goals, and tool names only.",
    },
    "workflow_run_start": {
        "method": "POST",
        "mcp_tool": "workflow_run_start",
        "args": ["query", "safety_mode", "token_limit", "tool_call_limit", "intent_contract"],
        "output_focus": "Run id, budget, and safety posture.",
    },
    "harness_eval": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["query", "mode", "expected_keywords"],
        "output_focus": "Pass/fail summary, score, and failure category.",
    },
    "qa_check": {
        "method": "MCP",
        "mcp_tool": "run_qa_check",
        "args": ["phase", "format", "timeout_seconds"],
        "output_focus": "QA phase summary with pass/fail/skipped counts and failing checks only.",
    },
    "health": {
        "method": "GET",
        "mcp_tool": "",
        "args": [],
        "output_focus": "Status booleans and degraded dependencies only.",
    },
    "web_research_fetch": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["urls", "selectors", "max_text_chars"],
        "output_focus": "Per-page title, extracted text excerpt, links, and policy/skip metadata only.",
    },
    "loop_orchestrate": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["prompt", "backend", "max_iterations", "require_approval", "context"],
        "output_focus": "Task id, backend, queue status, and activation posture only.",
    },
    "ai_coordinator_delegate": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["task", "profile", "messages", "tools", "tool_choice", "max_tokens"],
        "output_focus": "Selected runtime, route metadata, and concise delegated response only.",
    },
    "loop_status": {
        "method": "GET",
        "mcp_tool": "",
        "args": ["task_id", "include_result"],
        "output_focus": "Current loop status, iteration count, and final result when requested.",
    },
    "feedback": {
        "method": "POST",
        "mcp_tool": "",
        "args": ["query", "correction", "rating", "tags"],
        "output_focus": "Feedback id and acceptance status.",
    },
    "learning_stats": {
        "method": "GET",
        "mcp_tool": "",
        "args": [],
        "output_focus": "Counters and lag metrics only.",
    },
}


def _phase_summary(tools: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    tool_names = {str(tool.get("name", "")).strip() for tool in tools}

    def pick(names: List[str]) -> List[str]:
        return [name for name in names if name in tool_names]

    phases = [
        {"id": "discover", "tools": pick(["hints", "discovery", "route_search", "tree_search"])},
        {"id": "plan", "tools": pick(["workflow_plan", "hints", "discovery"])},
        {
            "id": "execute",
            "tools": pick(
                [
                    "route_search",
                    "memory_recall",
                    "web_research_fetch",
                    "workflow_run_start",
                    "ai_coordinator_delegate",
                    "loop_orchestrate",
                    "feedback",
                ]
            ),
        },
        {"id": "validate", "tools": pick(["qa_check", "harness_eval", "health", "loop_status", "learning_stats"])},
        {"id": "handoff", "tools": pick(["feedback", "learning_stats"])},
    ]
    return [phase for phase in phases if phase["tools"]]


def build_tooling_manifest(
    query: str,
    tools: List[Dict[str, str]],
    *,
    runtime: str = "python",
    max_tools: Optional[int] = None,
    max_result_chars: Optional[int] = None,
    max_reason_chars: Optional[int] = None,
    phases: Optional[List[Dict[str, Any]]] = None,
    tool_security: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_runtime = _normalize_runtime(runtime)
    manifest_enabled = _env_flag("AI_CODE_EXEC_TOOLING_MANIFEST_ENABLED", "true")
    max_tools_value = max_tools if max_tools is not None else _env_int("AI_CODE_EXEC_MAX_TOOLS", 6)
    max_result_chars_value = (
        max_result_chars if max_result_chars is not None else _env_int("AI_CODE_EXEC_MAX_RESULT_CHARS", 4000)
    )
    max_reason_chars_value = (
        max_reason_chars if max_reason_chars is not None else _env_int("AI_CODE_EXEC_MAX_REASON_CHARS", 160)
    )

    priority = {
        "ai_coordinator_delegate": 100,
        "loop_orchestrate": 95,
        "loop_status": 90,
        "workflow_run_start": 85,
        "qa_check": 80,
        "harness_eval": 75,
    }
    ordered_tools = sorted(
        tools,
        key=lambda tool: (-priority.get(str(tool.get("name", "")).strip(), 0), tools.index(tool)),
    )

    compact_tools: List[Dict[str, Any]] = []
    for tool in ordered_tools[:max_tools_value]:
        name = str(tool.get("name", "")).strip()
        spec = _TOOL_RUNTIME_SPECS.get(name, {})
        compact_tools.append(
            {
                "name": name,
                "endpoint": str(tool.get("endpoint", "")).strip(),
                "method": spec.get("method", "POST"),
                "mcp_tool": spec.get("mcp_tool", ""),
                "args": spec.get("args", []),
                "reason": _clip_text(tool.get("reason", ""), max_reason_chars_value),
                "output_focus": spec.get("output_focus", "Return concise result summaries only."),
            }
        )

    phase_summary = phases or _phase_summary(compact_tools)
    if normalized_runtime == "typescript":
        import_snippet = 'import { HarnessClient } from "@nixos-ai/harness-sdk";'
        factory_snippet = 'const client = new HarnessClient({ baseUrl: "http://127.0.0.1:8003" });'
    else:
        import_snippet = "from harness_sdk import HarnessClient"
        factory_snippet = 'client = HarnessClient(base_url="http://127.0.0.1:8003")'

    return {
        "objective": query,
        "enabled": manifest_enabled,
        "execution_mode": "code-exec-friendly",
        "runtime": normalized_runtime,
        "import_strategy": "import-on-demand",
        "response_budget_chars": max_result_chars_value,
        "usage_rules": [
            "Import the client once, then call only the tools needed for the current phase.",
            "Prefer compact summaries over full raw payloads.",
            "Escalate to deeper retrieval only after the current phase runs out of signal.",
        ],
        "sdk": {
            "import": import_snippet,
            "factory": factory_snippet,
            "manifest_method": "tooling_manifest" if normalized_runtime == "python" else "toolingManifest",
        },
        "tools": compact_tools,
        "phases": phase_summary,
        "metadata": {
            "tool_count": len(compact_tools),
            "max_tools": max_tools_value,
            "max_reason_chars": max_reason_chars_value,
            "query_length": len(query or ""),
            "tool_security": tool_security or {},
        },
    }
