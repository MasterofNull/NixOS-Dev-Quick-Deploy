#!/usr/bin/env python3
"""
Local agent subprocess runtime.

Extracted from http_server.py agent_code string (Phase 12.4 / senior review).
This module is the "brain" executed by _spawn_local_agent() in http_server.py.
Running as a real file enables: syntax highlighting, linting, unit testing,
and independent versioning of agent logic separate from the server.

Environment variables (all injected by _spawn_local_agent):
  AGENT_ID              — unique ID for this invocation
  AGENT_ROLE            — "coordinator" | "coder"
  AGENT_TASK            — the task text
  AGENT_SYSTEM_PROMPT   — system prompt for this role
  AGENT_STATE_FILE      — path to write JSON state updates
  AGENT_MAX_TOKENS      — max completion tokens (default 768)
  AGENT_TEMPERATURE     — sampling temperature (default 0.3)
  AGENT_TIMEOUT         — total timeout seconds (default 240)
  AGENT_THINKING_MODE   — "on" | "off"
  AGENT_NO_THINK_PREFIX — prefix to suppress CoT (e.g. "/no_think" for Qwen3)
  AGENT_STOP_SEQUENCES  — JSON-encoded list of stop tokens
  AGENT_TOOLS_ENABLED   — "true" | "false"
  AGENT_STREAMING       — "true" | "false" (SSE streaming mode)
  SWITCHBOARD_URL       — inference router (default localhost:8085)
  LLAMA_CPP_URL         — direct llama.cpp fallback (default localhost:8080)
  HYBRID_URL            — hybrid-coordinator base URL (default localhost:8003)
"""

import asyncio
import json
import logging
import os
import pathlib
import shutil
import sys
import time

import httpx

logger = logging.getLogger(__name__)

# shared/ lives at ai-stack/mcp-servers/shared/ — resolve from this file's location.
# ai-stack/agents/runtimes/ -> parents[2] = ai-stack/
_MCP_SERVERS_PATH = str(pathlib.Path(__file__).resolve().parents[2] / "mcp-servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)

from shared.llm_config import build_llama_payload  # noqa: E402

AGENT_ID = os.environ["AGENT_ID"]
AGENT_ROLE = os.environ["AGENT_ROLE"]
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
AGENT_TASK = os.environ["AGENT_TASK"]
SWITCHBOARD_URL = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085")
LLAMA_CPP_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080")
HYBRID_URL = os.environ.get("HYBRID_URL", "http://127.0.0.1:8003")
STATE_FILE = os.environ.get("AGENT_STATE_FILE", "")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "768"))
# None when not explicitly set — defers to task profile temperature in build_llama_payload().
TEMPERATURE: float | None = float(os.environ["AGENT_TEMPERATURE"]) if "AGENT_TEMPERATURE" in os.environ else None
# Phase 2026.06: Increased default timeout for edge AI
AGENT_TIMEOUT = float(os.environ.get("AGENT_TIMEOUT", "600"))
# Task profile selects thinking mode + token budget. Defaults to "agent" (no thinking).
# Callers may inject "research" or "deep_reasoning" via AGENT_TASK_TYPE for PRSI/planning tasks.
AGENT_TASK_TYPE = os.environ.get("AGENT_TASK_TYPE", "agent")

# Phase 30.6: auto-inject context-bootstrap preamble at startup
AGENT_INJECT_BOOTSTRAP = os.environ.get("AGENT_INJECT_BOOTSTRAP", "false").lower() == "true"
BOOTSTRAP_TIMEOUT = float(os.environ.get("AGENT_BOOTSTRAP_TIMEOUT", "15"))
# Phase 33.4: cap tool output injected back into context (tokenmaxxing — reduce wasted tokens)
TOOL_OUTPUT_MAX_CHARS = int(os.environ.get("AGENT_TOOL_OUTPUT_MAX_CHARS", "800"))

_thinking_on = os.environ.get("AGENT_THINKING_MODE", "off") == "on"
NO_THINK_PREFIX_STR = os.environ.get("AGENT_NO_THINK_PREFIX", "")
NO_THINK_PREFIX = (not _thinking_on) and bool(NO_THINK_PREFIX_STR)

try:
    STOP_SEQUENCES = json.loads(os.environ.get("AGENT_STOP_SEQUENCES", "[]")) or [
        "<|im_end|>",
        "<|endoftext|>",
    ]
except Exception:
    STOP_SEQUENCES = ["<|im_end|>", "<|endoftext|>"]

TOOLS_ENABLED = os.environ.get("AGENT_TOOLS_ENABLED", "false").lower() == "true"
STREAMING_MODE = (
    os.environ.get("AGENT_STREAMING", "false").lower() == "true" and not TOOLS_ENABLED
)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_ARG_BLOCKLIST_CHARS = set(";&|><`$\n\r")
_AQ_QA_PHASES = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "all", "phase0", "phase1", "phase2", "phase3"}
_ALLOWED_HARNESS_CLI_TOOLS = {
    "aq-qa": REPO_ROOT / "scripts" / "ai" / "aq-qa",
    "aq-report": REPO_ROOT / "scripts" / "ai" / "aq-report",
    "aq-operational-perspective": REPO_ROOT / "scripts" / "ai" / "aq-operational-perspective",
    "aq-introspection-validate": REPO_ROOT / "scripts" / "ai" / "aq-introspection-validate",
    "aq-memory": REPO_ROOT / "scripts" / "ai" / "aq-memory",
    "aq-context-bootstrap": REPO_ROOT / "scripts" / "ai" / "aq-context-bootstrap",
    "aq-context-manage": REPO_ROOT / "scripts" / "ai" / "aq-context-manage",
    "aq-feedback-loop": REPO_ROOT / "scripts" / "ai" / "aq-feedback-loop",
    "aq-hints": REPO_ROOT / "scripts" / "ai" / "aq-hints",
    "aq-runtime": REPO_ROOT / "scripts" / "ai" / "aq-runtime",
}

# ── TOOL_CATALOG ─────────────────────────────────────────────────────────────
# Complete registry of ALL harness tool schemas keyed by tool name.
# NOT auto-injected into model context — use _select_tools_for_task() to pick
# 4-6 relevant schemas per call (progressive disclosure, ~200-300 tokens max).
#
# Catalog has 17 entries:
#   3 base tools (route_search, recall_memory, run_harness_cli)
#   14 AI coordination tools (mirrors ai_coordination.py register_ai_coordination_tools)
# ─────────────────────────────────────────────────────────────────────────────
TOOL_CATALOG: dict[str, dict] = {
    "route_search": {
        "type": "function",
        "function": {
            "name": "route_search",
            "description": "Search the codebase and project documentation for relevant context using semantic and keyword RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"},
                    "limit": {"type": "integer", "description": "Max results to return (1-10)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    "recall_memory": {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Recall prior agent context, solutions, or task outcomes from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Memory recall query"},
                },
                "required": ["query"],
            },
        },
    },
    "run_harness_cli": {
        "type": "function",
        "function": {
            "name": "run_harness_cli",
            "description": (
                "Run a sanctioned local harness CLI command for bounded health, memory, "
                "bootstrap, feedback-loop, report, or runtime workflows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": sorted(_ALLOWED_HARNESS_CLI_TOOLS.keys()),
                        "description": "Sanctioned aq-* CLI entrypoint to run.",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exact argv tokens after the tool name. No shell metacharacters.",
                        "default": [],
                    },
                },
                "required": ["tool"],
            },
        },
    },
    # ── AI coordination tools (14) ──────────────────────────────────────────
    "get_hint": {
        "type": "function",
        "function": {
            "name": "get_hint",
            "description": "Query the hints engine for relevant hints and guidance about the current task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query string"},
                    "max_hints": {"type": "integer", "description": "Maximum hints to return", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    "delegate_to_remote": {
        "type": "function",
        "function": {
            "name": "delegate_to_remote",
            "description": "Delegate a task to a remote agent (codex, claude, qwen, opencode) when escalation is needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                    "agent_type": {
                        "type": "string",
                        "description": "Agent type",
                        "enum": ["codex", "claude", "qwen", "opencode"],
                        "default": "codex",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Task priority",
                        "enum": ["low", "normal", "high"],
                        "default": "normal",
                    },
                },
                "required": ["task"],
            },
        },
    },
    "query_context": {
        "type": "function",
        "function": {
            "name": "query_context",
            "description": "Query context memory for relevant information about the current task or project state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query string"},
                    "max_results": {"type": "integer", "description": "Maximum results to return", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    "store_memory": {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": "Store information in agent memory using canonical memory tiers (episodic/semantic/procedural/working/error_solutions).",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "context_type": {
                        "type": "string",
                        "description": "Memory tier: episodic, semantic, procedural, working, error_solutions, interaction_history",
                        "enum": ["episodic", "semantic", "procedural", "working", "error_solutions", "interaction_history"],
                        "default": "semantic",
                    },
                    "importance": {"type": "number", "description": "Importance score (0.0-1.0)", "default": 0.5},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                },
                "required": ["content"],
            },
        },
    },
    "get_workflow_status": {
        "type": "function",
        "function": {
            "name": "get_workflow_status",
            "description": "Get status and progress of a running workflow by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                },
                "required": ["workflow_id"],
            },
        },
    },
    "run_opencode": {
        "type": "function",
        "function": {
            "name": "run_opencode",
            "description": "Invoke the opencode CLI coding agent for file-editing, refactoring, or code-generation tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Coding task description"},
                    "model": {"type": "string", "description": "Override model id (OpenRouter format, e.g. qwen/qwen3-235b-a22b:free)"},
                },
                "required": ["prompt"],
            },
        },
    },
    "harness_health": {
        "type": "function",
        "function": {
            "name": "harness_health",
            "description": "Run AI stack health checks (aq-qa). Returns status of all harness services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {"type": "string", "description": "QA phase to run (0-10)", "default": "0"},
                },
            },
        },
    },
    "get_prsi_pending": {
        "type": "function",
        "function": {
            "name": "get_prsi_pending",
            "description": "Get list of pending PRSI (Proactive Runtime Self-Improvement) optimization actions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "prsi_orchestrate": {
        "type": "function",
        "function": {
            "name": "prsi_orchestrate",
            "description": "Approve, reject, sync, or execute PRSI actions to manage runtime self-improvement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["approve", "reject", "sync", "execute"]},
                    "action_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["action"],
            },
        },
    },
    "recommend_agent_for_task": {
        "type": "function",
        "function": {
            "name": "recommend_agent_for_task",
            "description": "Get recommendation for the best agent to handle a task from the agent mesh.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Task description to match against agent capabilities"},
                },
                "required": ["query"],
            },
        },
    },
    "query_aidb": {
        "type": "function",
        "function": {
            "name": "query_aidb",
            "description": "Search the AI stack knowledge base (AIDB) using hybrid search for errors, solutions, and patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    "get_working_memory": {
        "type": "function",
        "function": {
            "name": "get_working_memory",
            "description": "Retrieve recent session facts and decisions from working memory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "mesh_discovery": {
        "type": "function",
        "function": {
            "name": "mesh_discovery",
            "description": "Discover active agents, teams, and capabilities in the agent mesh.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "collective_memory_search": {
        "type": "function",
        "function": {
            "name": "collective_memory_search",
            "description": "Search past agent collaborations and lessons learned in collective memory (AIDB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
}

# ── Phase A: TOOL_SCHEMAS — all 17 tools, ultra-minimal schemas (≤800t) ──────
# Each entry uses the shortest description that preserves intent (≤25 chars).
# Zero-arg tools omit the ``parameters`` key entirely to save tokens.
# Required-only params — optional params are stripped.
# Validated: len(json.dumps(TOOL_SCHEMAS)) / 4 ≤ 800.
# DO NOT add description, enum, or default fields — they push over budget.
def _T(name: str, desc: str, required_props: dict | None = None) -> dict:
    fn: dict = {"name": name, "description": desc}
    if required_props is not None:
        fn["parameters"] = {
            "type": "object",
            "properties": {k: {"type": v} for k, v in required_props.items()},
        }
        if required_props:
            fn["parameters"]["required"] = list(required_props.keys())
    return {"type": "function", "function": fn}


TOOL_SCHEMAS = [
    # ── 3 base tools ────────────────────────────────────────────────────────
    _T("route_search",              "RAG codebase search",      {"query": "string"}),
    _T("recall_memory",             "Recall past context",      {"query": "string"}),
    _T("run_harness_cli",           "Run aq-* CLI",             {"tool": "string"}),
    # ── 14 AI coordination tools ────────────────────────────────────────────
    _T("get_hint",                  "Get harness hint",         {"query": "string"}),
    _T("delegate_to_remote",        "Delegate to agent",        {"task": "string"}),
    _T("query_context",             "Query context mem",        {"query": "string"}),
    _T("store_memory",              "Store to memory",          {"content": "string"}),
    _T("get_workflow_status",       "Workflow status",          {"workflow_id": "string"}),
    _T("run_opencode",              "Run opencode agent",       {"prompt": "string"}),
    _T("harness_health",            "Run QA health"),
    _T("get_prsi_pending",          "List PRSI pending"),
    _T("prsi_orchestrate",          "Execute PRSI action",      {"action": "string"}),
    _T("recommend_agent_for_task",  "Recommend agent",          {"query": "string"}),
    _T("query_aidb",                "Search AIDB",              {"query": "string"}),
    _T("get_working_memory",        "Get working memory"),
    _T("mesh_discovery",            "Discover agents"),
    _T("collective_memory_search",  "Search collab history",    {"query": "string"}),
]

# ── Keyword sets for task-aware tool selection ────────────────────────────────
_TOOL_SELECT_SEARCH_KW = frozenset(["search", "find", "look", "locate", "where", "which", "what is"])
_TOOL_SELECT_MEMORY_KW = frozenset(["remember", "store", "save", "record", "note", "memorize", "persist"])
_TOOL_SELECT_RECALL_KW = frozenset(["recall", "retrieve", "past", "previous", "history", "prior"])
_TOOL_SELECT_HINT_KW = frozenset(["hint", "suggest", "help", "guidance", "recommend", "advice", "how to"])
_TOOL_SELECT_HEALTH_KW = frozenset(["health", "status", "check", "verify", "diagnose", "monitor", "running", "alive"])
_TOOL_SELECT_DELEGATE_KW = frozenset(["delegate", "remote", "escalate", "assign", "handoff", "codex", "claude", "opencode"])
_TOOL_SELECT_MESH_KW = frozenset(["mesh", "agents", "discover", "team", "capabilities", "federated", "who can"])
_TOOL_SELECT_MEMORY_WRITE_KW = frozenset(["working memory", "session", "scratch", "current state", "active", "get memory"])
_TOOL_SELECT_WORKFLOW_KW = frozenset(["workflow", "pipeline", "prsi", "self-improve", "optimization"])
_TOOL_SELECT_AIDB_KW = frozenset(["aidb", "knowledge base", "error pattern", "solution", "bug", "fix", "pattern"])


def _slim_schema(schema: dict) -> dict:
    """Return a token-minimal copy of an OpenAI function schema for model context.

    Aggressively strips to fit n_ctx=8192 budget (target: ≤70 chars/schema):
    - Truncates function description to 60 chars
    - Strips all parameter-level ``description`` fields
    - Strips ``enum`` arrays (too verbose; model infers valid values from name)
    - Strips ``default`` values
    - Keeps ``type``, ``items``, and ``required`` — minimum for correct calling
    """
    import copy
    s = copy.deepcopy(schema)
    fn = s.get("function", {})
    # Truncate top-level description hard
    if "description" in fn:
        fn["description"] = fn["description"][:60]
    # Strip per-property noise
    params = fn.get("parameters", {})
    for _prop in params.get("properties", {}).values():
        _prop.pop("description", None)
        _prop.pop("enum", None)
        _prop.pop("default", None)
    return s


def _select_tools_for_task(task_description: str) -> list[dict]:
    """Select 4-6 relevant tool schemas from TOOL_CATALOG for a given task.

    Progressive disclosure strategy:
    - Always include route_search + recall_memory (core harness access)
    - Classify task keywords → add up to 4 more relevant tools
    - Cap at 6 tools total (~200-300 tokens when slimmed)
    - General/unclassified tasks: get_hint + query_aidb + store_memory + run_harness_cli
    - Returns slim schemas (descriptions stripped) to respect n_ctx=8192 budget
    """
    task_lower = task_description.lower()

    # Always-present base tools (2)
    selected: list[str] = ["route_search", "recall_memory"]

    # Scored candidate pools — collect by category match, then cap
    candidates: list[str] = []

    if any(k in task_lower for k in _TOOL_SELECT_SEARCH_KW):
        candidates.extend(["query_aidb", "collective_memory_search"])
    if any(k in task_lower for k in _TOOL_SELECT_AIDB_KW):
        candidates.append("query_aidb")
    if any(k in task_lower for k in _TOOL_SELECT_MEMORY_KW):
        candidates.extend(["store_memory", "get_working_memory"])
    if any(k in task_lower for k in _TOOL_SELECT_RECALL_KW):
        candidates.append("get_working_memory")
    if any(k in task_lower for k in _TOOL_SELECT_HINT_KW):
        candidates.extend(["get_hint", "query_context"])
    if any(k in task_lower for k in _TOOL_SELECT_HEALTH_KW):
        candidates.extend(["harness_health", "get_workflow_status"])
    if any(k in task_lower for k in _TOOL_SELECT_DELEGATE_KW):
        candidates.append("delegate_to_remote")
    if any(k in task_lower for k in _TOOL_SELECT_MESH_KW):
        candidates.extend(["mesh_discovery", "recommend_agent_for_task"])
    if any(k in task_lower for k in _TOOL_SELECT_MEMORY_WRITE_KW):
        candidates.append("get_working_memory")
    if any(k in task_lower for k in _TOOL_SELECT_WORKFLOW_KW):
        candidates.extend(["get_workflow_status", "get_prsi_pending"])

    # Deduplicate preserving first-seen order
    seen: set[str] = set(selected)
    for name in candidates:
        if name not in seen:
            selected.append(name)
            seen.add(name)

    # Fallback: no keyword match → general-purpose set
    if len(selected) == 2:
        selected.extend(["get_hint", "query_aidb", "store_memory", "run_harness_cli"])
    else:
        # Always include run_harness_cli for CLI access if budget allows
        if "run_harness_cli" not in seen and len(selected) < 5:
            selected.append("run_harness_cli")

    # Cap at 5 tools (slim schemas at ~80 chars each ≈ 400 tok for 5 tools)
    selected = selected[:5]

    return [_slim_schema(TOOL_CATALOG[name]) for name in selected if name in TOOL_CATALOG]


def _refresh_tools_from_result(
    tool_name: str,
    result_text: str,
    current_tools: list[dict],
    max_tools: int = 6,
) -> list[dict]:
    """Hot-swap active tool set based on tool result content.

    Monotonic expansion: never removes already-selected tools.
    Reads from TOOL_CATALOG — catalog is always complete.
    _slim_schema() keeps each addition ~50 tokens (cheap swap).
    """
    current_names = {t["function"]["name"] for t in current_tools}
    result_lower = result_text.lower()
    additions: list[str] = []

    if any(k in result_lower for k in _TOOL_SELECT_MEMORY_KW) and "store_memory" not in current_names:
        additions.append("store_memory")
    if any(k in result_lower for k in _TOOL_SELECT_WORKFLOW_KW) and "get_workflow_status" not in current_names:
        additions.extend(["get_workflow_status", "prsi_orchestrate"])
    if any(k in result_lower for k in _TOOL_SELECT_DELEGATE_KW) and "delegate_to_remote" not in current_names:
        additions.append("delegate_to_remote")
    if any(k in result_lower for k in _TOOL_SELECT_HEALTH_KW) and "harness_health" not in current_names:
        additions.append("harness_health")
    if any(k in result_lower for k in _TOOL_SELECT_MESH_KW) and "mesh_discovery" not in current_names:
        additions.append("mesh_discovery")

    result_tools = list(current_tools)
    for name in additions:
        if len(result_tools) >= max_tools:
            break
        if name in TOOL_CATALOG:
            result_tools.append(_slim_schema(TOOL_CATALOG[name]))
    return result_tools


def _profile_for_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    # Always use continue-local when spawned as a subprocess (TOOLS_ENABLED=False).
    # "local-tool-calling" in switchboard routes to _execute_local_tool_calling which
    # expects built-in server tools, not subprocess agent tool schemas — causes 400
    # which holds _local_sem and blocks all local inference for ~210s.
    _ = normalized
    return "continue-local"


def _write_state(state: dict) -> None:
    if STATE_FILE:
        p = pathlib.Path(STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))


async def _post_agent_event(
    client: httpx.AsyncClient,
    *,
    event_type: str,
    sub_type: str,
    outcome: str = "success",
    summary: str = "",
    latency_ms: int = 0,
    tags: list[str] | None = None,
) -> None:
    payload = {
        "event_type": event_type,
        "sub_type": sub_type,
        "agent": "local",
        "outcome": outcome,
        "summary": summary[:400],
        "task_id": AGENT_ID,
        "latency_ms": int(max(0, latency_ms)),
        "tags": tags or ["local_agent_runtime"],
    }
    try:
        await client.post(f"{HYBRID_URL}/api/agent-events", json=payload, timeout=5.0)
    except Exception as exc:
        logger.debug("agent_event_post_failed event_type=%s sub_type=%s err=%s", event_type, sub_type, exc)


def _build_inference_payload(messages: list[dict], selected_tools: list[dict] | None = None) -> dict:
    extra: dict = {"stop": STOP_SEQUENCES}
    if TOOLS_ENABLED:
        # Use caller-provided progressive selection; fall back to base 3-tool set
        tools = selected_tools if selected_tools is not None else TOOL_SCHEMAS
        extra["tools"] = tools
        extra["tool_choice"] = "auto"
    # Pass explicit temperature only when caller set AGENT_TEMPERATURE; otherwise
    # let the task profile's temperature take effect via build_llama_payload().
    if TEMPERATURE is not None:
        extra["temperature"] = TEMPERATURE
    return build_llama_payload(
        messages,
        max_tokens=MAX_TOKENS,
        task_type=AGENT_TASK_TYPE,
        **extra,
    )


def _resolve_bash_binary() -> str:
    candidates = [
        os.environ.get("BASH"),
        shutil.which("bash"),
        "/run/current-system/sw/bin/bash",
        "/bin/bash",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("bash binary not found for local harness CLI execution")


def _resolve_python3_binary() -> str:
    candidates = [
        os.environ.get("PYTHON3"),
        shutil.which("python3"),
        "/run/current-system/sw/bin/python3",
        "/usr/bin/python3",
        "/bin/python3",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("python3 binary not found for local harness CLI execution")


def _build_cli_exec_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    home = pathlib.Path(env.get("HOME") or str(REPO_ROOT))
    bash_bin = _resolve_bash_binary()
    python3_bin = _resolve_python3_binary()
    path_entries = [
        str(pathlib.Path(bash_bin).parent),
        str(pathlib.Path(python3_bin).parent),
        str(home / ".nix-profile" / "bin"),
        str(home / ".npm-global" / "bin"),
        str(home / ".local" / "bin"),
        str(home / ".cargo" / "bin"),
        "/run/current-system/sw/bin",
        "/usr/bin",
        "/bin",
    ]
    existing_path = env.get("PATH", "")
    if existing_path:
        path_entries.extend(segment for segment in existing_path.split(":") if segment)
    env["PATH"] = ":".join(dict.fromkeys(path_entries))
    env.setdefault("BASH", bash_bin)
    env.setdefault("PYTHON3", python3_bin)
    return env


def _validate_arg_tokens(args: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in args:
        value = str(raw)
        if not value:
            continue
        if len(value) > 512:
            raise ValueError("harness CLI argument too long")
        if any(ch in value for ch in _ARG_BLOCKLIST_CHARS):
            raise ValueError(f"unsafe harness CLI argument: {value}")
        normalized.append(value)
    return normalized


def _validate_harness_cli(tool: str, args: list[str]) -> tuple[list[str], float]:
    normalized = _validate_arg_tokens(args)
    if tool == "aq-qa":
        if not normalized:
            return ["0", "--json"], 90.0
        phase = normalized[0]
        if phase not in _AQ_QA_PHASES:
            raise ValueError(f"unsupported aq-qa phase: {phase}")
        for flag in normalized[1:]:
            if flag not in {"--json", "--sudo"}:
                raise ValueError(f"unsupported aq-qa flag: {flag}")
        return normalized, 180.0 if phase in {"2", "3", "all"} else 90.0
    if tool == "aq-report":
        if not normalized:
            return ["--format=json"], 90.0
        i = 0
        while i < len(normalized):
            token = normalized[i]
            if token.startswith("--since="):
                i += 1
                continue
            if token == "--since":
                if i + 1 >= len(normalized):
                    raise ValueError("aq-report --since requires a value")
                i += 2
                continue
            if token in {"--format=json", "--format=text"}:
                i += 1
                continue
            raise ValueError(f"unsupported aq-report argument: {token}")
        return normalized, 90.0
    if tool == "aq-operational-perspective":
        i = 0
        while i < len(normalized):
            token = normalized[i]
            if token == "--task" and i + 1 < len(normalized):
                i += 2
                continue
            if token in {"--since", "--format", "--memory-limit"} and i + 1 < len(normalized):
                i += 2
                continue
            if token.startswith("--since=") or token.startswith("--format=") or token.startswith("--memory-limit="):
                i += 1
                continue
            raise ValueError(f"unsupported aq-operational-perspective argument: {token}")
        return normalized, 120.0
    if tool == "aq-introspection-validate":
        if not normalized:
            raise ValueError("aq-introspection-validate requires --file <path> or --text <text>")
        i = 0
        saw_source = False
        while i < len(normalized):
            token = normalized[i]
            if token in {"--file", "--text", "--format"} and i + 1 < len(normalized):
                if token in {"--file", "--text"}:
                    saw_source = True
                i += 2
                continue
            if token.startswith("--format="):
                i += 1
                continue
            raise ValueError(f"unsupported aq-introspection-validate argument: {token}")
        if not saw_source:
            raise ValueError("aq-introspection-validate requires --file <path> or --text <text>")
        return normalized, 30.0
    if tool == "aq-memory":
        if len(normalized) < 2 or normalized[0] != "search":
            raise ValueError("aq-memory currently only supports: search <query> [--project <name>] [--limit <n>]")
        i = 2
        while i < len(normalized):
            token = normalized[i]
            if token == "--project" and i + 1 < len(normalized):
                i += 2
                continue
            if token == "--limit" and i + 1 < len(normalized):
                i += 2
                continue
            raise ValueError(f"unsupported aq-memory argument: {token}")
        return normalized, 60.0
    if tool == "aq-context-manage":
        if not normalized or normalized[0] not in {"check", "summary", "checkpoint"}:
            raise ValueError("aq-context-manage requires one of: check, summary, checkpoint")
        command = normalized[0]
        if command == "check":
            for token in normalized[1:]:
                if token != "--json":
                    raise ValueError(f"unsupported aq-context-manage check argument: {token}")
            return normalized, 60.0
        if "--task" not in normalized:
            raise ValueError(f"aq-context-manage {command} requires --task <value>")
        i = 1
        while i < len(normalized):
            token = normalized[i]
            if token == "--task" and i + 1 < len(normalized):
                i += 2
                continue
            if token in {"--json", "--force"}:
                i += 1
                continue
            if token in {"--project", "--topic", "--resume-query", "--limit", "--created-by", "--agent-owner", "--memory-storage"} and i + 1 < len(normalized):
                i += 2
                continue
            if token in {"--fact", "--decision", "--next-step", "--open-question", "--tags"} and i + 1 < len(normalized):
                i += 2
                continue
            raise ValueError(f"unsupported aq-context-manage argument: {token}")
        return normalized, 90.0
    if tool in {"aq-context-bootstrap", "aq-feedback-loop"}:
        if "--task" not in normalized:
            raise ValueError(f"{tool} requires --task <value>")
        i = 0
        while i < len(normalized):
            token = normalized[i]
            if token == "--task" and i + 1 < len(normalized):
                i += 2
                continue
            if token in {"--format", "--prd-path", "--plan-path", "--feedback-file"} and i + 1 < len(normalized):
                i += 2
                continue
            if token.startswith("--format="):
                i += 1
                continue
            raise ValueError(f"unsupported {tool} argument: {token}")
        return normalized, 90.0
    if tool == "aq-hints":
        i = 0
        while i < len(normalized):
            token = normalized[i]
            if not token.startswith("--") and i == 0:
                i += 1
                continue
            if token in {"--format", "--context", "--max", "--agent"} and i + 1 < len(normalized):
                i += 2
                continue
            if token.startswith("--format=") or token.startswith("--context=") or token.startswith("--max=") or token.startswith("--agent="):
                i += 1
                continue
            raise ValueError(f"unsupported aq-hints argument: {token}")
        return normalized, 60.0
    if tool == "aq-runtime":
        if not normalized or normalized[0] not in {"diagnose", "plan", "act", "remediate"}:
            raise ValueError("aq-runtime requires one of: diagnose, plan, act, remediate")
        return normalized, 180.0
    raise ValueError(f"unsupported harness CLI tool: {tool}")


async def _run_harness_cli(tool: str, args: list[str]) -> str:
    script = _ALLOWED_HARNESS_CLI_TOOLS.get(tool)
    if script is None or not script.exists():
        raise FileNotFoundError(f"sanctioned harness CLI not found: {tool}")
    validated_args, timeout_seconds = _validate_harness_cli(tool, args)
    proc = await asyncio.create_subprocess_exec(
        str(script),
        *validated_args,
        cwd=str(REPO_ROOT),
        env=_build_cli_exec_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return json.dumps({
            "tool": tool,
            "args": validated_args,
            "status": "error",
            "error": f"timeout after {timeout_seconds}s",
        })
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    payload: dict[str, object] = {
        "tool": tool,
        "args": validated_args,
        "status": "ok" if proc.returncode == 0 else "failed",
        "exit_code": int(proc.returncode),
        "stdout": stdout_text,
    }
    if stderr_text:
        payload["stderr"] = stderr_text
    if stdout_text.startswith("{") or stdout_text.startswith("["):
        try:
            payload["parsed"] = json.loads(stdout_text)
        except Exception:
            pass
    return json.dumps(payload)


def _payload_for_direct_llama(payload: dict) -> dict:
    sanitized = dict(payload)
    sanitized.pop("tools", None)
    sanitized.pop("tool_choice", None)
    return sanitized


async def _wait_for_llama_slot(
    client: httpx.AsyncClient,
    timeout: float = AGENT_TIMEOUT,
    poll_interval: float = 3.0,
) -> None:
    """Poll llama.cpp /health until a slot is available or timeout is reached."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            r = await client.get(f"{LLAMA_CPP_URL}/health", timeout=5.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        await asyncio.sleep(poll_interval)


async def _post_completion_with_fallback(
    client: httpx.AsyncClient,
    *,
    payload: dict,
    headers: dict,
    state: dict,
) -> httpx.Response:
    inference_url = f"{SWITCHBOARD_URL}/v1/chat/completions"
    start_time = time.perf_counter()
    
    # Phase 2026.06: Increased handshake resilience for edge AI
    # Retry once for transient connection/read issues on slow cold-starts
    for attempt in range(2):
        try:
            # Use a longer connect timeout for the initial handshake
            resp = await client.post(
                inference_url, 
                json=payload, 
                headers=headers,
                timeout=httpx.Timeout(AGENT_TIMEOUT, connect=30.0)
            )
            state["inference_latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return resp
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            if attempt == 0:
                logger.warning(f"Inference handshake attempt 1 failed ({exc}), retrying...")
                await asyncio.sleep(2.0)
                continue
                
            # Phase 175-B: fail cleanly rather than bypassing switchboard.
            # Direct llama.cpp fallback silently skips telemetry, circuit breakers,
            # and hint injection. Raise so the coordinator marks the task failed.
            state["fallback_backend"] = "none"
            state["fallback_reason"] = f"switchboard_unavailable: {type(exc).__name__}"
            _write_state(state)
            raise RuntimeError(
                f"switchboard_unavailable: {exc}. "
                "Refusing direct llama.cpp fallback to preserve telemetry and circuit-breaker integrity."
            )
    
    # Should not reach here
    raise RuntimeError("Inference delivery failed after all attempts")


def _streaming_payload(messages: list[dict]) -> dict:
    kwargs: dict = {}
    if TEMPERATURE is not None:
        kwargs["temperature"] = TEMPERATURE
    return build_llama_payload(
        messages,
        max_tokens=MAX_TOKENS,
        task_type=AGENT_TASK_TYPE,
        stream=True,
        stop=STOP_SEQUENCES,
        **kwargs,
    )


def _compress_tool_output(output: str, max_chars: int = TOOL_OUTPUT_MAX_CHARS) -> str:
    """Trim tool output to max_chars, appending a truncation notice if needed."""
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    return output[:half] + f"\n...[truncated {len(output) - max_chars} chars]...\n" + output[-half:]


async def _dispatch_tool(client: httpx.AsyncClient, name: str, args: dict) -> str:
    """Execute a harness tool call and return a plaintext result string."""
    try:
        if name == "route_search":
            query = str(args.get("query", "")).strip()
            limit = max(1, min(10, int(args.get("limit", 5))))
            r = await client.post(
                f"{HYBRID_URL}/query",
                json={
                    "query": query,
                    "mode": "retrieval_only",
                    "limit": limit,
                    "prefer_local": True,
                },
                timeout=30.0,
            )
            if r.status_code == 200:
                results = r.json().get("results") or []
                if results:
                    return _compress_tool_output("\n".join(
                        f"[{i+1}] {res.get('content', '')[:400]}"
                        for i, res in enumerate(results[:limit])
                    ))
                return "No results found."
            return f"route_search error: HTTP {r.status_code}"
        elif name == "recall_memory":
            query = str(args.get("query", "")).strip()
            r = await client.post(
                f"{HYBRID_URL}/query",
                json={"query": query, "mode": "memory_only", "limit": 5, "prefer_local": True},
                timeout=30.0,
            )
            if r.status_code == 200:
                results = r.json().get("results") or []
                if results:
                    return _compress_tool_output("\n".join(
                        f"[{i+1}] {res.get('content', '')[:400]}"
                        for i, res in enumerate(results[:5])
                    ))
                return "No memories found."
            return f"recall_memory error: HTTP {r.status_code}"
        elif name == "run_harness_cli":
            tool = str(args.get("tool", "")).strip()
            tool_args = args.get("args") or []
            if not isinstance(tool_args, list):
                return json.dumps({
                    "tool": tool,
                    "status": "error",
                    "error": "args must be a list of strings",
                })
            return _compress_tool_output(await _run_harness_cli(tool, [str(item) for item in tool_args]))
        # ── A.4: AI coordination tool dispatch handlers ────────────────────────
        elif name == "get_hint":
            query = str(args.get("query", "")).strip()
            max_hints = max(1, min(20, int(args.get("max_hints", 5))))
            r = await client.get(
                f"{HYBRID_URL}/hints",
                params={"q": query, "max": max_hints},
                timeout=15.0,
            )
            if r.status_code == 200:
                data = r.json()
                hints = data.get("hints") or []
                if hints:
                    return _compress_tool_output("\n".join(f"- {h}" for h in hints[:max_hints]))
                return "No hints found."
            return f"get_hint error: HTTP {r.status_code}"
        elif name == "delegate_to_remote":
            task_text = str(args.get("task", "")).strip()
            agent_type = str(args.get("agent_type", "codex"))
            priority = str(args.get("priority", "normal"))
            r = await client.post(
                f"{HYBRID_URL}/query",
                json={"query": task_text, "agent_type": agent_type, "context": {"priority": priority}},
                timeout=45.0,
            )
            if r.status_code == 200:
                data = r.json()
                return _compress_tool_output(json.dumps({
                    "agent": agent_type,
                    "response": data.get("response", ""),
                }))
            return f"delegate_to_remote error: HTTP {r.status_code}"
        elif name == "query_context":
            query = str(args.get("query", "")).strip()
            max_results = max(1, min(20, int(args.get("max_results", 10))))
            r = await client.post(
                f"{HYBRID_URL}/query",
                json={"query": query, "mode": "context_only", "limit": max_results, "prefer_local": True},
                timeout=20.0,
            )
            if r.status_code == 200:
                results = r.json().get("results") or []
                if results:
                    return _compress_tool_output("\n".join(
                        f"[{i+1}] {res.get('content', '')[:400]}"
                        for i, res in enumerate(results[:max_results])
                    ))
                return "No context found."
            return f"query_context error: HTTP {r.status_code}"
        elif name == "store_memory":
            content_val = str(args.get("content", "")).strip()
            context_type = str(args.get("context_type", "semantic"))
            importance = float(args.get("importance", 0.5))
            tags = list(args.get("tags") or [])
            # F.1 — auto-inject agent identity so stored memories are task-scoped
            # and recoverable by the same agent on future get_working_memory calls.
            _agent_tag = f"agent:{AGENT_ID}"
            if _agent_tag not in tags:
                tags.append(_agent_tag)
            r = await client.post(
                f"{HYBRID_URL}/memory/store",
                json={
                    "content": content_val,
                    "memory_type": context_type,
                    "importance": max(0.0, min(1.0, importance)),
                    "tags": tags if isinstance(tags, list) else [],
                    "source": "local-agent",
                },
                timeout=15.0,
            )
            if r.status_code == 200:
                return json.dumps(r.json())
            return f"store_memory error: HTTP {r.status_code}"
        elif name == "get_workflow_status":
            workflow_id = str(args.get("workflow_id", "")).strip()
            r = await client.get(
                f"{HYBRID_URL}/workflow/orchestrate/{workflow_id}",
                timeout=10.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"get_workflow_status error: HTTP {r.status_code}"
        elif name == "run_opencode":
            # run_opencode requires subprocess — proxy through harness_health path
            # (opencode not available in this subprocess context; return descriptive error)
            prompt = str(args.get("prompt", "")).strip()
            return json.dumps({
                "success": False,
                "error": "run_opencode not available in local_agent_runtime subprocess context. "
                         "Use delegate_to_remote with agent_type='opencode' instead.",
                "prompt_received": prompt[:100],
            })
        elif name == "harness_health":
            phase = str(args.get("phase", "0"))
            r = await client.post(
                f"{HYBRID_URL}/qa/check",
                json={"phase": phase},
                timeout=90.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"harness_health error: HTTP {r.status_code}"
        elif name == "get_prsi_pending":
            r = await client.get(
                f"{HYBRID_URL}/control/prsi/pending",
                timeout=10.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"get_prsi_pending error: HTTP {r.status_code}"
        elif name == "prsi_orchestrate":
            action = str(args.get("action", "")).strip()
            payload_data: dict = {"action": action}
            if args.get("action_id"):
                payload_data["action_id"] = str(args["action_id"])
            if args.get("note"):
                payload_data["note"] = str(args["note"])
            if action == "execute":
                r = await client.post(
                    f"{HYBRID_URL}/control/prsi/actions/execute",
                    json=payload_data,
                    timeout=30.0,
                )
            else:
                r = await client.get(
                    f"{HYBRID_URL}/control/prsi/actions",
                    params=payload_data,
                    timeout=15.0,
                )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"prsi_orchestrate error: HTTP {r.status_code}"
        elif name == "recommend_agent_for_task":
            # /federated/recommend is not registered; use /control/agents mesh status
            # which returns active_agents, total_agents, and instances as best proxy.
            r = await client.get(
                f"{HYBRID_URL}/control/agents",
                timeout=15.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"recommend_agent_for_task error: HTTP {r.status_code}"
        elif name == "query_aidb":
            query = str(args.get("query", "")).strip()
            limit = max(1, min(20, int(args.get("limit", 5))))
            r = await client.post(
                f"{HYBRID_URL}/search/tree",
                json={"query": query, "limit": limit},
                timeout=20.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"query_aidb error: HTTP {r.status_code}"
        elif name == "get_working_memory":
            r = await client.post(
                f"{HYBRID_URL}/memory/recall",
                json={"query": "working memory summary", "memory_types": ["semantic"]},
                timeout=15.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"get_working_memory error: HTTP {r.status_code}"
        elif name == "mesh_discovery":
            r = await client.get(
                f"{HYBRID_URL}/discovery/capabilities",
                timeout=10.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"mesh_discovery error: HTTP {r.status_code}"
        elif name == "collective_memory_search":
            query = str(args.get("query", "")).strip()
            limit = max(1, min(20, int(args.get("limit", 5))))
            aidb_url = os.environ.get("AIDB_URL", "http://127.0.0.1:8002")
            r = await client.post(
                f"{aidb_url}/vector/search",
                json={"query": query, "collection": "knowledge", "limit": limit},
                timeout=15.0,
            )
            if r.status_code == 200:
                return _compress_tool_output(json.dumps(r.json()))
            return f"collective_memory_search error: HTTP {r.status_code}"
        return f"unknown_tool: {name}"
    except Exception as exc:
        return f"tool_error({name}): {exc}"


def _run_bootstrap_preamble(task: str) -> str:
    """Run aq-context-bootstrap and return a compact preamble, or '' on any failure."""
    script = REPO_ROOT / "scripts" / "ai" / "aq-context-bootstrap"
    if not script.exists():
        return ""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script), "--task", task, "--format", "json"],
            capture_output=True, text=True, timeout=BOOTSTRAP_TIMEOUT,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        data = json.loads(result.stdout)
        scope = data.get("scope", "")
        cards = (data.get("recommended_cards") or [])[:3]
        preflight = (data.get("preflight_commands") or data.get("continuation_startup_commands") or [])[:1]
        parts = []
        if scope:
            parts.append(f"scope={scope}")
        if cards:
            parts.append(f"cards={','.join(cards)}")
        if preflight:
            parts.append(f"preflight={preflight[0]}")
        return "[bootstrap] " + " | ".join(parts) if parts else ""
    except Exception:
        return ""


async def run() -> None:
    state: dict = {
        "id": AGENT_ID,
        "role": AGENT_ROLE,
        "status": "running",
        "started_at": time.time(),
        "tool_calls": 0,
    }
    _write_state(state)
    try:
        task_content = AGENT_TASK
        if NO_THINK_PREFIX and not task_content.startswith(NO_THINK_PREFIX_STR):
            task_content = NO_THINK_PREFIX_STR + " " + task_content
        
        if AGENT_INJECT_BOOTSTRAP:
            _preamble = _run_bootstrap_preamble(AGENT_TASK)
            _sys = SYSTEM_PROMPT + ("\n\n[STARTUP CONTEXT] " + _preamble if _preamble else "")
        else:
            _sys = SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": _sys},
            {"role": "user", "content": task_content},
        ]
        # "local-tool-calling" profile intercepts the tools array against its built-in
        # server registry, causing 400 for agent-runtime tools (route_search, recall_memory,
        # get_hint, etc. are not switchboard built-ins). Use "local-agent" which has
        # toolExecution: None — passes tools through to llama.cpp, agent dispatches itself.
        profile = "local-agent" if TOOLS_ENABLED else _profile_for_role(AGENT_ROLE)
        headers = {"X-AI-Profile": profile, "X-AI-Route": "local"}
        content = ""
        data: dict = {}

        # A.3 — Progressive tool disclosure: select 4-6 relevant schemas for this task.
        # Only computed when tools are enabled; avoids any overhead for non-tool invocations.
        # A.6 — _active_tools tracks the live set; expanded per-iteration via _refresh_tools_from_result.
        _selected_tools: list[dict] | None = _select_tools_for_task(AGENT_TASK) if TOOLS_ENABLED else None
        _active_tools: list[dict] | None = list(_selected_tools) if _selected_tools is not None else None

        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            await _post_agent_event(
                client,
                event_type="delegation_start",
                sub_type="local_agent_runtime",
                summary=AGENT_TASK,
                tags=["local_agent_runtime", "tools_enabled" if TOOLS_ENABLED else "tool_free"],
            )
            if STREAMING_MODE:
                content_parts = []
                stream_payload = _streaming_payload(messages)
                stream_url = f"{SWITCHBOARD_URL}/v1/chat/completions"
                stream_headers = headers
                try:
                    stream_ctx = client.stream(
                        "POST",
                        stream_url,
                        json=stream_payload,
                        headers=stream_headers,
                    )
                    sresp = await stream_ctx.__aenter__()
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    state["fallback_backend"] = "llama.cpp"
                    state["fallback_reason"] = "switchboard_unreachable"
                    _write_state(state)
                    stream_url = f"{LLAMA_CPP_URL}/v1/chat/completions"
                    stream_headers = {}
                    stream_ctx = client.stream(
                        "POST",
                        stream_url,
                        json=_payload_for_direct_llama(stream_payload),
                        headers=stream_headers,
                    )
                    sresp = await stream_ctx.__aenter__()
                try:
                    sresp.raise_for_status()
                    async for raw_line in sresp.aiter_lines():
                        raw_line = raw_line.strip()
                        if not raw_line or raw_line == ":":
                            continue
                        line = raw_line[6:] if raw_line.startswith("data: ") else raw_line
                        if line == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                            piece = (
                                (chunk.get("choices") or [{}])[0]
                                .get("delta", {})
                                .get("content") or ""
                            )
                            if piece:
                                content_parts.append(piece)
                                sys.stdout.write(json.dumps({"t": piece, "done": False}) + "\n")
                                sys.stdout.flush()
                        except Exception:
                            pass
                finally:
                    await stream_ctx.__aexit__(None, None, None)
                content = "".join(content_parts)
                state.update({
                    "status": "completed",
                    "result": content,
                    "completed_at": time.time(),
                    "finish_reason": "stop",
                })
                _write_state(state)
                await _post_agent_event(
                    client,
                    event_type="delegation_end",
                    sub_type="local_agent_runtime",
                    summary=content,
                    latency_ms=int((state["completed_at"] - state["started_at"]) * 1000),
                    tags=["local_agent_runtime", "streaming"],
                )
                sys.stdout.write(
                    json.dumps({"done": True, "ok": True, "content": content, "agent_id": AGENT_ID})
                    + "\n"
                )
                sys.stdout.flush()
                return

            _round = 0
            _recent_tool_results: list[tuple[str, str]] = []
            while True:
                resp = await _post_completion_with_fallback(
                    client,
                    payload=_build_inference_payload(messages, selected_tools=_active_tools),
                    headers=headers,
                    state=state,
                )
                if resp.status_code == 503:
                    try:
                        err_body = resp.json()
                    except Exception:
                        err_body = {}
                    if (err_body.get("error") or {}).get("type") == "local_slot_busy":
                        # Wait for a free slot then retry this round instead of failing.
                        await _wait_for_llama_slot(client)
                        continue
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    content = (msg.get("content") or "").strip()
                    if not content:
                        content = (msg.get("reasoning_content") or "").strip()
                    break
                _round += 1
                assistant_turn: dict = {"role": "assistant"}
                if msg.get("content"):
                    assistant_turn["content"] = msg["content"]
                assistant_turn["tool_calls"] = tool_calls
                messages.append(assistant_turn)
                for tc in tool_calls:
                    tc_id = tc.get("id", f"call_{_round}")
                    tc_name = (tc.get("function") or {}).get("name", "")
                    try:
                        tc_args = json.loads((tc.get("function") or {}).get("arguments", "{}"))
                    except Exception:
                        tc_args = {}
                    tc_result = await _dispatch_tool(client, tc_name, tc_args)
                    await _post_agent_event(
                        client,
                        event_type="workflow",
                        sub_type="tool_call",
                        summary=f"{tc_name}: {tc_result[:240]}",
                        tags=["local_agent_runtime", "tool_call", tc_name[:64]],
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": tc_result,
                    })
                    state["tool_calls"] += 1
                    _write_state(state)
                    _recent_tool_results.append((tc_name, tc_result[:200]))
                    if len(_recent_tool_results) > 5:
                        _recent_tool_results.pop(0)
                    if (
                        len(_recent_tool_results) == 5
                        and len({name for name, _ in _recent_tool_results}) == 1
                        and len({result for _, result in _recent_tool_results}) == 1
                    ):
                        content = (
                            f"Stagnation detected: '{tc_name}' returned the same result "
                            "five consecutive times; loop stopped by progress guard."
                        )
                        break
                    # A.6 — hot-swap: expand active tool set based on what the result reveals.
                    if _active_tools is not None:
                        _active_tools = _refresh_tools_from_result(tc_name, tc_result, _active_tools)
                if content:
                    break

        state.update({
            "status": "completed",
            "result": content,
            "completed_at": time.time(),
            "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason", "stop"),
        })
        _write_state(state)
        async with httpx.AsyncClient(timeout=5.0) as event_client:
            await _post_agent_event(
                event_client,
                event_type="delegation_end",
                sub_type="local_agent_runtime",
                summary=content,
                latency_ms=int((state["completed_at"] - state["started_at"]) * 1000),
                tags=["local_agent_runtime", "tools_enabled" if TOOLS_ENABLED else "tool_free"],
            )
        print(json.dumps({"ok": True, "content": content, "agent_id": AGENT_ID}))

    except Exception as exc:
        error_text = str(exc)
        if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)) or not error_text:
            error_text = "local_agent_timeout"
        state.update({"status": "failed", "error": error_text, "completed_at": time.time()})
        _write_state(state)
        async with httpx.AsyncClient(timeout=5.0) as event_client:
            await _post_agent_event(
                event_client,
                event_type="delegation_end",
                sub_type="local_agent_runtime",
                outcome="failure",
                summary=error_text,
                latency_ms=int((state["completed_at"] - state["started_at"]) * 1000),
                tags=["local_agent_runtime", "error"],
            )
        print(
            json.dumps({"ok": False, "error": error_text, "agent_id": AGENT_ID}),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
