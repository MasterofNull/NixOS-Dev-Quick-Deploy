"""
Agentic Memory Journal — Phase 15.3

Unified auditable journal for all model/agent interactions across free, paid,
remote, and local tiers. Every delegation outcome writes a structured entry
with full provenance metadata so any interaction can be audited by model,
time, task type, outcome, or session.

Backends:
  - Redis list  (hot cache, last 1000 entries, key: journal:entries)
  - AIDB        (persistent, searchable, project: agentic-journal)

Entry schema (all fields always present):
  memory_id       str   — UUID4, globally unique
  timestamp       str   — ISO-8601 UTC
  epoch           float — Unix epoch for fast range queries
  session_id      str   — caller session or request_id
  task_id         str   — delegate task_id or request_id
  task_summary    str   — first 300 chars of task
  task_archetype  str   — inferred capability (coding/reasoning/chat/…)
  model_id        str   — e.g. "anthropic/claude-sonnet-4-6"
  provider        str   — e.g. "Anthropic"
  tier            str   — "free" | "paid_standard" | "paid_premium" | "local"
  profile         str   — switchboard profile used (e.g. "remote-coding")
  runtime_id      str   — coordinator runtime_id
  agent_role      str   — "orchestrator" | "implementer" | "reviewer" | "planner"
  success         bool
  error_code      int   — HTTP error code on failure, 0 on success
  error_msg       str   — first 200 chars of error
  latency_ms      float — wall-clock ms from request to response
  tokens_in       int   — estimated input tokens
  tokens_out      int   — output tokens from response
  outcome_summary str   — first 300 chars of response (for audit)
  fallback_used   bool  — whether this was a failover from another model
  fallback_from   str   — model_id that was tried first (if fallback)

Usage:
    import agentic_memory_journal as journal
    journal.init(redis_client=redis, aidb_url="http://127.0.0.1:8002",
                 aidb_api_key="...")

    entry_id = await journal.write_entry(
        task_summary="implement OAuth2 login",
        task_archetype="coding",
        model_id="anthropic/claude-sonnet-4-6",
        provider="Anthropic",
        tier="paid_standard",
        profile="remote-coding",
        runtime_id="openrouter-coding",
        agent_role="implementer",
        success=True,
        latency_ms=1240,
        tokens_in=312,
        tokens_out=88,
        outcome_summary="Here is the OAuth2 implementation...",
        session_id=request["request_id"],
    )

    entries = await journal.get_entries(limit=50, model_id="anthropic/claude-sonnet-4-6")
    stats   = await journal.get_stats()
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Lazy Redis + AIDB config
# ---------------------------------------------------------------------------
_redis: Optional[Any] = None
_redis_url: str = ""
_aidb_url: str = ""
_aidb_api_key: str = ""


async def _get_redis() -> Optional[Any]:
    global _redis
    if _redis is not None:
        return _redis
    url = _redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis = await aioredis.from_url(url, encoding="utf-8", decode_responses=False)
        logger.info("agentic_memory_journal: Redis connected url=%s", url.split("@")[-1])
    except Exception as exc:
        logger.warning("agentic_memory_journal: Redis connect failed: %s", exc)
        _redis = None
    return _redis

# Redis key for the hot journal list
_JOURNAL_KEY = "journal:entries"
_JOURNAL_MAX_ENTRIES = 1000        # keep last N in Redis
_AIDB_PROJECT = "agentic-journal"
_AIDB_TIMEOUT = 8.0                # seconds

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
def init(
    *,
    redis_url: str = "",
    aidb_url: str = "",
    aidb_api_key: str = "",
) -> None:
    """Configure backends. Call once at startup; Redis connection is lazy."""
    global _redis_url, _redis, _aidb_url, _aidb_api_key
    _redis_url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
    _redis = None  # reset so next call reconnects
    _aidb_url = (aidb_url or os.getenv("AIDB_URL", "")).rstrip("/")
    _aidb_api_key = (aidb_api_key or "").strip()
    logger.info(
        "agentic_memory_journal initialized aidb_url=%s",
        _aidb_url or "(not configured)",
    )


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
async def write_entry(
    *,
    task_summary: str,
    task_archetype: str,
    model_id: str,
    provider: str = "",
    tier: str = "",
    profile: str = "",
    runtime_id: str = "",
    agent_role: str = "implementer",
    success: bool,
    error_code: int = 0,
    error_msg: str = "",
    latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    outcome_summary: str = "",
    session_id: str = "",
    task_id: str = "",
    fallback_used: bool = False,
    fallback_from: str = "",
) -> str:
    """
    Write one journal entry to Redis + AIDB.
    Returns the memory_id (UUID) of the new entry.
    """
    memory_id = uuid4().hex
    now = time.time()
    timestamp = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

    entry: Dict[str, Any] = {
        "memory_id": memory_id,
        "timestamp": timestamp,
        "epoch": now,
        "session_id": (session_id or "")[:64],
        "task_id": (task_id or "")[:64],
        "task_summary": (task_summary or "")[:300],
        "task_archetype": (task_archetype or "chat")[:32],
        "model_id": (model_id or "")[:128],
        "provider": (provider or "")[:64],
        "tier": (tier or "")[:32],
        "profile": (profile or "")[:64],
        "runtime_id": (runtime_id or "")[:64],
        "agent_role": (agent_role or "implementer")[:32],
        "success": bool(success),
        "error_code": int(error_code or 0),
        "error_msg": (error_msg or "")[:200],
        "latency_ms": round(float(latency_ms or 0), 1),
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "outcome_summary": (outcome_summary or "")[:300],
        "fallback_used": bool(fallback_used),
        "fallback_from": (fallback_from or "")[:128],
    }

    # Write to Redis (hot cache, last 1000)
    await _redis_write(entry)

    # Write to AIDB (persistent, async — don't block response)
    await _aidb_write(entry)

    logger.debug(
        "journal_write memory_id=%s model=%s success=%s latency_ms=%.0f archetype=%s",
        memory_id, model_id, success, latency_ms, task_archetype,
    )
    return memory_id


# ---------------------------------------------------------------------------
# Read / Query
# ---------------------------------------------------------------------------
async def get_entries(
    *,
    limit: int = 50,
    model_id: Optional[str] = None,
    tier: Optional[str] = None,
    task_archetype: Optional[str] = None,
    success_only: bool = False,
    errors_only: bool = False,
    since_epoch: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Return journal entries from Redis hot cache, optionally filtered.
    For deep historical queries use the AIDB endpoint directly.
    """
    entries = await _redis_read_all()
    results = []

    for entry in entries:
        if since_epoch and entry.get("epoch", 0) < since_epoch:
            continue
        if model_id and entry.get("model_id") != model_id:
            continue
        if tier and entry.get("tier") != tier:
            continue
        if task_archetype and entry.get("task_archetype") != task_archetype:
            continue
        if success_only and not entry.get("success"):
            continue
        if errors_only and entry.get("success"):
            continue
        results.append(entry)
        if len(results) >= limit:
            break

    return results


async def get_stats(*, since_epoch: float = 0.0) -> Dict[str, Any]:
    """
    Aggregate stats from Redis hot cache.
    Returns per-model and per-archetype breakdowns.
    """
    entries = await _redis_read_all()
    if since_epoch:
        entries = [e for e in entries if e.get("epoch", 0) >= since_epoch]

    total = len(entries)
    successes = sum(1 for e in entries if e.get("success"))
    by_model: Dict[str, Dict[str, Any]] = {}
    by_archetype: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        mid = entry.get("model_id", "unknown")
        arch = entry.get("task_archetype", "unknown")
        ok = entry.get("success", False)
        lat = float(entry.get("latency_ms") or 0)

        for bucket, key in [(by_model, mid), (by_archetype, arch)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "success": 0, "error": 0,
                               "total_latency_ms": 0.0, "avg_latency_ms": 0.0}
            bucket[key]["total"] += 1
            if ok:
                bucket[key]["success"] += 1
            else:
                bucket[key]["error"] += 1
            bucket[key]["total_latency_ms"] += lat

    for bucket in (by_model, by_archetype):
        for key in bucket:
            t = bucket[key]["total"]
            bucket[key]["success_rate"] = round(bucket[key]["success"] / t, 4) if t else 0.0
            bucket[key]["avg_latency_ms"] = round(
                bucket[key]["total_latency_ms"] / t, 1
            ) if t else 0.0
            del bucket[key]["total_latency_ms"]

    return {
        "total_entries": total,
        "success_count": successes,
        "error_count": total - successes,
        "overall_success_rate": round(successes / total, 4) if total else 0.0,
        "by_model": dict(sorted(by_model.items(), key=lambda kv: -kv[1]["total"])),
        "by_archetype": dict(sorted(by_archetype.items(), key=lambda kv: -kv[1]["total"])),
        "hot_cache_size": total,
        "generated_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------
async def _redis_write(entry: Dict[str, Any]) -> None:
    redis = await _get_redis()
    if redis is None:
        return
    try:
        payload = json.dumps(entry, separators=(",", ":"))
        # LPUSH to front; LTRIM to keep last N
        await redis.lpush(_JOURNAL_KEY, payload)
        await redis.ltrim(_JOURNAL_KEY, 0, _JOURNAL_MAX_ENTRIES - 1)
    except Exception as exc:
        logger.debug("journal redis_write error: %s", exc)


async def _redis_read_all() -> List[Dict[str, Any]]:
    redis = await _get_redis()
    if redis is None:
        return []
    try:
        raw_list = await redis.lrange(_JOURNAL_KEY, 0, -1)
        entries = []
        for raw in raw_list:
            try:
                text = raw.decode() if isinstance(raw, bytes) else raw
                entries.append(json.loads(text))
            except Exception:
                pass
        return entries
    except Exception as exc:
        logger.debug("journal redis_read_all error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# AIDB backend
# ---------------------------------------------------------------------------
async def _aidb_write(entry: Dict[str, Any]) -> None:
    if not _aidb_url:
        return
    try:
        # Build a human-readable content string for semantic search
        ok_str = "SUCCESS" if entry["success"] else f"FAILED({entry['error_code']})"
        content = (
            f"[journal] {ok_str} | model={entry['model_id']} tier={entry['tier']} "
            f"archetype={entry['task_archetype']} role={entry['agent_role']} "
            f"latency={entry['latency_ms']}ms tokens_out={entry['tokens_out']}\n"
            f"task: {entry['task_summary']}\n"
            f"outcome: {entry['outcome_summary']}"
        ).strip()

        doc = {
            "content": content,
            "project": _AIDB_PROJECT,
            "relative_path": f"journal/{entry['task_archetype']}/{entry['memory_id']}.entry",
            "title": f"[{entry['task_archetype']}] {ok_str} {entry['model_id']} {entry['timestamp'][:19]}",
            "metadata": {
                "memory_id": entry["memory_id"],
                "model_id": entry["model_id"],
                "provider": entry["provider"],
                "tier": entry["tier"],
                "profile": entry["profile"],
                "runtime_id": entry["runtime_id"],
                "agent_role": entry["agent_role"],
                "task_archetype": entry["task_archetype"],
                "success": entry["success"],
                "error_code": entry["error_code"],
                "latency_ms": entry["latency_ms"],
                "tokens_in": entry["tokens_in"],
                "tokens_out": entry["tokens_out"],
                "fallback_used": entry["fallback_used"],
                "fallback_from": entry["fallback_from"],
                "epoch": entry["epoch"],
                "session_id": entry["session_id"],
                "task_id": entry["task_id"],
            },
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if _aidb_api_key:
            headers["X-API-Key"] = _aidb_api_key

        async with httpx.AsyncClient(timeout=_AIDB_TIMEOUT) as client:
            resp = await client.post(
                f"{_aidb_url}/documents",
                json=doc,
                headers=headers,
            )
        if resp.status_code not in {200, 201}:
            logger.debug(
                "journal aidb_write status=%d body=%s",
                resp.status_code,
                resp.text[:120],
            )
    except Exception as exc:
        # AIDB writes are non-blocking best-effort
        logger.debug("journal aidb_write error: %s", exc)
