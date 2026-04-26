"""
Helpers for the ai-coordinator control and delegation surfaces.

This layer turns declarative switchboard/OpenRouter configuration into concrete
runtime lanes the harness can list, schedule, and invoke without requiring
callers to hand-roll x-ai-profile usage.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional

from config import Config

# Phase 0 Slice 0.1: Route alias resolution for front-door routing
try:
    from route_aliases import resolve_route_alias, get_resolver
    _ROUTE_ALIASES_AVAILABLE = True
except ImportError:
    _ROUTE_ALIASES_AVAILABLE = False
    # Fallback if route_aliases module is not available
    def resolve_route_alias(alias: str) -> str:
        """Fallback alias resolver."""
        return "default"
    def get_resolver():
        """Fallback resolver getter."""
        return None


_ALLOWED_ROUTING_PROFILES = {
    "default",
    "local-tool-calling",
    "embedded-assist",
    "remote-gemini",
    "remote-free",
    "remote-coding",
    "remote-reasoning",
    "remote-tool-calling",
}


def _frontdoor_routing_enabled() -> bool:
    return str(os.getenv("AI_LOCAL_FRONTDOOR_ROUTING_ENABLE", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _profile_env(name: str, fallback: str) -> str:
    value = str(os.getenv(name, fallback) or fallback).strip().lower()
    return value if value in _ALLOWED_ROUTING_PROFILES else fallback


def _frontdoor_profile(route_name: str) -> str:
    # Fallbacks are local-first. Remote profiles are set via env vars only when
    # the operator has a verified, responsive remote agent available.
    mapping = {
        "default": ("AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE", "default"),
        "explore": ("AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE", "default"),
        "plan": ("AI_LOCAL_FRONTDOOR_PLAN_PROFILE", "default"),
        "implementation": ("AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE", "local-tool-calling"),
        "reasoning": ("AI_LOCAL_FRONTDOOR_REASONING_PROFILE", "local-tool-calling"),
        "tool-calling": ("AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE", "local-tool-calling"),
        "continuation": ("AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE", "default"),
    }
    env_name, fallback = mapping.get(route_name, ("AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE", "default"))
    return _profile_env(env_name, fallback)


def _runtime_record(
    runtime_id: str,
    *,
    name: str,
    profile: str,
    runtime_class: str,
    tags: List[str],
    status: str,
    note: str = "",
    model_alias: str = "",
    service_unit: str = "",
    healthcheck_url: str = "",
    now: int,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "runtime_id": runtime_id,
        "name": name,
        "profile": profile,
        "status": status,
        "runtime_class": runtime_class,
        "transport": "openai-chat",
        "endpoint_env_var": "SWITCHBOARD_URL",
        "tags": tags,
        "updated_at": now,
        "created_at": now,
        "source": "ai-coordinator-default",
    }
    if note:
        record["status_notes"] = [{"ts": now, "text": note}]
    if model_alias:
        record["model_alias"] = model_alias
    if service_unit:
        record["service_unit"] = service_unit
    if healthcheck_url:
        record["healthcheck_url"] = healthcheck_url
    return record


def runtime_defaults(now: int | None = None) -> List[Dict[str, Any]]:
    now_ts = int(now if now is not None else time.time())
    remote_configured = bool(Config.SWITCHBOARD_REMOTE_URL)
    # Local tool-calling is now fully operational with subprocess agent spawning
    # (wired into handle_ai_coordinator_delegate — spawns actual subprocess agents)
    local_tool_calling_status = "ready"

    remote_gemini_alias = Config.SWITCHBOARD_REMOTE_ALIAS_GEMINI or Config.SWITCHBOARD_REMOTE_ALIAS_FREE
    remote_gemini_status = "ready" if remote_configured and remote_gemini_alias else (
        "degraded" if remote_configured else "offline"
    )
    remote_free_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_FREE else (
        "degraded" if remote_configured else "offline"
    )
    remote_coding_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_CODING else (
        "degraded" if remote_configured else "offline"
    )
    remote_reasoning_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_REASONING else (
        "degraded" if remote_configured else "offline"
    )
    remote_tool_calling_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING else (
        "degraded" if remote_configured else "offline"
    )

    return [
        _runtime_record(
            "local-hybrid",
            name="Local Hybrid Coordinator",
            profile="default",
            runtime_class="local-agent",
            tags=["local", "hybrid", "harness", "repo", "default"],
            status="ready",
            note="Built-in local-first harness lane.",
            now=now_ts,
        ),
        _runtime_record(
            "local-tool-calling",
            name="Local Tool-Calling Agent",
            profile="local-tool-calling",
            runtime_class="local-agent",
            tags=["local", "tool-calling", "subprocess-agent", "llama.cpp"],
            status=local_tool_calling_status,
            note=(
                "Local agent lane with subprocess spawning. Delegates to switchboard "
                "for tool-augmented execution via llama.cpp."
            ),
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-gemini",
            name="OpenRouter Gemini Agent Lane",
            profile="remote-gemini",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "gemini", "planner", "synthesis"],
            status=remote_gemini_status,
            note=(
                "Uses the Gemini-oriented remote lane for discovery, planning, and "
                "general orchestration while preserving local tool and embedding fallbacks."
            ),
            model_alias=remote_gemini_alias,
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-free",
            name="OpenRouter Free Agent Lane",
            profile="remote-free",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "free", "tool-calling", "planner"],
            status=remote_free_status,
            note="Uses the free remote lane for bounded delegation and planning.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_FREE,
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-coding",
            name="OpenRouter Coding Agent Lane",
            profile="remote-coding",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "coding", "tool-calling", "implementation"],
            status=remote_coding_status,
            note="Uses the coding-optimized remote lane for implementation-heavy delegation.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_CODING,
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-reasoning",
            name="OpenRouter Reasoning Agent Lane",
            profile="remote-reasoning",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "reasoning", "tool-calling", "review"],
            status=remote_reasoning_status,
            note="Uses the higher-judgment remote lane for architecture and review tasks.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_REASONING,
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-tool-calling",
            name="OpenRouter Tool-Calling Agent Lane",
            profile="remote-tool-calling",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "tool-calling", "tools", "execution"],
            status=remote_tool_calling_status,
            note="Uses the tool-calling oriented remote lane for bounded tool-use delegation.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING,
            service_unit="ai-switchboard.service",
            healthcheck_url=f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
            now=now_ts,
        ),
    ]


def merge_runtime_defaults(registry: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    merged = {"runtimes": dict((registry or {}).get("runtimes", {}) or {})}
    for record in runtime_defaults(now=now):
        runtime_id = record["runtime_id"]
        existing = merged["runtimes"].get(runtime_id)
        if not isinstance(existing, dict):
            merged["runtimes"][runtime_id] = record
            continue
        # Refresh declarative defaults when the stored record was generated by
        # this module, but leave user-registered/custom runtimes untouched.
        if str(existing.get("source", "")).strip() == "ai-coordinator-default":
            refreshed = dict(record)
            if existing.get("created_at"):
                refreshed["created_at"] = existing["created_at"]
            merged["runtimes"][runtime_id] = refreshed
    return merged


def runtime_registry_retention_seconds() -> int:
    raw = str(getattr(Config, "AI_COORDINATOR_RUNTIME_RETENTION_SECONDS", "") or "").strip()
    if raw:
        try:
            return max(300, int(raw))
        except (TypeError, ValueError):
            pass
    return 12 * 60 * 60


def is_transient_runtime_record(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    if bool(record.get("persistent")):
        return False
    source = str(record.get("source", "") or "").strip().lower()
    if source in {"ai-coordinator-default", "user-managed", "declarative"}:
        return False
    tags = {str(tag or "").strip().lower() for tag in record.get("tags", []) if str(tag or "").strip()}
    name = str(record.get("name", "") or "").strip().lower()
    runtime_id = str(record.get("runtime_id", "") or "").strip().lower()
    runtime_class = str(record.get("runtime_class", "") or "").strip().lower()
    if source in {"runtime-register", "smoke", "test", "smoke-test"}:
        return True
    if "smoke" in tags or "test" in tags:
        return True
    if name == "smoke-runtime":
        return True
    if runtime_class == "sandboxed":
        return True
    if runtime_id.startswith("smoke-"):
        return True
    return False


def prune_runtime_registry(registry: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    current = int(now if now is not None else time.time())
    retention = runtime_registry_retention_seconds()
    merged = merge_runtime_defaults(registry, now=current)
    runtimes = dict((merged.get("runtimes", {}) or {}))
    kept: Dict[str, Dict[str, Any]] = {}
    pruned_ids: List[str] = []
    for runtime_id, record in runtimes.items():
        if not isinstance(record, dict):
            continue
        if not is_transient_runtime_record(record):
            kept[runtime_id] = record
            continue
        updated_at = int(record.get("updated_at") or record.get("created_at") or 0)
        age_s = max(0, current - updated_at) if updated_at > 0 else retention + 1
        if age_s > retention:
            pruned_ids.append(runtime_id)
            continue
        kept[runtime_id] = record
    return {
        "runtimes": kept,
        "meta": {
            "retention_seconds": retention,
            "last_pruned_at": current,
            "pruned_runtime_ids": pruned_ids,
        },
    }


def infer_profile(task: str, requested_profile: str = "") -> str:
    profile = str(requested_profile or "").strip().lower()

    # Phase 0 Slice 0.1: Try route alias resolution first
    if _ROUTE_ALIASES_AVAILABLE and requested_profile:
        # Check if this is a route alias (case-insensitive)
        resolver = get_resolver()
        if resolver and resolver.is_valid_alias(requested_profile):
            resolved = resolve_route_alias(requested_profile)
            # If resolution gives us a valid profile, use it
            if resolved in _ALLOWED_ROUTING_PROFILES:
                return resolved

    # Existing profile resolution logic
    if profile in {"default", "local", "local-hybrid", "continue-local"}:
        return _frontdoor_profile("default") if _frontdoor_routing_enabled() else "default"
    if profile in {"embedded-assist", "embedded", "assist"}:
        return "embedded-assist"
    if profile in {"explore", "exploration", "discover", "discovery"}:
        return _frontdoor_profile("explore") if _frontdoor_routing_enabled() else "remote-gemini"
    if profile in {"plan", "planner", "planning"}:
        return _frontdoor_profile("plan") if _frontdoor_routing_enabled() else "remote-gemini"
    if profile == "local-tool-calling":
        return "local-tool-calling"
    if profile in {"remote-gemini", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling"}:
        return profile

    lowered = str(task or "").lower()
    if any(token in lowered for token in ("local tool call", "local tool-call", "local tool use", "local function call")):
        return "local-tool-calling"
    if any(token in lowered for token in ("tool call", "tool-call", "tool use", "function call", "call tools", "tool routing")):
        return "remote-tool-calling"
    if any(token in lowered for token in ("architecture", "review", "risk", "tradeoff", "policy", "reasoning")):
        return "remote-reasoning"
    if any(token in lowered for token in ("code", "patch", "implement", "refactor", "fix", "debug")):
        return "remote-coding"
    if any(token in lowered for token in ("gemini", "discover", "discovery", "research", "explore", "synthesize", "synthesis")):
        return "remote-gemini"
    return "remote-gemini"


# ---------------------------------------------------------------------------
# Phase 9.3: Query Complexity Routing
# ---------------------------------------------------------------------------

# Routing telemetry accumulator
_ROUTING_DECISIONS: List[Dict[str, Any]] = []
_ROUTING_DECISION_MAX = 500  # Rolling window
_CONTINUATION_RE = re.compile(
    r"\b(resume|continue|follow[ -]?up|prior context|pick up where|last agent|left off|ongoing|current work|remaining work)\b",
    re.IGNORECASE,
)
_PLANNING_RE = re.compile(
    r"\b(plan|planning|outline|break down|steps|next step|approach|workflow|roadmap|sequence)\b",
    re.IGNORECASE,
)
_RETRIEVAL_RE = re.compile(
    r"\b(find|search|retrieve|lookup|look up|locate|grep|rg|docs|documentation|read|inspect|summarize|summary|recall)\b",
    re.IGNORECASE,
)
_TOOL_CALL_RE = re.compile(
    r"\b(tool call|tool-call|tool use|function call|call tools|use mcp|invoke tool)\b",
    re.IGNORECASE,
)
_IMPLEMENTATION_RE = re.compile(
    r"\b(implement|patch|code|refactor|fix|debug|write|update|modify|add test|create module|endpoint)\b",
    re.IGNORECASE,
)
_ARCHITECTURE_RE = re.compile(
    r"\b(architecture|architect|design|tradeoff|security review|risk review|policy|system design|scalab)\b",
    re.IGNORECASE,
)

_LIGHTWEIGHT_COMPLEXITY_MAX_WORDS = max(
    8,
    int(os.getenv("AI_COORDINATOR_LIGHTWEIGHT_COMPLEXITY_MAX_WORDS", "32")),
)


def _record_routing_decision(decision: Dict[str, Any]) -> None:
    """Record routing decision for telemetry analysis."""
    global _ROUTING_DECISIONS
    _ROUTING_DECISIONS.append({**decision, "ts": int(time.time())})
    if len(_ROUTING_DECISIONS) > _ROUTING_DECISION_MAX:
        _ROUTING_DECISIONS = _ROUTING_DECISIONS[-_ROUTING_DECISION_MAX:]


def detect_query_complexity(query: str) -> Dict[str, Any]:
    """
    Detect query complexity for intelligent model routing.

    Returns:
        Dict with complexity level, confidence, and matched signals.

    Complexity levels:
    - simple: Quick lookups, factual questions → lightweight/free models
    - medium: Standard tasks → balanced models
    - complex: Multi-step reasoning, debugging → capable models
    - architecture: Design decisions, security → reasoning-focused models
    """
    query_lower = query.lower()
    word_count = len(query.split())

    # Signal detection
    arch_signals = ["architect", "design", "system", "infrastructure", "security", "scalab", "tradeoff", "pattern"]
    complex_signals = ["implement", "integrate", "migrate", "refactor", "debug", "troubleshoot", "multi-step"]
    simple_signals = ["what is", "how do", "where", "list", "show", "find", "get", "check", "which"]
    coding_signals = ["code", "function", "class", "method", "api", "endpoint", "module"]

    continuation = bool(_CONTINUATION_RE.search(query))
    matched_arch = [s for s in arch_signals if s in query_lower]
    matched_complex = [s for s in complex_signals if s in query_lower]
    matched_simple = [s for s in simple_signals if s in query_lower]
    matched_coding = [s for s in coding_signals if s in query_lower]

    task_archetype = "general"
    if _TOOL_CALL_RE.search(query):
        task_archetype = "tool-calling"
    elif matched_arch or _ARCHITECTURE_RE.search(query):
        task_archetype = "architecture-review"
    elif _IMPLEMENTATION_RE.search(query):
        task_archetype = "implementation"
    elif _PLANNING_RE.search(query):
        task_archetype = "planning"
    elif _RETRIEVAL_RE.search(query):
        task_archetype = "retrieval"
    elif continuation:
        task_archetype = "continuation"

    # Determine complexity
    if task_archetype == "architecture-review":
        complexity = "architecture"
        confidence = min(0.5 + len(matched_arch) * 0.15, 0.95)
    elif continuation and word_count <= 24:
        complexity = "simple"
        confidence = 0.72
    elif matched_complex or word_count > 40:
        complexity = "complex"
        confidence = min(0.5 + len(matched_complex) * 0.12, 0.90)
    elif matched_simple and word_count < 15:
        complexity = "simple"
        confidence = min(0.6 + len(matched_simple) * 0.1, 0.90)
    elif matched_coding:
        complexity = "medium"  # Coding tasks are medium by default
        confidence = 0.7
    else:
        complexity = "medium"
        confidence = 0.5

    if task_archetype in {"planning", "retrieval"} and complexity in {"medium", "complex"} and word_count <= _LIGHTWEIGHT_COMPLEXITY_MAX_WORDS:
        complexity = "simple"
        confidence = max(confidence, 0.68)

    return {
        "complexity": complexity,
        "confidence": confidence,
        "word_count": word_count,
        "task_archetype": task_archetype,
        "signals": {
            "architecture": matched_arch,
            "complex": matched_complex,
            "simple": matched_simple,
            "coding": matched_coding,
            "continuation": ["continuation"] if continuation else [],
            "planning": ["planning"] if _PLANNING_RE.search(query) else [],
            "retrieval": ["retrieval"] if _RETRIEVAL_RE.search(query) else [],
            "tool_calling": ["tool-calling"] if _TOOL_CALL_RE.search(query) else [],
        },
    }


def route_by_complexity(
    query: str,
    requested_profile: str = "",
    prefer_local: bool = True,
) -> Dict[str, Any]:
    """
    Route query to appropriate model based on complexity.

    Args:
        query: The task/query to route
        requested_profile: Explicit profile request (overrides auto-routing)
        prefer_local: Prefer local models when possible

    Returns:
        Dict with recommended_profile, complexity, and routing rationale.
    """
    # If explicit profile requested, honor it
    if requested_profile:
        explicit = infer_profile(query, requested_profile)
        return {
            "recommended_profile": explicit,
            "complexity": "explicit",
            "rationale": f"explicit profile requested: {requested_profile}",
            "auto_routed": False,
        }

    # Detect complexity
    complexity_info = detect_query_complexity(query)
    complexity = complexity_info["complexity"]

    task_archetype = str(complexity_info.get("task_archetype", "general") or "general")
    continuation = bool(_CONTINUATION_RE.search(query))
    model_class = "balanced"

    if task_archetype == "tool-calling":
        if _frontdoor_routing_enabled():
            recommended = _frontdoor_profile("tool-calling")
        else:
            recommended = "local-tool-calling" if prefer_local else "remote-tool-calling"
        model_class = "tool-calling"
    elif task_archetype in {"planning", "retrieval"}:
        if prefer_local:
            recommended = "embedded-assist"
        elif _frontdoor_routing_enabled():
            route_name = "plan" if task_archetype == "planning" else "explore"
            recommended = _frontdoor_profile(route_name)
        else:
            recommended = "remote-gemini"
        model_class = "lightweight"
    elif task_archetype == "continuation" and complexity != "architecture":
        recommended = _frontdoor_profile("continuation") if _frontdoor_routing_enabled() else "default"
        model_class = "lightweight"
    elif task_archetype == "implementation":
        if _frontdoor_routing_enabled():
            recommended = _frontdoor_profile("implementation")
            if prefer_local and complexity == "simple" and recommended == "remote-coding":
                recommended = _frontdoor_profile("default")
        elif prefer_local and complexity == "simple":
            recommended = "default"
            model_class = "lightweight"
        else:
            recommended = "remote-coding"
            model_class = "coding"
    elif task_archetype == "architecture-review" or complexity == "architecture":
        recommended = _frontdoor_profile("reasoning") if _frontdoor_routing_enabled() else "remote-reasoning"
        model_class = "heavy-reasoning"
    elif complexity == "simple":
        recommended = _frontdoor_profile("explore") if _frontdoor_routing_enabled() else ("default" if prefer_local else "remote-gemini")
        model_class = "lightweight"
    elif complexity == "medium":
        recommended = _frontdoor_profile("default") if _frontdoor_routing_enabled() else ("default" if prefer_local else "remote-gemini")
        model_class = "lightweight"
    else:
        recommended = _frontdoor_profile("implementation") if _frontdoor_routing_enabled() else "remote-coding"
        model_class = "coding"

    if continuation and complexity != "architecture" and task_archetype != "tool-calling":
        if _frontdoor_routing_enabled():
            recommended = _frontdoor_profile("continuation")
        else:
            if prefer_local and task_archetype in {"planning", "retrieval", "continuation", "general"}:
                recommended = "embedded-assist"
            else:
                recommended = "default" if prefer_local or task_archetype != "implementation" else recommended
        if recommended in {"default", "embedded-assist"}:
            model_class = "lightweight"

    # Build rationale
    signals = complexity_info.get("signals", {})
    signal_parts = []
    for sig_type, matches in signals.items():
        if matches:
            signal_parts.append(f"{sig_type}({','.join(matches[:2])})")
    rationale = (
        f"task_archetype={task_archetype}, complexity={complexity}, "
        f"confidence={complexity_info['confidence']:.0%}, model_class={model_class}"
    )
    if signal_parts:
        rationale += f", signals=[{'; '.join(signal_parts[:3])}]"

    # Phase 8.11 — Thinking mode recommendation based on complexity.
    # Qwen3 /no_think skips CoT overhead for simple/medium tasks (~3-5x faster).
    # Architecture and complex implementation benefit from CoT reasoning.
    if complexity in {"architecture"} or task_archetype in {"architecture-review"}:
        thinking_mode = "on"
        thinking_budget = 4096
    elif complexity == "complex" or task_archetype in {"implementation", "tool-calling"}:
        thinking_mode = "on"
        thinking_budget = 1024
    else:
        thinking_mode = "off"
        thinking_budget = 0

    decision = {
        "recommended_profile": recommended,
        "model_class": model_class,
        "task_archetype": task_archetype,
        "complexity": complexity,
        "complexity_confidence": complexity_info["confidence"],
        "word_count": complexity_info["word_count"],
        "rationale": rationale,
        "auto_routed": True,
        "prefer_local": prefer_local,
        "thinking_mode": thinking_mode,
        "thinking_budget_tokens": thinking_budget,
    }

    # Record for telemetry
    _record_routing_decision({
        "query_prefix": query[:60] + "..." if len(query) > 60 else query,
        "task_archetype": task_archetype,
        "complexity": complexity,
        "profile": recommended,
        "model_class": model_class,
        "confidence": complexity_info["confidence"],
    })

    return decision


def get_routing_stats() -> Dict[str, Any]:
    """Get routing decision statistics for analysis."""
    if not _ROUTING_DECISIONS:
        return {"total_decisions": 0, "breakdown": {}}

    breakdown: Dict[str, int] = {}
    profile_breakdown: Dict[str, int] = {}
    for d in _ROUTING_DECISIONS:
        c = d.get("complexity", "unknown")
        p = d.get("profile", "unknown")
        breakdown[c] = breakdown.get(c, 0) + 1
        profile_breakdown[p] = profile_breakdown.get(p, 0) + 1

    return {
        "total_decisions": len(_ROUTING_DECISIONS),
        "complexity_breakdown": breakdown,
        "profile_breakdown": profile_breakdown,
        "recent_window_seconds": _ROUTING_DECISIONS[-1]["ts"] - _ROUTING_DECISIONS[0]["ts"] if len(_ROUTING_DECISIONS) > 1 else 0,
    }


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() not in {"text", "input_text"}:
                continue
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        text = str(content.get("text") or "").strip()
        return text
    return ""


def extract_task_from_openai_messages(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    user_texts: List[str] = []
    fallback_texts: List[str] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        text = _message_content_text(item.get("content"))
        if not text:
            continue
        role = str(item.get("role") or "").strip().lower()
        if role == "user":
            user_texts.append(text)
        elif role in {"assistant", "system", "tool"}:
            fallback_texts.append(text)
    if user_texts:
        return "\n".join(user_texts[-2:]).strip()
    if fallback_texts:
        return "\n".join(fallback_texts[-1:]).strip()
    return ""


def route_openai_chat_payload(
    payload: Dict[str, Any] | None,
    requested_profile: str = "",
    prefer_local: bool = True,
) -> Dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    messages = body.get("messages")
    task = extract_task_from_openai_messages(messages)
    if not task:
        task = str(body.get("prompt") or body.get("input") or "").strip()

    tools_present = isinstance(body.get("tools"), list) and len(body.get("tools") or []) > 0
    tool_choice = body.get("tool_choice")
    tool_choice_requested = bool(tool_choice) and str(tool_choice).strip().lower() not in {"none", "false"}
    if not requested_profile and (tools_present or tool_choice_requested):
        requested_profile = "local-tool-calling" if prefer_local else "remote-tool-calling"

    decision = route_by_complexity(
        task or "continue chat request",
        requested_profile=requested_profile,
        prefer_local=prefer_local,
    )
    decision["task"] = task
    decision["tools_present"] = tools_present
    decision["tool_choice_requested"] = tool_choice_requested
    return decision


def default_runtime_id_for_profile(profile: str) -> str:
    mapping = {
        "default": "local-hybrid",
        "local": "local-hybrid",
        "local-hybrid": "local-hybrid",
        "continue-local": "local-hybrid",
        "local-tool-calling": "local-tool-calling",
        "remote-gemini": "openrouter-gemini",
        "remote-free": "openrouter-free",
        "remote-coding": "openrouter-coding",
        "remote-reasoning": "openrouter-reasoning",
        "remote-tool-calling": "openrouter-tool-calling",
    }
    return mapping.get(str(profile or "").strip().lower(), "openrouter-gemini")


def coerce_orchestration_context(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = incoming if isinstance(incoming, dict) else {}
    requested_by = str(
        payload.get("requesting_agent")
        or payload.get("requested_by")
        or payload.get("agent")
        or payload.get("agent_type")
        or "human"
    ).strip() or "human"
    requester_role = str(payload.get("requester_role") or payload.get("role") or "orchestrator").strip().lower()
    if requester_role not in {"orchestrator", "sub-agent"}:
        requester_role = "orchestrator"
    return {
        "requesting_agent": requested_by,
        "requested_by": requested_by,
        "requester_role": requester_role,
        "top_level_orchestrator": requester_role == "orchestrator",
        "subagents_may_spawn_subagents": False,
        "delegate_via_coordinator_only": True,
        "coordinator_delegate_path": "/control/ai-coordinator/delegate",
    }


def _delegation_system_prompt(profile: str) -> str:
    role = {
        "remote-gemini": "gemini orchestration sub-agent",
        "remote-coding": "implementation sub-agent",
        "remote-reasoning": "architecture/review sub-agent",
        "remote-tool-calling": "tool-calling sub-agent",
        "remote-free": "bounded research/planning sub-agent",
        "local-tool-calling": "local tool-calling prep sub-agent",
        "default": "local delegated sub-agent",
    }.get(str(profile or "").strip().lower(), "delegated sub-agent")
    return (
        f"You are a {role} inside the NixOS-Dev-Quick-Deploy harness.\n"
        "You are not the orchestrator.\n"
        "Do not spawn, invoke, or route additional sub-agents.\n"
        "If more delegation is needed, return a coordinator_handoff note for the orchestrator to submit through /control/ai-coordinator/delegate.\n"
        "Execute only the assigned slice.\n"
        "Respond concisely.\n"
        "Do not invent files, commands, or validation you did not actually derive from the provided task/context.\n"
        "Return evidence-first output with concrete paths, commands, and risks when available.\n"
        "If the task cannot be completed from the provided inputs, say what is missing instead of improvising."
    )


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    text = str(value or "").strip()
    return [text] if text else []


def _profile_completion_rules(profile: str) -> List[str]:
    normalized = str(profile or "").strip().lower()
    if normalized == "remote-coding":
        return [
            "- keep the result tied to existing repo paths and current runtime behavior",
            "- prefer a minimal patch sketch, validation note, and concrete risk over broad redesign",
            "- do not propose extra files or tests unless the task/context justifies them",
        ]
    if normalized == "remote-reasoning":
        return [
            "- return a recommended direction first, then the top risks and tradeoffs",
            "- keep architecture/review notes concrete and bounded to the stated task",
            "- do not drift into patch design unless the task explicitly asks for it",
        ]
    if normalized == "remote-gemini":
        return [
            "- optimize for orchestration-ready synthesis that can hand off cleanly to local tools or downstream agents",
            "- prefer concise plans, explicit evidence, and the next harness action over broad exposition",
            "- call out when local tool, embedding, or local-model follow-up should be triggered",
        ]
    if normalized == "remote-free":
        return [
            "- keep synthesis short: main finding, evidence, and one next step",
            "- avoid generic background paragraphs or repeated task restatement",
            "- prefer directly reusable findings over speculation",
        ]
    if normalized == "local-tool-calling":
        return [
            "- prepare an OpenAI-compatible tool contract and explicit fallback path",
            "- assume the local backend may reject tools and state that fallback clearly",
            "- keep the contract bounded to approved harness capabilities",
        ]
    if normalized == "remote-tool-calling":
        return [
            "- return a final artifact even if the provider starts with tool-call planning",
            "- keep tool arguments strict and bounded to the stated task",
            "- do not claim any tool was executed unless execution evidence is present in the prompt",
        ]
    return [
        "- keep the artifact bounded to the assigned slice",
        "- prefer concise result and evidence over narrative explanation",
    ]


def _task_shape_completion_rules(task: str, profile: str) -> List[str]:
    lowered = str(task or "").strip().lower()
    normalized = str(profile or "").strip().lower()
    rules: List[str] = []
    if any(token in lowered for token in ("deploy", "rollback", "switch", "nixos-rebuild", "service restart", "systemd")):
        rules.extend(
            [
                "- include the exact live verification signal and one rollback path",
                "- prefer declarative activation guidance over ad hoc restart loops when both are viable",
            ]
        )
    if any(token in lowered for token in ("fix", "bug", "regression", "debug", "failure")) and normalized in {"remote-coding", "remote-free", "default"}:
        rules.extend(
            [
                "- state the most likely root cause before proposing the smallest reversible fix",
                "- include one concrete validation step that would prove the bugfix actually worked",
            ]
        )
    if any(token in lowered for token in ("review", "risk", "tradeoff", "acceptance", "patch review")):
        rules.extend(
            [
                "- lead with the recommended direction or top finding before secondary commentary",
                "- call out the main residual risk instead of returning only a neutral summary",
            ]
        )
    if any(token in lowered for token in ("research", "scrape", "summarize", "source", "dataset", "retrieval")):
        rules.extend(
            [
                "- keep findings tied to explicit sources or bounded source packs when provided",
                "- separate extracted evidence from summary claims so the orchestrator can review quickly",
            ]
        )
    seen = set()
    deduped: List[str] = []
    for item in rules:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _delegation_contract_block(task: str, profile: str, context: Dict[str, Any] | None) -> str:
    ctx = context if isinstance(context, dict) else {}
    repo_paths = _normalize_list(ctx.get("repo_paths"))
    constraints = _normalize_list(ctx.get("constraints"))
    evidence = _normalize_list(ctx.get("evidence_requirements"))
    anti_goals = _normalize_list(ctx.get("anti_goals"))
    artifact = str(ctx.get("expected_artifact") or "").strip()
    output_format = str(ctx.get("output_format") or "").strip()

    default_artifact = {
        "remote-gemini": "bounded orchestration synthesis with explicit handoff to local tools or embedded models when useful",
        "remote-coding": "small patch plan or implementation sketch tied to existing repo paths",
        "remote-reasoning": "design/review notes with concrete risks and recommended direction",
        "remote-tool-calling": "bounded tool-calling plan or tool-use-ready task output with strict arguments",
        "local-tool-calling": "local tool-calling-ready task contract with explicit fallback if the backend lacks tool support",
        "remote-free": "bounded synthesis with actionable findings",
        "default": "bounded task result with evidence",
    }.get(str(profile or "").strip().lower(), "bounded task result with evidence")
    if not artifact:
        artifact = default_artifact

    lines = [
        f"Task: {task.strip()}",
        f"Expected artifact: {artifact}",
        "Required output sections:",
        "- result",
        "- evidence",
        "- risks",
        "- rollback_or_next_step",
        "- coordinator_handoff (only if more delegation is required)",
        "Completion rules:",
    ]
    lines.extend(_profile_completion_rules(profile))
    lines.extend(_task_shape_completion_rules(task, profile))
    if output_format:
        lines.append(f"Output format constraint: {output_format}")
    if repo_paths:
        lines.append("Allowed repo paths:")
        lines.extend(f"- {item}" for item in repo_paths[:8])
    if constraints:
        lines.append("Constraints:")
        lines.extend(f"- {item}" for item in constraints[:8])
    else:
        lines.append("Constraints:")
        lines.append("- stay within the assigned slice")
        lines.append("- do not invent repo paths or validation")
    if evidence:
        lines.append("Evidence requirements:")
        lines.extend(f"- {item}" for item in evidence[:8])
    else:
        lines.append("Evidence requirements:")
        lines.append("- cite concrete files, commands, or runtime facts when available")
    if anti_goals:
        lines.append("Anti-goals:")
        lines.extend(f"- {item}" for item in anti_goals[:8])
    if str(profile or "").strip().lower() == "remote-tool-calling":
        lines.append("Tool-calling completion rules:")
        lines.append("- tool-call-only output is insufficient")
        lines.append("- if you propose tool calls, still return a final artifact from the information currently available")
        lines.append("- if no tool execution occurred, summarize the proposed tool actions and the exact next step")
    return "\n".join(lines)


def build_tool_call_finalization_messages(
    task: str,
    tool_calls: List[Dict[str, Any]] | None,
    profile: str = "remote-tool-calling",
) -> List[Dict[str, str]]:
    compact_calls: List[str] = []
    for item in tool_calls or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or "unknown_tool"
        arguments = str(item.get("arguments") or "").strip()
        if arguments:
            compact_calls.append(f"- {name}: {arguments}")
        else:
            compact_calls.append(f"- {name}")
    if not compact_calls:
        compact_calls.append("- no tool call details available")
    return [
        {
            "role": "system",
            "content": _delegation_system_prompt(profile)
            + "\nYou are performing a bounded finalization pass after a tool-call-only reply."
            + "\nDo not invent tool execution results."
            + "\nReturn the final artifact now using only the task and proposed tool-call plan.",
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    f"Original task: {str(task or '').strip()}",
                    "The prior delegated reply proposed tool calls but returned no final assistant text.",
                    "Proposed tool-call plan:",
                    *compact_calls[:6],
                    "Required output sections:",
                    "- result",
                    "- evidence",
                    "- risks",
                    "- rollback_or_next_step",
                    "Constraints:",
                    "- do not claim any tool actually ran",
                    "- summarize only the proposed actions and what should happen next",
                    "- keep the artifact concise and concrete",
                ]
            ),
        },
    ]


def build_reasoning_finalization_messages(
    task: str,
    reasoning_excerpt: str,
    profile: str = "remote-reasoning",
) -> List[Dict[str, str]]:
    excerpt = str(reasoning_excerpt or "").strip()[:800] or "no reasoning excerpt available"
    return [
        {
            "role": "system",
            "content": _delegation_system_prompt(profile)
            + "\nYou are performing a bounded finalization pass after a reasoning-only reply."
            + "\nTurn the reasoning draft into a concrete final artifact."
            + "\nDo not emit hidden chain-of-thought or restate internal planning.",
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    f"Original task: {str(task or '').strip()}",
                    "The prior delegated reply returned reasoning notes but no final assistant content.",
                    "Recovered reasoning draft:",
                    excerpt,
                    "Required output sections:",
                    "- result",
                    "- evidence",
                    "- risks",
                    "- rollback_or_next_step",
                    "Constraints:",
                    "- convert the reasoning into a direct final artifact",
                    "- keep only the top recommendation, evidence, and tradeoff",
                    "- do not mention hidden reasoning or internal draft process",
                ]
            ),
        },
    ]


def build_messages(
    task: str,
    system_prompt: str = "",
    context: Dict[str, Any] | None = None,
    profile: str = "remote-free",
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    normalized_profile = str(profile or "").strip().lower()
    if system_prompt.strip():
        sys_prompt = system_prompt.strip()
    elif normalized_profile in {"default", "local-tool-calling"}:
        sys_prompt = Config.build_local_system_prompt() or _delegation_system_prompt(profile)
    else:
        sys_prompt = _delegation_system_prompt(profile)
    messages.append({"role": "system", "content": sys_prompt})
    body = _delegation_contract_block(str(task or ""), profile, context)
    extra_context = context.get("extra_context") if isinstance(context, dict) else None
    if extra_context:
        body += "\n\nAdditional context:\n" + str(extra_context).strip()
    messages.append({"role": "user", "content": body.strip()})
    return messages
