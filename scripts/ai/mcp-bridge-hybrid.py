#!/usr/bin/env python3
"""
MCP stdio bridge for hybrid-coordinator REST API.
Translates MCP protocol (stdin/stdout) to hybrid-coordinator HTTP calls.
Used by Continue.dev and other MCP stdio clients.

Tools exposed:
  - hybrid_search: semantic search + optional LLM synthesis
  - get_hints: workflow hints for current task
  - workflow_plan: create phased plan using hybrid harness
  - tooling_manifest: compact code-execution-friendly tool manifest
  - workflow_run_start: start guarded workflow run with intent_contract
  - workflow_blueprints: fetch available workflow blueprints
  - aqd_workflows_list: list local AQD workflow catalog
  - project_init_workflow: run guided /project-init workflow
  - primer_workflow: run read-only /primer workflow
  - brownfield_workflow: run guided /brownfield workflow
  - retrofit_workflow: seed/refresh AI layer in an existing repo
  - bootstrap_agent_project: generate starter AI layer in a target repo
  - store_memory: store agent memory
  - recall_memory: retrieve agent memory
  - query_aidb: search AIDB knowledge base
"""
import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

# SafeCommandExecutor — block destructive agent commands at the subprocess level
try:
    _SCE_DIR = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "ai-stack", "mcp-servers", "hybrid-coordinator",
    ))
    if _SCE_DIR not in sys.path:
        sys.path.insert(0, _SCE_DIR)
    from safe_command_executor import check_command as _sce_check
except ImportError:
    def _sce_check(cmd: str):  # type: ignore[misc]
        return True, "ok"

HYBRID_URL = os.getenv("HYBRID_URL", "http://127.0.0.1:8003")
AIDB_URL   = os.getenv("AIDB_URL",   "http://127.0.0.1:8002")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
AQD_BIN = os.path.join(REPO_ROOT, "scripts", "ai", "aqd")
BRIDGE_MAX_RESULT_CHARS = max(
    256,
    int(os.getenv("AI_MCP_BRIDGE_MAX_RESULT_CHARS", os.getenv("AI_CODE_EXEC_MAX_RESULT_CHARS", "4000"))),
)

def _read_key(path_env: str, key_env: str) -> str:
    path = os.getenv(path_env, "")
    if path and os.path.isfile(path):
        return open(path).read().strip()
    return os.getenv(key_env, "")

HYBRID_KEY = _read_key("HYBRID_API_KEY_FILE", "HYBRID_API_KEY")
AIDB_KEY   = _read_key("AIDB_API_KEY_FILE",   "AIDB_API_KEY")

# Per-tool HTTP timeouts (seconds). Fast endpoints get short timeouts so
# VSCodium / Continue.dev don't hang when hybrid-coordinator is under load.
_TOOL_TIMEOUTS: dict[str, int] = {
    "get_hints":          5,
    "harness_health":     5,
    "qa_check":           5,
    "coordinator_status": 5,
    "coordinator_lessons":5,
    "hints_feedback":     5,
    "workflow_blueprints":8,
    "hybrid_search":      15,
    "recall_memory":      10,
    "store_memory":       10,
    "query_aidb":         15,
    "augment_query":      15,
    "get_working_memory": 8,
    "save_working_memory":10,
    "list_skills":        10,
    "get_skill_content":  10,
    "auto_select_tools":  12,
    "tool_catalog":       10,
    "trading_analyze":    90,
    "trading_forecast":   30,
    "workflow_plan":      45,
    "workflow_run_start": 60,
    "workflow_orchestrate":60,
    "agent_intake":       30,
    "lifecycle_status":   8,
    "lifecycle_advance":  8,
}
_DEFAULT_TIMEOUT_POST = 30
_DEFAULT_TIMEOUT_GET  = 10

# Client-side hints cache — avoids repeated calls to /hints on every keystroke.
# Entries expire after _HINTS_CACHE_TTL seconds.
_hints_cache: dict[str, tuple[dict, float]] = {}
_HINTS_CACHE_TTL = 30.0

# Thread pool for non-blocking local subprocess calls.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp-bridge")


def _resolve_workflow_target(target_dir_arg: str) -> tuple[str, str | None]:
    """Resolve a workflow target_dir arg to an absolute path.

    Returns (abs_path, warning_or_None).

    Cross-project isolation rule: workflow tools that write project files (retrofit,
    primer, brownfield, project-init) MUST operate on the caller's project directory,
    not the harness repo. Relative paths (including ".") are ambiguous when the bridge
    runs with cwd=REPO_ROOT — they silently resolve to the harness repo itself.

    Enforcement:
    - If the caller passes an absolute path → use it directly.
    - If the caller passes "." or a relative path → resolve relative to REPO_ROOT
      (unavoidable default) and emit a warning. External agents should always pass
      an absolute path to the project they're initialising.
    - If the resolved path equals REPO_ROOT → append a strong warning: writing
      project-init artifacts here will overwrite harness scaffolding.
    """
    abs_target = os.path.abspath(target_dir_arg) if os.path.isabs(target_dir_arg) else os.path.abspath(
        os.path.join(REPO_ROOT, target_dir_arg)
    )
    warning = None
    if not os.path.isabs(target_dir_arg) or target_dir_arg in (".", "./"):
        warning = (
            f"WARNING: target_dir '{target_dir_arg}' is a relative path; "
            f"resolved to '{abs_target}' (harness bridge cwd={REPO_ROOT}). "
            "For external projects pass an absolute path to avoid writing into the harness repo."
        )
    if os.path.normpath(abs_target) == os.path.normpath(REPO_ROOT):
        warning = (
            f"WARNING: target_dir resolved to the harness repo root ({REPO_ROOT}). "
            "This will overwrite harness scaffolding (.claude/CLAUDE.md, commands, .agent/ files). "
            "Pass target_dir as an absolute path to the external project directory."
        )
    return abs_target, warning


def _post(url: str, payload: dict, key: str, timeout: int = _DEFAULT_TIMEOUT_POST) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.reason, "status": e.code}
    except Exception as e:
        return {"error": str(e)}


def _get(url: str, key: str, timeout: int = _DEFAULT_TIMEOUT_GET) -> dict:
    req = urllib.request.Request(url, headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def _query_aidb_knowledge(query: str, limit: int = 5, project: str | None = None, timeout: int = _DEFAULT_TIMEOUT_POST) -> dict:
    payload = {"query": query, "limit": limit}
    if project:
        payload["project"] = project

    legacy = _post(f"{AIDB_URL}/query", payload, AIDB_KEY, timeout=timeout)
    if "error" not in legacy or legacy.get("status") != 404:
        return legacy

    params = {"search": query, "limit": str(limit)}
    if project:
        params["project"] = project
    docs_url = f"{AIDB_URL}/documents?{urllib.parse.urlencode(params)}"
    docs = _get(docs_url, AIDB_KEY, timeout=_DEFAULT_TIMEOUT_GET)
    if "error" in docs:
        return docs

    documents = docs.get("documents") if isinstance(docs, dict) else None
    if not isinstance(documents, list):
        return {"error": "AIDB documents search returned unexpected shape", "raw": docs}

    normalized = []
    for item in documents[:limit]:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "title": item.get("title"),
            "project": item.get("project"),
            "relative_path": item.get("relative_path"),
            "content": item.get("content"),
            "content_type": item.get("content_type"),
            "status": item.get("status"),
            "imported_at": item.get("imported_at"),
        })
    return {
        "query": query,
        "project": project,
        "limit": limit,
        "results": normalized,
        "documents_count": len(documents),
        "source": "documents_search_fallback",
    }


def _get_hints_cached(url: str, key: str) -> dict:
    now = time.monotonic()
    entry = _hints_cache.get(url)
    if entry is not None:
        result, ts = entry
        if now - ts < _HINTS_CACHE_TTL:
            cached = dict(result)
            cached["_bridge_cached"] = True
            return cached
    result = _get(url, key, timeout=_TOOL_TIMEOUTS["get_hints"])
    if "error" not in result:
        _hints_cache[url] = (result, now)
    return result


def _run_local(argv: list[str], cwd: str | None = None, timeout: int = 30) -> dict:
    # Safety gate — block destructive commands before execution
    _cmd_str = " ".join(str(a) for a in argv)
    _allowed, _reason = _sce_check(_cmd_str)
    if not _allowed:
        return {"ok": False, "blocked": True, "error": _reason, "argv": argv}
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd or REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"local command timed out after {timeout}s", "argv": argv}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "argv": argv}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "argv": argv,
    }


def _default_intent_contract(query: str) -> dict:
    q = (query or "").strip() or "workflow run"
    return {
        "user_intent": q,
        "definition_of_done": f"Complete requested workflow task: {q[:120]}",
        "depth_expectation": "minimum",
        "spirit_constraints": [
            "follow declarative-first policy",
            "capture validation evidence",
        ],
        "no_early_exit_without": [
            "all requested checks complete",
        ],
    }


def _format_result(value) -> str:
    text = json.dumps(value, indent=2)
    if len(text) <= BRIDGE_MAX_RESULT_CHARS:
        return text

    preview_budget = max(128, min(BRIDGE_MAX_RESULT_CHARS // 2, BRIDGE_MAX_RESULT_CHARS - 256))
    summary = {
        "truncated": True,
        "max_result_chars": BRIDGE_MAX_RESULT_CHARS,
        "result_type": type(value).__name__,
        "preview": text[:preview_budget],
    }
    if isinstance(value, dict):
        summary["top_level_keys"] = list(value.keys())[:12]
    elif isinstance(value, list):
        summary["item_count"] = len(value)
    return json.dumps(summary, indent=2)


def _normalize_memory_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "fact": "semantic",
        "decision": "procedural",
        "context": "episodic",
    }.get(normalized, normalized or "semantic")


TOOLS = [
    {
        "name": "hybrid_search",
        "description": (
            "Search the AI stack knowledge base using semantic + keyword hybrid search. "
            "Optionally generate an LLM-synthesised answer. Use for NixOS questions, "
            "code patterns, system architecture, and any task requiring context retrieval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":             {"type": "string",  "description": "Search query"},
                "mode":              {"type": "string",  "enum": ["auto","local","remote"], "default": "auto"},
                "generate_response": {"type": "boolean", "default": False,
                                     "description": "Set true to get an LLM-synthesised answer"},
                "limit":             {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_hints",
        "description": (
            "Get ranked workflow hints for the current task. Returns hints from the "
            "prompt registry, recent query gaps, and CLAUDE.md rules. "
            "Call this at the start of any non-trivial task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "q":     {"type": "string",  "description": "Task description or query"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": [],
        },
    },
    {
        "name": "workflow_plan",
        "description": (
            "Create a phased workflow plan from a task query using hybrid-coordinator "
            "/workflow/plan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Task objective"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "tooling_manifest",
        "description": (
            "Return a compact tooling manifest optimized for code-execution clients. "
            "Use this to import tools on demand and keep tool output bounded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Task objective"},
                "runtime": {"type": "string", "enum": ["python", "typescript"], "default": "python"},
                "max_tools": {"type": "integer", "default": 6},
                "max_result_chars": {"type": "integer", "default": BRIDGE_MAX_RESULT_CHARS},
            },
            "required": ["query"],
        },
    },
    {
        "name": "workflow_run_start",
        "description": (
            "Start a guarded workflow run via /workflow/run/start. "
            "If intent_contract is omitted, safe defaults are injected."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Task objective"},
                "safety_mode": {"type": "string", "enum": ["plan-readonly", "execute-mutating"], "default": "plan-readonly"},
                "token_limit": {"type": "integer", "default": 8000},
                "tool_call_limit": {"type": "integer", "default": 40},
                "intent_contract": {"type": "object"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "workflow_blueprints",
        "description": "Fetch available workflow blueprints from hybrid-coordinator.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "aqd_workflows_list",
        "description": "List AQD workflow/catalog commands from local harness tooling.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "bootstrap_agent_project",
        "description": (
            "Generate a new-repo agentic starter workflow pack "
            "(PRD, global rules, phase plan, intent contract, start script)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "goal": {"type": "string"},
                "target_dir": {"type": "string", "default": "."},
                "stack": {"type": "string"},
                "owner": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["project_name", "goal"],
        },
    },
    {
        "name": "project_init_workflow",
        "description": (
            "Run AQD guided /project-init workflow for empty-dir project initialization."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_dir": {"type": "string", "default": "."},
                "project_name": {"type": "string"},
                "goal": {"type": "string"},
                "stack": {"type": "string"},
                "owner": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "primer_workflow",
        "description": (
            "Run AQD read-only /primer workflow and emit session primer summary."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_dir": {"type": "string", "default": "."},
                "objective": {"type": "string"},
                "output": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "brownfield_workflow",
        "description": (
            "Run AQD guided /brownfield workflow to generate brownfield PDR "
            "from an existing codebase and AI layer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_dir": {"type": "string", "default": "."},
                "objective": {"type": "string"},
                "constraints": {"type": "string"},
                "out_of_scope": {"type": "string"},
                "acceptance": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "retrofit_workflow",
        "description": (
            "Run AQD /retrofit workflow to seed or refresh AI-layer artifacts "
            "in an existing repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_dir": {"type": "string", "default": "."},
                "project_name": {"type": "string"},
                "goal": {"type": "string"},
                "stack": {"type": "string"},
                "owner": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "store_memory",
        "description": "Store a key fact or decision in agent memory for later recall.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content":   {"type": "string", "description": "Fact or decision to store"},
                "agent_id":  {"type": "string", "default": "continue"},
                "memory_type": {
                    "type": "string",
                    "enum": ["semantic", "procedural", "episodic", "fact", "decision", "context"],
                    "default": "semantic",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Recall stored agent memory relevant to a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":    {"type": "string", "description": "What to recall"},
                "agent_id": {"type": "string", "default": "continue"},
                "limit":    {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_aidb",
        "description": (
            "Search the AIDB document knowledge base directly. "
            "Contains CLAUDE.md, AGENTS.md, QA plans, prompt registry, "
            "tooling registry, and all imported project documents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "augment_query",
        "description": (
            "Augment a query with additional context from the AI harness (codebase patterns, "
            "prior solutions, semantic context). Use before issuing a hybrid_search to "
            "improve retrieval quality."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to augment"},
                "context": {"type": "object", "description": "Optional extra context key/values"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "qa_check",
        "description": (
            "Run a QA health check against the AI stack. Returns service status, "
            "reachability of AIDB/Qdrant/Redis/hybrid-coordinator, and any failing checks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "phase": {"type": "integer", "description": "QA phase to run (0=all services, 1=data stores)", "default": 0},
            },
            "required": [],
        },
    },
    {
        "name": "hints_feedback",
        "description": (
            "Submit feedback on a hint (accepted/rejected). Helps the harness learn which "
            "hints are useful. Call after acting on (or ignoring) a hint."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hint_id":  {"type": "string", "description": "The hint ID returned by get_hints"},
                "accepted": {"type": "boolean", "description": "True if the hint was acted on"},
                "comment":  {"type": "string", "description": "Optional free-text feedback"},
            },
            "required": ["hint_id", "accepted"],
        },
    },
    {
        "name": "coordinator_status",
        "description": (
            "Get the AI coordinator status: active lessons, routing decisions, "
            "capability coverage, and performance metrics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "coordinator_lessons",
        "description": (
            "List lessons learned by the AI coordinator — patterns extracted from "
            "past successes/failures that guide future routing and tool selection."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max lessons to return", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch a URL via the AI harness research layer. Returns page content "
            "suitable for in-context use. Use for documentation lookups, issue trackers, "
            "or any URL-based research the local agent needs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url":       {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "description": "Max chars to return", "default": 4000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "workflow_orchestrate",
        "description": (
            "Start a full agentic workflow orchestration session on the harness. "
            "The harness plans, executes, and validates a multi-step task autonomously. "
            "Returns a session_id for polling status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":          {"type": "string", "description": "Task description"},
                "safety_mode":    {"type": "string", "enum": ["plan-readonly", "execute-mutating"], "default": "plan-readonly"},
                "token_limit":    {"type": "integer", "default": 8000},
                "tool_call_limit":{"type": "integer", "default": 40},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_sops",
        "description": (
            "List available SOP (Standard Operating Procedure) templates. "
            "SOPs are markdown-based workflows with RFC 2119 constraints "
            "(MUST, SHOULD, MAY) for systematic task execution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "parse_sop",
        "description": (
            "Parse an SOP file and extract structure, steps, and RFC 2119 "
            "constraints. Returns sections, steps, and constraint analysis."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sop_name": {"type": "string", "description": "SOP filename (e.g., 'codebase-analysis.sop.md')"},
            },
            "required": ["sop_name"],
        },
    },
    {
        "name": "get_prsi_pending",
        "description": (
            "Fetch pending PRSI (Pessimistic Recursive Self-Improvement) actions from the "
            "local queue. Returns actions awaiting triage or approval with their type, "
            "risk level, and summary. Call this first for any PRSI triage task instead "
            "of running ls or reading the repo root. Fast — reads queue file directly."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "prsi_orchestrate",
        "description": (
            "Run a PRSI orchestrator command: sync (refresh queue from aq-report), "
            "list (show all actions with optional risk filter), approve (mark an action "
            "approved by a named reviewer), or execute (run up to N approved actions). "
            "Use after get_prsi_pending to act on pending items."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["sync", "list", "approve", "execute"],
                    "description": "Orchestrator command to run",
                },
                "since":   {"type": "string", "default": "1d",
                            "description": "Time window for sync (e.g. '1d', '7d')"},
                "risk":    {"type": "string", "enum": ["low", "medium", "high"],
                            "description": "Filter by risk level for list"},
                "id":      {"type": "string", "description": "Action ID for approve"},
                "by":      {"type": "string", "description": "Reviewer name for approve"},
                "note":    {"type": "string", "description": "Reviewer note for approve"},
                "limit":   {"type": "integer", "default": 1,
                            "description": "Max actions for execute"},
                "dry_run": {"type": "boolean", "default": True,
                            "description": "Dry-run mode for execute"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "harness_health",
        "description": (
            "Run a quick AI stack health check (aq-qa phase 0). Returns pass/fail "
            "counts for all services. Use to diagnose service issues before deeper "
            "investigation. Equivalent to running aq-qa 0 in the terminal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "phase": {"type": "integer", "default": 0,
                          "description": "QA phase: 0=all services, 1=datastores only"},
            },
            "required": [],
        },
    },
    {
        "name": "execute_sop",
        "description": (
            "Execute an SOP workflow with validation and logging. "
            "Simulates step execution and validates against RFC 2119 constraints. "
            "Returns execution summary and validation results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sop_name": {"type": "string", "description": "SOP filename to execute"},
                "context": {"type": "object", "description": "Execution context (parameters)"},
            },
            "required": ["sop_name"],
        },
    },
    # -----------------------------------------------------------------------
    # Phase 24: Agent-agnostic tool discovery + skill registry
    # Available to ALL agents: Continue, qwen, gemini, local llama.cpp, etc.
    # -----------------------------------------------------------------------
    {
        "name": "list_skills",
        "description": (
            "List all skills registered in the harness skill registry (AIDB). "
            "Returns every approved skill with slug, name, description, and retrieval endpoint. "
            "Call this at agent startup to discover all available capabilities — no explicit "
            "skill naming needed. Available to all agents and MCP clients."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Filter by domain tag (optional)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results"},
            },
            "required": [],
        },
    },
    {
        "name": "get_skill_content",
        "description": (
            "Retrieve the full content of a specific skill by slug. "
            "Returns the SKILL.md content with HTTP invocation patterns, commands, "
            "tool sequences, and examples — usable by any agent without file access. "
            "Slug examples: impeccable, tradingagents, ai-stack-qa, debug-workflow."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Skill slug (e.g. impeccable, tradingagents)"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "auto_select_tools",
        "description": (
            "Automatically select and sequence the right tools for any task description. "
            "Returns an ordered tool manifest with HTTP endpoints, execution phases, "
            "recommended skills, and AIDB project context — without requiring any "
            "explicit tool naming. Call this at the START of any task. "
            "Available to all agents and MCP clients."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Free-text task description"},
                "limit": {"type": "integer", "default": 8, "description": "Max tools to return"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "tool_catalog",
        "description": (
            "Retrieve the full tool catalog — everything available in the harness. "
            "Returns all tools with endpoints, methods, and descriptions grouped by domain "
            "(core, design, trading, orchestration, research, quality). "
            "Call once at agent startup for complete capability discovery."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter by domain: core|design|trading|orchestration|research|quality (default: all)",
                },
                "format": {
                    "type": "string",
                    "enum": ["full", "compact", "names-only"],
                    "default": "compact",
                },
            },
            "required": [],
        },
    },
    {
        "name": "trading_analyze",
        "description": (
            "Run the full 5-team trading analysis pipeline on a stock ticker: "
            "market analyst (OHLCV + technicals) + fundamentals analyst (balance sheet, P&L) + "
            "news analyst (headlines, insider transactions) + sentiment analyst → "
            "bull/bear researcher debate → trader synthesis → risk management → portfolio approval. "
            "Returns BUY/HOLD/SELL decision with position size and full reasoning. "
            "Runs on local Qwen3.6-35B — no external API key required (yfinance for data)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock symbol (e.g. AAPL, NVDA)"},
                "date": {"type": "string", "description": "Trade date YYYY-MM-DD"},
                "analysts": {
                    "type": "string",
                    "default": "market,fundamentals,news,sentiment",
                    "description": "Comma-separated analyst types to run",
                },
                "debate_rounds": {"type": "integer", "default": 1},
            },
            "required": ["ticker", "date"],
        },
    },
    {
        "name": "trading_forecast",
        "description": (
            "Quick market signal for a stock — runs only the market/technical analyst "
            "and trader synthesis. Much faster than full pipeline. "
            "Returns trend direction, key indicator readings, and preliminary BUY/HOLD/SELL. "
            "Use for rapid screening before running full trading_analyze."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock symbol"},
                "date": {"type": "string", "description": "Trade date YYYY-MM-DD"},
            },
            "required": ["ticker", "date"],
        },
    },
    {
        "name": "trading_tools",
        "description": (
            "Discover all available financial data tools: get_stock_data, get_indicators, "
            "get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, "
            "get_news, get_insider_transactions. Returns tool names, descriptions, "
            "parameters, and HTTP endpoints. Use for tool discovery before trading analysis."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "impeccable_design",
        "description": (
            "Apply production-grade frontend design intelligence from the impeccable framework. "
            "Retrieves design reference docs from AIDB and returns actionable guidance for: "
            "audit (a11y, contrast, performance), critique (UX, hierarchy), polish (shipping readiness), "
            "craft (full design workflow), animate, colorize (OKLCH), typeset (typography scale), "
            "bolder, quieter, distill, overdrive. "
            "Also detects anti-patterns: gradient-text, glassmorphism, side-stripe-borders, "
            "hero-metric-template, identical-card-grid, missing-reduced-motion, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "audit", "critique", "polish", "craft", "shape", "animate",
                        "colorize", "typeset", "bolder", "quieter", "distill", "overdrive",
                        "layout", "onboard", "harden", "delight",
                    ],
                    "description": "Design command to apply",
                },
                "context": {
                    "type": "string",
                    "description": "Description of the UI/component being designed or reviewed",
                },
                "reference_query": {
                    "type": "string",
                    "description": "Specific design topic to retrieve from AIDB (optional)",
                },
            },
            "required": ["command", "context"],
        },
    },
    {
        "name": "simulate_nix_change",
        "description": (
            "Dry-run validate a NixOS derivation build before committing any .nix file change. "
            "Runs 'nix build <derivation> --dry-run' against the working tree. "
            "REQUIRED before any autonomous .nix file modification. "
            "Returns whether the build plan succeeds without actually building."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "derivation": {
                    "type": "string",
                    "description": "Nix derivation path (e.g. .#nixosConfigurations.hyperd.config.system.build.toplevel)",
                },
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra nix build flags (optional)",
                },
            },
            "required": ["derivation"],
        },
    },
    {
        "name": "validate_service_config",
        "description": (
            "Evaluate a NixOS service config option without building anything. "
            "Runs 'nix eval <option_path>' to confirm a config option is syntactically valid "
            "and has the expected value. Use to pre-validate service config changes "
            "before applying them with nixos-rebuild."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "option_path": {
                    "type": "string",
                    "description": "NixOS option path (e.g. .#nixosConfigurations.hyperd.config.services.nginx.enable)",
                },
            },
            "required": ["option_path"],
        },
    },
    # Phase 25-007: context offload + working memory tools
    {
        "name": "summarize_context",
        "description": (
            "Compress conversation history into a structured summary to avoid context limit errors. "
            "Returns key_decisions, open_questions, next_steps, and a compressed summary string. "
            "Use when the conversation is long — save the result with save_working_memory "
            "so future sessions can resume without re-scanning history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "history": {
                    "type": "array",
                    "description": "List of {role, content} message dicts to compress.",
                    "items": {"type": "object"},
                },
                "max_tokens": {"type": "integer", "description": "Target token budget for summary (default 2000)."},
                "focus": {"type": "string", "description": "What to focus on: decisions, next_steps, or all (default)."},
            },
            "required": ["history"],
        },
    },
    {
        "name": "save_working_memory",
        "description": (
            "Persist key session facts, decisions, and next steps to working memory so they survive context resets. "
            "Call this after summarize_context or whenever you want to checkpoint progress. "
            "A future session can call get_working_memory to resume without re-reading the full history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key_facts": {"type": "array", "items": {"type": "string"}, "description": "Key facts established this session."},
                "decisions": {"type": "array", "items": {"type": "string"}, "description": "Decisions made."},
                "next_steps": {"type": "array", "items": {"type": "string"}, "description": "Remaining tasks."},
                "open_questions": {"type": "array", "items": {"type": "string"}, "description": "Unresolved questions."},
                "session_id": {"type": "string", "description": "Optional session identifier."},
                "metadata": {"type": "object", "description": "Optional extra context."},
            },
            "required": ["key_facts"],
        },
    },
    {
        "name": "get_working_memory",
        "description": (
            "Retrieve the last saved working memory. Call this at the START of a new session to resume "
            "where you left off without re-reading the full conversation history."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "agent_intake",
        "description": (
            "Submit a user prompt to the Universal Agent Gateway (UAG). This is the SINGLE ENTRY POINT "
            "for all orchestrated tasks. Returns a session_id and lifecycle phase sequence "
            "(INTAKE→DISCOVER→PRD→PLAN→ASSIGN→DELEGATE→VALIDATE→COMMIT). "
            "Call this first for any task that involves code changes, planning, or multi-step work. "
            "Use lifecycle_status to track progress and lifecycle_advance to record phase completions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt":     {"type": "string",  "description": "The user task description"},
                "complexity": {"type": "string",  "description": "simple|standard|complex (auto-detected if omitted)"},
                "domain":     {"type": "string",  "description": "nixos|python|security|trading|design|infra|general"},
                "context":    {"type": "object",  "description": "Optional extra context: {file_path, selection, ...}"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "lifecycle_status",
        "description": (
            "Get the current state of a lifecycle session started via agent_intake. "
            "Shows phase history, current phase, pruned context (relevant outputs only — not full tool history), "
            "and the next_action guidance. Check this before each phase to get the right context slice."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID returned by agent_intake"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "lifecycle_advance",
        "description": (
            "Record phase completion and advance the lifecycle session to the next phase. "
            "IMPORTANT: output_summary must be a SHORT STRUCTURED SUMMARY (not raw tool output). "
            "context_updates must contain ONLY the key outputs from this phase (e.g., "
            "{prd_scope: '...', acceptance_checks: [...]}) — not the full conversation or search results. "
            "This ensures the next phase receives only relevant context, preventing context window bloat."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":      {"type": "string", "description": "Session ID"},
                "status":          {"type": "string", "description": "passed|failed|skipped"},
                "output_summary":  {"type": "string", "description": "Brief summary of phase outcome (1-3 sentences)"},
                "tools_used":      {"type": "array",  "items": {"type": "string"}, "description": "Tool names invoked"},
                "context_updates": {"type": "object", "description": "Structured key outputs for this phase only"},
                "error":           {"type": "string", "description": "Error message if status=failed"},
            },
            "required": ["session_id"],
        },
    },
]


def _call_tool(name: str, args: dict) -> str:
    _timeout_post = _TOOL_TIMEOUTS.get(name, _DEFAULT_TIMEOUT_POST)
    _timeout_get  = _TOOL_TIMEOUTS.get(name, _DEFAULT_TIMEOUT_GET)

    if name == "hybrid_search":
        r = _post(f"{HYBRID_URL}/query", {
            "query":             args.get("query", ""),
            "mode":              args.get("mode", "auto"),
            "prefer_local":      True,
            "limit":             args.get("limit", 5),
            "generate_response": args.get("generate_response", False),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "get_hints":
        params = f"?limit={args.get('limit', 3)}"
        q = args.get("q", "")
        if q:
            params += f"&q={urllib.parse.quote(q)}"
        r = _get_hints_cached(f"{HYBRID_URL}/hints{params}", HYBRID_KEY)
        return _format_result(r)

    if name == "workflow_plan":
        r = _post(f"{HYBRID_URL}/workflow/plan", {
            "query": args.get("query", ""),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "tooling_manifest":
        r = _post(f"{HYBRID_URL}/workflow/tooling-manifest", {
            "query": args.get("query", ""),
            "runtime": args.get("runtime", "python"),
            "max_tools": int(args.get("max_tools", 6)),
            "max_result_chars": int(args.get("max_result_chars", BRIDGE_MAX_RESULT_CHARS)),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "workflow_run_start":
        query = args.get("query", "")
        intent_contract = args.get("intent_contract") or _default_intent_contract(query)
        r = _post(f"{HYBRID_URL}/workflow/run/start", {
            "query": query,
            "safety_mode": args.get("safety_mode", "plan-readonly"),
            "token_limit": int(args.get("token_limit", 8000)),
            "tool_call_limit": int(args.get("tool_call_limit", 40)),
            "intent_contract": intent_contract,
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "workflow_blueprints":
        r = _get(f"{HYBRID_URL}/workflow/blueprints", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "aqd_workflows_list":
        r = _run_local([AQD_BIN, "workflows", "list"])
        return _format_result(r)

    if name == "bootstrap_agent_project":
        argv = [
            AQD_BIN,
            "workflows",
            "bootstrap",
            "--name",
            str(args.get("project_name", "")),
            "--goal",
            str(args.get("goal", "")),
            "--target",
            str(args.get("target_dir", ".")),
        ]
        if args.get("stack"):
            argv.extend(["--stack", str(args.get("stack"))])
        if args.get("owner"):
            argv.extend(["--owner", str(args.get("owner"))])
        if bool(args.get("force", False)):
            argv.append("--force")
        r = _run_local(argv)
        return _format_result(r)

    if name == "project_init_workflow":
        abs_target, target_warn = _resolve_workflow_target(str(args.get("target_dir", ".")))
        argv = [AQD_BIN, "workflows", "project-init", "--target", abs_target]
        if args.get("project_name"):
            argv.extend(["--name", str(args.get("project_name"))])
        if args.get("goal"):
            argv.extend(["--goal", str(args.get("goal"))])
        if args.get("stack"):
            argv.extend(["--stack", str(args.get("stack"))])
        if args.get("owner"):
            argv.extend(["--owner", str(args.get("owner"))])
        if bool(args.get("force", False)):
            argv.append("--force")
        r = _run_local(argv, cwd=abs_target)
        if target_warn:
            r.setdefault("warnings", []).append(target_warn)
        return _format_result(r)

    if name == "primer_workflow":
        abs_target, target_warn = _resolve_workflow_target(str(args.get("target_dir", ".")))
        argv = [AQD_BIN, "workflows", "primer", "--target", abs_target]
        if args.get("objective"):
            argv.extend(["--objective", str(args.get("objective"))])
        if args.get("output"):
            argv.extend(["--output", str(args.get("output"))])
        r = _run_local(argv, cwd=abs_target)
        if target_warn:
            r.setdefault("warnings", []).append(target_warn)
        return _format_result(r)

    if name == "brownfield_workflow":
        abs_target, target_warn = _resolve_workflow_target(str(args.get("target_dir", ".")))
        argv = [AQD_BIN, "workflows", "brownfield", "--target", abs_target]
        if args.get("objective"):
            argv.extend(["--objective", str(args.get("objective"))])
        if args.get("constraints"):
            argv.extend(["--constraints", str(args.get("constraints"))])
        if args.get("out_of_scope"):
            argv.extend(["--out-of-scope", str(args.get("out_of_scope"))])
        if args.get("acceptance"):
            argv.extend(["--acceptance", str(args.get("acceptance"))])
        if bool(args.get("force", False)):
            argv.append("--force")
        r = _run_local(argv, cwd=abs_target)
        if target_warn:
            r.setdefault("warnings", []).append(target_warn)
        return _format_result(r)

    if name == "retrofit_workflow":
        abs_target, target_warn = _resolve_workflow_target(str(args.get("target_dir", ".")))
        argv = [AQD_BIN, "workflows", "retrofit", "--target", abs_target]
        if args.get("project_name"):
            argv.extend(["--name", str(args.get("project_name"))])
        if args.get("goal"):
            argv.extend(["--goal", str(args.get("goal"))])
        if args.get("stack"):
            argv.extend(["--stack", str(args.get("stack"))])
        if args.get("owner"):
            argv.extend(["--owner", str(args.get("owner"))])
        if bool(args.get("force", False)):
            argv.append("--force")
        r = _run_local(argv, cwd=abs_target)
        if target_warn:
            r.setdefault("warnings", []).append(target_warn)
        return _format_result(r)

    if name == "store_memory":
        r = _post(f"{HYBRID_URL}/memory/store", {
            "content":     args.get("content", ""),
            "agent_id":    args.get("agent_id", "continue"),
            "memory_type": _normalize_memory_type(args.get("memory_type", "semantic")),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "recall_memory":
        r = _post(f"{HYBRID_URL}/memory/recall", {
            "query":    args.get("query", ""),
            "agent_id": args.get("agent_id", "continue"),
            "limit":    args.get("limit", 5),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "query_aidb":
        r = _query_aidb_knowledge(
            args.get("query", ""),
            limit=int(args.get("limit", 5)),
            project=args.get("project"),
            timeout=_timeout_post,
        )
        return _format_result(r)

    if name == "augment_query":
        r = _post(f"{HYBRID_URL}/augment_query", {
            "query":   args.get("query", ""),
            "context": args.get("context", {}),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "qa_check":
        phase = int(args.get("phase", 0))
        r = _post(f"{HYBRID_URL}/qa/check", {"phase": phase}, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "hints_feedback":
        r = _post(f"{HYBRID_URL}/hints/feedback", {
            "hint_id":  args.get("hint_id", ""),
            "accepted": bool(args.get("accepted", False)),
            "comment":  args.get("comment", ""),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "coordinator_status":
        r = _get(f"{HYBRID_URL}/control/ai-coordinator/status", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "coordinator_lessons":
        limit = int(args.get("limit", 10))
        r = _get(f"{HYBRID_URL}/control/ai-coordinator/lessons?limit={limit}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "get_prsi_pending":
        r = _get(f"{HYBRID_URL}/control/prsi/pending", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "prsi_orchestrate":
        import shutil
        command = args.get("command", "list")
        orchestrator = os.path.join(REPO_ROOT, "scripts", "automation", "prsi-orchestrator.py")
        python = shutil.which("python3") or sys.executable
        argv = [python, orchestrator, command]
        if command == "sync":
            argv += ["--since", args.get("since", "1d")]
        elif command == "list":
            if args.get("risk"):
                argv += ["--risk", args["risk"]]
        elif command == "approve":
            argv += ["--id", args.get("id", ""), "--by", args.get("by", "local-agent")]
            if args.get("note"):
                argv += ["--note", args["note"]]
        elif command == "execute":
            argv += ["--limit", str(args.get("limit", 1))]
            if args.get("dry_run", True):
                argv.append("--dry-run")
        r = _run_local(argv)
        return _format_result(r)

    if name == "harness_health":
        phase = int(args.get("phase", 0))
        r = _post(f"{HYBRID_URL}/qa/check", {"phase": phase}, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "web_fetch":
        r = _post(f"{HYBRID_URL}/research/web/fetch", {
            "url":       args.get("url", ""),
            "max_chars": int(args.get("max_chars", 4000)),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "workflow_orchestrate":
        query = args.get("query", "")
        intent_contract = _default_intent_contract(query)
        r = _post(f"{HYBRID_URL}/workflow/orchestrate", {
            "query":           query,
            "safety_mode":     args.get("safety_mode", "plan-readonly"),
            "token_limit":     int(args.get("token_limit", 8000)),
            "tool_call_limit": int(args.get("tool_call_limit", 40)),
            "intent_contract": intent_contract,
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "list_sops":
        from pathlib import Path
        sop_dir = Path(REPO_ROOT) / "ai-stack" / "sop-templates"
        if not sop_dir.exists():
            return _format_result({"sops": [], "count": 0})

        sops = []
        for sop_file in sop_dir.glob("*.sop.md"):
            sops.append({
                "name": sop_file.name,
                "path": str(sop_file),
            })

        return _format_result({"sops": sops, "count": len(sops)})

    if name == "parse_sop":
        from pathlib import Path
        import sys

        # Add local-orchestrator to path for sop_engine import
        orchestrator_path = str(Path(REPO_ROOT) / "ai-stack" / "local-orchestrator")
        if orchestrator_path not in sys.path:
            sys.path.insert(0, orchestrator_path)

        from sop_engine import parse_sop

        sop_name = args.get("sop_name", "")
        sop_path = Path(REPO_ROOT) / "ai-stack" / "sop-templates" / sop_name

        if not sop_path.exists():
            return _format_result({"error": f"SOP not found: {sop_name}"})

        try:
            sop = parse_sop(sop_path)

            # Convert to JSON-serializable format
            result = {
                "name": sop.name,
                "description": sop.description,
                "version": sop.version,
                "parameters": sop.parameters,
                "sections": [
                    {
                        "title": section.title,
                        "level": section.level,
                        "steps": [
                            {
                                "number": step.number,
                                "title": step.title,
                                "constraint": step.constraint.value,
                                "is_required": step.is_required(),
                                "is_optional": step.is_optional(),
                            }
                            for step in section.steps
                        ],
                    }
                    for section in sop.sections
                ],
                "required_steps": len(sop.get_required_steps()),
                "optional_steps": len(sop.get_optional_steps()),
            }

            return _format_result(result)
        except Exception as e:
            return _format_result({"error": f"Failed to parse SOP: {str(e)}"})

    if name == "execute_sop":
        from pathlib import Path
        import sys

        # Add local-orchestrator to path
        orchestrator_path = str(Path(REPO_ROOT) / "ai-stack" / "local-orchestrator")
        if orchestrator_path not in sys.path:
            sys.path.insert(0, orchestrator_path)

        from sop_engine import parse_sop, execute_sop

        sop_name = args.get("sop_name", "")
        sop_path = Path(REPO_ROOT) / "ai-stack" / "sop-templates" / sop_name

        if not sop_path.exists():
            return _format_result({"error": f"SOP not found: {sop_name}"})

        try:
            sop = parse_sop(sop_path)
            context = args.get("context", {})

            # Execute with default executor (marks all steps as completed)
            result = execute_sop(sop, context)

            return _format_result(result)
        except Exception as e:
            return _format_result({"error": f"Failed to execute SOP: {str(e)}"})

    # -----------------------------------------------------------------------
    # Phase 24: Agent-agnostic skill registry + tool discovery
    # -----------------------------------------------------------------------
    if name == "list_skills":
        domain = args.get("domain", "")
        limit = int(args.get("limit", 50))
        params = f"?include_pending=true&limit={limit}"
        r = _get(f"{AIDB_URL}/skills{params}", AIDB_KEY, timeout=_timeout_get)
        if isinstance(r, list):
            skills = [
                {
                    "slug": s.get("slug", ""),
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "status": s.get("status", ""),
                    "source_path": s.get("source_path", ""),
                    "content_endpoint": f"{HYBRID_URL}/skills/{s.get('slug', '')}/content",
                }
                for s in r
                if s.get("status") == "approved"
            ]
            if domain:
                # filter by description keyword as proxy for domain
                skills = [s for s in skills if domain.lower() in s.get("description", "").lower()]
            return _format_result({"skills": skills, "count": len(skills)})
        return _format_result(r)

    if name == "get_skill_content":
        slug = args.get("slug", "").strip()
        if not slug:
            return _format_result({"error": "slug is required"})
        r = _get(f"{HYBRID_URL}/skills/{slug}/content", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "auto_select_tools":
        task = args.get("task", "")
        limit = int(args.get("limit", 8))
        params = f"?task={urllib.parse.quote(task)}&limit={limit}"
        r = _get(f"{HYBRID_URL}/tools/auto-select{params}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "tool_catalog":
        domain = args.get("domain", "all")
        fmt = args.get("format", "compact")
        params = f"?domain={domain}&format={fmt}"
        r = _get(f"{HYBRID_URL}/tools/catalog{params}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "trading_analyze":
        ticker = args.get("ticker", "").upper()
        date = args.get("date", "")
        analysts = args.get("analysts", "market,fundamentals,news,sentiment")
        rounds = int(args.get("debate_rounds", 1))
        params = f"?ticker={ticker}&date={date}&analysts={analysts}&debate_rounds={rounds}"
        r = _get(f"{HYBRID_URL}/trading/analyze{params}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "trading_forecast":
        ticker = args.get("ticker", "").upper()
        date = args.get("date", "")
        r = _get(f"{HYBRID_URL}/trading/forecast?ticker={ticker}&date={date}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "trading_tools":
        r = _get(f"{HYBRID_URL}/trading/tools", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "impeccable_design":
        command = args.get("command", "audit")
        context = args.get("context", "")
        ref_query = args.get("reference_query", f"{command} design reference")
        # Retrieve reference docs from AIDB
        ref = _query_aidb_knowledge(
            ref_query,
            limit=3,
            project="impeccable-design",
            timeout=15,
        )
        # Get skill content
        skill = _get(f"{HYBRID_URL}/skills/impeccable/content", HYBRID_KEY, timeout=10)
        return _format_result({
            "command": command,
            "context": context,
            "reference_docs": ref,
            "skill_guidance": skill.get("content", "") if isinstance(skill, dict) else str(skill)[:500],
            "anti_pattern_scan": "Run: npx impeccable detect <target-path>",
            "http_api": f"POST {HYBRID_URL}/query with project=impeccable-design",
        })

    if name == "simulate_nix_change":
        derivation = args.get("derivation", ".#nixosConfigurations.hyperd.config.system.build.toplevel")
        extra = [str(a) for a in (args.get("extra_args") or [])]
        argv = ["nix", "build", derivation, "--dry-run"] + extra
        r = _run_local(argv, cwd=REPO_ROOT)
        r["derivation"] = derivation
        r["note"] = "dry-run only — no build output produced"
        return _format_result(r)

    if name == "validate_service_config":
        option_path = args.get("option_path", "")
        if not option_path:
            return _format_result({"error": "option_path is required"})
        argv = ["nix", "eval", option_path]
        r = _run_local(argv, cwd=REPO_ROOT)
        r["option_path"] = option_path
        return _format_result(r)

    if name == "summarize_context":
        r = _post(f"{HYBRID_URL}/agent/summarize-context", {
            "history":    args.get("history", []),
            "max_tokens": args.get("max_tokens", 2000),
            "focus":      args.get("focus", "all"),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "save_working_memory":
        r = _post(f"{HYBRID_URL}/agent/working-memory/save", {
            "session_id":     args.get("session_id", "default"),
            "key_facts":      args.get("key_facts", []),
            "decisions":      args.get("decisions", []),
            "next_steps":     args.get("next_steps", []),
            "open_questions": args.get("open_questions", []),
            "metadata":       args.get("metadata", {}),
        }, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "get_working_memory":
        r = _get(f"{HYBRID_URL}/agent/working-memory", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "agent_intake":
        body: dict = {"prompt": args.get("prompt", "")}
        if args.get("complexity"):
            body["complexity"] = args["complexity"]
        if args.get("domain"):
            body["domain"] = args["domain"]
        if args.get("context"):
            body["context"] = args["context"]
        r = _post(f"{HYBRID_URL}/agent/intake", body, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    if name == "lifecycle_status":
        session_id = args.get("session_id", "")
        r = _get(f"{HYBRID_URL}/agent/lifecycle/{session_id}", HYBRID_KEY, timeout=_timeout_get)
        return _format_result(r)

    if name == "lifecycle_advance":
        session_id = args.get("session_id", "")
        body = {
            "status":          args.get("status", "passed"),
            "output_summary":  args.get("output_summary", ""),
            "tools_used":      args.get("tools_used", []),
            "context_updates": args.get("context_updates", {}),
        }
        if args.get("error"):
            body["error"] = args["error"]
        r = _post(f"{HYBRID_URL}/agent/lifecycle/{session_id}/advance", body, HYBRID_KEY, timeout=_timeout_post)
        return _format_result(r)

    return _format_result({"error": f"unknown tool: {name}"})


def _respond(req_id, result):
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    line = json.dumps(msg)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _error(req_id, code: int, message: str):
    msg = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            _respond(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities":    {"tools": {}},
                "serverInfo":      {"name": "hybrid-coordinator-bridge", "version": "1.0"},
            })
        elif method == "tools/list":
            _respond(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result_text = _call_tool(tool_name, tool_args)
                _respond(req_id, {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                })
            except Exception as exc:
                _respond(req_id, {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                })
        elif method == "notifications/initialized":
            pass  # no response needed
        else:
            _error(req_id, -32601, f"method not found: {method}")


if __name__ == "__main__":
    main()
