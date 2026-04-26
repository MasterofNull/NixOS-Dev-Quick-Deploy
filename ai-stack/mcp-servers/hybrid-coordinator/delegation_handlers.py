"""
Delegation helper module for the hybrid-coordinator HTTP server.

Extracted from http_server.py during Phase 11.2 decomposition. This module
follows the existing init()-based dependency injection pattern used by other
extracted coordinator modules.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from context_management import ContextChunk
from lazy_context import ContextDependencyGraph, ContextNode, LazyContextLoader
from prompt_compression import CompressionStrategy

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Remote availability cache — gates remote routing without a per-request probe.
# TTL: 5 minutes. A remote profile that returns 4xx/5xx is marked unavailable
# until the TTL expires, after which it is re-probed on next use.
# ---------------------------------------------------------------------------
_REMOTE_AVAIL_CACHE: Dict[str, Any] = {}
_REMOTE_AVAIL_TTL_S = 300.0
_REMOTE_AVAIL_LOCK: Optional[Any] = None

# ---------------------------------------------------------------------------
# Injected dependencies — populated by init()
# ---------------------------------------------------------------------------
_AGENT_POOL_MANAGER: Optional[Any] = None
_DELEGATED_QUALITY_CHECKER: Optional[Any] = None
_DELEGATED_RESULT_REFINER: Optional[Any] = None
_DELEGATED_RESULT_CACHE: Optional[Any] = None
_DELEGATED_QUALITY_TRACKER: Optional[Any] = None
_DELEGATED_PROMPT_COMPRESSOR: Optional[Any] = None
_DELEGATED_CONTEXT_PRUNER: Optional[Any] = None
_DISCLOSURE_TIER_SELECTOR: Optional[Any] = None
_DISCLOSURE_TIER_LOADER: Optional[Any] = None
_DISCLOSURE_RELEVANCE_PREDICTOR: Optional[Any] = None
_DISCLOSURE_NEGATIVE_FILTER: Optional[Any] = None

# ---------------------------------------------------------------------------
# Phase 20.2: Priority-based delegation with automatic failover
# ---------------------------------------------------------------------------
_TASK_TYPE_CAPABILITIES = {
    "coding": {
        "priority_profiles": ["local-tool-calling", "default", "remote-coding", "remote-gemini", "remote-free"],
        "required_context_window": 8192,
        "prefer_free_first": False,
    },
    "reasoning": {
        "priority_profiles": ["local-tool-calling", "default", "remote-reasoning", "remote-gemini", "remote-free"],
        "required_context_window": 8192,
        "prefer_free_first": False,
    },
    "tool-calling": {
        "priority_profiles": ["local-tool-calling", "default", "remote-tool-calling", "remote-gemini", "remote-free"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
    "simple": {
        "priority_profiles": ["default", "local-tool-calling", "remote-gemini", "remote-free"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
    "default": {
        "priority_profiles": ["default", "local-tool-calling", "remote-gemini", "remote-free"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
}


def init(
    *,
    agent_pool_manager: Any,
    delegated_quality_checker: Any,
    delegated_result_refiner: Any,
    delegated_result_cache: Any,
    delegated_quality_tracker: Any,
    delegated_prompt_compressor: Any,
    delegated_context_pruner: Any,
    disclosure_tier_selector: Any,
    disclosure_tier_loader: Any,
    disclosure_relevance_predictor: Any,
    disclosure_negative_filter: Any,
) -> None:
    global _AGENT_POOL_MANAGER
    global _DELEGATED_QUALITY_CHECKER, _DELEGATED_RESULT_REFINER, _DELEGATED_RESULT_CACHE
    global _DELEGATED_QUALITY_TRACKER, _DELEGATED_PROMPT_COMPRESSOR, _DELEGATED_CONTEXT_PRUNER
    global _DISCLOSURE_TIER_SELECTOR, _DISCLOSURE_TIER_LOADER
    global _DISCLOSURE_RELEVANCE_PREDICTOR, _DISCLOSURE_NEGATIVE_FILTER

    _AGENT_POOL_MANAGER = agent_pool_manager
    _DELEGATED_QUALITY_CHECKER = delegated_quality_checker
    _DELEGATED_RESULT_REFINER = delegated_result_refiner
    _DELEGATED_RESULT_CACHE = delegated_result_cache
    _DELEGATED_QUALITY_TRACKER = delegated_quality_tracker
    _DELEGATED_PROMPT_COMPRESSOR = delegated_prompt_compressor
    _DELEGATED_CONTEXT_PRUNER = delegated_context_pruner
    _DISCLOSURE_TIER_SELECTOR = disclosure_tier_selector
    _DISCLOSURE_TIER_LOADER = disclosure_tier_loader
    _DISCLOSURE_RELEVANCE_PREDICTOR = disclosure_relevance_predictor
    _DISCLOSURE_NEGATIVE_FILTER = disclosure_negative_filter


def _is_remote_profile(profile: str) -> bool:
    return str(profile or "").startswith("remote-")


def _remote_avail_cache_get(profile: str) -> Optional[bool]:
    entry = _REMOTE_AVAIL_CACHE.get(profile)
    if not entry:
        return None
    if time.time() - entry["ts"] > _REMOTE_AVAIL_TTL_S:
        return None
    return bool(entry["ok"])


def _remote_avail_cache_set(profile: str, ok: bool) -> None:
    _REMOTE_AVAIL_CACHE[profile] = {"ok": ok, "ts": time.time()}


def _apply_remote_runtime_status(
    runtime: Dict[str, Any],
    runtime_id: str,
    remote_aliases: Dict[str, Any],
    remote_configured: bool,
) -> Dict[str, Any]:
    if runtime_id == "openrouter-gemini":
        runtime["status"] = "ready" if remote_configured and remote_aliases.get("gemini") else "offline"
        runtime["model_alias"] = remote_aliases.get("gemini") or ""
    elif runtime_id == "openrouter-free":
        runtime["status"] = "ready" if remote_configured and remote_aliases.get("free") else "offline"
        runtime["model_alias"] = remote_aliases.get("free") or ""
    elif runtime_id == "openrouter-coding":
        runtime["status"] = "ready" if remote_configured and remote_aliases.get("coding") else "offline"
        runtime["model_alias"] = remote_aliases.get("coding") or ""
    elif runtime_id == "openrouter-reasoning":
        runtime["status"] = "ready" if remote_configured and remote_aliases.get("reasoning") else "offline"
        runtime["model_alias"] = remote_aliases.get("reasoning") or ""
    elif runtime_id == "openrouter-tool-calling":
        runtime["status"] = "ready" if remote_configured and remote_aliases.get("tool_calling") else "offline"
        runtime["model_alias"] = remote_aliases.get("tool_calling") or ""
    elif runtime_id == "local-tool-calling":
        runtime["status"] = "ready"
    return runtime


def _agent_pool_status_snapshot() -> Dict[str, Any]:
    stats = _AGENT_POOL_MANAGER.get_pool_stats()
    agents = []
    for agent in _AGENT_POOL_MANAGER.agents.values():
        agents.append(
            {
                "agent_id": agent.agent_id,
                "provider": agent.provider,
                "model_id": agent.model_id,
                "tier": agent.tier.value,
                "status": agent.status.value,
                "current_load": agent.current_load,
                "max_concurrent": agent.max_concurrent,
                "success_rate": round(agent.success_rate(), 4),
                "avg_latency_ms": round(agent.avg_latency_ms, 2),
                "avg_quality_score": round(agent.avg_quality_score, 4),
                "total_requests": agent.total_requests,
            }
        )
    agents.sort(
        key=lambda item: (
            item["status"] != "available",
            item["tier"] != "free",
            item["current_load"],
            item["agent_id"],
        )
    )
    return {
        "total_agents": stats.total_agents,
        "available_agents": stats.available_agents,
        "free_agents_available": stats.free_agents_available,
        "total_requests": stats.total_requests,
        "successful_requests": stats.successful_requests,
        "avg_latency_ms": round(stats.avg_latency_ms, 2),
        "agents": agents,
    }


def _remote_profile_uses_agent_pool(profile_name: str) -> bool:
    return str(profile_name or "").strip() == "remote-free"


def _select_agent_pool_candidate(
    profile_name: str,
    *,
    min_context_window: int = 0,
    allow_paid: bool = True,
    exclude_agent_id: str = "",
) -> Optional[Any]:
    if not _remote_profile_uses_agent_pool(profile_name):
        return None
    candidate = _AGENT_POOL_MANAGER.get_available_agent(
        prefer_free=True,
        min_context_window=max(0, int(min_context_window or 0)) or None,
    )
    if candidate and candidate.agent_id != exclude_agent_id:
        return candidate
    if exclude_agent_id:
        candidate = _AGENT_POOL_MANAGER.get_failover_agent(exclude_agent_id, allow_paid=allow_paid)
        if candidate:
            return candidate
    if allow_paid:
        for agent in _AGENT_POOL_MANAGER.agents.values():
            if agent.agent_id == exclude_agent_id:
                continue
            if getattr(agent.tier, "value", "") != "free" and agent.is_available():
                return agent
    return None


def _detect_task_type(task: str, profile: str = "") -> str:
    task_lower = (task or "").lower()
    if profile:
        profile_lower = profile.lower()
        if "coding" in profile_lower or "implement" in profile_lower:
            return "coding"
        if "reasoning" in profile_lower or "architecture" in profile_lower:
            return "reasoning"
        if "tool" in profile_lower:
            return "tool-calling"
        return "default"

    coding_keywords = ["implement", "code", "function", "class", "fix bug", "refactor", "patch", "script"]
    reasoning_keywords = ["architecture", "design", "review", "analyze", "tradeoff", "strategy", "plan"]
    tool_keywords = ["run", "execute", "command", "script", "deploy", "build", "test"]

    if any(kw in task_lower for kw in coding_keywords):
        return "coding"
    if any(kw in task_lower for kw in reasoning_keywords):
        return "reasoning"
    if any(kw in task_lower for kw in tool_keywords):
        return "tool-calling"
    if len(task_lower.split()) <= 10:
        return "simple"
    return "default"


def _build_delegation_fallback_chain(
    task: str,
    requested_profile: str = "",
    prefer_local: bool = False,
) -> List[Dict[str, Any]]:
    task_type = _detect_task_type(task, requested_profile)
    capabilities = _TASK_TYPE_CAPABILITIES.get(task_type, _TASK_TYPE_CAPABILITIES["default"])
    chain = []
    seen_profiles = set()

    for profile in capabilities["priority_profiles"]:
        if profile in seen_profiles:
            continue
        seen_profiles.add(profile)
        is_local = "local" in profile.lower()
        try:
            from ai_coordinator import _profile_to_runtime_id  # type: ignore

            runtime_id = _profile_to_runtime_id(profile)
        except Exception:
            runtime_map = {
                "remote-gemini": "openrouter-gemini",
                "remote-free": "openrouter-free",
                "remote-coding": "openrouter-coding",
                "remote-reasoning": "openrouter-reasoning",
                "remote-tool-calling": "openrouter-tool-calling",
                "local-tool-calling": "local-tool-calling",
                "default": "local-hybrid",
            }
            runtime_id = runtime_map.get(profile, "local-hybrid")

        chain.append(
            {
                "profile": profile,
                "runtime_id": runtime_id,
                "reason": f"{task_type} task: {profile} (priority {len(chain) + 1})",
                "is_local": is_local,
                "context_window": capabilities["required_context_window"],
            }
        )

    if prefer_local and not any(candidate["is_local"] for candidate in chain):
        chain.append(
            {
                "profile": "default",
                "runtime_id": "local-hybrid",
                "reason": "prefer_local flag: local fallback",
                "is_local": True,
                "context_window": 4096,
            }
        )

    return chain


def _check_runtime_available(runtime_id: str) -> bool:
    try:
        from switchboard_state import get_switchboard_state  # type: ignore

        state = get_switchboard_state()
        runtime_status = state.get_runtime_status(runtime_id)
        return runtime_status in ("ready", "degraded")
    except Exception:
        return True


def _check_agent_available_for_profile(profile: str) -> bool:
    if not _remote_profile_uses_agent_pool(profile):
        return True
    for agent in _AGENT_POOL_MANAGER.agents.values():
        if agent.is_available() and not agent.is_rate_limited():
            return True
    return False


def _select_next_available_delegation_target(
    fallback_chain: List[Dict[str, Any]],
    exclude_profiles: Optional[Set[str]] = None,
    exclude_agent_id: str = "",
) -> Optional[Dict[str, Any]]:
    exclude = exclude_profiles or set()
    for target in fallback_chain:
        profile = target["profile"]
        runtime_id = target["runtime_id"]
        if profile in exclude:
            continue
        if not _check_runtime_available(runtime_id):
            logger.info("delegation_failover: runtime %s unavailable, skipping", runtime_id)
            continue
        if not _check_agent_available_for_profile(profile):
            logger.info("delegation_failover: no agents available for %s, skipping", profile)
            continue
        if exclude_agent_id and _remote_profile_uses_agent_pool(profile):
            candidate = _select_agent_pool_candidate(
                profile,
                min_context_window=int(target.get("context_window", 0) or 0),
                exclude_agent_id=exclude_agent_id,
            )
            if not candidate:
                continue
        return target
    return None


def _delegated_quality_status_snapshot() -> Dict[str, Any]:
    tracked_agents = []
    for agent_id in sorted(_DELEGATED_QUALITY_TRACKER.agent_quality.keys()):
        trend = _DELEGATED_QUALITY_TRACKER.get_trend(agent_id, window_hours=24)
        tracked_agents.append(
            {
                "agent_id": agent_id,
                "sample_count": int(trend.get("sample_count", 0) or 0),
                "avg_quality": round(float(trend.get("avg_quality", 0.0) or 0.0), 4),
                "trend": str(trend.get("trend", trend.get("status", "unknown")) or "unknown"),
            }
        )
    return {
        "threshold": _DELEGATED_QUALITY_CHECKER.threshold.name.lower(),
        "cache_entries": len(_DELEGATED_RESULT_CACHE.cache),
        "tracked_agents": tracked_agents,
    }


def _extract_delegated_response_text(body: Any) -> str:
    if isinstance(body, str):
        return body.strip()
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            parts.append(text.strip())
                return "\n".join(parts).strip()
        text = choices[0].get("text") if isinstance(choices[0], dict) else ""
        if isinstance(text, str):
            return text.strip()
    content = body.get("content")
    if isinstance(content, str):
        return content.strip()
    response = body.get("response")
    if isinstance(response, str):
        return response.strip()
    return ""


def _inject_delegated_response_text(body: Any, text: str) -> Any:
    if isinstance(body, str):
        return text
    if not isinstance(body, dict):
        return body
    payload = dict(body)
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        updated_choices = list(choices)
        first = dict(updated_choices[0])
        message = first.get("message")
        if isinstance(message, dict):
            updated_message = dict(message)
            if isinstance(updated_message.get("content"), list):
                updated_message["content"] = [{"type": "text", "text": text}]
            else:
                updated_message["content"] = text
            first["message"] = updated_message
        else:
            first["text"] = text
        updated_choices[0] = first
        payload["choices"] = updated_choices
        return payload
    payload["content"] = text
    return payload


async def _assess_delegated_response_quality(
    task: str,
    body: Any,
    *,
    agent_id: str,
) -> Dict[str, Any]:
    response_text = _extract_delegated_response_text(body)
    if not response_text:
        return {"available": False}

    quality_check = _DELEGATED_QUALITY_CHECKER.check_quality(task, response_text)
    selected_text = response_text
    refined_response = ""
    cached_fallback_used = False

    if quality_check.refinement_needed:
        refinement = await _DELEGATED_RESULT_REFINER.refine(task, response_text, quality_check.score)
        refined_check = _DELEGATED_QUALITY_CHECKER.check_quality(task, refinement.refined_response)
        if refined_check.score.overall >= quality_check.score.overall:
            selected_text = refinement.refined_response
            refined_response = refinement.refined_response
            quality_check = refined_check

    if not quality_check.passed:
        cached = _DELEGATED_RESULT_CACHE.get(task)
        if cached:
            cached_text, _cached_quality = cached
            cached_check = _DELEGATED_QUALITY_CHECKER.check_quality(task, cached_text)
            if cached_check.score.overall >= quality_check.score.overall:
                selected_text = cached_text
                cached_fallback_used = True
                quality_check = cached_check

    if quality_check.passed:
        _DELEGATED_RESULT_CACHE.set(task, selected_text, quality_check.score)
    _DELEGATED_QUALITY_TRACKER.record_quality(agent_id, quality_check.score.overall)

    return {
        "available": True,
        "passed": quality_check.passed,
        "refinement_applied": bool(refined_response),
        "cached_fallback_used": cached_fallback_used,
        "fallback_recommended": quality_check.fallback_recommended,
        "quality_score": round(quality_check.score.overall, 4),
        "issues": quality_check.score.issues[:5],
        "suggestions": quality_check.score.suggestions[:5],
        "response_text": selected_text,
    }


def _message_content_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts)
    return ""


def _content_has_only_text_blocks(content: Any) -> bool:
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    return all(
        isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
        for item in content
    )


def _message_content_can_be_rewritten(message: Dict[str, Any]) -> bool:
    role = str(message.get("role", "")).strip()
    return role in {"system", "user"} and _content_has_only_text_blocks(message.get("content"))


def _build_text_message(role: str, text: str) -> Dict[str, Any]:
    return {"role": role, "content": text}


def _replace_message_content(message: Dict[str, Any], text: str) -> Dict[str, Any]:
    if not _message_content_can_be_rewritten(message):
        return dict(message)
    updated = dict(message)
    if isinstance(updated.get("content"), list):
        updated["content"] = [{"type": "text", "text": text}]
    else:
        updated["content"] = text
    return updated


def _estimate_message_tokens(messages: List[Dict[str, Any]]) -> int:
    return sum(_DELEGATED_PROMPT_COMPRESSOR._estimate_tokens(_message_content_text(message)) for message in messages)


def _infer_progressive_context_category(task: str, context: Optional[Dict[str, Any]] = None) -> str:
    text = " ".join(
        part
        for part in [
            str(task or "").lower(),
            json.dumps(context, sort_keys=True).lower() if isinstance(context, dict) and context else "",
        ]
        if part
    )
    category_rules = [
        ("security", {"security", "auth", "token", "secret", "tls", "audit"}),
        ("deployment", {"deploy", "deployment", "service", "nixos", "systemd", "restart"}),
        ("troubleshooting", {"error", "debug", "issue", "problem", "failure", "regression"}),
        ("api", {"api", "endpoint", "route", "http", "json", "request"}),
    ]
    for category, keywords in category_rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "architecture"


def _ensure_system_message(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if messages and str(messages[0].get("role", "")).strip() == "system":
        return [dict(message) for message in messages]
    return [{"role": "system", "content": "Use the supplied context conservatively and prefer direct evidence."}, *[dict(message) for message in messages]]


async def _apply_progressive_context(
    task: str,
    messages: List[Dict[str, Any]],
    *,
    context: Optional[Dict[str, Any]] = None,
    profile_name: str = "",
    context_budget: int = 0,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not messages:
        return messages, {"applied": False}

    category = _infer_progressive_context_category(task, context)
    budget = max(200, int(context_budget or 0) or 0)
    tier_decision = _DISCLOSURE_TIER_SELECTOR.select_tier(task, context_budget=budget)
    load_result = await _DISCLOSURE_TIER_LOADER.load_context(task, category, tier_decision.selected_tier)
    if not load_result.chunks_loaded:
        return messages, {"applied": False, "category": category, "tier": tier_decision.selected_tier.name.lower()}

    scored_contexts = _DISCLOSURE_RELEVANCE_PREDICTOR.predict_batch(
        task,
        {chunk.chunk_id: chunk.content for chunk in load_result.chunks_loaded},
    )
    filtered_contexts = _DISCLOSURE_NEGATIVE_FILTER.filter(scored_contexts)
    selected_contexts = (filtered_contexts or scored_contexts)[: min(3, len(filtered_contexts or scored_contexts))]
    if not selected_contexts:
        return messages, {"applied": False, "category": category, "tier": tier_decision.selected_tier.name.lower()}

    graph = ContextDependencyGraph()
    previous_id = ""
    for rank, score in enumerate(selected_contexts):
        matching = next((chunk for chunk in load_result.chunks_loaded if chunk.chunk_id == score.context_id), None)
        if not matching:
            continue
        graph.add_node(
            ContextNode(
                node_id=matching.chunk_id,
                content=matching.content,
                tokens=matching.tokens,
                load_priority=max(1, 10 - rank),
                metadata={"tier": matching.tier.name.lower(), "category": matching.category},
            )
        )
        if previous_id:
            graph.add_dependency(matching.chunk_id, previous_id)
        previous_id = matching.chunk_id

    lazy_loader = LazyContextLoader(graph)
    loaded_context = await lazy_loader.load([score.context_id for score in selected_contexts], max_concurrent=3)
    ordered_loaded = [loaded_context.get(score.context_id, "").strip() for score in selected_contexts if loaded_context.get(score.context_id)]
    ordered_loaded = [item for item in ordered_loaded if item]
    if not ordered_loaded:
        return messages, {"applied": False, "category": category, "tier": tier_decision.selected_tier.name.lower()}

    injection = "\n".join(f"- {item}" for item in ordered_loaded)
    updated_messages = _ensure_system_message(messages)
    system_text = _message_content_text(updated_messages[0]).strip()
    progressive_prefix = (
        f"{system_text}\n\n"
        f"Progressive context [{category}/{tier_decision.selected_tier.name.lower()}]:\n"
        f"{injection}"
    ).strip()
    if _message_content_can_be_rewritten(updated_messages[0]):
        updated_messages[0] = _replace_message_content(updated_messages[0], progressive_prefix)
    else:
        updated_messages.insert(0, _build_text_message("system", progressive_prefix))

    return updated_messages, {
        "applied": True,
        "category": category,
        "tier": tier_decision.selected_tier.name.lower(),
        "confidence": round(float(tier_decision.confidence), 4),
        "reasoning": tier_decision.reasoning,
        "loaded_chunks": [score.context_id for score in selected_contexts],
        "loaded_chunk_count": len(ordered_loaded),
        "loaded_tokens": int(sum(chunk.tokens for chunk in load_result.chunks_loaded)),
        "filtered_candidates": max(0, len(scored_contexts) - len(filtered_contexts)),
        "profile": str(profile_name or "").strip(),
    }


def _optimize_delegated_messages(
    messages: List[Dict[str, Any]],
    profile_name: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not messages:
        return messages, {"applied": False}

    optimized = [dict(message) for message in messages]
    original_tokens = _estimate_message_tokens(optimized)
    token_budget = 900 if str(profile_name or "").strip() in {"remote-gemini", "remote-free"} else 1200
    compressed_messages = 0
    protected_indexes = {
        idx
        for idx, message in enumerate(optimized)
        if str(message.get("role", "")).strip() == "assistant" or not _message_content_can_be_rewritten(message)
    }

    for idx, message in enumerate(list(optimized)):
        if idx in protected_indexes:
            continue
        text = _message_content_text(message).strip()
        if len(text) < 160:
            continue
        strategy = (
            CompressionStrategy.ABBREVIATE
            if str(message.get("role", "")).strip() == "system"
            else CompressionStrategy.REMOVE_STOPWORDS
        )
        compressed = _DELEGATED_PROMPT_COMPRESSOR.compress(text, strategy=strategy)
        if compressed.compressed_tokens < compressed.original_tokens:
            optimized[idx] = _replace_message_content(message, compressed.compressed_text)
            compressed_messages += 1

    compressed_tokens = _estimate_message_tokens(optimized)
    pruned_messages = 0
    if compressed_tokens > token_budget and len(optimized) > 2:
        anchor_text = ""
        for message in reversed(optimized):
            if str(message.get("role", "")).strip() == "user":
                anchor_text = _message_content_text(message).strip()
                if anchor_text:
                    break
        fixed_indexes = {0, len(optimized) - 1, *protected_indexes}
        fixed_tokens = sum(
            _DELEGATED_PROMPT_COMPRESSOR._estimate_tokens(_message_content_text(optimized[idx]))
            for idx in fixed_indexes
            if 0 <= idx < len(optimized)
        )
        candidate_chunks: List[ContextChunk] = []
        for idx, message in enumerate(optimized):
            if idx in fixed_indexes:
                continue
            text = _message_content_text(message).strip()
            if not text:
                continue
            candidate_chunks.append(
                ContextChunk(
                    chunk_id=str(idx),
                    content=text,
                    tokens=max(1, _DELEGATED_PROMPT_COMPRESSOR._estimate_tokens(text)),
                    source=str(message.get("role", "message") or "message"),
                )
            )
        keep_budget = max(1, token_budget - fixed_tokens)
        kept_chunks, pruned_chunks = _DELEGATED_CONTEXT_PRUNER.prune(candidate_chunks, keep_budget, query=anchor_text or None)
        keep_ids = {chunk.chunk_id for chunk in kept_chunks}
        optimized = [
            message
            for idx, message in enumerate(optimized)
            if idx in fixed_indexes or str(idx) in keep_ids
        ]
        pruned_messages = len(pruned_chunks)

    final_tokens = _estimate_message_tokens(optimized)
    return optimized, {
        "applied": compressed_messages > 0 or pruned_messages > 0,
        "original_tokens": original_tokens,
        "compressed_tokens": final_tokens,
        "token_budget": token_budget,
        "compressed_messages": compressed_messages,
        "pruned_messages": pruned_messages,
    }
