"""
Advanced Features Integration for Hybrid Coordinator

Unified integration module for Phases 6-10:
- Phase 6: Intelligent Remote Agent Offloading (6.2-6.3)
- Phase 7: Token & Context Efficiency (7.1-7.2)
- Phase 8: Advanced Progressive Disclosure (8.1-8.3)
- Phase 9: Automated Capability Gap Resolution (9.1-9.3)
- Phase 10: Real-Time Learning & Adaptation (10.1-10.3)

This module bridges standalone implementations in ai-stack/ subdirectories
with the live hybrid coordinator service.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from config import Config

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state — populated by init()
# ---------------------------------------------------------------------------
_qdrant: Optional[Any] = None
_embed: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_initialized: bool = False

# Runtime paths - use writable state directories
ADVANCED_FEATURES_STATE = Path(os.getenv(
    "ADVANCED_FEATURES_STATE",
    "/var/lib/ai-stack/hybrid/advanced-features"
))


def init(
    *,
    qdrant_client: Any,
    embed_fn: Callable,
    record_telemetry_fn: Optional[Callable] = None,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _qdrant, _embed, _record_telemetry, _initialized
    _qdrant = qdrant_client
    _embed = embed_fn
    _record_telemetry = record_telemetry_fn
    _initialized = True

    # Ensure runtime directories exist
    for subdir in ["offloading", "efficiency", "progressive-disclosure", "capability-gap", "learning"]:
        (ADVANCED_FEATURES_STATE / subdir).mkdir(parents=True, exist_ok=True)

    logger.info("advanced_features module initialized, state_dir=%s", ADVANCED_FEATURES_STATE)


# ===========================================================================
# Phase 6.2: Free Agent Pool Management
# ===========================================================================

class AgentTier(Enum):
    """Agent pricing tiers"""
    FREE = "free"
    PAID_CHEAP = "paid_cheap"
    PAID_STANDARD = "paid_standard"
    PAID_PREMIUM = "paid_premium"


class AgentStatus(Enum):
    """Agent availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


@dataclass
class AgentProfile:
    """Remote agent profile with metrics"""
    agent_id: str
    name: str
    provider: str
    model_id: str
    tier: AgentTier
    status: AgentStatus = AgentStatus.AVAILABLE
    total_requests: int = 0
    successful_requests: int = 0
    avg_latency_ms: float = 0.0
    avg_quality_score: float = 0.0
    last_used: Optional[datetime] = None


@dataclass
class PromptVariant:
    """A prompt-template variant with outcome tracking."""
    variant_id: str
    template: str
    uses: int = 0
    cumulative_score: float = 0.0


class AgentPoolManager:
    """Manages pool of remote agents with availability and quality tracking."""

    def __init__(self):
        self.agents: Dict[str, AgentProfile] = {}
        self.metrics_file = ADVANCED_FEATURES_STATE / "offloading" / "agent_pool.json"
        self._load()

        # Register some default free agents from OpenRouter
        self._register_default_agents()

    def _register_default_agents(self):
        """Register default free agents from OpenRouter."""
        default_agents = [
            ("mistral-7b-free", "Mistral 7B Free", "openrouter", "mistralai/mistral-7b-instruct:free"),
            ("llama3-8b-free", "Llama 3 8B Free", "openrouter", "meta-llama/llama-3-8b-instruct:free"),
            ("gemma-7b-free", "Gemma 7B Free", "openrouter", "google/gemma-7b-it:free"),
            ("mistral-small-paid", "Mistral Small", "openrouter", "mistralai/mistral-small-3.2"),
            ("deepseek-chat-paid", "DeepSeek Chat", "openrouter", "deepseek/deepseek-chat"),
        ]
        for agent_id, name, provider, model_id in default_agents:
            if agent_id not in self.agents:
                tier = AgentTier.FREE if agent_id.endswith("-free") else AgentTier.PAID_CHEAP
                self.agents[agent_id] = AgentProfile(
                    agent_id=agent_id,
                    name=name,
                    provider=provider,
                    model_id=model_id,
                    tier=tier,
                )

    def _load(self):
        """Load agent pool state from disk."""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    data = json.load(f)
                    for agent_id, agent_data in data.items():
                        self.agents[agent_id] = AgentProfile(
                            agent_id=agent_id,
                            name=agent_data.get("name", agent_id),
                            provider=agent_data.get("provider", "unknown"),
                            model_id=agent_data.get("model_id", ""),
                            tier=AgentTier(agent_data.get("tier", "free")),
                            status=AgentStatus(agent_data.get("status", "available")),
                            total_requests=agent_data.get("total_requests", 0),
                            successful_requests=agent_data.get("successful_requests", 0),
                            avg_latency_ms=agent_data.get("avg_latency_ms", 0.0),
                            avg_quality_score=agent_data.get("avg_quality_score", 0.0),
                        )
            except Exception as e:
                logger.warning("Failed to load agent pool: %s", e)

    def _save(self):
        """Persist agent pool state to disk."""
        try:
            data = {}
            for agent_id, agent in self.agents.items():
                data[agent_id] = {
                    "name": agent.name,
                    "provider": agent.provider,
                    "model_id": agent.model_id,
                    "tier": agent.tier.value,
                    "status": agent.status.value,
                    "total_requests": agent.total_requests,
                    "successful_requests": agent.successful_requests,
                    "avg_latency_ms": agent.avg_latency_ms,
                    "avg_quality_score": agent.avg_quality_score,
                }
            with open(self.metrics_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save agent pool: %s", e)

    def get_available_agents(self, tier: Optional[AgentTier] = None) -> List[AgentProfile]:
        """Get available agents, optionally filtered by tier."""
        agents = [a for a in self.agents.values() if a.status == AgentStatus.AVAILABLE]
        if tier:
            agents = [a for a in agents if a.tier == tier]
        return sorted(agents, key=lambda a: a.avg_quality_score, reverse=True)

    def select_best_agent(self, prefer_free: bool = True) -> Optional[AgentProfile]:
        """Select best available agent based on quality and cost."""
        if prefer_free:
            free_agents = self.get_available_agents(AgentTier.FREE)
            if free_agents:
                return free_agents[0]

        all_agents = self.get_available_agents()
        return all_agents[0] if all_agents else None

    def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Score agents by quality, reliability, and latency."""
        profiles: List[Dict[str, Any]] = []
        for agent in self.agents.values():
            success_rate = (
                agent.successful_requests / agent.total_requests
                if agent.total_requests > 0
                else 0.5
            )
            latency_score = 1.0 / (1.0 + max(agent.avg_latency_ms, 0.0) / 2000.0)
            recency_penalty = 0.0
            if agent.last_used is not None:
                idle_hours = max((datetime.now() - agent.last_used).total_seconds() / 3600.0, 0.0)
                recency_penalty = min(idle_hours / 72.0, 0.2)
            composite_score = max(
                0.0,
                min(
                    1.0,
                    success_rate * 0.45
                    + agent.avg_quality_score * 0.4
                    + latency_score * 0.15
                    - recency_penalty,
                ),
            )
            profiles.append(
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "tier": agent.tier.value,
                    "status": agent.status.value,
                    "success_rate": round(success_rate, 4),
                    "latency_score": round(latency_score, 4),
                    "avg_latency_ms": round(agent.avg_latency_ms, 2),
                    "avg_quality_score": round(agent.avg_quality_score, 4),
                    "composite_score": round(composite_score, 4),
                }
            )
        return sorted(profiles, key=lambda item: item["composite_score"], reverse=True)

    def select_failover_agent(
        self,
        min_composite_score: float = 0.55,
    ) -> Optional[AgentProfile]:
        """Choose a paid fallback when free capacity is weak or unhealthy."""
        profiles = self.get_quality_profiles()
        profile_by_id = {profile["agent_id"]: profile for profile in profiles}

        free_agents = [
            agent
            for agent in self.get_available_agents(AgentTier.FREE)
            if profile_by_id.get(agent.agent_id, {}).get("composite_score", 0.0) >= min_composite_score
        ]
        if free_agents:
            return free_agents[0]

        paid_order = [
            AgentTier.PAID_CHEAP,
            AgentTier.PAID_STANDARD,
            AgentTier.PAID_PREMIUM,
        ]
        for tier in paid_order:
            candidates = [
                agent
                for agent in self.get_available_agents(tier)
                if profile_by_id.get(agent.agent_id, {}).get("composite_score", 0.0) >= min_composite_score * 0.85
            ]
            if candidates:
                return candidates[0]

        return self.select_best_agent(prefer_free=False)

    def get_performance_benchmarks(self) -> Dict[str, Any]:
        """Summarize agent pool benchmarking from observed traffic."""
        profiles = self.get_quality_profiles()
        tier_summary: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"agents": 0, "avg_composite_score": 0.0, "avg_latency_ms": 0.0}
        )
        for profile in profiles:
            summary = tier_summary[profile["tier"]]
            summary["agents"] += 1
            summary["avg_composite_score"] += profile["composite_score"]
            summary["avg_latency_ms"] += profile["avg_latency_ms"]

        for summary in tier_summary.values():
            if summary["agents"] > 0:
                summary["avg_composite_score"] = round(summary["avg_composite_score"] / summary["agents"], 4)
                summary["avg_latency_ms"] = round(summary["avg_latency_ms"] / summary["agents"], 2)

        return {
            "profiles": profiles,
            "tier_summary": dict(tier_summary),
            "best_agent": profiles[0] if profiles else None,
            "benchmark_basis": "observed_runtime_requests",
        }

    def record_request(
        self,
        agent_id: str,
        success: bool,
        latency_ms: float,
        quality_score: float,
    ):
        """Record request metrics for an agent."""
        if agent_id not in self.agents:
            return

        agent = self.agents[agent_id]
        agent.total_requests += 1
        if success:
            agent.successful_requests += 1

        # Rolling average
        n = agent.total_requests
        agent.avg_latency_ms = ((n - 1) * agent.avg_latency_ms + latency_ms) / n
        agent.avg_quality_score = ((n - 1) * agent.avg_quality_score + quality_score) / n
        agent.last_used = datetime.now()

        self._save()

    def get_pool_stats(self) -> Dict:
        """Get agent pool statistics."""
        total = len(self.agents)
        available = len([a for a in self.agents.values() if a.status == AgentStatus.AVAILABLE])
        free_count = len([a for a in self.agents.values() if a.tier == AgentTier.FREE])

        return {
            "total_agents": total,
            "available_agents": available,
            "free_agents": free_count,
            "agents": [
                {
                    "id": a.agent_id,
                    "name": a.name,
                    "tier": a.tier.value,
                    "status": a.status.value,
                    "success_rate": a.successful_requests / a.total_requests if a.total_requests > 0 else 0,
                    "avg_latency_ms": a.avg_latency_ms,
                    "avg_quality": a.avg_quality_score,
                }
                for a in self.agents.values()
            ],
        }


# Singleton instance
_agent_pool: Optional[AgentPoolManager] = None


def get_agent_pool() -> AgentPoolManager:
    """Get or create agent pool manager."""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = AgentPoolManager()
    return _agent_pool


# ===========================================================================
# Phase 6.3: Result Quality Assurance
# ===========================================================================

class QualityLevel(Enum):
    """Quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"


@dataclass
class QualityAssessment:
    """Quality assessment result"""
    quality_level: QualityLevel
    score: float
    issues: List[str]
    suggestions: List[str]
    needs_refinement: bool


class ResultQualityChecker:
    """Checks and scores the quality of agent responses."""

    def __init__(self):
        self.quality_history: List[Dict] = []
        self.history_file = ADVANCED_FEATURES_STATE / "offloading" / "quality_history.json"
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    self.quality_history = json.load(f)[-1000:]  # Keep last 1000
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.quality_history[-1000:], f)
        except Exception as e:
            logger.error("Failed to save quality history: %s", e)

    def assess_response(
        self,
        query: str,
        response: str,
        agent_id: Optional[str] = None,
    ) -> QualityAssessment:
        """Assess the quality of a response."""
        issues = []
        suggestions = []
        score = 0.5  # Base score

        # Length checks
        response_words = len(response.split())
        query_words = len(query.split())

        if response_words < 5:
            issues.append("Response too short")
            score -= 0.2
        elif response_words > 10 * query_words and query_words > 5:
            issues.append("Response may be overly verbose")
            score -= 0.1
        else:
            score += 0.1

        # Content relevance (simple keyword overlap)
        query_terms = set(query.lower().split())
        response_terms = set(response.lower().split())
        overlap = len(query_terms & response_terms) / max(len(query_terms), 1)

        if overlap > 0.3:
            score += 0.2
        elif overlap < 0.1:
            issues.append("Response may not address the query")
            suggestions.append("Consider rephrasing the query for better results")
            score -= 0.15

        # Code detection and validation
        has_code = "```" in response or "def " in response or "function " in response
        if has_code:
            score += 0.1
            # Basic code block check
            code_blocks = response.count("```")
            if code_blocks % 2 != 0:
                issues.append("Unclosed code block detected")
                score -= 0.1

        # Error pattern detection
        error_patterns = ["I don't know", "I cannot", "I'm unable", "error occurred"]
        for pattern in error_patterns:
            if pattern.lower() in response.lower():
                issues.append(f"Potential failure indicator: '{pattern}'")
                score -= 0.15
                break

        # Determine quality level
        score = max(0.0, min(1.0, score))
        if score >= 0.8:
            level = QualityLevel.EXCELLENT
        elif score >= 0.6:
            level = QualityLevel.GOOD
        elif score >= 0.4:
            level = QualityLevel.ACCEPTABLE
        elif score >= 0.2:
            level = QualityLevel.POOR
        else:
            level = QualityLevel.FAILED

        assessment = QualityAssessment(
            quality_level=level,
            score=score,
            issues=issues,
            suggestions=suggestions,
            needs_refinement=level in [QualityLevel.POOR, QualityLevel.FAILED],
        )

        # Record for tracking
        self.quality_history.append({
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "query_length": query_words,
            "response_length": response_words,
            "quality_level": level.value,
            "score": score,
            "issues_count": len(issues),
        })
        self._save()

        return assessment

    def get_quality_stats(self) -> Dict:
        """Get quality assessment statistics."""
        if not self.quality_history:
            return {"status": "no_data"}

        recent = self.quality_history[-100:]
        avg_score = sum(h["score"] for h in recent) / len(recent)

        level_counts = defaultdict(int)
        for h in recent:
            level_counts[h["quality_level"]] += 1

        return {
            "total_assessments": len(self.quality_history),
            "recent_avg_score": avg_score,
            "level_distribution": dict(level_counts),
            "recent_issues_rate": sum(1 for h in recent if h["issues_count"] > 0) / len(recent),
        }


class LocalFallbackAdvisor:
    """Recommend local-model fallback after degraded remote responses."""

    def __init__(self):
        self.state_file = ADVANCED_FEATURES_STATE / "offloading" / "local_fallback.json"
        self.failure_history: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, encoding="utf-8") as f:
                self.failure_history = json.load(f).get("failure_history", [])[-500:]
        except Exception as exc:
            logger.warning("Failed to load local fallback state: %s", exc)

    def _save(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump({"failure_history": self.failure_history[-500:]}, f, indent=2)

    def record_remote_failure(
        self,
        query: str,
        response: str,
        agent_id: Optional[str],
        reason: str,
        quality_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        record = {
            "timestamp": datetime.now().isoformat(),
            "query": query[:500],
            "response_excerpt": response[:500],
            "agent_id": agent_id,
            "reason": reason,
            "quality_score": quality_score,
        }
        self.failure_history.append(record)
        self._save()
        return record

    def recommend(self, query: str, failed_agent_id: Optional[str] = None) -> Dict[str, Any]:
        query_terms = set(query.lower().split())
        matching: List[Dict[str, Any]] = []
        for record in self.failure_history:
            record_terms = set(str(record.get("query", "")).lower().split())
            similarity = (
                len(query_terms & record_terms) / len(query_terms | record_terms)
                if query_terms or record_terms
                else 0.0
            )
            if similarity >= 0.3 or (
                failed_agent_id is not None and record.get("agent_id") == failed_agent_id
            ):
                enriched = dict(record)
                enriched["similarity"] = round(similarity, 4)
                matching.append(enriched)

        reasons = [str(item.get("reason", "")).lower() for item in matching]
        fallback = len(matching) >= 2 or any(
            key in reason for reason in reasons for key in ("timeout", "rate", "unavailable", "quota")
        )
        return {
            "fallback_to_local": fallback,
            "recommended_profile": "local-first" if fallback else "remote-retry",
            "matching_failures": len(matching),
            "reason": (
                "remote failure history favors bounded local fallback"
                if fallback
                else "insufficient correlated failures for local fallback"
            ),
        }


_quality_checker: Optional[ResultQualityChecker] = None
_fallback_advisor: Optional[LocalFallbackAdvisor] = None


def get_quality_checker() -> ResultQualityChecker:
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = ResultQualityChecker()
    return _quality_checker


def get_fallback_advisor() -> LocalFallbackAdvisor:
    global _fallback_advisor
    if _fallback_advisor is None:
        _fallback_advisor = LocalFallbackAdvisor()
    return _fallback_advisor


# ===========================================================================
# Phase 7.1: Prompt Compression
# ===========================================================================

class CompressionStrategy(Enum):
    """Prompt compression strategies"""
    STOPWORD_REMOVAL = "stopword_removal"
    ABBREVIATION = "abbreviation"
    SEMANTIC_DEDUP = "semantic_dedup"


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "that", "which", "who", "whom", "this", "these", "those", "am",
    "just", "very", "really", "quite", "rather", "somewhat", "please",
}

ABBREVIATIONS = {
    "configuration": "config",
    "implementation": "impl",
    "documentation": "docs",
    "application": "app",
    "function": "func",
    "repository": "repo",
    "directory": "dir",
    "environment": "env",
    "development": "dev",
    "production": "prod",
}


class PromptCompressor:
    """Compresses prompts to reduce token usage."""

    def __init__(self):
        self.compression_stats = {"total": 0, "tokens_saved": 0}
        self.stats_file = ADVANCED_FEATURES_STATE / "efficiency" / "compression_stats.json"
        self._load()

    def _load(self):
        if self.stats_file.exists():
            try:
                with open(self.stats_file) as f:
                    self.compression_stats = json.load(f)
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.compression_stats, f)
        except Exception as e:
            logger.error("Failed to save compression stats: %s", e)

    def compress(
        self,
        text: str,
        strategy: CompressionStrategy = CompressionStrategy.STOPWORD_REMOVAL,
        preserve_code: bool = True,
    ) -> Tuple[str, Dict]:
        """Compress text using specified strategy."""
        original_tokens = len(text.split())

        # Preserve code blocks
        code_blocks = []
        if preserve_code:
            code_pattern = r'```[\s\S]*?```'
            matches = list(re.finditer(code_pattern, text))
            for i, match in enumerate(matches):
                placeholder = f"__CODE_BLOCK_{i}__"
                code_blocks.append((placeholder, match.group()))
                text = text[:match.start()] + placeholder + text[match.end():]

        # Apply compression strategy
        if strategy == CompressionStrategy.STOPWORD_REMOVAL:
            words = text.split()
            compressed_words = [w for w in words if w.lower() not in STOPWORDS or w.startswith("__")]
            text = " ".join(compressed_words)

        elif strategy == CompressionStrategy.ABBREVIATION:
            for full, abbrev in ABBREVIATIONS.items():
                text = re.sub(rf'\b{full}\b', abbrev, text, flags=re.IGNORECASE)

        elif strategy == CompressionStrategy.SEMANTIC_DEDUP:
            # Remove repeated phrases
            sentences = text.split(". ")
            seen = set()
            unique = []
            for s in sentences:
                key = s.lower().strip()[:50]
                if key not in seen:
                    seen.add(key)
                    unique.append(s)
            text = ". ".join(unique)

        # Restore code blocks
        for placeholder, code in code_blocks:
            text = text.replace(placeholder, code)

        compressed_tokens = len(text.split())
        tokens_saved = original_tokens - compressed_tokens

        # Update stats
        self.compression_stats["total"] += 1
        self.compression_stats["tokens_saved"] += tokens_saved
        self._save()

        return text, {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": tokens_saved,
            "compression_ratio": compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            "strategy": strategy.value,
        }

    def get_stats(self) -> Dict:
        return {
            **self.compression_stats,
            "avg_tokens_saved": self.compression_stats["tokens_saved"] / max(self.compression_stats["total"], 1),
        }

    def semantic_compress_long_context(
        self,
        text: str,
        max_sentences: int = 8,
    ) -> Tuple[str, Dict[str, Any]]:
        """Compress long context by keeping high-signal unique sentences and all code blocks."""
        original_tokens = len(text.split())
        code_blocks = re.findall(r"```[\s\S]*?```", text)
        text_wo_code = re.sub(r"```[\s\S]*?```", " ", text)
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text_wo_code) if segment.strip()]

        token_frequency: Dict[str, int] = defaultdict(int)
        for sentence in sentences:
            for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]+\b", sentence.lower()):
                if token not in STOPWORDS:
                    token_frequency[token] += 1

        scored: List[Tuple[float, str]] = []
        seen_signatures: Set[str] = set()
        for sentence in sentences:
            signature = " ".join(sentence.lower().split()[:10])
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            score = 0.0
            words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]+\b", sentence.lower())
            for word in words:
                score += token_frequency.get(word, 0)
            if "error" in sentence.lower() or "must" in sentence.lower():
                score += 3.0
            if len(sentence.split()) > 18:
                score += 1.5
            scored.append((score, sentence))

        kept_sentences = [sentence for _, sentence in sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]]
        compressed = "\n".join(kept_sentences + code_blocks).strip()
        compressed_tokens = len(compressed.split())
        tokens_saved = max(original_tokens - compressed_tokens, 0)

        self.compression_stats["total"] += 1
        self.compression_stats["tokens_saved"] += tokens_saved
        self._save()

        return compressed, {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": tokens_saved,
            "compression_ratio": compressed_tokens / original_tokens if original_tokens else 1.0,
            "strategy": "semantic_long_context",
            "kept_sentences": len(kept_sentences),
            "preserved_code_blocks": len(code_blocks),
        }


class PromptTemplateOptimizer:
    """Optimize prompt templates and track A/B outcomes."""

    def __init__(self):
        self.templates_file = ADVANCED_FEATURES_STATE / "efficiency" / "prompt_templates.json"
        self.variants: Dict[str, List[PromptVariant]] = {}
        self._load()

    def _default_variants(self) -> Dict[str, List[PromptVariant]]:
        return {
            "implementation": [
                PromptVariant("impl_direct", "Implement {task}. Constraints: {constraints}."),
                PromptVariant("impl_reasoned", "Implement {task}. Explain tradeoffs briefly. Constraints: {constraints}."),
            ],
            "debugging": [
                PromptVariant("debug_trace", "Debug this issue: {task}. Include root cause and fix."),
                PromptVariant("debug_patch", "Find the minimal fix for {task}. Mention risk areas."),
            ],
            "review": [
                PromptVariant("review_risks", "Review {task}. Prioritize bugs, regressions, and missing tests."),
                PromptVariant("review_security", "Review {task}. Focus on correctness, safety, and maintainability."),
            ],
        }

    def _load(self) -> None:
        self.variants = self._default_variants()
        if not self.templates_file.exists():
            return
        try:
            with open(self.templates_file, encoding="utf-8") as f:
                data = json.load(f)
            loaded: Dict[str, List[PromptVariant]] = {}
            for task_type, variants in data.items():
                loaded[task_type] = [
                    PromptVariant(
                        variant_id=item["variant_id"],
                        template=item["template"],
                        uses=item.get("uses", 0),
                        cumulative_score=item.get("cumulative_score", 0.0),
                    )
                    for item in variants
                ]
            self.variants.update(loaded)
        except Exception as exc:
            logger.warning("Failed to load prompt templates: %s", exc)

    def _save(self) -> None:
        try:
            payload = {
                task_type: [
                    {
                        "variant_id": variant.variant_id,
                        "template": variant.template,
                        "uses": variant.uses,
                        "cumulative_score": variant.cumulative_score,
                    }
                    for variant in variants
                ]
                for task_type, variants in self.variants.items()
            }
            with open(self.templates_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.error("Failed to save prompt templates: %s", exc)

    def choose_variant(self, task_type: str) -> PromptVariant:
        variants = self.variants.get(task_type) or self.variants["implementation"]
        return max(
            variants,
            key=lambda variant: (
                (variant.cumulative_score / variant.uses) if variant.uses else 0.6,
                -variant.uses,
            ),
        )

    def optimize_template(
        self,
        task_type: str,
        task: str,
        context: Optional[str] = None,
        constraints: Optional[str] = None,
    ) -> Dict[str, Any]:
        variant = self.choose_variant(task_type)
        prompt = variant.template.format(
            task=task,
            context=context or "repo-local context",
            constraints=constraints or "preserve existing behavior",
        )
        if context:
            prompt = f"{prompt}\nContext: {context}"
        return {
            "task_type": task_type,
            "variant_id": variant.variant_id,
            "prompt": prompt,
        }

    def generate_dynamic_prompt(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        query_lower = query.lower()
        if any(word in query_lower for word in ("debug", "fix", "trace", "failure")):
            task_type = "debugging"
        elif any(word in query_lower for word in ("review", "risk", "regression")):
            task_type = "review"
        else:
            task_type = "implementation"
        return self.optimize_template(task_type=task_type, task=query, context=context)

    def record_variant_outcome(
        self,
        task_type: str,
        variant_id: str,
        score: float,
    ) -> Dict[str, Any]:
        variants = self.variants.get(task_type) or self.variants["implementation"]
        for variant in variants:
            if variant.variant_id == variant_id:
                variant.uses += 1
                variant.cumulative_score += max(0.0, min(1.0, score))
                self._save()
                avg_score = variant.cumulative_score / max(variant.uses, 1)
                return {
                    "variant_id": variant.variant_id,
                    "uses": variant.uses,
                    "avg_score": round(avg_score, 4),
                }
        raise ValueError(f"Unknown variant_id={variant_id} for task_type={task_type}")

    def get_ab_stats(self) -> Dict[str, Any]:
        return {
            task_type: [
                {
                    "variant_id": variant.variant_id,
                    "uses": variant.uses,
                    "avg_score": round(variant.cumulative_score / variant.uses, 4) if variant.uses else None,
                }
                for variant in variants
            ]
            for task_type, variants in self.variants.items()
        }


_compressor: Optional[PromptCompressor] = None
_template_optimizer: Optional[PromptTemplateOptimizer] = None


def get_compressor() -> PromptCompressor:
    global _compressor
    if _compressor is None:
        _compressor = PromptCompressor()
    return _compressor


def get_template_optimizer() -> PromptTemplateOptimizer:
    global _template_optimizer
    if _template_optimizer is None:
        _template_optimizer = PromptTemplateOptimizer()
    return _template_optimizer


# ===========================================================================
# Phase 7.2: Context Window Management
# ===========================================================================

class ContextPruner:
    """Manages context window by intelligently pruning content."""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.pruning_history: List[Dict] = []

    def prune_context(
        self,
        context_items: List[Dict[str, Any]],
        target_tokens: Optional[int] = None,
    ) -> Tuple[List[Dict], Dict]:
        """Prune context to fit within token budget."""
        target = target_tokens or self.max_tokens
        current_tokens = sum(len(item.get("content", "").split()) for item in context_items)

        if current_tokens <= target:
            return context_items, {"pruned": False, "original_tokens": current_tokens}

        # Sort by relevance/priority
        sorted_items = sorted(
            context_items,
            key=lambda x: x.get("relevance_score", 0.5),
            reverse=True
        )

        pruned_items = []
        total_tokens = 0

        for item in sorted_items:
            item_tokens = len(item.get("content", "").split())
            if total_tokens + item_tokens <= target:
                pruned_items.append(item)
                total_tokens += item_tokens
            elif total_tokens < target * 0.9:
                # Truncate the last item if we have room
                remaining = target - total_tokens
                words = item.get("content", "").split()[:remaining]
                truncated = {**item, "content": " ".join(words), "truncated": True}
                pruned_items.append(truncated)
                total_tokens += remaining
                break

        self.pruning_history.append({
            "timestamp": datetime.now().isoformat(),
            "original_items": len(context_items),
            "pruned_items": len(pruned_items),
            "original_tokens": current_tokens,
            "final_tokens": total_tokens,
        })

        return pruned_items, {
            "pruned": True,
            "original_items": len(context_items),
            "kept_items": len(pruned_items),
            "original_tokens": current_tokens,
            "final_tokens": total_tokens,
            "tokens_saved": current_tokens - total_tokens,
        }


class HierarchicalSummarizer:
    """Summarize long contexts while preserving high-signal sentences."""

    def summarize(self, text: str, target_tokens: int) -> Dict[str, Any]:
        original_tokens = len(text.split())
        if original_tokens <= target_tokens:
            return {
                "summary": text,
                "original_tokens": original_tokens,
                "summary_tokens": original_tokens,
                "compression_ratio": 1.0,
                "levels": 0,
            }

        summary = text
        levels = 0
        while len(summary.split()) > target_tokens and levels < 3:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary) if s.strip()]
            if len(sentences) <= 3:
                break
            scored: List[Tuple[float, str]] = []
            for idx, sentence in enumerate(sentences):
                score = 1.0
                if idx in {0, len(sentences) - 1}:
                    score += 1.5
                if any(term in sentence.lower() for term in ("error", "critical", "must", "fix", "warning")):
                    score += 2.0
                score += min(len(sentence.split()) / 20.0, 1.0)
                scored.append((score, sentence))
            keep = {sentence for _, sentence in sorted(scored, key=lambda item: item[0], reverse=True)[: max(3, len(sentences) // 2)]}
            summary = " ".join(sentence for sentence in sentences if sentence in keep)
            levels += 1

        summary_tokens = len(summary.split())
        return {
            "summary": summary,
            "original_tokens": original_tokens,
            "summary_tokens": summary_tokens,
            "compression_ratio": round(summary_tokens / max(original_tokens, 1), 4),
            "levels": levels,
        }


class RelevanceScorer:
    """Score context items against a query."""

    def score(self, query: str, context: str) -> float:
        query_terms = {term for term in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", query.lower())}
        context_terms = {term for term in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", context.lower())}
        if not query_terms:
            return 0.5
        overlap = query_terms & context_terms
        if not overlap:
            return 0.0
        jaccard = len(overlap) / len(query_terms | context_terms)
        tf = sum(context.lower().count(term) for term in overlap) / (len(overlap) * 4)
        return round(min(1.0, jaccard * 0.7 + tf * 0.3), 4)


class SlidingWindowManager:
    """Break long documents into overlapping windows."""

    def __init__(self, window_size: int = 200):
        self.window_size = window_size

    def create_windows(self, document: str, overlap: int = 40) -> List[Dict[str, Any]]:
        words = document.split()
        windows: List[Dict[str, Any]] = []
        start = 0
        index = 0
        step = max(self.window_size - overlap, 1)
        while start < len(words):
            slice_words = words[start:start + self.window_size]
            windows.append(
                {
                    "window_id": f"window_{index}",
                    "content": " ".join(slice_words),
                    "tokens": len(slice_words),
                    "start_word": start,
                    "end_word": start + len(slice_words),
                }
            )
            if start + self.window_size >= len(words):
                break
            start += step
            index += 1
        return windows


class ContextReuseCache:
    """Reuse context across similar queries."""

    def __init__(self):
        self.state_file = ADVANCED_FEATURES_STATE / "efficiency" / "context_reuse.json"
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, encoding="utf-8") as f:
                self.cache = json.load(f)
        except Exception as exc:
            logger.warning("Failed to load context reuse state: %s", exc)

    def _save(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    def cache_context(self, query: str, context: str) -> Dict[str, Any]:
        key = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        self.cache[key] = {
            "query": query,
            "context": context,
            "stored_at": datetime.now().isoformat(),
        }
        self._save()
        return {"cache_key": key, "stored": True}

    def get_context(self, query: str, similarity_threshold: float = 0.7) -> Dict[str, Any]:
        query_terms = set(query.lower().split())
        exact_key = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        if exact_key in self.cache:
            return {"hit": True, "mode": "exact", "context": self.cache[exact_key]["context"]}

        for payload in self.cache.values():
            cached_terms = set(str(payload.get("query", "")).lower().split())
            similarity = (
                len(query_terms & cached_terms) / len(query_terms | cached_terms)
                if query_terms or cached_terms
                else 0.0
            )
            if similarity >= similarity_threshold:
                return {
                    "hit": True,
                    "mode": "similar",
                    "similarity": round(similarity, 4),
                    "context": payload.get("context"),
                }

        return {"hit": False}


_pruner: Optional[ContextPruner] = None
_hierarchical_summarizer: Optional[HierarchicalSummarizer] = None
_relevance_scorer: Optional[RelevanceScorer] = None
_window_manager: Optional[SlidingWindowManager] = None
_context_reuse_cache: Optional[ContextReuseCache] = None


def get_context_pruner() -> ContextPruner:
    global _pruner
    if _pruner is None:
        _pruner = ContextPruner()
    return _pruner


def get_hierarchical_summarizer() -> HierarchicalSummarizer:
    global _hierarchical_summarizer
    if _hierarchical_summarizer is None:
        _hierarchical_summarizer = HierarchicalSummarizer()
    return _hierarchical_summarizer


def get_relevance_scorer() -> RelevanceScorer:
    global _relevance_scorer
    if _relevance_scorer is None:
        _relevance_scorer = RelevanceScorer()
    return _relevance_scorer


def get_window_manager() -> SlidingWindowManager:
    global _window_manager
    if _window_manager is None:
        _window_manager = SlidingWindowManager()
    return _window_manager


def get_context_reuse_cache() -> ContextReuseCache:
    global _context_reuse_cache
    if _context_reuse_cache is None:
        _context_reuse_cache = ContextReuseCache()
    return _context_reuse_cache


# ===========================================================================
# Phase 8: Progressive Disclosure
# ===========================================================================

class ContextTier(Enum):
    """Context loading tiers"""
    MINIMAL = 1
    BRIEF = 2
    STANDARD = 3
    DETAILED = 4
    EXHAUSTIVE = 5


@dataclass
class TierSelection:
    """Tier selection decision"""
    tier: ContextTier
    confidence: float
    reasoning: str


class TierSelector:
    """Selects appropriate context tier based on query complexity."""

    def __init__(self):
        self.selection_history: List[Dict] = []

    def select_tier(self, query: str, context: Optional[str] = None) -> TierSelection:
        """Select appropriate tier for a query."""
        query_words = len(query.split())
        query_lower = query.lower()

        # Simple complexity heuristics
        complexity_score = 0.5

        # Long queries suggest more complex needs
        if query_words > 50:
            complexity_score += 0.2
        elif query_words > 20:
            complexity_score += 0.1
        elif query_words < 5:
            complexity_score -= 0.2

        # Technical keywords suggest detailed needs
        technical_keywords = ["implement", "architecture", "design", "debug", "analyze", "explain"]
        if any(kw in query_lower for kw in technical_keywords):
            complexity_score += 0.15

        # Simple keywords suggest minimal needs
        simple_keywords = ["what is", "quick", "simple", "brief", "short"]
        if any(kw in query_lower for kw in simple_keywords):
            complexity_score -= 0.15

        # Map score to tier
        complexity_score = max(0.0, min(1.0, complexity_score))

        if complexity_score < 0.2:
            tier = ContextTier.MINIMAL
            reasoning = "Simple query, minimal context needed"
        elif complexity_score < 0.4:
            tier = ContextTier.BRIEF
            reasoning = "Straightforward query, brief context sufficient"
        elif complexity_score < 0.6:
            tier = ContextTier.STANDARD
            reasoning = "Moderate complexity, standard context appropriate"
        elif complexity_score < 0.8:
            tier = ContextTier.DETAILED
            reasoning = "Complex query requiring detailed context"
        else:
            tier = ContextTier.EXHAUSTIVE
            reasoning = "Highly complex query, exhaustive context recommended"

        self.selection_history.append({
            "timestamp": datetime.now().isoformat(),
            "query_length": query_words,
            "complexity_score": complexity_score,
            "selected_tier": tier.value,
        })

        return TierSelection(tier=tier, confidence=complexity_score, reasoning=reasoning)

    def get_tier_stats(self) -> Dict:
        if not self.selection_history:
            return {"status": "no_data"}

        tier_counts = defaultdict(int)
        for h in self.selection_history:
            tier_counts[h["selected_tier"]] += 1

        return {
            "total_selections": len(self.selection_history),
            "tier_distribution": dict(tier_counts),
            "avg_complexity": sum(h["complexity_score"] for h in self.selection_history) / len(self.selection_history),
        }


_tier_selector: Optional[TierSelector] = None


def get_tier_selector() -> TierSelector:
    global _tier_selector
    if _tier_selector is None:
        _tier_selector = TierSelector()
    return _tier_selector


# ===========================================================================
# Phase 9: Capability Gap Detection
# ===========================================================================

class GapType(Enum):
    """Types of capability gaps"""
    TOOL_MISSING = "tool_missing"
    KNOWLEDGE_GAP = "knowledge_gap"
    SKILL_GAP = "skill_gap"
    PATTERN_GAP = "pattern_gap"


@dataclass
class CapabilityGap:
    """Detected capability gap"""
    gap_id: str
    gap_type: GapType
    description: str
    severity: float  # 0-1
    detected_at: datetime
    query_context: str
    suggested_remediation: Optional[str] = None


class GapDetector:
    """Detects capability gaps from failed or poor quality interactions."""

    def __init__(self):
        self.detected_gaps: List[CapabilityGap] = []
        self.gaps_file = ADVANCED_FEATURES_STATE / "capability-gap" / "detected_gaps.json"
        self._load()

    def _load(self):
        if self.gaps_file.exists():
            try:
                with open(self.gaps_file) as f:
                    data = json.load(f)
                    self.detected_gaps = [
                        CapabilityGap(
                            gap_id=g["gap_id"],
                            gap_type=GapType(g["gap_type"]),
                            description=g["description"],
                            severity=g["severity"],
                            detected_at=datetime.fromisoformat(g["detected_at"]),
                            query_context=g["query_context"],
                            suggested_remediation=g.get("suggested_remediation"),
                        )
                        for g in data
                    ]
            except Exception as e:
                logger.warning("Failed to load gaps: %s", e)

    def _save(self):
        try:
            data = [
                {
                    "gap_id": g.gap_id,
                    "gap_type": g.gap_type.value,
                    "description": g.description,
                    "severity": g.severity,
                    "detected_at": g.detected_at.isoformat(),
                    "query_context": g.query_context,
                    "suggested_remediation": g.suggested_remediation,
                }
                for g in self.detected_gaps[-500:]  # Keep last 500
            ]
            with open(self.gaps_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save gaps: %s", e)

    def detect_gap(
        self,
        query: str,
        response: str,
        outcome: str,
        error_message: Optional[str] = None,
        user_feedback: Optional[Dict[str, Any]] = None,
    ) -> Optional[CapabilityGap]:
        """Detect capability gap from interaction."""
        if outcome == "success":
            return None

        query_lower = query.lower()
        response_lower = response.lower()
        pattern_analysis = self.analyze_failure_patterns(
            query=query,
            response=response,
            error_message=error_message,
            user_feedback=user_feedback,
        )

        # Detect gap type
        gap_type = GapType(pattern_analysis["gap_type"])
        description = pattern_analysis["description"]
        severity = pattern_analysis["priority_score"]

        # Tool-related patterns
        tool_patterns = ["run", "execute", "call", "invoke", "use tool"]
        if any(p in query_lower for p in tool_patterns):
            if "not available" in response_lower or "cannot" in response_lower:
                gap_type = GapType.TOOL_MISSING
                description = "Required tool not available"
                severity = 0.7

        # Knowledge patterns
        knowledge_patterns = ["don't know", "not sure", "cannot find", "no information"]
        if any(p in response_lower for p in knowledge_patterns):
            gap_type = GapType.KNOWLEDGE_GAP
            description = "Knowledge base lacks required information"
            severity = 0.6

        # Skill patterns
        skill_patterns = ["unable to", "cannot perform", "failed to"]
        if any(p in response_lower for p in skill_patterns):
            gap_type = GapType.SKILL_GAP
            description = "Required skill or capability missing"
            severity = 0.65

        if outcome == "failure":
            severity = min(severity + 0.2, 1.0)
        if user_feedback and user_feedback.get("negative"):
            severity = min(severity + 0.1, 1.0)

        gap = CapabilityGap(
            gap_id=str(uuid4()),
            gap_type=gap_type,
            description=description,
            severity=severity,
            detected_at=datetime.now(),
            query_context=query[:200],
            suggested_remediation=self._suggest_remediation(gap_type),
        )

        self.detected_gaps.append(gap)
        self._save()

        logger.info("Detected capability gap: type=%s, severity=%.2f", gap_type.value, severity)
        return gap

    def analyze_failure_patterns(
        self,
        query: str,
        response: str,
        error_message: Optional[str] = None,
        user_feedback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify failure signatures and derive a priority score."""
        combined = " ".join(filter(None, [query.lower(), response.lower(), (error_message or "").lower()]))
        pattern_hits: List[str] = []
        gap_type = GapType.KNOWLEDGE_GAP
        description = "Unable to provide satisfactory response"
        priority_score = 0.45

        patterns = {
            "tool_unavailable": ["tool not available", "command not found", "missing tool", "not available"],
            "knowledge_missing": ["don't know", "cannot find", "no information", "unknown"],
            "execution_failed": ["traceback", "exception", "failed to", "error occurred"],
            "pattern_missing": ["no pattern", "not supported", "missing workflow"],
        }
        for pattern_name, indicators in patterns.items():
            if any(indicator in combined for indicator in indicators):
                pattern_hits.append(pattern_name)

        if "tool_unavailable" in pattern_hits:
            gap_type = GapType.TOOL_MISSING
            description = "Required tool not available for requested operation"
            priority_score = 0.7
        elif "execution_failed" in pattern_hits:
            gap_type = GapType.SKILL_GAP
            description = "Execution failed for a supported request shape"
            priority_score = 0.68
        elif "pattern_missing" in pattern_hits:
            gap_type = GapType.PATTERN_GAP
            description = "Coordinator lacks a reusable execution pattern"
            priority_score = 0.63
        elif "knowledge_missing" in pattern_hits:
            gap_type = GapType.KNOWLEDGE_GAP
            description = "Knowledge base lacks required information"
            priority_score = 0.6

        if user_feedback:
            feedback_score = float(user_feedback.get("score", 0.0) or 0.0)
            if user_feedback.get("negative"):
                priority_score += 0.08
            if feedback_score < 0:
                priority_score += min(abs(feedback_score) * 0.1, 0.1)

        return {
            "pattern_hits": pattern_hits,
            "gap_type": gap_type.value,
            "description": description,
            "priority_score": round(min(priority_score, 1.0), 4),
        }

    def _suggest_remediation(self, gap_type: GapType) -> str:
        remediation_map = {
            GapType.TOOL_MISSING: "Consider adding the required tool to the MCP registry",
            GapType.KNOWLEDGE_GAP: "Expand knowledge base with relevant documentation",
            GapType.SKILL_GAP: "Implement the required capability or pattern",
            GapType.PATTERN_GAP: "Add the missing pattern to the agentic pattern library",
        }
        return remediation_map.get(gap_type, "Review and address the capability gap")

    def get_gap_stats(self) -> Dict:
        if not self.detected_gaps:
            return {"status": "no_gaps_detected"}

        type_counts = defaultdict(int)
        pattern_counts = defaultdict(int)
        for g in self.detected_gaps:
            type_counts[g.gap_type.value] += 1
            pattern_counts[g.description] += 1

        recent = [g for g in self.detected_gaps if g.detected_at > datetime.now() - timedelta(days=7)]

        return {
            "total_gaps": len(self.detected_gaps),
            "recent_gaps_7d": len(recent),
            "type_distribution": dict(type_counts),
            "avg_severity": sum(g.severity for g in self.detected_gaps) / len(self.detected_gaps),
            "failure_patterns": dict(sorted(pattern_counts.items(), key=lambda item: item[1], reverse=True)[:10]),
            "top_gaps": [
                {"type": g.gap_type.value, "description": g.description, "severity": g.severity}
                for g in sorted(self.detected_gaps, key=lambda x: x.severity, reverse=True)[:5]
            ],
        }


_gap_detector: Optional[GapDetector] = None


def get_gap_detector() -> GapDetector:
    global _gap_detector
    if _gap_detector is None:
        _gap_detector = GapDetector()
    return _gap_detector


class RemediationWorkspace:
    """Writable-state remediation artifact generator for Phase 9.2."""

    def __init__(self):
        self.base_dir = ADVANCED_FEATURES_STATE / "capability-gap"
        for subdir in ("knowledge", "skills", "patterns"):
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)
        self.results_file = self.base_dir / "remediation_results.json"

    def import_knowledge(self, topic: str, reason: str, source_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        filename = f"{topic.replace(' ', '_').lower()[:64]}.md"
        path = self.base_dir / "knowledge" / filename
        refs = "\n".join(f"- {url}" for url in (source_urls or [])) or "- No explicit sources recorded"
        path.write_text(
            (
                f"# Knowledge: {topic}\n\n"
                f"Imported: {datetime.now().isoformat()}\n"
                f"Reason: {reason}\n\n"
                "## Summary\n\n"
                f"Imported knowledge artifact for {topic}.\n\n"
                "## References\n\n"
                f"{refs}\n"
            ),
            encoding="utf-8",
        )
        return self._record_result("import_knowledge", path)

    def synthesize_skill(self, skill_name: str, examples: List[Dict[str, Any]], reason: str) -> Dict[str, Any]:
        filename = f"{skill_name.replace(' ', '_').lower()[:64]}.md"
        path = self.base_dir / "skills" / filename
        common_keys = sorted({key for example in examples for key in example.keys()})
        path.write_text(
            (
                f"# Skill: {skill_name}\n\n"
                f"Synthesized: {datetime.now().isoformat()}\n"
                f"Reason: {reason}\n\n"
                "## Common Fields\n\n"
                f"{', '.join(common_keys) if common_keys else 'No example fields supplied'}\n\n"
                "## Examples\n\n"
                f"```json\n{json.dumps(examples[:3], indent=2)}\n```\n"
            ),
            encoding="utf-8",
        )
        return self._record_result("synthesize_skill", path)

    def extract_pattern(self, pattern_name: str, instances: List[Dict[str, Any]], reason: str) -> Dict[str, Any]:
        filename = f"{pattern_name.replace(' ', '_').lower()[:64]}.md"
        path = self.base_dir / "patterns" / filename
        repeated_keys = defaultdict(int)
        for instance in instances:
            for key in instance.keys():
                repeated_keys[key] += 1
        ranked = sorted(repeated_keys.items(), key=lambda item: item[1], reverse=True)
        path.write_text(
            (
                f"# Pattern: {pattern_name}\n\n"
                f"Extracted: {datetime.now().isoformat()}\n"
                f"Reason: {reason}\n\n"
                "## Frequent Fields\n\n"
                + "\n".join(f"- {key}: {count}" for key, count in ranked[:10])
                + "\n"
            ),
            encoding="utf-8",
        )
        return self._record_result("extract_pattern", path)

    def validate(self, artifact_path: str) -> Dict[str, Any]:
        path = Path(artifact_path)
        valid = path.exists() and path.stat().st_size > 0
        return {"validation_passed": valid, "artifact_path": str(path)}

    def _record_result(self, action: str, path: Path) -> Dict[str, Any]:
        if self.results_file.exists():
            try:
                payload = json.loads(self.results_file.read_text(encoding="utf-8"))
            except Exception:
                payload = {"results": []}
        else:
            payload = {"results": []}
        payload["results"].append(
            {
                "action": action,
                "artifact_path": str(path),
                "recorded_at": datetime.now().isoformat(),
            }
        )
        self.results_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"artifact_path": str(path), "action": action}


_remediation_workspace: Optional[RemediationWorkspace] = None


def get_remediation_workspace() -> RemediationWorkspace:
    global _remediation_workspace
    if _remediation_workspace is None:
        _remediation_workspace = RemediationWorkspace()
    return _remediation_workspace


# ===========================================================================
# Phase 10: Real-Time Learning
# ===========================================================================

class FeedbackType(Enum):
    """Types of learning feedback"""
    EXPLICIT = "explicit"  # User thumbs up/down
    IMPLICIT = "implicit"  # Inferred from behavior
    AUTOMATED = "automated"  # System-detected


@dataclass
class LearningSignal:
    """Learning signal from interaction"""
    signal_id: str
    feedback_type: FeedbackType
    query: str
    response: str
    outcome: str
    score: float  # -1 to 1
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)


class OnlineLearner:
    """Real-time learning from interactions."""

    def __init__(self):
        self.signals: List[LearningSignal] = []
        self.pattern_scores: Dict[str, float] = defaultdict(lambda: 0.5)
        self.learning_file = ADVANCED_FEATURES_STATE / "learning" / "online_signals.json"
        self._load()

    def _load(self):
        if self.learning_file.exists():
            try:
                with open(self.learning_file) as f:
                    data = json.load(f)
                    self.signals = [
                        LearningSignal(
                            signal_id=s["signal_id"],
                            feedback_type=FeedbackType(s["feedback_type"]),
                            query=s["query"],
                            response=s["response"],
                            outcome=s["outcome"],
                            score=s["score"],
                            timestamp=datetime.fromisoformat(s["timestamp"]),
                            metadata=s.get("metadata", {}),
                        )
                        for s in data.get("signals", [])[-1000:]
                    ]
                    self.pattern_scores = defaultdict(lambda: 0.5, data.get("pattern_scores", {}))
            except Exception as e:
                logger.warning("Failed to load learning data: %s", e)

    def _save(self):
        try:
            data = {
                "signals": [
                    {
                        "signal_id": s.signal_id,
                        "feedback_type": s.feedback_type.value,
                        "query": s.query[:500],
                        "response": s.response[:500],
                        "outcome": s.outcome,
                        "score": s.score,
                        "timestamp": s.timestamp.isoformat(),
                        "metadata": s.metadata,
                    }
                    for s in self.signals[-1000:]
                ],
                "pattern_scores": dict(self.pattern_scores),
            }
            with open(self.learning_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error("Failed to save learning data: %s", e)

    def record_signal(
        self,
        query: str,
        response: str,
        outcome: str,
        feedback_type: FeedbackType = FeedbackType.AUTOMATED,
        explicit_score: Optional[float] = None,
    ) -> LearningSignal:
        """Record a learning signal from an interaction."""
        # Calculate score
        if explicit_score is not None:
            score = explicit_score
        elif outcome == "success":
            score = 0.8
        elif outcome == "partial":
            score = 0.3
        else:
            score = -0.5

        signal = LearningSignal(
            signal_id=str(uuid4()),
            feedback_type=feedback_type,
            query=query,
            response=response,
            outcome=outcome,
            score=score,
            timestamp=datetime.now(),
        )

        self.signals.append(signal)

        # Update pattern scores based on query patterns
        query_patterns = self._extract_patterns(query)
        for pattern in query_patterns:
            old_score = self.pattern_scores[pattern]
            # Exponential moving average
            self.pattern_scores[pattern] = 0.9 * old_score + 0.1 * ((score + 1) / 2)

        self._save()
        return signal

    def _extract_patterns(self, query: str) -> List[str]:
        """Extract simple patterns from query."""
        patterns = []
        query_lower = query.lower()

        # Task type patterns
        if "how to" in query_lower:
            patterns.append("how_to_query")
        if "what is" in query_lower:
            patterns.append("definition_query")
        if "debug" in query_lower or "fix" in query_lower:
            patterns.append("debugging_query")
        if "implement" in query_lower or "create" in query_lower:
            patterns.append("implementation_query")

        return patterns or ["general_query"]

    def get_pattern_recommendations(self, query: str) -> Dict:
        """Get recommendations based on learned patterns."""
        patterns = self._extract_patterns(query)
        scores = {p: self.pattern_scores[p] for p in patterns}

        avg_score = sum(scores.values()) / len(scores) if scores else 0.5

        return {
            "patterns": patterns,
            "pattern_scores": scores,
            "confidence": avg_score,
            "recommendation": "high_quality_expected" if avg_score > 0.7 else "may_need_verification",
        }

    def get_learning_stats(self) -> Dict:
        if not self.signals:
            return {"status": "no_signals"}

        recent = [s for s in self.signals if s.timestamp > datetime.now() - timedelta(days=7)]
        avg_score = sum(s.score for s in recent) / len(recent) if recent else 0

        feedback_counts = defaultdict(int)
        for s in self.signals:
            feedback_counts[s.feedback_type.value] += 1

        return {
            "total_signals": len(self.signals),
            "recent_signals_7d": len(recent),
            "avg_recent_score": avg_score,
            "feedback_distribution": dict(feedback_counts),
            "top_patterns": sorted(
                [(k, v) for k, v in self.pattern_scores.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
        }


_online_learner: Optional[OnlineLearner] = None


def get_online_learner() -> OnlineLearner:
    global _online_learner
    if _online_learner is None:
        _online_learner = OnlineLearner()
    return _online_learner


# ===========================================================================
# API Functions for MCP Handlers
# ===========================================================================

async def get_agent_pool_stats() -> Dict:
    """Get agent pool statistics (Phase 6.2)."""
    pool = get_agent_pool()
    return pool.get_pool_stats()


async def get_agent_quality_profiles() -> Dict:
    """Get composite agent quality profiles (Phase 6.2)."""
    pool = get_agent_pool()
    return {"profiles": pool.get_quality_profiles()}


async def select_remote_agent(prefer_free: bool = True) -> Dict:
    """Select best available remote agent (Phase 6.2)."""
    pool = get_agent_pool()
    agent = pool.select_best_agent(prefer_free=prefer_free)

    if agent is None:
        return {"selected": False, "reason": "No agents available"}

    return {
        "selected": True,
        "agent_id": agent.agent_id,
        "name": agent.name,
        "tier": agent.tier.value,
        "model_id": agent.model_id,
    }


async def select_failover_remote_agent(min_composite_score: float = 0.55) -> Dict:
    """Select a failover-capable remote agent, escalating cost tiers when needed."""
    pool = get_agent_pool()
    agent = pool.select_failover_agent(min_composite_score=min_composite_score)
    if agent is None:
        return {"selected": False, "reason": "No failover agent available"}
    return {
        "selected": True,
        "agent_id": agent.agent_id,
        "name": agent.name,
        "tier": agent.tier.value,
        "model_id": agent.model_id,
        "mode": "failover",
    }


async def get_agent_benchmarks() -> Dict:
    """Get observed performance benchmarks for the current pool."""
    pool = get_agent_pool()
    return pool.get_performance_benchmarks()


async def assess_response_quality(query: str, response: str, agent_id: Optional[str] = None) -> Dict:
    """Assess response quality (Phase 6.3)."""
    checker = get_quality_checker()
    assessment = checker.assess_response(query, response, agent_id)

    return {
        "quality_level": assessment.quality_level.value,
        "score": assessment.score,
        "issues": assessment.issues,
        "suggestions": assessment.suggestions,
        "needs_refinement": assessment.needs_refinement,
    }


async def get_quality_stats() -> Dict:
    """Get quality assessment statistics (Phase 6.3)."""
    checker = get_quality_checker()
    return checker.get_quality_stats()


async def record_remote_failure(
    query: str,
    response: str,
    reason: str,
    agent_id: Optional[str] = None,
    quality_score: Optional[float] = None,
) -> Dict:
    """Record a failed/degraded remote response for local fallback decisions."""
    advisor = get_fallback_advisor()
    return advisor.record_remote_failure(query, response, agent_id, reason, quality_score)


async def recommend_local_fallback(query: str, failed_agent_id: Optional[str] = None) -> Dict:
    """Recommend whether a failed remote request should fall back locally."""
    advisor = get_fallback_advisor()
    return advisor.recommend(query=query, failed_agent_id=failed_agent_id)


async def compress_prompt(text: str, strategy: str = "stopword_removal") -> Dict:
    """Compress a prompt (Phase 7.1)."""
    compressor = get_compressor()
    strategy_enum = CompressionStrategy(strategy)
    compressed, metadata = compressor.compress(text, strategy=strategy_enum)

    return {
        "compressed_text": compressed,
        **metadata,
    }


async def semantic_compress_prompt(text: str, max_sentences: int = 8) -> Dict:
    """Semantically compress a long prompt or context block."""
    compressor = get_compressor()
    compressed, metadata = compressor.semantic_compress_long_context(text, max_sentences=max_sentences)
    return {
        "compressed_text": compressed,
        **metadata,
    }


async def get_compression_stats() -> Dict:
    """Get compression statistics (Phase 7.1)."""
    compressor = get_compressor()
    return compressor.get_stats()


async def summarize_long_context(text: str, target_tokens: int = 120) -> Dict:
    """Hierarchically summarize long context blocks."""
    summarizer = get_hierarchical_summarizer()
    return summarizer.summarize(text, target_tokens=target_tokens)


async def score_context_relevance(query: str, context: str) -> Dict:
    """Score how relevant a context block is to a query."""
    scorer = get_relevance_scorer()
    return {"score": scorer.score(query, context)}


async def create_sliding_windows(document: str, window_size: int = 200, overlap: int = 40) -> Dict:
    """Split a long document into overlapping windows."""
    manager = get_window_manager()
    manager.window_size = window_size
    windows = manager.create_windows(document, overlap=overlap)
    return {"windows": windows, "window_count": len(windows)}


async def cache_reusable_context(query: str, context: str) -> Dict:
    """Cache reusable context for later similar queries."""
    cache = get_context_reuse_cache()
    return cache.cache_context(query, context)


async def get_reusable_context(query: str, similarity_threshold: float = 0.7) -> Dict:
    """Retrieve reusable context for a similar query."""
    cache = get_context_reuse_cache()
    return cache.get_context(query, similarity_threshold=similarity_threshold)


async def optimize_prompt_template(
    task_type: str,
    task: str,
    context: Optional[str] = None,
    constraints: Optional[str] = None,
) -> Dict:
    """Create an optimized prompt template variant for a task."""
    optimizer = get_template_optimizer()
    return optimizer.optimize_template(task_type, task, context=context, constraints=constraints)


async def generate_dynamic_prompt(query: str, context: Optional[str] = None) -> Dict:
    """Generate a task-adaptive prompt variant from a raw query."""
    optimizer = get_template_optimizer()
    return optimizer.generate_dynamic_prompt(query, context=context)


async def record_prompt_variant_outcome(task_type: str, variant_id: str, score: float) -> Dict:
    """Record an A/B outcome for a prompt variant."""
    optimizer = get_template_optimizer()
    return optimizer.record_variant_outcome(task_type, variant_id, score)


async def get_prompt_ab_stats() -> Dict:
    """Get current prompt-template A/B statistics."""
    optimizer = get_template_optimizer()
    return {"variants": optimizer.get_ab_stats()}


async def prune_context(context_items: List[Dict], target_tokens: Optional[int] = None) -> Dict:
    """Prune context to fit token budget (Phase 7.2)."""
    pruner = get_context_pruner()
    pruned, metadata = pruner.prune_context(context_items, target_tokens)

    return {
        "pruned_context": pruned,
        **metadata,
    }


async def select_context_tier(query: str, context: Optional[str] = None) -> Dict:
    """Select appropriate context tier (Phase 8)."""
    selector = get_tier_selector()
    selection = selector.select_tier(query, context)

    return {
        "tier": selection.tier.value,
        "tier_level": selection.tier.value,
        "confidence": selection.confidence,
        "reasoning": selection.reasoning,
    }


async def get_tier_selection_stats() -> Dict:
    """Get tier selection statistics (Phase 8)."""
    selector = get_tier_selector()
    return selector.get_tier_stats()


async def detect_capability_gap(
    query: str,
    response: str,
    outcome: str,
    error_message: Optional[str] = None,
    user_feedback: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Detect capability gap from interaction (Phase 9)."""
    detector = get_gap_detector()
    gap = detector.detect_gap(query, response, outcome, error_message, user_feedback=user_feedback)

    if gap is None:
        return {"gap_detected": False}

    return {
        "gap_detected": True,
        "gap_id": gap.gap_id,
        "gap_type": gap.gap_type.value,
        "description": gap.description,
        "severity": gap.severity,
        "suggested_remediation": gap.suggested_remediation,
    }


async def analyze_failure_patterns(
    query: str,
    response: str,
    error_message: Optional[str] = None,
    user_feedback: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Analyze failure patterns without creating a persisted gap record."""
    detector = get_gap_detector()
    return detector.analyze_failure_patterns(
        query=query,
        response=response,
        error_message=error_message,
        user_feedback=user_feedback,
    )


async def get_capability_gap_stats() -> Dict:
    """Get capability gap statistics (Phase 9)."""
    detector = get_gap_detector()
    return detector.get_gap_stats()


async def import_gap_knowledge(topic: str, reason: str, source_urls: Optional[List[str]] = None) -> Dict:
    """Create a knowledge artifact for a capability gap."""
    workspace = get_remediation_workspace()
    artifact = workspace.import_knowledge(topic, reason, source_urls=source_urls)
    validation = workspace.validate(artifact["artifact_path"])
    return {**artifact, **validation}


async def synthesize_gap_skill(skill_name: str, examples: List[Dict[str, Any]], reason: str) -> Dict:
    """Create a skill artifact from remediation examples."""
    workspace = get_remediation_workspace()
    artifact = workspace.synthesize_skill(skill_name, examples, reason)
    validation = workspace.validate(artifact["artifact_path"])
    return {**artifact, **validation}


async def extract_gap_pattern(pattern_name: str, instances: List[Dict[str, Any]], reason: str) -> Dict:
    """Create a generalized pattern artifact from remediation instances."""
    workspace = get_remediation_workspace()
    artifact = workspace.extract_pattern(pattern_name, instances, reason)
    validation = workspace.validate(artifact["artifact_path"])
    return {**artifact, **validation}


async def record_learning_signal(
    query: str,
    response: str,
    outcome: str,
    explicit_score: Optional[float] = None,
) -> Dict:
    """Record learning signal (Phase 10)."""
    learner = get_online_learner()
    feedback_type = FeedbackType.EXPLICIT if explicit_score is not None else FeedbackType.AUTOMATED
    signal = learner.record_signal(query, response, outcome, feedback_type, explicit_score)

    return {
        "signal_id": signal.signal_id,
        "feedback_type": signal.feedback_type.value,
        "score": signal.score,
    }


async def get_learning_recommendations(query: str) -> Dict:
    """Get recommendations based on learned patterns (Phase 10)."""
    learner = get_online_learner()
    return learner.get_pattern_recommendations(query)


async def get_learning_stats() -> Dict:
    """Get learning statistics (Phase 10)."""
    learner = get_online_learner()
    return learner.get_learning_stats()


async def get_advanced_features_readiness() -> Dict:
    """Get readiness status for Phases 6-10."""
    pool_stats = get_agent_pool().get_pool_stats()
    benchmark_stats = get_agent_pool().get_performance_benchmarks()
    quality_stats = get_quality_checker().get_quality_stats()
    fallback_stats = get_fallback_advisor().recommend("local bounded retry", None)
    compression_stats = get_compressor().get_stats()
    prompt_ab_stats = get_template_optimizer().get_ab_stats()
    context_reuse = get_context_reuse_cache().get_context("cached context probe", similarity_threshold=0.1)
    tier_stats = get_tier_selector().get_tier_stats()
    gap_stats = get_gap_detector().get_gap_stats()
    remediation_results_path = get_remediation_workspace().results_file
    learning_stats = get_online_learner().get_learning_stats()

    return {
        "readiness": {
            "phase_6_offloading": {
                "status": "implementation_exists",
                "agent_pool": f"{pool_stats['available_agents']}/{pool_stats['total_agents']} available",
                "quality_assessments": quality_stats.get("total_assessments", 0),
                "benchmarked_profiles": len(benchmark_stats.get("profiles", [])),
                "local_fallback_mode": fallback_stats.get("recommended_profile"),
            },
            "phase_7_efficiency": {
                "status": "implementation_exists",
                "compressions": compression_stats.get("total", 0),
                "tokens_saved": compression_stats.get("tokens_saved", 0),
                "ab_variants": sum(len(variants) for variants in prompt_ab_stats.values()),
                "context_reuse_ready": "hit" in context_reuse,
            },
            "phase_8_progressive_disclosure": {
                "status": "implementation_exists",
                "tier_selections": tier_stats.get("total_selections", 0),
            },
            "phase_9_capability_gap": {
                "status": "implementation_exists",
                "gaps_detected": gap_stats.get("total_gaps", 0),
                "failure_patterns": len(gap_stats.get("failure_patterns", {})),
                "remediation_artifacts_recorded": remediation_results_path.exists(),
            },
            "phase_10_learning": {
                "status": "implementation_exists",
                "signals_recorded": learning_stats.get("total_signals", 0),
            },
        },
        "summary": "Phases 6-10 have repo-grounded implementations and runtime-state persistence; coordinator activation remains the redeploy gate",
    }
