#!/usr/bin/env python3
"""
MCP stdio bridge for hybrid-coordinator REST API.
Translates MCP protocol (stdin/stdout) to hybrid-coordinator HTTP calls.
Used by Continue.dev and other MCP stdio clients.

Tools exposed:
  - hybrid_search: semantic search + optional LLM synthesis
  - get_hints: workflow hints for current task
  - workflow_plan: create phased plan using hybrid harness
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

HYBRID_URL = os.getenv("HYBRID_URL", "http://127.0.0.1:8003")
AIDB_URL   = os.getenv("AIDB_URL",   "http://127.0.0.1:8002")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
AQD_BIN = os.path.join(REPO_ROOT, "scripts", "ai", "aqd")

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
                "memory_type": {"type": "string", "enum": ["fact","decision","context"], "default": "fact"},
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
        return json.dumps(r, indent=2)

    if name == "get_hints":
        params = f"?limit={args.get('limit', 3)}"
        q = args.get("q", "")
        if q:
            params += f"&q={urllib.parse.quote(q)}"
        r = _get(f"{HYBRID_URL}/hints{params}", HYBRID_KEY)
        return json.dumps(r, indent=2)

    if name == "workflow_plan":
        r = _post(f"{HYBRID_URL}/workflow/plan", {
            "query": args.get("query", ""),
        }, HYBRID_KEY)
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

    if name == "workflow_blueprints":
        r = _get(f"{HYBRID_URL}/workflow/blueprints", HYBRID_KEY)
        return json.dumps(r, indent=2)

    if name == "aqd_workflows_list":
        r = _run_local([AQD_BIN, "workflows", "list"])
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

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
        return json.dumps(r, indent=2)

    if name == "store_memory":
        r = _post(f"{HYBRID_URL}/memory/store", {
            "content":     args.get("content", ""),
            "agent_id":    args.get("agent_id", "continue"),
            "memory_type": args.get("memory_type", "fact"),
        }, HYBRID_KEY)
        return json.dumps(r, indent=2)

    if name == "recall_memory":
        r = _post(f"{HYBRID_URL}/memory/recall", {
            "query":    args.get("query", ""),
            "agent_id": args.get("agent_id", "continue"),
            "limit":    args.get("limit", 5),
        }, HYBRID_KEY)
        return json.dumps(r, indent=2)

    if name == "query_aidb":
        r = _post(f"{AIDB_URL}/query", {
            "query": args.get("query", ""),
            "limit": args.get("limit", 5),
        }, AIDB_KEY)
        return json.dumps(r, indent=2)

    return json.dumps({"error": f"unknown tool: {name}"})


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
