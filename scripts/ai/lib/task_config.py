"""
task_config — TaskConfig dataclass for local task dispatch.

Phase 74C — single config object built from CLI args + env vars + defaults.
Downstream runners (DirectRunner, HybridRunner, etc.) consume TaskConfig;
nothing builds inline config dicts any more.

Token budget resolution order (highest priority first):
  1. Explicit --max-tokens CLI flag
  2. DIRECT_MAX_TOKENS env var  (direct/ralph modes)
  3. LLAMA_MAX_TOKENS env var   (direct/ralph modes, from llm_config SSOT)
  4. Mode-specific hardcoded default (see _MODE_TOKEN_DEFAULTS)

Switchboard profile token values are informational — the actual budget is
ENV-driven so training-loop overrides (EVAL_MAX_TOKENS=512) still work.
"""

import os
from dataclasses import dataclass

# Canonical role-matrix values and their legacy aliases.
# Source of truth: docs/architecture/role-matrix.md
_ROLE_ALIASES: dict[str, str] = {
    "plan":      "architect",
    "implement": "implementer",
    "review":    "reviewer",
    "research":  "implementer",
}

_CANONICAL_ROLES = {"orchestrator", "architect", "implementer", "reviewer"}

# Mode → sensible default max_tokens when no env var is set.
# Direct/ralph: 4096 production default (env DIRECT_MAX_TOKENS overrides).
# Hybrid: coordinator manages its own budget; we send 0 (ignored by /query).
# Agent: aq-agent-loop sets LLAMA_MAX_TOKENS=512 internally; use 1200 here
#        as the outer cap (aq-agent-loop's own env var takes precedence).
_MODE_TOKEN_DEFAULTS: dict[str, int] = {
    "direct": 4096,
    "ralph":  4096,
    "hybrid": 0,     # coordinator manages tokens
    "agent":  1200,  # aq-agent-loop overrides internally
}

_VALID_MODES = {"agent", "hybrid", "direct", "ralph"}

# Valid task profile names — kept in sync with llm_config.TASK_PROFILES.
# "auto" is a sentinel resolved by classify_task_type() before TaskConfig is built.
_VALID_TASK_TYPES = {"structured", "lookup", "code", "reasoning", "agent"}


def normalize_role(role: str) -> str:
    """Map legacy alias to canonical role-matrix value."""
    return _ROLE_ALIASES.get(role, role)


@dataclass
class TaskConfig:
    mode: str
    role: str           # canonical role-matrix value
    max_tokens: int
    timeout_secs: int
    llama_url: str
    hybrid_url: str
    ralph_url: str
    task_type: str      # modal payload profile (structured/lookup/code/reasoning/agent)
    tool_manifest: str = "full"  # agent mode only: "full" | "self-improvement"

    @classmethod
    def from_args(
        cls,
        mode: str,
        role: str,
        timeout_secs: int,
        max_tokens: int | None,
        llama_url: str,
        hybrid_url: str,
        ralph_url: str,
        task_type: str = "code",
        max_tokens_hint: int | None = None,
        tool_manifest: str = "full",
    ) -> "TaskConfig":
        """Build a TaskConfig, resolving token budget and normalising role."""
        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid mode {mode!r}. Valid: {sorted(_VALID_MODES)}")

        canonical_role = normalize_role(role)
        if canonical_role not in _CANONICAL_ROLES:
            raise ValueError(
                f"Invalid role {role!r}. Valid: {sorted(_CANONICAL_ROLES)} "
                f"(or legacy aliases: {sorted(_ROLE_ALIASES)})"
            )

        resolved_tokens = cls._resolve_tokens(mode, max_tokens, hint=max_tokens_hint)
        resolved_task_type = task_type if task_type in _VALID_TASK_TYPES else "code"

        return cls(
            mode=mode,
            role=canonical_role,
            max_tokens=resolved_tokens,
            timeout_secs=timeout_secs,
            llama_url=llama_url,
            hybrid_url=hybrid_url,
            ralph_url=ralph_url,
            task_type=resolved_task_type,
            tool_manifest=tool_manifest if tool_manifest in ("full", "self-improvement") else "full",
        )

    @staticmethod
    def _resolve_tokens(mode: str, explicit: int | None, hint: int | None = None) -> int:
        """Priority: explicit CLI → DIRECT_MAX_TOKENS env → LLAMA_MAX_TOKENS env → hint → default.

        hint: profile max_tokens_hint (Phase 163). Applied after env vars so
        DIRECT_MAX_TOKENS=8192 still overrides the profile suggestion. This lets
        each task class carry a sensible default without the mode-global 4096 fallback
        generating unnecessarily large budgets for tiny/structured tasks.
        """
        if explicit is not None:
            return explicit
        if mode in ("direct", "ralph"):
            env_direct = os.environ.get("DIRECT_MAX_TOKENS")
            if env_direct:
                try:
                    return int(env_direct)
                except ValueError:
                    pass
        env_llama = os.environ.get("LLAMA_MAX_TOKENS")
        if env_llama:
            try:
                return int(env_llama)
            except ValueError:
                pass
        if hint is not None:
            return hint
        return _MODE_TOKEN_DEFAULTS.get(mode, 1200)
