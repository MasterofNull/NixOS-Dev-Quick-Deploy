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
import json
import os
import subprocess
import sys
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


def _post(url: str, payload: dict, key: str) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.reason, "status": e.code}
    except Exception as e:
        return {"error": str(e)}


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def _run_local(argv: list[str], cwd: str | None = None) -> dict:
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
        )
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
]


def _call_tool(name: str, args: dict) -> str:
    if name == "hybrid_search":
        r = _post(f"{HYBRID_URL}/query", {
            "query":             args.get("query", ""),
            "mode":              args.get("mode", "auto"),
            "prefer_local":      True,
            "limit":             args.get("limit", 5),
            "generate_response": args.get("generate_response", False),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "get_hints":
        params = f"?limit={args.get('limit', 3)}"
        q = args.get("q", "")
        if q:
            params += f"&q={urllib.parse.quote(q)}"
        r = _get(f"{HYBRID_URL}/hints{params}", HYBRID_KEY)
        return _format_result(r)

    if name == "workflow_plan":
        r = _post(f"{HYBRID_URL}/workflow/plan", {
            "query": args.get("query", ""),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "tooling_manifest":
        r = _post(f"{HYBRID_URL}/workflow/tooling-manifest", {
            "query": args.get("query", ""),
            "runtime": args.get("runtime", "python"),
            "max_tools": int(args.get("max_tools", 6)),
            "max_result_chars": int(args.get("max_result_chars", BRIDGE_MAX_RESULT_CHARS)),
        }, HYBRID_KEY)
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
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "workflow_blueprints":
        r = _get(f"{HYBRID_URL}/workflow/blueprints", HYBRID_KEY)
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
        argv = [
            AQD_BIN,
            "workflows",
            "project-init",
            "--target",
            str(args.get("target_dir", ".")),
        ]
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
        r = _run_local(argv)
        return _format_result(r)

    if name == "primer_workflow":
        argv = [
            AQD_BIN,
            "workflows",
            "primer",
            "--target",
            str(args.get("target_dir", ".")),
        ]
        if args.get("objective"):
            argv.extend(["--objective", str(args.get("objective"))])
        if args.get("output"):
            argv.extend(["--output", str(args.get("output"))])
        r = _run_local(argv)
        return _format_result(r)

    if name == "brownfield_workflow":
        argv = [
            AQD_BIN,
            "workflows",
            "brownfield",
            "--target",
            str(args.get("target_dir", ".")),
        ]
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
        r = _run_local(argv)
        return _format_result(r)

    if name == "retrofit_workflow":
        argv = [
            AQD_BIN,
            "workflows",
            "retrofit",
            "--target",
            str(args.get("target_dir", ".")),
        ]
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
        r = _run_local(argv)
        return _format_result(r)

    if name == "store_memory":
        r = _post(f"{HYBRID_URL}/memory/store", {
            "content":     args.get("content", ""),
            "agent_id":    args.get("agent_id", "continue"),
            "memory_type": _normalize_memory_type(args.get("memory_type", "semantic")),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "recall_memory":
        r = _post(f"{HYBRID_URL}/memory/recall", {
            "query":    args.get("query", ""),
            "agent_id": args.get("agent_id", "continue"),
            "limit":    args.get("limit", 5),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "query_aidb":
        r = _post(f"{AIDB_URL}/query", {
            "query": args.get("query", ""),
            "limit": args.get("limit", 5),
        }, AIDB_KEY)
        return _format_result(r)

    if name == "augment_query":
        r = _post(f"{HYBRID_URL}/augment_query", {
            "query":   args.get("query", ""),
            "context": args.get("context", {}),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "qa_check":
        phase = int(args.get("phase", 0))
        r = _post(f"{HYBRID_URL}/qa/check", {"phase": phase}, HYBRID_KEY)
        return _format_result(r)

    if name == "hints_feedback":
        r = _post(f"{HYBRID_URL}/hints/feedback", {
            "hint_id":  args.get("hint_id", ""),
            "accepted": bool(args.get("accepted", False)),
            "comment":  args.get("comment", ""),
        }, HYBRID_KEY)
        return _format_result(r)

    if name == "coordinator_status":
        r = _get(f"{HYBRID_URL}/control/ai-coordinator/status", HYBRID_KEY)
        return _format_result(r)

    if name == "coordinator_lessons":
        limit = int(args.get("limit", 10))
        r = _get(f"{HYBRID_URL}/control/ai-coordinator/lessons?limit={limit}", HYBRID_KEY)
        return _format_result(r)

    if name == "get_prsi_pending":
        r = _get(f"{HYBRID_URL}/control/prsi/pending", HYBRID_KEY)
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
        r = _post(f"{HYBRID_URL}/qa/check", {"phase": phase}, HYBRID_KEY)
        return _format_result(r)

    if name == "web_fetch":
        r = _post(f"{HYBRID_URL}/research/web/fetch", {
            "url":       args.get("url", ""),
            "max_chars": int(args.get("max_chars", 4000)),
        }, HYBRID_KEY)
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
        }, HYBRID_KEY)
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
        r = _get(f"{AIDB_URL}/skills{params}", AIDB_KEY)
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
        r = _get(f"{HYBRID_URL}/skills/{slug}/content", HYBRID_KEY)
        return _format_result(r)

    if name == "auto_select_tools":
        task = args.get("task", "")
        limit = int(args.get("limit", 8))
        params = f"?task={urllib.parse.quote(task)}&limit={limit}"
        r = _get(f"{HYBRID_URL}/tools/auto-select{params}", HYBRID_KEY)
        return _format_result(r)

    if name == "tool_catalog":
        domain = args.get("domain", "all")
        fmt = args.get("format", "compact")
        params = f"?domain={domain}&format={fmt}"
        r = _get(f"{HYBRID_URL}/tools/catalog{params}", HYBRID_KEY)
        return _format_result(r)

    if name == "trading_analyze":
        ticker = args.get("ticker", "").upper()
        date = args.get("date", "")
        analysts = args.get("analysts", "market,fundamentals,news,sentiment")
        rounds = int(args.get("debate_rounds", 1))
        params = f"?ticker={ticker}&date={date}&analysts={analysts}&debate_rounds={rounds}"
        r = _get(f"{HYBRID_URL}/trading/analyze{params}", HYBRID_KEY)
        return _format_result(r)

    if name == "trading_forecast":
        ticker = args.get("ticker", "").upper()
        date = args.get("date", "")
        r = _get(f"{HYBRID_URL}/trading/forecast?ticker={ticker}&date={date}", HYBRID_KEY)
        return _format_result(r)

    if name == "trading_tools":
        r = _get(f"{HYBRID_URL}/trading/tools", HYBRID_KEY)
        return _format_result(r)

    if name == "impeccable_design":
        command = args.get("command", "audit")
        context = args.get("context", "")
        ref_query = args.get("reference_query", f"{command} design reference")
        # Retrieve reference docs from AIDB
        ref = _post(f"{AIDB_URL}/query", {
            "query": ref_query,
            "project": "impeccable-design",
            "limit": 3,
        }, AIDB_KEY)
        # Get skill content
        skill = _get(f"{HYBRID_URL}/skills/impeccable/content", HYBRID_KEY)
        return _format_result({
            "command": command,
            "context": context,
            "reference_docs": ref,
            "skill_guidance": skill.get("content", "") if isinstance(skill, dict) else str(skill)[:500],
            "anti_pattern_scan": "Run: npx impeccable detect <target-path>",
            "http_api": f"POST {HYBRID_URL}/query with project=impeccable-design",
        })

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
