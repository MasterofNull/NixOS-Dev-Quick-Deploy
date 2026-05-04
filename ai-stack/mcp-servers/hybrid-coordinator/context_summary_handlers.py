"""
context_summary_handlers.py - Agent context summarization endpoint

POST /agent/summarize-context    - compress history to structured summary
POST /agent/working-memory/save  - persist key session facts
GET  /agent/working-memory       - retrieve working memory sidecar
DELETE /agent/working-memory     - clear working memory
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from aiohttp import web

logger = logging.getLogger("context-summary")

WORKING_MEMORY_PATH = Path("/var/lib/nixos-ai-stack/agent/working_memory.json")


def _extractive_summary(
    history: list[dict[str, Any]],
    max_tokens: int = 2000,
    focus: str = "all",
) -> dict[str, Any]:
    chars_budget = max_tokens * 4
    user_turns = [m["content"] for m in history if m.get("role") == "user"]
    assistant_turns = [m["content"] for m in history if m.get("role") == "assistant"]

    decision_re = re.compile(
        r"(decided|will|done|completed|fixed|added|created|committed|resolved|PASS|FAIL)",
        re.IGNORECASE,
    )
    open_q_re = re.compile(
        r"(TODO|FIXME|pending|unclear|need to|should|consider|investigate)",
        re.IGNORECASE,
    )
    next_step_re = re.compile(
        r"(next step|following|P\\d{2}-\\d{3}|step \\d)",
        re.IGNORECASE,
    )

    key_decisions: list[str] = []
    open_questions: list[str] = []
    next_steps: list[str] = []

    for turn in assistant_turns:
        for line in turn.split("\n"):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            if decision_re.search(line):
                key_decisions.append(line[:200])
            if open_q_re.search(line):
                open_questions.append(line[:200])
            if next_step_re.search(line):
                next_steps.append(line[:200])

    key_decisions = list(dict.fromkeys(key_decisions))[:10]
    open_questions = list(dict.fromkeys(open_questions))[:10]
    next_steps = list(dict.fromkeys(next_steps))[:8]

    summary_parts = []
    if user_turns:
        summary_parts.append("Session objective: " + user_turns[0][:300])
    if len(user_turns) > 1:
        summary_parts.append("Latest request: " + user_turns[-1][:300])
    if assistant_turns:
        summary_parts.append("Last output: " + assistant_turns[-1][:500])

    summary = " | ".join(summary_parts)
    if len(summary) > chars_budget:
        summary = summary[:chars_budget] + "...[truncated]"

    return {
        "summary": summary,
        "key_decisions": key_decisions,
        "open_questions": open_questions,
        "next_steps": next_steps,
        "original_turns": len(history),
        "compressed_tokens": len(summary) // 4,
        "strategy": "extractive",
    }


async def _llm_summary(
    history: list[dict[str, Any]],
    max_tokens: int,
    focus: str,
    coordinator: Any,
) -> dict[str, Any]:
    try:
        import aiohttp as _aiohttp
        lines = [
            "Output ONLY valid JSON: {summary, key_decisions, open_questions, next_steps}.",
            f"Focus: {focus}.",
            "--- HISTORY ---",
        ]
        for msg in history[-12:]:
            role = msg.get("role", "user")
            content = str(msg.get("content", ""))[:600]
            lines.append(f"[{role}]: {content}")
        lines.append("--- END ---\nJSON:")
        payload = {
            "model": "active.gguf",
            "messages": [{"role": "user", "content": "\n".join(lines)}],
            "max_tokens": min(max_tokens, 800),
            "temperature": 0.1,
        }
        async with _aiohttp.ClientSession() as sess:
            async with sess.post(
                "http://127.0.0.1:8080/v1/chat/completions",
                json=payload,
                timeout=_aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    m = re.search(r"\{.*\}", raw, re.DOTALL)
                    if m:
                        result = json.loads(m.group())
                        result["original_turns"] = len(history)
                        result["compressed_tokens"] = len(str(result.get("summary", ""))) // 4
                        result["strategy"] = "llm"
                        return result
    except Exception as exc:
        logger.warning("LLM summary failed, falling back to extractive: %s", exc)
    return _extractive_summary(history, max_tokens, focus)


async def handle_summarize_context(request: web.Request) -> web.Response:
    """POST /agent/summarize-context"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    history = body.get("history") or []
    if not history or not isinstance(history, list):
        return web.json_response({"error": "history must be a non-empty list"}, status=400)
    max_tokens = int(body.get("max_tokens") or 2000)
    focus = str(body.get("focus") or "all")
    use_llm = bool(body.get("use_llm", True))
    coordinator = request.app.get("coordinator")
    if use_llm and coordinator is not None:
        result = await _llm_summary(history, max_tokens, focus, coordinator)
    else:
        result = _extractive_summary(history, max_tokens, focus)
    return web.json_response(result)


async def handle_save_working_memory(request: web.Request) -> web.Response:
    """POST /agent/working-memory/save"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    entry = {
        "session_id": body.get("session_id", "default"),
        "timestamp": time.time(),
        "key_facts": (body.get("key_facts") or [])[:50],
        "decisions": (body.get("decisions") or [])[:50],
        "next_steps": (body.get("next_steps") or [])[:20],
        "open_questions": (body.get("open_questions") or [])[:20],
        "metadata": body.get("metadata") or {},
    }
    try:
        WORKING_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(WORKING_MEMORY_PATH, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, indent=2)
    except OSError as exc:
        return web.json_response({"error": f"failed to write: {exc}"}, status=500)
    return web.json_response({"ok": True, "path": str(WORKING_MEMORY_PATH), "session_id": entry["session_id"]})


async def handle_get_working_memory(request: web.Request) -> web.Response:
    """GET /agent/working-memory"""
    if not WORKING_MEMORY_PATH.exists():
        return web.json_response({
            "ok": False,
            "message": "No working memory. POST /agent/working-memory/save to persist context.",
            "path": str(WORKING_MEMORY_PATH),
        })
    try:
        with open(WORKING_MEMORY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return web.json_response(data)
    except Exception as exc:
        return web.json_response({"error": f"failed to read: {exc}"}, status=500)


async def handle_clear_working_memory(request: web.Request) -> web.Response:
    """DELETE /agent/working-memory"""
    try:
        if WORKING_MEMORY_PATH.exists():
            WORKING_MEMORY_PATH.unlink()
        return web.json_response({"ok": True, "cleared": True})
    except OSError as exc:
        return web.json_response({"error": f"failed to clear: {exc}"}, status=500)


def register_routes(http_app: web.Application) -> None:
    """Register context summary routes on the aiohttp app."""
    http_app.router.add_post("/agent/summarize-context", handle_summarize_context)
    http_app.router.add_post("/agent/working-memory/save", handle_save_working_memory)
    http_app.router.add_get("/agent/working-memory", handle_get_working_memory)
    http_app.router.add_delete("/agent/working-memory", handle_clear_working_memory)
    logger.info("context_summary_handlers: routes registered")
