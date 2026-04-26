"""
Canonical routing contract for the hybrid-coordinator.

Single source of truth for:
- RoutingTier enum  (LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP)
- PROFILE_REGISTRY  (profile-name → tier + model-alias, sourced from Config env vars)
- RoutingDecision   (unified dataclass shared by all router implementations)
- CostEstimates     (per-tier, sourced from env, not hard-coded)
- validate_profile  (startup guard: raises ValueError if profile not in registry)

Usage
-----
    from routing_contract import RoutingTier, PROFILE_REGISTRY, RoutingDecision, CostEstimates

    decision = RoutingDecision(
        tier=RoutingTier.REMOTE_FREE,
        profile="remote-coding",
        model_alias="qwen-coder",
        task_type="code",
        reason="task_type=code_requires_remote",
        confidence=0.85,
    )
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger("hybrid-coordinator.routing_contract")


# ---------------------------------------------------------------------------
# Tier hierarchy
# ---------------------------------------------------------------------------

class RoutingTier(Enum):
    """
    Ordered routing tiers, cheapest-first.

    Escalation order: LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP
    """
    LOCAL           = "local"            # llama.cpp, $0, ~90-120s on this hw
    EDGE            = "edge"             # local specialised model (coder/reasoning), $0
    REMOTE_FREE     = "remote_free"      # OpenRouter free tier (gemini-flash, qwen), $0
    REMOTE_PAID     = "remote_paid"      # claude-sonnet / gpt-4o, $$
    REMOTE_FLAGSHIP = "remote_flagship"  # claude-opus-4, $$$

    def can_escalate_to(self) -> Optional["RoutingTier"]:
        """Return the next tier in the escalation chain, or None if at ceiling."""
        _chain = [
            RoutingTier.LOCAL,
            RoutingTier.EDGE,
            RoutingTier.REMOTE_FREE,
            RoutingTier.REMOTE_PAID,
            RoutingTier.REMOTE_FLAGSHIP,
        ]
        try:
            idx = _chain.index(self)
            return _chain[idx + 1] if idx + 1 < len(_chain) else None
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Unified routing decision
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """
    Canonical result produced by any router in the system.

    All router implementations (task_classifier path, llm_router path,
    local-orchestrator path) should converge on this type so callers can
    reason uniformly about the decision.
    """
    tier: RoutingTier
    profile: str           # coordinator profile name, e.g. "remote-coding"
    model_alias: str       # human-readable model name, e.g. "qwen-coder"
    task_type: str         # lookup | format | synthesize | code | reasoning
    reason: str            # machine-readable reason code
    confidence: float      # 0.0–1.0
    escalated_from: Optional[RoutingTier] = None
    advisor_action: Optional[str] = None    # "proceed" | "modify" | "stop"
    extra: Dict = field(default_factory=dict)

    @property
    def is_local(self) -> bool:
        return self.tier in (RoutingTier.LOCAL, RoutingTier.EDGE)

    @property
    def is_remote(self) -> bool:
        return not self.is_local

    def to_dict(self) -> Dict:
        return {
            "tier": self.tier.value,
            "profile": self.profile,
            "model_alias": self.model_alias,
            "task_type": self.task_type,
            "reason": self.reason,
            "confidence": self.confidence,
            "escalated_from": self.escalated_from.value if self.escalated_from else None,
            "advisor_action": self.advisor_action,
        }


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProfileEntry:
    """Metadata for a single coordinator profile."""
    tier: RoutingTier
    model_alias: str        # human-readable model name used in payloads
    description: str = ""


def _build_profile_registry() -> Dict[str, ProfileEntry]:
    """
    Build profile registry sourced from Config env vars so it stays in sync
    with [profile-card:*] sections in switchboard.nix without duplicating
    model names here.
    """
    try:
        from config import Config
        alias_gemini    = Config.SWITCHBOARD_REMOTE_ALIAS_GEMINI       or "gemini-2.0-flash"
        alias_free      = Config.SWITCHBOARD_REMOTE_ALIAS_FREE         or "gemini-2.0-flash"
        alias_coding    = Config.SWITCHBOARD_REMOTE_ALIAS_CODING       or "qwen-coder"
        alias_reasoning = Config.SWITCHBOARD_REMOTE_ALIAS_REASONING    or "claude-sonnet-4-6"
        alias_tool      = Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING or alias_reasoning
    except (ImportError, AttributeError):
        # Fallback when imported outside the coordinator process (tests, CI)
        alias_gemini    = os.getenv("SWITCHBOARD_REMOTE_ALIAS_GEMINI",       "gemini-2.0-flash")
        alias_free      = os.getenv("SWITCHBOARD_REMOTE_ALIAS_FREE",         "gemini-2.0-flash")
        alias_coding    = os.getenv("SWITCHBOARD_REMOTE_ALIAS_CODING",       "qwen-coder")
        alias_reasoning = os.getenv("SWITCHBOARD_REMOTE_ALIAS_REASONING",    "claude-sonnet-4-6")
        alias_tool      = os.getenv("SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING", alias_reasoning)

    return {
        "default": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Default local harness lane",
        ),
        # ── local tiers ──────────────────────────────────────────────────────
        "local": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Direct llama.cpp inference, no switchboard",
        ),
        "local-chat": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Chat-optimised local inference",
        ),
        # Continue IDE lane — local model via switchboard ingress
        "continue-local": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="VSCode Continue IDE local lane via switchboard",
        ),
        "local-agent": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Local agent lane for direct harness execution",
        ),
        # ── edge tiers (local specialised models) ────────────────────────────
        "local-coding": ProfileEntry(
            tier=RoutingTier.EDGE,
            model_alias="llama-cpp-coder",
            description="Local coder model (LLAMA_CPP_CODER_URL)",
        ),
        "local-reasoning": ProfileEntry(
            tier=RoutingTier.EDGE,
            model_alias="llama-cpp-reasoning",
            description="Local reasoning model (LLAMA_CPP_REASONING_URL / DeepSeek-R1)",
        ),
        # ── remote-free tiers ────────────────────────────────────────────────
        "remote-free": ProfileEntry(
            tier=RoutingTier.REMOTE_FREE,
            model_alias=alias_free,
            description="Remote free-tier model (Gemini flash or equivalent)",
        ),
        "remote-gemini": ProfileEntry(
            tier=RoutingTier.REMOTE_FREE,
            model_alias=alias_gemini,
            description="Gemini model via OpenRouter free tier",
        ),
        "remote-default": ProfileEntry(
            tier=RoutingTier.REMOTE_FREE,
            model_alias=alias_gemini,
            description="Default remote orchestration lane",
        ),
        # ── remote-paid tiers ────────────────────────────────────────────────
        "remote-coding": ProfileEntry(
            tier=RoutingTier.REMOTE_PAID,
            model_alias=alias_coding,
            description="Remote coding-specialist model (Qwen-coder or equivalent)",
        ),
        "remote-reasoning": ProfileEntry(
            tier=RoutingTier.REMOTE_PAID,
            model_alias=alias_reasoning,
            description="Remote reasoning model (Claude Sonnet or equivalent)",
        ),
        "remote-tool-calling": ProfileEntry(
            tier=RoutingTier.REMOTE_PAID,
            model_alias=alias_tool,
            description="Remote model with reliable tool-calling support",
        ),
        "local-tool-calling": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Local tool-calling lane",
        ),
        "embedding-local": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="embeddings-local",
            description="Local embeddings-only retrieval lane",
        ),
        "embedded-assist": ProfileEntry(
            tier=RoutingTier.LOCAL,
            model_alias="llama-cpp-local",
            description="Compact embedded-assist lane",
        ),
    }


# Module-level registry — built once at import time.
PROFILE_REGISTRY: Dict[str, ProfileEntry] = _build_profile_registry()


def validate_profile(profile: str) -> ProfileEntry:
    """
    Return the ProfileEntry for *profile*, or raise ValueError.

    Call at startup or before delegating to catch profile-name drift early.
    """
    entry = PROFILE_REGISTRY.get(profile)
    if entry is None:
        known = ", ".join(sorted(PROFILE_REGISTRY))
        raise ValueError(
            f"Unknown routing profile {profile!r}. Known profiles: {known}"
        )
    return entry


def profile_for_tier(tier: RoutingTier) -> str:
    """Return the default profile name for a given tier."""
    _defaults: Dict[RoutingTier, str] = {
        RoutingTier.LOCAL:            "local",
        RoutingTier.EDGE:             "local-coding",
        RoutingTier.REMOTE_FREE:      "remote-free",
        RoutingTier.REMOTE_PAID:      "remote-reasoning",
        # No dedicated flagship switchboard profile exists today.
        RoutingTier.REMOTE_FLAGSHIP:  "remote-reasoning",
    }
    return _defaults[tier]


def profile_for_model_alias(model_alias: str, *, tier_hint: Optional[RoutingTier] = None) -> str:
    """Map legacy llm_router model names to canonical coordinator profiles."""
    normalized = str(model_alias or "").strip().lower()
    if not normalized:
        return profile_for_tier(tier_hint or RoutingTier.LOCAL)

    explicit = {
        "llama-cpp-local": "local",
        "qwen-coder": "remote-coding",
        "gemini-free": "remote-free",
        "gemini": "remote-gemini",
        "gemini-2.0-flash": "remote-gemini",
        "claude-sonnet": "remote-reasoning",
        # Until switchboard exposes a distinct flagship profile, critical
        # requests reuse the strongest existing reasoning lane.
        "claude-opus": "remote-reasoning",
    }
    profile = explicit.get(normalized)
    if profile:
        return profile
    return profile_for_tier(tier_hint or RoutingTier.LOCAL)


# ---------------------------------------------------------------------------
# Cost estimates (env-sourced, not hard-coded)
# ---------------------------------------------------------------------------

class CostEstimates:
    """
    Per-tier cost estimates (USD per task, rough order-of-magnitude).

    Read from env vars so pricing can be updated without code changes.
    Local/Edge/Free tiers are always $0 (infrastructure cost already paid).
    """
    LOCAL:           float = 0.0
    EDGE:            float = 0.0
    REMOTE_FREE:     float = 0.0
    REMOTE_PAID:     float = float(os.getenv("ROUTING_COST_REMOTE_PAID",     "0.005"))
    REMOTE_FLAGSHIP: float = float(os.getenv("ROUTING_COST_REMOTE_FLAGSHIP", "0.025"))

    _TIER_MAP: Dict[RoutingTier, float] = {}

    @classmethod
    def for_tier(cls, tier: RoutingTier) -> float:
        return cls._TIER_MAP.get(tier, 0.0)


CostEstimates._TIER_MAP = {
    RoutingTier.LOCAL:            CostEstimates.LOCAL,
    RoutingTier.EDGE:             CostEstimates.EDGE,
    RoutingTier.REMOTE_FREE:      CostEstimates.REMOTE_FREE,
    RoutingTier.REMOTE_PAID:      CostEstimates.REMOTE_PAID,
    RoutingTier.REMOTE_FLAGSHIP:  CostEstimates.REMOTE_FLAGSHIP,
}


# ---------------------------------------------------------------------------
# Legacy adapter — backward compat for llm_router.AgentTier
# ---------------------------------------------------------------------------

def legacy_tier_to_routing_tier(legacy_tier_value: str) -> RoutingTier:
    """
    Map llm_router.AgentTier.value strings to RoutingTier so llm_router can
    emit RoutingDecision objects without a circular import.

    "local"    → LOCAL
    "free"     → REMOTE_FREE
    "paid"     → REMOTE_PAID
    "critical" → REMOTE_FLAGSHIP
    """
    _map: Dict[str, RoutingTier] = {
        "local":    RoutingTier.LOCAL,
        "free":     RoutingTier.REMOTE_FREE,
        "paid":     RoutingTier.REMOTE_PAID,
        "critical": RoutingTier.REMOTE_FLAGSHIP,
    }
    tier = _map.get(legacy_tier_value)
    if tier is None:
        logger.warning("Unknown legacy tier %r, defaulting to LOCAL", legacy_tier_value)
        return RoutingTier.LOCAL
    return tier
