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

import session_transcripts

logger = logging.getLogger("hybrid-coordinator")

# Compatibility alias
_extract_history = session_transcripts.extract_history




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
        session: str | List[Dict[str, str]] | Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Handle dict payload (client-side extracted: {"history": [...], "session_hash": str, "session_path": str})
        if isinstance(session, dict):
            return await self._crystallize_dict_payload(session)
        # Handle file path (legacy, server-side extraction)
        if isinstance(session, str):
            return await self._crystallize_file_session(session)
        # Handle in-memory history list
        return await self._crystallize_history(session, metadata=metadata)

    async def _crystallize_dict_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process client-submitted history dict with validation and deduplication."""
        session_hash = payload.get("session_hash", "").strip()
        session_path = payload.get("session_path", "").strip()
        history = payload.get("history", [])

        # Validate inputs
        if not isinstance(history, list):
            return {"status": "error", "reason": "history_not_list"}
        if len(history) < 4:
            return {"status": "skipped", "reason": "history_too_short"}

        # Validate each message: must have role in {user, assistant} and str content
        validated_history = []
        for msg in history[:20]:  # Cap at 20 items
            if isinstance(msg, dict):
                role = msg.get("role", "").strip()
                content = msg.get("content", "")
                if role in {"user", "assistant"} and isinstance(content, str):
                    # Re-apply redaction server-side for defense in depth
                    content = session_transcripts.redact_secrets(content.strip())[:1200]
                    if content:
                        validated_history.append({"role": role, "content": content})

        if len(validated_history) < 4:
            return {"status": "skipped", "reason": "history_too_short"}

        # Dedupe on session_hash if provided
        if session_hash:
            await self.ensure_schema()
            if await self._already_processed(session_hash):
                return {"status": "already_processed", "session_hash": session_hash, "insights_stored": 0}

        # Distill the history
        result = await self._crystallize_history(
            validated_history,
            metadata={"session_path": session_path, "session_hash": session_hash}
        )

        # Record hash only on success/skip
        if session_hash and result.get("status") in {"complete", "skipped"}:
            if self._pg is not None:
                try:
                    await self._pg.execute(
                        """
                        INSERT INTO crystallized_sessions
                            (session_hash, session_path, insights_stored, processed_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        session_hash,
                        session_path,
                        result.get("facts_stored", 0),
                        datetime.now(timezone.utc).isoformat(),
                    )
                except Exception:
                    pass  # Ignore DB errors on hash recording
            self._processed[session_hash] = {
                "session_hash": session_hash,
                "session_path": session_path,
                "insights_stored": result.get("facts_stored", 0),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._insights_stored += result.get("facts_stored", 0)

        return {
            "status": result.get("status"),
            "session_hash": session_hash or None,
            "insights_stored": result.get("facts_stored", 0)
        }

    async def _crystallize_file_session(self, session_path: str) -> Dict[str, Any]:
        path = Path(session_path).expanduser()
        if not path.is_file():
            raise ValueError("session_path must point to an existing file")

        try:
            raw = path.read_bytes()
        except (PermissionError, OSError) as exc:
            return {"status": "error", "reason": "unreadable_session_path", "detail": str(exc)}

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
        history = data.get("history")

        # Support either session_path (legacy) or history+session_hash+session_path (client-side).
        # When both are present, history takes priority (dict payload branch avoids file read).
        if history:
            # Client-side extracted history: session_path is just provenance, never used for file read
            if not isinstance(history, list):
                raise ValueError("history must be a list")
            payload = {
                "history": history,
                "session_hash": str(data.get("session_hash") or "").strip(),
                "session_path": session_path,
            }
        elif session_path:
            # Legacy file-path branch (server-side extraction, may hit PermissionError)
            payload = session_path
        else:
            raise ValueError("either session_path or history required")

        # Wrap background task to log exceptions
        async def _wrapped_crystallize():
            try:
                await _crystallizer.crystallize_session(payload)
            except Exception as exc:
                logger.warning("memory_crystallizer: background task exception: %s", exc)

        asyncio.create_task(_wrapped_crystallize())
        return web.json_response({"accepted": True}, status=202)
    except ValueError as exc:
        return web.json_response({"error": "memory_crystalline_invalid", "detail": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("memory_crystalline_run_failed")
        return web.json_response({"error": "memory_crystalline_run_failed", "detail": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/memory/crystalline/status", handle_memory_crystalline_status)
    http_app.router.add_post("/memory/crystalline/run", handle_memory_crystalline_run)
