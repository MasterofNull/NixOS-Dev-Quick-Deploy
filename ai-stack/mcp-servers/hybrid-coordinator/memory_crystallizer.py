"""Unified Phase 55 session crystallization service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")


def _extract_history(raw: bytes) -> List[Dict[str, str]]:
    """Extract chat history from multiple session formats.

    Parses Claude Code JSONL, Codex JSONL, and Continue JSON formats,
    extracting only text content. Returns the last 20 messages (≤1200 chars each).
    """
    messages: List[Dict[str, str]] = []
    raw_str = raw.decode("utf-8", errors="replace")

    # Try JSONL formats (Claude Code / Codex)
    for line in raw_str.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        # Claude Code JSONL: type in ["user", "assistant"], message.content is str or list of blocks
        if obj.get("type") in {"user", "assistant"}:
            role = obj["type"]
            msg_obj = obj.get("message", {})
            content = msg_obj.get("content", "")

            # Handle list of blocks (e.g., tool_use, text)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                content = " ".join(text_parts)

            # Truncate to 1200 chars and skip empty
            content = str(content).strip()[:1200]
            if content:
                messages.append({"role": role, "content": content})

        # Codex JSONL: type=="response_item", payload.type=="message", payload.role in ["user", "assistant"]
        elif obj.get("type") == "response_item":
            payload = obj.get("payload", {})
            if payload.get("type") == "message" and payload.get("role") in {"user", "assistant"}:
                role = payload["role"]
                content_list = payload.get("content", [])
                text_parts = []
                if isinstance(content_list, list):
                    for item in content_list:
                        if isinstance(item, dict) and item.get("type") in {"input_text", "output_text"}:
                            text_parts.append(item.get("text", ""))
                content = " ".join(text_parts).strip()[:1200]
                if content:
                    messages.append({"role": role, "content": content})

    # Try single-object Continue JSON format
    if not messages:
        try:
            obj = json.loads(raw_str)
            if isinstance(obj, dict) and "history" in obj:
                history_list = obj["history"]
                if isinstance(history_list, list):
                    for item in history_list:
                        if isinstance(item, dict):
                            msg = item.get("message", {})
                            if isinstance(msg, dict):
                                role = msg.get("role")
                                content = msg.get("content", "")

                                # Handle str or list of {text}
                                if isinstance(content, list):
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict):
                                            text_parts.append(block.get("text", ""))
                                    content = " ".join(text_parts)

                                content = str(content).strip()[:1200]
                                if role and content:
                                    messages.append({"role": role, "content": content})
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # Return last 20 messages
    return messages[-20:] if messages else []


DDL_CRYSTALLIZED_SESSIONS = """
CREATE TABLE IF NOT EXISTS crystallized_sessions (
    session_hash      TEXT PRIMARY KEY,
    session_path      TEXT NOT NULL,
    insights_stored   INTEGER NOT NULL DEFAULT 0,
    processed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crystallized_sessions_processed_at
    ON crystallized_sessions (processed_at DESC);
"""


class MemoryCrystallizer:
    """Unified crystallizer for file-backed sessions and in-memory chat history."""

    def __init__(
        self,
        postgres_client: Optional[Any] = None,
        *,
        broker: Optional[Any] = None,
        llama_client: Optional[Any] = None,
        store_insight_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    ) -> None:
        self._pg = postgres_client
        self._broker = broker
        self._llama_client = llama_client
        self._store_insight = store_insight_fn
        self._schema_ready = False
        self._processed: Dict[str, Dict[str, Any]] = {}
        self._last_run: Optional[str] = None
        self._insights_stored = 0

    @property
    def broker(self) -> Optional[Any]:
        """Return the wired MemoryBroker, dynamically resolving from memory_broker module if unset."""
        if self._broker is not None:
            return self._broker
        try:
            import memory_broker
            self._broker = memory_broker.get_broker()
            return self._broker
        except Exception:
            return None

    async def ensure_schema(self) -> None:
        if self._schema_ready or self._pg is None:
            return
        await self._pg.execute(DDL_CRYSTALLIZED_SESSIONS)
        self._schema_ready = True
        logger.info("memory_crystallizer: PostgreSQL schema verified")

    async def crystallize_session(
        self,
        session: str | List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if isinstance(session, str):
            return await self._crystallize_file_session(session)
        return await self._crystallize_history(session, metadata=metadata)

    async def _crystallize_file_session(self, session_path: str) -> Dict[str, Any]:
        path = Path(session_path).expanduser()
        if not path.is_file():
            raise ValueError("session_path must point to an existing file")

        raw = path.read_bytes()
        session_hash = hashlib.sha256(raw).hexdigest()
        await self.ensure_schema()
        if await self._already_processed(session_hash):
            return {"status": "already_processed", "session_hash": session_hash, "insights_stored": 0}

        history = _extract_history(raw)
        result = await self._crystallize_history(
            history,
            metadata={"session_path": str(path), "session_hash": session_hash}
        )

        # Record hash only on success/skip (retry on dependency/LLM errors)
        if result.get("status") in {"complete", "skipped"}:
            if self._pg is not None:
                await self._pg.execute(
                    """
                    INSERT INTO crystallized_sessions
                        (session_hash, session_path, insights_stored, processed_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    session_hash,
                    str(path),
                    result.get("facts_stored", 0),
                    datetime.now(timezone.utc).isoformat(),
                )
            self._processed[session_hash] = {
                "session_hash": session_hash,
                "session_path": str(path),
                "insights_stored": result.get("facts_stored", 0),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._insights_stored += result.get("facts_stored", 0)

        return {
            "status": result.get("status"),
            "session_hash": session_hash,
            "insights_stored": result.get("facts_stored", 0)
        }

    async def _crystallize_history(
        self,
        history: List[Dict[str, str]],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not history or len(history) < 4:
            return {"status": "skipped", "reason": "history_too_short"}
        broker = self.broker
        if self._llama_client is None or broker is None:
            return {"status": "error", "reason": "dependencies_not_met"}

        prompt = self._build_distillation_prompt(history)
        try:
            response = await self._llama_client.create_message(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1,
                system="You are a Knowledge Crystallizer.",
            )
            raw_text = response.content
            # Extract only lines starting with "-" or "*", strip markers, keep max 10
            raw_facts = [
                fact.strip()
                for fact in raw_text.split("\n")
                if fact.strip() and fact.strip()[0] in {"-", "*"}
            ]
            facts = [fact[1:].strip() for fact in raw_facts[:10] if len(fact.strip()) > 10]

            stored_count = 0
            for fact in facts:
                context = {
                    "distillation_date": datetime.now(timezone.utc).isoformat(),
                    "crystalline": True,
                }
                if metadata:
                    # Fallback: session_id > session_path > session_hash
                    context["crystallized_from"] = (
                        metadata.get("session_id")
                        or metadata.get("session_path")
                        or metadata.get("session_hash")
                        or "unknown"
                    )
                    # Include session_path when present
                    if metadata.get("session_path"):
                        context["session_path"] = metadata["session_path"]
                else:
                    context["crystallized_from"] = "unknown"

                result = await broker.write(
                    memory_type="semantic",
                    content=fact,
                    context=context,
                    source="crystallizer",
                )
                if result.get("status") in {"stored", "success"}:
                    stored_count += 1
                    try:
                        from metrics import CRYSTALLIZATION_FACTS_EXTRACTED

                        CRYSTALLIZATION_FACTS_EXTRACTED.inc()
                    except (ImportError, Exception):
                        pass
            logger.info("memory_crystallizer: distilled %d facts from %d messages", stored_count, len(history))
            return {
                "status": "complete",
                "facts_extracted": len(facts),
                "facts_stored": stored_count,
                "history_length": len(history),
            }
        except Exception as exc:
            logger.warning("memory_crystallizer: distillation failed: %s", exc)
            return {"status": "error", "detail": str(exc)}

    async def status(self) -> Dict[str, Any]:
        sessions_processed = len(self._processed)
        if self._pg is not None:
            await self.ensure_schema()
            try:
                rows = await self._pg.fetch_all(
                    """
                    SELECT count(*)::int AS sessions_processed,
                           coalesce(sum(insights_stored), 0)::int AS insights_stored,
                           max(processed_at)::text AS last_run
                    FROM crystallized_sessions
                    """
                )
                if rows:
                    row = dict(rows[0])
                    return {
                        "sessions_processed": row["sessions_processed"],
                        "insights_stored": row["insights_stored"],
                        "last_run": row["last_run"],
                    }
            except Exception as exc:
                logger.warning("memory_crystalline_status_pg_failed error=%s", exc)
        return {
            "sessions_processed": sessions_processed,
            "insights_stored": self._insights_stored,
            "last_run": self._last_run,
        }

    async def _already_processed(self, session_hash: str) -> bool:
        if session_hash in self._processed:
            return True
        if self._pg is None:
            return False
        rows = await self._pg.fetch_all(
            "SELECT session_hash FROM crystallized_sessions WHERE session_hash = %s LIMIT 1",
            session_hash,
        )
        return bool(rows)

    def _build_distillation_prompt(self, history: List[Dict[str, str]]) -> str:
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-20:])
        return f"""You are a Knowledge Crystallizer. Your job is to extract atomic, permanent facts from the following chat history.
Avoid duplicates. Be concise. Output ONLY a bulleted list of 3-10 facts (each fact on one line, prefixed with a dash).

HISTORY:
{history_text}

EXTRACTED FACTS:"""


_crystallizer = MemoryCrystallizer()


def init(
    broker: Optional[Any] = None,
    llama_client: Optional[Any] = None,
    postgres_client: Optional[Any] = None,
    store_insight_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
) -> None:
    global _crystallizer
    _crystallizer = MemoryCrystallizer(
        postgres_client=postgres_client,
        broker=broker,
        llama_client=llama_client,
        store_insight_fn=store_insight_fn,
    )
    logger.info("memory_crystallizer: initialized (Phase 55.2 Active)")


def get_crystallizer() -> MemoryCrystallizer:
    return _crystallizer


async def handle_memory_crystalline_status(_request: web.Request) -> web.Response:
    return web.json_response(await _crystallizer.status())


async def handle_memory_crystalline_run(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        session_path = str(data.get("session_path") or "").strip()
        if not session_path:
            raise ValueError("session_path required")
        asyncio.create_task(_crystallizer.crystallize_session(session_path))
        return web.json_response({"accepted": True, "session_path": session_path}, status=202)
    except ValueError as exc:
        return web.json_response({"error": "memory_crystalline_invalid", "detail": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("memory_crystalline_run_failed")
        return web.json_response({"error": "memory_crystalline_run_failed", "detail": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/memory/crystalline/status", handle_memory_crystalline_status)
    http_app.router.add_post("/memory/crystalline/run", handle_memory_crystalline_run)
