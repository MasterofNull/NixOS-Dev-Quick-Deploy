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
import sys
from pathlib import Path

# Stability Backbone (Phase 55.2): Ensure shared utilities are on path
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SHARED_PATH = str(_REPO_ROOT / "ai-stack" / "mcp-servers")
if _SHARED_PATH not in sys.path:
    sys.path.insert(0, _SHARED_PATH)

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
from middleware.auth import API_KEY_HEADER as _API_KEY_HEADER  # R2.7: canonical header constant
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
from mlfq_scheduler import (
    MLFQAdmissionError,
    WorkloadDescriptor,
    get_scheduler,
)
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
import orchestration_graph_runner
import model_opt_handlers
import llm_router_handlers
import orchestration_handlers
import workflow_session_handlers
import hints_handlers
import memory_context_handlers
import agents_task_handlers
import evidence_safety_handlers
import ai_coordinator_handlers
import model_fleet_manager as _mfm
import agentic_memory_journal as _journal
import identity_handlers  # Phase 16.4: persistent identity kernel
import affective_handlers  # Phase 19: values signals / affective engine
import trading_handlers          # Phase 24: multi-agent trading framework (agent-agnostic HTTP API)
import auto_tool_select_handlers  # Phase 24: autonomous tool auto-selection for all agents
import context_summary_handlers   # Phase 25-007: agent context summarization + working memory
import intake_gateway              # Phase 26: Unified Agent Orchestration Gateway (UAG)
from inference_param_manager import get_ipm  # Phase B: Thermal + hardware state monitor
# Phase 54: Agentic-First Architecture Elevation
import memory_broker               # 54.1 — unified memory layer
import memory_superseder           # 55.1 — temporal memory supersession
import drift_analyzer              # 55.3 — reasoning drift detection
import memory_crystallizer         # 55.2 — crystalline session distillation
from extensions import memory_superseder as memory_superseder_routes
from extensions import drift_analyzer as drift_analyzer_routes
from extensions import memory_crystallizer as memory_crystallizer_routes
import intent_classifier           # 54.2 — semantic intent classification
import rag_augmentor               # 54.3 — active RAG pipeline
import trace_collector             # 54.5 — end-to-end query trace
import eval_runner                 # 54.6 — continuous evaluation
import agent_capability_registry   # Phase 26: dynamic agent capability registry
import domain_router               # Phase 26: domain classifier + team routing
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
    _workflow_memory_first_strategy,
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
_intent_classifier: Optional[Any] = None

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

# Phase 69.3 — TemporalGraph postgres client reference (set by init(), read by run_http_mode())
_POSTGRES_CLIENT: Optional[Any] = None

# Phase 11.2 — Health history tracking for trend analysis
from collections import deque
_HEALTH_HISTORY: deque = deque(maxlen=60)  # Last 60 snapshots (1 hour at 1/min)

_local_llm_healthy_ref: Optional[Callable] = None   # lambda: _local_llm_healthy
_local_llm_loading_ref: Optional[Callable] = None   # lambda: _local_llm_loading
_queue_depth_ref: Optional[Callable] = None          # lambda: _model_loading_queue_depth
_queue_max_ref: Optional[Callable] = None            # lambda: _MODEL_QUEUE_MAX
_embedding_cache_ref: Optional[Callable] = None      # Phase 21.3 — lambda: embedding_cache
_workflow_sessions_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Team-load concurrency control (prevents Qwen CPU/RAM exhaustion)
# ---------------------------------------------------------------------------
# MLFQ Task Prioritization & Concurrency Management
# Humans (interactive) get priority over automated agents (background/batch)
# via the MLFQScheduler.
# ---------------------------------------------------------------------------


# Reindex status — path matches REINDEX_OUTPUT injected by the systemd unit.
# aidb-reindex.sh writes {"status":"running"} at start and overwrites with the
# final result on completion so agents can detect a stale RAG corpus.
_REINDEX_STATUS_PATH: str = os.getenv(
    "REINDEX_OUTPUT",
    "/var/lib/ai-stack/hybrid/telemetry/aidb-reindex-latest.json",
)
_reindex_status_cache: Dict[str, Any] = {}
_reindex_status_ts: float = 0.0
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
# Orchestration lane/mode constants live in orchestration_utils (shared with runtime_manager)
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
        headers[_API_KEY_HEADER] = api_key
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
    token = request.headers.get(_API_KEY_HEADER) or request.headers.get("Authorization", "")
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
    token = request.headers.get(_API_KEY_HEADER) or request.headers.get("Authorization", "")
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
    _ORCHESTRATION_LANES,
    _ORCHESTRATION_COLLABORATOR_LANES,
    _ORCHESTRATION_REVIEW_LANES,
    _ORCHESTRATION_ESCALATION_LANES,
    _ORCHESTRATION_CONSENSUS_MODES,
    _ORCHESTRATION_SELECTION_STRATEGIES,
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
    postgres_client: Optional[Any] = None,
    intent_classifier: Optional[Any] = None,
    crystallizer_llm: Optional[Any] = None,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _augment_query, _route_search, _tree_search, _store_memory, _recall_memory
    global _run_harness_eval, _build_scorecard, _record_learning_feedback
    global _record_simple_feedback, _update_outcome, _get_variant_stats, _generate_dataset
    global _get_process_memory, _snapshot_stats, _error_payload, _wait_for_model
    global _multi_turn_manager, _progressive_disclosure, _feedback_api, _learning_pipeline
    global _COLLECTIONS, _HYBRID_STATS, _HARNESS_STATS, _CIRCUIT_BREAKERS, _SERVICE_NAME
    global _local_llm_healthy_ref, _local_llm_loading_ref, _queue_depth_ref, _queue_max_ref
    global _embedding_cache_ref, _intent_classifier
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
    _intent_classifier = intent_classifier

    # R2.2: inject runtime refs into StatusService
    from core import status_service as _status_service
    _status_service.configure(
        local_llm_healthy_ref=local_llm_healthy_ref,
        queue_depth_ref=queue_depth_ref,
        queue_max_ref=queue_max_ref,
    )

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
    # Phase 15.1 + 15.3: Model fleet manager + agentic memory journal
    _mfm.init()
    _journal.init(
        aidb_url=os.getenv("AIDB_URL", ""),
        aidb_api_key=_read_secret_file(os.getenv("AIDB_API_KEY_FILE", "")),
    )
    # Phase 54.1 — MemoryBroker: unified typed memory interface
    memory_broker.init(store_fn=_store_memory, recall_fn=_recall_memory)

    # Phase 54.3 — RagAugmentor: active RAG pipeline
    # Build a dedicated httpx client — journal stores only URL strings, has no _aidb_client attr.
    _aidb_key_54 = _read_secret_file(os.getenv("AIDB_API_KEY_FILE", ""))
    _aidb_url_54 = os.getenv("AIDB_URL", "http://127.0.0.1:8002").rstrip("/")
    _rag_aidb_client = httpx.AsyncClient(base_url=_aidb_url_54, timeout=10.0) if _aidb_url_54 else None
    rag_augmentor.init(
        aidb_client=_rag_aidb_client,
        aidb_api_key=_aidb_key_54,
    )

    # Phase 54.5 / 54.6 — TraceCollector + EvalRunner (share postgres_client)
    # postgres_client may be None if DB is unavailable; modules degrade gracefully
    global _POSTGRES_CLIENT
    _POSTGRES_CLIENT = postgres_client
    trace_collector.init(postgres_client=postgres_client)
    eval_runner.init(postgres_client=postgres_client)

    # Phase 16.4: Identity kernel
    identity_handlers.init()
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
    orchestration_graph_runner.init(error_payload_fn=_error_payload)
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


# ---------------------------------------------------------------------------
# handle_query helpers — each covers one phase of the query pipeline.
# All use module-level globals injected via init().
# ---------------------------------------------------------------------------

def _parse_query_input(data: Dict[str, Any]) -> tuple:
    """Extract and normalise all fields from the raw request body."""
    query = data.get("prompt") or data.get("query") or ""
    generate_response = bool(data.get("generate_response", False))
    prefer_local = bool(data.get("prefer_local", True))
    semantic_tooling_autorun = os.getenv("AI_SEMANTIC_TOOLING_AUTORUN", "true").lower() == "true"
    memory_recall_priority = _should_prioritize_memory_recall(query)
    request_context = data.get("context")
    if not isinstance(request_context, dict):
        request_context = {}
    orchestration = _coerce_orchestration_context(data)
    request_context["orchestration"] = orchestration
    include_debug_metadata = bool(data.get("include_debug_metadata") or data.get("debug"))
    return (
        query, generate_response, prefer_local, semantic_tooling_autorun,
        memory_recall_priority, request_context, orchestration, include_debug_metadata,
    )


def _init_query_audit_and_tooling(
    request,
    orchestration: Dict[str, Any],
    generate_response: bool,
    semantic_tooling_autorun: bool,
    memory_recall_priority: bool,
) -> Dict[str, Any]:
    """Initialise request['audit_metadata'] and return a blank tooling_layer dict."""
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
        "generate_response_requested": generate_response,
        "generate_response": generate_response,
        "memory_recall_priority": memory_recall_priority,
        "memory_recall_attempted": False,
        "backend": "unknown",
    }
    return {
        "enabled": semantic_tooling_autorun,
        "planned_tools": [],
        "executed": [],
        "hints": [],
    }


def _run_prompt_coaching(query: str, agent_type: str, request) -> Dict[str, Any]:
    """Run HintsEngine prompt coaching; update audit fields. Returns coaching dict (empty on error)."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _hints_dir = _Path(__file__).parent
        if str(_hints_dir) not in _sys.path:
            _sys.path.insert(0, str(_hints_dir))
        from hints_engine import HintsEngine  # type: ignore[import]
        coaching = HintsEngine().prompt_coaching_as_dict(query, agent_type=agent_type)
        request["audit_metadata"]["prompt_coaching_score"] = float(coaching.get("score", 0.0) or 0.0)
        request["audit_metadata"]["prompt_coaching_missing_fields"] = len(
            coaching.get("missing_fields", []) or []
        )
        return coaching
    except Exception as exc:
        logger.debug("prompt_coaching_skipped error=%s", exc)
        return {}


_HINT_AUDIT_PATH = Path(
    os.getenv("HINT_AUDIT_LOG_PATH", "/var/log/nixos-ai-stack/hint-audit.jsonl")
)


class _QueryShimRequest:
    """Minimal request facade used to keep /query and /v1/orchestrate semantics identical."""

    def __init__(self, body: bytes, real_req, *, path: str = "/query"):
        self._body = body
        self.headers = real_req.headers
        self.match_info = real_req.match_info
        self.method = "POST"
        self.path = path
        self.rel_url = real_req.rel_url
        self.app = getattr(real_req, "app", None)
        self._audit: dict = {}

    async def json(self):
        return json.loads(self._body)

    def __setitem__(self, key, val):
        self._audit[key] = val

    def __getitem__(self, key):
        return self._audit[key]

    def get(self, key, default=None):
        return self._audit.get(key, default)


def _write_query_hint_audit(hints: list, query: str) -> None:
    """P22-004: append coordinator hint injections to hint-audit.jsonl.

    Mirrors the schema written by aider-wrapper so aq-report §14 captures
    the much larger /query synthesis volume alongside aider-wrapper calls.
    """
    try:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _HINT_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HINT_AUDIT_PATH.open("a", encoding="utf-8") as fh:
            for h in hints:
                if not isinstance(h, dict):
                    continue
                snippet = str(h.get("snippet", "") or h.get("compact_injection", "")).strip()
                if not snippet:
                    continue
                entry = json.dumps({
                    "timestamp": ts,
                    "service": "hybrid-coordinator",
                    "task_id": "",
                    "hint_id": str(h.get("id", h.get("domain_id", "unknown"))),
                    "hint_snippet": snippet[:80],
                    "hint_accepted": True,
                    "query_prefix": query[:80],
                })
                fh.write(entry + "\n")
    except Exception as exc:
        logger.debug("query_hint_audit_write_failed error=%s", exc)


async def _inject_semantic_tooling(
    query: str,
    memory_recall_priority: bool,
    request_context: Dict[str, Any],
    tooling_layer: Dict[str, Any],
    request,
) -> None:
    """Inject planned tools, hints, discovery, and memory recall into request_context/tooling_layer."""
    planned, tool_security = _audit_planned_tools(
        query, workflow_tool_catalog(query, memory_recall_priority=memory_recall_priority)
    )
    tooling_layer["planned_tools"] = [p.get("name", "") for p in planned]
    tooling_layer["tool_security"] = tool_security
    request["audit_metadata"]["tool_security_blocked"] = len(tool_security.get("blocked", []))
    request["audit_metadata"]["tool_security_cache_hits"] = int(tool_security.get("cache_hits", 0))
    request["audit_metadata"]["tool_security_first_seen"] = int(tool_security.get("first_seen", 0))

    # Auto-hints: inject top semantic hints into route context.
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
                    request, "hints",
                    (time.perf_counter() - _hint_start) * 1000.0,
                    parameters={"query": query[:200], "result_count": len(hint_snippets[:2])},
                )
                # P22-004: track hint injections from /query synthesis path
                # into hint-audit.jsonl so aq-report §14 captures coordinator volume.
                _write_query_hint_audit(top_hints[:2], query)
        except Exception as exc:
            _audit_internal_tool_execution(
                request, "hints", 0.0,
                parameters={"query": query[:200]},
                outcome="error", error_message=str(exc),
            )
            logger.debug("semantic_tooling_hints_skipped error=%s", exc)

    # Auto-discovery: enrich context with capability overview.
    if _progressive_disclosure and any(p.get("name") == "discovery" for p in planned):
        try:
            _discovery_start = time.perf_counter()
            disc = await _progressive_disclosure.discover(level="overview", categories=None, token_budget=200)
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
                request, "discovery",
                (time.perf_counter() - _discovery_start) * 1000.0,
                parameters={
                    "query": query[:200],
                    "capability_count": int(request_context["tool_discovery"].get("capability_count", 0)),
                },
            )
        except Exception as exc:
            _audit_internal_tool_execution(
                request, "discovery", 0.0,
                parameters={"query": query[:200]},
                outcome="error", error_message=str(exc),
            )
            logger.debug("semantic_tooling_discovery_skipped error=%s", exc)

    # Memory recall: prepend relevant prior context.
    if _recall_memory is not None and memory_recall_priority:
        try:
            _memory_start = time.perf_counter()
            request_context["memory_recall_attempted"] = True
            request["audit_metadata"]["memory_recall_attempted"] = True
            memory_result = await asyncio.wait_for(
                _recall_memory(query=query, memory_types=None, limit=3, retrieval_mode="hybrid"),
                timeout=5.0,  # Increased from 2.0: reflection loop (5 collections × 2 retries) needs headroom
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
                request, "recall_agent_memory",
                (time.perf_counter() - _memory_start) * 1000.0,
                parameters={
                    "query": query[:200],
                    "result_count": len(memory_summaries[:3]),
                    "memory_recall_miss": not bool(memory_summaries),
                },
            )
        except Exception as exc:
            _audit_internal_tool_execution(
                request, "recall_agent_memory", 0.0,
                parameters={"query": query[:200]},
                outcome="error", error_message=str(exc),
            )
            logger.debug("semantic_tooling_memory_recall_skipped error=%s", exc)


def _apply_query_response_mode(
    query: str,
    data: Dict[str, Any],
    request_context: Dict[str, Any],
    generate_response: bool,
    memory_recall_priority: bool,
    request,
) -> bool:
    """Downshift a narrow continuation subset to retrieval-only when synthesis is the hotspot."""
    aq_report_summary = _load_aq_report_status_summary()
    retrieval_strategy = _workflow_memory_first_strategy(
        query, memory_recall_priority, aq_report_summary,
    )
    request_context["retrieval_strategy"] = retrieval_strategy

    effective_generate_response = generate_response
    if generate_response and retrieval_strategy.get("active"):
        normalized = str(query or "").strip().lower()
        has_recalled_memory = bool(request_context.get("prior_memory") or request_context.get("memory_recall"))
        # P23-001: Removed the duplicate resume_markers gate — _is_continuation_query already
        # classifies continuation intent. The old dual-gate required both _is_continuation_query
        # AND a separate resume_markers list, but resume_markers used "continue from" (not "continue")
        # and "remaining work" (not "remaining improvements"), so queries that correctly passed
        # _is_continuation_query failed the second check → 0/8 downshift coverage in aq-report.
        explanation_markers = (
            "explain why",
            "why the",
            "root cause",
            "step by step",
            "reason through",
            "walk through",
            "summarize",
            "explain",
            "describe",
        )
        explicit_search_markers = ("search", "find", "lookup", "retrieve", "grep", "rg ", "query")
        has_explanation = any(marker in normalized for marker in explanation_markers)
        has_search = any(marker in normalized for marker in explicit_search_markers)
        # Phase 89.4: use memory_recall_priority (broad signal: already used to decide strategy)
        # instead of the narrow _is_continuation_query — audit showed 0/14 because the narrow
        # check rejected all queries that triggered memory-first via the broader heuristics.
        # retrieval_strategy_active=True already implies the strategy fired; aligning the
        # downshift gate with that same signal prevents the double-gating.
        if has_recalled_memory and memory_recall_priority and not has_explanation and not has_search:
            effective_generate_response = False
            request_context["response_generation_downshifted"] = True
            request_context["response_generation_downshift_reason"] = "continuation_memory_first"
            request_context["response_generation_downshift_evidence"] = retrieval_strategy.get("evidence", {})
        else:
            # Phase 84: debug log so aq-report can surface skip reasons
            skip_reasons = []
            if not has_recalled_memory:
                skip_reasons.append("no_recalled_memory")
            if not memory_recall_priority:
                skip_reasons.append("memory_recall_not_prioritized")
            if has_explanation:
                skip_reasons.append("explanation_marker")
            if has_search:
                skip_reasons.append("search_marker")
            logger.debug(
                "downshift_skipped reasons=%s strategy=%s q=%.80r",
                skip_reasons, retrieval_strategy.get("reasons"), query,
            )

    if isinstance(request.get("audit_metadata"), dict):
        request["audit_metadata"]["generate_response"] = effective_generate_response
        request["audit_metadata"]["retrieval_strategy_mode"] = retrieval_strategy.get("mode", "standard")
        request["audit_metadata"]["retrieval_strategy_active"] = bool(retrieval_strategy.get("active"))
        request["audit_metadata"]["response_generation_downshifted"] = bool(
            request_context.get("response_generation_downshifted")
        )
        if request_context.get("response_generation_downshift_reason"):
            request["audit_metadata"]["response_generation_downshift_reason"] = request_context.get(
                "response_generation_downshift_reason"
            )
    return effective_generate_response


async def _execute_query_search(
    query: str,
    data: Dict[str, Any],
    prefer_local: bool,
    request_context: Dict[str, Any],
    generate_response: bool,
) -> Dict[str, Any]:
    """Gate on model loading, run route search with cache, return result dict.

    Returns a dict with '_loading_error': True when the local model is still
    loading and the caller should respond with HTTP 503.
    """
    _llm_timeout_s = float(data.get("llm_timeout_s") or os.getenv("AI_QUERY_LLM_TIMEOUT_S", "120"))

    if prefer_local and _local_llm_loading_ref():
        ready = await _wait_for_model(timeout=30.0)
        if not ready:
            return {
                "_loading_error": True,
                "queue_depth": _queue_depth_ref(),
                "queue_max": _queue_max_ref(),
            }

    cache_enabled = bool(data.get("enable_cache", True))
    # Caller can pass max_tokens (int) or heavy=true to override the per-type budget
    # and force switchboard routing for the full 900s inference window.
    _max_tokens_raw = data.get("max_tokens") or data.get("max_tokens_override")
    _heavy = bool(data.get("heavy", False))
    _max_tokens_override: Optional[int] = None
    if _heavy:
        _max_tokens_override = int(os.getenv("AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_HEAVY", "3000"))
    elif _max_tokens_raw is not None:
        try:
            _max_tokens_override = max(1, int(_max_tokens_raw))
        except (TypeError, ValueError):
            pass

    _route_kwargs: Dict[str, Any] = dict(
        query=query,
        mode=data.get("mode", "auto"),
        prefer_local=prefer_local,
        context=request_context,
        limit=int(data.get("limit", 5)),
        keyword_limit=int(data.get("keyword_limit", 5)),
        score_threshold=float(data.get("score_threshold", Config.AI_SEARCH_SCORE_THRESHOLD)),
        generate_response=generate_response,
        max_tokens_override=_max_tokens_override,
    )

    # Phase 8.10 — Parallel retrieval + cache check.
    _retrieval_task: Optional[asyncio.Task] = None
    cached_result = None
    if cache_enabled and _should_use_cache(query):
        _retrieval_task = asyncio.create_task(
            asyncio.wait_for(_route_search(**_route_kwargs), timeout=_llm_timeout_s)
        )
        cached_result = _get_cached_response(query, context=request_context)

    if cached_result:
        if _retrieval_task is not None and not _retrieval_task.done():
            _retrieval_task.cancel()
        cached_response, cache_metadata = cached_result
        logger.info("Cache hit for query: %s...", query[:60])
        return {"response": cached_response, "from_cache": True, "cache_metadata": cache_metadata, "query": query}

    if _retrieval_task is None:
        _retrieval_task = asyncio.create_task(
            asyncio.wait_for(_route_search(**_route_kwargs), timeout=_llm_timeout_s)
        )
    try:
        result = await _retrieval_task
    except asyncio.TimeoutError:
        logger.warning(
            "route_search_llm_timeout: query truncated after %.0fs (generate_response=%s)",
            _llm_timeout_s, generate_response,
        )
        if generate_response:
            result = await _route_search(
                query=query,
                mode=data.get("mode", "auto"),
                prefer_local=prefer_local,
                context=request_context,
                limit=int(data.get("limit", 5)),
                keyword_limit=int(data.get("keyword_limit", 5)),
                score_threshold=float(data.get("score_threshold", Config.AI_SEARCH_SCORE_THRESHOLD)),
                generate_response=False,
            )
        else:
            result = {"results": [], "error": "route_search_timeout"}
        result["truncated"] = True
        result["truncation_reason"] = "llm_timeout"

    if cache_enabled and result.get("response"):
        quality_score = result.get("quality_score", 0)
        if quality_score > 0:
            _cache_response(
                query=query,
                response=result["response"],
                quality_score=quality_score,
                confidence=result.get("confidence", 1.0),
                context=request_context,
            )
    return result


def _annotate_query_result(
    result: Dict[str, Any],
    tooling_layer: Dict[str, Any],
    request_context: Dict[str, Any],
    orchestration: Dict[str, Any],
    prompt_coaching: Dict[str, Any],
    lesson_refs: list,
    include_debug_metadata: bool,
    semantic_tooling_autorun: bool,
) -> None:
    """Annotate result with tooling layer, memory context, lesson refs, coaching, orchestration."""
    if semantic_tooling_autorun:
        result["tooling_layer"] = _compact_tooling_layer_response(
            tooling_layer, include_debug_metadata=include_debug_metadata,
        )
    if request_context.get("retrieval_strategy"):
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta
        meta["retrieval_strategy"] = request_context.get("retrieval_strategy")
    if request_context.get("memory_recall_attempted"):
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta
        meta["memory_recall_attempted"] = True
        meta["memory_recall_miss"] = bool(request_context.get("memory_recall_miss"))
    if "generate_response_requested" in request_context:
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta
        meta["generate_response_requested"] = bool(request_context.get("generate_response_requested"))
        meta["generate_response_effective"] = bool(request_context.get("generate_response_effective"))
    if request_context.get("response_generation_downshifted"):
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta
        meta["response_generation_downshifted"] = True
        meta["response_generation_downshift_reason"] = str(
            request_context.get("response_generation_downshift_reason") or ""
        )
    if request_context.get("memory_recall"):
        result["memory_recall"] = request_context.get("memory_recall")
    if request_context.get("prior_memory"):
        result["prior_memory"] = request_context.get("prior_memory")
    if lesson_refs:
        result["active_lesson_refs"] = lesson_refs
    if prompt_coaching:
        result["prompt_coaching"] = _query_prompt_coaching_response(
            prompt_coaching, include_debug_metadata=include_debug_metadata,
        )
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta
        meta["prompt_coaching"] = _compact_prompt_coaching_metadata(prompt_coaching)
    meta = result.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
        result["metadata"] = meta
    meta["orchestration"] = {
        "requesting_agent": orchestration["requesting_agent"],
        "requester_role": orchestration["requester_role"],
        "delegate_via_coordinator_only": orchestration["delegate_via_coordinator_only"],
    }
    if lesson_refs:
        meta["active_lesson_refs"] = lesson_refs
    result["orchestration"] = orchestration


def _collect_query_audit(request, result: Dict[str, Any], tooling_layer: Dict[str, Any]) -> None:
    """Write result-derived telemetry fields into request['audit_metadata']."""
    audit = request["audit_metadata"]
    audit["semantic_autorun_planned"] = len(tooling_layer.get("planned_tools", []))
    audit["semantic_autorun_executed"] = len(tooling_layer.get("executed", []))
    audit["route_strategy"] = str(result.get("route", "unknown"))
    audit["strategy_tag"] = str(result.get("route", "unknown"))
    audit["backend"] = str(result.get("backend", "unknown"))

    for key, src in (
        ("backend_reason_class", "backend_reason_class"),
        ("local_inference_lane", "local_inference_lane"),
        ("local_inference_lane_reason", "local_inference_lane_reason"),
    ):
        val = str(result.get(src, "") or "").strip()
        if val:
            audit[key] = val

    response_max_tokens = result.get("response_max_tokens")
    if isinstance(response_max_tokens, int):
        audit["response_max_tokens"] = response_max_tokens

    task_complexity = result.get("task_complexity")
    if isinstance(task_complexity, dict):
        for key, src in (("task_complexity_reason", "reason"), ("task_complexity_type", "type")):
            val = str(task_complexity.get(src, "") or "").strip()
            if val:
                audit[key] = val
        tc_tokens = task_complexity.get("tokens")
        if isinstance(tc_tokens, int):
            audit["task_complexity_tokens"] = tc_tokens
        for flag in ("local_suitable", "remote_required"):
            if flag in task_complexity:
                audit[f"task_complexity_{flag}"] = bool(task_complexity.get(flag))

    retrieval_profile = result.get("retrieval_profile")
    if isinstance(retrieval_profile, dict):
        audit["retrieval_profile"] = str(retrieval_profile.get("profile", "standard"))
        cols = retrieval_profile.get("collections")
        if isinstance(cols, list):
            audit["retrieval_collection_count"] = len(cols)

    result_payload = result.get("results")
    synthesis_fallback = result_payload.get("synthesis_fallback") if isinstance(result_payload, dict) else None
    if isinstance(synthesis_fallback, dict):
        fb_reason = str(synthesis_fallback.get("reason", "") or "").strip()
        if fb_reason:
            audit["fallback_reason"] = fb_reason
        fb_status = synthesis_fallback.get("status_code")
        if isinstance(fb_status, int):
            audit["fallback_status_code"] = fb_status
        orig_backend = str(synthesis_fallback.get("original_backend", "") or "").strip()
        if orig_backend:
            audit["fallback_original_backend"] = orig_backend

    prompt_cache = result_payload.get("prompt_cache") if isinstance(result_payload, dict) else None
    if isinstance(prompt_cache, dict):
        audit["prompt_cache_policy_enabled"] = bool(prompt_cache.get("policy_enabled"))
        cached_tokens = prompt_cache.get("cached_tokens")
        if isinstance(cached_tokens, int):
            audit["prompt_cache_cached_tokens"] = cached_tokens


# R2.7: loopback auth helpers removed — canonical auth logic in middleware/auth.py.
# core/auth_middleware.py is a backwards-compatibility re-export shim.


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
    # R2.2: Middleware now owned by router.py (create_app).
    # The closures below are kept as R2.2 FALLBACK — remove after nixos-rebuild
    # confirms StatusService routes are healthy.
    # ------------------------------------------------------------------

    # R2.2 fallback — tracing_middleware (moved to router._make_tracing_middleware):
    # @web.middleware
    # async def tracing_middleware(request, handler): ...

    # R2.2 fallback — request_id_middleware (moved to router._make_request_id_middleware):
    # @web.middleware
    # async def request_id_middleware(request, handler): ...

    # R2.2 fallback — api_key_middleware (moved to core.auth_middleware.create_api_key_middleware):
    # @web.middleware
    # async def api_key_middleware(request, handler): ...

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    # R2.2 fallback — handle_status (moved to core.status_service):
    # async def handle_status(request): ...

    # R2.2: handle_status moved to core.status_service — see FALLBACK comment above.
    # (original closure preserved in git history; remove this comment after nixos-rebuild)

    async def _fallback_handle_status(request):  # noqa: F841  R2.2 fallback
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

    async def _fallback_handle_hardware_state(request):  # noqa: F841  R2.2 fallback
        """GET /api/hardware/state — return current thermal and RAM metrics."""
        from dataclasses import asdict
        state = await get_ipm().hardware_state()
        return web.json_response(asdict(state))

    async def _fallback_handle_delegate_stats(request):  # noqa: F841  R2.2 fallback
        """GET /stats/delegate — delegation success rate from audit log.

        Reads the ai-audit-sidecar JSONL log under the coordinator's own
        process credentials (ai-hybrid:ai-stack), so callers like aq-qa
        do not need direct file-system group membership to get the rate.

        Query params:
          window_s  — lookback window in seconds (default 86400 = 24h)

        Response:
          {total, ok, success_rate, window_s, skipped_probes}
        """
        try:
            window_s = int(request.rel_url.query.get("window_s", "86400"))
        except (TypeError, ValueError):
            window_s = 86400

        audit_log = os.getenv(
            "TOOL_AUDIT_LOG_PATH",
            "/var/log/ai-audit-sidecar/tool-audit.jsonl",
        )
        now = time.time()
        total = 0
        ok = 0
        skipped_probes = 0
        failure_breakdown: dict = {}
        error_msg = None
        _TERMINAL_OUTCOMES = {"success", "error", "timeout", "failed"}
        try:
            with open(audit_log, "r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except Exception:
                        continue
                    if entry.get("tool_name") != "ai_coordinator_delegate":
                        continue
                    ts_str = entry.get("timestamp", "")
                    try:
                        from datetime import datetime as _dt, timezone as _tz
                        ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        continue
                    if now - ts > window_s:
                        continue
                    latency_ms = float(entry.get("latency_ms") or 0)
                    err_msg_e = entry.get("error_message") or ""
                    is_probe = (
                        (entry.get("outcome") == "error"
                         and err_msg_e == "http_status_504"
                         and latency_ms < 15000)
                        or err_msg_e.startswith("blocked_endpoint_pattern:")
                    )
                    if is_probe:
                        skipped_probes += 1
                        continue
                    outcome = entry.get("outcome", "")
                    # Skip non-terminal entries (running / pending / started).
                    # These are stale stubs from sessions that ended before the
                    # delegate script wrote a final outcome — counting them as
                    # failures would skew the rate against incomplete-but-harmless
                    # background tasks.
                    if outcome not in _TERMINAL_OUTCOMES:
                        continue
                    total += 1
                    if outcome == "success":
                        ok += 1
                    else:
                        # Use stored failure_reason if present; fall back to classifier
                        reason = entry.get("failure_reason") or _classify_failure_reason(err_msg_e)
                        failure_breakdown[reason] = failure_breakdown.get(reason, 0) + 1
        except OSError as exc:
            error_msg = str(exc)
        except Exception as exc:
            error_msg = str(exc)

        if error_msg:
            return web.json_response(
                {"error": error_msg, "total": 0, "ok": 0, "window_s": window_s},
                status=503,
            )
        success_rate = round(ok / total, 3) if total > 0 else None
        return web.json_response({
            "total": total,
            "ok": ok,
            "success_rate": success_rate,
            "window_s": window_s,
            "skipped_probes": skipped_probes,
            "failure_breakdown": failure_breakdown,
        })

    # Phase 56.4 — Commit Fact Ingest
    # R2.3: handle_memory_facts_post/get + handle_journal_* moved to memory.memory_service
    async def _fallback_handle_memory_facts_post(request):  # noqa: F841  R2.3 fallback
        """POST /api/memory/facts — store structured facts from aq-commit-facts.

        Writes each fact to MemoryBroker semantic store with valid_from=now().
        Body: {"facts": [{"fact":str, "scope":str, "confidence":float, "source":str}]}
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)

        facts = data.get("facts") or []
        if not isinstance(facts, list):
            return web.json_response({"error": "facts must be array"}, status=400)

        stored = 0
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        mb = memory_broker.get_broker()
        for f in facts[:8]:  # cap at 8 per call
            if not isinstance(f, dict):
                continue
            fact_text = str(f.get("fact") or "").strip()[:500]
            if not fact_text:
                continue
            try:
                result = await mb.write(
                    memory_type="semantic",
                    content=fact_text,
                    context={
                        "scope":      str(f.get("scope") or "other")[:64],
                        "confidence": float(f.get("confidence") or 0.8),
                        "source":     str(f.get("source") or "aq-commit-facts")[:128],
                        "valid_from": ts,
                        "origin":     "commit_facts",
                    },
                )
                # "skipped" (dedup) = already present; "queued" = fire-and-forget accepted
                if result.get("status") in {"stored", "skipped", "queued"}:
                    stored += 1
            except Exception as _exc:
                logger.debug("memory_facts_store_skip err=%s", _exc)

        return web.json_response({"stored": stored, "timestamp": ts})

    async def _fallback_handle_memory_facts_get(request):  # noqa: F841  R2.3 fallback
        """GET /api/memory/facts — retrieve stored facts (used by aq-session-start).

        Query params: scope=<str> (filter by scope), limit=<int> (default 10)
        """
        scope = request.rel_url.query.get("scope", "")
        try:
            limit = max(1, min(int(request.rel_url.query.get("limit", "10")), 50))
        except (ValueError, TypeError):
            limit = 10

        mb = memory_broker.get_broker()
        try:
            results = await mb.read(
                memory_type="semantic",
                query=scope or "procedural constraints",
                top_k=limit,
            )
        except Exception as _exc:
            return web.json_response({"facts": [], "error": str(_exc)})

        facts = []
        for item in (results if isinstance(results, list) else []):
            content = item.get("content") or item.get("text") or ""
            ctx = item.get("context") or item.get("metadata") or {}
            if scope and ctx.get("scope", "") != scope:
                continue
            facts.append({
                "fact":       content[:500],
                "scope":      ctx.get("scope", ""),
                "confidence": ctx.get("confidence", 0.8),
                "source":     ctx.get("source", ""),
            })
        return web.json_response({"facts": facts[:limit]})

    # Phase 56.5 — Agent Ops Status
    _agent_ops_state: dict = {"drift_score": None, "profile_override": None, "alert_active": False, "since": None}

    async def handle_agent_ops_status(_request):
        """GET /api/agent-ops/status — live drift state + profile override."""
        da = drift_analyzer.get_analyzer()
        try:
            drift_data = await da.compute_drift(window=20)
            score = drift_data.get("drift_score")
        except Exception:
            score = None
        return web.json_response({
            "drift_score":      score,
            "profile_override": _agent_ops_state.get("profile_override"),
            "alert_active":     _agent_ops_state.get("alert_active", False),
            "since":            _agent_ops_state.get("since"),
            "window_size":      20,
        })

    # Phase 90 — failure_reason classifier
    def _classify_failure_reason(error_message: str) -> str:
        """Map a raw error_message string to a structured failure_reason enum value."""
        msg = (error_message or "").lower()
        if not msg.strip():
            return "empty_response"
        if "timeout" in msg or "504" in msg or "408" in msg or "timed out" in msg:
            return "timeout"
        if "context" in msg or "413" in msg or "too long" in msg or "context_length" in msg:
            return "context_overflow"
        if "500" in msg or "internal server" in msg or "backend" in msg:
            return "backend_500"
        return "unknown"

    # Phase 56.6 — Agent Event Bus
    _VALID_EVENT_TYPES = frozenset({
        "task_completed", "error_resolution", "lesson", "decision",
        "delegation_start", "delegation_end",
    })
    _VALID_AGENTS = frozenset({
        "gemini", "codex", "claude", "local", "coordinator", "unknown",
    })

    async def handle_agent_events_post(request):
        """POST /api/agent-events — ingest a delegation/lesson/decision event.

        Writes to tool-audit.jsonl (fixes 0.8.1) and feeds ContinuousLearning
        when event_type is task_completed or error_resolution.
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)

        event_type = str(data.get("event_type") or "task_completed").strip()
        sub_type   = str(data.get("sub_type") or "").strip()
        agent      = str(data.get("agent") or "unknown").strip()
        outcome    = str(data.get("outcome") or "success").strip()
        summary    = str(data.get("summary") or "")[:400]
        prompt     = str(data.get("prompt") or "")[:1000]
        tags       = data.get("tags") or []
        try:
            latency_ms = int(float(data.get("latency_ms") or 0))
        except (ValueError, TypeError):
            latency_ms = 0
        task_id    = str(data.get("task_id") or "")[:64]
        try:
            iteration = int(data.get("iteration") or 0)
        except (ValueError, TypeError):
            iteration = 0

        if event_type not in _VALID_EVENT_TYPES:
            # Preserve unknown types under a flagged key rather than silently coercing
            return web.json_response(
                {"error": f"unknown event_type '{event_type}'; valid: {sorted(_VALID_EVENT_TYPES)}"},
                status=400,
            )
        if agent not in _VALID_AGENTS:
            agent = "unknown"

        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Write to tool-audit.jsonl — same format /stats/delegate reads
        audit_entry = {
            "tool_name": "ai_coordinator_delegate",
            "timestamp": ts,
            "outcome": outcome,
            "latency_ms": latency_ms,
            "parameters": {
                "agent": agent,
                "task_id": task_id,
                "event_type": event_type,
                "sub_type": sub_type,
                "summary": summary,
                "tags": tags,
            },
            "error_message": "" if outcome == "success" else summary[:120],
            "failure_reason": None if outcome == "success" else _classify_failure_reason(summary),
        }
        audit_log = os.getenv(
            "TOOL_AUDIT_LOG_PATH",
            "/var/log/ai-audit-sidecar/tool-audit.jsonl",
        )
        try:
            with open(audit_log, "a", encoding="utf-8") as _fh:
                _fh.write(json.dumps(audit_entry) + "\n")
        except OSError as _e:
            logger.warning("agent_event_audit_write_failed path=%s err=%s", audit_log, _e)

        # Feed ContinuousLearning for task_completed / error_resolution.
        # CL._extract_pattern_from_event() reads a nested "task" sub-object for
        # task_completed and flat error_description/solution for error_resolution.
        if event_type in {"task_completed", "error_resolution"}:
            try:
                if event_type == "task_completed":
                    _cl_event = {
                        "event": event_type,
                        "timestamp": ts,
                        "task": {
                            "task_id": task_id,
                            "prompt": prompt or summary,
                            "output": summary,
                            "backend": agent,
                            "iteration": iteration,
                            "context": {"sub_type": sub_type, "outcome": outcome},
                        },
                    }
                else:  # error_resolution
                    _cl_event = {
                        "event": event_type,
                        "timestamp": ts,
                        "error_id": task_id,
                        "error_description": summary,
                        "solution": summary,
                        "resolution_time": latency_ms / 1000.0,
                    }
                if hasattr(_continuous_learning, "process_event"):
                    # asyncio.coroutine() was removed in Python 3.12 — call directly
                    asyncio.create_task(_continuous_learning.process_event(_cl_event))
            except Exception as _exc:
                logger.debug("agent_event_cl_feed_skip err=%s", _exc)

        # Lesson events → agent-lesson registry candidate
        if event_type == "lesson" and summary:
            try:
                async with _agent_lessons_lock:
                    _registry = await _load_agent_lessons_registry()
                    _entries = list(_registry.get("entries") or [])
                    import hashlib as _hl
                    _key = "auto-" + _hl.md5(summary.encode()).hexdigest()[:8]
                    _exists = any(e.get("lesson_key") == _key for e in _entries)
                    if not _exists:
                        _entries.append({
                            "lesson_key": _key,
                            "summary": summary[:240],
                            "source_agent": agent,
                            "state": "pending_review",
                            "created_at": ts,
                            "tags": tags,
                        })
                        _registry["entries"] = _entries
                        await _save_agent_lessons_registry(_registry)
            except Exception as _exc:
                logger.debug("agent_event_lesson_registry_skip err=%s", _exc)

        return web.json_response({
            "accepted": True,
            "event_type": event_type,
            "agent": agent,
            "outcome": outcome,
            "timestamp": ts,
        })

    async def handle_agent_events_get(request):
        """GET /api/agent-events — recent events from tool-audit.jsonl."""
        try:
            limit = min(int(request.rel_url.query.get("limit", "20")), 100)
        except (ValueError, TypeError):
            limit = 20
        filter_type = request.rel_url.query.get("event_type", "")
        try:
            window_s = int(request.rel_url.query.get("window_s", "86400"))
        except (ValueError, TypeError):
            window_s = 86400

        audit_log = os.getenv(
            "TOOL_AUDIT_LOG_PATH",
            "/var/log/ai-audit-sidecar/tool-audit.jsonl",
        )
        now = time.time()
        events = []
        try:
            with open(audit_log, "r", encoding="utf-8", errors="replace") as _fh:
                lines = _fh.readlines()
            for raw in reversed(lines):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except Exception:
                    continue
                if entry.get("tool_name") != "ai_coordinator_delegate":
                    continue
                ts_str = entry.get("timestamp", "")
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if now - ts > window_s:
                    continue
                params = entry.get("parameters") or {}
                if filter_type and params.get("event_type") != filter_type:
                    continue
                events.append({
                    "event_type": params.get("event_type", "task_completed"),
                    "agent":      params.get("agent", "unknown"),
                    "outcome":    entry.get("outcome", ""),
                    "summary":    params.get("summary", ""),
                    "task_id":    params.get("task_id", ""),
                    "tags":       params.get("tags") or [],
                    "latency_ms": entry.get("latency_ms", 0),
                    "timestamp":  ts_str,
                })
                if len(events) >= limit:
                    break
        except OSError:
            pass
        return web.json_response({"events": events, "total_in_window": len(events)})

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

    async def handle_scheduler_status(request):
        return web.json_response(await get_scheduler().status())

    def _is_agent_query(d: Dict[str, Any]) -> bool:
        """True when the caller is an automated agent, not an interactive human session."""
        return str(d.get("agent_type") or "").lower() in {
            "gemini", "codex", "claude", "local", "coordinator", "local-agent",
        }

    def _get_reindex_status() -> Dict[str, Any]:
        """Return last-written reindex status with 5 s cache; empty dict on error."""
        global _reindex_status_cache, _reindex_status_ts
        now = time.monotonic()
        if _reindex_status_cache and now - _reindex_status_ts < 5.0:
            return _reindex_status_cache
        try:
            with open(_REINDEX_STATUS_PATH) as _rf:
                _reindex_status_cache = json.load(_rf)
            _reindex_status_ts = now
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return _reindex_status_cache

    async def handle_query(request):
        """HTTP endpoint for query routing."""
        try:
            data = await request.json()
            (
                query, generate_response, prefer_local, semantic_tooling_autorun,
                memory_recall_priority, request_context, orchestration, include_debug_metadata,
            ) = _parse_query_input(data)
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            # Phase 54.5 — wrap handler in trace span (init after body parse to avoid
            # consuming the aiohttp request body stream via request.clone().text())
            _trace = trace_collector.TraceCollector(
                postgres_client=None,  # uses module-level _pg set by trace_collector.init()
                query=query[:200],
            )

            # Phase 54.2 — classify intent before any routing decisions
            # Use classify_async: keyword-first with semantic rescue for low-confidence
            # queries (prevents ~47% intent_flip_rate from unknown accumulation).
            _clf = _intent_classifier or intent_classifier.get_classifier()
            _intent_result = await _clf.classify_async(query)
            _detected_intent = _intent_result.get("intent", "unknown")
            _intent_conf = _intent_result.get("confidence", 0.0)
            request_context["intent"] = _detected_intent
            request_context["intent_confidence"] = _intent_conf
            request_context["intent_profile"] = _intent_result.get("profile", "local")
            _trace.set_intent(_detected_intent)
            _trace.set_profile(_intent_result.get("profile", "local"))
            # Elevate memory_recall_priority based on intent routing map
            if _intent_result.get("memory_recall") and not memory_recall_priority:
                memory_recall_priority = True

            # Phase 54.3 — RAG augmentation (default ON, 500ms cap)
            _rag = rag_augmentor.get_augmentor()
            _rag_result = await _rag.augment(
                query=query,
                intent=_detected_intent,
                rag_project=_intent_result.get("rag_project", "semantic"),
            )
            _trace.set_retrieval(
                hits=_rag_result.get("hits", 0),
                latency_ms=_rag_result.get("latency_ms", 0),
                skipped=_rag_result.get("skipped", True),
                collection_count=_rag_result.get("collection_count", 0),
            )
            if _rag_result.get("augmented") and _rag_result.get("context_text"):
                request_context["rag_context"] = _rag_result["context_text"]
                request_context["rag_project"] = _rag_result.get("project", "")

            tooling_layer = _init_query_audit_and_tooling(
                request, orchestration, generate_response,
                semantic_tooling_autorun, memory_recall_priority,
            )
            prompt_coaching = _run_prompt_coaching(
                query, str(data.get("agent_type") or "human"), request,
            )
            if semantic_tooling_autorun:
                await _inject_semantic_tooling(
                    query, memory_recall_priority, request_context, tooling_layer, request,
                )
            request_context["generate_response_requested"] = generate_response
            generate_response = _apply_query_response_mode(
                query, data, request_context, generate_response, memory_recall_priority, request,
            )
            request_context["generate_response_effective"] = generate_response

            # Phase 55.2 — MLFQ Priority Scheduling
            _query_is_agent = _is_agent_query(data)
            task_class: TaskClass = "background" if _query_is_agent else "interactive"
            if data.get("batch") or data.get("low_priority"):
                task_class = "batch"

            # Estimate tokens for admission control
            token_estimate = (len(query) + len(str(request_context))) // 4
            
            workload = WorkloadDescriptor(
                task_id=str(uuid4()),
                task_class=task_class,
                priority=int(data.get("priority", 5)),
                token_budget=int(data.get("max_tokens") or 2000),
                agent_id=data.get("agent_id"),
                x_maeah=data.get("x_maeah", {}),
            )

            try:
                # Submit to MLFQ scheduler
                handle = await get_scheduler().submit(
                    workload,
                    _execute_query_search(
                        query, data, prefer_local, request_context, generate_response,
                    )
                )
                # Wait for execution (respecting LLM timeouts)
                handle = await get_scheduler().wait(handle.task_id)
                if handle.status == "failed":
                    raise RuntimeError(handle.error or "task execution failed")
                if handle.status == "evicted":
                    return web.json_response({"error": "task_evicted", "detail": handle.error}, status=503)
                
                result = handle.result
            except MLFQAdmissionError as exc:
                return web.json_response({"error": "scheduler_busy", "detail": str(exc)}, status=503)
            except Exception as exc:
                logger.exception("Scheduled query failed: %s", exc)
                return web.json_response({"error": "execution_failed", "detail": str(exc)}, status=500)


            # Warn agents when AIDB reindex is in progress (RAG corpus may be stale)
            _ridx = _get_reindex_status()
            if _ridx.get("status") == "running" and isinstance(result, dict):
                result["reindex_in_progress"] = True
                result["reindex_warning"] = (
                    "AIDB reindex is in progress — RAG results may be incomplete. "
                    f"Reindex started at {_ridx.get('started_at', 'unknown')}. "
                    "Proceed with current results or retry after indexing completes."
                )

            if result.get("_loading_error"):
                # Attempt transparent remote fallback before surfacing 503.
                # Local agents should never gate remote workflows.
                _remote_active = bool(os.getenv("SWITCHBOARD_REMOTE_URL", "").strip())
                if _remote_active:
                    logger.info(
                        "local_model_loading: transparent fallback to remote for query=%r",
                        query[:60],
                    )
                    result = await _execute_query_search(
                        query, data, False, request_context, generate_response,
                    )
                    if not result.get("_loading_error"):
                        result.setdefault("fallback_reason", "local_model_loading")
                if result.get("_loading_error"):
                    return web.json_response(
                        {
                            "error": "model_loading",
                            "detail": "Local model is loading and no remote fallback is configured. Retry or set SWITCHBOARD_REMOTE_URL.",
                            "queue_depth": result.get("queue_depth", 0),
                            "queue_max": result.get("queue_max", 0),
                        },
                        status=503,
                    )

            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)

            _annotate_query_result(
                result, tooling_layer, request_context, orchestration,
                prompt_coaching, lesson_refs, include_debug_metadata, semantic_tooling_autorun,
            )
            _collect_query_audit(request, result, tooling_layer)

            iid = result.get("interaction_id", "")
            if iid:
                try:
                    _last_id_path = os.path.expanduser("~/.local/share/nixos-ai-stack/last-interaction")
                    os.makedirs(os.path.dirname(_last_id_path), exist_ok=True)
                    with open(_last_id_path, "w") as _f:
                        _f.write(iid)
                except OSError:
                    pass

            # Phase 19 — Affective engine: modulate response if enabled
            if os.environ.get("AFFECTIVE_ENABLED", "false").lower() == "true":
                try:
                    _aff_bypass = request.headers.get("X-Affective-Bypass", "false").lower() == "true"
                    if not _aff_bypass and result.get("response"):
                        _aff_eng_dir = str(affective_handlers._AFFECTIVE_DIR)
                        if _aff_eng_dir not in sys.path:
                            sys.path.insert(0, _aff_eng_dir)
                        from signal_detectors import SignalDetectors as _SigDet  # noqa: PLC0415
                        from state_model import AffectiveState as _AffState  # noqa: PLC0415
                        from output_modulator import OutputModulator as _OutMod  # noqa: PLC0415
                        from reciprocity_tracker import ReciprocityTracker as _RecTrack  # noqa: PLC0415
                        _req_ctx = {"query": query}
                        _det = _SigDet()
                        _session_id = request.headers.get("X-Session-ID") or iid or "default"
                        _reciprocity = _RecTrack()
                        _reciprocity.record_give(_session_id, 1.0)
                        _state = _AffState(
                            empathy_signal=_det.detect_empathy(_req_ctx),
                            compassion_level=_det.detect_compassion(_req_ctx),
                            aesthetic_gap=_det.detect_aesthetic_gap(result.get("response", "")),
                            reciprocity_debt=_reciprocity.get_debt(_session_id),
                        )
                        result["response"] = _OutMod().modulate(result["response"], _state)
                        # Cache state snapshot for /affective/state endpoint
                        affective_handlers.update_state_snapshot({
                            "empathy_signal": _state.empathy_signal,
                            "reciprocity_debt": _state.reciprocity_debt,
                            "aesthetic_gap": _state.aesthetic_gap,
                            "compassion_level": _state.compassion_level,
                            "dominant_signal": _state.dominant_signal(),
                            "timestamp": _state.timestamp.isoformat(),
                        })
                except Exception as _aff_exc:
                    logger.debug("affective pipeline skipped (non-fatal): %s", _aff_exc)

            # Phase 54.2 — annotate result with detected intent (merged with semantic boost if available)
            final_intent = result.get("intent_classification", {})
            result["intent_classification"] = {
                "intent": final_intent.get("intent", _detected_intent),
                "confidence": final_intent.get("confidence", _intent_conf),
                "profile": final_intent.get("profile", _intent_result.get("profile", "local")),
                "cognitive_lift": final_intent.get("cognitive_lift", 0.0),
                "classification_mode": final_intent.get("classification_mode", "keyword_fallback"),
                "layers_active": final_intent.get("layers_active", ["L5:Session"])
            }

            # Phase 55.3 — Reasoning Drift Detection (Layer 6)
            import drift_analyzer
            _resp_text = result.get("response", "")
            if _resp_text and _detected_intent != "unknown":
                _drift = await drift_analyzer.get_analyzer().compute_live_drift(_resp_text, _detected_intent)
                result["intent_classification"]["drift"] = _drift
                if not _drift.get("is_stable", True):
                    logger.warning("reasoning_drift_detected intent=%s score=%.3f", _detected_intent, _drift["drift_score"])

            # Phase 55.2 — Memory Crystallization (Layer 5)
            import memory_crystallizer
            _session_id = data.get("session_id") or request_context.get("session_id")
            if _session_id and _multi_turn_manager:
                _session = await _multi_turn_manager.load_session(_session_id)
                if _session and _session.turn_count > 0 and _session.turn_count % 5 == 0:
                    # Every 5 turns, crystallize the queries into facts
                    # Construct a history from queries
                    _history = [{"role": "user", "content": q} for q in _session.queries]
                    asyncio.create_task(memory_crystallizer.get_crystallizer().crystallize_session(
                        _history, metadata={"session_id": _session_id}
                    ))

            # Phase 56 — Homeostasis & Self-Correction (L6 Active Remediation)
            import homeostasis_manager
            _hm = homeostasis_manager.get_manager()
            _stability = await _hm.evaluate_stability(result, session_id=_session_id)
            if _stability.get("status") == "remediating":
                result["homeostasis"] = _stability["remediation"]
                logger.info("homeostasis: applied remediation for intent=%s", _detected_intent)

            # Phase 137 — RAGAS auto-scoring (fire-and-forget, 20% sample)
            import random as _random_ragas
            if result.get("response") and _random_ragas.random() < 0.20:
                _q_ragas = query
                _r_ragas = result["response"]
                _i_ragas = _detected_intent
                _m_ragas = str(result.get("backend", "")) or os.getenv("ACTIVE_LLM_MODEL", "")
                _inner_ragas = result.get("results") or {}
                _docs_ragas = (
                    _inner_ragas.get("combined_results") or
                    _inner_ragas.get("semantic_results") or
                    _inner_ragas.get("keyword_results") or []
                )
                async def _ragas_score(q=_q_ragas, r=_r_ragas, intent=_i_ragas,
                                       model=_m_ragas, docs=_docs_ragas):
                    try:
                        ar = await eval_runner.score_answer_relevance(q, r)
                        cp = eval_runner.score_context_precision(docs)
                        # Phase 139 — faithfulness (Qwen-as-judge, 10% sample when env enabled)
                        _ctx = " ".join(
                            str(d.get("content") or d.get("text") or d.get("snippet") or "")[:300]
                            for d in (docs if isinstance(docs, list) else [])
                            if isinstance(d, dict)
                        )[:800]
                        fs = await eval_runner.score_faithfulness_async(q, _ctx, r) if _ctx else None
                        await eval_runner.record_query_metrics(
                            query_text=q, intent=intent, llm_model=model,
                            answer_relevance=ar, context_precision=cp, faithfulness=fs,
                        )
                    except Exception as _ragas_exc:
                        logger.debug("ragas_autoscore_failed: %s", _ragas_exc)
                asyncio.create_task(_ragas_score())

            # Phase 54.5 — commit trace span
            asyncio.create_task(_trace._commit(
                int((time.perf_counter() - _trace._start) * 1000)
            ))
            return web.json_response(result)
        except Exception as exc:
            audit_metadata = request.get("audit_metadata")
            if isinstance(audit_metadata, dict):
                audit_metadata.setdefault(
                    "generate_response",
                    generate_response if "generate_response" in locals() else False,
                )
                prefer_local = bool(data.get("prefer_local", True)) if "data" in locals() and isinstance(data, dict) else True
                if str(audit_metadata.get("backend", "unknown")) == "unknown":
                    audit_metadata["backend"] = "local" if prefer_local else "remote"
            _qh_query = query[:120] if "query" in locals() else ""
            logger.exception(
                "query_handler_failed query=%r generate_response=%s prefer_local=%s",
                _qh_query,
                generate_response if "generate_response" in locals() else False,
                prefer_local if "prefer_local" in locals() else True,
            )
            # Phase 138.2 — Attention queue: surface unexpected query-path exceptions (auto_ok → archive)
            _qh_exc_msg = str(exc)[:200]
            _qh_exc_type = type(exc).__name__

            def _push_query_attention(_q=_qh_query, _t=_qh_exc_type, _e=_qh_exc_msg):
                try:
                    from attention_queue import push as _aq_push  # noqa: PLC0415
                    _aq_push(
                        source="query-handler",
                        severity="medium",
                        autonomy_boundary="auto_ok",
                        title=f"Unexpected query handler exception: {_t}",
                        detail=f"Query: {_q!r}. {_t}: {_e}.",
                        proposed_action=(
                            "Check coordinator logs for stack trace. "
                            "If persistent, investigate route_search or memory recall path."
                        ),
                    )
                except Exception:
                    pass

            try:
                asyncio.create_task(asyncio.to_thread(_push_query_attention))
            except RuntimeError:
                pass  # no running loop during tests

            return web.json_response({"error": "route_search_failed", "detail": str(exc)}, status=500)

    async def handle_query_http(request):
        """Normalize public /query requests through the same facade used by /v1/orchestrate."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)
        body = json.dumps(data).encode()
        shim = _QueryShimRequest(body, request)
        resp = await handle_query(shim)
        # Propagate audit_metadata from shim back to the real aiohttp request so
        # the request_id_middleware audit hook can read backend/routing telemetry.
        audit_meta = shim.get("audit_metadata")
        if isinstance(audit_meta, dict):
            request["audit_metadata"] = audit_meta
        return resp

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

        # Agent routes should synthesize by default; retrieval-only routes do not.
        _agent_routes = {"local-agent", "LocalAgent", "Agent", "embedded-assist", "EmbeddedAssist"}
        _default_generate = raw_route in _agent_routes or resolved_profile in {
            "local-agent", "embedded-assist",
        }
        forwarded_payload = {
            "prompt": prompt,
            "context": context,
            "generate_response": bool(options.get("generate_response", _default_generate)),
            "prefer_local": bool(options.get("prefer_local", True)),
            "mode": options.get("mode", "hybrid"),
            # Propagate LLM timeout hint from caller — defaults to 180s for local synthesis.
            "llm_timeout_s": options.get("llm_timeout_s", data.get("llm_timeout_s", 180)),
        }
        if "limit" in options:
            forwarded_payload["limit"] = options["limit"]

        shim = _QueryShimRequest(json.dumps(forwarded_payload).encode(), request)
        resp = await handle_query(shim)

        # Propagate audit_metadata from shim back to the real aiohttp request so
        # the request_id_middleware audit hook can read backend/routing telemetry.
        audit_meta = shim.get("audit_metadata")
        if isinstance(audit_meta, dict):
            request["audit_metadata"] = audit_meta

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
                score_threshold=float(data.get("score_threshold", Config.AI_SEARCH_SCORE_THRESHOLD)),
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

    # Phase 15.1: Model fleet status endpoint
    async def handle_fleet_status(request: web.Request) -> web.Response:
        try:
            status = await _mfm.get_fleet_status()
            return web.json_response(status)
        except Exception as exc:
            logger.exception("handle_fleet_status error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    # Phase 15.3: Journal read endpoints
    async def _fallback_handle_journal_entries(request: web.Request) -> web.Response:  # noqa: F841  R2.3 fallback
        try:
            params = request.rel_url.query
            entries = await _journal.get_entries(
                limit=int(params.get("limit", "50")),
                model_id=params.get("model_id") or None,
                tier=params.get("tier") or None,
                task_archetype=params.get("task_archetype") or None,
                success_only=params.get("success_only", "").lower() == "true",
                errors_only=params.get("errors_only", "").lower() == "true",
                since_epoch=float(params.get("since_epoch", "0")),
            )
            return web.json_response({"entries": entries, "count": len(entries)})
        except Exception as exc:
            logger.exception("handle_journal_entries error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def _fallback_handle_journal_stats(request: web.Request) -> web.Response:  # noqa: F841  R2.3 fallback
        try:
            params = request.rel_url.query
            stats = await _journal.get_stats(
                since_epoch=float(params.get("since_epoch", "0")),
            )
            return web.json_response(stats)
        except Exception as exc:
            logger.exception("handle_journal_stats error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    # R2.5: Inject OrchestrationService closure refs before create_app() wires routes.
    from workflow import orchestration_service as _orchestration_service
    _orchestration_service.configure(
        handle_orchestrate_fn=handle_orchestrate,
        handle_tree_search_fn=handle_tree_search,
    )

    # R2.4: Inject QueryService closure refs before create_app() wires routes.
    from query import query_service as _query_service
    _query_service.configure(
        handle_query_fn=handle_query,
        handle_query_http_fn=handle_query_http,
        handle_augment_query_fn=handle_augment_query,
    )

    # R2.2: middleware + StatusService routes owned by router.py.
    # Rate limiter config is now in router._make_rate_limit_config().
    from router import create_app as _create_router_app
    http_app = _create_router_app(audit_request_fn=_audit_http_request)
    scheduler = get_scheduler()

    async def _scheduler_startup(_app):
        await scheduler.start()

    async def _scheduler_cleanup(_app):
        await scheduler.stop()

    http_app.on_startup.append(_scheduler_startup)
    http_app.on_cleanup.append(_scheduler_cleanup)

    # Phase 69.3: Wire TemporalGraph into aiohttp app dict
    try:
        from knowledge.temporal_graph import TemporalGraph as _TemporalGraph
        http_app["temporal_graph"] = _TemporalGraph(_POSTGRES_CLIENT)
        logger.info("temporal_graph: initialized and wired into http_app")
    except Exception as _tg_exc:
        logger.warning("temporal_graph: startup wiring skipped: %s", _tg_exc)

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

    # R2.6: /a2a/* now owned by agent_service (router.py).
    # openai_a2a_handlers.register_routes(http_app)  # _fallback
    ops_handlers.register_routes(http_app)
    # R2.2: /status, /api/hardware/state, /stats/delegate now registered by router.py
    # R2.3: /api/memory/facts, /memory/journal* now registered by router.py (MemoryService)
    # R2.6: /api/agent-ops/status, /api/agent-events now owned by agent_service (router.py).
    # http_app.router.add_get("/api/agent-ops/status", handle_agent_ops_status)   # _fallback
    # http_app.router.add_post("/api/agent-events", handle_agent_events_post)     # _fallback
    # http_app.router.add_get("/api/agent-events", handle_agent_events_get)       # _fallback
    # R2.4: /augment_query, /query, /api/query now owned by query_service (router.py).
    # http_app.router.add_post("/augment_query", handle_augment_query)  # _fallback_handle_augment_query
    # http_app.router.add_post("/query", handle_query_http)            # _fallback_handle_query_http
    # http_app.router.add_post("/api/query", handle_query_http)        # _fallback_handle_query_http
    # R2.6: /admin/v1/scheduler/status now owned by control_service (router.py).
    # http_app.router.add_get("/admin/v1/scheduler/status", handle_scheduler_status)  # _fallback
    # R2.5: /v1/orchestrate, /search/tree now owned by orchestration_service (router.py).
    # http_app.router.add_post("/v1/orchestrate", handle_orchestrate)  # _fallback_handle_orchestrate
    # http_app.router.add_post("/search/tree", handle_tree_search)     # _fallback_handle_tree_search
    memory_context_handlers.register_routes(http_app)
    hints_handlers.register_routes(http_app)
    workflow_session_handlers.register_routes(http_app)
    ai_coordinator_handlers.register_routes(http_app)  # Phase 12.4: extracted to ai_coordinator_handlers.py
    # Phase 12.1/12.2 — Model Coordination + LLM Router endpoints
    llm_router_handlers.register_routes(http_app)
    # Batch 3.2 — PRSI Action Execution endpoints
    prsi_handlers.register_routes(http_app)
    # R2.6: /control/* now owned by control_service (router.py).
    # runtime_control_handlers.register_routes(http_app)  # _fallback
    # R2.5: orchestration_graph_runner routes now owned by orchestration_service (router.py).
    # orchestration_graph_runner.register_routes(http_app)  # _fallback Phase 49: multi-agent graph runner

    # Phase 5 — Model Optimization + Advanced Features endpoints
    model_opt_handlers.register_routes(http_app)
    # Phase 4.2 + 1.3 + review/acceptance
    orchestration_handlers.register_routes(http_app)

    # Phase 1: WebSocket alert endpoint
    http_app.router.add_get("/ws/alerts", handle_alerts_websocket)


    agents_task_handlers.register_routes(http_app)  # Phase 12.4: extracted to agents_task_handlers.py

    evidence_safety_handlers.register_routes(http_app)

    # R2.6: /control/model-fleet/status now owned by control_service (router.py).
    # http_app.router.add_get("/control/model-fleet/status", handle_fleet_status)  # _fallback
    # R2.3: /memory/journal* now registered by router.py (MemoryService)
    # Phase 16.4: Identity kernel
    identity_handlers.register_routes(http_app)
    affective_handlers.register_routes(http_app)  # Phase 19: values signals
    trading_handlers.register_routes(http_app)          # Phase 24: trading analysis (all-agent API)
    auto_tool_select_handlers.register_routes(http_app)  # Phase 24: autonomous tool auto-selection
    context_summary_handlers.register_routes(http_app)   # Phase 25-007: /agent/summarize-context + working-memory

    # Phase 54: Agentic-First Architecture Elevation routes
    http_app.router.add_get("/memory/broker/status", memory_broker.handle_broker_status)
    # R2.3: superseder + crystallizer now registered by router.py (MemoryService)
    drift_analyzer_routes.register_routes(http_app)
    http_app.router.add_get("/control/intent/map", intent_classifier.handle_get_intent_map)
    http_app.router.add_post("/control/intent/reload", intent_classifier.handle_reload_intent_map)
    http_app.router.add_get("/api/health/rag", rag_augmentor.handle_rag_health)
    http_app.router.add_get("/homeostasis/events", lambda r: web.json_response(homeostasis_manager.get_manager().get_recent_events()))
    # R2.6: /api/traces, /eval/run, /eval/trend now owned by insights_service (router.py).
    # http_app.router.add_get("/api/traces", trace_collector.handle_get_traces)  # _fallback
    # http_app.router.add_post("/eval/run", eval_runner.handle_eval_run)         # _fallback
    # http_app.router.add_get("/eval/trend", eval_runner.handle_eval_trend)      # _fallback

    # Phase 26: Unified Agent Orchestration Gateway
    _lifecycle_dir = Path(
        os.environ.get("DATA_DIR", os.path.expanduser("~/.local/share/nixos-ai-stack/hybrid"))
    ) / "lifecycle"
    intake_gateway.init(
        lifecycle_dir=_lifecycle_dir,
        switchboard_url=os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085"),
        cli_bridge_url=os.environ.get("CLI_BRIDGE_URL", "http://127.0.0.1:8089"),
        hints_url=os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003"),
        error_payload_fn=_error_payload,
    )
    intake_gateway.register_routes(http_app)

    # Phase 20: World Model — /world/forecast (inline handler)
    async def handle_world_forecast(request):
        """GET /world/forecast — current intent predictions + latest warming log."""
        import json as _json
        _wm_dir = str(Path(__file__).resolve().parent.parent.parent / "world-model")
        if _wm_dir not in sys.path:
            sys.path.insert(0, _wm_dir)
        forecast_data = {"predictions": [], "sources": [], "warming_log": None}
        try:
            from intent_forecaster import IntentForecaster as _IF  # noqa: PLC0415
            result = _IF().forecast()
            forecast_data["predictions"] = result.predictions
            forecast_data["sources"] = result.sources
        except Exception as _exc:
            logger.debug("world_forecast forecaster error (non-fatal): %s", _exc)
        try:
            _log_path = os.path.join(
                os.environ.get("DATA_DIR", "/var/lib/ai-stack/hybrid"),
                "telemetry", "world-model-warm-latest.json",
            )
            if os.path.exists(_log_path):
                with open(_log_path) as _f:
                    forecast_data["warming_log"] = _json.load(_f)
        except Exception:
            pass
        return web.json_response(forecast_data)

    http_app.router.add_get("/world/forecast", handle_world_forecast)

    # Phase 2.4: Register YAML workflow routes
    if YAML_WORKFLOWS_AVAILABLE:
        try:
            yaml_workflow_handlers.register_routes(http_app)
            logger.info("YAML workflow routes registered")
        except Exception as e:
            logger.error(f"Failed to register YAML workflow routes: {e}")

    # Start IPM Phase B polling
    await get_ipm().start()

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
