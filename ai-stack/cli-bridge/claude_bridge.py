#!/usr/bin/env python3
"""
CLI bridge: OpenAI-compatible /v1/chat/completions endpoint backed by local CLI tools.

Routes requests to CLI binaries that authenticate via their own OAuth sessions —
no API keys stored anywhere. Currently supports:
  - claude (claude --print, Claude Code OAuth → claude.ai Pro)
  - codex  (codex exec, Codex CLI OAuth → ChatGPT Plus)

All tokens and credentials are managed exclusively by each CLI tool's own
keychain/OAuth flow. This service just bridges HTTP ↔ subprocess.

Port: configured by CLI_BRIDGE_PORT env (default 8089)
"""
import asyncio
import json
import os
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude").strip()
CODEX_BIN  = os.environ.get("CODEX_BIN", "codex").strip()
PORT       = int(os.environ.get("CLI_BRIDGE_PORT", "8089"))
HOST       = os.environ.get("CLI_BRIDGE_HOST", "127.0.0.1").strip()
# Hard cap: CLI processes can be slow; 300s matches llama.cpp timeout
CLI_TIMEOUT_S = float(os.environ.get("CLI_BRIDGE_TIMEOUT_S", "300"))

app = FastAPI(title="CLI Bridge")


def _messages_to_prompt(messages: list) -> tuple[str, str]:
    """Convert OpenAI messages to (system_prompt, user_prompt) for CLI stdin."""
    system_parts: list[str] = []
    turns: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
            )
        content = str(content).strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            turns.append(f"Human: {content}")
        elif role == "assistant":
            turns.append(f"Assistant: {content}")
    return "\n\n".join(system_parts), "\n\n".join(turns)


def _wrap_response(content: str, model_id: str) -> dict:
    return {
        "id": f"cli-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _call_claude(messages: list) -> str:
    system_prompt, user_prompt = _messages_to_prompt(messages)
    cmd = [
        CLAUDE_BIN,
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=user_prompt.encode()),
            timeout=CLI_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"claude CLI timed out after {CLI_TIMEOUT_S}s")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"claude exited {proc.returncode}: {err}")

    try:
        data = json.loads(stdout.decode(errors="replace"))
        return str(data.get("result", ""))
    except json.JSONDecodeError:
        return stdout.decode(errors="replace").strip()


async def _call_codex(messages: list) -> str:
    _, user_prompt = _messages_to_prompt(messages)
    cmd = [
        CODEX_BIN,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        user_prompt,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=CLI_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"codex CLI timed out after {CLI_TIMEOUT_S}s")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"codex exited {proc.returncode}: {err}")

    return stdout.decode(errors="replace").strip()


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "cli-bridge",
        "backends": {
            "claude": CLAUDE_BIN,
            "codex": CODEX_BIN,
        },
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": {"message": "invalid JSON body"}}, status_code=400)

    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": {"message": "messages required"}}, status_code=400)

    model = str(body.get("model", "")).strip().lower()
    use_codex = "codex" in model

    try:
        if use_codex:
            content = await _call_codex(messages)
            model_id = "codex-cli"
        else:
            content = await _call_claude(messages)
            model_id = "claude-cli"
    except RuntimeError as exc:
        return JSONResponse(
            {"error": {"message": str(exc), "type": "cli_error"}},
            status_code=500,
        )

    return JSONResponse(_wrap_response(content, model_id))


@app.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": "claude-cli", "object": "model", "created": 0, "owned_by": "local-cli"},
            {"id": "codex-cli",  "object": "model", "created": 0, "owned_by": "local-cli"},
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, timeout_graceful_shutdown=5)
