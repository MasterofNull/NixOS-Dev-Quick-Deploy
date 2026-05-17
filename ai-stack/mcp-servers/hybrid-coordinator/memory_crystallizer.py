"""
memory_crystallizer.py — Session distillation and knowledge extraction (Phase 55.2)

Provides 'crystallization': the process of distilling volatile chat history
into persistent, atomic 'crystalline' facts in semantic memory.

Benefits:
  - Reduces context window saturation.
  - Fixes the 'Goldfish Effect' (forgetting early parts of a long session).
  - Enables cross-session knowledge persistence.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_memory_broker: Optional[Any] = None
_llama_client: Optional[Any] = None
_postgres_client: Optional[Any] = None
_store_insight_fn: Optional[Callable] = None

def init(
    broker: Optional[Any] = None, 
    llama_client: Optional[Any] = None,
    postgres_client: Optional[Any] = None,
    store_insight_fn: Optional[Callable] = None
) -> None:
    global _memory_broker, _llama_client, _postgres_client, _store_insight_fn
    if broker: _memory_broker = broker
    if llama_client: _llama_client = llama_client
    if postgres_client: _postgres_client = postgres_client
    if store_insight_fn: _store_insight_fn = store_insight_fn
    logger.info("memory_crystallizer: initialized (Phase 55.2 Active)")


class MemoryCrystallizer:
    """
    Distills conversational context into permanent knowledge.
    """

    def __init__(self) -> None:
        pass

    async def ensure_schema(self) -> None:
        """Create crystallized sessions table if it doesn't exist."""
        if not _postgres_client:
            return

        ddl = """
        CREATE TABLE IF NOT EXISTS crystallized_sessions (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            session_hash TEXT NOT NULL,
            facts_count INTEGER NOT NULL,
            crystallized_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_crystallized_session ON crystallized_sessions(session_id);
        """
        try:
            await _postgres_client.execute(ddl)
            logger.info("memory_crystallizer: PostgreSQL schema verified")
        except Exception as exc:
            logger.warning("memory_crystallizer: schema init failed: %s", exc)

    async def crystallize_session(self, history: List[Dict[str, str]], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract facts from history and store them via MemoryBroker.
        """
        if not history or len(history) < 4:
            return {"status": "skipped", "reason": "history_too_short"}

        if not _llama_client or not _memory_broker:
            return {"status": "error", "reason": "dependencies_not_met"}

        # 1. Generate distillation prompt
        prompt = self._build_distillation_prompt(history)
        
        try:
            # 2. Call LLM for extraction
            response = await _llama_client.create_message(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1, # low temp for factual extraction
                system="You are a Knowledge Crystallizer."
            )
            
            # 3. Parse facts (Expect one fact per line)
            raw_text = response.content
            facts = [f.strip("- ").strip() for f in raw_text.split("\n") if len(f.strip()) > 10]
            
            # 4. Store each fact as a 'crystalline' semantic memory
            stored_count = 0
            for fact in facts:
                # Crystalline facts have long TTL or are perpetual
                res = await _memory_broker.write(
                    memory_type="semantic",
                    content=fact,
                    context={
                        "crystallized_from": metadata.get("session_id") if metadata else "unknown",
                        "distillation_date": datetime.now(timezone.utc).isoformat(),
                        "crystalline": True
                    },
                    source="crystallizer"
                )
                if res.get("status") in ["stored", "success"]:
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
                "history_length": len(history)
            }

        except Exception as exc:
            logger.warning("memory_crystallizer: distillation failed: %s", exc)
            return {"status": "error", "detail": str(exc)}

    def _build_distillation_prompt(self, history: List[Dict[str, str]]) -> str:
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-20:]]) # last 20 messages
        return f"""<|im_start|>system
You are a 'Knowledge Crystallizer'. Your job is to extract atomic, permanent facts from the following chat history.
Avoid duplicates. Be concise. Output ONLY a bulleted list of facts.

HISTORY:
{history_text}

EXTRACTED FACTS:
- <|im_end|>
<|im_start|>assistant
- """

# Singleton accessor
_instance: Optional[MemoryCrystallizer] = None

def get_crystallizer() -> MemoryCrystallizer:
    global _instance
    if _instance is None:
        _instance = MemoryCrystallizer()
    return _instance
