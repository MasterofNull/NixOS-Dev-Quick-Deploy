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
import hashlib
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
# urllib.parse (urlsplit/urlunsplit): moved to handler modules that use them
from uuid import uuid4

from aiohttp import web
import httpx
from opentelemetry import trace
from config import Config, OptimizationProposal, apply_proposal, routing_config
from metrics import (
    CAPABILITY_GAP_DETECTIONS,
    DELEGATED_PROMPT_TOKENS_AFTER,
    DELEGATED_PROMPT_TOKENS_BEFORE,
    DELEGATED_PROMPT_TOKEN_SAVINGS,
    DELEGATED_QUALITY_EVENTS,
    DELEGATED_QUALITY_SCORE,
    META_LEARNING_ADAPTATIONS,
    ORCHESTRATION_ACTIVE_WORKSPACES,
    ORCHESTRATION_CHECKPOINTS_CREATED,
    ORCHESTRATION_CHECKPOINTS_RESTORED,
    ORCHESTRATION_DELEGATIONS_COMPLETED,
    ORCHESTRATION_TOOL_CACHE_HITS,
    ORCHESTRATION_TOOL_INVOCATIONS,
    PROGRESSIVE_CONTEXT_LOADS,
    REAL_TIME_LEARNING_EVENTS,
    REASONING_PATTERN_USAGE,
    REQUEST_COUNT,
    REQUEST_ERRORS,
    REQUEST_LATENCY,
)
from shared.tool_security_auditor import ToolSecurityAuditor
from shared.tool_audit import write_audit_entry as _write_audit_entry
from shared.rate_limiter import create_rate_limiter_middleware, RateLimiterConfig
from ai_coordinator import (
    build_messages as _ai_coordinator_build_messages,
    coerce_orchestration_context as _ai_coordinator_coerce_orchestration_context,
    build_reasoning_finalization_messages as _ai_coordinator_build_reasoning_finalization_messages,
    build_tool_call_finalization_messages as _ai_coordinator_build_tool_call_finalization_messages,
    build_empty_content_retry_messages as _ai_coordinator_build_empty_content_retry_messages,
    default_runtime_id_for_profile as _ai_coordinator_default_runtime_id_for_profile,
    extract_task_from_openai_messages as _ai_coordinator_extract_task_from_openai_messages,
    infer_profile as _ai_coordinator_infer_profile,
    merge_runtime_defaults as _ai_coordinator_merge_runtime_defaults,
    prune_runtime_registry as _ai_coordinator_prune_runtime_registry,
    # Phase 9.3 — Query Complexity Routing
    route_by_complexity as _ai_coordinator_route_by_complexity,
    route_openai_chat_payload as _ai_coordinator_route_openai_chat_payload,
    get_routing_stats as _ai_coordinator_get_routing_stats,
)
from tooling_manifest import build_tooling_manifest, workflow_tool_catalog
from memory_manager import coerce_memory_summary, normalize_memory_type, get_memory_latency_metrics, validate_memory_content
from rag_reflection import get_reflection_stats as _get_rag_reflection_stats
from generator_critic import get_critic_stats as _get_generator_critic_stats
from quality_cache import (
    get_cache_stats as _get_quality_cache_stats,
    get_cached_response as _get_cached_response,
    cache_response as _cache_response,
    should_use_cache as _should_use_cache,
)
from quality_monitor import get_health_summary as _get_quality_health_summary, get_monitor_stats as _get_quality_monitor_stats
from auto_quality_improver import get_improvement_summary as _get_auto_improvement_summary
from skill_usage_tracker import (
    track_skill_usage as _track_skill_usage,
    get_skill_usage_stats as _get_skill_usage_stats,
    get_skill_recommendation as _get_skill_recommendation,
    get_recent_skill_events as _get_recent_skill_events,
)
from pattern_integration import (
    get_pattern_stats as _get_pattern_stats,
    get_pattern_boost as _get_pattern_boost,
    get_pattern_effectiveness as _get_pattern_effectiveness,
    track_pattern_usage as _track_pattern_usage,
)
from remediation_tracker import (
    get_remediation_success_rate as _get_remediation_success_rate,
    get_remediation_trend as _get_remediation_trend,
)
from lesson_effectiveness_tracker import (
    track_lesson_usage as _track_lesson_usage,
    get_lesson_effectiveness_stats as _get_lesson_effectiveness_stats,
    get_lesson_recommendation as _get_lesson_recommendation,
    get_recent_lesson_events as _get_recent_lesson_events,
)
from route_handler import get_route_search_metrics as _get_route_search_metrics
# browser_research, web_research, research_workflows: imported by their own handler
# modules (extracted Phase 11); http_server.py delegates via register_routes()
from delegation_feedback import build_recovered_artifact, classify_delegated_response, record_delegation_feedback
from model_coordinator import (
    get_model_coordinator as _get_model_coordinator,
    classify_and_route_task as _classify_and_route_task,
)
import mcp_handlers
import delegation_handlers
import openai_a2a_handlers
import ops_handlers
import prsi_handlers
import runtime_control_handlers
import model_opt_handlers
import llm_router_handlers
import orchestration_handlers
import workflow_session_handlers
import hints_handlers
import memory_context_handlers
import evidence_safety_handlers
import ai_coordinator_handlers
from delegation_handlers import (
    _REMOTE_AVAIL_TTL_S,
    _agent_pool_status_snapshot,
    _apply_progressive_context,
    _apply_remote_runtime_status,
    _assess_delegated_response_quality,
    _build_delegation_fallback_chain,
    _delegated_quality_status_snapshot,
    _inject_delegated_response_text,
    _is_remote_profile,
    _optimize_delegated_messages,
    _remote_avail_cache_get,
    _remote_avail_cache_set,
    _remote_profile_uses_agent_pool,
    _select_agent_pool_candidate,
    _select_next_available_delegation_target,
)
from workflow_session_handlers import _load_workflow_sessions, _save_workflow_sessions

# Phase 2.4: YAML Workflow Integration
try:
    import yaml_workflow_handlers
    YAML_WORKFLOWS_AVAILABLE = True
except ImportError:
    YAML_WORKFLOWS_AVAILABLE = False

# Phase 1: Alert Engine integration
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "observability"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "offloading"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "efficiency"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "progressive-disclosure"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "capability-gap"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "real-time-learning"))
from orchestration import (
    AgentHQ,
    AgentInfo,
    AgentStatus,
    DelegationAPI,
    DelegationStatus,
    IsolationMode,
    MCPToolInvoker,
    SessionState,
    ToolStatus,
    WorkspaceManager,
)
from performance_profiler import PerformanceProfiler, get_profiler as _get_global_profiler
from alert_engine import AlertEngine
from agent_pool_manager import AgentPoolManager, RemoteAgent  # AgentTier: used only in delegation_handlers
from quality_assurance import QualityChecker, QualityThreshold, ResultCache, ResultRefiner, QualityTrendTracker
from prompt_compression import PromptCompressor  # CompressionStrategy: used only in delegation_handlers
from context_management import ContextPruner  # ContextChunk: used only in delegation_handlers
from multi_tier_loading import (
    ContextRepository as DisclosureContextRepository,
    MultiTierLoader,
    TierSelector,
)
# lazy_context (ContextDependencyGraph/Node/LazyContextLoader): imported by delegation_handlers
from relevance_prediction import NegativeContextFilter, RelevancePredictor
# Phase 12.4: learning/gap modules extracted to real_time_learning_engine.py
from real_time_learning_engine import (
    _GAP_DETECTOR,
    _REMEDIATION_OUTCOME_TRACKER,
    _REMEDIATION_STRATEGY_OPTIMIZER,
    _REMEDIATION_PLAYBOOK_LIBRARY,
    _ONLINE_LEARNER,
    _HINT_QUALITY_ADJUSTER,
    _LIVE_PATTERN_MINER,
    _IMMEDIATE_FEEDBACK_PROCESSOR,
    _SUCCESS_FAILURE_DETECTOR,
    _RAPID_ADAPTOR,
    _capability_gap_status_snapshot,
    _real_time_learning_status_snapshot,
    _meta_learning_status_snapshot,
    _build_gap_failure_text,
    _plan_capability_gap_remediation,
    _record_capability_gap_outcomes,
    _apply_real_time_learning,
    _apply_meta_learning,
)
import workflow_planning
from workflow_planning import (
    _load_aq_report_status_summary,
    _audit_planned_tools,
    _is_continuation_query,
    _should_prioritize_memory_recall,
    _build_workflow_plan,
    _select_reasoning_pattern,
)

logger = logging.getLogger("hybrid-coordinator")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

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
_AGENT_POOL_MANAGER = AgentPoolManager()
_DELEGATED_QUALITY_CHECKER = QualityChecker(threshold=QualityThreshold.PERMISSIVE)  # Phase 12.1: relaxed from ACCEPTABLE(0.7) — keyword-overlap scorer over-rejects paraphrasing
_DELEGATED_RESULT_REFINER = ResultRefiner()
_DELEGATED_RESULT_CACHE = ResultCache()
_DELEGATED_QUALITY_TRACKER = QualityTrendTracker()
_DELEGATED_PROMPT_COMPRESSOR = PromptCompressor()
_DELEGATED_CONTEXT_PRUNER = ContextPruner()
_DISCLOSURE_CONTEXT_DIR = Path(
    os.getenv("DISCLOSURE_CONTEXT_DIR", "/var/lib/ai-stack/hybrid/context-tiers")
)
_DISCLOSURE_REPOSITORY = DisclosureContextRepository(_DISCLOSURE_CONTEXT_DIR)
_DISCLOSURE_TIER_SELECTOR = TierSelector()
_DISCLOSURE_TIER_LOADER = MultiTierLoader(_DISCLOSURE_REPOSITORY)
_DISCLOSURE_RELEVANCE_PREDICTOR = RelevancePredictor()
_DISCLOSURE_NEGATIVE_FILTER = NegativeContextFilter(threshold=0.25)
# _GAP_DETECTOR, _REMEDIATION_*, _ONLINE_LEARNER, etc. imported from real_time_learning_engine

# Phase 4.2 — Multi-Agent Orchestration Framework (live instances)
_ORCHESTRATION_PERSISTENCE_DIR = Path(
    os.getenv("ORCHESTRATION_DIR", "/var/lib/ai-stack/hybrid/orchestration")
)
_WORKSPACE_BASE_DIR = Path(
    os.getenv("WORKSPACE_DIR", "/var/lib/ai-stack/hybrid/workspaces")
)
_AGENT_HQ = AgentHQ(persistence_dir=_ORCHESTRATION_PERSISTENCE_DIR)
_DELEGATION_API = DelegationAPI()
_WORKSPACE_MANAGER = WorkspaceManager(base_dir=_WORKSPACE_BASE_DIR)
_MCP_TOOL_INVOKER = MCPToolInvoker(cache_enabled=True)

# Phase 1.3 — Live Bottleneck Detection & Performance Profiling
_PERFORMANCE_PROFILER = _get_global_profiler()

# Phase 11.2 — Health history tracking for trend analysis
from collections import deque
_HEALTH_HISTORY: deque = deque(maxlen=60)  # Last 60 snapshots (1 hour at 1/min)

_local_llm_healthy_ref: Optional[Callable] = None   # lambda: _local_llm_healthy
_local_llm_loading_ref: Optional[Callable] = None   # lambda: _local_llm_loading
_queue_depth_ref: Optional[Callable] = None          # lambda: _model_loading_queue_depth
_queue_max_ref: Optional[Callable] = None            # lambda: _MODEL_QUEUE_MAX
_embedding_cache_ref: Optional[Callable] = None      # Phase 21.3 — lambda: embedding_cache
_workflow_sessions_lock = asyncio.Lock()
# Phase 12.4: registry symbols imported from extracted modules
from runtime_manager import (
    _runtime_registry_lock,
    _coerce_orchestration_context,
    _validate_orchestration_policy,
    _load_and_validate_workflow_blueprints,
    _load_runtime_safety_policy,
)
from agent_registry import (
    _agent_lessons_lock,
    _agent_evaluations_lock,
    _INTENT_DEPTH_EXPECTATIONS,
    _normalize_agent_role,
    _validate_intent_contract,
    _coerce_intent_contract,
    _default_intent_contract,
    _load_agent_evaluations_registry,
    _save_agent_evaluations_registry,
    _record_agent_consensus_event,
    _record_agent_runtime_event,
    _active_lesson_refs,
    _load_active_lesson_refs,
    _load_agent_lessons_registry,
    _save_agent_lessons_registry,
)
_TOOL_SECURITY_AUDITOR: Optional[ToolSecurityAuditor] = None
_ORCHESTRATION_LANES = {
    "implementation",
    "hardening",
    "self-improvement",
    "operations",
    "diagnostics",
    "research",
    "reasoning",
}
_ORCHESTRATION_REVIEW_LANES = {"codex-review", "peer-review", "artifact-review"}
_ORCHESTRATION_CONSENSUS_MODES = {"reviewer-gate", "evidence-review", "arbiter-review"}
_ORCHESTRATION_SELECTION_STRATEGIES = {"orchestrator-first", "local-first", "evidence-first", "escalate-on-complexity"}
# _AQ_REPORT_LATEST_JSON: moved to workflow_planning.py

# Phase 1: Alert Engine instance (initialized on first access)
_ALERT_ENGINE: Optional[AlertEngine] = None


def _get_alert_engine() -> AlertEngine:
    """Get or initialize the global alert engine instance."""
    global _ALERT_ENGINE
    if _ALERT_ENGINE is None:
        data_dir = Path(os.path.expanduser(os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")))
        rules_config = Path(os.path.expanduser(os.getenv("ALERT_RULES_CONFIG", "config/alert-rules.yaml")))

        _ALERT_ENGINE = AlertEngine(
            rules_config_path=rules_config if rules_config.exists() else None,
            dedup_window_seconds=int(os.getenv("ALERT_DEDUP_WINDOW", "300")),
            grouping_window_seconds=int(os.getenv("ALERT_GROUPING_WINDOW", "60")),
            max_alert_history=int(os.getenv("ALERT_MAX_HISTORY", "10000")),
        )
        logger.info("Alert Engine initialized")
    return _ALERT_ENGINE


def _read_secret_file(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


# Phase 12.4: _load_aq_report_status_summary extracted to workflow_planning.py



def _ralph_request_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = _read_secret_file(Config.RALPH_WIGGUM_API_KEY_FILE)
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _http_path_to_tool_name(path: str, method: str) -> Optional[str]:
    """Map high-value HTTP endpoints to tool names for audit coverage."""
    if path in ("/.well-known/agent.json", "/.well-known/agent-card.json") and method == "GET":
        return "a2a_agent_card"
    if path == "/a2a" and method == "POST":
        return "a2a_rpc"
    if path.startswith("/a2a/tasks/") and method == "GET":
        return "a2a_task_events"
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
    if path == "/control/ai-coordinator/status" and method == "GET":
        return "ai_coordinator_status"
    if path == "/control/ai-coordinator/lessons" and method == "GET":
        return "ai_coordinator_lessons"
    if path == "/control/ai-coordinator/lessons/review" and method == "POST":
        return "ai_coordinator_lessons_review"
    if path == "/control/ai-coordinator/skills" and method == "GET":
        return "ai_coordinator_skills"
    if path == "/control/ai-coordinator/delegate" and method == "POST":
        return "ai_coordinator_delegate"
    if path == "/research/web/fetch" and method == "POST":
        return "web_research_fetch"
    if path == "/research/web/browser-fetch" and method == "POST":
        return "browser_research_fetch"
    if path == "/research/workflows/curated-fetch" and method == "POST":
        return "curated_research_fetch"
    return None


# Model catalog, helper functions, and delegate task state moved to ai_coordinator_handlers.py


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
    if int(status) >= 500:
        outcome = "error"
        error_message = f"http_status_{status}"
    elif int(status) >= 400:
        outcome = "client_error"
        error_message = f"http_status_{status}"
    else:
        outcome = "success"
        error_message = None
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
        outcome=outcome,
        error_message=error_message,
        latency_ms=latency_ms,
        metadata=metadata,
    )


def _gap_query_fingerprint(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(query or "").strip().lower()).strip()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _audit_internal_tool_execution(
    request: web.Request,
    tool_name: str,
    latency_ms: float,
    *,
    parameters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    outcome: str = "success",
    error_message: Optional[str] = None,
) -> None:
    token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
    caller_identity = token if token else "anonymous"
    payload = {
        "transport": "http-autorun",
        "parent_path": request.path,
        "http_method": request.method,
    }
    if isinstance(parameters, dict):
        payload.update(parameters)
    audit_metadata = {
        "http_status": 200 if outcome == "success" else 500,
        "transport": "http-autorun",
    }
    parent_metadata = request.get("audit_metadata")
    if isinstance(parent_metadata, dict):
        for key in ("requesting_agent", "requester_role", "delegate_via_coordinator_only"):
            if key in parent_metadata:
                audit_metadata[key] = parent_metadata[key]
    if isinstance(metadata, dict):
        audit_metadata.update(metadata)
    _write_audit_entry(
        service="hybrid-coordinator-http",
        tool_name=tool_name,
        caller_identity=caller_identity,
        parameters=payload,
        risk_tier="low",
        outcome=outcome,
        error_message=error_message,
        latency_ms=latency_ms,
        metadata=audit_metadata,
    )



# Phase 12.4: _audit_planned_tools extracted to workflow_planning.py

# Phase 12.4: _is_continuation_query, _should_prioritize_memory_recall, _build_workflow_plan,
# _select_reasoning_pattern extracted to workflow_planning.py

# Phase 12.4: orchestration utilities extracted to orchestration_utils.py
from orchestration_utils import (
    _ORCHESTRATION_ESCALATION_LANES,
    _compact_prompt_coaching_metadata,
    _query_prompt_coaching_response,
    _compact_tooling_layer_response,
    _compact_tool_security,
    _compact_workflow_tool_catalog,
    _phase_tool_names,
    _session_lineage,
    _normalize_safety_mode,
    _default_budget,
    _default_usage,
    _evaluation_history_bias,
    _agent_for_orchestration_lane,
    _profile_for_orchestration_lane,
    _seed_agent_evaluation,
    _build_orchestration_team,
    _normalize_consensus_decisions,
    _apply_consensus_update,
    _apply_arbiter_update,
)
# Phase 12.4: session builder functions extracted to session_builders.py
import session_builders
from session_builders import (
    _ensure_session_runtime_fields,
    _build_workflow_run_session,
    _resolve_history_role,
    _blueprint_requires_reviewer_gate,
    _budget_exceeded,
    _resolve_isolation_profile,
    _resolve_orchestration_workspace_mode,
    _build_orchestration_runtime_contract,
    _check_isolation_constraints,
)

# Phase 12.4: session builder functions extracted to session_builders.py


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

    session_builders.init(
        agent_hq=_AGENT_HQ,
        delegation_api=_DELEGATION_API,
        workspace_manager=_WORKSPACE_MANAGER,
        mcp_tool_invoker=_MCP_TOOL_INVOKER,
    )

    delegation_handlers.init(
        agent_pool_manager=_AGENT_POOL_MANAGER,
        delegated_quality_checker=_DELEGATED_QUALITY_CHECKER,
        delegated_result_refiner=_DELEGATED_RESULT_REFINER,
        delegated_result_cache=_DELEGATED_RESULT_CACHE,
        delegated_quality_tracker=_DELEGATED_QUALITY_TRACKER,
        delegated_prompt_compressor=_DELEGATED_PROMPT_COMPRESSOR,
        delegated_context_pruner=_DELEGATED_CONTEXT_PRUNER,
        disclosure_tier_selector=_DISCLOSURE_TIER_SELECTOR,
        disclosure_tier_loader=_DISCLOSURE_TIER_LOADER,
        disclosure_relevance_predictor=_DISCLOSURE_RELEVANCE_PREDICTOR,
        disclosure_negative_filter=_DISCLOSURE_NEGATIVE_FILTER,
    )

    workflow_session_handlers.init(
        build_workflow_plan_fn=_build_workflow_plan,
        error_payload_fn=_error_payload,
        audit_planned_tools_fn=_audit_planned_tools,
        phase_tool_names_fn=_phase_tool_names,
        load_lesson_refs_fn=_load_active_lesson_refs,
        ralph_request_headers_fn=_ralph_request_headers,
        workflow_sessions_lock=_workflow_sessions_lock,
        normalize_safety_mode_fn=_normalize_safety_mode,
        default_budget_fn=_default_budget,
        default_usage_fn=_default_usage,
        ensure_session_runtime_fields_fn=_ensure_session_runtime_fields,
        session_lineage_fn=_session_lineage,
        budget_exceeded_fn=_budget_exceeded,
        load_runtime_safety_policy_fn=_load_runtime_safety_policy,
        check_isolation_constraints_fn=_check_isolation_constraints,
        resolve_isolation_profile_fn=_resolve_isolation_profile,
        load_and_validate_workflow_blueprints_fn=_load_and_validate_workflow_blueprints,
        coerce_orchestration_context_fn=_coerce_orchestration_context,
        build_workflow_run_session_fn=_build_workflow_run_session,
        apply_consensus_update_fn=_apply_consensus_update,
        apply_arbiter_update_fn=_apply_arbiter_update,
        build_orchestration_team_fn=_build_orchestration_team,
        agent_evaluations_lock=_agent_evaluations_lock,
        load_agent_evaluations_registry_fn=_load_agent_evaluations_registry,
        save_agent_evaluations_registry_fn=_save_agent_evaluations_registry,
        record_agent_consensus_event_fn=_record_agent_consensus_event,
        record_agent_runtime_event_fn=_record_agent_runtime_event,
        performance_profiler=_PERFORMANCE_PROFILER,
        build_tooling_manifest_fn=build_tooling_manifest,
        workflow_tool_catalog_fn=workflow_tool_catalog,
        default_intent_contract_fn=_default_intent_contract,
        ralph_wiggum_url=Config.RALPH_WIGGUM_URL,
    )
    openai_a2a_handlers.init(
        error_payload_fn=_error_payload,
        workflow_tool_catalog_fn=workflow_tool_catalog,
        load_lesson_refs_fn=_load_active_lesson_refs,
        workflow_sessions_lock=_workflow_sessions_lock,
        load_workflow_sessions_fn=_load_workflow_sessions,
        save_workflow_sessions_fn=_save_workflow_sessions,
        ensure_session_runtime_fields_fn=_ensure_session_runtime_fields,
        load_and_validate_workflow_blueprints_fn=_load_and_validate_workflow_blueprints,
        coerce_orchestration_context_fn=_coerce_orchestration_context,
        build_workflow_run_session_fn=_build_workflow_run_session,
        ai_coordinator_route_openai_chat_payload_fn=_ai_coordinator_route_openai_chat_payload,
        ai_coordinator_extract_task_from_openai_messages_fn=_ai_coordinator_extract_task_from_openai_messages,
        ai_coordinator_route_by_complexity_fn=_ai_coordinator_route_by_complexity,
        switchboard_url=Config.SWITCHBOARD_URL,
        service_version=SERVICE_VERSION,
    )
    ops_handlers.init(
        error_payload_fn=_error_payload,
        load_lesson_refs_fn=_load_active_lesson_refs,
        snapshot_stats_fn=_snapshot_stats,
        queue_depth_ref=_queue_depth_ref,
        queue_max_ref=_queue_max_ref,
        get_alert_engine_fn=_get_alert_engine,
        record_learning_feedback_fn=_record_learning_feedback,
        record_simple_feedback_fn=_record_simple_feedback,
        update_outcome_fn=_update_outcome,
        get_variant_stats_fn=_get_variant_stats,
        generate_dataset_fn=_generate_dataset,
        get_process_memory_fn=_get_process_memory,
        feedback_api=_feedback_api,
        embedding_cache_ref=_embedding_cache_ref,
        learning_pipeline=_learning_pipeline,
        agent_hq=_AGENT_HQ,
        delegation_api=_DELEGATION_API,
        workspace_manager=_WORKSPACE_MANAGER,
        mcp_tool_invoker=_MCP_TOOL_INVOKER,
        performance_profiler=_PERFORMANCE_PROFILER,
        config=Config,
        collections=_COLLECTIONS,
        hybrid_stats=_HYBRID_STATS,
        harness_stats=_HARNESS_STATS,
        circuit_breakers=_CIRCUIT_BREAKERS,
    )
    hints_handlers.init(
        performance_profiler=_PERFORMANCE_PROFILER,
        agent_pool_manager=_AGENT_POOL_MANAGER,
    )
    ai_coordinator_handlers.init(
        agent_pool_manager=_AGENT_POOL_MANAGER,
        store_memory_fn=_store_memory,
        error_payload_fn=_error_payload,
    )
    memory_context_handlers.init(
        store_memory_fn=_store_memory,
        recall_memory_fn=_recall_memory,
        run_harness_eval_fn=_run_harness_eval,
        build_scorecard_fn=_build_scorecard,
        harness_stats=_HARNESS_STATS,
        performance_profiler=_PERFORMANCE_PROFILER,
        multi_turn_manager=_multi_turn_manager,
        progressive_disclosure=_progressive_disclosure,
        error_payload_fn=_error_payload,
    )
    prsi_handlers.init(error_payload_fn=_error_payload)
    runtime_control_handlers.init(error_payload_fn=_error_payload)
    llm_router_handlers.init(
        error_payload_fn=_error_payload,
        classify_and_route_task_fn=_classify_and_route_task,
        get_model_coordinator_fn=_get_model_coordinator,
    )
    orchestration_handlers.init(
        agent_hq=_AGENT_HQ,
        delegation_api=_DELEGATION_API,
        workspace_manager=_WORKSPACE_MANAGER,
        mcp_tool_invoker=_MCP_TOOL_INVOKER,
        performance_profiler=_PERFORMANCE_PROFILER,
        orchestration_persistence_dir=_ORCHESTRATION_PERSISTENCE_DIR,
        workspace_base_dir=_WORKSPACE_BASE_DIR,
        error_payload_fn=_error_payload,
        run_harness_eval_fn=_run_harness_eval,
    )
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
    workflow_planning.set_tool_security_auditor(_TOOL_SECURITY_AUDITOR)


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
        def _is_loopback_request(req: web.Request) -> bool:
            """Check if the request originates from localhost."""
            remote = (req.remote or "").strip()
            if remote in {"127.0.0.1", "::1", "localhost"}:
                return True
            forwarded_for = (req.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
            return forwarded_for in {"127.0.0.1", "::1", "localhost"}

        def _is_loopback_agent_request(req: web.Request) -> bool:
            """Loopback bypass for local agent endpoints.

            Local agents (Qwen, Claude Code, Aider, etc.) running on the same
            machine should be able to use the harness without manual API key
            configuration. Remote requests still require full auth.
            """
            if not _is_loopback_request(req):
                return False
            # Only bypass for endpoints that local agents actually need
            agent_prefixes = (
                "/hints",
                "/workflow/",
                "/query",
                "/v1/orchestrate",
                "/v1/",
                "/review/",
                "/discovery/",
                "/control/ai-coordinator/",
                "/control/llm/",
                "/control/agents/",
                "/control/agents",
                "/control/review/",
                "/control/runtimes",
                "/control/runtimes/",
                "/memory/",
                "/learning/",
                "/cache/",
                "/harness/",
                "/parity/",
                "/feedback",
                "/status",
                "/alerts",
                "/stats",
                "/learning/stats",
            )
            return any(req.path.startswith(pfx) for pfx in agent_prefixes)

        # Public endpoints that don't require authentication
        public_paths = (
            "/health",
            "/metrics",
            "/.well-known/mcp.json",
            "/.well-known/agent.json",
            "/.well-known/agent-card.json",
            "/health/detailed",
            "/health/aggregate",
        )
        if request.path in public_paths:
            return await handler(request)
        if _is_loopback_agent_request(request):
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
        payload = {
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
                # Phase 9.3 — Query Complexity Routing stats
                "complexity_routing": _ai_coordinator_get_routing_stats(),
            },
            # Phase 12.1/12.2 — Model Coordination
            "model_coordination": _get_model_coordinator().get_routing_stats(),
            # Batch 9.1 — RAG Reflection Loop stats
            "rag_reflection_stats": _get_rag_reflection_stats(),
            # Batch 9.2 — Generator-Critic Pattern stats
            "generator_critic_stats": _get_generator_critic_stats(),
            # Quality-Aware Response Caching stats
            "quality_cache_stats": _get_quality_cache_stats(),
            # Quality Monitoring & Health
            "quality_health": _get_quality_health_summary(
                reflection_stats=_get_rag_reflection_stats(),
                critic_stats=_get_generator_critic_stats(),
                cache_stats=_get_quality_cache_stats(),
            ),
            "quality_monitor": _get_quality_monitor_stats(),
            # Auto Quality Improvement stats
            "auto_quality_improvement": _get_auto_improvement_summary(),
            # Batch 6.2 — Remote agent pool stats
            "agent_pool": _agent_pool_status_snapshot(),
            # Batch 6.3 — Delegated response quality state
            "delegated_quality_assurance": _delegated_quality_status_snapshot(),
            # Batch 9.x — Capability gap state
            "capability_gap_automation": _capability_gap_status_snapshot(),
            # Batch 10.x — Real-time learning state
            "real_time_learning": _real_time_learning_status_snapshot(),
            # Batch 10.3 — Meta-learning state
            "meta_learning": _meta_learning_status_snapshot(),
            # Batch 5.2 — Skill Usage Tracking
            "skill_usage_stats": _get_skill_usage_stats(),
            # Batch 6.2 — Pattern Integration & Effectiveness
            "pattern_stats": _get_pattern_stats(),
            "pattern_effectiveness": _get_pattern_effectiveness(),
            # Batch 6.3 — Remediation Success Rate Tracking
            "remediation_success_rate": _get_remediation_success_rate(),
            # Batch 2.1 — Memory Latency Metrics
            "memory_latency_metrics": get_memory_latency_metrics(),
            # Batch 2.2 — Route Search Optimization Metrics
            "route_search_metrics": _get_route_search_metrics(),
            # Batch 5.1 — Lesson Effectiveness Tracking
            "lesson_effectiveness_stats": _get_lesson_effectiveness_stats(),
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

    async def handle_augment_query(request):
        try:
            data = await request.json()
            result = await _augment_query(data.get("query", ""), data.get("agent_type", "remote"))
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
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
            generate_response = bool(data.get("generate_response", False))
            semantic_tooling_autorun = os.getenv("AI_SEMANTIC_TOOLING_AUTORUN", "true").lower() == "true"
            memory_recall_priority = _should_prioritize_memory_recall(query)
            request_context = data.get("context")
            if not isinstance(request_context, dict):
                request_context = {}
            orchestration = _coerce_orchestration_context(data)
            request_context["orchestration"] = orchestration
            include_debug_metadata = bool(data.get("include_debug_metadata") or data.get("debug"))
            prompt_coaching: Dict[str, Any] = {}
            request["audit_metadata"] = {
                "semantic_autorun_enabled": bool(semantic_tooling_autorun),
                "semantic_autorun_planned": 0,
                "semantic_autorun_executed": 0,
                "tool_security_blocked": 0,
                "tool_security_cache_hits": 0,
                "tool_security_first_seen": 0,
                "prompt_coaching_score": 0.0,
                "prompt_coaching_missing_fields": 0,
                "requesting_agent": orchestration["requesting_agent"],
                "requester_role": orchestration["requester_role"],
                "delegate_via_coordinator_only": orchestration["delegate_via_coordinator_only"],
                "generate_response": generate_response,
                "memory_recall_priority": memory_recall_priority,
                "memory_recall_attempted": False,
                "backend": "unknown",
            }
            tooling_layer = {
                "enabled": semantic_tooling_autorun,
                "planned_tools": [],
                "executed": [],
                "hints": [],
            }
            try:
                import sys as _sys
                from pathlib import Path as _Path
                _hints_dir = _Path(__file__).parent
                if str(_hints_dir) not in _sys.path:
                    _sys.path.insert(0, str(_hints_dir))
                from hints_engine import HintsEngine  # type: ignore[import]
                prompt_coaching = HintsEngine().prompt_coaching_as_dict(
                    query,
                    agent_type=str(data.get("agent_type") or "human"),
                )
                request["audit_metadata"]["prompt_coaching_score"] = float(prompt_coaching.get("score", 0.0) or 0.0)
                request["audit_metadata"]["prompt_coaching_missing_fields"] = len(
                    prompt_coaching.get("missing_fields", []) or []
                )
            except Exception as exc:
                logger.debug("prompt_coaching_skipped error=%s", exc)
            if semantic_tooling_autorun:
                planned, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query, memory_recall_priority=memory_recall_priority))
                tooling_layer["planned_tools"] = [p.get("name", "") for p in planned]
                tooling_layer["tool_security"] = tool_security
                request["audit_metadata"]["tool_security_blocked"] = len(tool_security.get("blocked", []))
                request["audit_metadata"]["tool_security_cache_hits"] = int(tool_security.get("cache_hits", 0))
                request["audit_metadata"]["tool_security_first_seen"] = int(tool_security.get("first_seen", 0))

                # Auto-hints: pull top semantic hint and pass into route context.
                if any(p.get("name") == "hints" for p in planned):
                    try:
                        _hint_start = time.perf_counter()
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
                            _audit_internal_tool_execution(
                                request,
                                "hints",
                                (time.perf_counter() - _hint_start) * 1000.0,
                                parameters={"query": query[:200], "result_count": len(hint_snippets[:2])},
                            )
                    except Exception as exc:
                        _audit_internal_tool_execution(
                            request,
                            "hints",
                            0.0,
                            parameters={"query": query[:200]},
                            outcome="error",
                            error_message=str(exc),
                        )
                        logger.debug("semantic_tooling_hints_skipped error=%s", exc)

                # Auto-discovery summary: enrich context with capability overview.
                if _progressive_disclosure and any(p.get("name") == "discovery" for p in planned):
                    try:
                        _discovery_start = time.perf_counter()
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
                        _audit_internal_tool_execution(
                            request,
                            "discovery",
                            (time.perf_counter() - _discovery_start) * 1000.0,
                            parameters={
                                "query": query[:200],
                                "capability_count": int(request_context["tool_discovery"].get("capability_count", 0)),
                            },
                        )
                    except Exception as exc:
                        _audit_internal_tool_execution(
                            request,
                            "discovery",
                            0.0,
                            parameters={"query": query[:200]},
                            outcome="error",
                            error_message=str(exc),
                        )
                        logger.debug("semantic_tooling_discovery_skipped error=%s", exc)

                if (
                    _recall_memory is not None
                    and memory_recall_priority
                ):
                    try:
                        _memory_start = time.perf_counter()
                        request_context["memory_recall_attempted"] = True
                        request["audit_metadata"]["memory_recall_attempted"] = True
                        memory_result = await asyncio.wait_for(
                            _recall_memory(
                                query=query,
                                memory_types=None,
                                limit=3,
                                retrieval_mode="hybrid",
                            ),
                            timeout=2.0,
                        )
                        memory_rows = memory_result.get("results", []) if isinstance(memory_result, dict) else []
                        memory_summaries = [
                            str(row.get("summary") or row.get("content") or "").strip()
                            for row in memory_rows
                            if isinstance(row, dict) and str(row.get("summary") or row.get("content") or "").strip()
                        ]
                        if memory_summaries:
                            request_context["prior_memory"] = memory_summaries[:3]
                            request_context["memory_recall"] = memory_summaries[:3]
                            tooling_layer["memory_recall"] = memory_summaries[:2]
                        else:
                            request_context["memory_recall_miss"] = True
                            request["audit_metadata"]["memory_recall_miss"] = True
                            tooling_layer["memory_recall"] = ["no stored prior context matched this continuation query"]
                        tooling_layer["executed"].append("memory_recall")
                        _audit_internal_tool_execution(
                            request,
                            "recall_agent_memory",
                            (time.perf_counter() - _memory_start) * 1000.0,
                            parameters={
                                "query": query[:200],
                                "result_count": len(memory_summaries[:3]),
                                "memory_recall_miss": not bool(memory_summaries),
                            },
                        )
                    except Exception as exc:
                        _audit_internal_tool_execution(
                            request,
                            "recall_agent_memory",
                            0.0,
                            parameters={"query": query[:200]},
                            outcome="error",
                            error_message=str(exc),
                        )
                        logger.debug("semantic_tooling_memory_recall_skipped error=%s", exc)

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

            # Quality cache check (if enabled and appropriate)
            cache_enabled = bool(data.get("enable_cache", True))
            _llm_timeout_s = float(
                data.get("llm_timeout_s")
                or os.getenv("AI_QUERY_LLM_TIMEOUT_S", "120")
            )
            _route_kwargs: Dict[str, Any] = dict(
                query=query,
                mode=data.get("mode", "auto"),
                prefer_local=prefer_local,
                context=request_context,
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", 0.7)),
                generate_response=generate_response,
            )

            # Phase 8.10 — Parallel retrieval + cache check.
            # Start retrieval as a background task immediately so Qdrant embedding
            # and vector search begin while the (synchronous) cache lookup runs.
            # On cache hit the retrieval task is cancelled; on miss the result is
            # already in-flight, reducing effective latency for cache-miss requests.
            _retrieval_task: Optional[asyncio.Task] = None
            cached_result = None
            if cache_enabled and _should_use_cache(query):
                # Kick off retrieval in background before blocking on cache lookup
                _retrieval_task = asyncio.create_task(
                    asyncio.wait_for(_route_search(**_route_kwargs), timeout=_llm_timeout_s)
                )
                cached_result = _get_cached_response(query, context=request_context)

            if cached_result:
                # Cache hit — cancel pre-fetched retrieval task, return cached response
                if _retrieval_task is not None and not _retrieval_task.done():
                    _retrieval_task.cancel()
                cached_response, cache_metadata = cached_result
                result = {
                    "response": cached_response,
                    "from_cache": True,
                    "cache_metadata": cache_metadata,
                    "query": query,
                }
                logger.info(f"Cache hit for query: {query[:60]}...")
            else:
                # Cache miss — await pre-fetched task if already started, else start now
                if _retrieval_task is None:
                    _retrieval_task = asyncio.create_task(
                        asyncio.wait_for(_route_search(**_route_kwargs), timeout=_llm_timeout_s)
                    )
                try:
                    result = await _retrieval_task
                except asyncio.TimeoutError:
                    logger.warning(
                        "route_search_llm_timeout: query truncated after %.0fs (generate_response=%s)",
                        _llm_timeout_s,
                        generate_response,
                    )
                    if generate_response:
                        # Fallback: return vector results without LLM generation
                        result = await _route_search(
                            query=query,
                            mode=data.get("mode", "auto"),
                            prefer_local=prefer_local,
                            context=request_context,
                            limit=int(data.get("limit", 5)),
                            keyword_limit=int(data.get("keyword_limit", 5)),
                            score_threshold=float(data.get("score_threshold", 0.7)),
                            generate_response=False,
                        )
                    else:
                        result = {"results": [], "error": "route_search_timeout"}
                    result["truncated"] = True
                    result["truncation_reason"] = "llm_timeout"

                # Cache the response if it has quality metrics
                if cache_enabled and result.get("response"):
                    quality_score = result.get("quality_score", 0)
                    confidence = result.get("confidence", 1.0)

                    # Only cache if we have a quality score (from critic evaluation)
                    if quality_score > 0:
                        _cache_response(
                            query=query,
                            response=result["response"],
                            quality_score=quality_score,
                            confidence=confidence,
                            context=request_context,
                        )
            if semantic_tooling_autorun:
                result["tooling_layer"] = _compact_tooling_layer_response(
                    tooling_layer,
                    include_debug_metadata=include_debug_metadata,
                )
            if request_context.get("memory_recall_attempted"):
                metadata = result.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                    result["metadata"] = metadata
                metadata["memory_recall_attempted"] = True
                metadata["memory_recall_miss"] = bool(request_context.get("memory_recall_miss"))
            if request_context.get("memory_recall"):
                result["memory_recall"] = request_context.get("memory_recall")
            if request_context.get("prior_memory"):
                result["prior_memory"] = request_context.get("prior_memory")
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                result["active_lesson_refs"] = lesson_refs
            if prompt_coaching:
                result["prompt_coaching"] = _query_prompt_coaching_response(
                    prompt_coaching,
                    include_debug_metadata=include_debug_metadata,
                )
                metadata = result.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                    result["metadata"] = metadata
                metadata["prompt_coaching"] = _compact_prompt_coaching_metadata(prompt_coaching)
            metadata = result.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                result["metadata"] = metadata
            metadata["orchestration"] = {
                "requesting_agent": orchestration["requesting_agent"],
                "requester_role": orchestration["requester_role"],
                "delegate_via_coordinator_only": orchestration["delegate_via_coordinator_only"],
            }
            if lesson_refs:
                metadata["active_lesson_refs"] = lesson_refs
            result["orchestration"] = orchestration
            request["audit_metadata"]["semantic_autorun_planned"] = len(tooling_layer.get("planned_tools", []))
            request["audit_metadata"]["semantic_autorun_executed"] = len(tooling_layer.get("executed", []))
            request["audit_metadata"]["route_strategy"] = str(result.get("route", "unknown"))
            request["audit_metadata"]["strategy_tag"] = str(result.get("route", "unknown"))
            request["audit_metadata"]["backend"] = str(result.get("backend", "unknown"))
            backend_reason_class = str(result.get("backend_reason_class", "") or "").strip()
            if backend_reason_class:
                request["audit_metadata"]["backend_reason_class"] = backend_reason_class
            response_max_tokens = result.get("response_max_tokens")
            if isinstance(response_max_tokens, int):
                request["audit_metadata"]["response_max_tokens"] = response_max_tokens
            local_inference_lane = str(result.get("local_inference_lane", "") or "").strip()
            if local_inference_lane:
                request["audit_metadata"]["local_inference_lane"] = local_inference_lane
            local_inference_lane_reason = str(result.get("local_inference_lane_reason", "") or "").strip()
            if local_inference_lane_reason:
                request["audit_metadata"]["local_inference_lane_reason"] = local_inference_lane_reason
            task_complexity = result.get("task_complexity")
            if isinstance(task_complexity, dict):
                task_complexity_reason = str(task_complexity.get("reason", "") or "").strip()
                if task_complexity_reason:
                    request["audit_metadata"]["task_complexity_reason"] = task_complexity_reason
                task_complexity_type = str(task_complexity.get("type", "") or "").strip()
                if task_complexity_type:
                    request["audit_metadata"]["task_complexity_type"] = task_complexity_type
                task_complexity_tokens = task_complexity.get("tokens")
                if isinstance(task_complexity_tokens, int):
                    request["audit_metadata"]["task_complexity_tokens"] = task_complexity_tokens
                if "local_suitable" in task_complexity:
                    request["audit_metadata"]["task_complexity_local_suitable"] = bool(
                        task_complexity.get("local_suitable")
                    )
                if "remote_required" in task_complexity:
                    request["audit_metadata"]["task_complexity_remote_required"] = bool(
                        task_complexity.get("remote_required")
                    )
            retrieval_profile = result.get("retrieval_profile")
            if isinstance(retrieval_profile, dict):
                request["audit_metadata"]["retrieval_profile"] = str(
                    retrieval_profile.get("profile", "standard")
                )
                collections = retrieval_profile.get("collections")
                if isinstance(collections, list):
                    request["audit_metadata"]["retrieval_collection_count"] = len(collections)
            synthesis_fallback = None
            result_payload = result.get("results")
            if isinstance(result_payload, dict):
                synthesis_fallback = result_payload.get("synthesis_fallback")
            if isinstance(synthesis_fallback, dict):
                fallback_reason = str(synthesis_fallback.get("reason", "") or "").strip()
                if fallback_reason:
                    request["audit_metadata"]["fallback_reason"] = fallback_reason
                fallback_status = synthesis_fallback.get("status_code")
                if isinstance(fallback_status, int):
                    request["audit_metadata"]["fallback_status_code"] = fallback_status
                original_backend = str(synthesis_fallback.get("original_backend", "") or "").strip()
                if original_backend:
                    request["audit_metadata"]["fallback_original_backend"] = original_backend
            prompt_cache = None
            if isinstance(result_payload, dict):
                prompt_cache = result_payload.get("prompt_cache")
            if isinstance(prompt_cache, dict):
                request["audit_metadata"]["prompt_cache_policy_enabled"] = bool(
                    prompt_cache.get("policy_enabled")
                )
                cached_tokens = prompt_cache.get("cached_tokens")
                if isinstance(cached_tokens, int):
                    request["audit_metadata"]["prompt_cache_cached_tokens"] = cached_tokens
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
            audit_metadata = request.get("audit_metadata")
            if isinstance(audit_metadata, dict):
                audit_metadata.setdefault("generate_response", generate_response if "generate_response" in locals() else False)
                prefer_local = bool(data.get("prefer_local", True)) if "data" in locals() and isinstance(data, dict) else True
                if str(audit_metadata.get("backend", "unknown")) == "unknown":
                    audit_metadata["backend"] = "local" if prefer_local else "remote"
            return web.json_response({"error": "route_search_failed", "detail": str(exc)}, status=500)

    async def handle_orchestrate(request):
        """Phase 0 Slice 0.2 — unified front-door routing endpoint.

        POST /v1/orchestrate
        {
            "prompt":  "<query>",          # required
            "route":   "Explore",          # optional route alias (case-insensitive)
            "context": {},                 # optional, forwarded to /query
            "options": {}                  # optional, forwarded to /query
        }

        Resolves the route alias to a harness profile, injects it into the
        query context, and proxies to the existing /query handler.
        Adds X-AI-Route-Alias and X-AI-Profile-Resolved response headers.
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        prompt = (data.get("prompt") or data.get("query") or "").strip()
        if not prompt:
            return web.json_response({"error": "'prompt' is required"}, status=400)

        # Resolve route alias → harness profile
        raw_route = str(data.get("route") or "default").strip()
        try:
            from route_aliases import resolve_route_alias as _resolve_alias
            resolved_profile = _resolve_alias(raw_route)
        except Exception:
            resolved_profile = "default"

        # Build forwarding payload for handle_query
        context = data.get("context") if isinstance(data.get("context"), dict) else {}
        context["routed_profile"] = resolved_profile
        context["route_alias"] = raw_route

        options = data.get("options") if isinstance(data.get("options"), dict) else {}
        forwarded_payload = {
            "prompt": prompt,
            "context": context,
            "generate_response": bool(options.get("generate_response", False)),
            "prefer_local": bool(options.get("prefer_local", True)),
            "mode": options.get("mode", "hybrid"),
        }
        if "limit" in options:
            forwarded_payload["limit"] = options["limit"]

        # Wrap as a minimal shim so handle_query can consume it
        import json as _json_inner

        class _ShimRequest:
            def __init__(self, body: bytes, real_req):
                self._body = body
                self.headers = real_req.headers
                self.match_info = real_req.match_info
                self.method = "POST"
                self.path = "/query"
                self.rel_url = real_req.rel_url
                self.app = getattr(real_req, "app", None)
                self._audit: dict = {}

            async def json(self):
                return _json_inner.loads(self._body)

            def __setitem__(self, key, val):
                self._audit[key] = val

            def __getitem__(self, key):
                return self._audit[key]

            def get(self, key, default=None):
                return self._audit.get(key, default)

        shim = _ShimRequest(_json_inner.dumps(forwarded_payload).encode(), request)
        resp = await handle_query(shim)

        # Inject routing telemetry headers on success
        try:
            resp.headers["X-AI-Route-Alias"] = raw_route
            resp.headers["X-AI-Profile-Resolved"] = resolved_profile
        except Exception:
            pass
        return resp

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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"error": "tree_search_failed", "detail": str(exc)}, status=500)


    # Phase 12.4: handle_memory_store, handle_memory_recall, handle_harness_eval,
    # handle_qa_check, handle_harness_stats, handle_harness_scorecard,
    # handle_multi_turn_context, handle_session_info, handle_clear_session,
    # handle_discover_capabilities, handle_token_budget_recommendations,
    # handle_apply_proposal extracted to memory_context_handlers.py


    # Phase 12.4: handle_hints, handle_hints_feedback, handle_agent_status extracted
    # to hints_handlers.py (routes registered via hints_handlers.register_routes).


    # Initialize rate limiter with endpoint-specific limits
    rate_limiter_config = RateLimiterConfig(
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        default_rpm=int(os.getenv("RATE_LIMIT_DEFAULT_RPM", "100")),
        default_rph=int(os.getenv("RATE_LIMIT_DEFAULT_RPH", "3000")),
        burst_multiplier=float(os.getenv("RATE_LIMIT_BURST_MULTIPLIER", "1.5")),
        endpoint_limits={
            "/": int(os.getenv("RATE_LIMIT_ROOT_RPM", "300")),
            "/query": int(os.getenv("RATE_LIMIT_QUERY_RPM", "30")),
            "/search/tree": int(os.getenv("RATE_LIMIT_TREE_RPM", "20")),
            "/hints": int(os.getenv("RATE_LIMIT_HINTS_RPM", "60")),
            "/harness/eval": int(os.getenv("RATE_LIMIT_EVAL_RPM", "20")),
            "/workflow": int(os.getenv("RATE_LIMIT_WORKFLOW_RPM", "30")),
            "/a2a": int(os.getenv("RATE_LIMIT_A2A_RPM", "300")),
        },
        exempt_paths={"/health", "/metrics", "/health/detailed", "/health/aggregate"},
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

    # Phase 2.4: Initialize YAML workflow system
    if YAML_WORKFLOWS_AVAILABLE:
        try:
            yaml_workflow_handlers.init(workflows_dir="ai-stack/workflows/examples")
            logger.info("YAML workflow system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize YAML workflows: {e}")

    # Phase 1: WebSocket alert handler
    async def handle_alerts_websocket(request):
        """
        WebSocket endpoint for real-time browser alert notifications.

        Clients connect to this endpoint to receive alert updates in real-time.
        Alerts are sent as JSON messages with alert details.
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        alert_engine = _get_alert_engine()
        alert_engine.register_websocket(ws)

        try:
            logger.info(f"WebSocket client connected to /ws/alerts from {request.remote}")

            # Send current active alerts on connection
            active_alerts = alert_engine.get_active_alerts()
            if active_alerts:
                for alert in active_alerts[:10]:  # Send up to 10 most recent
                    await ws.send_json(alert.to_dict())

            # Keep connection alive and listen for client messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        action = data.get("action")

                        # Support client actions like acknowledge/resolve
                        if action == "acknowledge" and "alert_id" in data:
                            await alert_engine.acknowledge_alert(data["alert_id"])
                        elif action == "resolve" and "alert_id" in data:
                            await alert_engine.resolve_alert(data["alert_id"])
                        elif action == "get_active":
                            alerts = alert_engine.get_active_alerts()
                            await ws.send_json({
                                "action": "active_alerts",
                                "alerts": [a.to_dict() for a in alerts]
                            })
                        elif action == "get_stats":
                            stats = alert_engine.get_stats()
                            await ws.send_json({
                                "action": "stats",
                                "data": stats
                            })
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from WebSocket client: {msg.data}")
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")

        finally:
            alert_engine.unregister_websocket(ws)
            logger.info(f"WebSocket client disconnected from /ws/alerts")

        return ws

    # Phase 5 — Model Optimization HTTP handlers
    # -------------------------------------------------------------------------
    # Phase 4.2 + Phase 1.3 + review/acceptance — extracted to orchestration_handlers.py
    # -------------------------------------------------------------------------

    openai_a2a_handlers.register_routes(http_app)
    ops_handlers.register_routes(http_app)
    http_app.router.add_get("/status", handle_status)
    http_app.router.add_post("/augment_query", handle_augment_query)
    http_app.router.add_post("/query", handle_query)
    http_app.router.add_post("/v1/orchestrate", handle_orchestrate)  # Phase 0 Slice 0.2
    http_app.router.add_post("/search/tree", handle_tree_search)
    memory_context_handlers.register_routes(http_app)
    hints_handlers.register_routes(http_app)
    workflow_session_handlers.register_routes(http_app)
    ai_coordinator_handlers.register_routes(http_app)  # Phase 12.4: extracted to ai_coordinator_handlers.py
    # Phase 12.1/12.2 — Model Coordination + LLM Router endpoints
    llm_router_handlers.register_routes(http_app)
    # Batch 3.2 — PRSI Action Execution endpoints
    prsi_handlers.register_routes(http_app)
    runtime_control_handlers.register_routes(http_app)

    # Phase 5 — Model Optimization + Advanced Features endpoints
    model_opt_handlers.register_routes(http_app)
    # Phase 4.2 + 1.3 + review/acceptance
    orchestration_handlers.register_routes(http_app)

    # Phase 1: WebSocket alert endpoint
    http_app.router.add_get("/ws/alerts", handle_alerts_websocket)


    # ── Agent management endpoints (subprocess agent orchestration) ────────
    _AGENT_STATE: Dict[str, Any] = {}  # In-memory agent state store
    _LOCAL_AGENT_CODE = '''
import asyncio, json, os, sys, time, httpx, pathlib
AGENT_ID = os.environ["AGENT_ID"]
AGENT_ROLE = os.environ["AGENT_ROLE"]
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
AGENT_TASK = os.environ["AGENT_TASK"]
SWITCHBOARD_URL = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085")
STATE_FILE = os.environ.get("AGENT_STATE_FILE", "")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "4096"))
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))

def _profile_for_role(role):
    normalized = str(role or "").strip().lower()
    if normalized == "coder":
        return "local-tool-calling"
    return "continue-local"

def _write_state(state):
    if STATE_FILE:
        p = pathlib.Path(STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))

async def run():
    state = {"id": AGENT_ID, "role": AGENT_ROLE, "status": "running",
             "started_at": time.time(), "tool_calls": 0}
    _write_state(state)
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": AGENT_TASK},
        ]
        async with httpx.AsyncClient(timeout=float(os.environ.get("AGENT_TIMEOUT", "120"))) as client:
            resp = await client.post(
                f"{SWITCHBOARD_URL}/v1/chat/completions",
                json={"messages": messages, "temperature": TEMPERATURE,
                      "max_tokens": MAX_TOKENS, "stream": False},
                headers={"X-AI-Profile": _profile_for_role(AGENT_ROLE),
                         "X-AI-Route": "local"},
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            state.update({"status": "completed", "result": content,
                          "completed_at": time.time()})
            _write_state(state)
            print(json.dumps({"ok": True, "content": content, "agent_id": AGENT_ID}))
    except Exception as e:
        state.update({"status": "failed", "error": str(e), "completed_at": time.time()})
        _write_state(state)
        print(json.dumps({"ok": False, "error": str(e), "agent_id": AGENT_ID}), file=sys.stderr)
        sys.exit(1)
asyncio.run(run())
'''

    async def _spawn_local_agent_instance(
        *,
        role: str,
        task_text: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        timeout_sec: float,
        team_id: str | None = None,
    ) -> tuple[Dict[str, Any], int]:
        agent_id = str(uuid4())[:8]
        state_file = f"/tmp/agent-spawner/agent-{agent_id}.json"
        Path("/tmp/agent-spawner").mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update({
            "AGENT_ID": agent_id,
            "AGENT_ROLE": role,
            "AGENT_TASK": task_text,
            "AGENT_SYSTEM_PROMPT": system_prompt,
            "AGENT_STATE_FILE": state_file,
            "AGENT_MAX_TOKENS": str(max_tokens),
            "AGENT_TEMPERATURE": str(temperature),
            "AGENT_TIMEOUT": str(timeout_sec),
            "SWITCHBOARD_URL": Config.SWITCHBOARD_URL,
            "PYTHONUNBUFFERED": "1",
        })

        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", _LOCAL_AGENT_CODE,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        instance = {
            "id": agent_id,
            "role": role,
            "task": task_text,
            "status": "running",
            "pid": proc.pid,
            "started_at": datetime.now().isoformat(),
            "state_file": state_file,
        }
        if team_id:
            instance["team_id"] = team_id
        _AGENT_STATE[agent_id] = instance

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            instance["status"] = "timeout"
            instance["completed_at"] = datetime.now().isoformat()
            return instance, 504

        if proc.returncode != 0:
            instance["status"] = "failed"
            instance["error"] = stderr.decode(errors="replace")[:500] if stderr else "unknown"
            instance["completed_at"] = datetime.now().isoformat()
            return instance, 500

        try:
            result = json.loads(stdout.decode())
            if result.get("ok"):
                instance["status"] = "completed"
                instance["result"] = result.get("content", "")
            else:
                instance["status"] = "failed"
                instance["error"] = result.get("error", "unknown")
        except (json.JSONDecodeError, UnicodeDecodeError):
            instance["status"] = "completed"
            instance["result"] = stdout.decode(errors="replace")[:2000]

        instance["completed_at"] = datetime.now().isoformat()
        return instance, 201

    async def handle_agents_status(request: web.Request) -> web.Response:
        """GET /control/agents — list all agent instances"""
        instance_id = request.query.get("id")
        if instance_id:
            inst = _AGENT_STATE.get(instance_id)
            if not inst:
                return web.json_response({"error": f"Instance {instance_id} not found"})
            return web.json_response(inst)
        return web.json_response({
            "active_agents": sum(1 for v in _AGENT_STATE.values() if v.get("status") in ("pending", "running")),
            "total_agents": len(_AGENT_STATE),
            "instances": list(_AGENT_STATE.values()),
        })

    async def handle_agents_spawn(request: web.Request) -> web.Response:
        """POST /control/agents/spawn — spawn a single agent subprocess"""
        data = await request.json()
        role = data.get("role", "coordinator")
        task_text = data.get("task", "")
        if not task_text:
            return web.json_response({"error": "task required"}, status=400)
        instance, status_code = await _spawn_local_agent_instance(
            role=role,
            task_text=task_text,
            system_prompt=data.get("system_prompt", f"You are a {role} agent. Execute the task."),
            max_tokens=int(data.get("max_tokens", 4096)),
            temperature=float(data.get("temperature", 0.3)),
            timeout_sec=float(data.get("timeout", 120)),
        )
        return web.json_response(instance, status=status_code)

    async def handle_agents_team(request: web.Request) -> web.Response:
        """POST /control/agents/team — spawn multiple agents in parallel"""
        data = await request.json()
        task_text = data.get("task", "")
        if not task_text:
            return web.json_response({"error": "task required"}, status=400)

        roles = data.get("roles", ["coordinator", "coder", "reviewer"])
        team_id = str(uuid4())[:8]
        Path("/tmp/agent-spawner").mkdir(parents=True, exist_ok=True)

        role_prompts = data.get("role_prompts", {}) if isinstance(data.get("role_prompts"), dict) else {}
        timeout_sec = float(data.get("timeout", 120))
        max_tokens = int(data.get("max_tokens", 4096))
        temperature = float(data.get("temperature", 0.3))

        async def _run_role(role: str) -> tuple[Dict[str, Any], int]:
            default_prompt = f"You are a {role} agent. Execute the assigned team slice and return only your result."
            return await _spawn_local_agent_instance(
                role=role,
                task_text=task_text,
                system_prompt=str(role_prompts.get(role) or data.get("system_prompt") or default_prompt),
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_sec=timeout_sec,
                team_id=team_id,
            )

        member_results = await asyncio.gather(*[_run_role(role) for role in roles])
        members = [result for result, _status in member_results]
        statuses = [status for _result, status in member_results]
        if all(status == 201 for status in statuses):
            team_status = "completed"
            response_status = 201
        elif any(status == 201 for status in statuses):
            team_status = "partial"
            response_status = 207
        elif any(status == 504 for status in statuses):
            team_status = "timeout"
            response_status = 504
        else:
            team_status = "failed"
            response_status = 500

        return web.json_response({
            "team_id": team_id,
            "task": task_text,
            "roles": roles,
            "members": members,
            "status": team_status,
            "summary": {
                "completed": sum(1 for item in members if item.get("status") == "completed"),
                "failed": sum(1 for item in members if item.get("status") == "failed"),
                "timed_out": sum(1 for item in members if item.get("status") == "timeout"),
            },
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        }, status=response_status)

    async def handle_agents_kill(request: web.Request) -> web.Response:
        """POST /control/agents/kill — kill agent(s)"""
        data = await request.json()
        instance_id = data.get("id")
        if instance_id:
            inst = _AGENT_STATE.get(instance_id)
            if inst and inst.get("pid"):
                try:
                    os.kill(inst["pid"], signal.SIGTERM)
                    inst["status"] = "killed"
                    inst["completed_at"] = datetime.now().isoformat()
                    return web.json_response({"killed": instance_id})
                except ProcessLookupError:
                    inst["status"] = "killed"
                    return web.json_response({"killed": instance_id})
            return web.json_response({"error": "not found or no PID"}, status=404)
        # Kill all
        killed = []
        for iid, inst in _AGENT_STATE.items():
            if inst.get("status") in ("running", "pending") and inst.get("pid"):
                try:
                    os.kill(inst["pid"], signal.SIGTERM)
                    killed.append(iid)
                except ProcessLookupError:
                    killed.append(iid)
                inst["status"] = "killed"
                inst["completed_at"] = datetime.now().isoformat()
        return web.json_response({"killed": killed, "count": len(killed)})

    async def handle_agents_roles(request: web.Request) -> web.Response:
        """GET /control/agents/roles — list available agent roles"""
        return web.json_response({
            "roles": {
                "coordinator": {
                    "description": "Orchestrates agent teams, delegates tasks, aggregates results",
                    "tools": ["shell", "file_read", "delegate"],
                },
                "coder": {
                    "description": "Implements code changes, writes tests, fixes bugs",
                    "tools": ["shell", "file_read", "file_write", "code_execution"],
                },
                "reviewer": {
                    "description": "Reviews code for correctness, security, performance, quality",
                    "tools": ["shell", "file_read", "code_execution"],
                },
                "researcher": {
                    "description": "Gathers context, searches knowledge base, finds documentation",
                    "tools": ["shell", "file_read", "file_search"],
                },
                "planner": {
                    "description": "Breaks complex tasks into phases, identifies dependencies and risks",
                    "tools": ["shell", "file_read", "file_search"],
                },
            }
        })

    http_app.router.add_get("/control/agents", handle_agents_status)
    http_app.router.add_get("/control/agents/roles", handle_agents_roles)
    http_app.router.add_post("/control/agents/spawn", handle_agents_spawn)
    http_app.router.add_post("/control/agents/team", handle_agents_team)
    http_app.router.add_post("/control/agents/kill", handle_agents_kill)

    # ── Task Manager (IndyDevDan polling-based pattern) ────────────────────
    _TASK_QUEUE: List[Dict[str, Any]] = []  # In-memory task queue

    async def handle_task_manager_poll(request: web.Request) -> web.Response:
        """POST /control/task-manager/poll — poll for tasks to work on."""
        try:
            data = await request.json()
            source = data.get("source", "local")
            status_filter = data.get("status_filter", "todo")
            max_tasks = int(data.get("max_tasks", 5))
            agent = data.get("agent", "codex")

            # Filter tasks by status and source
            available_tasks = [
                t for t in _TASK_QUEUE
                if t.get("status") == status_filter
                and (source == "local" or t.get("source") == source)
            ][:max_tasks]

            # Mark polled tasks as assigned
            for task in available_tasks:
                task["status"] = "in_progress"
                task["assigned_to"] = agent
                task["assigned_at"] = time.time()

            return web.json_response({
                "status": "ok",
                "source": source,
                "tasks": available_tasks,
                "count": len(available_tasks),
                "remaining": len([t for t in _TASK_QUEUE if t.get("status") == "todo"]),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_task_manager_complete(request: web.Request) -> web.Response:
        """POST /control/task-manager/complete — mark a task as completed."""
        try:
            data = await request.json()
            task_id = data.get("task_id", "")
            result = data.get("result", "completed")
            evidence = data.get("evidence", "")

            task = next((t for t in _TASK_QUEUE if t.get("id") == task_id), None)
            if not task:
                return web.json_response({"error": f"Task {task_id} not found"}, status=404)

            task["status"] = result
            task["completed_at"] = time.time()
            task["evidence"] = evidence

            return web.json_response({
                "status": "ok",
                "task_id": task_id,
                "result": result,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_task_manager_create(request: web.Request) -> web.Response:
        """POST /control/task-manager/create — create a new task."""
        try:
            data = await request.json()
            title = data.get("title", "")
            if not title:
                return web.json_response({"error": "title required"}, status=400)

            task_id = f"task-{uuid4().hex[:8]}"
            task = {
                "id": task_id,
                "title": title,
                "description": data.get("description", ""),
                "source": data.get("source", "local"),
                "priority": data.get("priority", "normal"),
                "assignee": data.get("assignee", ""),
                "status": "todo",
                "created_at": time.time(),
            }
            _TASK_QUEUE.append(task)

            return web.json_response({
                "status": "ok",
                "task": task,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/task-manager/poll", handle_task_manager_poll)
    http_app.router.add_post("/control/task-manager/complete", handle_task_manager_complete)
    http_app.router.add_post("/control/task-manager/create", handle_task_manager_create)

    # ── Agent-to-Agent Review Handoff (IndyDevDan pattern) ─────────────────
    _REVIEW_QUEUE: Dict[str, Dict[str, Any]] = {}  # session_id -> review state

    def _load_review_artifact_preview(
        artifact_path: str,
        inline_content: str,
        max_chars: int = 6000,
    ) -> Dict[str, Any]:
        preview = str(inline_content or "").strip()
        source = "inline"
        resolved_path = str(artifact_path or "").strip()
        if not preview and resolved_path:
            candidate = Path(resolved_path)
            candidate_paths = [candidate]
            if not candidate.is_absolute():
                candidate_paths.append(Path(__file__).resolve().parents[3] / candidate)
            existing_candidate = next((item for item in candidate_paths if item.exists() and item.is_file()), None)
            if existing_candidate:
                try:
                    preview = existing_candidate.read_text(encoding="utf-8", errors="replace")[:max_chars]
                    source = "file"
                    resolved_path = str(existing_candidate)
                except Exception as exc:
                    preview = f"[artifact preview unavailable: {exc}]"
                    source = "error"
        elif preview:
            preview = preview[:max_chars]
        return {
            "artifact_path": resolved_path,
            "preview": preview,
            "preview_source": source,
            "preview_truncated": len(preview) >= max_chars if preview else False,
        }

    def _parse_review_agent_result(result_text: str) -> Dict[str, Any]:
        raw = str(result_text or "").strip()
        parsed: Dict[str, Any] = {}
        if not raw:
            return {
                "decision": "needs_manual_review",
                "reason": "reviewer returned empty output",
                "evidence": "",
                "feedback": "",
                "suggested_fixes": [],
                "raw_result": raw,
            }
        try:
            candidate = json.loads(raw)
            if isinstance(candidate, dict):
                parsed = candidate
        except json.JSONDecodeError:
            parsed = {}

        decision = str(parsed.get("decision", "") or "").strip().lower()
        if decision not in {"accept", "accepted", "approve", "approved", "reject", "rejected"}:
            lowered = raw.lower()
            if any(token in lowered for token in ("\"decision\":\"accept", "\"decision\": \"accept", "approved", "accept")):
                decision = "accept"
            elif any(token in lowered for token in ("\"decision\":\"reject", "\"decision\": \"reject", "rejected", "reject")):
                decision = "reject"
            else:
                decision = "needs_manual_review"

        return {
            "decision": "accept" if decision.startswith("accept") or decision.startswith("approv") else (
                "reject" if decision.startswith("reject") else "needs_manual_review"
            ),
            "reason": str(parsed.get("reason", "") or "").strip(),
            "evidence": str(parsed.get("evidence", "") or "").strip(),
            "feedback": str(parsed.get("feedback", "") or "").strip(),
            "suggested_fixes": (
                [str(item).strip() for item in parsed.get("suggested_fixes", []) if str(item).strip()]
                if isinstance(parsed.get("suggested_fixes"), list) else []
            ),
            "raw_result": raw[:4000],
        }

    async def handle_review_agent_handoff(request: web.Request) -> web.Response:
        """POST /control/review/agent-handoff — hand off work for review."""
        try:
            data = await request.json()
            from_agent = data.get("from_agent", "codex")
            to_agent = data.get("to_agent", "qwen")
            session_id = data.get("session_id") or f"review-{uuid4().hex[:8]}"
            artifact_type = data.get("artifact_type", "code")
            artifact_path = data.get("artifact_path", "")
            review_criteria = data.get("review_criteria", ["correctness", "style"])
            auto_merge = data.get("auto_merge", False)
            timeout_sec = float(data.get("timeout", 45))
            artifact_preview = _load_review_artifact_preview(
                str(artifact_path or ""),
                str(data.get("artifact_content") or data.get("artifact_excerpt") or ""),
            )

            review = {
                "session_id": session_id,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "artifact_type": artifact_type,
                "artifact_path": artifact_path,
                "artifact_preview_source": artifact_preview["preview_source"],
                "review_criteria": review_criteria,
                "auto_merge": auto_merge,
                "status": "running_review",
                "created_at": time.time(),
                "history": [
                    {
                        "event": "handoff_initiated",
                        "from": from_agent,
                        "to": to_agent,
                        "timestamp": time.time(),
                    }
                ],
            }
            _REVIEW_QUEUE[session_id] = review

            reviewer_prompt = (
                "Review the supplied artifact and return strict JSON only.\n"
                "Schema:\n"
                "{\"decision\":\"accept|reject\",\"reason\":\"...\",\"evidence\":\"...\","
                "\"feedback\":\"...\",\"suggested_fixes\":[\"...\"]}\n"
                "Use decision=accept only when the artifact meets the stated criteria."
            )
            review_task = (
                f"Review handoff session: {session_id}\n"
                f"From agent: {from_agent}\n"
                f"Reviewer agent role requested: {to_agent}\n"
                f"Artifact type: {artifact_type}\n"
                f"Artifact path: {artifact_preview['artifact_path'] or '[none provided]'}\n"
                f"Review criteria: {', '.join(str(item) for item in review_criteria)}\n"
                "Artifact preview:\n"
                f"{artifact_preview['preview'] or '[no artifact preview available]'}"
            )
            reviewer_instance, reviewer_status = await _spawn_local_agent_instance(
                role="reviewer",
                task_text=review_task,
                system_prompt=reviewer_prompt,
                max_tokens=int(data.get("max_tokens", 400)),
                temperature=float(data.get("temperature", 0.1)),
                timeout_sec=timeout_sec,
            )
            review["review_agent_instance_id"] = reviewer_instance.get("id")
            review["review_agent_status"] = reviewer_instance.get("status")
            review["review_agent_result"] = reviewer_instance.get("result", "")

            if reviewer_status == 201 and reviewer_instance.get("status") == "completed":
                parsed_result = _parse_review_agent_result(str(reviewer_instance.get("result", "")))
                review["review_result"] = parsed_result
                if parsed_result["decision"] == "accept":
                    review["status"] = "accepted"
                    review["accepted_at"] = time.time()
                    review["accepted_by"] = to_agent
                    review["acceptance_reason"] = parsed_result["reason"] or "accepted by delegated reviewer"
                    review["acceptance_evidence"] = parsed_result["evidence"]
                    review["history"].append({
                        "event": "review_accepted",
                        "by": to_agent,
                        "reason": review["acceptance_reason"],
                        "timestamp": time.time(),
                    })
                elif parsed_result["decision"] == "reject":
                    review["status"] = "rejected"
                    review["rejected_at"] = time.time()
                    review["rejected_by"] = to_agent
                    review["rejection_reason"] = parsed_result["reason"] or "rejected by delegated reviewer"
                    review["feedback"] = parsed_result["feedback"]
                    review["suggested_fixes"] = parsed_result["suggested_fixes"]
                    review["history"].append({
                        "event": "review_rejected",
                        "by": to_agent,
                        "reason": review["rejection_reason"],
                        "timestamp": time.time(),
                    })
                else:
                    review["status"] = "pending_review"
                    review["history"].append({
                        "event": "review_needs_manual_followup",
                        "by": to_agent,
                        "reason": parsed_result["reason"] or "delegated reviewer returned inconclusive output",
                        "timestamp": time.time(),
                    })
            else:
                review["status"] = "pending_review"
                review["history"].append({
                    "event": "review_agent_unavailable",
                    "by": to_agent,
                    "reason": f"delegated reviewer finished with status={reviewer_instance.get('status', 'unknown')}",
                    "timestamp": time.time(),
                })

            return web.json_response({
                "status": "ok",
                "session_id": session_id,
                "review": review,
                "next_action": (
                    "merge" if review.get("status") == "accepted" and review.get("auto_merge")
                    else "manual merge required" if review.get("status") == "accepted"
                    else f"Agent {from_agent} should address feedback and resubmit" if review.get("status") == "rejected"
                    else f"Agent {to_agent} should review and call /control/review/accept or /control/review/reject"
                ),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_review_status(request: web.Request) -> web.Response:
        """GET /control/review/status — check review status."""
        try:
            session_id = request.query.get("session_id", "")
            if session_id:
                review = _REVIEW_QUEUE.get(session_id)
                if not review:
                    return web.json_response({"error": f"Review {session_id} not found"}, status=404)
                return web.json_response(review)

            return web.json_response({
                "pending_reviews": len([r for r in _REVIEW_QUEUE.values() if r.get("status") == "pending_review"]),
                "total_reviews": len(_REVIEW_QUEUE),
                "reviews": list(_REVIEW_QUEUE.values()),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_review_accept(request: web.Request) -> web.Response:
        """POST /control/review/accept — accept and approve a review."""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            review = _REVIEW_QUEUE.get(session_id)
            if not review:
                return web.json_response({"error": f"Review {session_id} not found"}, status=404)

            reviewer_agent = data.get("reviewer_agent", "codex")
            reason = data.get("reason", "approved")
            evidence = data.get("evidence", "")

            review["status"] = "accepted"
            review["accepted_at"] = time.time()
            review["accepted_by"] = reviewer_agent
            review["acceptance_reason"] = reason
            review["acceptance_evidence"] = evidence
            review["history"].append({
                "event": "review_accepted",
                "by": reviewer_agent,
                "reason": reason,
                "timestamp": time.time(),
            })

            return web.json_response({
                "status": "ok",
                "session_id": session_id,
                "accepted": True,
                "auto_merge": review.get("auto_merge", False),
                "next_action": "merge" if review.get("auto_merge") else "manual merge required",
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_review_reject(request: web.Request) -> web.Response:
        """POST /control/review/reject — reject a review with feedback."""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            review = _REVIEW_QUEUE.get(session_id)
            if not review:
                return web.json_response({"error": f"Review {session_id} not found"}, status=404)

            reviewer_agent = data.get("reviewer_agent", "codex")
            reason = data.get("reason", "")
            feedback = data.get("feedback", "")
            suggested_fixes = data.get("suggested_fixes", [])

            review["status"] = "rejected"
            review["rejected_at"] = time.time()
            review["rejected_by"] = reviewer_agent
            review["rejection_reason"] = reason
            review["feedback"] = feedback
            review["suggested_fixes"] = suggested_fixes
            review["history"].append({
                "event": "review_rejected",
                "by": reviewer_agent,
                "reason": reason,
                "timestamp": time.time(),
            })

            return web.json_response({
                "status": "ok",
                "session_id": session_id,
                "rejected": True,
                "feedback": feedback,
                "suggested_fixes": suggested_fixes,
                "next_action": f"Agent {review.get('from_agent')} should address feedback and resubmit",
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/review/agent-handoff", handle_review_agent_handoff)
    http_app.router.add_get("/control/review/status", handle_review_status)
    http_app.router.add_post("/control/review/accept", handle_review_accept)
    http_app.router.add_post("/control/review/reject", handle_review_reject)

    evidence_safety_handlers.register_routes(http_app)

    # Phase 2.4: Register YAML workflow routes
    if YAML_WORKFLOWS_AVAILABLE:
        try:
            yaml_workflow_handlers.register_routes(http_app)
            logger.info("YAML workflow routes registered")
        except Exception as e:
            logger.error(f"Failed to register YAML workflow routes: {e}")

    runner = web.AppRunner(
        http_app,
        access_log=access_logger,
        access_log_format=access_log_format,
    )
    await runner.setup()
    # Security: bind to HOST env var, default to localhost to prevent LAN exposure
    bind_host = os.getenv("HOST", "127.0.0.1")
    site = web.TCPSite(runner, bind_host, port)
    await site.start()

    logger.info("✓ Hybrid Coordinator HTTP server running on http://%s:%d", bind_host, port)

    # Keep server running
    await asyncio.Event().wait()
