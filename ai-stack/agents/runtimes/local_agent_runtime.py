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
    if TOOLS_ENABLED:
        payload["tools"] = TOOL_SCHEMAS
        payload["tool_choice"] = "auto"
    return payload


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
    try:
        return await client.post(inference_url, json=payload, headers=headers)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        state["fallback_backend"] = "llama.cpp"
        state["fallback_reason"] = "switchboard_unreachable"
        _write_state(state)
        return await client.post(
            f"{LLAMA_CPP_URL}/v1/chat/completions",
            json=_payload_for_direct_llama(payload),
            headers={},
        )


def _streaming_payload(messages: list[dict]) -> dict:
    return {
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "stop": STOP_SEQUENCES,
    }


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
                    return "\n".join(
                        f"[{i+1}] {res.get('content', '')[:400]}"
                        for i, res in enumerate(results[:limit])
                    )
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
                    return "\n".join(
                        f"[{i+1}] {res.get('content', '')[:400]}"
                        for i, res in enumerate(results[:5])
                    )
                return "No memories found."
            return f"recall_memory error: HTTP {r.status_code}"
        return f"unknown_tool: {name}"
    except Exception as exc:
        return f"tool_error({name}): {exc}"


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
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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
        state.update({"status": "failed", "error": str(exc), "completed_at": time.time()})
        _write_state(state)
        print(
            json.dumps({"ok": False, "error": str(exc), "agent_id": AGENT_ID}),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
