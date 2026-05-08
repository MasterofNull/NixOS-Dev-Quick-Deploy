"""
model_coordinator.py — Model Role Classification and Dual-Model Routing (Phase 12.1/12.2)

Coordinates work distribution across remote and local models:
- Model role classification (orchestrator, reasoning, coding, embedding)
- Task routing to appropriate model types
- Cost optimization with tier-based routing (local > free > paid)
- Cache warming for anticipated queries
- Hint generation and tool suggestion serving

Usage:
    from model_coordinator import ModelCoordinator, get_model_coordinator

    coord = get_model_coordinator()
    assignment = coord.classify_and_route(
        task="Implement user authentication",
        context={"domain": "web-dev", "complexity": "complex"}
    )
"""

from __future__ import annotations

import os
import json
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# Import LLM router for cost-optimization layer
try:
    from llm_router import get_router, AgentTier, TaskComplexity
    _LLM_ROUTER_AVAILABLE = True
except ImportError:
    logger.warning("llm_router not available, cost optimization disabled")
    _LLM_ROUTER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Model Role Definitions (Phase 12.1)
# ---------------------------------------------------------------------------

class ModelRole(str, Enum):
    """Model roles in the coordination system."""
    ORCHESTRATOR = "orchestrator"    # High-level planning, delegation, review
    REASONING = "reasoning"          # Architecture, analysis, design decisions
    CODING = "coding"                # Implementation, refactoring, tests
    EMBEDDING = "embedding"          # Semantic search, RAG, similarity
    FAST_CHAT = "fast_chat"          # Quick lookups, simple queries


@dataclass
class ModelProfile:
    """Profile describing a model's capabilities and routing info."""
    name: str
    role: ModelRole
    endpoint: str
    capabilities: Set[str] = field(default_factory=set)
    preferred_domains: Set[str] = field(default_factory=set)
    max_context_tokens: int = 8192
    avg_latency_ms: float = 0.0
    is_local: bool = False
    is_available: bool = True
    cost_per_1k_tokens: float = 0.0  # 0 = free/local


# ---------------------------------------------------------------------------
# Task Classification (Phase 12.1)
# ---------------------------------------------------------------------------

@dataclass
class TaskClassification:
    """Result of task classification for routing."""
    task: str
    primary_role: ModelRole
    secondary_role: Optional[ModelRole]
    confidence: float
    signals_matched: List[str]
    domain_hint: Optional[str]
    complexity: str  # simple, medium, complex, architecture
    requires_handoff: bool  # True if task needs reasoning then coding


# Task signal patterns for classification
ROLE_SIGNALS = {
    ModelRole.ORCHESTRATOR: [
        "review", "approve", "delegate", "coordinate", "orchestrate",
        "merge", "finalize", "accept", "reject", "prioritize"
    ],
    ModelRole.REASONING: [
        "architect", "design", "analyze", "plan", "strategize",
        "evaluate", "compare", "tradeoff", "security audit", "assess",
        "recommend", "advise", "investigate", "diagnose", "explain why"
    ],
    ModelRole.CODING: [
        "implement", "code", "write", "build", "create function",
        "refactor", "fix bug", "add feature", "write test", "debug",
        "optimize", "performance", "add endpoint", "create module"
    ],
    ModelRole.EMBEDDING: [
        "search", "find similar", "recall", "memory", "rag",
        "semantic", "embed", "index", "retrieve", "lookup"
    ],
    ModelRole.FAST_CHAT: [
        "what is", "how do", "where", "list", "show me",
        "quick", "simple", "help", "explain", "define"
    ],
}


def classify_task(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> TaskClassification:
    """
    Classify a task to determine which model role should handle it.

    Args:
        task: The task description
        context: Optional context with domain, complexity hints

    Returns:
        TaskClassification with role assignment and confidence
    """
    task_lower = task.lower()
    context = context or {}

    # Count signal matches per role
    role_scores: Dict[ModelRole, List[str]] = {role: [] for role in ModelRole}

    for role, signals in ROLE_SIGNALS.items():
        for signal in signals:
            if signal in task_lower:
                role_scores[role].append(signal)

    # Find primary role (highest match count)
    sorted_roles = sorted(
        role_scores.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    primary_role = sorted_roles[0][0]
    primary_signals = sorted_roles[0][1]
    primary_count = len(primary_signals)

    # Find secondary role if applicable
    secondary_role = None
    if len(sorted_roles) > 1 and len(sorted_roles[1][1]) > 0:
        secondary_role = sorted_roles[1][0]

    # Calculate confidence
    total_signals = sum(len(s) for s in role_scores.values())
    confidence = primary_count / max(total_signals, 1)

    # Determine complexity from context or task
    complexity = context.get("complexity", "medium")
    word_count = len(task.split())
    if complexity == "medium":
        if word_count > 30 or "multi-step" in task_lower:
            complexity = "complex"
        elif word_count < 10 and any(s in task_lower for s in ROLE_SIGNALS[ModelRole.FAST_CHAT]):
            complexity = "simple"
        elif any(s in task_lower for s in ROLE_SIGNALS[ModelRole.REASONING]):
            complexity = "architecture"

    # Check if task requires handoff (reasoning -> coding)
    requires_handoff = (
        primary_role == ModelRole.REASONING
        and secondary_role == ModelRole.CODING
        and confidence < 0.7  # Mixed signals suggest both are needed
    )

    return TaskClassification(
        task=task,
        primary_role=primary_role if primary_count > 0 else ModelRole.CODING,
        secondary_role=secondary_role,
        confidence=confidence if primary_count > 0 else 0.5,
        signals_matched=primary_signals,
        domain_hint=context.get("domain"),
        complexity=complexity,
        requires_handoff=requires_handoff,
    )


# ---------------------------------------------------------------------------
# Model Routing (Phase 12.2)
# ---------------------------------------------------------------------------

# Default model profiles (can be overridden via config)
DEFAULT_PROFILES: Dict[str, ModelProfile] = {
    "claude-orchestrator": ModelProfile(
        name="claude-orchestrator",
        role=ModelRole.ORCHESTRATOR,
        endpoint="anthropic",
        capabilities={"planning", "review", "delegation", "synthesis"},
        max_context_tokens=200000,
        cost_per_1k_tokens=0.015,
    ),
    "claude-reasoning": ModelProfile(
        name="claude-reasoning",
        role=ModelRole.REASONING,
        endpoint="anthropic",
        capabilities={"architecture", "analysis", "design", "security"},
        max_context_tokens=200000,
        cost_per_1k_tokens=0.015,
    ),
    "qwen-coder": ModelProfile(
        name="qwen-coder",
        role=ModelRole.CODING,
        endpoint="openrouter",
        capabilities={"implementation", "refactoring", "testing", "debugging"},
        preferred_domains={"web-dev", "ai-harness", "devops"},
        max_context_tokens=32768,
        cost_per_1k_tokens=0.0,  # Free tier
    ),
    "codex": ModelProfile(
        name="codex",
        role=ModelRole.CODING,
        endpoint="openrouter",
        capabilities={"implementation", "refactoring", "code-review"},
        preferred_domains={"web-dev", "data-engineering"},
        max_context_tokens=128000,
        cost_per_1k_tokens=0.0,
    ),
    "gemini-orchestrator": ModelProfile(
        name="gemini-orchestrator",
        role=ModelRole.ORCHESTRATOR,
        endpoint="openrouter",
        capabilities={"planning", "synthesis", "discovery", "delegation"},
        preferred_domains={"ai-harness", "research", "planning"},
        max_context_tokens=1048576,
        cost_per_1k_tokens=0.0,
    ),
    "llama-cpp-local": ModelProfile(
        name="llama-cpp-local",
        role=ModelRole.FAST_CHAT,
        endpoint="http://127.0.0.1:8080",
        capabilities={"chat", "completion", "quick-lookup"},
        max_context_tokens=4096,
        is_local=True,
        cost_per_1k_tokens=0.0,
    ),
    "qdrant-embedding": ModelProfile(
        name="qdrant-embedding",
        role=ModelRole.EMBEDDING,
        endpoint="http://127.0.0.1:6333",
        capabilities={"embedding", "similarity", "rag"},
        is_local=True,
        cost_per_1k_tokens=0.0,
    ),
}


@dataclass
class RoutingDecision:
    """Result of model routing decision."""
    task_classification: TaskClassification
    primary_model: str
    secondary_model: Optional[str]
    handoff_required: bool
    context_transfer_needed: bool
    routing_rationale: str
    estimated_cost: float
    prefer_local: bool


class ModelCoordinator:
    """
    Coordinates work distribution across models.

    Responsibilities:
    - Classify tasks by required model role
    - Route to appropriate models (remote/local)
    - Manage handoffs between reasoning and coding models
    - Track routing decisions for telemetry
    - Support cache warming and tool suggestion serving
    """

    def __init__(self, config_path: Optional[str] = None):
        self._profiles: Dict[str, ModelProfile] = dict(DEFAULT_PROFILES)
        self._routing_history: deque = deque(maxlen=500)
        self._cache_warming_queue: deque = deque(maxlen=100)
        self._tool_suggestions_cache: Dict[str, List[Dict[str, Any]]] = {}

        if config_path and Path(config_path).exists():
            self._load_config(config_path)

    def _load_config(self, path: str) -> None:
        """Load model profiles from config file."""
        try:
            with open(path) as f:
                config = json.load(f)
            for name, profile_data in config.get("models", {}).items():
                self._profiles[name] = ModelProfile(
                    name=name,
                    role=ModelRole(profile_data.get("role", "coding")),
                    endpoint=profile_data.get("endpoint", ""),
                    capabilities=set(profile_data.get("capabilities", [])),
                    preferred_domains=set(profile_data.get("preferred_domains", [])),
                    max_context_tokens=profile_data.get("max_context_tokens", 8192),
                    is_local=profile_data.get("is_local", False),
                    cost_per_1k_tokens=profile_data.get("cost_per_1k_tokens", 0.0),
                )
        except Exception as e:
            logger.warning("Failed to load model config: %s", e)

    def classify_and_route(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        prefer_local: bool = False,
        cost_sensitive: bool = True,
        use_tier_routing: bool = True,
    ) -> RoutingDecision:
        """
        Classify a task and route to appropriate model(s).

        Args:
            task: The task description
            context: Optional context (domain, complexity, etc.)
            prefer_local: Prefer local models when possible
            cost_sensitive: Prefer free/cheap models when quality allows
            use_tier_routing: Use LLM router for tier-based cost optimization

        Returns:
            RoutingDecision with model assignment and rationale
        """
        classification = classify_task(task, context)

        # Use LLM router for tier-based routing if available
        tier_suggestion = None
        if use_tier_routing and _LLM_ROUTER_AVAILABLE and cost_sensitive:
            try:
                router = get_router()
                tier, suggested_model = router.route_task(task, context or {})
                tier_suggestion = {"tier": tier.value, "model": suggested_model}
                logger.debug(f"LLM router suggests tier={tier.value}, model={suggested_model}")
            except Exception as e:
                logger.warning(f"LLM router failed, falling back to model coordinator: {e}")

        # Find models matching the primary role
        primary_candidates = [
            p for p in self._profiles.values()
            if p.role == classification.primary_role and p.is_available
        ]

        # Apply tier suggestion if available
        if tier_suggestion and tier_suggestion["model"] in [p.name for p in primary_candidates]:
            primary_model = tier_suggestion["model"]
            logger.info(f"Using LLM router suggestion: {primary_model}")
        else:
            # Apply preferences
            if prefer_local:
                local_candidates = [p for p in primary_candidates if p.is_local]
                if local_candidates:
                    primary_candidates = local_candidates

            if cost_sensitive:
                primary_candidates.sort(key=lambda p: p.cost_per_1k_tokens)

            # Select primary model
            primary_model = primary_candidates[0].name if primary_candidates else "qwen-coder"

        # Handle handoff case (reasoning -> coding)
        secondary_model = None
        context_transfer_needed = False

        if classification.requires_handoff:
            coding_models = [
                p for p in self._profiles.values()
                if p.role == ModelRole.CODING and p.is_available
            ]
            if cost_sensitive:
                coding_models.sort(key=lambda p: p.cost_per_1k_tokens)
            if coding_models:
                secondary_model = coding_models[0].name
                context_transfer_needed = True

        # Build rationale
        rationale_parts = [
            f"Task classified as {classification.primary_role.value}",
            f"complexity={classification.complexity}",
        ]
        if tier_suggestion:
            rationale_parts.append(f"tier={tier_suggestion['tier']}")
        if classification.signals_matched:
            rationale_parts.append(f"signals: {', '.join(classification.signals_matched[:3])}")
        if classification.requires_handoff:
            rationale_parts.append("handoff: reasoning->coding")
        if prefer_local:
            rationale_parts.append("prefer_local=true")
        if use_tier_routing and not _LLM_ROUTER_AVAILABLE:
            rationale_parts.append("tier_routing=unavailable")

        # Estimate cost (rough)
        primary_profile = self._profiles.get(primary_model)
        estimated_cost = (primary_profile.cost_per_1k_tokens * 2) if primary_profile else 0.0

        decision = RoutingDecision(
            task_classification=classification,
            primary_model=primary_model,
            secondary_model=secondary_model,
            handoff_required=classification.requires_handoff,
            context_transfer_needed=context_transfer_needed,
            routing_rationale="; ".join(rationale_parts),
            estimated_cost=estimated_cost,
            prefer_local=prefer_local,
        )

        # Record for telemetry
        self._routing_history.append({
            "timestamp": time.time(),
            "task_hash": hash(task) % 10000,
            "primary_role": classification.primary_role.value,
            "primary_model": primary_model,
            "handoff": classification.requires_handoff,
            "complexity": classification.complexity,
        })

        return decision

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics for telemetry."""
        if not self._routing_history:
            return {"total_decisions": 0, "history_empty": True}

        role_counts: Dict[str, int] = {}
        model_counts: Dict[str, int] = {}
        complexity_counts: Dict[str, int] = {}
        handoff_count = 0

        for entry in self._routing_history:
            role = entry.get("primary_role", "unknown")
            model = entry.get("primary_model", "unknown")
            complexity = entry.get("complexity", "unknown")

            role_counts[role] = role_counts.get(role, 0) + 1
            model_counts[model] = model_counts.get(model, 0) + 1
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
            if entry.get("handoff"):
                handoff_count += 1

        total = len(self._routing_history)
        return {
            "total_decisions": total,
            "role_distribution": role_counts,
            "model_distribution": model_counts,
            "complexity_distribution": complexity_counts,
            "handoff_rate": handoff_count / total if total > 0 else 0,
        }

    # -----------------------------------------------------------------------
    # Cache Warming (Proactive)
    # -----------------------------------------------------------------------

    def queue_cache_warming(
        self,
        query: str,
        domain: Optional[str] = None,
        priority: int = 1
    ) -> None:
        """
        Queue a query for proactive cache warming.

        High-priority items will be processed first by local models
        to pre-compute embeddings, hints, and tool suggestions.
        """
        self._cache_warming_queue.append({
            "query": query,
            "domain": domain,
            "priority": priority,
            "queued_at": time.time(),
        })

    def get_cache_warming_batch(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """Get next batch of queries for cache warming."""
        # Sort by priority (descending) and return batch
        sorted_queue = sorted(
            list(self._cache_warming_queue),
            key=lambda x: x.get("priority", 0),
            reverse=True
        )
        return sorted_queue[:batch_size]

    def clear_processed_warming(self, processed_queries: List[str]) -> None:
        """Remove processed queries from warming queue."""
        query_set = set(processed_queries)
        self._cache_warming_queue = deque(
            [q for q in self._cache_warming_queue if q.get("query") not in query_set],
            maxlen=100
        )

    # -----------------------------------------------------------------------
    # Tool Suggestion Serving
    # -----------------------------------------------------------------------

    def get_tool_suggestions(
        self,
        domain: str,
        task_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tool suggestions for a domain/task type.

        Returns cached suggestions or generates new ones based on
        domain configuration from progressive disclosure.
        """
        cache_key = f"{domain}:{task_type or 'general'}"

        if cache_key in self._tool_suggestions_cache:
            return self._tool_suggestions_cache[cache_key]

        # Generate suggestions based on domain
        # (In production, this would query progressive disclosure config)
        suggestions = self._generate_domain_suggestions(domain, task_type)
        self._tool_suggestions_cache[cache_key] = suggestions

        return suggestions

    def _generate_domain_suggestions(
        self,
        domain: str,
        task_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Generate tool suggestions for a domain."""
        # Default suggestions by domain
        DOMAIN_TOOLS = {
            "nixos-dev": [
                {"tool": "nixos-rebuild", "when": "deploying changes", "priority": 1},
                {"tool": "nix-build", "when": "testing derivations", "priority": 2},
                {"tool": "nix flake check", "when": "validating flake", "priority": 2},
            ],
            "web-dev": [
                {"tool": "npm run build", "when": "building project", "priority": 1},
                {"tool": "npm test", "when": "running tests", "priority": 2},
                {"tool": "npx eslint", "when": "linting code", "priority": 3},
            ],
            "ai-harness": [
                {"tool": "aq-report", "when": "checking system status", "priority": 1},
                {"tool": "aq-hints", "when": "getting workflow hints", "priority": 2},
                {"tool": "aq-qa", "when": "running QA checks", "priority": 2},
            ],
            "devops": [
                {"tool": "systemctl status", "when": "checking service", "priority": 1},
                {"tool": "journalctl -f", "when": "viewing logs", "priority": 2},
                {"tool": "docker ps", "when": "checking containers", "priority": 3},
            ],
        }

        return DOMAIN_TOOLS.get(domain, [])

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all configured model profiles."""
        return [
            {
                "name": p.name,
                "role": p.role.value,
                "endpoint": p.endpoint,
                "is_local": p.is_local,
                "is_available": p.is_available,
                "cost_per_1k_tokens": p.cost_per_1k_tokens,
            }
            for p in self._profiles.values()
        ]


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_coordinator: Optional[ModelCoordinator] = None


def get_model_coordinator() -> ModelCoordinator:
    """Get or create singleton ModelCoordinator."""
    global _coordinator
    if _coordinator is None:
        config_path = os.getenv(
            "MODEL_COORDINATOR_CONFIG",
            str(Path(__file__).parent.parent.parent.parent / "config" / "model-coordinator.json")
        )
        _coordinator = ModelCoordinator(config_path)
    return _coordinator


def classify_and_route_task(
    task: str,
    context: Optional[Dict[str, Any]] = None,
    prefer_local: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function for task classification and routing.

    Returns dict with routing decision for easy JSON serialization.
    """
    coord = get_model_coordinator()
    decision = coord.classify_and_route(task, context, prefer_local=prefer_local)

    return {
        "primary_model": decision.primary_model,
        "secondary_model": decision.secondary_model,
        "handoff_required": decision.handoff_required,
        "context_transfer_needed": decision.context_transfer_needed,
        "routing_rationale": decision.routing_rationale,
        "estimated_cost": decision.estimated_cost,
        "task_classification": {
            "primary_role": decision.task_classification.primary_role.value,
            "secondary_role": decision.task_classification.secondary_role.value if decision.task_classification.secondary_role else None,
            "confidence": decision.task_classification.confidence,
            "complexity": decision.task_classification.complexity,
            "signals_matched": decision.task_classification.signals_matched,
        },
    }
