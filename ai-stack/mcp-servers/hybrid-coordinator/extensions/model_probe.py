"""
model_probe.py — Runtime model capability detection for hybrid-coordinator.

Queries the loaded llama.cpp model at startup to detect:
  - Context window size
  - Thinking mode (has <think> tags, can disable via enable_thinking=false)
  - Function-calling support
  - Output tokens/second (measured, not assumed)

Derives token budgets from measured speed × timeout windows so the harness
automatically scales when the model is swapped — no hardcoded model names.

Profile is cached to AI_MODEL_PROFILE_PATH and re-used unless stale (model changed).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# shared/ is at ai-stack/mcp-servers/shared/ — parents[2] from this file's location.
_SHARED_PATH = str(Path(__file__).resolve().parents[2])
if _SHARED_PATH not in sys.path:
    sys.path.insert(0, _SHARED_PATH)

from shared.llm_config import build_llama_payload, PROBE_MAX_TOKENS  # noqa: E402

logger = logging.getLogger("model-probe")

_PROFILE_VERSION = 2
_PROBE_TIMEOUT = 30.0
_SPEED_PROBE_TOKENS = 60  # generation tokens in the speed probe
_SWITCHBOARD_TIMEOUT_S = float(os.getenv("LLAMA_CPP_SWITCHBOARD_TIMEOUT_S", "900"))
_DIRECT_TIMEOUT_S = float(os.getenv("LLAMA_CPP_INFERENCE_TIMEOUT_SECONDS", "180"))
# Fraction of the timeout window we allow generation to use (leaves headroom for
# prompt processing, network, and safety margin).
_WINDOW_FRACTION_INTERACTIVE = 0.65
_WINDOW_FRACTION_SYNTHESIS = 0.65
_WINDOW_FRACTION_HEAVY = 0.85


@dataclass
class ModelProfile:
    """Detected + computed capabilities for the currently loaded model."""
    model_id: str = "unknown"
    model_path: str = ""
    context_length: int = 4096
    measured_tps_output: float = 5.0
    has_thinking_mode: bool = False
    can_disable_thinking: bool = False
    supports_tools: bool = False
    supports_system_prompt: bool = True
    eos_token: str = ""
    # Computed token budgets (tps × timeout × window_fraction)
    budget_interactive: int = 400
    budget_synthesis: int = 1500
    budget_heavy: int = 2500
    budget_lookup: int = 400
    budget_reasoning: int = 1200
    # Context budgets (how much retrieved content goes into the prompt)
    ctx_budget_lookup: int = 1200
    ctx_budget_synthesis: int = 2500
    ctx_budget_reasoning: int = 2000
    # Probe metadata
    profile_version: int = _PROFILE_VERSION
    probed_at: str = ""
    probe_model_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelProfile":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


def _default_profile() -> ModelProfile:
    """Safe fallback used when the probe fails — conservative but functional."""
    return ModelProfile(
        model_id="unknown-fallback",
        measured_tps_output=4.0,
        has_thinking_mode=False,
        can_disable_thinking=False,
        budget_interactive=600,
        budget_synthesis=2000,
        budget_heavy=2700,
        budget_lookup=600,
        budget_reasoning=1500,
        ctx_budget_lookup=1200,
        ctx_budget_synthesis=2500,
        ctx_budget_reasoning=2000,
    )


def _compute_budgets(tps: float, has_thinking: bool) -> Dict[str, int]:
    """Compute token budgets from measured throughput and timeout windows."""
    # When thinking is enabled and cannot be disabled, ~20-25% of tokens go to
    # <think> blocks on average — we factor that into the answer budget.
    think_penalty = 0.78 if has_thinking else 1.0

    interactive = int(tps * _DIRECT_TIMEOUT_S * _WINDOW_FRACTION_INTERACTIVE * think_penalty)
    synthesis = int(tps * _SWITCHBOARD_TIMEOUT_S * _WINDOW_FRACTION_SYNTHESIS * think_penalty)
    heavy = int(tps * _SWITCHBOARD_TIMEOUT_S * _WINDOW_FRACTION_HEAVY * think_penalty)

    # Lookup and reasoning are sub-classes of interactive/synthesis
    lookup = int(interactive * 0.60)
    reasoning = int(synthesis * 0.70)

    # Context budgets: allow 1.25× the generation budget for input context
    ctx_lookup = int(lookup * 1.5)
    ctx_synthesis = int(synthesis * 1.25)
    ctx_reasoning = int(reasoning * 1.5)

    # Floor: ensure budgets are large enough to produce any visible output
    # (thinking models need ≥120 tokens just for the think block)
    min_gen = 250 if has_thinking else 100
    return {
        "budget_interactive": max(interactive, min_gen),
        "budget_synthesis": max(synthesis, min_gen * 4),
        "budget_heavy": max(heavy, min_gen * 6),
        "budget_lookup": max(lookup, min_gen),
        "budget_reasoning": max(reasoning, min_gen * 3),
        "ctx_budget_lookup": max(ctx_lookup, 800),
        "ctx_budget_synthesis": max(ctx_synthesis, 1500),
        "ctx_budget_reasoning": max(ctx_reasoning, 1200),
    }


async def _probe_speed(client: httpx.AsyncClient, base_url: str) -> float:
    """Measure output t/s with a short forced-generation prompt."""
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{base_url}/v1/chat/completions",
            json=build_llama_payload(
                [{"role": "user", "content": "List the numbers 1 through 20 separated by commas."}],
                max_tokens=_SPEED_PROBE_TOKENS,
                temperature=0,
            ),
            timeout=_PROBE_TIMEOUT,
        )
        elapsed = time.perf_counter() - t0
        data = resp.json()
        tokens = data.get("usage", {}).get("completion_tokens", 0)
        if elapsed > 0.5 and tokens >= 10:
            tps = tokens / elapsed
            logger.info("model_probe speed=%.1f t/s (%d tokens / %.1fs)", tps, tokens, elapsed)
            return round(tps, 1)
    except Exception as exc:
        logger.warning("model_probe speed_probe_failed: %s", exc)
    return 4.0  # conservative fallback


def _detect_thinking(chat_template: str, caps: Dict[str, Any]) -> tuple[bool, bool]:
    """
    Return (has_thinking_mode, can_disable_thinking) from template text + caps.
    Does not rely on model name — purely structural detection.
    """
    has = bool(caps.get("supports_preserve_reasoning")) or "<think>" in chat_template
    can_disable = "enable_thinking" in chat_template and has
    return has, can_disable


async def probe(llama_cpp_url: str, profile_path: Optional[Path] = None) -> ModelProfile:
    """
    Probe the loaded model and return (and cache) its ModelProfile.

    Uses cached profile if the model_id matches and version is current.
    """
    profile_path = profile_path or _default_profile_path()

    # Load cached profile if it matches the current model
    cached = _load_cached(profile_path)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Get model identity + context length
        try:
            models_resp = await client.get(f"{llama_cpp_url}/v1/models")
            model_data = models_resp.json().get("data", [{}])[0]
            model_id = str(model_data.get("id", "unknown"))
            meta = model_data.get("meta", {})
            context_length = int(meta.get("n_ctx_train", 4096))
        except Exception as exc:
            logger.warning("model_probe models_fetch_failed: %s — using fallback", exc)
            return cached or _default_profile()

        if cached and cached.probe_model_id == model_id:
            logger.info("model_probe cache_hit model_id=%s", model_id)
            return cached

        logger.info("model_probe running model_id=%s ctx=%d", model_id, context_length)

        # Step 2: Detect capabilities from /props
        has_thinking = False
        can_disable = False
        supports_tools = False
        supports_system = True
        eos_token = ""
        model_path = ""
        try:
            props_resp = await client.get(f"{llama_cpp_url}/props")
            props = props_resp.json()
            caps = props.get("chat_template_caps", {})
            template = props.get("chat_template", "")
            has_thinking, can_disable = _detect_thinking(template, caps)
            supports_tools = bool(caps.get("supports_tools"))
            supports_system = bool(caps.get("supports_system_role", True))
            eos_token = str(props.get("eos_token", ""))
            model_path = str(props.get("model_path", ""))
        except Exception as exc:
            logger.warning("model_probe props_fetch_failed: %s", exc)

        # Step 3: Measure output t/s
        tps = await _probe_speed(client, llama_cpp_url)

        # Step 4: Compute budgets
        budgets = _compute_budgets(tps, has_thinking and not can_disable)

        import datetime
        profile = ModelProfile(
            model_id=model_id,
            model_path=model_path,
            context_length=context_length,
            measured_tps_output=tps,
            has_thinking_mode=has_thinking,
            can_disable_thinking=can_disable,
            supports_tools=supports_tools,
            supports_system_prompt=supports_system,
            eos_token=eos_token,
            probed_at=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            probe_model_id=model_id,
            **budgets,
        )
        _save(profile, profile_path)
        logger.info(
            "model_probe complete model=%s tps=%.1f thinking=%s disable_think=%s "
            "ctx=%d budgets=interactive:%d synthesis:%d heavy:%d",
            model_id, tps, has_thinking, can_disable, context_length,
            profile.budget_interactive, profile.budget_synthesis, profile.budget_heavy,
        )
        return profile


def _default_profile_path() -> Path:
    env = os.getenv("AI_MODEL_PROFILE_PATH", "").strip()
    if env:
        return Path(env)
    # Detect repo root by flake.nix (most reliable anchor)
    here = Path(__file__).resolve().parent
    for candidate in [here, here.parent, here.parent.parent, here.parent.parent.parent, here.parent.parent.parent.parent]:
        if (candidate / "flake.nix").exists():
            return candidate / "config" / "model-profile.json"
    # Fallback: writable runtime location (dataDir from ai-stack.nix)
    return Path("/var/lib/ai-stack/model-profile.json")


def _load_cached(path: Path) -> Optional[ModelProfile]:
    try:
        if path.exists():
            d = json.loads(path.read_text())
            if d.get("profile_version") == _PROFILE_VERSION:
                return ModelProfile.from_dict(d)
    except Exception:
        pass
    return None


def _save(profile: ModelProfile, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile.to_dict(), indent=2))
    except Exception as exc:
        logger.warning("model_probe save_failed path=%s: %s", path, exc)


# Synchronous probe for use in scripts
def probe_sync(llama_cpp_url: str, profile_path: Optional[Path] = None) -> ModelProfile:
    import asyncio
    return asyncio.run(probe(llama_cpp_url, profile_path))
