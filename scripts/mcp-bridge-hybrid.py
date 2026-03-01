#!/usr/bin/env python3
"""
MCP stdio bridge for hybrid-coordinator REST API.
Translates MCP protocol (stdin/stdout) to hybrid-coordinator HTTP calls.
Used by Continue.dev and other MCP stdio clients.

Tools exposed:
  - hybrid_search: semantic search + optional LLM synthesis
  - get_hints: workflow hints for current task
  - store_memory: store agent memory
  - recall_memory: retrieve agent memory
  - query_aidb: search AIDB knowledge base
"""
import asyncio
import json
import os
import sys
import urllib.request
import urllib.error

HYBRID_URL = os.getenv("HYBRID_URL", "http://127.0.0.1:8003")
AIDB_URL   = os.getenv("AIDB_URL",   "http://127.0.0.1:8002")

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
    import urllib.parse  # noqa: needed inside _call_tool
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
