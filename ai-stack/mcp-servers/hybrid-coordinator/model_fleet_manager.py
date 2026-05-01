"""
Model Fleet Manager — Phase 15.1

Manages capability-pooled model registries with Redis-backed live state.
Provides smart model selection across free, paid-remote, and local tiers
with per-model cooldown, rolling error/success counters, and latency tracking.

Capability pools: coding, reasoning, writing, chat, vision, agents, video

Usage:
    import model_fleet_manager as mfm
    mfm.init(redis_client=redis_client)

    # Get ranked available models for a task
    models = await mfm.get_available_models("coding")

    # Record outcomes
    await mfm.record_success("anthropic/claude-sonnet-4-6", latency_ms=1240, tokens_out=88)
    await mfm.record_error("qwen/qwen3-next-80b:free", error_code=429, error_msg="rate limited")

    # Full fleet status for /control/model-fleet/status
    status = await mfm.get_fleet_status()
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Lazy Redis connection (created on first use from REDIS_URL env var)
# ---------------------------------------------------------------------------
_redis: Optional[Any] = None
_redis_url: str = ""


async def _get_redis() -> Optional[Any]:
    """Return a connected Redis client, creating it lazily on first call."""
    global _redis
    if _redis is not None:
        return _redis
    url = _redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis = await aioredis.from_url(url, encoding="utf-8", decode_responses=False)
        logger.info("model_fleet_manager: Redis connected url=%s", url.split("@")[-1])
    except Exception as exc:
        logger.warning("model_fleet_manager: Redis connect failed: %s", exc)
        _redis = None
    return _redis

# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------
def _model_key(model_id: str, field: str) -> str:
    """Stable Redis key for a model state field."""
    safe = model_id.replace("/", "__").replace(":", "--").replace(".", "_")
    return f"fleet:model:{safe}:{field}"


# ---------------------------------------------------------------------------
# Cooldown durations (seconds) per HTTP error code
# ---------------------------------------------------------------------------
_COOLDOWN_BY_CODE: Dict[int, float] = {
    429: 300.0,   # rate limited — 5 min
    401: 3600.0,  # auth failure — 1 hour (needs key fix)
    403: 3600.0,  # forbidden — 1 hour
    502: 120.0,   # bad gateway — 2 min
    503: 120.0,   # service unavailable — 2 min
    504: 120.0,   # timeout — 2 min
}
_DEFAULT_COOLDOWN = 60.0  # any other error — 1 min

# Rolling window for error/success counters
_COUNTER_TTL = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Model entry definition
# ---------------------------------------------------------------------------
@dataclass
class ModelEntry:
    model_id: str           # OpenRouter model ID (e.g. "anthropic/claude-sonnet-4-6")
    provider: str           # upstream provider name
    tier: str               # "free" | "paid_standard" | "paid_premium" | "local"
    capabilities: List[str] # which pools this model belongs to
    context_window: int     # max input tokens
    max_output_tokens: int  # max output tokens
    notes: str = ""         # human notes (specialty, caveats)


# ---------------------------------------------------------------------------
# Live per-model state (read from / written to Redis)
# ---------------------------------------------------------------------------
@dataclass
class ModelState:
    model_id: str
    cooldown_until: float = 0.0       # epoch seconds; 0 = not cooling
    error_count_1h: int = 0
    success_count_1h: int = 0
    avg_latency_ms: float = 0.0
    last_error: str = ""
    last_error_code: int = 0
    last_error_at: float = 0.0
    last_success_at: float = 0.0

    @property
    def is_cooling(self) -> bool:
        return self.cooldown_until > time.time()

    @property
    def availability(self) -> str:
        if self.is_cooling:
            return "cooling"
        if self.error_count_1h >= 10 and self.success_count_1h == 0:
            return "unavailable"
        return "available"

    @property
    def success_rate(self) -> float:
        total = self.error_count_1h + self.success_count_1h
        if total == 0:
            return 1.0
        return round(self.success_count_1h / total, 4)


# ---------------------------------------------------------------------------
# Capability pool registry
# ---------------------------------------------------------------------------
# NOTE: OpenRouter model IDs are verified slugs at time of writing (2026-04-30).
# Free-tier models are marked with ":free" suffix; paid models without.
# Top-9 coding models sourced from OpenRouter real-time rankings provided by user.
# ---------------------------------------------------------------------------

_POOL_REGISTRY: Dict[str, List[ModelEntry]] = {

    # ── CODING ───────────────────────────────────────────────────────────────
    # Top-9 from OpenRouter programming leaderboard + strong known coders
    "coding": [
        ModelEntry("moonshotai/kimi-k2", "Moonshot AI", "paid_premium",
                   ["coding", "reasoning"], 131072, 16384,
                   "Top-1 OpenRouter coding; 1.17T tokens context. MoE architecture."),
        ModelEntry("tencent/hy3-preview:free", "Tencent", "free",
                   ["coding", "chat"], 32768, 4096,
                   "Top-2 OpenRouter coding (free). Verify slug on OpenRouter."),
        ModelEntry("stepfun/step-3.5-flash", "StepFun", "paid_standard",
                   ["coding"], 32768, 8192,
                   "Top-3 OpenRouter coding. Fast flash variant."),
        ModelEntry("anthropic/claude-opus-4-7", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Top-4 OpenRouter coding. Claude Opus 4.7."),
        ModelEntry("anthropic/claude-sonnet-4-6", "Anthropic", "paid_standard",
                   ["coding", "reasoning", "writing", "agents"], 200000, 16000,
                   "Top-5 OpenRouter coding. Claude Sonnet 4.6 (current harness model)."),
        ModelEntry("nvidia/nemotron-3-super:free", "NVIDIA", "free",
                   ["coding", "reasoning"], 131072, 8192,
                   "Top-6 OpenRouter coding (free). NVIDIA Nemotron 3 Super."),
        ModelEntry("inclusionai/ling-2.6-1t:free", "InclusionAI", "free",
                   ["coding"], 32768, 4096,
                   "Top-7 OpenRouter coding (free). 1T param MoE."),
        ModelEntry("anthropic/claude-opus-4-6", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Top-8 OpenRouter coding. Claude Opus 4.6."),
        ModelEntry("minimax/minimax-m2", "MiniMax", "paid_standard",
                   ["coding", "chat"], 1000000, 8192,
                   "Top-9 OpenRouter coding. MiniMax M2 / M2.7."),
        # Additional top coders from prior plan
        ModelEntry("deepseek/deepseek-r1", "DeepSeek", "paid_standard",
                   ["coding", "reasoning"], 128000, 32768,
                   "Top reasoning + complex code. Chain-of-thought."),
        ModelEntry("deepseek/deepseek-coder-v2", "DeepSeek", "paid_standard",
                   ["coding"], 128000, 16384,
                   "Code-specialized variant. Strong on refactoring."),
        ModelEntry("openai/o1", "OpenAI", "paid_premium",
                   ["coding", "reasoning"], 200000, 100000,
                   "Best for hard algorithms and math-heavy code."),
        ModelEntry("qwen/qwen2.5-coder-32b-instruct", "Alibaba", "paid_standard",
                   ["coding"], 128000, 8192,
                   "Top open-weight coder. Fast, strong completions."),
        ModelEntry("mistralai/codestral-2501", "Mistral AI", "paid_standard",
                   ["coding"], 256000, 32768,
                   "Code-only specialist. Excellent fill-in-middle."),
        ModelEntry("google/gemini-2.5-pro", "Google", "paid_premium",
                   ["coding", "reasoning", "vision"], 2000000, 65536,
                   "Massive context. Strong multi-file code understanding."),
        ModelEntry("meta-llama/llama-3.3-70b-instruct", "Meta", "paid_standard",
                   ["coding", "chat"], 128000, 8192,
                   "Open-weight fallback. Reliable general coder."),
        # Free coding fallbacks (verified available 2026-05).
        # qwen3-next-80b-a3b-instruct:free and qwen3-coder:free removed —
        # no longer available on OpenRouter free tier.
        ModelEntry("deepseek/deepseek-r1:free", "DeepSeek", "free",
                   ["coding", "reasoning"], 65536, 8192,
                   "Free reasoning + code. Strong chain-of-thought."),
        ModelEntry("meta-llama/llama-3.3-70b-instruct:free", "Meta", "free",
                   ["coding", "chat"], 128000, 4096,
                   "Free Llama 3.3 70B. Reliable general coder."),
        ModelEntry("google/gemini-2.0-flash-exp:free", "Google", "free",
                   ["coding", "chat", "vision"], 1048576, 8192,
                   "Free Gemini flash. Large context. Rate-limited on free tier."),
    ],

    # ── REASONING ────────────────────────────────────────────────────────────
    "reasoning": [
        ModelEntry("anthropic/claude-opus-4-7", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Best available for complex analysis and planning."),
        ModelEntry("deepseek/deepseek-r1", "DeepSeek", "paid_standard",
                   ["coding", "reasoning"], 128000, 32768,
                   "Chain-of-thought reasoning. Math, logic, planning."),
        ModelEntry("openai/o1", "OpenAI", "paid_premium",
                   ["coding", "reasoning"], 200000, 100000,
                   "Hard reasoning problems. Extended thinking."),
        ModelEntry("google/gemini-2.5-pro", "Google", "paid_premium",
                   ["coding", "reasoning", "vision"], 2000000, 65536,
                   "Deep analysis with massive context window."),
        ModelEntry("x-ai/grok-3", "xAI", "paid_premium",
                   ["reasoning", "chat"], 131072, 16384,
                   "Strong structured reasoning. Real-time knowledge."),
        ModelEntry("qwen/qwen3-235b-a22b", "Alibaba", "paid_standard",
                   ["reasoning", "coding"], 128000, 16384,
                   "Large MoE reasoning model."),
        ModelEntry("moonshotai/kimi-k2", "Moonshot AI", "paid_premium",
                   ["coding", "reasoning"], 131072, 16384,
                   "Strong reasoning. Top OpenRouter coding model."),
        ModelEntry("deepseek/deepseek-r1:free", "DeepSeek", "free",
                   ["coding", "reasoning"], 65536, 8192,
                   "Free reasoning fallback."),
        ModelEntry("nvidia/nemotron-3-super:free", "NVIDIA", "free",
                   ["coding", "reasoning"], 131072, 8192,
                   "Free NVIDIA reasoning model."),
    ],

    # ── WRITING ──────────────────────────────────────────────────────────────
    "writing": [
        ModelEntry("anthropic/claude-opus-4-6", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Best prose quality. Nuanced creative and technical writing."),
        ModelEntry("anthropic/claude-sonnet-4-6", "Anthropic", "paid_standard",
                   ["coding", "reasoning", "writing", "agents"], 200000, 16000,
                   "Excellent writing. Better cost/quality ratio."),
        ModelEntry("openai/gpt-4o", "OpenAI", "paid_standard",
                   ["writing", "chat", "vision"], 128000, 16384,
                   "Strong creative and technical writing."),
        ModelEntry("google/gemini-2.0-flash", "Google", "paid_standard",
                   ["writing", "chat", "vision", "video"], 1048576, 8192,
                   "Fast. Good summarization and long-doc writing."),
        ModelEntry("meta-llama/llama-3.3-70b-instruct", "Meta", "paid_standard",
                   ["coding", "chat"], 128000, 8192,
                   "Open-weight writing fallback."),
        ModelEntry("mistralai/mistral-large-2411", "Mistral AI", "paid_standard",
                   ["writing", "chat"], 131072, 16384,
                   "Strong European model. Good multilingual writing."),
        ModelEntry("google/gemini-2.0-flash-exp:free", "Google", "free",
                   ["writing", "chat", "vision"], 1048576, 8192,
                   "Free flash model for writing tasks."),
        ModelEntry("meta-llama/llama-3.3-70b-instruct:free", "Meta", "free",
                   ["coding", "chat"], 128000, 4096,
                   "Free writing fallback."),
    ],

    # ── CHAT ─────────────────────────────────────────────────────────────────
    "chat": [
        ModelEntry("anthropic/claude-sonnet-4-6", "Anthropic", "paid_standard",
                   ["coding", "reasoning", "writing", "agents"], 200000, 16000,
                   "Best chat quality for general use."),
        ModelEntry("openai/gpt-4o-mini", "OpenAI", "paid_standard",
                   ["chat"], 128000, 16384,
                   "Fast, cheap chat. High volume suitable."),
        ModelEntry("google/gemini-2.0-flash", "Google", "paid_standard",
                   ["writing", "chat", "vision", "video"], 1048576, 8192,
                   "Fast conversational model. Large context."),
        ModelEntry("x-ai/grok-3", "xAI", "paid_premium",
                   ["reasoning", "chat"], 131072, 16384,
                   "Real-time knowledge. Conversational."),
        ModelEntry("mistralai/mistral-large-2411", "Mistral AI", "paid_standard",
                   ["writing", "chat"], 131072, 16384,
                   "General chat. Multilingual capable."),
        ModelEntry("meta-llama/llama-3.1-8b-instruct:free", "Meta", "free",
                   ["chat"], 131072, 4096,
                   "Fast, lightweight free chat model."),
        ModelEntry("google/gemini-2.0-flash-exp:free", "Google", "free",
                   ["writing", "chat", "vision"], 1048576, 8192,
                   "Free Gemini chat fallback."),
        ModelEntry("mistralai/mistral-7b-instruct:free", "Mistral AI", "free",
                   ["chat"], 32768, 4096,
                   "Lightweight free chat fallback."),
    ],

    # ── VISION (image understanding, OCR, photo analysis) ───────────────────
    "vision": [
        ModelEntry("anthropic/claude-opus-4-6", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Best image understanding and visual reasoning."),
        ModelEntry("openai/gpt-4o", "OpenAI", "paid_standard",
                   ["writing", "chat", "vision"], 128000, 16384,
                   "Strong vision. OCR, diagrams, screenshots."),
        ModelEntry("google/gemini-2.0-flash", "Google", "paid_standard",
                   ["writing", "chat", "vision", "video"], 1048576, 8192,
                   "Multimodal. Fast vision tasks."),
        ModelEntry("google/gemini-2.5-pro", "Google", "paid_premium",
                   ["coding", "reasoning", "vision"], 2000000, 65536,
                   "Deep visual analysis with massive context."),
        ModelEntry("mistralai/pixtral-large-2411", "Mistral AI", "paid_standard",
                   ["vision"], 131072, 16384,
                   "Vision-specialized. Strong on technical images."),
        ModelEntry("meta-llama/llama-3.2-90b-vision-instruct", "Meta", "paid_standard",
                   ["vision"], 128000, 8192,
                   "Open-weight vision model. Good generalist."),
        ModelEntry("google/gemini-2.0-flash-exp:free", "Google", "free",
                   ["writing", "chat", "vision"], 1048576, 8192,
                   "Free vision fallback. Gemini Flash."),
    ],

    # ── AGENTS (tool-calling, function use, agentic tasks) ───────────────────
    "agents": [
        ModelEntry("anthropic/claude-sonnet-4-6", "Anthropic", "paid_standard",
                   ["coding", "reasoning", "writing", "agents"], 200000, 16000,
                   "Best tool-calling reliability. Preferred for agentic tasks."),
        ModelEntry("anthropic/claude-opus-4-7", "Anthropic", "paid_premium",
                   ["coding", "reasoning", "writing", "agents"], 200000, 32000,
                   "Premium agentic. Complex multi-step tasks."),
        ModelEntry("openai/gpt-4o", "OpenAI", "paid_standard",
                   ["writing", "chat", "vision"], 128000, 16384,
                   "Reliable function-calling. Broad tool schema support."),
        ModelEntry("google/gemini-2.5-pro", "Google", "paid_premium",
                   ["coding", "reasoning", "vision"], 2000000, 65536,
                   "Strong agentic reasoning. Parallel tool-calling."),
        ModelEntry("mistralai/mistral-large-2411", "Mistral AI", "paid_standard",
                   ["writing", "chat"], 131072, 16384,
                   "Good tool-calling. European data residency option."),
        ModelEntry("meta-llama/llama-3.1-70b-instruct", "Meta", "paid_standard",
                   ["agents"], 131072, 8192,
                   "Open-weight agent model. Function-calling capable."),
        ModelEntry("deepseek/deepseek-r1:free", "DeepSeek", "free",
                   ["coding", "reasoning"], 65536, 8192,
                   "Free agentic fallback. Reasoning-based tool selection."),
    ],

    # ── VIDEO (understanding only; generation = future Runway/Kling APIs) ────
    "video": [
        ModelEntry("google/gemini-2.0-flash", "Google", "paid_standard",
                   ["writing", "chat", "vision", "video"], 1048576, 8192,
                   "Primary video understanding. Native multimodal."),
        ModelEntry("google/gemini-2.5-pro", "Google", "paid_premium",
                   ["coding", "reasoning", "vision"], 2000000, 65536,
                   "Deep video analysis. Massive context for long videos."),
        ModelEntry("google/gemini-2.0-flash-exp:free", "Google", "free",
                   ["writing", "chat", "vision"], 1048576, 8192,
                   "Free video understanding fallback."),
    ],
}

# Validate capability consistency at module load
_ALL_MODEL_IDS: Dict[str, ModelEntry] = {}
for _pool_id, _entries in _POOL_REGISTRY.items():
    for _entry in _entries:
        _ALL_MODEL_IDS[_entry.model_id] = _entry


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
def init(*, redis_url: str = "") -> None:
    """Configure Redis URL. Call once at startup; connection is lazy."""
    global _redis_url, _redis
    _redis_url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
    _redis = None  # reset so next call reconnects to new URL
    logger.info(
        "model_fleet_manager initialized pools=%s models=%d",
        list(_POOL_REGISTRY.keys()),
        len(_ALL_MODEL_IDS),
    )


# ---------------------------------------------------------------------------
# Redis state read/write
# ---------------------------------------------------------------------------
async def _read_model_state(model_id: str) -> ModelState:
    state = ModelState(model_id=model_id)
    redis = await _get_redis()
    if redis is None:
        return state
    try:
        key = _model_key(model_id, "state")
        raw = await redis.hgetall(key)
        if raw:
            def _f(k: bytes, default: str = "") -> str:
                v = raw.get(k) or raw.get(k.decode() if isinstance(k, bytes) else k.encode())
                return (v.decode() if isinstance(v, bytes) else str(v or "")) or default

            state.cooldown_until = float(_f(b"cooldown_until") or 0)
            state.error_count_1h = int(_f(b"error_count_1h") or 0)
            state.success_count_1h = int(_f(b"success_count_1h") or 0)
            state.avg_latency_ms = float(_f(b"avg_latency_ms") or 0)
            state.last_error = _f(b"last_error")
            state.last_error_code = int(_f(b"last_error_code") or 0)
            state.last_error_at = float(_f(b"last_error_at") or 0)
            state.last_success_at = float(_f(b"last_success_at") or 0)
    except Exception as exc:
        logger.debug("model_fleet_manager: redis read failed model=%s error=%s", model_id, exc)
    return state


async def _write_model_state(model_id: str, updates: Dict[str, str]) -> None:
    redis = await _get_redis()
    if redis is None:
        return
    try:
        key = _model_key(model_id, "state")
        await redis.hset(key, mapping=updates)
        # State TTL: keep for 24 hours
        await redis.expire(key, 86400)
    except Exception as exc:
        logger.debug("model_fleet_manager: redis write failed model=%s error=%s", model_id, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def record_success(model_id: str, *, latency_ms: float, tokens_out: int = 0) -> None:
    """Record a successful model response. Updates rolling counters and latency."""
    now = time.time()
    state = await _read_model_state(model_id)

    # Exponential moving average for latency (α=0.2)
    alpha = 0.2
    prev = state.avg_latency_ms or latency_ms
    new_avg = alpha * latency_ms + (1 - alpha) * prev

    await _write_model_state(model_id, {
        "success_count_1h": str(state.success_count_1h + 1),
        "avg_latency_ms": str(round(new_avg, 1)),
        "last_success_at": str(now),
        # Clear cooldown on success
        "cooldown_until": "0",
        "last_error_code": str(state.last_error_code),
        "last_error": state.last_error,
        "error_count_1h": str(state.error_count_1h),
        "last_error_at": str(state.last_error_at),
    })
    logger.debug(
        "fleet_record_success model=%s latency_ms=%.0f avg_ms=%.0f",
        model_id, latency_ms, new_avg,
    )


async def record_error(model_id: str, *, error_code: int, error_msg: str = "") -> None:
    """Record a model error. Sets cooldown based on error code."""
    now = time.time()
    state = await _read_model_state(model_id)

    cooldown_s = _COOLDOWN_BY_CODE.get(error_code, _DEFAULT_COOLDOWN)
    new_cooldown = now + cooldown_s

    await _write_model_state(model_id, {
        "error_count_1h": str(state.error_count_1h + 1),
        "last_error": error_msg[:200],
        "last_error_code": str(error_code),
        "last_error_at": str(now),
        "cooldown_until": str(new_cooldown),
        "success_count_1h": str(state.success_count_1h),
        "avg_latency_ms": str(state.avg_latency_ms),
        "last_success_at": str(state.last_success_at),
    })
    logger.info(
        "fleet_record_error model=%s code=%d cooldown_s=%.0f msg=%s",
        model_id, error_code, cooldown_s, error_msg[:80],
    )


async def get_available_models(
    capability: str,
    *,
    tier_filter: Optional[str] = None,   # "free" | "paid_standard" | "paid_premium" | None
    min_context_window: int = 0,
    exclude_ids: Optional[List[str]] = None,
    include_cooling: bool = False,
) -> List[Dict[str, Any]]:
    """
    Return ordered list of available models for a capability pool.

    Each entry: {model_id, provider, tier, context_window, max_output_tokens,
                 state: ModelState, score: float, notes}

    Models are ordered by: availability > success_rate > (1/avg_latency) > pool priority.
    Cooling models are excluded unless include_cooling=True.
    """
    pool = _POOL_REGISTRY.get(capability, [])
    if not pool:
        # Fall back to chat pool for unknown capabilities
        pool = _POOL_REGISTRY.get("chat", [])

    excluded = set(exclude_ids or [])
    results = []

    for entry in pool:
        if entry.model_id in excluded:
            continue
        if tier_filter and entry.tier != tier_filter:
            continue
        if min_context_window and entry.context_window < min_context_window:
            continue

        state = await _read_model_state(entry.model_id)

        if state.is_cooling and not include_cooling:
            continue

        # Score: success_rate (0–1) boosted by low latency, penalised by cooling
        latency_factor = 1.0 / max(1.0, state.avg_latency_ms / 1000.0)
        score = state.success_rate * latency_factor
        if state.is_cooling:
            score *= 0.1  # heavy penalty even if include_cooling

        results.append({
            "model_id": entry.model_id,
            "provider": entry.provider,
            "tier": entry.tier,
            "context_window": entry.context_window,
            "max_output_tokens": entry.max_output_tokens,
            "notes": entry.notes,
            "state": {
                "availability": state.availability,
                "cooldown_until": state.cooldown_until,
                "cooldown_remaining_s": max(0.0, round(state.cooldown_until - time.time(), 1)),
                "error_count_1h": state.error_count_1h,
                "success_count_1h": state.success_count_1h,
                "success_rate": state.success_rate,
                "avg_latency_ms": state.avg_latency_ms,
                "last_error_code": state.last_error_code,
                "last_error": state.last_error,
                "last_error_at": state.last_error_at,
                "last_success_at": state.last_success_at,
            },
            "score": round(score, 4),
        })

    # Sort: available first, then by score descending
    results.sort(key=lambda m: (
        m["state"]["availability"] != "available",
        -m["score"],
    ))
    return results


async def get_model_state(model_id: str) -> Dict[str, Any]:
    """Return live state dict for a single model."""
    entry = _ALL_MODEL_IDS.get(model_id)
    state = await _read_model_state(model_id)
    return {
        "model_id": model_id,
        "provider": entry.provider if entry else "unknown",
        "tier": entry.tier if entry else "unknown",
        "capabilities": entry.capabilities if entry else [],
        "context_window": entry.context_window if entry else 0,
        "notes": entry.notes if entry else "",
        "availability": state.availability,
        "cooldown_until": state.cooldown_until,
        "cooldown_remaining_s": max(0.0, round(state.cooldown_until - time.time(), 1)),
        "error_count_1h": state.error_count_1h,
        "success_count_1h": state.success_count_1h,
        "success_rate": state.success_rate,
        "avg_latency_ms": state.avg_latency_ms,
        "last_error_code": state.last_error_code,
        "last_error": state.last_error,
        "last_error_at": state.last_error_at,
        "last_success_at": state.last_success_at,
    }


async def get_fleet_status() -> Dict[str, Any]:
    """
    Full fleet status for /control/model-fleet/status.
    Returns per-pool summary and per-model state.
    """
    pools_summary: Dict[str, Any] = {}
    all_model_states: Dict[str, Any] = {}

    for pool_id, entries in _POOL_REGISTRY.items():
        available = 0
        cooling = 0
        for entry in entries:
            if entry.model_id in all_model_states:
                s = all_model_states[entry.model_id]
            else:
                s = await get_model_state(entry.model_id)
                all_model_states[entry.model_id] = s
            if s["availability"] == "available":
                available += 1
            elif s["availability"] == "cooling":
                cooling += 1

        pools_summary[pool_id] = {
            "total_models": len(entries),
            "available": available,
            "cooling": cooling,
            "unavailable": len(entries) - available - cooling,
        }

    return {
        "pools": pools_summary,
        "models": all_model_states,
        "total_registered_models": len(_ALL_MODEL_IDS),
        "generated_at": time.time(),
    }


def get_pool_names() -> List[str]:
    """Return list of all registered pool names."""
    return list(_POOL_REGISTRY.keys())


def get_pool_model_ids(capability: str) -> List[str]:
    """Return ordered model_id list for a capability pool (no Redis I/O)."""
    return [e.model_id for e in _POOL_REGISTRY.get(capability, [])]


def get_model_entry(model_id: str) -> Optional[ModelEntry]:
    """Return static ModelEntry for a model_id, or None."""
    return _ALL_MODEL_IDS.get(model_id)


def infer_capability_from_task(task: str, profile: str = "") -> str:
    """
    Infer the best capability pool from task text and profile hint.
    Returns a pool name from: coding, reasoning, writing, chat, vision, agents, video.
    """
    task_l = (task or "").lower()
    profile_l = (profile or "").lower()

    # Profile hints take priority
    if "coding" in profile_l or "code" in profile_l:
        return "coding"
    if "reasoning" in profile_l or "architecture" in profile_l:
        return "reasoning"
    if "tool" in profile_l or "agent" in profile_l:
        return "agents"
    if "vision" in profile_l or "image" in profile_l or "photo" in profile_l:
        return "vision"
    if "video" in profile_l:
        return "video"
    if "writ" in profile_l or "doc" in profile_l:
        return "writing"

    # Task content signals
    coding_kw = {"implement", "code", "function", "class", "bug", "refactor", "patch",
                 "script", "debug", "compile", "syntax", "algorithm", "api", "endpoint"}
    reasoning_kw = {"architecture", "design", "review", "analyze", "tradeoff", "strategy",
                    "plan", "evaluate", "compare", "decision", "assess", "explain"}
    writing_kw = {"write", "document", "summarize", "draft", "compose", "paragraph",
                  "essay", "report", "readme", "changelog", "blog", "email"}
    vision_kw = {"image", "photo", "picture", "screenshot", "diagram", "chart", "ocr",
                 "visual", "pixel", "jpeg", "png", "svg"}
    agent_kw = {"run", "execute", "deploy", "build", "test", "tool", "function call",
                "workflow", "automate", "pipeline", "shell", "command"}
    video_kw = {"video", "mp4", "frame", "clip", "movie", "scene", "timestamp"}

    words = set(task_l.split())
    if any(kw in task_l for kw in video_kw):
        return "video"
    if any(kw in task_l for kw in vision_kw):
        return "vision"
    if any(kw in task_l for kw in coding_kw) or any(w in words for w in coding_kw):
        return "coding"
    if any(kw in task_l for kw in reasoning_kw):
        return "reasoning"
    if any(kw in task_l for kw in agent_kw):
        return "agents"
    if any(kw in task_l for kw in writing_kw):
        return "writing"
    return "chat"
