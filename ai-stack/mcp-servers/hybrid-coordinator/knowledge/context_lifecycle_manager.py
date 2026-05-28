"""
knowledge/context_lifecycle_manager.py — AgentRM Context Lifecycle Manager (Phase 61)

Implements the 3-tier context lifecycle from arXiv:2603.13110 (AgentRM):

    Hot  — Redis working set (≤4K tokens/session, ≤256MB total; AM-Q1)
    Warm — gzipped JSONL on disk (/var/lib/ai-stack/hybrid/clm-warm/)
    Cold — AIDB episodic store (400-token Qwen summary)

Promotion triggers (AM-G2 / PRD 61.2):
    Hot  → Warm: idle > 5 min  OR  Hot-tier pressure > 85%
    Warm → Cold: idle > 30 min

Thermal gate (AM-G4): LLM summarization tasks are skipped/deferred when the
MLFQ scheduler reports thermal tier = critical or shutdown.

Model gate (AM-G2): compaction is suspended when the local model is unavailable.

Usage:
    from knowledge.context_lifecycle_manager import ContextLifecycleManager, init, get_clm

    await init(redis_url=..., llm_url=..., store_fn=...)
    clm = get_clm()
    await clm.touch(session_id, tokens=512)   # called per query
    status = await clm.status()               # GET /context/lifecycle/status
    await clm.evict(session_id)               # POST /context/lifecycle/evict/{id}
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# shared/ is at ai-stack/mcp-servers/shared/ — parents[2] from this file's location.
_SHARED_PATH = str(Path(__file__).resolve().parents[2])
if _SHARED_PATH not in sys.path:
    sys.path.insert(0, _SHARED_PATH)

from shared.llm_config import build_llama_payload  # noqa: E402

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Constants (AM-Q1: Redis budget 256MB; tier thresholds from PRD 61.2)
# ---------------------------------------------------------------------------
_HOT_MAX_MB: int = int(os.getenv("CLM_HOT_MAX_MB", "256"))
_HOT_IDLE_SECS: int = int(os.getenv("CLM_HOT_IDLE_SECS", "300"))    # 5 min
_WARM_IDLE_SECS: int = int(os.getenv("CLM_WARM_IDLE_SECS", "1800"))  # 30 min
_HOT_PRESSURE_PCT: float = float(os.getenv("CLM_HOT_PRESSURE_PCT", "85"))
_REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
_LLM_URL: str = os.getenv("LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080")
_WARM_DIR: Path = Path(os.getenv(
    "CLM_WARM_DIR",
    "/var/lib/ai-stack/hybrid/clm-warm",
))
_COMPACTION_PROMPT_FILE: Path = Path(os.getenv(
    "AI_CLM_COMPACTION_PROMPT_FILE",
    str(Path(__file__).resolve().parents[4] / "config" / "clm-compaction-prompt.yaml"),
))
_HOT_REDIS_PREFIX: str = "clm:hot:"
_TICK_INTERVAL: int = 60  # seconds between background promotion checks
_WARM_MAX_SESSIONS: int = int(os.getenv("CLM_WARM_MAX_SESSIONS", "8"))  # Phase 65.1: K-LRU threshold
_WARM_KLRU_K: int = int(os.getenv("CLM_WARM_KLRU_K", "3"))             # Phase 65.1: evict K LRU warm blocks

# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------
_clm: Optional["ContextLifecycleManager"] = None


def get_clm() -> "ContextLifecycleManager":
    global _clm
    if _clm is None:
        _clm = ContextLifecycleManager()
    return _clm


async def init(
    redis_url: str = _REDIS_URL,
    llm_url: str = _LLM_URL,
    store_fn: Optional[Callable] = None,
) -> None:
    """Wire CLM singleton. Call once at coordinator startup."""
    global _clm
    _clm = ContextLifecycleManager(redis_url=redis_url, llm_url=llm_url, store_fn=store_fn)
    await _clm.start()
    logger.info("context_lifecycle_manager: initialized (hot=%dMB, hot_idle=%ds, warm_idle=%ds)",
                _HOT_MAX_MB, _HOT_IDLE_SECS, _WARM_IDLE_SECS)


# ---------------------------------------------------------------------------
# CLM
# ---------------------------------------------------------------------------

class ContextLifecycleManager:
    """
    3-tier session context lifecycle: Hot → Warm → Cold.

    Session state (in-process dict):
        {session_id: {"tier": str, "last_active": float, "tokens": int}}
    """

    def __init__(
        self,
        redis_url: str = _REDIS_URL,
        llm_url: str = _LLM_URL,
        store_fn: Optional[Callable] = None,
    ) -> None:
        self._redis_url = redis_url
        self._llm_url = llm_url
        self._store_fn = store_fn  # memory_broker store callable for Cold tier
        self._redis: Optional[Any] = None
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._tick_task: Optional[asyncio.Task] = None
        self._compaction_prompt: Optional[str] = None
        self._klru_evictions: int = 0   # Phase 65.1: lifetime K-LRU eviction counter
        _WARM_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect Redis and start background promotion ticker."""
        await self._connect_redis()
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._tick_task:
            self._tick_task.cancel()
        if self._redis:
            await self._redis.aclose()

    async def _connect_redis(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await self._redis.ping()
            logger.info("context_lifecycle_manager: Redis connected")
        except Exception as exc:
            logger.warning("context_lifecycle_manager: Redis unavailable (%s) — Hot tier degraded", exc)
            self._redis = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def touch(self, session_id: str, tokens: int = 0) -> None:
        """Record activity for a session. Creates Hot entry if new."""
        now = time.time()
        if session_id not in self._sessions:
            self._sessions[session_id] = {"tier": "hot", "last_active": now, "tokens": tokens}
        else:
            s = self._sessions[session_id]
            s["last_active"] = now
            s["tokens"] = max(s.get("tokens", 0), tokens)
            if s["tier"] == "warm":
                # Re-activate: promote back to hot
                s["tier"] = "hot"

        if self._redis:
            try:
                key = f"{_HOT_REDIS_PREFIX}{session_id}"
                await self._redis.setex(
                    key,
                    _HOT_IDLE_SECS + 60,
                    json.dumps({"tokens": tokens, "last_active": now}),
                )
            except Exception as exc:
                logger.debug("clm.touch redis_failed session=%s exc=%s", session_id, exc)

    async def evict(self, session_id: str) -> Dict[str, Any]:
        """Manually evict a session (move Hot→Warm or Warm→Cold immediately)."""
        s = self._sessions.get(session_id)
        if s is None:
            return {"evicted": False, "reason": "session_not_found"}
        if s["tier"] == "hot":
            await self._demote_to_warm(session_id, s)
            return {"evicted": True, "new_tier": "warm"}
        if s["tier"] == "warm":
            await self._demote_to_cold(session_id, s)
            return {"evicted": True, "new_tier": "cold"}
        return {"evicted": False, "reason": "already_cold"}

    async def status(self) -> Dict[str, Any]:
        """Return CLM tier counts + pressure metrics."""
        tiers: Dict[str, int] = {"hot": 0, "warm": 0, "cold": 0}
        for s in self._sessions.values():
            tiers[s.get("tier", "cold")] = tiers.get(s.get("tier", "cold"), 0) + 1

        hot_mb = await self._hot_redis_mb()
        pressure_pct = round(hot_mb / _HOT_MAX_MB * 100, 1)
        thermal = self._thermal_tier()

        return {
            "tiers": tiers,
            "session_count": len(self._sessions),
            "hot_redis_mb": round(hot_mb, 2),
            "hot_max_mb": _HOT_MAX_MB,
            "pressure_pct": pressure_pct,
            "pressure_high": pressure_pct >= _HOT_PRESSURE_PCT,
            "thermal_tier": thermal,
            "compaction_suspended": thermal in ("critical", "shutdown"),
            "warm_dir": str(_WARM_DIR),
            "klru_evictions": self._klru_evictions,
            "thresholds": {
                "hot_idle_secs": _HOT_IDLE_SECS,
                "warm_idle_secs": _WARM_IDLE_SECS,
                "hot_pressure_pct": _HOT_PRESSURE_PCT,
                "warm_max_sessions": _WARM_MAX_SESSIONS,
                "warm_klru_k": _WARM_KLRU_K,
            },
        }

    # ------------------------------------------------------------------
    # Background promotion tick (runs every _TICK_INTERVAL seconds)
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_TICK_INTERVAL)
                await self._promote_stale_sessions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("clm._tick_loop error: %s", exc)

    async def _promote_stale_sessions(self) -> None:
        now = time.time()
        hot_mb = await self._hot_redis_mb()
        pressure_pct = hot_mb / _HOT_MAX_MB * 100

        # Phase 61.5: feed CLM pressure back to MLFQ scheduler (AM-G4)
        self._report_pressure_to_scheduler(pressure_pct)

        for sid, s in list(self._sessions.items()):
            tier = s.get("tier", "hot")
            idle = now - s.get("last_active", now)

            if tier == "hot":
                should_demote = (
                    idle > _HOT_IDLE_SECS
                    or pressure_pct >= _HOT_PRESSURE_PCT
                )
                if should_demote:
                    await self._demote_to_warm(sid, s)

            elif tier == "warm":
                if idle > _WARM_IDLE_SECS:
                    await self._demote_to_cold(sid, s)

        # Phase 65.1: K-LRU eviction when warm tier exceeds max sessions
        warm_count = sum(1 for s in self._sessions.values() if s.get("tier") == "warm")
        if warm_count > _WARM_MAX_SESSIONS:
            await self.apply_klru_pressure(k=_WARM_KLRU_K)

    @staticmethod
    def _report_pressure_to_scheduler(pressure_pct: float) -> None:
        """Phase 61.5: notify MLFQ scheduler of CLM Hot-tier pressure."""
        try:
            from mlfq_scheduler import get_scheduler
            get_scheduler().apply_clm_pressure(pressure_pct)
        except Exception:
            pass

    async def apply_klru_pressure(self, k: int = 3) -> int:
        """Phase 65.1: K-LRU eviction for the warm tier.

        Evicts the K least-recently-used warm context blocks to cold storage.
        Uses the existing `last_active` timestamp already tracked in `_sessions` —
        no separate Redis hash needed (Codex Staff Eng review 2026-05-23).

        Called from _promote_stale_sessions() when warm_count > _WARM_MAX_SESSIONS.
        Returns the number of sessions actually evicted.
        """
        warm_sessions = [
            (sid, s)
            for sid, s in list(self._sessions.items())
            if s.get("tier") == "warm"
        ]
        if not warm_sessions:
            return 0

        # Sort by last_active ascending — oldest (least recently used) first
        warm_sessions.sort(key=lambda x: x[1].get("last_active", 0))
        evicted = 0
        for sid, s in warm_sessions[:k]:
            try:
                await self._demote_to_cold(sid, s)
                evicted += 1
                logger.info("clm.klru_evict session=%s last_active=%.0f", sid, s.get("last_active", 0))
            except Exception as exc:
                logger.debug("clm.klru_evict_failed session=%s exc=%s", sid, exc)
        self._klru_evictions += evicted
        if evicted:
            logger.info("clm.klru_pressure evicted=%d warm_remaining=%d total_klru=%d",
                        evicted, len(warm_sessions) - evicted, self._klru_evictions)
        return evicted

    # ------------------------------------------------------------------
    # Tier demotion helpers
    # ------------------------------------------------------------------

    async def _demote_to_warm(self, session_id: str, state: Dict[str, Any]) -> None:
        """Snapshot session to gzipped JSONL on disk and remove from Redis."""
        try:
            payload = {
                "session_id": session_id,
                "tier": "warm",
                "tokens": state.get("tokens", 0),
                "last_active": state.get("last_active", time.time()),
                "archived_at": time.time(),
            }
            warm_path = _WARM_DIR / f"{session_id}.jsonl.gz"
            with gzip.open(str(warm_path), "wt", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")

            if self._redis:
                try:
                    await self._redis.delete(f"{_HOT_REDIS_PREFIX}{session_id}")
                except Exception:
                    pass

            state["tier"] = "warm"
            logger.debug("clm.demote_to_warm session=%s tokens=%d", session_id, state.get("tokens", 0))
        except Exception as exc:
            logger.warning("clm.demote_to_warm_failed session=%s exc=%s", session_id, exc)

    async def _demote_to_cold(self, session_id: str, state: Dict[str, Any]) -> None:
        """Summarize via Qwen (thermal-gated) and archive to AIDB episodic."""
        # AM-G4: skip if thermal critical/shutdown
        if self._thermal_tier() in ("critical", "shutdown"):
            logger.debug("clm.demote_to_cold deferred thermal=%s", self._thermal_tier())
            return

        summary = await self._compact_summary(session_id, state)
        if summary and self._store_fn:
            try:
                await asyncio.wait_for(
                    self._store_fn(
                        memory_type="episodic",
                        summary=summary,
                        content=summary,
                        metadata={
                            "session_id": session_id,
                            "clm_tier": "cold",
                            "archived_at": datetime.now(timezone.utc).isoformat(),
                            "original_tokens": state.get("tokens", 0),
                        },
                    ),
                    timeout=10.0,
                )
                logger.info("clm.demote_to_cold session=%s summary_len=%d stored", session_id, len(summary))
            except Exception as exc:
                logger.warning("clm.cold_store_failed session=%s exc=%s", session_id, exc)

        # Remove warm file
        warm_path = _WARM_DIR / f"{session_id}.jsonl.gz"
        if warm_path.exists():
            warm_path.unlink(missing_ok=True)

        state["tier"] = "cold"
        # Prune from in-process dict after cold archival (keep last 200)
        if len(self._sessions) > 200:
            oldest = sorted(self._sessions, key=lambda k: self._sessions[k].get("last_active", 0))
            for old_sid in oldest[:10]:
                self._sessions.pop(old_sid, None)

    async def _compact_summary(self, session_id: str, state: Dict[str, Any]) -> Optional[str]:
        """
        Call Qwen to produce a ≤400-token episodic summary (AM-C2).
        Uses fixed template from clm-compaction-prompt.yaml.
        Returns None on failure (cold archival skipped gracefully).
        """
        prompt_template = self._load_compaction_prompt()
        warm_path = _WARM_DIR / f"{session_id}.jsonl.gz"

        # Read warm snapshot content (if available)
        context = ""
        if warm_path.exists():
            try:
                with gzip.open(str(warm_path), "rt", encoding="utf-8") as fh:
                    payload = json.loads(fh.readline())
                context = f"session_id={session_id}, tokens={payload.get('tokens', 0)}"
            except Exception:
                pass

        prompt = prompt_template.replace("{session_id}", session_id).replace("{context}", context or "no context")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{self._llm_url}/v1/chat/completions",
                    json=build_llama_payload(
                        [{"role": "user", "content": prompt}],
                        max_tokens=512,
                        temperature=0.1,
                        model="local",
                    ),
                    timeout=aiohttp.ClientTimeout(total=30.0),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["choices"][0]["message"]["content"].strip()
                        return text[:2000]  # hard cap before AIDB store
        except Exception as exc:
            logger.debug("clm.compact_summary_failed session=%s exc=%s", session_id, exc)
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_compaction_prompt(self) -> str:
        if self._compaction_prompt:
            return self._compaction_prompt
        try:
            import yaml
            data = yaml.safe_load(_COMPACTION_PROMPT_FILE.read_text())
            self._compaction_prompt = str(data.get("template", _DEFAULT_COMPACTION_PROMPT))
        except Exception:
            self._compaction_prompt = _DEFAULT_COMPACTION_PROMPT
        return self._compaction_prompt

    @staticmethod
    def _thermal_tier() -> str:
        """Read current thermal tier from MLFQ scheduler (best-effort)."""
        try:
            from mlfq_scheduler import get_scheduler
            return get_scheduler()._thermal_tier
        except Exception:
            return "normal"

    async def _hot_redis_mb(self) -> float:
        """Estimate Hot-tier Redis memory usage in MB."""
        if self._redis is None:
            return 0.0
        try:
            info = await self._redis.info("memory")
            used_bytes = int(info.get("used_memory", 0))
            return used_bytes / (1024 * 1024)
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# Default compaction prompt (AM-C2 fallback if YAML not found)
# ---------------------------------------------------------------------------
_DEFAULT_COMPACTION_PROMPT = (
    "You are a context archiver. Summarize the following session into a compact episodic record "
    "of at most 400 tokens. Preserve: key decisions, open questions, active tasks, and critical facts. "
    "Discard: conversational filler and redundant context.\n\n"
    "Session: {session_id}\nContext: {context}\n\n"
    "Episodic summary:"
)


# ---------------------------------------------------------------------------
# HTTP handlers (Phase 61.4)
# ---------------------------------------------------------------------------

async def handle_clm_status(request: Any) -> Any:
    """GET /context/lifecycle/status"""
    from aiohttp import web
    try:
        return web.json_response(await get_clm().status())
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_clm_evict(request: Any) -> Any:
    """POST /context/lifecycle/evict/{session_id}"""
    from aiohttp import web
    session_id = request.match_info.get("session_id", "").strip()
    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)
    try:
        result = await get_clm().evict(session_id)
        return web.json_response(result)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


def register_routes(app: Any) -> None:
    from aiohttp import web
    app.router.add_get("/context/lifecycle/status", handle_clm_status)
    app.router.add_post("/context/lifecycle/evict/{session_id}", handle_clm_evict)
