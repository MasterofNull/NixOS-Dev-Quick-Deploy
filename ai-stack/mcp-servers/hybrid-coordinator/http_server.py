"""
HTTP server module for the hybrid-coordinator.

Provides run_http_mode(): creates the aiohttp web application with all route
handlers, registers routes, and runs the server.

Extracted from server.py main() (Phase 6.1 decomposition).

Usage:
    import http_server
    http_server.init(
        augment_query_fn=augment_query_with_context,
        route_search_fn=route_search,
        ...
    )
    await http_server.run_http_mode(port=port, access_log_format=..., ...)
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from aiohttp import web
import httpx
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import Config, OptimizationProposal, apply_proposal, routing_config
from metrics import PROCESS_MEMORY_BYTES, REQUEST_COUNT, REQUEST_ERRORS, REQUEST_LATENCY
from shared.tool_security_auditor import ToolSecurityAuditor
from shared.tool_audit import write_audit_entry as _write_audit_entry
from shared.rate_limiter import create_rate_limiter_middleware, RateLimiterConfig
from tooling_manifest import build_tooling_manifest, workflow_tool_catalog
from memory_manager import coerce_memory_summary, normalize_memory_type
import mcp_handlers

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state — populated by init()
# ---------------------------------------------------------------------------
_augment_query: Optional[Callable] = None
_route_search: Optional[Callable] = None
_tree_search: Optional[Callable] = None
_store_memory: Optional[Callable] = None
_recall_memory: Optional[Callable] = None
_run_harness_eval: Optional[Callable] = None
_build_scorecard: Optional[Callable] = None
_record_learning_feedback: Optional[Callable] = None
_record_simple_feedback: Optional[Callable] = None
_update_outcome: Optional[Callable] = None
_get_variant_stats: Optional[Callable] = None
_generate_dataset: Optional[Callable] = None
_get_process_memory: Optional[Callable] = None
_snapshot_stats: Optional[Callable] = None
_error_payload: Optional[Callable] = None
_wait_for_model: Optional[Callable] = None

_multi_turn_manager: Optional[Any] = None
_progressive_disclosure: Optional[Any] = None
_feedback_api: Optional[Any] = None
_learning_pipeline: Optional[Any] = None

_COLLECTIONS: Dict[str, Any] = {}
_HYBRID_STATS: Dict[str, Any] = {}
_HARNESS_STATS: Dict[str, Any] = {}
_CIRCUIT_BREAKERS: Optional[Any] = None
_SERVICE_NAME: str = "hybrid-coordinator"

_local_llm_healthy_ref: Optional[Callable] = None   # lambda: _local_llm_healthy
_local_llm_loading_ref: Optional[Callable] = None   # lambda: _local_llm_loading
_queue_depth_ref: Optional[Callable] = None          # lambda: _model_loading_queue_depth
_queue_max_ref: Optional[Callable] = None            # lambda: _MODEL_QUEUE_MAX
_embedding_cache_ref: Optional[Callable] = None      # Phase 21.3 — lambda: embedding_cache
_workflow_sessions_lock = asyncio.Lock()
_runtime_registry_lock = asyncio.Lock()
_TOOL_SECURITY_AUDITOR: Optional[ToolSecurityAuditor] = None
_INTENT_DEPTH_EXPECTATIONS = {"minimum", "standard", "deep"}


def _read_secret_file(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _ralph_request_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = _read_secret_file(Config.RALPH_WIGGUM_API_KEY_FILE)
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _http_path_to_tool_name(path: str, method: str) -> Optional[str]:
    """Map high-value HTTP endpoints to tool names for audit coverage."""
    if path == "/query" and method == "POST":
        return "route_search"
    if path == "/augment_query" and method == "POST":
        return "augment_query"
    if path == "/search/tree" and method == "POST":
        return "tree_search"
    if path == "/memory/store" and method == "POST":
        return "store_agent_memory"
    if path == "/memory/recall" and method == "POST":
        return "recall_agent_memory"
    if path == "/harness/eval" and method == "POST":
        return "run_harness_eval"
    if path == "/qa/check" and method == "POST":
        return "qa_check"
    if path == "/hints" and method in ("GET", "POST"):
        return "hints"
    if path == "/hints/feedback" and method == "POST":
        return "hints_feedback"
    if path.startswith("/discovery/"):
        return "discovery"
    if path == "/workflow/plan":
        return "workflow_plan"
    if path == "/workflow/tooling-manifest":
        return "tooling_manifest"
    if path == "/workflow/orchestrate" and method == "POST":
        return "loop_orchestrate"
    if path.startswith("/workflow/orchestrate/") and method == "GET":
        return "loop_status"
    if path == "/workflow/run/start" and method == "POST":
        return "workflow_run_start"
    return None


def _audit_http_request(request: web.Request, status: int, latency_ms: float) -> None:
    """Emit tool-audit rows for HTTP endpoint usage (non-MCP transport)."""
    tool_name = _http_path_to_tool_name(request.path, request.method)
    if not tool_name:
        return
    token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
    caller_identity = token if token else "anonymous"
    query_pairs = list(request.rel_url.query.items())[:10]
    metadata = {
        "http_status": int(status),
        "transport": "http",
    }
    extra = request.get("audit_metadata")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(key, str):
                metadata[key] = value
    _write_audit_entry(
        service="hybrid-coordinator-http",
        tool_name=tool_name,
        caller_identity=caller_identity,
        parameters={
            "method": request.method,
            "path": request.path,
            "query": query_pairs,
        },
        risk_tier="low",
        outcome="success" if int(status) < 500 else "error",
        error_message=None if int(status) < 500 else f"http_status_{status}",
        latency_ms=latency_ms,
        metadata=metadata,
    )


def _audit_planned_tools(query: str, tools: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Audit tools on first use and keep only approved/sanitized tool entries."""
    if not _TOOL_SECURITY_AUDITOR:
        return tools, {
            "enabled": False,
            "approved": [t.get("name", "") for t in tools],
            "blocked": [],
            "cache_hits": 0,
            "first_seen": 0,
        }

    approved: List[Dict[str, str]] = []
    blocked: List[str] = []
    cache_hits = 0
    first_seen = 0
    for tool in tools:
        tool_name = str(tool.get("name", "")).strip()
        if not tool_name:
            continue
        try:
            decision = _TOOL_SECURITY_AUDITOR.audit_tool(
                tool_name,
                {
                    "query": query[:400],
                    "endpoint": tool.get("endpoint"),
                    "reason": tool.get("reason"),
                    "manifest": {"name": tool_name, "endpoint": tool.get("endpoint")},
                },
            )
            if decision.get("cached"):
                cache_hits += 1
            if decision.get("first_seen"):
                first_seen += 1
            if decision.get("approved", True):
                approved.append(tool)
            else:
                blocked.append(tool_name)
        except PermissionError:
            blocked.append(tool_name)
    return approved, {
        "enabled": True,
        "approved": [t.get("name", "") for t in approved],
        "blocked": blocked,
        "cache_hits": cache_hits,
        "first_seen": first_seen,
    }


def _workflow_sessions_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "workflow-sessions.json"


def _runtime_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-runtimes.json"


def _workflow_blueprints_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("WORKFLOW_BLUEPRINTS_FILE", "config/workflow-blueprints.json")
        )
    )


def _hint_feedback_log_path() -> Path:
    return Path(
        os.path.expanduser(
            os.getenv("HINT_FEEDBACK_LOG_PATH", "/var/log/nixos-ai-stack/hint-feedback.jsonl")
        )
    )


def _normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _validate_intent_contract(contract: Any) -> Dict[str, Any]:
    """Validate required prompt-intent/spirit contract fields."""
    errors: List[str] = []
    if not isinstance(contract, dict):
        return {
            "ok": False,
            "errors": ["intent_contract must be an object"],
            "normalized": {},
        }

    user_intent = str(contract.get("user_intent", "") or "").strip()
    definition_of_done = str(contract.get("definition_of_done", "") or "").strip()
    depth_expectation = str(contract.get("depth_expectation", "") or "").strip().lower()
    spirit_constraints = _normalize_string_list(contract.get("spirit_constraints", []))
    no_early_exit_without = _normalize_string_list(contract.get("no_early_exit_without", []))
    anti_goals = _normalize_string_list(contract.get("anti_goals", []))

    if not user_intent:
        errors.append("intent_contract.user_intent is required")
    if not definition_of_done:
        errors.append("intent_contract.definition_of_done is required")
    if depth_expectation not in _INTENT_DEPTH_EXPECTATIONS:
        errors.append(
            "intent_contract.depth_expectation must be one of: minimum, standard, deep"
        )
    if not spirit_constraints:
        errors.append("intent_contract.spirit_constraints must contain at least one item")
    if not no_early_exit_without:
        errors.append("intent_contract.no_early_exit_without must contain at least one item")

    normalized = {
        "user_intent": user_intent,
        "definition_of_done": definition_of_done,
        "depth_expectation": depth_expectation if depth_expectation in _INTENT_DEPTH_EXPECTATIONS else "standard",
        "spirit_constraints": spirit_constraints,
        "no_early_exit_without": no_early_exit_without,
        "anti_goals": anti_goals,
    }
    return {"ok": len(errors) == 0, "errors": errors, "normalized": normalized}


def _default_intent_contract(query: str) -> Dict[str, Any]:
    objective = (query or "").strip()[:280] or "complete current workflow objective"
    return {
        "user_intent": objective,
        "definition_of_done": "deliver validated results that satisfy the objective",
        "depth_expectation": "minimum",
        "spirit_constraints": [
            "follow declarative-first policy",
            "capture validation evidence for major actions",
        ],
        "no_early_exit_without": [
            "all requested checks completed",
            "known blockers documented with remediation",
        ],
        "anti_goals": [],
    }


def _coerce_intent_contract(query: str, incoming: Any) -> Dict[str, Any]:
    """
    Produce a valid intent contract even when callers omit/partially provide it.
    This keeps workflow telemetry contract coverage high without weakening fields.
    """
    base = _default_intent_contract(query)
    if not isinstance(incoming, dict):
        return base

    user_intent = str(incoming.get("user_intent", "") or "").strip()
    definition = str(incoming.get("definition_of_done", "") or "").strip()
    depth = str(incoming.get("depth_expectation", "") or "").strip().lower()
    spirit = _normalize_string_list(incoming.get("spirit_constraints", []))
    no_early = _normalize_string_list(incoming.get("no_early_exit_without", []))
    anti_goals = _normalize_string_list(incoming.get("anti_goals", []))

    if user_intent:
        base["user_intent"] = user_intent
    if definition:
        base["definition_of_done"] = definition
    if depth in _INTENT_DEPTH_EXPECTATIONS:
        base["depth_expectation"] = depth
    if spirit:
        base["spirit_constraints"] = spirit
    if no_early:
        base["no_early_exit_without"] = no_early
    if anti_goals:
        base["anti_goals"] = anti_goals
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

        normalized = dict(item)
        normalized["intent_contract"] = intent_validation["normalized"]
        normalized["intent_contract_valid"] = bool(intent_validation["ok"])
        normalized["intent_contract_errors"] = intent_validation["errors"]
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
        return {"runtimes": {}}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("runtimes"), dict):
            return data
    except Exception:
        pass
    return {"runtimes": {}}


async def _save_runtime_registry(data: Dict[str, Any]) -> None:
    path = _runtime_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _build_workflow_plan(
    query: str,
    tools: Optional[List[Dict[str, str]]] = None,
    tool_security: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if tools is None or tool_security is None:
        tools, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query))
    prompt_coaching: Dict[str, Any] = {}
    try:
        from hints_engine import HintsEngine  # type: ignore[import]
        prompt_coaching = HintsEngine().prompt_coaching_as_dict(query, agent_type="codex")
    except Exception:
        prompt_coaching = {}
    return {
        "objective": query,
        "workflow_version": "1.1",
        "phases": [
            {
                "id": "discover",
                "goal": "Collect only high-signal context first.",
                "tools": [t for t in tools if t["name"] in {"hints", "discovery", "route_search", "tree_search"}],
                "exit_criteria": "Top risks and likely root causes identified.",
            },
            {
                "id": "plan",
                "goal": "Convert findings into discrete steps with verification points.",
                "tools": [t for t in tools if t["name"] in {"hints", "discovery"}],
                "exit_criteria": "Ordered task list with acceptance checks exists.",
            },
            {
                "id": "execute",
                "goal": "Apply changes in small reversible increments.",
                "tools": [t for t in tools if t["name"] in {"route_search", "memory_recall", "feedback"}],
                "exit_criteria": "Primary objective implemented.",
            },
            {
                "id": "validate",
                "goal": "Run smoke/eval checks and confirm expected behavior.",
                "tools": [t for t in tools if t["name"] in {"qa_check", "harness_eval", "health", "learning_stats"}],
                "exit_criteria": "All mandatory checks pass or failures are documented.",
            },
            {
                "id": "handoff",
                "goal": "Capture outcomes, residual risk, and rollback path.",
                "tools": [t for t in tools if t["name"] in {"feedback", "learning_stats"}],
                "exit_criteria": "Actionable handoff summary ready.",
            },
        ],
        "token_policy": {
            "approach": "progressive-disclosure",
            "rules": [
                "Start with concise hints/capability summaries.",
                "Load deeper context only when a phase requires it.",
                "Prefer retrieval over full-policy prompt stuffing.",
            ],
        },
        "metadata": {
            "query_length": len(query),
            "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            "prompt_coaching": prompt_coaching,
            "tool_security": tool_security,
            "created_epoch_s": int(time.time()),
        },
    }


def _session_lineage(sessions: Dict[str, Any], session_id: str) -> List[str]:
    """Return root->...->session lineage for a session id."""
    lineage: List[str] = []
    seen = set()
    current = session_id
    while current and current not in seen and current in sessions:
        seen.add(current)
        lineage.append(current)
        parent = (
            sessions.get(current, {})
            .get("fork", {})
            .get("from_session_id")
        )
        current = parent if isinstance(parent, str) else ""
    lineage.reverse()
    return lineage


async def _load_workflow_sessions() -> Dict[str, Any]:
    path = _workflow_sessions_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def _save_workflow_sessions(data: Dict[str, Any]) -> None:
    path = _workflow_sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _normalize_safety_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"plan-readonly", "plan_readonly", "readonly"}:
        return "plan-readonly"
    if mode in {"execute-mutating", "execute_mutating", "execute"}:
        return "execute-mutating"
    return "plan-readonly"


def _default_budget(data: Dict[str, Any]) -> Dict[str, int]:
    env_token_limit = int(os.getenv("AI_RUN_DEFAULT_TOKEN_LIMIT", "8000"))
    env_tool_call_limit = int(os.getenv("AI_RUN_DEFAULT_TOOL_CALL_LIMIT", "40"))
    return {
        "token_limit": int(data.get("token_limit", env_token_limit)),
        "tool_call_limit": int(data.get("tool_call_limit", env_tool_call_limit)),
    }


def _default_usage() -> Dict[str, int]:
    return {"tokens_used": 0, "tool_calls_used": 0}


def _ensure_session_runtime_fields(session: Dict[str, Any]) -> None:
    default_mode = _normalize_safety_mode(os.getenv("AI_RUN_DEFAULT_SAFETY_MODE", "plan-readonly"))
    default_token_limit = int(os.getenv("AI_RUN_DEFAULT_TOKEN_LIMIT", "8000"))
    default_tool_call_limit = int(os.getenv("AI_RUN_DEFAULT_TOOL_CALL_LIMIT", "40"))
    session.setdefault("safety_mode", default_mode)
    session.setdefault("budget", {"token_limit": default_token_limit, "tool_call_limit": default_tool_call_limit})
    session.setdefault("usage", {"tokens_used": 0, "tool_calls_used": 0})
    session.setdefault("trajectory", [])
    session.setdefault(
        "isolation",
        {
            "profile": "",
            "workspace_root": "",
            "network_policy": "",
        },
    )


def _budget_exceeded(session: Dict[str, Any]) -> Optional[str]:
    budget = session.get("budget", {})
    usage = session.get("usage", {})
    token_limit = int(budget.get("token_limit", 0))
    tool_call_limit = int(budget.get("tool_call_limit", 0))
    tokens_used = int(usage.get("tokens_used", 0))
    tool_calls_used = int(usage.get("tool_calls_used", 0))
    if token_limit > 0 and tokens_used > token_limit:
        return f"token budget exceeded: {tokens_used}>{token_limit}"
    if tool_call_limit > 0 and tool_calls_used > tool_call_limit:
        return f"tool-call budget exceeded: {tool_calls_used}>{tool_call_limit}"
    return None


def _resolve_isolation_profile(session: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load_runtime_isolation_profiles()
    profiles = cfg.get("profiles", {}) if isinstance(cfg, dict) else {}
    isolation = session.get("isolation", {}) if isinstance(session.get("isolation"), dict) else {}
    profile_name = str(isolation.get("profile", "")).strip()
    if not profile_name:
        by_mode = cfg.get("default_profile_by_mode", {}) if isinstance(cfg, dict) else {}
        profile_name = str(by_mode.get(session.get("safety_mode", "plan-readonly"), "readonly-strict"))
    profile = profiles.get(profile_name, profiles.get("readonly-strict", {}))
    workspace_root = str(isolation.get("workspace_root", "")).strip() or str(profile.get("workspace_root", "/tmp/agent-runs"))
    network_policy = str(isolation.get("network_policy", "")).strip() or str(profile.get("network_policy", "none"))
    return {
        "profile_name": profile_name,
        "workspace_root": workspace_root,
        "network_policy": network_policy,
        "allow_workspace_write": bool(profile.get("allow_workspace_write", False)),
        "allowed_processes": list(profile.get("allowed_processes", [])),
    }


def _check_isolation_constraints(session: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
    isolation = _resolve_isolation_profile(session)
    exec_meta = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    workspace_path = str(exec_meta.get("workspace_path", "")).strip()
    process_exec = str(exec_meta.get("process_exec", "")).strip()
    requested_network = str(exec_meta.get("network_access", "")).strip().lower()

    if workspace_path:
        root = os.path.abspath(isolation["workspace_root"])
        wp = os.path.abspath(workspace_path)
        if not (wp == root or wp.startswith(root.rstrip("/") + "/")):
            return f"workspace path outside isolation root: {workspace_path}"

    if process_exec:
        exe_name = os.path.basename(process_exec)
        allowed = set(isolation.get("allowed_processes", []))
        if allowed and exe_name not in allowed:
            return f"process not allowed by isolation profile: {exe_name}"

    if requested_network:
        policy = isolation.get("network_policy", "none")
        order = {"none": 0, "loopback": 1, "egress": 2}
        if order.get(requested_network, 99) > order.get(policy, 0):
            return f"network access '{requested_network}' exceeds policy '{policy}'"

    return None


def init(
    *,
    augment_query_fn: Callable,
    route_search_fn: Callable,
    tree_search_fn: Callable,
    store_memory_fn: Callable,
    recall_memory_fn: Callable,
    run_harness_eval_fn: Callable,
    build_scorecard_fn: Callable,
    record_learning_feedback_fn: Callable,
    record_simple_feedback_fn: Callable,
    update_outcome_fn: Callable,
    get_variant_stats_fn: Callable,
    generate_dataset_fn: Callable,
    get_process_memory_fn: Callable,
    snapshot_stats_fn: Callable,
    error_payload_fn: Callable,
    wait_for_model_fn: Callable,
    multi_turn_manager: Any,
    progressive_disclosure: Any,
    feedback_api: Optional[Any],
    learning_pipeline: Optional[Any],
    collections: Dict[str, Any],
    hybrid_stats: Dict[str, Any],
    harness_stats: Dict[str, Any],
    circuit_breakers: Any,
    service_name: str,
    local_llm_healthy_ref: Callable,
    local_llm_loading_ref: Callable,
    queue_depth_ref: Callable,
    queue_max_ref: Callable,
    embedding_cache_ref: Optional[Callable] = None,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _augment_query, _route_search, _tree_search, _store_memory, _recall_memory
    global _run_harness_eval, _build_scorecard, _record_learning_feedback
    global _record_simple_feedback, _update_outcome, _get_variant_stats, _generate_dataset
    global _get_process_memory, _snapshot_stats, _error_payload, _wait_for_model
    global _multi_turn_manager, _progressive_disclosure, _feedback_api, _learning_pipeline
    global _COLLECTIONS, _HYBRID_STATS, _HARNESS_STATS, _CIRCUIT_BREAKERS, _SERVICE_NAME
    global _local_llm_healthy_ref, _local_llm_loading_ref, _queue_depth_ref, _queue_max_ref
    global _embedding_cache_ref
    global _TOOL_SECURITY_AUDITOR

    _augment_query = augment_query_fn
    _route_search = route_search_fn
    _tree_search = tree_search_fn
    _store_memory = store_memory_fn
    _recall_memory = recall_memory_fn
    _run_harness_eval = run_harness_eval_fn
    _build_scorecard = build_scorecard_fn
    _record_learning_feedback = record_learning_feedback_fn
    _record_simple_feedback = record_simple_feedback_fn
    _update_outcome = update_outcome_fn
    _get_variant_stats = get_variant_stats_fn
    _generate_dataset = generate_dataset_fn
    _get_process_memory = get_process_memory_fn
    _snapshot_stats = snapshot_stats_fn
    _error_payload = error_payload_fn
    _wait_for_model = wait_for_model_fn
    _multi_turn_manager = multi_turn_manager
    _progressive_disclosure = progressive_disclosure
    _feedback_api = feedback_api
    _learning_pipeline = learning_pipeline
    _COLLECTIONS = collections
    _HYBRID_STATS = hybrid_stats
    _HARNESS_STATS = harness_stats
    _CIRCUIT_BREAKERS = circuit_breakers
    _SERVICE_NAME = service_name
    _local_llm_healthy_ref = local_llm_healthy_ref
    _local_llm_loading_ref = local_llm_loading_ref
    _queue_depth_ref = queue_depth_ref
    _queue_max_ref = queue_max_ref
    _embedding_cache_ref = embedding_cache_ref
    audit_enabled = os.getenv("AI_TOOL_SECURITY_AUDIT_ENABLED", "true").lower() == "true"
    audit_enforce = os.getenv("AI_TOOL_SECURITY_AUDIT_ENFORCE", "true").lower() == "true"
    audit_ttl_hours = int(os.getenv("AI_TOOL_SECURITY_CACHE_TTL_HOURS", "168"))
    data_dir = Path(os.path.expanduser(os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")))
    policy_path = Path(
        os.path.expanduser(
            os.getenv("RUNTIME_TOOL_SECURITY_POLICY_FILE", "config/runtime-tool-security-policy.json")
        )
    )
    cache_path = Path(
        os.path.expanduser(
            os.getenv(
                "TOOL_SECURITY_AUDIT_CACHE_FILE",
                str(data_dir / "tool-security-audit-cache.json"),
            )
        )
    )
    _TOOL_SECURITY_AUDITOR = ToolSecurityAuditor(
        service_name=_SERVICE_NAME,
        policy_path=policy_path,
        cache_path=cache_path,
        enabled=audit_enabled,
        enforce=audit_enforce,
        cache_ttl_hours=audit_ttl_hours,
    )


async def run_http_mode(port: int) -> None:
    """Build and run the aiohttp HTTP server."""

    access_log_format = (
        '{"remote":"%a","request":"%r","status":%s,'
        '"bytes":"%b","agent":"%{User-Agent}i","time":"%t"}'
    )
    access_logger = logging.getLogger("aiohttp.access")
    access_logger.handlers.clear()
    access_handler = logging.StreamHandler()
    access_handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    @web.middleware
    async def tracing_middleware(request, handler):
        tracer = trace.get_tracer(_SERVICE_NAME)
        span_name = f"{request.method} {request.path}"
        with tracer.start_as_current_span(
            span_name,
            attributes={"http.method": request.method, "http.target": request.path},
        ) as span:
            response = await handler(request)
            span.set_attribute("http.status_code", response.status)
            return response

    @web.middleware
    async def request_id_middleware(request, handler):
        from structlog.contextvars import bind_contextvars, clear_contextvars
        import time
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request["request_id"] = request_id
        bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        response = None
        try:
            response = await handler(request)
            return response
        except Exception:  # noqa: BLE001
            REQUEST_ERRORS.labels(request.path, request.method).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            status = str(response.status) if response else "500"
            REQUEST_LATENCY.labels(request.path, request.method).observe(duration)
            REQUEST_COUNT.labels(request.path, status).inc()
            _audit_http_request(request, int(status), duration * 1000.0)
            if response:
                response.headers["X-Request-ID"] = request_id
            clear_contextvars()

    @web.middleware
    async def api_key_middleware(request, handler):
        if request.path in ("/health", "/metrics"):
            return await handler(request)
        if not Config.API_KEY:
            return await handler(request)
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
        if token != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def handle_status(request):
        """Phase 2.4.2 — Model loading status endpoint."""
        import time as _time
        try:
            async with httpx.AsyncClient(timeout=2.0) as hc:
                resp = await hc.get(f"{Config.LLAMA_CPP_URL}/health")
                llama_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                llama_status = llama_data.get("status", "unknown")
                loading = llama_status == "loading"
        except Exception as exc:
            llama_status = "unreachable"
            loading = False
            logger.debug("handle_status llama.cpp probe failed: %s", exc)

        threshold = await routing_config.get_threshold()
        return web.json_response({
            "service": "hybrid-coordinator",
            "local_llm": {
                "url": Config.LLAMA_CPP_URL,
                "status": llama_status,
                "loading": loading,
                "healthy": _local_llm_healthy_ref(),
                "model_name": os.getenv("LLAMA_MODEL_NAME", "unknown"),
                "queue_depth": _queue_depth_ref(),
                "queue_max": _queue_max_ref(),
            },
            "routing": {
                "threshold": threshold,
                "local_supports_json": os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true",
            },
        })

    async def handle_health(request):
        """Health check endpoint with circuit breakers."""
        try:
            from continuous_learning import learning_pipeline
            if learning_pipeline and hasattr(learning_pipeline, "circuit_breakers"):
                breakers = {name: breaker.state.name for name, breaker in learning_pipeline.circuit_breakers._breakers.items()}
            else:
                breakers = {}
        except (ImportError, AttributeError) as exc:
            logger.debug("Circuit breaker state unavailable: %s", exc)
            breakers = {}

        return web.json_response({
            "status": "healthy",
            "service": "hybrid-coordinator",
            "collections": list(_COLLECTIONS.keys()),
            "ai_harness": {
                "enabled": Config.AI_HARNESS_ENABLED,
                "memory_enabled": Config.AI_MEMORY_ENABLED,
                "tree_search_enabled": Config.AI_TREE_SEARCH_ENABLED,
                "eval_enabled": Config.AI_HARNESS_EVAL_ENABLED,
                "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
                "capability_discovery_ttl_seconds": Config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS,
                "capability_discovery_on_query": Config.AI_CAPABILITY_DISCOVERY_ON_QUERY,
                "autonomy_max_external_calls": Config.AI_AUTONOMY_MAX_EXTERNAL_CALLS,
                "autonomy_max_retrieval_results": Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS,
                "prompt_cache_policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
                "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
                "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            },
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            "circuit_breakers": breakers or (_CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {}),
        })

    async def handle_health_detailed(request):
        """Detailed health endpoint with dependency probes and performance indicators."""
        deps: Dict[str, Any] = {}

        qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip()
        aidb_url = os.getenv("AIDB_URL", "http://127.0.0.1:8002").strip()
        llama_url = os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080").strip()
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()
        postgres_host = os.getenv("POSTGRES_HOST", "127.0.0.1").strip()
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432") or 5432)

        async with httpx.AsyncClient(timeout=2.5) as hc:
            try:
                r = await hc.get(f"{qdrant_url.rstrip('/')}/collections")
                deps["qdrant"] = {"status": "ok" if r.status_code < 500 else "error", "http_status": r.status_code}
            except Exception as exc:  # noqa: BLE001
                deps["qdrant"] = {"status": "unavailable", "error": str(exc)[:180]}

            try:
                r = await hc.get(f"{aidb_url.rstrip('/')}/health/fast")
                body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
                deps["aidb"] = {
                    "status": "ok" if r.status_code < 500 else "error",
                    "http_status": r.status_code,
                    "reported_status": body.get("status"),
                }
            except Exception as exc:  # noqa: BLE001
                deps["aidb"] = {"status": "unavailable", "error": str(exc)[:180]}

            try:
                r = await hc.get(f"{llama_url.rstrip('/')}/health")
                body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
                deps["llama_cpp"] = {
                    "status": "ok" if r.status_code < 500 else "error",
                    "http_status": r.status_code,
                    "reported_status": body.get("status"),
                }
            except Exception as exc:  # noqa: BLE001
                deps["llama_cpp"] = {"status": "unavailable", "error": str(exc)[:180]}

        redis_host_port = redis_url.split("://", 1)[-1].split("/", 1)[0]
        redis_host, redis_port = (redis_host_port.split(":", 1) + ["6379"])[:2]
        try:
            with socket.create_connection((redis_host, int(redis_port)), timeout=2.0):
                deps["redis"] = {"status": "ok", "host": redis_host, "port": int(redis_port)}
        except Exception as exc:  # noqa: BLE001
            deps["redis"] = {"status": "unavailable", "error": str(exc)[:180]}

        try:
            with socket.create_connection((postgres_host, postgres_port), timeout=2.0):
                deps["postgres"] = {"status": "ok", "host": postgres_host, "port": postgres_port}
        except Exception as exc:  # noqa: BLE001
            deps["postgres"] = {"status": "unavailable", "error": str(exc)[:180]}

        stats = _snapshot_stats() if _snapshot_stats else {}
        total_queries = int(stats.get("total_queries", 0) or 0)
        context_hits = int(stats.get("context_hits", 0) or 0)
        context_hit_rate = round((100.0 * context_hits / total_queries), 1) if total_queries > 0 else None
        perf = {
            "total_queries": total_queries,
            "context_hits": context_hits,
            "context_hit_rate_pct": context_hit_rate,
            "model_loading_queue_depth": _queue_depth_ref() if _queue_depth_ref else None,
            "model_loading_queue_max": _queue_max_ref() if _queue_max_ref else None,
        }
        dependency_unhealthy = any(d.get("status") != "ok" for d in deps.values())
        service_status = "degraded" if dependency_unhealthy else "healthy"
        return web.json_response(
            {
                "status": service_status,
                "service": "hybrid-coordinator",
                "dependencies": deps,
                "performance": perf,
                "circuit_breakers": _CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {},
                "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            },
            status=200 if service_status in ("healthy", "degraded") else 503,
        )

    async def handle_stats(request):
        return web.json_response({
            "status": "ok",
            "service": "hybrid-coordinator",
            "stats": _snapshot_stats(),
            "collections": list(_COLLECTIONS.keys()),
            "harness_stats": _HARNESS_STATS,
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            "circuit_breakers": _CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {},
        })

    async def handle_augment_query(request):
        try:
            data = await request.json()
            result = await _augment_query(data.get("query", ""), data.get("agent_type", "remote"))
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "augment_query_failed", "detail": str(exc)}, status=500)

    async def handle_query(request):
        """HTTP endpoint for query routing."""
        try:
            data = await request.json()
            query = data.get("prompt") or data.get("query") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            semantic_tooling_autorun = os.getenv("AI_SEMANTIC_TOOLING_AUTORUN", "true").lower() == "true"
            request_context = data.get("context")
            if not isinstance(request_context, dict):
                request_context = {}
            request["audit_metadata"] = {
                "semantic_autorun_enabled": bool(semantic_tooling_autorun),
                "semantic_autorun_planned": 0,
                "semantic_autorun_executed": 0,
                "tool_security_blocked": 0,
                "tool_security_cache_hits": 0,
                "tool_security_first_seen": 0,
            }
            tooling_layer = {
                "enabled": semantic_tooling_autorun,
                "planned_tools": [],
                "executed": [],
                "hints": [],
            }
            if semantic_tooling_autorun:
                planned, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query))
                tooling_layer["planned_tools"] = [p.get("name", "") for p in planned]
                tooling_layer["tool_security"] = tool_security
                request["audit_metadata"]["tool_security_blocked"] = len(tool_security.get("blocked", []))
                request["audit_metadata"]["tool_security_cache_hits"] = int(tool_security.get("cache_hits", 0))
                request["audit_metadata"]["tool_security_first_seen"] = int(tool_security.get("first_seen", 0))

                # Auto-hints: pull top semantic hint and pass into route context.
                if any(p.get("name") == "hints" for p in planned):
                    try:
                        import sys as _sys
                        from pathlib import Path as _Path
                        _hints_dir = _Path(__file__).parent
                        if str(_hints_dir) not in _sys.path:
                            _sys.path.insert(0, str(_hints_dir))
                        from hints_engine import HintsEngine  # type: ignore[import]
                        hint_data = HintsEngine().rank_as_dict(query, context="", max_hints=2)
                        top_hints = hint_data.get("hints", []) if isinstance(hint_data, dict) else []
                        hint_snippets = [
                            str(h.get("snippet", "")).strip()
                            for h in top_hints
                            if isinstance(h, dict) and str(h.get("snippet", "")).strip()
                        ]
                        if hint_snippets:
                            request_context["tool_hints"] = hint_snippets[:2]
                            tooling_layer["hints"] = hint_snippets[:2]
                            tooling_layer["executed"].append("hints")
                    except Exception as exc:
                        logger.debug("semantic_tooling_hints_skipped error=%s", exc)

                # Auto-discovery summary: enrich context with capability overview.
                if _progressive_disclosure and any(p.get("name") == "discovery" for p in planned):
                    try:
                        disc = await _progressive_disclosure.discover(
                            level="overview",
                            categories=None,
                            token_budget=200,
                        )
                        if hasattr(disc, "model_dump"):
                            disc_data = disc.model_dump()
                        elif hasattr(disc, "dict"):
                            disc_data = disc.dict()
                        else:
                            disc_data = {}
                        request_context["tool_discovery"] = {
                            "summary": str(disc_data.get("summary", ""))[:300],
                            "capability_count": len(disc_data.get("capabilities", []) or []),
                        }
                        tooling_layer["executed"].append("discovery")
                    except Exception as exc:
                        logger.debug("semantic_tooling_discovery_skipped error=%s", exc)

            prefer_local = bool(data.get("prefer_local", True))
            if prefer_local and _local_llm_loading_ref():
                ready = await _wait_for_model(timeout=30.0)
                if not ready:
                    return web.json_response(
                        {
                            "error": "model_loading",
                            "detail": "Local model is loading and the queue is full or timed out. Retry or set prefer_local=false.",
                            "queue_depth": _queue_depth_ref(),
                            "queue_max": _queue_max_ref(),
                        },
                        status=503,
                    )
            result = await _route_search(
                query=query,
                mode=data.get("mode", "auto"),
                prefer_local=prefer_local,
                context=request_context,
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", 0.7)),
                generate_response=bool(data.get("generate_response", False)),
            )
            if semantic_tooling_autorun:
                result["tooling_layer"] = tooling_layer
            request["audit_metadata"]["semantic_autorun_planned"] = len(tooling_layer.get("planned_tools", []))
            request["audit_metadata"]["semantic_autorun_executed"] = len(tooling_layer.get("executed", []))
            request["audit_metadata"]["route_strategy"] = str(result.get("route", "unknown"))
            request["audit_metadata"]["backend"] = str(result.get("backend", "unknown"))
            iid = result.get("interaction_id", "")
            if iid:
                try:
                    _last_id_path = os.path.expanduser("~/.local/share/nixos-ai-stack/last-interaction")
                    os.makedirs(os.path.dirname(_last_id_path), exist_ok=True)
                    with open(_last_id_path, "w") as _f:
                        _f.write(iid)
                except OSError:
                    pass
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "route_search_failed", "detail": str(exc)}, status=500)

    async def handle_tree_search(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _tree_search(
                query=query,
                collections=data.get("collections"),
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", 0.7)),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "tree_search_failed", "detail": str(exc)}, status=500)

    async def handle_memory_store(request):
        try:
            data = await request.json()
            memory_type = normalize_memory_type(data.get("memory_type", ""))
            summary = coerce_memory_summary(data.get("summary"), data.get("content"))
            result = await _store_memory(
                memory_type=memory_type,
                summary=summary,
                content=data.get("content"),
                metadata=data.get("metadata"),
            )
            return web.json_response(result)
        except ValueError as exc:
            return web.json_response({"error": "memory_store_invalid", "detail": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": "memory_store_failed", "detail": str(exc)}, status=500)

    async def handle_memory_recall(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _recall_memory(
                query=query,
                memory_types=data.get("memory_types"),
                limit=data.get("limit"),
                retrieval_mode=data.get("retrieval_mode", "hybrid"),
            )
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "memory_recall_failed", "detail": str(exc)}, status=500)

    async def handle_harness_eval(request):
        try:
            data = await request.json()
            query = data.get("query") or data.get("prompt") or ""
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            result = await _run_harness_eval(
                query=query,
                expected_keywords=data.get("expected_keywords"),
                mode=data.get("mode", "auto"),
                max_latency_ms=data.get("max_latency_ms"),
            )
            metrics = result.get("metrics") if isinstance(result, dict) else {}
            request["audit_metadata"] = {
                "harness_status": result.get("status") if isinstance(result, dict) else "",
                "harness_passed": bool(result.get("passed")) if isinstance(result, dict) else False,
                "harness_overall_score": metrics.get("overall_score") if isinstance(metrics, dict) else None,
                "harness_failure_category": result.get("failure_category") if isinstance(result, dict) else None,
            }
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "harness_eval_failed", "detail": str(exc)}, status=500)

    async def handle_qa_check(request):
        try:
            data = await request.json()
            result = await mcp_handlers.run_qa_check_as_dict(data)
            qa_result = result.get("qa_result") if isinstance(result, dict) else {}
            request["audit_metadata"] = {
                "phase": result.get("phase"),
                "exit_code": result.get("exit_code"),
                "qa_passed": (qa_result or {}).get("passed") if isinstance(qa_result, dict) else None,
                "qa_failed": (qa_result or {}).get("failed") if isinstance(qa_result, dict) else None,
                "qa_skipped": (qa_result or {}).get("skipped") if isinstance(qa_result, dict) else None,
            }
            status = 200 if result.get("status") == "ok" else 500
            return web.json_response(result, status=status)
        except ValueError as exc:
            return web.json_response({"error": "qa_check_invalid", "detail": str(exc)}, status=400)
        except TimeoutError as exc:
            return web.json_response({"error": "qa_check_timeout", "detail": str(exc)}, status=504)
        except FileNotFoundError as exc:
            return web.json_response({"error": "qa_check_unavailable", "detail": str(exc)}, status=503)
        except Exception as exc:
            return web.json_response({"error": "qa_check_failed", "detail": str(exc)}, status=500)

    async def handle_harness_stats(_request):
        return web.json_response(_HARNESS_STATS)

    async def handle_harness_scorecard(_request):
        return web.json_response(_build_scorecard())

    async def handle_multi_turn_context(request):
        try:
            data = await request.json()
            session_id = data.get("session_id") or str(uuid4())
            response = await _multi_turn_manager.get_context(
                session_id=session_id,
                query=data.get("query", ""),
                context_level=data.get("context_level", "standard"),
                previous_context_ids=data.get("previous_context_ids", []),
                max_tokens=data.get("max_tokens", 2000),
                metadata=data.get("metadata"),
            )
            return web.json_response(response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback(request):
        try:
            data = await request.json()
            interaction_id = data.get("interaction_id")
            outcome = data.get("outcome")
            user_feedback = data.get("user_feedback", 0)
            correction = data.get("correction")
            if correction:
                feedback_id = await _record_learning_feedback(
                    query=data.get("query", ""),
                    correction=correction,
                    original_response=data.get("original_response"),
                    interaction_id=interaction_id,
                    rating=data.get("rating"),
                    tags=data.get("tags"),
                    model=data.get("model"),
                    variant=data.get("variant"),
                )
                return web.json_response({"status": "recorded", "feedback_id": feedback_id})
            if interaction_id and outcome:
                await _update_outcome(interaction_id=interaction_id, outcome=outcome, user_feedback=user_feedback)
                return web.json_response({"status": "updated"})
            return web.json_response({"error": "missing_feedback_fields"}, status=400)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_simple_feedback(request):
        """Phase 3.1.1 — POST /feedback/{interaction_id}"""
        try:
            interaction_id = request.match_info.get("interaction_id", "")
            if not interaction_id:
                return web.json_response({"error": "interaction_id required in path"}, status=400)
            data = await request.json()
            rating = data.get("rating")
            if rating not in (1, -1):
                return web.json_response({"error": "rating must be 1 (good) or -1 (bad)"}, status=400)
            feedback_id = await _record_simple_feedback(
                interaction_id=interaction_id,
                rating=rating,
                note=str(data.get("note", ""))[:1000],
                query=str(data.get("query", ""))[:500],
            )
            return web.json_response({"status": "recorded", "feedback_id": feedback_id})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback_evaluate(request):
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            feedback_response = await _feedback_api.evaluate_response(
                session_id=session_id,
                response=data.get("response", ""),
                confidence=data.get("confidence", 0.5),
                gaps=data.get("gaps", []),
                metadata=data.get("metadata"),
            )
            return web.json_response(feedback_response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_session_info(request):
        try:
            session_id = request.match_info.get("session_id")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            session_info = await _multi_turn_manager.get_session_info(session_id)
            if not session_info:
                return web.json_response({"error": "session not found"}, status=404)
            return web.json_response(session_info)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_clear_session(request):
        try:
            session_id = request.match_info.get("session_id")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            await _multi_turn_manager.clear_session(session_id)
            return web.json_response({"status": "cleared", "session_id": session_id})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_discover_capabilities(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            discovery_response = await _progressive_disclosure.discover(
                level=data.get("level", "overview"),
                categories=data.get("categories"),
                token_budget=data.get("token_budget", 500),
            )
            return web.json_response(discovery_response.dict())
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_token_budget_recommendations(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            recommendations = await _progressive_disclosure.get_token_budget_recommendations(
                query_type=data.get("query_type", "quick_lookup"),
                context_level=data.get("context_level", "standard"),
            )
            return web.json_response(recommendations)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_apply_proposal(request: web.Request) -> web.Response:
        """Apply a validated OptimizationProposal. Requires API key."""
        key = request.headers.get("X-API-Key", "")
        if Config.API_KEY and key != Config.API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            body = await request.json()
            proposal = OptimizationProposal(**body)
        except Exception as exc:
            return web.json_response({"error": "invalid_proposal", "detail": str(exc)}, status=400)
        result = await apply_proposal(proposal)
        return web.json_response(result)

    async def handle_metrics(_request):
        PROCESS_MEMORY_BYTES.set(_get_process_memory())
        # Phase 21.3 — update embedding cache size gauge
        if _embedding_cache_ref:
            try:
                cache = _embedding_cache_ref()
                if cache:
                    from metrics import EMBEDDING_CACHE_SIZE
                    size = await cache.get_cache_size()
                    EMBEDDING_CACHE_SIZE.set(size)
            except Exception:
                pass
        return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    # Phase 21.3 — Cache invalidation endpoint for event-driven cache management
    async def handle_cache_invalidate(request):
        """
        Invalidate embedding cache entries.

        POST /cache/invalidate
        Body:
            {"trigger": "rebuild"|"manual"|"model_change", "scope": "all"|"prefix", "prefix": "..."}

        Returns:
            {"status": "ok", "keys_deleted": N}
        """
        if not _embedding_cache_ref:
            return web.json_response({"error": "cache not initialized"}, status=503)

        try:
            cache = _embedding_cache_ref()
            if not cache:
                return web.json_response({"error": "cache not available"}, status=503)

            data = await request.json()
            trigger = data.get("trigger", "manual")
            scope = data.get("scope", "all")

            from metrics import EMBEDDING_CACHE_INVALIDATIONS
            EMBEDDING_CACHE_INVALIDATIONS.labels(trigger=trigger).inc()

            if scope == "all":
                deleted = await cache.clear_all()
                logger.info("cache_invalidation trigger=%s scope=all deleted=%d", trigger, deleted)
                return web.json_response({"status": "ok", "keys_deleted": deleted})
            else:
                # Future: support prefix-based invalidation
                return web.json_response({"error": "unsupported scope"}, status=400)

        except Exception as exc:
            logger.error("cache_invalidation_error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_cache_stats(_request):
        """
        Get embedding cache statistics.

        GET /cache/stats
        Returns cache hit/miss stats and current size.
        """
        if not _embedding_cache_ref:
            return web.json_response({"error": "cache not initialized"}, status=503)

        try:
            cache = _embedding_cache_ref()
            if not cache:
                return web.json_response({"error": "cache not available"}, status=503)

            stats = cache.get_stats()
            size = await cache.get_cache_size()
            stats["current_size"] = size
            return web.json_response(stats)

        except Exception as exc:
            logger.error("cache_stats_error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_learning_stats(_request):
        try:
            stats_path = Path(
                os.path.expanduser(
                    os.getenv(
                        "CONTINUOUS_LEARNING_STATS_PATH",
                        os.path.join(
                            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid"),
                            "telemetry",
                            "continuous_learning_stats.json",
                        ),
                    )
                )
            )
            if stats_path.exists():
                import json
                with open(stats_path, "r") as f:
                    return web.json_response(json.load(f))
            if _learning_pipeline:
                stats = await _learning_pipeline.get_statistics()
                return web.json_response(stats)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        return web.json_response({
            "checkpoints": {"total": 0, "last_checkpoint": None},
            "backpressure": {"unprocessed_mb": 0, "paused": False},
            "backpressure_threshold_mb": 100,
            "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0},
        })

    async def handle_learning_process(_request):
        if not _learning_pipeline:
            return web.json_response({"status": "disabled"}, status=503)
        try:
            patterns = await _learning_pipeline.process_telemetry_batch()
            examples_count = 0
            if patterns:
                examples = await _learning_pipeline.generate_finetuning_examples(patterns)
                examples_count = len(examples)
                await _learning_pipeline._save_finetuning_examples(examples)
                await _learning_pipeline._index_patterns(patterns)
            await _learning_pipeline._write_stats_snapshot()
            return web.json_response({"status": "ok", "patterns": len(patterns), "examples": examples_count})
        except Exception as exc:
            return web.json_response({"status": "error", "detail": str(exc)}, status=500)

    async def handle_learning_export(_request):
        try:
            dataset_path = ""
            if _learning_pipeline:
                dataset_path = await _learning_pipeline.export_dataset_for_training()
            else:
                dataset_path = await _generate_dataset()
            dataset_path_str = str(dataset_path) if dataset_path else ""
            count = 0
            if dataset_path_str and Path(dataset_path_str).exists():
                with open(dataset_path_str, "r") as f:
                    count = sum(1 for _ in f)
            return web.json_response({"status": "ok", "dataset_path": dataset_path_str, "examples": count})
        except Exception as exc:
            return web.json_response({"status": "error", "detail": str(exc)}, status=500)

    async def handle_learning_ab_compare(request):
        try:
            data = await request.json()
            tag_prefix = data.get("tag_prefix", "variant:")
            tag_a = data.get("tag_a")
            tag_b = data.get("tag_b")
            variant_a = data.get("variant_a")
            variant_b = data.get("variant_b")
            days = data.get("days")
            if not tag_a and variant_a:
                tag_a = f"{tag_prefix}{variant_a}"
            if not tag_b and variant_b:
                tag_b = f"{tag_prefix}{variant_b}"
            if not tag_a or not tag_b:
                return web.json_response({"error": "variant_a/variant_b or tag_a/tag_b required"}, status=400)
            stats_a = await _get_variant_stats(tag_a, days)
            stats_b = await _get_variant_stats(tag_b, days)
            avg_a = stats_a.get("avg_rating")
            avg_b = stats_b.get("avg_rating")
            delta = (float(avg_a) - float(avg_b)) if avg_a is not None and avg_b is not None else None
            return web.json_response({
                "status": "ok",
                "variant_a": stats_a,
                "variant_b": stats_b,
                "delta": {"avg_rating": delta},
            })
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=503)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    _RELOAD_ALLOWLIST = {
        "llama-cpp": "llama-cpp.service",
        "llama-cpp-embed": "llama-cpp-embed.service",
        "ai-embeddings": "ai-embeddings.service",
    }

    async def handle_reload_model(request: web.Request) -> web.Response:
        """POST /reload-model — restart a whitelisted systemd service with metrics."""
        from metrics import MODEL_RELOADS, MODEL_RELOAD_DURATION
        import time as _time
        try:
            body = await request.json()
        except Exception:
            body = {}
        service = body.get("service", "llama-cpp")
        if service not in _RELOAD_ALLOWLIST:
            MODEL_RELOADS.labels(service=service, status="failure").inc()
            return web.json_response({"error": "service not in allowlist"}, status=400)
        service_unit = _RELOAD_ALLOWLIST[service]
        start = _time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "restart", service_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        duration = _time.monotonic() - start
        MODEL_RELOAD_DURATION.labels(service=service).observe(duration)
        if proc.returncode == 0:
            MODEL_RELOADS.labels(service=service, status="success").inc()
            return web.json_response({
                "status": "restarted",
                "service": service_unit,
                "duration_seconds": round(duration, 2),
            })
        else:
            MODEL_RELOADS.labels(service=service, status="failure").inc()
            return web.json_response({
                "status": "failed",
                "service": service_unit,
                "error": stderr.decode("utf-8", errors="replace")[:500],
            }, status=500)

    async def handle_model_status(request: web.Request) -> web.Response:
        """GET /model/status — return status of model services (Phase 5)."""
        from metrics import MODEL_ACTIVE_INFO
        results = {}
        for name, unit in _RELOAD_ALLOWLIST.items():
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "is-active", unit,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            status = stdout.decode().strip()
            # Try to get model path from environment
            model_path = "unknown"
            if name in ("llama-cpp", "llama-cpp-embed"):
                env_proc = await asyncio.create_subprocess_exec(
                    "systemctl", "show", unit, "--property=ExecStart",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                env_out, _ = await env_proc.communicate()
                env_str = env_out.decode()
                # Extract --model path from ExecStart
                import re
                model_match = re.search(r'--model\s+([^\s;]+)', env_str)
                if model_match:
                    model_path = model_match.group(1)
            MODEL_ACTIVE_INFO.labels(service=name, model_path=model_path).set(1 if status == "active" else 0)
            results[name] = {
                "unit": unit,
                "status": status,
                "model_path": model_path,
            }
        return web.json_response({"services": results})

    # ------------------------------------------------------------------
    # Phase 19.2.1/19.2.2 — /hints endpoint (agent-agnostic hint API)
    # ------------------------------------------------------------------

    async def handle_hints(request: web.Request) -> web.Response:
        """POST /hints or GET /hints?q= — return ranked workflow hints for any agent.

        Phase 19.3.2: When format=continue (GET param) or body contains 'fullInput'
        (Continue.dev HTTP context provider), returns [{"name","description","content"}].
        """
        try:
            if request.method == "POST":
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                # Continue.dev HTTP context provider sends {"query":..., "fullInput":...}
                is_continue = "fullInput" in body or body.get("format") == "continue"
                query = body.get("query", "") or body.get("fullInput", "")
                ctx = body.get("context", {})
                file_ext = ctx.get("file_ext", "") if isinstance(ctx, dict) else str(ctx)
                max_hints = int(body.get("max_hints", 5))
                agent_type = ctx.get("agent_type", "remote") if isinstance(ctx, dict) else "remote"
            else:
                is_continue = request.rel_url.query.get("format") == "continue"
                query = request.rel_url.query.get("q", "")
                file_ext = request.rel_url.query.get("context", "")
                max_hints = int(request.rel_url.query.get("max", "5"))
                agent_type = request.rel_url.query.get("agent", "remote")

            try:
                import sys as _sys
                from pathlib import Path as _Path
                _hints_dir = _Path(__file__).parent
                if str(_hints_dir) not in _sys.path:
                    _sys.path.insert(0, str(_hints_dir))
                from hints_engine import HintsEngine  # type: ignore[import]
                engine = HintsEngine()
                result = engine.rank_as_dict(
                    query,
                    context=file_ext,
                    max_hints=max_hints,
                    agent_type=agent_type,
                )
            except Exception as exc:
                logger.warning("hints_engine_unavailable error=%s", exc)
                result = {
                    "hints": [],
                    "generated_at": "",
                    "query": query,
                    "error": f"hints_engine unavailable: {exc}",
                }

            # Phase 19.3.2 — Continue.dev HTTP context provider format
            if is_continue:
                hints = result.get("hints", [])
                content_lines = [f"# AI Stack Hints\n\n"]
                for i, h in enumerate(hints, 1):
                    score_pct = f"{h.get('score', 0):.0%}"
                    content_lines.append(
                        f"{i}. [{h.get('type', 'hint')}] {h.get('title', '')} ({score_pct})\n"
                        f"   {h.get('snippet', '')[:120]}\n"
                        f"   Reason: {h.get('reason', '')}\n\n"
                    )
                return web.json_response([{
                    "name": "aq-hints",
                    "description": f"AI Stack workflow hints" + (f" for: {query[:60]}" if query else ""),
                    "content": "".join(content_lines) or "No hints available — run aq-prompt-eval to score registry prompts.",
                }])

            # Agent-type-specific augmentation
            if result.get("hints") and agent_type in ("claude", "codex", "qwen", "aider"):
                top = result["hints"][0]
                result["inject_prefix"] = top.get("snippet", "")[:150]
            result["feedback_contract"] = {
                "endpoint": "/hints/feedback",
                "fields": {
                    "hint_id": "string (required)",
                    "helpful": "boolean (optional if score present)",
                    "score": "number -1..1 (optional if helpful present)",
                    "comment": "string optional",
                    "task_id": "string optional",
                    "agent": "string optional",
                    "agent_preferences": {
                        "preferred_tools": ["string"],
                        "preferred_data_sources": ["string"],
                        "preferred_hint_types": ["string"],
                        "preferred_tags": ["string"],
                    },
                },
            }

            return web.json_response(result)
        except Exception as exc:
            logger.error("handle_hints error=%s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_hints_feedback(request: web.Request) -> web.Response:
        """POST /hints/feedback — explicit agent feedback loop for hint quality."""
        try:
            data = await request.json()
        except Exception:
            data = {}

        hint_id = str(data.get("hint_id", "") or "").strip()
        if not hint_id:
            return web.json_response({"error": "hint_id required"}, status=400)

        helpful_raw = data.get("helpful")
        helpful = bool(helpful_raw) if isinstance(helpful_raw, bool) else None
        score_raw = data.get("score")
        score_val: Optional[float] = None
        if score_raw is not None:
            try:
                score_val = float(score_raw)
            except (TypeError, ValueError):
                return web.json_response({"error": "score must be numeric"}, status=400)

        if helpful is None and score_val is None:
            return web.json_response({"error": "helpful or score required"}, status=400)

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hint_id": hint_id,
            "helpful": helpful,
            "score": score_val,
            "comment": str(data.get("comment", "") or "").strip()[:240],
            "agent": str(data.get("agent", "") or "").strip()[:48] or "unknown",
            "task_id": str(data.get("task_id", "") or "").strip()[:80],
            "source": "agent_feedback",
        }
        prefs = data.get("agent_preferences", {})
        if isinstance(prefs, dict):
            def _norm_list(value: object, limit: int = 8) -> List[str]:
                if not isinstance(value, list):
                    return []
                out: List[str] = []
                seen = set()
                for item in value:
                    text = str(item or "").strip().lower()
                    if not text or text in seen:
                        continue
                    seen.add(text)
                    out.append(text[:48])
                    if len(out) >= limit:
                        break
                return out

            entry["agent_preferences"] = {
                "preferred_tools": _norm_list(prefs.get("preferred_tools")),
                "preferred_data_sources": _norm_list(prefs.get("preferred_data_sources")),
                "preferred_hint_types": _norm_list(prefs.get("preferred_hint_types")),
                "preferred_tags": _norm_list(prefs.get("preferred_tags")),
            }
        try:
            log_path = _hint_feedback_log_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.error("hint_feedback_write_failed error=%s", exc)
            return web.json_response({"error": "feedback_write_failed"}, status=500)

        return web.json_response({"status": "recorded", "hint_id": hint_id})

    async def handle_workflow_plan(request: web.Request) -> web.Response:
        """Build a structured phase plan with explicit tool assignments."""
        try:
            if request.method == "POST":
                data = await request.json()
                query = (data.get("query") or data.get("prompt") or "").strip()
            else:
                data = {}
                query = (request.rel_url.query.get("q") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            return web.json_response(_build_workflow_plan(query))
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_tooling_manifest(request: web.Request) -> web.Response:
        """Return a compact tool manifest optimized for code-execution clients."""
        try:
            if request.method == "POST":
                data = await request.json()
                query = (data.get("query") or data.get("prompt") or "").strip()
            else:
                data = {}
                query = (request.rel_url.query.get("q") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            tools, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query))
            plan = _build_workflow_plan(query, tools=tools, tool_security=tool_security)
            return web.json_response(
                build_tooling_manifest(
                    query,
                    tools,
                    runtime=str(data.get("runtime") or request.rel_url.query.get("runtime") or "python"),
                    max_tools=data.get("max_tools"),
                    max_result_chars=data.get("max_result_chars"),
                    phases=[
                        {
                            "id": str(phase.get("id", "")).strip(),
                            "tools": [
                                str(tool.get("name", "")).strip()
                                for tool in phase.get("tools", [])
                                if isinstance(tool, dict) and str(tool.get("name", "")).strip()
                            ],
                        }
                        for phase in plan.get("phases", [])
                        if isinstance(phase, dict)
                    ],
                    tool_security=tool_security,
                )
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_orchestrate(request: web.Request) -> web.Response:
        """Submit work to the Ralph loop through the harness layer."""
        try:
            data = await request.json()
            prompt = (data.get("prompt") or data.get("query") or "").strip()
            if not prompt:
                return web.json_response({"error": "prompt required"}, status=400)
            payload = {"prompt": prompt}
            for key in ("backend", "max_iterations", "require_approval", "context"):
                if key in data:
                    payload[key] = data[key]
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{Config.RALPH_WIGGUM_URL.rstrip('/')}/tasks",
                    headers=_ralph_request_headers(),
                    json=payload,
                )
            return web.json_response(response.json(), status=response.status_code)
        except httpx.HTTPError as exc:
            return web.json_response(_error_payload("ralph_unavailable", exc), status=502)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_orchestrate_status(request: web.Request) -> web.Response:
        """Get Ralph loop task state or final result through the harness layer."""
        try:
            task_id = str(request.match_info.get("task_id", "")).strip()
            if not task_id:
                return web.json_response({"error": "task_id required"}, status=400)
            include_result = (
                str(request.rel_url.query.get("include_result", "false")).strip().lower()
                in {"1", "true", "yes", "on"}
            )
            upstream_path = "/result" if include_result else ""
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{Config.RALPH_WIGGUM_URL.rstrip('/')}/tasks/{task_id}{upstream_path}",
                    headers=_ralph_request_headers(),
                )
            return web.json_response(response.json(), status=response.status_code)
        except httpx.HTTPError as exc:
            return web.json_response(_error_payload("ralph_unavailable", exc), status=502)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_start(request: web.Request) -> web.Response:
        """Start a persisted workflow session from a query."""
        try:
            data = await request.json()
            query = (data.get("query") or data.get("prompt") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            session_id = str(uuid4())
            plan = _build_workflow_plan(query)
            phases = []
            for idx, phase in enumerate(plan.get("phases", [])):
                phases.append({
                    "id": phase.get("id", f"phase-{idx}"),
                    "status": "in_progress" if idx == 0 else "pending",
                    "started_at": int(time.time()) if idx == 0 else None,
                    "completed_at": None,
                    "notes": [],
                })
            session = {
                "session_id": session_id,
                "objective": query,
                "plan": plan,
                "phase_state": phases,
                "current_phase_index": 0,
                "status": "in_progress",
                "safety_mode": _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly"))),
                "budget": _default_budget(data),
                "usage": _default_usage(),
                "isolation": {
                    "profile": str(data.get("isolation_profile", "")).strip(),
                    "workspace_root": str(data.get("workspace_root", "")).strip(),
                    "network_policy": str(data.get("network_policy", "")).strip(),
                },
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
                "trajectory": [
                    {
                        "ts": int(time.time()),
                        "event_type": "session_start",
                        "phase_id": "discover",
                        "detail": "workflow session created",
                    }
                ],
            }
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_get(request: web.Request) -> web.Response:
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            include_lineage = (
                request.rel_url.query.get("lineage", "").lower() in {"1", "true", "yes"}
            )
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            if include_lineage:
                payload = dict(session)
                payload["lineage"] = _session_lineage(sessions, session_id)
                return web.json_response(payload)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_sessions_list(_request: web.Request) -> web.Response:
        """List persisted workflow sessions with compact metadata."""
        try:
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
            items = []
            for sid, sess in sessions.items():
                phase_state = sess.get("phase_state", [])
                current_idx = int(sess.get("current_phase_index", 0))
                current_phase = None
                if 0 <= current_idx < len(phase_state):
                    current_phase = phase_state[current_idx].get("id")
                _ensure_session_runtime_fields(sess)
                items.append({
                    "session_id": sid,
                    "status": sess.get("status", "unknown"),
                    "objective": sess.get("objective", ""),
                    "current_phase": current_phase,
                    "current_phase_index": current_idx,
                    "safety_mode": sess.get("safety_mode", "plan-readonly"),
                    "budget": sess.get("budget", {}),
                    "usage": sess.get("usage", {}),
                    "created_at": sess.get("created_at"),
                    "updated_at": sess.get("updated_at"),
                })
            items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
            return web.json_response({"sessions": items, "count": len(items)})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_tree(request: web.Request) -> web.Response:
        """Return workflow session tree with parent/child relationships."""
        try:
            include_completed = (
                request.rel_url.query.get("include_completed", "true").lower() in {"1", "true", "yes"}
            )
            include_failed = (
                request.rel_url.query.get("include_failed", "true").lower() in {"1", "true", "yes"}
            )
            include_objective = (
                request.rel_url.query.get("include_objective", "true").lower() in {"1", "true", "yes"}
            )

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()

            nodes = []
            edges = []
            children_count: Dict[str, int] = {}

            for sid, sess in sessions.items():
                status = str(sess.get("status", "unknown"))
                if status == "completed" and not include_completed:
                    continue
                if status == "failed" and not include_failed:
                    continue

                parent_id = (
                    sess.get("fork", {})
                    .get("from_session_id")
                )
                if isinstance(parent_id, str) and parent_id:
                    edges.append({"from": parent_id, "to": sid, "type": "fork"})
                    children_count[parent_id] = int(children_count.get(parent_id, 0)) + 1

                node = {
                    "session_id": sid,
                    "status": status,
                    "current_phase_index": int(sess.get("current_phase_index", 0)),
                    "created_at": sess.get("created_at"),
                    "updated_at": sess.get("updated_at"),
                    "parent_session_id": parent_id if isinstance(parent_id, str) and parent_id else None,
                }
                if include_objective:
                    node["objective"] = sess.get("objective", "")
                nodes.append(node)

            for node in nodes:
                sid = node["session_id"]
                node["children_count"] = int(children_count.get(sid, 0))

            roots = [n["session_id"] for n in nodes if n.get("parent_session_id") is None]
            nodes.sort(key=lambda n: int(n.get("updated_at") or 0), reverse=True)

            return web.json_response({
                "nodes": nodes,
                "edges": edges,
                "roots": roots,
                "count": len(nodes),
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_fork(request: web.Request) -> web.Response:
        """Fork a workflow session to create a branch from current state."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json() if request.can_read_body else {}
            note = str(data.get("note", "forked session")).strip()
            new_id = str(uuid4())
            now = int(time.time())
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                source = sessions.get(session_id)
                if not source:
                    return web.json_response({"error": "session not found"}, status=404)
                forked = json.loads(json.dumps(source))
                forked["session_id"] = new_id
                forked["status"] = "in_progress"
                forked["created_at"] = now
                forked["updated_at"] = now
                forked.setdefault("fork", {})
                forked["fork"] = {
                    "from_session_id": session_id,
                    "note": note,
                    "forked_at": now,
                }
                sessions[new_id] = forked
                await _save_workflow_sessions(sessions)
            return web.json_response({"session_id": new_id, "forked_from": session_id, "status": "created"})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_session_advance(request: web.Request) -> web.Response:
        """Advance workflow state using actions: pass|fail|skip|note."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json()
            action = str(data.get("action", "note")).strip().lower()
            note = str(data.get("note", "")).strip()
            if action not in {"pass", "fail", "skip", "note"}:
                return web.json_response({"error": "action must be one of pass|fail|skip|note"}, status=400)

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)

                idx = int(session.get("current_phase_index", 0))
                phases = session.get("phase_state", [])
                if not phases or idx >= len(phases):
                    session["status"] = "completed"
                    session["updated_at"] = int(time.time())
                    sessions[session_id] = session
                    await _save_workflow_sessions(sessions)
                    return web.json_response(session)

                phase = phases[idx]
                if note:
                    phase.setdefault("notes", []).append({"ts": int(time.time()), "text": note})
                phase_id = str(phase.get("id", f"phase-{idx}"))

                # In plan-readonly mode, phase pass/skip/fail is allowed, but mutating notes must be explicit.
                if session.get("safety_mode") == "plan-readonly":
                    mutating_note = any(x in note.lower() for x in ("write", "apply", "edit", "delete", "execute"))
                    if mutating_note and action == "note":
                        return web.json_response(
                            {
                                "error": "plan-readonly mode blocks mutating action notes; switch to execute-mutating",
                                "safety_mode": "plan-readonly",
                            },
                            status=403,
                        )

                if action in {"pass", "skip"}:
                    phase["status"] = "completed"
                    phase["completed_at"] = int(time.time())
                    idx += 1
                    if idx < len(phases):
                        phases[idx]["status"] = "in_progress"
                        if not phases[idx].get("started_at"):
                            phases[idx]["started_at"] = int(time.time())
                        session["current_phase_index"] = idx
                        session["status"] = "in_progress"
                    else:
                        session["status"] = "completed"
                        session["current_phase_index"] = len(phases)
                elif action == "fail":
                    phase["status"] = "failed"
                    phase["completed_at"] = int(time.time())
                    session["status"] = "failed"
                else:
                    if phase.get("status") == "pending":
                        phase["status"] = "in_progress"
                        phase["started_at"] = int(time.time())

                session["trajectory"].append(
                    {
                        "ts": int(time.time()),
                        "event_type": "phase_advance",
                        "phase_id": phase_id,
                        "action": action,
                        "note": note,
                    }
                )

                budget_error = _budget_exceeded(session)
                if budget_error:
                    session["status"] = "failed"
                    session["trajectory"].append(
                        {
                            "ts": int(time.time()),
                            "event_type": "budget_violation",
                            "detail": budget_error,
                        }
                    )

                session["phase_state"] = phases
                session["updated_at"] = int(time.time())
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_review_acceptance(request: web.Request) -> web.Response:
        """Deterministic reviewer gate: criteria + keyword coverage scoring."""
        try:
            data = await request.json()
            response_text = str(data.get("response", "") or "")
            query = str(data.get("query", "") or "")
            criteria = data.get("criteria", []) or []
            expected_keywords = data.get("expected_keywords", []) or []
            min_criteria_ratio = float(data.get("min_criteria_ratio", 0.7))
            min_keyword_ratio = float(data.get("min_keyword_ratio", 0.6))
            run_eval = bool(data.get("run_harness_eval", False))

            if not response_text:
                return web.json_response({"error": "response required"}, status=400)

            text = response_text.lower()
            criteria_hits = []
            for criterion in criteria:
                crit = str(criterion).strip()
                if not crit:
                    continue
                hit = crit.lower() in text
                criteria_hits.append({"criterion": crit, "hit": hit})
            criteria_total = len(criteria_hits)
            criteria_hit_count = len([c for c in criteria_hits if c["hit"]])
            criteria_ratio = (criteria_hit_count / criteria_total) if criteria_total else 1.0

            keyword_hits = []
            for kw in expected_keywords:
                item = str(kw).strip().lower()
                if not item:
                    continue
                keyword_hits.append({"keyword": item, "hit": item in text})
            keyword_total = len(keyword_hits)
            keyword_hit_count = len([k for k in keyword_hits if k["hit"]])
            keyword_ratio = (keyword_hit_count / keyword_total) if keyword_total else 1.0

            harness_eval = None
            if run_eval and query and expected_keywords and _run_harness_eval is not None:
                try:
                    harness_eval = await _run_harness_eval(
                        query=query,
                        expected_keywords=[str(k) for k in expected_keywords],
                        mode="auto",
                        max_latency_ms=None,
                    )
                except Exception as exc:
                    harness_eval = {"error": str(exc)}

            passed = criteria_ratio >= min_criteria_ratio and keyword_ratio >= min_keyword_ratio
            if isinstance(harness_eval, dict) and harness_eval.get("passed") is False:
                passed = False

            return web.json_response({
                "passed": passed,
                "score": round((criteria_ratio + keyword_ratio) / 2.0, 4),
                "criteria": {
                    "hits": criteria_hits,
                    "hit_count": criteria_hit_count,
                    "total": criteria_total,
                    "ratio": round(criteria_ratio, 4),
                    "threshold": min_criteria_ratio,
                },
                "keywords": {
                    "hits": keyword_hits,
                    "hit_count": keyword_hit_count,
                    "total": keyword_total,
                    "ratio": round(keyword_ratio, 4),
                    "threshold": min_keyword_ratio,
                },
                "harness_eval": harness_eval,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_start(request: web.Request) -> web.Response:
        """Start a workflow run with explicit safety mode + budget contract."""
        try:
            data = await request.json()
            query = (data.get("query") or data.get("prompt") or "").strip()
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            blueprints_data = _load_and_validate_workflow_blueprints()
            blueprint_id = str(data.get("blueprint_id", "") or "").strip()
            selected_blueprint = (
                blueprints_data.get("blueprint_by_id", {}).get(blueprint_id)
                if blueprint_id
                else None
            )
            incoming_contract = data.get("intent_contract")
            if incoming_contract is None and selected_blueprint:
                incoming_contract = selected_blueprint.get("intent_contract", {})
            validation = _validate_intent_contract(_coerce_intent_contract(query, incoming_contract))
            session_id = str(uuid4())
            plan = _build_workflow_plan(query)
            phases = []
            for idx, phase in enumerate(plan.get("phases", [])):
                phases.append({
                    "id": phase.get("id", f"phase-{idx}"),
                    "status": "in_progress" if idx == 0 else "pending",
                    "started_at": int(time.time()) if idx == 0 else None,
                    "completed_at": None,
                    "notes": [],
                })
            now = int(time.time())
            session = {
                "session_id": session_id,
                "objective": query,
                "plan": plan,
                "phase_state": phases,
                "current_phase_index": 0,
                "status": "in_progress",
                "safety_mode": _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly"))),
                "budget": _default_budget(data),
                "usage": _default_usage(),
                "blueprint_id": blueprint_id or None,
                "intent_contract": validation["normalized"],
                "isolation": {
                    "profile": str(data.get("isolation_profile", "")).strip(),
                    "workspace_root": str(data.get("workspace_root", "")).strip(),
                    "network_policy": str(data.get("network_policy", "")).strip(),
                },
                "created_at": now,
                "updated_at": now,
                "trajectory": [
                    {
                        "ts": now,
                        "event_type": "run_start",
                        "phase_id": "discover",
                        "detail": "workflow run started",
                        "intent_contract_present": True,
                    }
                ],
            }
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(session)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_get(request: web.Request) -> web.Response:
        """Get workflow run state, including budget + usage + trajectory summary."""
        try:
            session_id = request.match_info.get("session_id", "")
            include_replay = request.rel_url.query.get("replay", "false").lower() in {"1", "true", "yes"}
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            payload = dict(session)
            if not include_replay:
                payload["trajectory_count"] = len(session.get("trajectory", []))
                payload.pop("trajectory", None)
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_mode(request: web.Request) -> web.Response:
        """Switch run safety mode; moving to execute-mutating requires confirm=true."""
        try:
            session_id = request.match_info.get("session_id", "")
            data = await request.json()
            target_mode = _normalize_safety_mode(str(data.get("safety_mode", "plan-readonly")))
            confirm = bool(data.get("confirm", False))
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)
                if target_mode == "execute-mutating" and not confirm:
                    return web.json_response(
                        {"error": "confirm=true required to switch to execute-mutating"},
                        status=400,
                    )
                session["safety_mode"] = target_mode
                session["updated_at"] = int(time.time())
                session["trajectory"].append(
                    {
                        "ts": int(time.time()),
                        "event_type": "mode_change",
                        "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
                        "detail": f"safety_mode -> {target_mode}",
                    }
                )
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response({"session_id": session_id, "safety_mode": target_mode})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_isolation_get(request: web.Request) -> web.Response:
        """Return current and resolved isolation profile for a run."""
        try:
            session_id = request.match_info.get("session_id", "")
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            return web.json_response(
                {
                    "session_id": session_id,
                    "isolation": session.get("isolation", {}),
                    "resolved_profile": _resolve_isolation_profile(session),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_isolation_set(request: web.Request) -> web.Response:
        """Update isolation profile fields for a run."""
        try:
            session_id = request.match_info.get("session_id", "")
            data = await request.json()
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)
                iso = dict(session.get("isolation", {}))
                if "profile" in data:
                    iso["profile"] = str(data.get("profile", "")).strip()
                if "workspace_root" in data:
                    iso["workspace_root"] = str(data.get("workspace_root", "")).strip()
                if "network_policy" in data:
                    iso["network_policy"] = str(data.get("network_policy", "")).strip()
                session["isolation"] = iso
                session["updated_at"] = int(time.time())
                session["trajectory"].append(
                    {
                        "ts": int(time.time()),
                        "event_type": "isolation_update",
                        "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
                        "detail": f"isolation -> {iso}",
                    }
                )
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(
                {
                    "session_id": session_id,
                    "isolation": session.get("isolation", {}),
                    "resolved_profile": _resolve_isolation_profile(session),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_event(request: web.Request) -> web.Response:
        """Append run trajectory event and enforce safety mode + budget guardrails."""
        try:
            session_id = request.match_info.get("session_id", "")
            data = await request.json()
            event_type = str(data.get("event_type", "event")).strip().lower()
            risk_class = str(data.get("risk_class", "safe")).strip().lower()
            approved = bool(data.get("approved", False))
            token_delta = int(data.get("token_delta", 0))
            tool_call_delta = int(data.get("tool_call_delta", 0))
            detail = str(data.get("detail", "")).strip()

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)
                mode = str(session.get("safety_mode", "plan-readonly"))
                policy = _load_runtime_safety_policy()
                mode_policy = (policy.get("modes", {}) or {}).get(mode, {})
                allowed = set(mode_policy.get("allowed_risk_classes", ["safe"]))
                requires_approval = set(mode_policy.get("requires_approval", ["review-required"]))
                blocked = set(mode_policy.get("blocked", ["blocked"]))

                if risk_class in blocked:
                    return web.json_response({"error": "blocked risk_class cannot be executed"}, status=403)
                if risk_class in requires_approval and not approved:
                    return web.json_response({"error": "review-required event must include approved=true"}, status=403)
                if risk_class not in allowed and risk_class not in requires_approval:
                    return web.json_response(
                        {
                            "error": "risk_class not allowed by runtime safety policy",
                            "risk_class": risk_class,
                            "safety_mode": mode,
                        },
                        status=403,
                    )

                isolation_error = _check_isolation_constraints(session, data)
                if isolation_error:
                    return web.json_response(
                        {
                            "error": isolation_error,
                            "isolation": session.get("isolation", {}),
                            "resolved_profile": _resolve_isolation_profile(session),
                        },
                        status=403,
                    )

                usage = session.get("usage", {})
                usage["tokens_used"] = int(usage.get("tokens_used", 0)) + max(0, token_delta)
                usage["tool_calls_used"] = int(usage.get("tool_calls_used", 0)) + max(0, tool_call_delta)
                session["usage"] = usage
                budget_error = _budget_exceeded(session)
                if budget_error:
                    return web.json_response(
                        {"error": budget_error, "usage": usage, "budget": session.get("budget", {})},
                        status=429,
                    )

                current_idx = int(session.get("current_phase_index", 0))
                phase_id = f"phase-{current_idx}"
                phases = session.get("phase_state", [])
                if 0 <= current_idx < len(phases):
                    phase_id = str(phases[current_idx].get("id", phase_id))

                session["trajectory"].append(
                    {
                        "ts": int(time.time()),
                        "event_type": event_type,
                        "phase_id": phase_id,
                        "risk_class": risk_class,
                        "approved": approved,
                        "token_delta": token_delta,
                        "tool_call_delta": tool_call_delta,
                        "detail": detail,
                    }
                )
                session["updated_at"] = int(time.time())
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)

            return web.json_response(
                {
                    "session_id": session_id,
                    "usage": session.get("usage", {}),
                    "budget": session.get("budget", {}),
                    "trajectory_count": len(session.get("trajectory", [])),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_replay(request: web.Request) -> web.Response:
        """Replay stored trajectory with optional filtering."""
        try:
            session_id = request.match_info.get("session_id", "")
            phase = str(request.rel_url.query.get("phase", "")).strip()
            event_type = str(request.rel_url.query.get("event_type", "")).strip().lower()
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            _ensure_session_runtime_fields(session)
            events = list(session.get("trajectory", []))
            if phase:
                events = [e for e in events if str(e.get("phase_id", "")) == phase]
            if event_type:
                events = [e for e in events if str(e.get("event_type", "")).lower() == event_type]
            return web.json_response(
                {
                    "session_id": session_id,
                    "count": len(events),
                    "events": events,
                    "usage": session.get("usage", {}),
                    "budget": session.get("budget", {}),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_blueprints(_request: web.Request) -> web.Response:
        """Return curated MCP workflow blueprints for common coding-agent tasks."""
        try:
            parsed = _load_and_validate_workflow_blueprints()
            items = parsed.get("blueprints", [])
            errors = parsed.get("errors", [])
            return web.json_response(
                {
                    "blueprints": items,
                    "count": len(items),
                    "source": parsed.get("source", ""),
                    "valid": len(errors) == 0,
                    "errors": errors,
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_parity_scorecard(_request: web.Request) -> web.Response:
        """Return declarative parity scorecard (from env path, fallback to repo config)."""
        try:
            path = _parity_scorecard_path()
            if not path.exists():
                return web.json_response({"scorecard": {}, "source": str(path), "exists": False})
            data = json.loads(path.read_text(encoding="utf-8"))
            return web.json_response({"scorecard": data, "source": str(path), "exists": True})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_register(request: web.Request) -> web.Response:
        """Register or update an agent runtime in local control-plane state."""
        try:
            data = await request.json()
            runtime_id = str(data.get("runtime_id") or uuid4())
            now = int(time.time())
            record = {
                "runtime_id": runtime_id,
                "name": str(data.get("name", runtime_id)),
                "profile": str(data.get("profile", "default")),
                "status": str(data.get("status", "ready")),
                "runtime_class": str(data.get("runtime_class", "generic")),
                "transport": str(data.get("transport", "http")),
                "endpoint_env_var": str(data.get("endpoint_env_var", "")),
                "tags": data.get("tags", []) if isinstance(data.get("tags", []), list) else [],
                "updated_at": now,
            }
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                existing = registry["runtimes"].get(runtime_id, {})
                record["created_at"] = int(existing.get("created_at", now))
                record["deployments"] = existing.get("deployments", [])
                registry["runtimes"][runtime_id] = record
                await _save_runtime_registry(registry)
            return web.json_response(record)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_list(_request: web.Request) -> web.Response:
        try:
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
            items = list(registry.get("runtimes", {}).values())
            items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
            return web.json_response({"runtimes": items, "count": len(items)})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_get(request: web.Request) -> web.Response:
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = registry.get("runtimes", {}).get(runtime_id)
            if not runtime:
                return web.json_response({"error": "runtime not found"}, status=404)
            return web.json_response(runtime)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_status(request: web.Request) -> web.Response:
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            data = await request.json()
            status = str(data.get("status", "ready"))
            note = str(data.get("note", "")).strip()
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = registry.get("runtimes", {}).get(runtime_id)
                if not runtime:
                    return web.json_response({"error": "runtime not found"}, status=404)
                runtime["status"] = status
                runtime["updated_at"] = int(time.time())
                if note:
                    runtime.setdefault("status_notes", []).append({"ts": int(time.time()), "text": note})
                registry["runtimes"][runtime_id] = runtime
                await _save_runtime_registry(registry)
            return web.json_response(runtime)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_deploy(request: web.Request) -> web.Response:
        """Record deployment events for runtime rollout tracking."""
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            data = await request.json()
            deployment = {
                "deployment_id": str(data.get("deployment_id") or uuid4()),
                "version": str(data.get("version", "")),
                "profile": str(data.get("profile", "default")),
                "target": str(data.get("target", "local")),
                "status": str(data.get("status", "deployed")),
                "created_at": int(time.time()),
                "note": str(data.get("note", "")),
            }
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = registry.get("runtimes", {}).get(runtime_id)
                if not runtime:
                    return web.json_response({"error": "runtime not found"}, status=404)
                runtime.setdefault("deployments", []).append(deployment)
                runtime["updated_at"] = int(time.time())
                registry["runtimes"][runtime_id] = runtime
                await _save_runtime_registry(registry)
            return web.json_response({"runtime_id": runtime_id, "deployment": deployment})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_rollback(request: web.Request) -> web.Response:
        """Record rollback requests against runtime deployment history."""
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            data = await request.json()
            to_deployment_id = str(data.get("to_deployment_id", "")).strip()
            reason = str(data.get("reason", "")).strip()
            if not to_deployment_id:
                return web.json_response({"error": "to_deployment_id required"}, status=400)
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = registry.get("runtimes", {}).get(runtime_id)
                if not runtime:
                    return web.json_response({"error": "runtime not found"}, status=404)
                runtime.setdefault("rollbacks", []).append(
                    {
                        "to_deployment_id": to_deployment_id,
                        "reason": reason,
                        "created_at": int(time.time()),
                    }
                )
                runtime["updated_at"] = int(time.time())
                registry["runtimes"][runtime_id] = runtime
                await _save_runtime_registry(registry)
            return web.json_response({"runtime_id": runtime_id, "to_deployment_id": to_deployment_id, "status": "recorded"})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_schedule_policy(_request: web.Request) -> web.Response:
        """Return active runtime scheduler policy (declarative source + defaults)."""
        try:
            path = _runtime_scheduler_policy_path()
            policy = _load_runtime_scheduler_policy()
            return web.json_response(
                {
                    "policy": policy,
                    "source": str(path),
                    "exists": path.exists(),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_schedule(request: web.Request) -> web.Response:
        """Select the best runtime candidate for a task objective + requirements."""
        try:
            data = await request.json()
            objective = str(data.get("objective") or data.get("query") or "").strip()
            requirements = data.get("requirements", {}) if isinstance(data.get("requirements"), dict) else {}
            strategy = str(data.get("strategy", "weighted")).strip().lower()
            include_degraded = bool(data.get("include_degraded", False))
            policy = _load_runtime_scheduler_policy()
            selection = policy.get("selection", {}) if isinstance(policy, dict) else {}
            allowed_statuses = {
                str(s).strip().lower()
                for s in selection.get("allowed_statuses", ["ready"])
                if str(s).strip()
            }
            if include_degraded:
                allowed_statuses.add("degraded")
            require_all_tags = bool(selection.get("require_all_tags", False))
            max_candidates = max(1, int(selection.get("max_candidates", 5)))
            req_tags = _normalize_tags(requirements.get("tags", []))
            req_class = str(requirements.get("runtime_class", "")).strip().lower()
            req_transport = str(requirements.get("transport", "")).strip().lower()
            now = int(time.time())

            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtimes = list((registry.get("runtimes", {}) or {}).values())
                candidates: List[Dict[str, Any]] = []
                for runtime in runtimes:
                    runtime_id = str(runtime.get("runtime_id", "")).strip()
                    status = str(runtime.get("status", "unknown")).strip().lower()
                    if not runtime_id:
                        continue
                    if allowed_statuses and status not in allowed_statuses:
                        continue
                    runtime_tags = _normalize_tags(runtime.get("tags", []))
                    if req_tags:
                        overlap = set(req_tags) & set(runtime_tags)
                        if require_all_tags and not all(t in runtime_tags for t in req_tags):
                            continue
                        if not require_all_tags and not overlap:
                            continue
                    if req_class and str(runtime.get("runtime_class", "")).strip().lower() != req_class:
                        continue
                    if req_transport and str(runtime.get("transport", "")).strip().lower() != req_transport:
                        continue

                    scored = _runtime_schedule_score(runtime, requirements, policy, now)
                    candidates.append(
                        {
                            "runtime_id": runtime_id,
                            "name": runtime.get("name", runtime_id),
                            "status": runtime.get("status", "unknown"),
                            "runtime_class": runtime.get("runtime_class", "generic"),
                            "transport": runtime.get("transport", "http"),
                            "tags": _normalize_tags(runtime.get("tags", [])),
                            "updated_at": int(runtime.get("updated_at") or 0),
                            "score": scored["score"],
                            "score_components": scored["components"],
                        }
                    )

                candidates.sort(key=lambda x: (float(x.get("score", 0.0)), int(x.get("updated_at", 0))), reverse=True)
                top_candidates = candidates[:max_candidates]
                if not top_candidates:
                    return web.json_response(
                        {
                            "error": "no_runtime_candidate",
                            "objective": objective,
                            "requirements": {
                                "runtime_class": req_class,
                                "transport": req_transport,
                                "tags": req_tags,
                            },
                            "allowed_statuses": sorted(allowed_statuses),
                        },
                        status=404,
                    )

                selected = top_candidates[0]
                selected_runtime = registry.get("runtimes", {}).get(selected["runtime_id"])
                if isinstance(selected_runtime, dict):
                    selected_runtime.setdefault("schedule_events", []).append(
                        {
                            "ts": now,
                            "objective": objective[:500],
                            "strategy": strategy,
                            "score": selected.get("score", 0.0),
                            "requirements": {
                                "runtime_class": req_class,
                                "transport": req_transport,
                                "tags": req_tags,
                            },
                        }
                    )
                    selected_runtime["schedule_events"] = selected_runtime["schedule_events"][-50:]
                    selected_runtime["updated_at"] = now
                    registry["runtimes"][selected["runtime_id"]] = selected_runtime
                    await _save_runtime_registry(registry)

            return web.json_response(
                {
                    "objective": objective,
                    "strategy": strategy,
                    "selected": selected,
                    "candidate_count": len(candidates),
                    "candidates": top_candidates,
                    "policy": {
                        "allowed_statuses": sorted(allowed_statuses),
                        "max_candidates": max_candidates,
                        "require_all_tags": require_all_tags,
                    },
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    # ------------------------------------------------------------------
    # App assembly and startup
    # ------------------------------------------------------------------

    # Initialize rate limiter with endpoint-specific limits
    rate_limiter_config = RateLimiterConfig(
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        default_rpm=int(os.getenv("RATE_LIMIT_DEFAULT_RPM", "100")),
        default_rph=int(os.getenv("RATE_LIMIT_DEFAULT_RPH", "3000")),
        burst_multiplier=float(os.getenv("RATE_LIMIT_BURST_MULTIPLIER", "1.5")),
        endpoint_limits={
            "/query": int(os.getenv("RATE_LIMIT_QUERY_RPM", "30")),
            "/search/tree": int(os.getenv("RATE_LIMIT_TREE_RPM", "20")),
            "/hints": int(os.getenv("RATE_LIMIT_HINTS_RPM", "60")),
            "/harness/eval": int(os.getenv("RATE_LIMIT_EVAL_RPM", "20")),
            "/workflow": int(os.getenv("RATE_LIMIT_WORKFLOW_RPM", "30")),
        },
        exempt_paths={"/health", "/metrics", "/health/detailed"},
    )
    _rate_limiter, rate_limit_middleware = create_rate_limiter_middleware(rate_limiter_config)
    logger.info(
        "rate_limiter_initialized enabled=%s default_rpm=%s",
        rate_limiter_config.enabled,
        rate_limiter_config.default_rpm,
    )

    http_app = web.Application(
        middlewares=[tracing_middleware, request_id_middleware, rate_limit_middleware, api_key_middleware]
    )
    http_app.router.add_get("/health", handle_health)
    http_app.router.add_get("/health/detailed", handle_health_detailed)
    http_app.router.add_get("/status", handle_status)
    http_app.router.add_get("/stats", handle_stats)
    http_app.router.add_post("/augment_query", handle_augment_query)
    http_app.router.add_post("/query", handle_query)
    http_app.router.add_post("/search/tree", handle_tree_search)
    http_app.router.add_post("/memory/store", handle_memory_store)
    http_app.router.add_post("/memory/recall", handle_memory_recall)
    http_app.router.add_post("/harness/eval", handle_harness_eval)
    http_app.router.add_post("/qa/check", handle_qa_check)
    http_app.router.add_get("/harness/stats", handle_harness_stats)
    http_app.router.add_get("/harness/scorecard", handle_harness_scorecard)
    http_app.router.add_post("/feedback", handle_feedback)
    http_app.router.add_post("/feedback/{interaction_id}", handle_simple_feedback)
    http_app.router.add_post("/proposals/apply", handle_apply_proposal)
    http_app.router.add_post("/context/multi_turn", handle_multi_turn_context)
    http_app.router.add_post("/feedback/evaluate", handle_feedback_evaluate)
    http_app.router.add_get("/session/{session_id}", handle_session_info)
    http_app.router.add_delete("/session/{session_id}", handle_clear_session)
    http_app.router.add_post("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_get("/discovery/capabilities", handle_discover_capabilities)
    http_app.router.add_post("/discovery/token_budget", handle_token_budget_recommendations)
    http_app.router.add_get("/metrics", handle_metrics)
    # Phase 21.3 — cache management endpoints
    http_app.router.add_post("/cache/invalidate", handle_cache_invalidate)
    http_app.router.add_get("/cache/stats", handle_cache_stats)
    http_app.router.add_get("/learning/stats", handle_learning_stats)
    http_app.router.add_post("/learning/process", handle_learning_process)
    http_app.router.add_post("/learning/export", handle_learning_export)
    http_app.router.add_post("/learning/ab_compare", handle_learning_ab_compare)
    http_app.router.add_post("/reload-model", handle_reload_model)
    http_app.router.add_get("/model/status", handle_model_status)  # Phase 5
    http_app.router.add_post("/hints", handle_hints)           # Phase 19.2.1
    http_app.router.add_get("/hints", handle_hints)            # Phase 19.2.2
    http_app.router.add_post("/hints/feedback", handle_hints_feedback)
    http_app.router.add_post("/workflow/plan", handle_workflow_plan)
    http_app.router.add_get("/workflow/plan", handle_workflow_plan)
    http_app.router.add_post("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_get("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_post("/workflow/orchestrate", handle_workflow_orchestrate)
    http_app.router.add_get("/workflow/orchestrate/{task_id}", handle_workflow_orchestrate_status)
    http_app.router.add_post("/workflow/session/start", handle_workflow_session_start)
    http_app.router.add_get("/workflow/sessions", handle_workflow_sessions_list)
    http_app.router.add_get("/workflow/tree", handle_workflow_tree)
    http_app.router.add_get("/workflow/session/{session_id}", handle_workflow_session_get)
    http_app.router.add_post("/workflow/session/{session_id}/fork", handle_workflow_session_fork)
    http_app.router.add_post("/workflow/session/{session_id}/advance", handle_workflow_session_advance)
    http_app.router.add_post("/review/acceptance", handle_review_acceptance)
    http_app.router.add_post("/workflow/run/start", handle_workflow_run_start)
    http_app.router.add_get("/workflow/run/{session_id}", handle_workflow_run_get)
    http_app.router.add_post("/workflow/run/{session_id}/mode", handle_workflow_run_mode)
    http_app.router.add_get("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_get)
    http_app.router.add_post("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_set)
    http_app.router.add_post("/workflow/run/{session_id}/event", handle_workflow_run_event)
    http_app.router.add_get("/workflow/run/{session_id}/replay", handle_workflow_run_replay)
    http_app.router.add_get("/workflow/blueprints", handle_workflow_blueprints)
    http_app.router.add_get("/parity/scorecard", handle_parity_scorecard)
    http_app.router.add_post("/control/runtimes/register", handle_runtime_register)
    http_app.router.add_get("/control/runtimes", handle_runtime_list)
    http_app.router.add_get("/control/runtimes/{runtime_id}", handle_runtime_get)
    http_app.router.add_post("/control/runtimes/{runtime_id}/status", handle_runtime_status)
    http_app.router.add_post("/control/runtimes/{runtime_id}/deployments", handle_runtime_deploy)
    http_app.router.add_post("/control/runtimes/{runtime_id}/rollback", handle_runtime_rollback)
    http_app.router.add_get("/control/runtimes/schedule/policy", handle_runtime_schedule_policy)
    http_app.router.add_post("/control/runtimes/schedule/select", handle_runtime_schedule)

    runner = web.AppRunner(
        http_app,
        access_log=access_logger,
        access_log_format=access_log_format,
    )
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("✓ Hybrid Coordinator HTTP server running on http://0.0.0.0:%d", port)

    # Keep server running
    await asyncio.Event().wait()
