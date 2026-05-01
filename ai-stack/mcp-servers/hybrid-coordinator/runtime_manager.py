"""
Runtime registry, policy loading, and service lifecycle utilities.

Extracted from http_server.py (Phase 12.4 decomposition).

Provides file-backed runtime records, safety/isolation/scheduler policy
loaders, provider fallback policy, and the execute_runtime_service_action
helper for systemctl interactions.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_coordinator import (
    prune_runtime_registry as _ai_coordinator_prune_runtime_registry,
    coerce_orchestration_context as _ai_coordinator_coerce_orchestration_context,
    route_by_complexity as _ai_coordinator_route_by_complexity,
)
from config import Config

logger = logging.getLogger("hybrid-coordinator")

# Shared lock for runtime registry file I/O
_runtime_registry_lock = asyncio.Lock()

def _runtime_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-runtimes.json"


# Phase 12.4: agent registry + intent contract utilities extracted
from agent_registry import (
    _agent_lessons_lock,
    _agent_evaluations_lock,
    _INTENT_DEPTH_EXPECTATIONS,
    _agent_lessons_registry_path,
    _agent_evaluations_registry_path,
    _workflow_blueprints_path,
    _hint_feedback_log_path,
    _default_agent_lessons_registry,
    _default_agent_evaluations_registry,
    _normalize_agent_role,
    _default_agent_evaluation_row,
    _normalize_agent_lessons_registry,
    _normalize_agent_evaluations_registry,
    _load_agent_evaluations_registry_sync,
    _load_agent_evaluations_registry,
    _save_agent_evaluations_registry,
    _record_agent_review_event,
    _record_agent_consensus_event,
    _runtime_event_score,
    _record_agent_runtime_event,
    _active_lesson_refs,
    _load_active_lesson_refs,
    _normalize_review_type,
    _normalize_artifact_kind,
    _normalize_task_class,
    _load_agent_lessons_registry,
    _save_agent_lessons_registry,
    _normalize_string_list,
    _normalize_orchestration_lane_list,
    _validate_intent_contract,
    _default_intent_contract,
    _coerce_intent_contract,
)
def _coerce_orchestration_context(incoming: Any) -> Dict[str, Any]:
    data = incoming if isinstance(incoming, dict) else {}
    normalized = dict(data)
    if "requesting_agent" not in normalized:
        normalized["requesting_agent"] = data.get("agent") or data.get("agent_type") or "human"
    if "requester_role" not in normalized:
        normalized["requester_role"] = data.get("role") or "orchestrator"
    return _ai_coordinator_coerce_orchestration_context(normalized)


def _orchestration_prefers_local_handoff(query: str) -> bool:
    normalized = str(query or "").strip().lower()
    if not normalized:
        return False
    tokens = (
        "embedded",
        "embedding",
        "local tool",
        "local tools",
        "local model",
        "local models",
        "continue-local",
        "handoff to local",
    )
    return any(token in normalized for token in tokens)


def _default_orchestration_policy_for_query(query: str) -> Dict[str, Any]:
    base = {
        "primary_lane": "implementation",
        "reviewer_lane": "codex-review",
        "escalation_lane": "remote-reasoning",
        "collaborator_lanes": [],
        "consensus_mode": "reviewer-gate",
        "selection_strategy": "orchestrator-first",
        "allow_parallel_subagents": False,
        "max_parallel_subagents": 1,
    }
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return base

    routing = _ai_coordinator_route_by_complexity(normalized_query, "", False)
    profile = str(routing.get("recommended_profile", "") or "").strip().lower()
    task_archetype = str(routing.get("task_archetype", "general") or "general").strip().lower()
    local_handoff = _orchestration_prefers_local_handoff(normalized_query)

    if profile == "remote-gemini" or task_archetype in {"planning", "retrieval"}:
        base.update(
            {
                "primary_lane": "research",
                "escalation_lane": "none",
                "selection_strategy": "evidence-first",
                "allow_parallel_subagents": True,
                "max_parallel_subagents": 2,
                "collaborator_lanes": ["diagnostics" if local_handoff else "implementation"],
            }
        )
    elif profile == "remote-reasoning" or task_archetype == "architecture-review":
        base.update(
            {
                "primary_lane": "reasoning",
                "selection_strategy": "escalate-on-complexity",
                "allow_parallel_subagents": True,
                "max_parallel_subagents": 2,
                "collaborator_lanes": ["research"],
            }
        )
    elif profile == "local-tool-calling" or task_archetype == "tool-calling":
        base.update(
            {
                "primary_lane": "diagnostics",
                "selection_strategy": "local-first",
                "allow_parallel_subagents": True,
                "max_parallel_subagents": 2,
                "collaborator_lanes": ["implementation"],
            }
        )
    elif local_handoff:
        base.update(
            {
                "selection_strategy": "evidence-first",
                "allow_parallel_subagents": True,
                "max_parallel_subagents": 2,
                "collaborator_lanes": ["diagnostics"],
            }
        )

    return base


def _validate_orchestration_policy(policy: Any, query: str = "") -> Dict[str, Any]:
    base = {
        "ok": True,
        "errors": [],
        "normalized": _default_orchestration_policy_for_query(query),
    }
    if policy is None:
        return base
    if not isinstance(policy, dict):
        base["ok"] = False
        base["errors"].append("orchestration_policy must be an object")
        return base

    normalized = dict(base["normalized"])
    for key in ("primary_lane", "reviewer_lane", "escalation_lane", "consensus_mode", "selection_strategy"):
        normalized[key] = str(policy.get(key, normalized[key]) or normalized[key]).strip().lower()
    normalized["collaborator_lanes"] = _normalize_orchestration_lane_list(policy.get("collaborator_lanes", []))
    normalized["allow_parallel_subagents"] = bool(policy.get("allow_parallel_subagents", False))
    try:
        normalized["max_parallel_subagents"] = max(1, int(policy.get("max_parallel_subagents", 1) or 1))
    except (TypeError, ValueError):
        normalized["max_parallel_subagents"] = 1
        base["ok"] = False
        base["errors"].append("orchestration_policy.max_parallel_subagents must be an integer >= 1")

    if normalized["primary_lane"] not in _ORCHESTRATION_LANES:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.primary_lane must be one of: " + ", ".join(sorted(_ORCHESTRATION_LANES))
        )
    if normalized["reviewer_lane"] not in _ORCHESTRATION_REVIEW_LANES:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.reviewer_lane must be one of: " + ", ".join(sorted(_ORCHESTRATION_REVIEW_LANES))
        )
    if normalized["escalation_lane"] not in _ORCHESTRATION_ESCALATION_LANES:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.escalation_lane must be one of: " + ", ".join(sorted(_ORCHESTRATION_ESCALATION_LANES))
        )
    invalid_collaborator_lanes = [
        lane for lane in normalized["collaborator_lanes"] if lane not in _ORCHESTRATION_COLLABORATOR_LANES
    ]
    if invalid_collaborator_lanes:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.collaborator_lanes must be drawn from: "
            + ", ".join(sorted(_ORCHESTRATION_COLLABORATOR_LANES))
        )
    if normalized["consensus_mode"] not in _ORCHESTRATION_CONSENSUS_MODES:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.consensus_mode must be one of: " + ", ".join(sorted(_ORCHESTRATION_CONSENSUS_MODES))
        )
    if normalized["selection_strategy"] not in _ORCHESTRATION_SELECTION_STRATEGIES:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.selection_strategy must be one of: "
            + ", ".join(sorted(_ORCHESTRATION_SELECTION_STRATEGIES))
        )
    if not normalized["allow_parallel_subagents"]:
        normalized["max_parallel_subagents"] = 1
        normalized["collaborator_lanes"] = []
    elif not normalized["collaborator_lanes"] and normalized["max_parallel_subagents"] > 1:
        base["ok"] = False
        base["errors"].append(
            "orchestration_policy.collaborator_lanes must contain at least one lane when parallel subagents are enabled"
        )
    base["normalized"] = normalized
    return base


def _load_and_validate_workflow_blueprints() -> Dict[str, Any]:
    """Load blueprint file and validate intent contract schema for each item."""
    path = _workflow_blueprints_path()
    base = {
        "source": str(path),
        "blueprints": [],
        "blueprint_by_id": {},
        "errors": [],
    }
    if not path.exists():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        base["errors"].append(f"failed to parse blueprints JSON: {exc}")
        return base

    items = raw.get("blueprints", []) if isinstance(raw, dict) else []
    if not isinstance(items, list):
        base["errors"].append("blueprints must be a list")
        return base

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            base["errors"].append(f"blueprints[{idx}] must be an object")
            continue
        blueprint_id = str(item.get("id", "") or "").strip()
        if not blueprint_id:
            base["errors"].append(f"blueprints[{idx}] missing id")
            continue
        intent_validation = _validate_intent_contract(item.get("intent_contract", {}))
        if not intent_validation["ok"]:
            joined = "; ".join(intent_validation["errors"])
            base["errors"].append(f"blueprint '{blueprint_id}' invalid intent_contract: {joined}")
        policy_validation = _validate_orchestration_policy(
            item.get("orchestration_policy"),
            str(item.get("title") or item.get("objective") or item.get("description") or blueprint_id),
        )
        if not policy_validation["ok"]:
            joined = "; ".join(policy_validation["errors"])
            base["errors"].append(f"blueprint '{blueprint_id}' invalid orchestration_policy: {joined}")

        normalized = dict(item)
        normalized["intent_contract"] = intent_validation["normalized"]
        normalized["intent_contract_valid"] = bool(intent_validation["ok"])
        normalized["intent_contract_errors"] = intent_validation["errors"]
        normalized["orchestration_policy"] = policy_validation["normalized"]
        normalized["orchestration_policy_valid"] = bool(policy_validation["ok"])
        normalized["orchestration_policy_errors"] = policy_validation["errors"]
        base["blueprints"].append(normalized)
        base["blueprint_by_id"][blueprint_id] = normalized
    return base


def _runtime_safety_policy_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("RUNTIME_SAFETY_POLICY_FILE", "config/runtime-safety-policy.json")
        )
    )


def _runtime_isolation_profiles_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("RUNTIME_ISOLATION_PROFILES_FILE", "config/runtime-isolation-profiles.json")
        )
    )


def _parity_scorecard_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("PARITY_SCORECARD_FILE", "config/parity-scorecard.json")
        )
    )


def _runtime_scheduler_policy_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("RUNTIME_SCHEDULER_POLICY_FILE", "config/runtime-scheduler-policy.json")
        )
    )


def _default_runtime_safety_policy() -> Dict[str, Any]:
    return {
        "modes": {
            "plan-readonly": {
                "allowed_risk_classes": ["safe"],
                "requires_approval": ["review-required"],
                "blocked": ["blocked"],
            },
            "execute-mutating": {
                "allowed_risk_classes": ["safe"],
                "requires_approval": ["review-required"],
                "blocked": ["blocked"],
            },
        }
    }


def _load_runtime_safety_policy() -> Dict[str, Any]:
    path = _runtime_safety_policy_path()
    if not path.exists():
        return _default_runtime_safety_policy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("modes"), dict):
            return data
    except Exception:
        pass
    return _default_runtime_safety_policy()


def _default_runtime_isolation_profiles() -> Dict[str, Any]:
    return {
        "default_profile_by_mode": {
            "plan-readonly": "readonly-strict",
            "execute-mutating": "execute-guarded",
        },
        "profiles": {
            "readonly-strict": {
                "workspace_root": "/tmp/agent-runs",
                "allow_workspace_write": False,
                "allowed_processes": ["rg", "cat", "ls", "jq", "sed"],
                "network_policy": "none",
            },
            "execute-guarded": {
                "workspace_root": "/tmp/agent-runs",
                "allow_workspace_write": True,
                "allowed_processes": ["rg", "cat", "ls", "jq", "sed", "bash", "python3", "node", "git"],
                "network_policy": "loopback",
            },
        },
    }


def _load_runtime_isolation_profiles() -> Dict[str, Any]:
    path = _runtime_isolation_profiles_path()
    if not path.exists():
        return _default_runtime_isolation_profiles()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
            return data
    except Exception:
        pass
    return _default_runtime_isolation_profiles()


def _default_runtime_scheduler_policy() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "selection": {
            "max_candidates": 5,
            "allowed_statuses": ["ready", "degraded"],
            "require_all_tags": False,
            "freshness_window_seconds": 3600,
            "weights": {
                "status": 0.45,
                "runtime_class": 0.2,
                "transport": 0.15,
                "tag_overlap": 0.1,
                "freshness": 0.1,
            },
        },
        "status_weights": {
            "ready": 1.0,
            "degraded": 0.5,
            "draining": 0.1,
            "offline": 0.0,
        },
    }


def _load_runtime_scheduler_policy() -> Dict[str, Any]:
    path = _runtime_scheduler_policy_path()
    if not path.exists():
        return _default_runtime_scheduler_policy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("selection"), dict):
            return data
    except Exception:
        pass
    return _default_runtime_scheduler_policy()


def _provider_fallback_policy_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("PROVIDER_FALLBACK_POLICY_FILE", "config/provider-fallback-policy.json")
        )
    )


def _default_provider_fallback_policy() -> Dict[str, Any]:
    return {
        "version": 1,
        "fallback_triggers": {
            "rate_limited": {"enabled": True, "http_codes": [429], "cooldown_seconds": 300},
            "provider_error": {"enabled": True, "http_codes": [500, 502, 503, 504], "cooldown_seconds": 60},
        },
        "provider_health": {
            "tracking_enabled": True,
            "window_seconds": 3600,
            "degraded_threshold_pct": 20,
            "unhealthy_threshold_pct": 50,
        },
        "selection_scoring": {
            "weights": {"health_score": 0.35, "latency_score": 0.20, "cost_score": 0.20, "success_rate": 0.15, "capability_match": 0.10}
        },
        "cost_aware_routing": {"enabled": True, "budget_tracking": False},
    }


def _load_provider_fallback_policy() -> Dict[str, Any]:
    path = _provider_fallback_policy_path()
    if not path.exists():
        return _default_provider_fallback_policy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("fallback_triggers"), dict):
            return data
    except Exception:
        pass
    return _default_provider_fallback_policy()


def _provider_health_summary() -> Dict[str, Any]:
    """Summarize provider health status based on recent fallback/error rates."""
    policy = _load_provider_fallback_policy()
    health_config = policy.get("provider_health", {})
    cost_config = policy.get("cost_aware_routing", {})
    selection_config = policy.get("selection_scoring", {})

    return {
        "available": True,
        "tracking_enabled": health_config.get("tracking_enabled", True),
        "window_seconds": health_config.get("window_seconds", 3600),
        "thresholds": {
            "degraded_pct": health_config.get("degraded_threshold_pct", 20),
            "unhealthy_pct": health_config.get("unhealthy_threshold_pct", 50),
        },
        "cost_aware_routing": {
            "enabled": cost_config.get("enabled", True),
            "budget_tracking": cost_config.get("budget_tracking", False),
        },
        "selection_weights": selection_config.get("weights", {}),
    }


def _get_domain_disclosure_summary() -> Dict[str, Any]:
    """Summarize available progressive disclosure domains (Phase 12.3)."""
    try:
        from progressive_disclosure import get_domain_loader
        loader = get_domain_loader()
        domains = loader.list_domains()
        return {
            "available": True,
            "domain_count": len(domains),
            "domains": [{"id": d["id"], "name": d["name"]} for d in domains],
            "levels": ["minimal", "standard", "full"],
            "config_path": str(loader._config_path),
        }
    except Exception as e:
        return {
            "available": False,
            "reason": str(e),
        }


def _normalize_tags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    tags: List[str] = []
    seen = set()
    for raw in value:
        tag = str(raw).strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _runtime_schedule_score(
    runtime: Dict[str, Any],
    requirements: Dict[str, Any],
    policy: Dict[str, Any],
    now: int,
) -> Dict[str, Any]:
    selection = policy.get("selection", {}) if isinstance(policy, dict) else {}
    weights = selection.get("weights", {}) if isinstance(selection, dict) else {}
    status_weights = policy.get("status_weights", {}) if isinstance(policy, dict) else {}

    runtime_status = str(runtime.get("status", "unknown")).strip().lower()
    runtime_class = str(runtime.get("runtime_class", "")).strip().lower()
    runtime_transport = str(runtime.get("transport", "")).strip().lower()
    runtime_tags = _normalize_tags(runtime.get("tags", []))

    req_class = str(requirements.get("runtime_class", "")).strip().lower()
    req_transport = str(requirements.get("transport", "")).strip().lower()
    req_tags = _normalize_tags(requirements.get("tags", []))

    updated_at = int(runtime.get("updated_at") or 0)
    freshness_window = max(1, int(selection.get("freshness_window_seconds", 3600)))

    status_score = float(status_weights.get(runtime_status, 0.0))
    class_score = 1.0 if req_class and runtime_class == req_class else (0.5 if not req_class else 0.0)
    transport_score = 1.0 if req_transport and runtime_transport == req_transport else (0.5 if not req_transport else 0.0)
    if req_tags:
        overlap = len(set(req_tags) & set(runtime_tags))
        tag_score = overlap / max(1, len(req_tags))
    else:
        tag_score = 0.5
    age_s = max(0, now - updated_at) if updated_at > 0 else freshness_window * 4
    freshness_score = max(0.0, min(1.0, 1.0 - (age_s / float(freshness_window))))

    total = (
        float(weights.get("status", 0.45)) * status_score
        + float(weights.get("runtime_class", 0.2)) * class_score
        + float(weights.get("transport", 0.15)) * transport_score
        + float(weights.get("tag_overlap", 0.1)) * tag_score
        + float(weights.get("freshness", 0.1)) * freshness_score
    )
    return {
        "score": round(total, 6),
        "components": {
            "status": round(status_score, 4),
            "runtime_class": round(class_score, 4),
            "transport": round(transport_score, 4),
            "tag_overlap": round(tag_score, 4),
            "freshness": round(freshness_score, 4),
        },
    }


async def _load_runtime_registry() -> Dict[str, Any]:
    path = _runtime_registry_path()
    if not path.exists():
        return _ai_coordinator_prune_runtime_registry({"runtimes": {}})
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("runtimes"), dict):
            pruned = _ai_coordinator_prune_runtime_registry(data)
            if pruned != data:
                await _save_runtime_registry(pruned)
            return pruned
    except Exception:
        pass
    return _ai_coordinator_prune_runtime_registry({"runtimes": {}})


async def _save_runtime_registry(data: Dict[str, Any]) -> None:
    path = _runtime_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _runtime_service_metadata(runtime_id: str) -> Dict[str, str]:
    normalized = str(runtime_id or "").strip().lower()
    switchboard_runtimes = {
        "local-tool-calling",
        "openrouter-gemini",
        "openrouter-free",
        "openrouter-coding",
        "openrouter-reasoning",
        "openrouter-tool-calling",
    }
    if normalized in switchboard_runtimes:
        return {
            "service_unit": "ai-switchboard.service",
            "healthcheck_url": f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
        }
    return {}


def _enrich_runtime_record(record: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(record)
    metadata = _runtime_service_metadata(str(enriched.get("runtime_id", "")))
    for key, value in metadata.items():
        if value and not str(enriched.get(key, "") or "").strip():
            enriched[key] = value
    return enriched


_RUNTIME_EXECUTION_ALLOWLIST = {
    "ai-switchboard.service": {
        "healthcheck_url": f"{Config.SWITCHBOARD_URL.rstrip('/')}/health",
    },
}


async def _execute_runtime_service_action(
    runtime: Dict[str, Any],
    *,
    action: str,
) -> tuple[Dict[str, Any], int]:
    service_unit = str(runtime.get("service_unit", "") or "").strip()
    runtime_id = str(runtime.get("runtime_id", "") or "").strip()
    if not service_unit:
        return {
            "status": "not_supported",
            "runtime_id": runtime_id,
            "action": action,
            "reason": "runtime has no executable service_unit",
        }, 409
    if service_unit not in _RUNTIME_EXECUTION_ALLOWLIST:
        return {
            "status": "not_allowed",
            "runtime_id": runtime_id,
            "action": action,
            "service_unit": service_unit,
            "reason": "service_unit not in execution allowlist",
        }, 403

    started = time.time()
    proc = await asyncio.create_subprocess_exec(
        "systemctl",
        "is-active",
        service_unit,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    duration = round(time.time() - started, 2)
    if proc.returncode != 0:
        return {
            "status": "failed",
            "runtime_id": runtime_id,
            "action": action,
            "service_unit": service_unit,
            "duration_seconds": duration,
            "service_state": stdout.decode("utf-8", errors="replace").strip()[:120],
            "error": stderr.decode("utf-8", errors="replace")[:500],
        }, 500

    healthcheck_url = str(
        runtime.get("healthcheck_url")
        or _RUNTIME_EXECUTION_ALLOWLIST.get(service_unit, {}).get("healthcheck_url")
        or ""
    ).strip()
    health_result: Dict[str, Any] = {"checked": False}
    if healthcheck_url:
        health_result["checked"] = True
        health_result["url"] = healthcheck_url
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(healthcheck_url)
            health_result["status_code"] = response.status_code
            health_result["ok"] = response.status_code < 400
            health_result["body_preview"] = response.text[:300]
        except Exception as exc:
            health_result["ok"] = False
            health_result["error"] = str(exc)
    else:
        health_result["ok"] = True

    payload = {
        "status": "verified" if health_result.get("ok") else "degraded",
        "runtime_id": runtime_id,
        "action": action,
        "mode": "verify-service-and-health",
        "service_unit": service_unit,
        "service_state": stdout.decode("utf-8", errors="replace").strip()[:120] or "active",
        "duration_seconds": duration,
        "healthcheck": health_result,
    }
    return payload, 200 if health_result.get("ok") else 502


