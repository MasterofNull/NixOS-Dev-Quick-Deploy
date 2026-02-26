"""
Hybrid-coordinator configuration: Config, RoutingConfig, PerformanceWindow,
OptimizationProposal, and related helpers.

Extracted from server.py (Phase 6.1 decomposition).
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from shared.stack_settings import HybridSettings

logger = logging.getLogger("hybrid-coordinator")

HYBRID_SETTINGS = HybridSettings.load()
STRICT_ENV = os.getenv("AI_STRICT_ENV", "true").strip().lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _enforce_startup_env() -> None:
    if not STRICT_ENV:
        return

    required_env = [
        "QDRANT_URL",
        "LLAMA_CPP_BASE_URL",
        "EMBEDDING_SERVICE_URL",
        "AIDB_URL",
        "REDIS_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD_FILE",
        "HYBRID_API_KEY_FILE",
        "EMBEDDING_API_KEY_FILE",
        "MCP_SERVER_MODE",
        "MCP_SERVER_PORT",
    ]
    for env_name in required_env:
        _require_env(env_name)

    for secret_env in ("POSTGRES_PASSWORD_FILE", "HYBRID_API_KEY_FILE", "EMBEDDING_API_KEY_FILE"):
        secret_file = Path(_require_env(secret_env))
        if not secret_file.exists():
            raise RuntimeError(
                f"AI_STRICT_ENV requires existing secret file for {secret_env}: {secret_file}"
            )
        if not secret_file.is_file():
            raise RuntimeError(
                f"AI_STRICT_ENV requires file path for {secret_env}: {secret_file}"
            )


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Hybrid coordinator configuration."""

    QDRANT_URL = _require_env("QDRANT_URL") if STRICT_ENV else os.getenv("QDRANT_URL", HYBRID_SETTINGS.qdrant_url)
    QDRANT_API_KEY_FILE = os.getenv("QDRANT_API_KEY_FILE", "")
    QDRANT_API_KEY = ""
    QDRANT_HNSW_M = int(os.getenv("QDRANT_HNSW_M", HYBRID_SETTINGS.qdrant_hnsw_m))
    QDRANT_HNSW_EF_CONSTRUCT = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", HYBRID_SETTINGS.qdrant_hnsw_ef_construct))
    QDRANT_HNSW_FULL_SCAN_THRESHOLD = int(
        os.getenv("QDRANT_HNSW_FULL_SCAN_THRESHOLD", HYBRID_SETTINGS.qdrant_hnsw_full_scan_threshold)
    )
    LLAMA_CPP_URL = _require_env("LLAMA_CPP_BASE_URL") if STRICT_ENV else os.getenv("LLAMA_CPP_BASE_URL", HYBRID_SETTINGS.llama_cpp_url)
    LLAMA_CPP_CODER_URL = os.getenv("LLAMA_CPP_CODER_URL", HYBRID_SETTINGS.llama_cpp_url)
    LLAMA_CPP_DEEPSEEK_URL = os.getenv("LLAMA_CPP_DEEPSEEK_URL", HYBRID_SETTINGS.llama_cpp_url)

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", HYBRID_SETTINGS.embedding_model)
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", HYBRID_SETTINGS.embedding_dimensions))
    EMBEDDING_SERVICE_URL = _require_env("EMBEDDING_SERVICE_URL") if STRICT_ENV else os.getenv("EMBEDDING_SERVICE_URL", "")
    EMBEDDING_API_KEY_FILE = os.getenv("EMBEDDING_API_KEY_FILE", "")
    EMBEDDING_API_KEY = ""
    AIDB_URL = _require_env("AIDB_URL") if STRICT_ENV else os.getenv("AIDB_URL", "")

    LOCAL_CONFIDENCE_THRESHOLD = float(
        os.getenv("LOCAL_CONFIDENCE_THRESHOLD", HYBRID_SETTINGS.local_confidence_threshold)
    )
    HIGH_VALUE_THRESHOLD = float(os.getenv("HIGH_VALUE_THRESHOLD", HYBRID_SETTINGS.high_value_threshold))
    PATTERN_EXTRACTION_ENABLED = os.getenv(
        "PATTERN_EXTRACTION_ENABLED", str(HYBRID_SETTINGS.pattern_extraction_enabled)
    ).lower() == "true"

    # Token Optimization Flags
    QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "false").lower() == "true"
    REMOTE_LLM_FEEDBACK_ENABLED = os.getenv("REMOTE_LLM_FEEDBACK_ENABLED", "false").lower() == "true"
    MULTI_TURN_QUERY_EXPANSION = os.getenv("MULTI_TURN_QUERY_EXPANSION", "false").lower() == "true"
    DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1000"))
    # Canonical name; CONTEXT_COMPRESSION_ENABLED kept as alias below for back-compat.
    AI_CONTEXT_COMPRESSION_ENABLED = os.getenv(
        "AI_CONTEXT_COMPRESSION_ENABLED",
        os.getenv("CONTEXT_COMPRESSION_ENABLED", "true"),
    ).lower() == "true"

    FINETUNE_DATA_PATH = os.path.expanduser(
        os.getenv(
            "FINETUNE_DATA_PATH",
            HYBRID_SETTINGS.finetune_data_path
            or "~/.local/share/nixos-ai-stack/interaction-archive/dataset.jsonl",
        )
    )
    CACHE_EPOCH = int(os.getenv("CACHE_EPOCH", "1"))
    AB_TEST_VARIANT_B_FRACTION = float(os.getenv("AB_TEST_VARIANT_B_FRACTION", "0.0"))
    API_KEY_FILE = _require_env("HYBRID_API_KEY_FILE") if STRICT_ENV else os.getenv("HYBRID_API_KEY_FILE", HYBRID_SETTINGS.api_key_file or "")
    API_KEY = ""
    AI_HARNESS_ENABLED = os.getenv("AI_HARNESS_ENABLED", "true").lower() == "true"
    AI_MEMORY_ENABLED = os.getenv("AI_MEMORY_ENABLED", "true").lower() == "true"
    AI_MEMORY_MAX_RECALL_ITEMS = int(os.getenv("AI_MEMORY_MAX_RECALL_ITEMS", "8"))
    AI_TREE_SEARCH_ENABLED = os.getenv("AI_TREE_SEARCH_ENABLED", "true").lower() == "true"
    AI_TREE_SEARCH_MAX_DEPTH = int(os.getenv("AI_TREE_SEARCH_MAX_DEPTH", "2"))
    AI_TREE_SEARCH_BRANCH_FACTOR = int(os.getenv("AI_TREE_SEARCH_BRANCH_FACTOR", "3"))
    AI_HARNESS_EVAL_ENABLED = os.getenv("AI_HARNESS_EVAL_ENABLED", "true").lower() == "true"
    AI_HARNESS_MIN_ACCEPTANCE_SCORE = float(os.getenv("AI_HARNESS_MIN_ACCEPTANCE_SCORE", "0.7"))
    AI_HARNESS_MAX_LATENCY_MS = int(os.getenv("AI_HARNESS_MAX_LATENCY_MS", "3000"))
    AI_CAPABILITY_DISCOVERY_ENABLED = os.getenv("AI_CAPABILITY_DISCOVERY_ENABLED", "true").lower() == "true"
    AI_CAPABILITY_DISCOVERY_TTL_SECONDS = int(os.getenv("AI_CAPABILITY_DISCOVERY_TTL_SECONDS", "1800"))
    AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS = int(os.getenv("AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS", "18"))
    AI_CAPABILITY_DISCOVERY_MAX_RESULTS = int(os.getenv("AI_CAPABILITY_DISCOVERY_MAX_RESULTS", "3"))
    AI_CAPABILITY_DISCOVERY_ON_QUERY = os.getenv("AI_CAPABILITY_DISCOVERY_ON_QUERY", "true").lower() == "true"
    AI_AUTONOMY_MAX_EXTERNAL_CALLS = int(os.getenv("AI_AUTONOMY_MAX_EXTERNAL_CALLS", "4"))
    AI_AUTONOMY_MAX_RETRIES = int(os.getenv("AI_AUTONOMY_MAX_RETRIES", "1"))
    AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = int(os.getenv("AI_AUTONOMY_MAX_RETRIEVAL_RESULTS", "8"))
    AI_PROMPT_CACHE_POLICY_ENABLED = os.getenv("AI_PROMPT_CACHE_POLICY_ENABLED", "true").lower() == "true"
    AI_PROMPT_CACHE_STATIC_PREFIX = os.getenv(
        "AI_PROMPT_CACHE_STATIC_PREFIX",
        "You are the NixOS AI stack coordinator. Prefer local-first secure execution.",
    )
    AI_SPECULATIVE_DECODING_ENABLED = os.getenv("AI_SPECULATIVE_DECODING_ENABLED", "false").lower() == "true"
    AI_SPECULATIVE_DECODING_MODE = os.getenv("AI_SPECULATIVE_DECODING_MODE", "draft-model")
    AI_CONTEXT_MAX_TOKENS = int(os.getenv("AI_CONTEXT_MAX_TOKENS", "3000"))


def _read_secret(path: str) -> str:
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


if not Config.QDRANT_API_KEY and Config.QDRANT_API_KEY_FILE:
    Config.QDRANT_API_KEY = _read_secret(Config.QDRANT_API_KEY_FILE)
if not Config.API_KEY and Config.API_KEY_FILE:
    Config.API_KEY = _read_secret(Config.API_KEY_FILE)
if not Config.EMBEDDING_API_KEY and Config.EMBEDDING_API_KEY_FILE:
    Config.EMBEDDING_API_KEY = _read_secret(Config.EMBEDDING_API_KEY_FILE)


# ============================================================================
# Hot-reloadable Routing Config (Phase 2.2.1)
# ============================================================================

@dataclass
class RoutingConfig:
    """Hot-reloadable routing threshold configuration.

    Reads ``~/.local/share/nixos-ai-stack/routing-config.json`` on each call
    to ``get_threshold()`` if the cached value is older than 60 seconds.
    Falls back to the env-var default when the file is absent or malformed.
    """

    threshold: float = field(
        default_factory=lambda: float(
            os.getenv("LOCAL_CONFIDENCE_THRESHOLD", HYBRID_SETTINGS.local_confidence_threshold)
        )
    )
    _path: Path = field(
        default_factory=lambda: Path.home() / ".local/share/nixos-ai-stack/routing-config.json",
        repr=False,
    )
    _loaded_at: float = field(default=0.0, repr=False)
    _ttl: float = field(default=60.0, repr=False)

    async def get_threshold(self) -> float:
        """Return current threshold, reloading from disk if TTL has expired."""
        now = time.monotonic()
        if now - self._loaded_at < self._ttl:
            return self.threshold
        if self._path.exists():
            try:
                raw = self._path.read_text(encoding="utf-8")
                data = json.loads(raw)
                value = float(data["local_confidence_threshold"])
                self.threshold = value
            except Exception:  # noqa: BLE001
                pass
        self._loaded_at = now
        return self.threshold

    def write_threshold(self, value: float) -> None:
        """Atomically write a new threshold to the config file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"local_confidence_threshold": value}), encoding="utf-8")
        tmp.replace(self._path)
        self.threshold = value
        self._loaded_at = time.monotonic()


# Module-level singleton used by routing and proposal handlers.
routing_config: RoutingConfig = RoutingConfig()


# ============================================================================
# Phase 4.2 — Structured Optimization Proposal System
# ============================================================================

class OptimizationProposalType(str, Enum):
    ROUTING_THRESHOLD_ADJUSTMENT = "routing_threshold_adjustment"
    ITERATION_LIMIT_INCREASE      = "iteration_limit_increase"
    MODEL_SWAP                    = "model_swap"
    CODE_CHANGE_REQUIRED          = "code_change_required"


class OptimizationProposal(BaseModel):
    proposal_type:    OptimizationProposalType
    target_config_key: str
    current_value:    Union[float, int, str]
    proposed_value:   Union[float, int, str]
    evidence_summary: str
    confidence:       float = Field(ge=0.0, le=1.0)


async def apply_proposal(proposal: OptimizationProposal) -> dict:
    """Dispatch a validated OptimizationProposal to its deterministic apply function."""
    ptype = proposal.proposal_type

    if ptype in (
        OptimizationProposalType.ROUTING_THRESHOLD_ADJUSTMENT,
        OptimizationProposalType.ITERATION_LIMIT_INCREASE,
    ):
        new_val = float(proposal.proposed_value)
        routing_config.write_threshold(new_val)
        logger.info(
            "proposal_applied type=%s key=%s old=%s new=%s confidence=%.2f",
            ptype, proposal.target_config_key,
            proposal.current_value, new_val, proposal.confidence,
        )
        return {"status": "applied", "new_value": new_val}

    if ptype == OptimizationProposalType.MODEL_SWAP:
        logger.info(
            "proposal_model_swap key=%s proposed=%s confidence=%.2f (manual step required)",
            proposal.target_config_key, proposal.proposed_value, proposal.confidence,
        )
        return {
            "status": "manual_required",
            "instructions": f"Update AI_MODEL_NAME={proposal.proposed_value} in NixOS ai-stack.nix, then nixos-rebuild switch",
        }

    if ptype == OptimizationProposalType.CODE_CHANGE_REQUIRED:
        return await _append_code_change_issue(proposal)

    return {"status": "unknown_type", "proposal_type": ptype}


async def _append_code_change_issue(proposal: OptimizationProposal) -> dict:
    """Append a structured issue entry to AI-STACK-IMPROVEMENT-PLAN.md."""
    plan_path = Path(__file__).parents[3] / "AI-STACK-IMPROVEMENT-PLAN.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = (
        f"\n\n### AUTO-GENERATED PROPOSAL — {now}\n\n"
        f"**Key:** `{proposal.target_config_key}`  \n"
        f"**Current:** `{proposal.current_value}`  **Proposed:** `{proposal.proposed_value}`  \n"
        f"**Confidence:** {proposal.confidence:.0%}  \n"
        f"**Evidence:** {proposal.evidence_summary}\n\n"
        f"- [ ] Review and implement: `{proposal.target_config_key}` → `{proposal.proposed_value}`\n"
    )
    try:
        with open(plan_path, "a") as fh:
            fh.write(entry)
        logger.info("proposal_issue_appended key=%s plan=%s", proposal.target_config_key, plan_path)
        return {"status": "issue_created", "plan_path": str(plan_path)}
    except OSError as exc:
        logger.error("proposal_issue_write_failed err=%s", exc)
        return {"status": "error", "detail": str(exc)}


# ============================================================================
# Phase 2.2.3 — 7-Day Rolling Performance Window & Auto-Nudge
# ============================================================================

@dataclass
class PerformanceWindow:
    """Track local LLM success/failure per query-type bucket over a rolling 7-day window."""

    TARGET_SUCCESS_RATE: float = 0.80
    NUDGE_AMOUNT: float = 0.05
    THRESHOLD_MIN: float = 0.30
    THRESHOLD_MAX: float = 0.95
    WINDOW_DAYS: int = 7
    MIN_SAMPLES: int = 10

    _path: Path = field(
        default_factory=lambda: Path.home() / ".local/share/nixos-ai-stack/performance-window.json",
        repr=False,
    )
    _data: dict = field(default_factory=dict, repr=False)
    _loaded: bool = field(default=False, repr=False)

    def _load(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}
        self._loaded = True

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _today(self) -> str:
        from datetime import date
        return date.today().isoformat()

    def record(self, bucket: str, success: bool) -> None:
        self._load()
        today = self._today()
        buckets = self._data.setdefault("buckets", {})
        day_data = buckets.setdefault(bucket, {}).setdefault(today, {"success": 0, "total": 0})
        day_data["total"] += 1
        if success:
            day_data["success"] += 1
        self._save()

    def _window_stats(self) -> Dict[str, Dict[str, int]]:
        from datetime import date, timedelta
        self._load()
        cutoff = (date.today() - timedelta(days=self.WINDOW_DAYS)).isoformat()
        agg: Dict[str, Dict[str, int]] = {}
        for bucket, days in self._data.get("buckets", {}).items():
            for day, counts in days.items():
                if day >= cutoff:
                    agg.setdefault(bucket, {"success": 0, "total": 0})
                    agg[bucket]["success"] += counts.get("success", 0)
                    agg[bucket]["total"] += counts.get("total", 0)
        return agg

    def maybe_nudge(self, cfg: "RoutingConfig") -> None:
        stats = self._window_stats()
        total = sum(v["total"] for v in stats.values())
        if total < self.MIN_SAMPLES:
            logger.info(
                "performance_window_nudge_skipped total_samples=%d min_required=%d",
                total, self.MIN_SAMPLES,
            )
            return

        success = sum(v["success"] for v in stats.values())
        rate = success / total if total else 0.0
        current = cfg.threshold
        if rate >= self.TARGET_SUCCESS_RATE:
            new_threshold = max(self.THRESHOLD_MIN, current - self.NUDGE_AMOUNT)
            direction = "down"
        else:
            new_threshold = min(self.THRESHOLD_MAX, current + self.NUDGE_AMOUNT)
            direction = "up"

        if new_threshold != current:
            cfg.write_threshold(new_threshold)
            logger.info(
                "performance_window_nudge direction=%s old=%.3f new=%.3f "
                "success_rate=%.3f samples=%d",
                direction, current, new_threshold, rate, total,
            )
        else:
            logger.info(
                "performance_window_nudge at_limit threshold=%.3f direction=%s success_rate=%.3f",
                current, direction, rate,
            )


performance_window: PerformanceWindow = PerformanceWindow()
