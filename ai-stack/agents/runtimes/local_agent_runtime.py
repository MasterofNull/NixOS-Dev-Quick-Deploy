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
  AGENT_MAX_TOOL_ROUNDS — max tool-call rounds (default 3)
  AGENT_STREAMING       — "true" | "false" (SSE streaming mode)
  SWITCHBOARD_URL       — inference router (default localhost:8085)
  LLAMA_CPP_URL         — direct llama.cpp fallback (default localhost:8080)
  HYBRID_URL            — hybrid-coordinator base URL (default localhost:8003)
"""

import asyncio
import json
import os
import pathlib
import shutil
import sys
import time

import httpx

AGENT_ID = os.environ["AGENT_ID"]
AGENT_ROLE = os.environ["AGENT_ROLE"]
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
AGENT_TASK = os.environ["AGENT_TASK"]
SWITCHBOARD_URL = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085")
LLAMA_CPP_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080")
HYBRID_URL = os.environ.get("HYBRID_URL", "http://127.0.0.1:8003")
STATE_FILE = os.environ.get("AGENT_STATE_FILE", "")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "768"))
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))
AGENT_TIMEOUT = float(os.environ.get("AGENT_TIMEOUT", "240"))

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
MAX_TOOL_ROUNDS = int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", "3"))
STREAMING_MODE = (
    os.environ.get("AGENT_STREAMING", "false").lower() == "true" and not TOOLS_ENABLED
)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_ARG_BLOCKLIST_CHARS = set(";&|><`\n\r")
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

# OpenAI-compatible tool schemas for harness endpoints (loopback auth bypass applies)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "route_search",
            "description": "Search the codebase and project documentation for relevant context using semantic and keyword RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
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
    {
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
]


def _profile_for_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized == "coder":
        return "local-tool-calling"
    # continue-local has ~150-char system prompt vs local-agent ~2000-char.
    # Lighter profile avoids >300s prefill overhead for simple delegate tasks.
    return "continue-local"


def _write_state(state: dict) -> None:
    if STATE_FILE:
        p = pathlib.Path(STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))


def _build_inference_payload(messages: list[dict]) -> dict:
    payload: dict = {
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "stop": STOP_SEQUENCES,
    }
    if not _thinking_on:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    if TOOLS_ENABLED:
        payload["tools"] = TOOL_SCHEMAS
        payload["tool_choice"] = "auto"
    return payload


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


async def _post_completion_with_fallback(
    client: httpx.AsyncClient,
    *,
    payload: dict,
    headers: dict,
    state: dict,
) -> httpx.Response:
    inference_url = f"{SWITCHBOARD_URL}/v1/chat/completions"
    start_time = time.perf_counter()
    try:
        resp = await client.post(inference_url, json=payload, headers=headers)
        state["inference_latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return resp
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        state["fallback_backend"] = "llama.cpp"
        state["fallback_reason"] = "switchboard_timeout_or_unreachable"
        _write_state(state)
        start_time = time.perf_counter()
        resp = await client.post(
            f"{LLAMA_CPP_URL}/v1/chat/completions",
            json=_payload_for_direct_llama(payload),
            headers={},
            timeout=AGENT_TIMEOUT
        )
        state["inference_latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return resp


def _streaming_payload(messages: list[dict]) -> dict:
    payload = {
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "stop": STOP_SEQUENCES,
    }
    if not _thinking_on:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return payload


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
        profile = "local-tool-calling" if TOOLS_ENABLED else _profile_for_role(AGENT_ROLE)
        headers = {"X-AI-Profile": profile, "X-AI-Route": "local"}
        content = ""
        data: dict = {}

        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
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
                sys.stdout.write(
                    json.dumps({"done": True, "ok": True, "content": content, "agent_id": AGENT_ID})
                    + "\n"
                )
                sys.stdout.flush()
                return

            max_rounds = MAX_TOOL_ROUNDS if TOOLS_ENABLED else 1
            for _round in range(max_rounds):
                resp = await _post_completion_with_fallback(
                    client,
                    payload=_build_inference_payload(messages),
                    headers=headers,
                    state=state,
                )
                if resp.status_code == 503:
                    try:
                        err_body = resp.json()
                    except Exception:
                        err_body = {}
                    if (err_body.get("error") or {}).get("type") == "local_slot_busy":
                        raise RuntimeError("local_slot_busy")
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    content = (msg.get("content") or "").strip()
                    if not content:
                        content = (msg.get("reasoning_content") or "").strip()
                    break
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
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": tc_result,
                    })
                    state["tool_calls"] += 1
                    _write_state(state)
            else:
                if not content:
                    last_msg = messages[-1] if messages else {}
                    content = str(last_msg.get("content") or "")

        state.update({
            "status": "completed",
            "result": content,
            "completed_at": time.time(),
            "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason", "stop"),
        })
        _write_state(state)
        print(json.dumps({"ok": True, "content": content, "agent_id": AGENT_ID}))

    except Exception as exc:
        error_text = str(exc)
        if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)) or not error_text:
            error_text = "local_agent_timeout"
        state.update({"status": "failed", "error": error_text, "completed_at": time.time()})
        _write_state(state)
        print(
            json.dumps({"ok": False, "error": error_text, "agent_id": AGENT_ID}),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
