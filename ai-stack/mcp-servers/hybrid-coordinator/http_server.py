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
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from aiohttp import web
import httpx
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import Config, OptimizationProposal, apply_proposal, routing_config
from metrics import (
    CAPABILITY_GAP_DETECTIONS,
    DELEGATED_PROMPT_TOKENS_AFTER,
    DELEGATED_PROMPT_TOKENS_BEFORE,
    DELEGATED_PROMPT_TOKEN_SAVINGS,
    DELEGATED_QUALITY_EVENTS,
    DELEGATED_QUALITY_SCORE,
    META_LEARNING_ADAPTATIONS,
    ORCHESTRATION_ACTIVE_SESSIONS,
    ORCHESTRATION_ACTIVE_WORKSPACES,
    ORCHESTRATION_CHECKPOINTS_CREATED,
    ORCHESTRATION_CHECKPOINTS_RESTORED,
    ORCHESTRATION_DELEGATIONS_COMPLETED,
    ORCHESTRATION_PENDING_DELEGATIONS,
    ORCHESTRATION_REGISTERED_AGENTS,
    ORCHESTRATION_TOOL_CACHE_HITS,
    ORCHESTRATION_TOOL_INVOCATIONS,
    ORCHESTRATION_TOOL_PENDING_APPROVALS,
    ORCHESTRATION_WORKSPACES_BY_MODE,
    PROCESS_MEMORY_BYTES,
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
from memory_manager import coerce_memory_summary, normalize_memory_type, get_memory_latency_metrics
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
from browser_research import fetch_browser_research
from web_research import fetch_web_research
from research_workflows import list_curated_research_workflows, run_curated_research_workflow
from delegation_feedback import build_recovered_artifact, classify_delegated_response, record_delegation_feedback
from model_coordinator import (
    get_model_coordinator as _get_model_coordinator,
    classify_and_route_task as _classify_and_route_task,
)
import mcp_handlers

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
from alert_engine import AlertEngine, AlertSeverity, AlertStatus
from agent_pool_manager import AgentPoolManager, AgentTier, RemoteAgent
from quality_assurance import QualityChecker, QualityThreshold, ResultCache, ResultRefiner, QualityTrendTracker
from prompt_compression import CompressionStrategy, PromptCompressor
from context_management import ContextChunk, ContextPruner
from multi_tier_loading import (
    ContextRepository as DisclosureContextRepository,
    MultiTierLoader,
    TierSelector,
)
from lazy_context import ContextDependencyGraph, ContextNode, LazyContextLoader
from relevance_prediction import NegativeContextFilter, RelevancePredictor
from gap_detection import GapDetector, GapType
from gap_remediation import RemediationPlan, RemediationResult, RemediationStatus, RemediationStrategy
from remediation_learning import OutcomeTracker, PlaybookLibrary, StrategyOptimizer
from online_learning import IncrementalLearner, LearningExample, UpdateStrategy, HintQualityAdjuster, LivePatternMiner
from feedback_acceleration import ImmediateFeedbackProcessor, SuccessFailureDetector
from meta_learning import RapidAdaptor, Task, TaskDomain

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
_DELEGATED_QUALITY_CHECKER = QualityChecker(threshold=QualityThreshold.ACCEPTABLE)
_DELEGATED_RESULT_REFINER = ResultRefiner()
_DELEGATED_RESULT_CACHE = ResultCache()
_DELEGATED_QUALITY_TRACKER = QualityTrendTracker()
_DELEGATED_PROMPT_COMPRESSOR = PromptCompressor()
_DELEGATED_CONTEXT_PRUNER = ContextPruner()
_DISCLOSURE_CONTEXT_DIR = Path(
    os.getenv("DISCLOSURE_CONTEXT_DIR", "/var/lib/ai-stack/hybrid/context-tiers")
)
_REMEDIATION_PLAYBOOKS_DIR = Path(
    os.getenv("REMEDIATION_PLAYBOOKS_DIR", "/var/lib/ai-stack/hybrid/playbooks")
)
_DISCLOSURE_REPOSITORY = DisclosureContextRepository(_DISCLOSURE_CONTEXT_DIR)
_DISCLOSURE_TIER_SELECTOR = TierSelector()
_DISCLOSURE_TIER_LOADER = MultiTierLoader(_DISCLOSURE_REPOSITORY)
_DISCLOSURE_RELEVANCE_PREDICTOR = RelevancePredictor()
_DISCLOSURE_NEGATIVE_FILTER = NegativeContextFilter(threshold=0.25)
_GAP_DETECTOR = GapDetector()
_REMEDIATION_OUTCOME_TRACKER = OutcomeTracker()
_REMEDIATION_STRATEGY_OPTIMIZER = StrategyOptimizer(_REMEDIATION_OUTCOME_TRACKER)
_REMEDIATION_PLAYBOOK_LIBRARY = PlaybookLibrary(_REMEDIATION_PLAYBOOKS_DIR)
_ONLINE_LEARNER = IncrementalLearner(update_strategy=UpdateStrategy.BATCH)
_HINT_QUALITY_ADJUSTER = HintQualityAdjuster()
_LIVE_PATTERN_MINER = LivePatternMiner()
_IMMEDIATE_FEEDBACK_PROCESSOR = ImmediateFeedbackProcessor()
_SUCCESS_FAILURE_DETECTOR = SuccessFailureDetector()
_RAPID_ADAPTOR = RapidAdaptor()

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
_runtime_registry_lock = asyncio.Lock()
_agent_lessons_lock = asyncio.Lock()
_agent_evaluations_lock = asyncio.Lock()
_TOOL_SECURITY_AUDITOR: Optional[ToolSecurityAuditor] = None
_INTENT_DEPTH_EXPECTATIONS = {"minimum", "standard", "deep"}
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
_ORCHESTRATION_ESCALATION_LANES = {"remote-reasoning", "flagship-remote", "none"}
_ORCHESTRATION_COLLABORATOR_LANES = _ORCHESTRATION_LANES | (_ORCHESTRATION_ESCALATION_LANES - {"none"})
_ORCHESTRATION_CONSENSUS_MODES = {"reviewer-gate", "evidence-review", "arbiter-review"}
_ORCHESTRATION_SELECTION_STRATEGIES = {"orchestrator-first", "local-first", "evidence-first", "escalate-on-complexity"}
_AQ_REPORT_LATEST_JSON = Path(
    os.getenv("AQ_REPORT_LATEST_JSON", "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
)

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


def _load_aq_report_status_summary() -> Dict[str, Any]:
    try:
        if not _AQ_REPORT_LATEST_JSON.exists():
            return {"available": False, "source": str(_AQ_REPORT_LATEST_JSON)}
        payload = json.loads(_AQ_REPORT_LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "source": str(_AQ_REPORT_LATEST_JSON),
            "error": str(exc)[:180],
        }

    continue_editor = payload.get("continue_editor") or {}
    continue_windows = ((payload.get("continue_editor_windows") or {}).get("windows") or {})
    workflow_review = payload.get("intent_contract_compliance") or {}
    retrieval_windows = ((payload.get("route_retrieval_breadth_windows") or {}).get("windows") or {})
    routing_windows = ((payload.get("routing_windows") or {}).get("windows") or {})
    remote_windows = ((payload.get("remote_profile_utilization_windows") or {}).get("windows") or {})
    route_latency = payload.get("route_search_latency_decomposition") or {}
    delegation_windows = ((payload.get("delegated_prompt_failure_windows") or {}).get("windows") or {})
    delegation_trend = ((payload.get("delegated_prompt_failure_windows") or {}).get("trend") or {})
    recommendations = [
        str(item).strip()
        for item in (payload.get("recommendations") or [])
        if str(item).strip()
    ]
    structured_actions = payload.get("structured_actions") or []
    compact_actions = []
    for item in structured_actions[:3]:
        if not isinstance(item, dict):
            continue
        compact_actions.append(
            {
                "type": str(item.get("type", "") or "").strip(),
                "action": str(item.get("action", "") or "").strip(),
                "reason": str(item.get("reason", "") or "").strip()[:180],
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "safe": bool(item.get("safe", False)),
            }
        )

    # Compute trend indicators for quick visibility
    def _trend_indicator(w1h: dict, w24h: dict, metric_key: str, higher_is_better: bool = True) -> str:
        """Return trend indicator: ↑ improving, ↓ worsening, → stable, ? unknown."""
        try:
            v1h = w1h.get(metric_key)
            v24h = w24h.get(metric_key)
            if v1h is None or v24h is None:
                return "?"
            v1h, v24h = float(v1h), float(v24h)
            if v24h == 0:
                return "→" if v1h == 0 else ("↑" if higher_is_better else "↓")
            ratio = v1h / v24h
            if ratio > 1.1:
                return "↑" if higher_is_better else "↓"
            elif ratio < 0.9:
                return "↓" if higher_is_better else "↑"
            return "→"
        except (TypeError, ValueError, ZeroDivisionError):
            return "?"

    routing_1h = routing_windows.get("1h", {})
    routing_24h = routing_windows.get("24h", {})
    retrieval_1h = retrieval_windows.get("1h", {})
    retrieval_24h = retrieval_windows.get("24h", {})
    delegation_1h = delegation_windows.get("1h", {})
    delegation_24h = delegation_windows.get("24h", {})

    return {
        "available": True,
        "source": str(_AQ_REPORT_LATEST_JSON),
        "generated_at": payload.get("generated_at", ""),
        "trend_summary": {
            "routing_local_pct": _trend_indicator(routing_1h, routing_24h, "local_pct", higher_is_better=True),
            "retrieval_rag_share": _trend_indicator(retrieval_1h, retrieval_24h, "rag_share_pct", higher_is_better=True),
            "delegation_failures": _trend_indicator(delegation_1h, delegation_24h, "total_failures", higher_is_better=False),
        },
        "continue_editor": {
            "healthy": bool(continue_editor.get("healthy", False)),
            "failed_n": int(continue_editor.get("failed_n", 0) or 0),
            "total_checks": int(continue_editor.get("total_checks", 0) or 0),
            "top_failure_category": continue_editor.get("top_failure_category"),
            "trend_1h": continue_windows.get("1h", {}),
            "trend_24h": continue_windows.get("24h", {}),
            "trend_7d": continue_windows.get("7d", {}),
        },
        "remote_profile_utilization": {
            "current": payload.get("remote_profile_utilization", {}),
            "trend_1h": remote_windows.get("1h", {}),
            "trend_24h": remote_windows.get("24h", {}),
            "trend_7d": remote_windows.get("7d", {}),
        },
        "routing": {
            "current": payload.get("routing", {}),
            "trend_1h": routing_1h,
            "trend_24h": routing_24h,
            "trend_7d": routing_windows.get("7d", {}),
            "latency": {
                "window": route_latency.get("window", ""),
                "overall_p95_ms": route_latency.get("overall_p95_ms"),
                "actionable_p95_ms": route_latency.get("actionable_p95_ms"),
                "backend_valid_p95_ms": route_latency.get("backend_valid_p95_ms"),
                "client_error_count": route_latency.get("client_error_count"),
                "top_breakdown": (route_latency.get("breakdown") or [])[:3],
            },
        },
        "retrieval": {
            "current": payload.get("route_retrieval_breadth", {}),
            "trend_1h": retrieval_1h,
            "trend_24h": retrieval_24h,
            "trend_7d": retrieval_windows.get("7d", {}),
        },
        "delegation_failures": {
            "trend_status": delegation_trend.get("status", "unknown"),
            "trend_summary": delegation_trend.get("summary", ""),
            "trend_1h": delegation_1h,
            "trend_24h": delegation_24h,
            "trend_7d": delegation_windows.get("7d", {}),
        },
        "workflow_review": {
            "required_reviews": int(workflow_review.get("required_reviews", 0) or 0),
            "accepted_reviews": int(workflow_review.get("accepted_reviews", 0) or 0),
            "rejected_reviews": int(workflow_review.get("rejected_reviews", 0) or 0),
            "top_review_types": (workflow_review.get("top_review_types") or [])[:3],
            "accepted_task_classes": (workflow_review.get("accepted_task_classes") or [])[:5],
            "accepted_by_reviewed_profile": (workflow_review.get("accepted_by_reviewed_profile") or [])[:5],
        },
        "optimization_watch": {
            "available": bool(recommendations or compact_actions),
            "recommendation_count": len(recommendations),
            "structured_action_count": len(structured_actions),
            "top_recommendations": recommendations[:3],
            "top_actions": compact_actions,
        },
    }


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


async def _switchboard_ai_coordinator_state() -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "remote_configured": bool(Config.SWITCHBOARD_REMOTE_URL),
        "remote_aliases": {
            "gemini": Config.SWITCHBOARD_REMOTE_ALIAS_GEMINI or Config.SWITCHBOARD_REMOTE_ALIAS_FREE or None,
            "free": Config.SWITCHBOARD_REMOTE_ALIAS_FREE or None,
            "coding": Config.SWITCHBOARD_REMOTE_ALIAS_CODING or None,
            "reasoning": Config.SWITCHBOARD_REMOTE_ALIAS_REASONING or None,
            "tool_calling": Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING or None,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{Config.SWITCHBOARD_URL.rstrip('/')}/health")
        if response.status_code != 200:
            return state
        payload = response.json()
        profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
        state["remote_configured"] = bool(payload.get("remote_configured", state["remote_configured"]))
        state["remote_aliases"] = {
            "gemini": ((profiles.get("remote-gemini") or {}).get("model_alias")) or state["remote_aliases"]["gemini"],
            "free": ((profiles.get("remote-free") or {}).get("model_alias")) or state["remote_aliases"]["free"],
            "coding": ((profiles.get("remote-coding") or {}).get("model_alias")) or state["remote_aliases"]["coding"],
            "reasoning": ((profiles.get("remote-reasoning") or {}).get("model_alias")) or state["remote_aliases"]["reasoning"],
            "tool_calling": ((profiles.get("remote-tool-calling") or {}).get("model_alias")) or state["remote_aliases"]["tool_calling"],
        }
    except Exception:
        return state
    return state


def _coordinator_requested_profile(request: web.Request, payload: Dict[str, Any] | None = None) -> str:
    profile = str(request.headers.get("X-AI-Profile") or "").strip().lower()
    if profile:
        return profile
    profile = str(request.rel_url.query.get("ai_profile") or "").strip().lower()
    if profile:
        return profile
    if isinstance(payload, dict):
        profile = str(payload.get("ai_profile") or payload.get("profile") or "").strip().lower()
        if profile:
            return profile
    return ""


def _coordinator_prefer_local(request: web.Request, payload: Dict[str, Any] | None = None) -> bool:
    raw = str(request.headers.get("X-AI-Prefer-Local") or "").strip().lower()
    if raw in {"0", "false", "no", "remote"}:
        return False
    if raw in {"1", "true", "yes", "local"}:
        return True
    raw = str(request.rel_url.query.get("prefer_local") or "").strip().lower()
    if raw in {"0", "false", "no", "remote"}:
        return False
    if raw in {"1", "true", "yes", "local"}:
        return True
    if isinstance(payload, dict) and "prefer_local" in payload:
        return bool(payload.get("prefer_local"))
    return True


async def _proxy_openai_request_via_coordinator(
    request: web.Request,
    payload: Dict[str, Any],
    *,
    path: str,
) -> web.Response:
    requested_profile = _coordinator_requested_profile(request, payload)
    prefer_local = _coordinator_prefer_local(request, payload)

    if path == "chat/completions":
        routing = _ai_coordinator_route_openai_chat_payload(
            payload,
            requested_profile=requested_profile,
            prefer_local=prefer_local,
        )
    else:
        task = str(payload.get("prompt") or "").strip() or _ai_coordinator_extract_task_from_openai_messages(payload.get("messages"))
        routing = _ai_coordinator_route_by_complexity(
            task or "continue completion request",
            requested_profile=requested_profile,
            prefer_local=prefer_local,
        )
        routing["task"] = task

    selected_profile = str(routing.get("recommended_profile") or "default").strip() or "default"
    outbound_headers = {
        "Content-Type": "application/json",
        "X-AI-Profile": "continue-local" if selected_profile == "default" else selected_profile,
        "X-AI-Route": "local" if selected_profile in {"default", "local-tool-calling"} else "remote",
    }
    if "Authorization" in request.headers:
        outbound_headers["Authorization"] = request.headers["Authorization"]

    timeout_s = float(payload.get("timeout_s") or 120.0)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        upstream = await client.post(
            f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/{path}",
            headers=outbound_headers,
            json=payload,
        )

    content_type = upstream.headers.get("content-type", "application/json")
    response = web.Response(
        status=upstream.status_code,
        body=upstream.content,
        content_type=content_type.split(";", 1)[0] if content_type else None,
    )
    response.headers["X-AI-Profile"] = selected_profile
    response.headers["X-Coordinator-Task-Archetype"] = str(routing.get("task_archetype") or "")
    response.headers["X-Coordinator-Model-Class"] = str(routing.get("model_class") or "")
    response.headers["X-Coordinator-Complexity"] = str(routing.get("complexity") or "")
    return response


async def _aidb_shared_skills_catalog(limit: int = 25) -> Dict[str, Any]:
    aidb_url = Config.AIDB_URL.rstrip("/")
    if not aidb_url:
        return {"available": False, "source": "", "skills": []}
    cache_bust = str(time.time_ns())
    url = f"{aidb_url}/skills?include_pending=true&_={cache_bust}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"available": False, "source": url, "skills": [], "error": str(exc)[:180]}

    skills = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).strip().lower() != "approved":
            continue
        skills.append(
            {
                "slug": str(item.get("slug", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "description": str(item.get("description", "")).strip(),
                "managed_by": str(item.get("managed_by", "")).strip(),
                "source_path": str(item.get("source_path", "")).strip(),
            }
        )
    skills = [item for item in skills if item["slug"]]
    skills.sort(key=lambda item: item["slug"])
    return {
        "available": True,
        "source": url,
        "skills": skills[:limit],
        "total": len(skills),
        "truncated": len(skills) > limit,
    }


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
        runtime["status"] = "degraded"
    return runtime


def _agent_pool_status_snapshot() -> Dict[str, Any]:
    """Return compact remote agent-pool status for health and operator surfaces."""
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
            item["tier"] != AgentTier.FREE.value,
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
) -> Optional[RemoteAgent]:
    """Select a pool agent for remote-free or fallback routing."""
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
            if agent.tier != AgentTier.FREE and agent.is_available():
                return agent
    return None


# ---------------------------------------------------------------------------
# Phase 20.2: Priority-based delegation with automatic failover
# ---------------------------------------------------------------------------

# Task type to agent capability mapping
_TASK_TYPE_CAPABILITIES = {
    "coding": {
        "priority_profiles": ["remote-coding", "remote-gemini", "remote-free", "local-tool-calling", "default"],
        "required_context_window": 8192,
        "prefer_free_first": False,
    },
    "reasoning": {
        "priority_profiles": ["remote-reasoning", "remote-gemini", "remote-free", "default"],
        "required_context_window": 8192,
        "prefer_free_first": False,
    },
    "tool-calling": {
        "priority_profiles": ["remote-tool-calling", "local-tool-calling", "remote-gemini", "remote-free", "default"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
    "simple": {
        "priority_profiles": ["remote-gemini", "remote-free", "default", "local-tool-calling"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
    "default": {
        "priority_profiles": ["remote-gemini", "remote-free", "default", "local-tool-calling"],
        "required_context_window": 4096,
        "prefer_free_first": True,
    },
}


def _detect_task_type(task: str, profile: str = "") -> str:
    """Detect task type from task description for capability-based routing."""
    task_lower = (task or "").lower()

    # Explicit profile overrides detection
    if profile:
        profile_lower = profile.lower()
        if "coding" in profile_lower or "implement" in profile_lower:
            return "coding"
        if "reasoning" in profile_lower or "architecture" in profile_lower:
            return "reasoning"
        if "tool" in profile_lower:
            return "tool-calling"
        return "default"

    # Detect from task content
    coding_keywords = ["implement", "code", "function", "class", "fix bug", "refactor", "patch", "script"]
    reasoning_keywords = ["architecture", "design", "review", "analyze", "tradeoff", "strategy", "plan"]
    tool_keywords = ["run", "execute", "command", "script", "deploy", "build", "test"]

    if any(kw in task_lower for kw in coding_keywords):
        return "coding"
    if any(kw in task_lower for kw in reasoning_keywords):
        return "reasoning"
    if any(kw in task_lower for kw in tool_keywords):
        return "tool-calling"

    # Simple heuristic: short tasks are likely simple
    if len(task_lower.split()) <= 10:
        return "simple"

    return "default"


def _build_delegation_fallback_chain(
    task: str,
    requested_profile: str = "",
    prefer_local: bool = False,
) -> List[Dict[str, Any]]:
    """Build a prioritized fallback chain of delegation targets.

    Phase 20.2: Returns an ordered list of delegation attempts with:
    - profile: The routing profile to use
    - runtime_id: The corresponding runtime ID
    - reason: Why this profile is in the chain
    - is_local: Whether this is a local delegation
    """
    task_type = _detect_task_type(task, requested_profile)
    capabilities = _TASK_TYPE_CAPABILITIES.get(task_type, _TASK_TYPE_CAPABILITIES["default"])

    chain = []
    seen_profiles = set()

    for profile in capabilities["priority_profiles"]:
        if profile in seen_profiles:
            continue
        seen_profiles.add(profile)

        # Skip local profiles if we already tried local
        is_local = "local" in profile.lower()

        # Determine runtime ID for this profile
        try:
            from ai_coordinator import _profile_to_runtime_id  # type: ignore
            runtime_id = _profile_to_runtime_id(profile)
        except Exception:
            # Fallback mapping
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

        chain.append({
            "profile": profile,
            "runtime_id": runtime_id,
            "reason": f"{task_type} task: {profile} (priority {len(chain) + 1})",
            "is_local": is_local,
            "context_window": capabilities["required_context_window"],
        })

    # If prefer_local is set, ensure local is in the chain
    if prefer_local and not any(c["is_local"] for c in chain):
        chain.append({
            "profile": "default",
            "runtime_id": "local-hybrid",
            "reason": "prefer_local flag: local fallback",
            "is_local": True,
            "context_window": 4096,
        })

    return chain


def _check_runtime_available(runtime_id: str) -> bool:
    """Check if a runtime is currently available."""
    try:
        from switchboard_state import get_switchboard_state  # type: ignore
        state = get_switchboard_state()
        runtime_status = state.get_runtime_status(runtime_id)
        return runtime_status in ("ready", "degraded")
    except Exception:
        # If we can't check, assume available (will fail gracefully later)
        return True


def _check_agent_available_for_profile(profile: str) -> bool:
    """Check if any agent is available for the given profile."""
    if not _remote_profile_uses_agent_pool(profile):
        return True  # Non-pool profiles are assumed available

    # Check if any agent in the pool is available
    for agent in _AGENT_POOL_MANAGER.agents.values():
        if agent.is_available() and not agent.is_rate_limited():
            return True

    return False


def _select_next_available_delegation_target(
    fallback_chain: List[Dict[str, Any]],
    exclude_profiles: Optional[Set[str]] = None,
    exclude_agent_id: str = "",
) -> Optional[Dict[str, Any]]:
    """Select the next available delegation target from the fallback chain.

    Phase 20.2: Proactively checks availability before attempting delegation.
    Returns the first available target, or None if all are unavailable.
    """
    exclude = exclude_profiles or set()

    for target in fallback_chain:
        profile = target["profile"]
        runtime_id = target["runtime_id"]

        # Skip excluded profiles
        if profile in exclude:
            continue

        # Check runtime availability
        if not _check_runtime_available(runtime_id):
            logger.info("delegation_failover: runtime %s unavailable, skipping", runtime_id)
            continue

        # Check agent pool availability for pool-based profiles
        if not _check_agent_available_for_profile(profile):
            logger.info("delegation_failover: no agents available for %s, skipping", profile)
            continue

        # This target is available
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
    """Extract assistant text from delegated response payloads."""
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
    """Write assistant text back into delegated response payloads."""
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
    """Assess, refine, cache, and trend delegated responses."""
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
        part for part in [
            str(task or "").lower(),
            json.dumps(context, sort_keys=True).lower() if isinstance(context, dict) and context else "",
        ] if part
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
    """Attach progressively selected context chunks to delegated message envelopes."""
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


def _capability_gap_status_snapshot() -> Dict[str, Any]:
    top_gaps = _GAP_DETECTOR.get_top_gaps(limit=5)
    return {
        "detected_gap_count": len(_GAP_DETECTOR.detected_gaps),
        "tracked_outcomes": len(_REMEDIATION_OUTCOME_TRACKER.outcomes),
        "top_gaps": [
            {
                "gap_id": gap.gap_id,
                "gap_type": gap.gap_type.value,
                "severity": gap.severity.name.lower(),
                "priority_score": round(float(gap.priority_score or 0.0), 4),
                "description": gap.description,
            }
            for gap in top_gaps
        ],
    }


def _real_time_learning_status_snapshot() -> Dict[str, Any]:
    top_hints = _HINT_QUALITY_ADJUSTER.get_top_hints(limit=5)
    pending_actions = _IMMEDIATE_FEEDBACK_PROCESSOR.get_pending_actions(limit=5)
    return {
        "learning_buffer_size": len(_ONLINE_LEARNER.learning_buffer),
        "update_count": len(_ONLINE_LEARNER.update_history),
        "pattern_count": len(_LIVE_PATTERN_MINER.patterns),
        "top_hints": [[hint_id, round(float(score), 4)] for hint_id, score in top_hints],
        "pending_feedback_actions": [
            {
                "action_id": action.action_id,
                "description": action.description,
                "priority": round(float(action.priority), 4),
            }
            for action in pending_actions
        ],
    }


def _meta_learning_status_snapshot() -> Dict[str, Any]:
    optimizer_history = _RAPID_ADAPTOR.meta_optimizer.optimization_history
    latest = optimizer_history[-1] if optimizer_history else {}
    return {
        "cached_adaptations": len(_RAPID_ADAPTOR.adaptation_cache),
        "meta_update_count": len(_RAPID_ADAPTOR.maml.update_history),
        "known_task_embeddings": len(_RAPID_ADAPTOR.embedder.task_embeddings),
        "known_domain_prototypes": len(_RAPID_ADAPTOR.few_shot.prototypes),
        "latest_hyperparams": dict(_RAPID_ADAPTOR.meta_optimizer.hyperparams),
        "latest_optimization_score": round(float(latest.get("best_score", 0.0) or 0.0), 4) if latest else 0.0,
    }


def _build_gap_failure_text(
    final_classification: Dict[str, Any],
    delegated_quality: Dict[str, Any],
) -> str:
    parts: List[str] = []
    failure_classes = final_classification.get("failure_classes") or []
    if failure_classes:
        parts.append("delegated failure classes: " + ", ".join(str(item) for item in failure_classes))
    salvage = final_classification.get("salvage")
    if isinstance(salvage, dict) and salvage.get("reasoning_excerpt"):
        parts.append(str(salvage.get("reasoning_excerpt") or ""))
    issues = delegated_quality.get("issues") or []
    if issues:
        parts.append("quality issues: " + "; ".join(str(item) for item in issues))
    suggestions = delegated_quality.get("suggestions") or []
    if suggestions:
        parts.append("quality suggestions: " + "; ".join(str(item) for item in suggestions))
    return " | ".join(part for part in parts if part).strip()


def _plan_capability_gap_remediation(gap: Any) -> Dict[str, Any]:
    strategies = _REMEDIATION_STRATEGY_OPTIMIZER.optimize_for_gap_type(gap.gap_type)
    strategy = strategies[0] if strategies else RemediationStrategy.MANUAL_INTERVENTION
    steps_by_strategy = {
        RemediationStrategy.INSTALL_PACKAGE: [
            "check declarative package source of truth",
            "stage package integration through Nix modules",
            "validate with repo gates before deploy",
        ],
        RemediationStrategy.IMPORT_KNOWLEDGE: [
            "collect authoritative docs for the missing topic",
            "stage bounded knowledge artifact or hint",
            "validate references and expected operators",
        ],
        RemediationStrategy.SYNTHESIZE_SKILL: [
            "derive a repeatable procedure from recent successful examples",
            "stage a bounded skill artifact",
            "validate the workflow against the failing task class",
        ],
        RemediationStrategy.EXTRACT_PATTERN: [
            "extract a reusable pattern from repeated successful work",
            "stage the pattern contract in repo surfaces",
            "validate against similar tasks",
        ],
        RemediationStrategy.CREATE_INTEGRATION: [
            "identify the missing coordinator or dashboard hook",
            "stage non-destructive integration wiring",
            "validate with targeted regression coverage",
        ],
        RemediationStrategy.MANUAL_INTERVENTION: [
            "collect failure evidence",
            "surface manual remediation recommendation",
            "defer destructive changes until reviewed",
        ],
    }
    playbook = _REMEDIATION_PLAYBOOK_LIBRARY.find_similar_playbook(gap)
    plan = RemediationPlan(
        plan_id=f"gap-plan-{gap.gap_id}",
        gap_id=gap.gap_id,
        strategy=strategy,
        steps=steps_by_strategy.get(strategy, steps_by_strategy[RemediationStrategy.MANUAL_INTERVENTION]),
        estimated_effort="low" if strategy != RemediationStrategy.MANUAL_INTERVENTION else "medium",
        requires_approval=strategy in {RemediationStrategy.INSTALL_PACKAGE, RemediationStrategy.MANUAL_INTERVENTION},
    )
    return {
        "plan_id": plan.plan_id,
        "strategy": plan.strategy.value,
        "steps": plan.steps,
        "estimated_effort": plan.estimated_effort,
        "requires_approval": plan.requires_approval,
        "playbook_id": playbook.playbook_id if playbook else "",
        "playbook_name": playbook.name if playbook else "",
    }


def _record_capability_gap_outcomes(
    gaps: List[Any],
    *,
    duration_seconds: float,
    response_status: int,
    fallback_applied: bool,
    finalization_applied: bool,
    delegated_quality: Dict[str, Any],
) -> None:
    remediation_actions: List[str] = []
    strategy = RemediationStrategy.MANUAL_INTERVENTION
    if fallback_applied:
        remediation_actions.append("delegated remote-free fallback applied")
        strategy = RemediationStrategy.CREATE_INTEGRATION
    if finalization_applied:
        remediation_actions.append("delegated finalization remediation applied")
        strategy = RemediationStrategy.EXTRACT_PATTERN
    if delegated_quality.get("refinement_applied"):
        remediation_actions.append("delegated quality refinement applied")
        strategy = RemediationStrategy.SYNTHESIZE_SKILL
    if delegated_quality.get("cached_fallback_used"):
        remediation_actions.append("delegated cached response fallback applied")
        strategy = RemediationStrategy.IMPORT_KNOWLEDGE
    if not remediation_actions:
        return
    success = response_status < 400
    for gap in gaps:
        plan = RemediationPlan(
            plan_id=f"gap-outcome-{gap.gap_id}-{int(time.time())}",
            gap_id=gap.gap_id,
            strategy=strategy,
            steps=remediation_actions,
            estimated_effort="low",
        )
        result = RemediationResult(
            plan_id=plan.plan_id,
            gap_id=gap.gap_id,
            status=RemediationStatus.SUCCESSFUL if success else RemediationStatus.FAILED,
            success=success,
            actions_taken=list(remediation_actions),
            artifacts_created=[],
            validation_passed=success,
        )
        outcome = _REMEDIATION_OUTCOME_TRACKER.record_outcome(gap, plan, result, duration_seconds)
        playbook = _REMEDIATION_PLAYBOOK_LIBRARY.find_similar_playbook(gap)
        if playbook:
            _REMEDIATION_PLAYBOOK_LIBRARY.update_playbook(playbook.playbook_id, outcome)
        elif success:
            _REMEDIATION_PLAYBOOK_LIBRARY.create_playbook(
                f"{gap.gap_type.value} recovery",
                gap,
                plan,
                outcome,
            )


async def _apply_real_time_learning(
    task: str,
    body: Any,
    *,
    profile_name: str,
    delegated_quality: Dict[str, Any],
    final_classification: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response_text = _extract_delegated_response_text(body)
    if not response_text:
        return {"available": False}
    quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
    if quality_score <= 0:
        quality_score = 0.85 if not final_classification.get("is_failure") else 0.35
    example = LearningExample(
        example_id=str(uuid4()),
        query=task,
        response=response_text,
        feedback=max(0.0, min(1.0, quality_score)),
        context={
            "profile": profile_name,
            "context": context or {},
            "failure_classes": final_classification.get("failure_classes", []),
        },
    )
    await _ONLINE_LEARNER.add_example(example)
    await _LIVE_PATTERN_MINER.mine_interaction(task, response_text, example.context)
    _HINT_QUALITY_ADJUSTER.record_hint_feedback(f"delegate:{profile_name}", example.feedback)
    implicit_feedback = _SUCCESS_FAILURE_DETECTOR.create_implicit_feedback(task, response_text, None)
    actions = await _IMMEDIATE_FEEDBACK_PROCESSOR.process_feedback(implicit_feedback)
    return {
        "available": True,
        "example_id": example.example_id,
        "feedback_score": round(example.feedback, 4),
        "update_count": len(_ONLINE_LEARNER.update_history),
        "pattern_count": len(_LIVE_PATTERN_MINER.patterns),
        "pending_action_count": len(_IMMEDIATE_FEEDBACK_PROCESSOR.pending_actions),
        "executed_action_count": sum(1 for action in actions if action.executed_at is not None),
    }


async def _apply_meta_learning(
    task: str,
    body: Any,
    *,
    profile_name: str,
    delegated_quality: Dict[str, Any],
) -> Dict[str, Any]:
    response_text = _extract_delegated_response_text(body)
    if not response_text:
        return {"available": False}

    domain_map = {
        "remote-gemini": TaskDomain.PLANNING,
        "remote-coding": TaskDomain.CODE_GENERATION,
        "remote-reasoning": TaskDomain.PLANNING,
        "remote-tool-calling": TaskDomain.CONFIGURATION,
        "remote-free": TaskDomain.EXPLANATION,
    }
    domain = domain_map.get(str(profile_name or "").strip(), TaskDomain.PLANNING)
    quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
    few_shot_examples = [
        {
            "input": task,
            "output": response_text[:1200],
            "quality": max(0.0, min(1.0, quality_score or 0.75)),
        }
    ]
    meta_task = Task(
        task_id=str(uuid4()),
        domain=domain,
        description=task,
        examples=list(few_shot_examples),
    )
    adaptation = await _RAPID_ADAPTOR.adapt_to_new_task(meta_task, few_shot_examples)
    return {
        "available": True,
        "task_id": meta_task.task_id,
        "domain": domain.value,
        "method": str(adaptation.get("method", "") or ""),
        "similar_task_count": len(adaptation.get("similar_tasks") or []),
        "embedding_norm": round(float(adaptation.get("embedding_norm", 0.0) or 0.0), 4),
        "cached_adaptations": len(_RAPID_ADAPTOR.adaptation_cache),
    }


def _optimize_delegated_messages(
    messages: List[Dict[str, Any]],
    profile_name: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Compress and prune delegated message envelopes before remote dispatch."""
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


def _agent_lessons_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-lessons.json"


def _agent_evaluations_registry_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "agent-evaluations.json"


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


def _default_agent_lessons_registry() -> Dict[str, Any]:
    return {
        "available": True,
        "path": str(_agent_lessons_registry_path()),
        "entries": [],
        "counts": {
            "total": 0,
            "pending_review": 0,
            "promoted": 0,
            "avoided": 0,
            "rejected": 0,
        },
        "active_lessons": [],
    }


def _default_agent_evaluations_registry() -> Dict[str, Any]:
    return {
        "available": True,
        "path": str(_agent_evaluations_registry_path()),
        "agents": {},
        "recent_events": [],
        "summary": {
            "agent_count": 0,
            "review_events": 0,
            "consensus_events": 0,
            "runtime_events": 0,
        },
    }


def _normalize_agent_role(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return normalized[:64] or "unknown"


def _default_agent_evaluation_row() -> Dict[str, Any]:
    return {
        "review_events": 0,
        "accepted_reviews": 0,
        "rejected_reviews": 0,
        "consensus_selected": 0,
        "runtime_events": 0,
        "successful_runtime_events": 0,
        "average_runtime_score": 0.0,
        "average_review_score": 0.0,
        "last_event_at": None,
    }


def _normalize_agent_lessons_registry(data: Any) -> Dict[str, Any]:
    registry = _default_agent_lessons_registry()
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            registry["entries"] = [item for item in entries if isinstance(item, dict)]
    counts = {
        "total": len(registry["entries"]),
        "pending_review": 0,
        "promoted": 0,
        "avoided": 0,
        "rejected": 0,
    }
    active_lessons: List[Dict[str, Any]] = []
    for item in registry["entries"]:
        state = str(item.get("state", "") or "").strip().lower()
        if state in counts:
            counts[state] += 1
        if state in {"promoted", "avoided"}:
            active_lessons.append(
                {
                    "lesson_key": item.get("lesson_key"),
                    "agent": item.get("agent"),
                    "hint_id": item.get("hint_id"),
                    "state": state,
                    "scope": item.get("scope"),
                    "materialization": item.get("materialization"),
                    "updated_at": item.get("updated_at"),
                }
            )
    active_lessons.sort(
        key=lambda item: (
            str(item.get("state") or ""),
            str(item.get("agent") or ""),
            str(item.get("hint_id") or ""),
        )
    )
    registry["counts"] = counts
    registry["active_lessons"] = active_lessons[:10]
    return registry


def _normalize_agent_evaluations_registry(data: Any) -> Dict[str, Any]:
    registry = _default_agent_evaluations_registry()
    if isinstance(data, dict):
        agents = data.get("agents")
        if isinstance(agents, dict):
            normalized_agents: Dict[str, Any] = {}
            for key, value in agents.items():
                agent_key = str(key or "").strip()
                if not agent_key or not isinstance(value, dict):
                    continue
                normalized_agents[agent_key] = {
                    "agent": agent_key,
                    "profiles": value.get("profiles", {}) if isinstance(value.get("profiles"), dict) else {},
                    "roles": value.get("roles", {}) if isinstance(value.get("roles"), dict) else {},
                    "totals": value.get("totals", {}) if isinstance(value.get("totals"), dict) else {},
                    "last_event_at": value.get("last_event_at"),
                }
            registry["agents"] = normalized_agents
        events = data.get("recent_events")
        if isinstance(events, list):
            registry["recent_events"] = [item for item in events if isinstance(item, dict)][-25:]

    review_events = 0
    consensus_events = 0
    runtime_events = 0
    for agent, payload in list(registry["agents"].items()):
        profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
        roles = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
        totals = {
            "review_events": 0,
            "accepted_reviews": 0,
            "rejected_reviews": 0,
            "consensus_selected": 0,
            "runtime_events": 0,
            "successful_runtime_events": 0,
            "average_runtime_score": 0.0,
            "average_review_score": 0.0,
        }
        weighted_scores = []
        total_score_events = 0
        weighted_runtime_scores = []
        total_runtime_score_events = 0
        normalized_profiles: Dict[str, Any] = {}
        normalized_roles: Dict[str, Any] = {}
        for profile_name, profile_payload in profiles.items():
            profile_key = str(profile_name or "").strip() or "unknown"
            if not isinstance(profile_payload, dict):
                continue
            review_count = int(profile_payload.get("review_events", 0) or 0)
            accepted = int(profile_payload.get("accepted_reviews", 0) or 0)
            rejected = int(profile_payload.get("rejected_reviews", 0) or 0)
            consensus_selected = int(profile_payload.get("consensus_selected", 0) or 0)
            runtime_count = int(profile_payload.get("runtime_events", 0) or 0)
            successful_runtime = int(profile_payload.get("successful_runtime_events", 0) or 0)
            avg_runtime_score = float(profile_payload.get("average_runtime_score", 0.0) or 0.0)
            avg_score = float(profile_payload.get("average_review_score", 0.0) or 0.0)
            normalized_profiles[profile_key] = {
                "review_events": review_count,
                "accepted_reviews": accepted,
                "rejected_reviews": rejected,
                "consensus_selected": consensus_selected,
                "runtime_events": runtime_count,
                "successful_runtime_events": successful_runtime,
                "average_runtime_score": round(avg_runtime_score, 4),
                "average_review_score": round(avg_score, 4),
                "last_event_at": profile_payload.get("last_event_at"),
            }
            totals["review_events"] += review_count
            totals["accepted_reviews"] += accepted
            totals["rejected_reviews"] += rejected
            totals["consensus_selected"] += consensus_selected
            totals["runtime_events"] += runtime_count
            totals["successful_runtime_events"] += successful_runtime
            if review_count > 0:
                weighted_scores.append(avg_score * review_count)
                total_score_events += review_count
            if runtime_count > 0:
                weighted_runtime_scores.append(avg_runtime_score * runtime_count)
                total_runtime_score_events += runtime_count
        for role_name, role_payload in roles.items():
            role_key = _normalize_agent_role(role_name)
            if not isinstance(role_payload, dict):
                continue
            normalized_roles[role_key] = {
                **_default_agent_evaluation_row(),
                "review_events": int(role_payload.get("review_events", 0) or 0),
                "accepted_reviews": int(role_payload.get("accepted_reviews", 0) or 0),
                "rejected_reviews": int(role_payload.get("rejected_reviews", 0) or 0),
                "consensus_selected": int(role_payload.get("consensus_selected", 0) or 0),
                "runtime_events": int(role_payload.get("runtime_events", 0) or 0),
                "successful_runtime_events": int(role_payload.get("successful_runtime_events", 0) or 0),
                "average_runtime_score": round(float(role_payload.get("average_runtime_score", 0.0) or 0.0), 4),
                "average_review_score": round(float(role_payload.get("average_review_score", 0.0) or 0.0), 4),
                "last_event_at": role_payload.get("last_event_at"),
            }
        totals["average_review_score"] = round(
            (sum(weighted_scores) / total_score_events) if total_score_events else 0.0,
            4,
        )
        totals["average_runtime_score"] = round(
            (sum(weighted_runtime_scores) / total_runtime_score_events) if total_runtime_score_events else 0.0,
            4,
        )
        payload["profiles"] = normalized_profiles
        payload["roles"] = normalized_roles
        payload["totals"] = totals
        review_events += totals["review_events"]
        consensus_events += totals["consensus_selected"]
        runtime_events += totals["runtime_events"]
    registry["summary"] = {
        "agent_count": len(registry["agents"]),
        "review_events": review_events,
        "consensus_events": consensus_events,
        "runtime_events": runtime_events,
    }
    return registry


def _load_agent_evaluations_registry_sync() -> Dict[str, Any]:
    path = _agent_evaluations_registry_path()
    if not path.exists():
        return _default_agent_evaluations_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_evaluations_registry()
    return _normalize_agent_evaluations_registry(data)


async def _load_agent_evaluations_registry() -> Dict[str, Any]:
    path = _agent_evaluations_registry_path()
    if not path.exists():
        return _default_agent_evaluations_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_evaluations_registry()
    return _normalize_agent_evaluations_registry(data)


async def _save_agent_evaluations_registry(data: Dict[str, Any]) -> None:
    path = _agent_evaluations_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_normalize_agent_evaluations_registry(data), indent=2) + "\n", encoding="utf-8")


def _record_agent_review_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    role: str,
    passed: bool,
    score: float,
    reviewer: str,
    review_type: str,
    task_class: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(profile or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    review_events = int(profile_row.get("review_events", 0) or 0) + 1
    running_total = float(profile_row.get("average_review_score", 0.0) or 0.0) * max(0, review_events - 1)
    profile_row["review_events"] = review_events
    profile_row["accepted_reviews"] = int(profile_row.get("accepted_reviews", 0) or 0) + (1 if passed else 0)
    profile_row["rejected_reviews"] = int(profile_row.get("rejected_reviews", 0) or 0) + (0 if passed else 1)
    profile_row["average_review_score"] = round((running_total + float(score)) / review_events, 4)
    profile_row["last_event_at"] = ts
    role_review_events = int(role_row.get("review_events", 0) or 0) + 1
    role_running_total = float(role_row.get("average_review_score", 0.0) or 0.0) * max(0, role_review_events - 1)
    role_row["review_events"] = role_review_events
    role_row["accepted_reviews"] = int(role_row.get("accepted_reviews", 0) or 0) + (1 if passed else 0)
    role_row["rejected_reviews"] = int(role_row.get("rejected_reviews", 0) or 0) + (0 if passed else 1)
    role_row["average_review_score"] = round((role_running_total + float(score)) / role_review_events, 4)
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "review",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "passed": bool(passed),
            "score": round(float(score), 4),
            "reviewer": reviewer,
            "review_type": review_type,
            "task_class": task_class,
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _record_agent_consensus_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    lane: str,
    role: str,
    selected_candidate_id: str,
    summary: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(lane or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    profile_row["consensus_selected"] = int(profile_row.get("consensus_selected", 0) or 0) + 1
    profile_row["last_event_at"] = ts
    role_row["consensus_selected"] = int(role_row.get("consensus_selected", 0) or 0) + 1
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "consensus",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "selected_candidate_id": selected_candidate_id,
            "summary": summary[:240],
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _runtime_event_score(event_type: str, risk_class: str, approved: bool) -> float:
    text = str(event_type or "").strip().lower()
    risk = str(risk_class or "").strip().lower()
    if text in {"failed", "failure", "error", "blocked", "rejected"} or risk == "blocked":
        return 0.0
    if text in {"completed", "complete", "success", "validation_pass", "phase_complete"}:
        return 1.0
    if risk == "review-required":
        return 0.8 if approved else 0.35
    return 0.7 if approved or risk == "safe" else 0.5


def _record_agent_runtime_event(
    registry: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    role: str,
    event_type: str,
    risk_class: str,
    approved: bool,
    token_delta: int,
    tool_call_delta: int,
    detail: str,
    ts: int,
) -> Dict[str, Any]:
    normalized = _normalize_agent_evaluations_registry(registry)
    agent_key = str(agent or "").strip() or "unknown"
    profile_key = str(profile or "").strip() or "unknown"
    role_key = _normalize_agent_role(role)
    agent_row = normalized["agents"].setdefault(
        agent_key,
        {"agent": agent_key, "profiles": {}, "roles": {}, "totals": {}, "last_event_at": None},
    )
    profile_row = agent_row["profiles"].setdefault(
        profile_key,
        _default_agent_evaluation_row(),
    )
    role_row = agent_row["roles"].setdefault(
        role_key,
        _default_agent_evaluation_row(),
    )
    runtime_events = int(profile_row.get("runtime_events", 0) or 0) + 1
    runtime_score = _runtime_event_score(event_type, risk_class, approved)
    running_total = float(profile_row.get("average_runtime_score", 0.0) or 0.0) * max(0, runtime_events - 1)
    profile_row["runtime_events"] = runtime_events
    profile_row["successful_runtime_events"] = int(profile_row.get("successful_runtime_events", 0) or 0) + (
        1 if runtime_score >= 0.8 else 0
    )
    profile_row["average_runtime_score"] = round((running_total + runtime_score) / runtime_events, 4)
    profile_row["last_event_at"] = ts
    role_runtime_events = int(role_row.get("runtime_events", 0) or 0) + 1
    role_running_total = float(role_row.get("average_runtime_score", 0.0) or 0.0) * max(0, role_runtime_events - 1)
    role_row["runtime_events"] = role_runtime_events
    role_row["successful_runtime_events"] = int(role_row.get("successful_runtime_events", 0) or 0) + (
        1 if runtime_score >= 0.8 else 0
    )
    role_row["average_runtime_score"] = round((role_running_total + runtime_score) / role_runtime_events, 4)
    role_row["last_event_at"] = ts
    agent_row["last_event_at"] = ts
    normalized["recent_events"].append(
        {
            "ts": ts,
            "event_type": "runtime",
            "agent": agent_key,
            "profile": profile_key,
            "role": role_key,
            "runtime_event_type": str(event_type or "").strip().lower(),
            "risk_class": str(risk_class or "").strip().lower(),
            "approved": bool(approved),
            "runtime_score": round(runtime_score, 4),
            "token_delta": max(0, int(token_delta or 0)),
            "tool_call_delta": max(0, int(tool_call_delta or 0)),
            "detail": str(detail or "").strip()[:240],
        }
    )
    normalized["recent_events"] = normalized["recent_events"][-25:]
    return _normalize_agent_evaluations_registry(normalized)


def _active_lesson_refs(registry: Dict[str, Any], limit: int = 2) -> List[Dict[str, Any]]:
    active_lessons = registry.get("active_lessons") if isinstance(registry, dict) else []
    if not isinstance(active_lessons, list):
        return []
    refs: List[Dict[str, Any]] = []
    for item in active_lessons[:max(0, limit)]:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "lesson_key": str(item.get("lesson_key", "") or "").strip(),
                "agent": str(item.get("agent", "") or "").strip(),
                "hint_id": str(item.get("hint_id", "") or "").strip(),
                "scope": str(item.get("scope", "") or "").strip(),
                "materialization": str(item.get("materialization", "") or "").strip(),
                "updated_at": str(item.get("updated_at", "") or "").strip(),
            }
        )
    return [item for item in refs if item.get("lesson_key")]


def _normalize_review_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text or "acceptance"


def _normalize_artifact_kind(value: Any, review_type: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text:
        return text
    if review_type == "patch_review":
        return "patch"
    if review_type == "plan_review":
        return "plan"
    if review_type == "artifact_review":
        return "artifact"
    return "response"


def _normalize_task_class(value: Any, session: Optional[Dict[str, Any]]) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text:
        return text
    if isinstance(session, dict):
        blueprint_id = str(session.get("blueprint_id", "") or "").strip().lower().replace("-", "_")
        if blueprint_id:
            return blueprint_id
    return "general"


def _isoformat_epoch(value: Any) -> str:
    try:
        ts = float(value or 0)
    except (TypeError, ValueError):
        ts = 0.0
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _a2a_text_parts(text: str) -> List[Dict[str, Any]]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    return [{"type": "text", "text": normalized}]


def _a2a_role(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_")
    if text in {"ROLE_USER", "USER"}:
        return "ROLE_USER"
    if text in {"ROLE_AGENT", "AGENT", "ASSISTANT"}:
        return "ROLE_AGENT"
    return "ROLE_AGENT"


def _a2a_message_payload(role: str, text: str, *, message_id: str = "", task_id: str = "") -> Dict[str, Any]:
    message: Dict[str, Any] = {
        "role": _a2a_role(role),
        "parts": _a2a_text_parts(text),
    }
    if message_id:
        message["messageId"] = message_id
    if task_id:
        message["taskId"] = task_id
    return message


def _extract_a2a_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    direct = str(message.get("text", "") or "").strip()
    if direct:
        return direct
    parts = message.get("parts")
    if not isinstance(parts, list):
        return ""
    texts: List[str] = []
    for item in parts:
        if not isinstance(item, dict):
            continue
        part_type = str(item.get("type", "")).strip().lower()
        text = str(item.get("text", "") or "").strip()
        if not text and not part_type and isinstance(item.get("data"), dict):
            text = json.dumps(item.get("data"), sort_keys=True)
        if not text and not part_type and item.get("url"):
            text = str(item.get("url", "")).strip()
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def _a2a_latest_detail(session: Dict[str, Any]) -> str:
    trajectory = session.get("trajectory", []) if isinstance(session, dict) else []
    if not isinstance(trajectory, list):
        return ""
    for event in reversed(trajectory):
        if not isinstance(event, dict):
            continue
        detail = str(event.get("detail", "") or "").strip()
        if detail:
            return detail
    return ""


def _a2a_task_state(session: Dict[str, Any]) -> str:
    status = str(session.get("status", "") or "").strip().lower()
    if status == "completed":
        return "TASK_STATE_COMPLETED"
    if status in {"error", "failed"}:
        return "TASK_STATE_FAILED"
    if status == "canceled":
        return "TASK_STATE_CANCELED"
    if status in {"pending", "queued"}:
        return "TASK_STATE_SUBMITTED"
    return "TASK_STATE_WORKING"


def _normalize_a2a_method(value: Any) -> str:
    text = str(value or "").strip()
    method_aliases = {
        "SendMessage": "message/send",
        "GetTask": "tasks/get",
        "ListTasks": "tasks/list",
        "CancelTask": "tasks/cancel",
        "SubscribeToTask": "tasks/resubscribe",
        "GetExtendedAgentCard": "agent/getAuthenticatedExtendedCard",
    }
    return method_aliases.get(text, text)


def _coerce_a2a_request_id(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float)):
        return value
    return None


def _normalize_a2a_status_filter(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_")
    if not text:
        return ""
    if text.startswith("TASK_STATE_"):
        return text
    mapping = {
        "SUBMITTED": "TASK_STATE_SUBMITTED",
        "WORKING": "TASK_STATE_WORKING",
        "INPUT_REQUIRED": "TASK_STATE_INPUT_REQUIRED",
        "COMPLETED": "TASK_STATE_COMPLETED",
        "CANCELED": "TASK_STATE_CANCELED",
        "FAILED": "TASK_STATE_FAILED",
    }
    return mapping.get(text, "")


def _session_to_a2a_artifacts(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    session_id = str(session.get("session_id", "") or "").strip()
    objective = str(session.get("objective", "") or "").strip()
    latest_detail = _a2a_latest_detail(session)
    artifacts: List[Dict[str, Any]] = []

    summary_lines = [line for line in [objective, latest_detail] if line]
    if summary_lines:
        artifacts.append(
            {
                "artifactId": f"{session_id}:summary",
                "name": "Workflow Summary",
                "description": "Current workflow objective and latest recorded detail.",
                "parts": _a2a_text_parts("\n\n".join(summary_lines)),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "summary",
                },
            }
        )

    gate = session.get("reviewer_gate", {})
    if isinstance(gate, dict):
        last_review = gate.get("last_review", {})
        if isinstance(last_review, dict) and last_review:
            review_text = (
                f"Reviewer gate status: {str(gate.get('status', 'pending_review') or 'pending_review').strip()}\n"
                f"Reviewer: {str(last_review.get('reviewer', 'unknown') or 'unknown').strip()}\n"
                f"Review type: {str(last_review.get('review_type', 'acceptance') or 'acceptance').strip()}\n"
                f"Artifact kind: {str(last_review.get('artifact_kind', 'response') or 'response').strip()}\n"
                f"Score: {last_review.get('score', 0)}"
            )
            artifacts.append(
                {
                    "artifactId": f"{session_id}:reviewer-gate",
                    "name": "Reviewer Gate",
                    "description": "Latest reviewer-gate decision for this workflow task.",
                    "parts": _a2a_text_parts(review_text),
                    "metadata": {
                        "workflow_session_id": session_id,
                        "artifact_kind": "reviewer_gate",
                        "review_status": str(gate.get("status", "") or "").strip(),
                    },
                }
            )

    consensus = session.get("consensus", {})
    if isinstance(consensus, dict) and consensus:
        candidate_count = len(consensus.get("candidates", []) or [])
        arbiter = consensus.get("arbiter") if isinstance(consensus.get("arbiter"), dict) else {}
        consensus_text = (
            f"Consensus status: {str(consensus.get('status', 'pending') or 'pending').strip()}\n"
            f"Consensus mode: {str(consensus.get('consensus_mode', 'reviewer-gate') or 'reviewer-gate').strip()}\n"
            f"Selection strategy: {str(consensus.get('selection_strategy', 'orchestrator-first') or 'orchestrator-first').strip()}\n"
            f"Selected candidate: {str(consensus.get('selected_candidate_id', '') or 'none').strip()}\n"
            f"Selected lane: {str(consensus.get('selected_lane', '') or 'unknown').strip()}\n"
            f"Candidate count: {candidate_count}\n"
            f"Arbiter status: {str(arbiter.get('status', 'not-required') or 'not-required').strip()}"
        )
        artifacts.append(
            {
                "artifactId": f"{session_id}:consensus",
                "name": "Consensus Snapshot",
                "description": "Current candidate evaluation and consensus state for this workflow task.",
                "parts": _a2a_text_parts(consensus_text),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "consensus",
                    "consensus_status": str(consensus.get("status", "") or "").strip(),
                    "selected_candidate_id": str(consensus.get("selected_candidate_id", "") or "").strip(),
                },
            }
        )
        last_arbiter = arbiter.get("last_decision") if isinstance(arbiter.get("last_decision"), dict) else {}
        if last_arbiter:
            arbiter_text = (
                f"Arbiter: {str(last_arbiter.get('arbiter', 'unknown') or 'unknown').strip()}\n"
                f"Verdict: {str(last_arbiter.get('verdict', 'unknown') or 'unknown').strip()}\n"
                f"Selected candidate: {str(last_arbiter.get('selected_candidate_id', 'none') or 'none').strip()}\n"
                f"Selected lane: {str(last_arbiter.get('selected_lane', 'unknown') or 'unknown').strip()}\n"
                f"Rationale: {str(last_arbiter.get('rationale', '') or '').strip()}"
            )
            artifacts.append(
                {
                    "artifactId": f"{session_id}:arbiter",
                    "name": "Arbiter Decision",
                    "description": "Latest arbiter decision for this workflow task.",
                    "parts": _a2a_text_parts(arbiter_text),
                    "metadata": {
                        "workflow_session_id": session_id,
                        "artifact_kind": "arbiter",
                        "arbiter_status": str(arbiter.get("status", "") or "").strip(),
                        "selected_candidate_id": str(last_arbiter.get("selected_candidate_id", "") or "").strip(),
                    },
                }
            )

    team = session.get("team", {})
    if isinstance(team, dict) and (team.get("members") or []):
        team_lines = [
            f"Formation mode: {str(team.get('formation_mode', 'dynamic-role-assignment') or 'dynamic-role-assignment').strip()}",
            f"Selection strategy: {str(team.get('selection_strategy', 'orchestrator-first') or 'orchestrator-first').strip()}",
            f"Active slots: {', '.join(str(slot or '').strip() for slot in (team.get('active_slots') or []) if str(slot or '').strip()) or 'none'}",
        ]
        for member in team.get("members") or []:
            if not isinstance(member, dict):
                continue
            team_lines.append(
                f"{str(member.get('slot', 'member') or 'member').strip()}: "
                f"{str(member.get('agent', 'unknown') or 'unknown').strip()} "
                f"[{str(member.get('lane', 'unknown') or 'unknown').strip()}]"
            )
        artifacts.append(
            {
                "artifactId": f"{session_id}:team",
                "name": "Orchestration Team",
                "description": "Current dynamically formed role assignment for this workflow task.",
                "parts": _a2a_text_parts("\n".join(team_lines)),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "team",
                    "formation_mode": str(team.get("formation_mode", "") or "").strip(),
                },
            }
        )

    return artifacts


def _session_history_to_a2a_messages(session: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    session_id = str(session.get("session_id", "") or "").strip()
    trajectory = session.get("trajectory", [])
    if not isinstance(trajectory, list):
        return []
    messages: List[Dict[str, Any]] = []
    start = max(0, len(trajectory) - max(1, limit))
    for idx, event in enumerate(trajectory[start:], start=start):
        if not isinstance(event, dict):
            continue
        detail = str(event.get("detail", "") or "").strip()
        if not detail:
            continue
        messages.append(
            _a2a_message_payload(
                "agent",
                detail,
                message_id=f"{session_id}:history:{idx}",
                task_id=session_id,
            )
        )
    return messages


def _history_subset(session: Dict[str, Any], history_length: Optional[int]) -> List[Dict[str, Any]]:
    trajectory = session.get("trajectory", []) if isinstance(session, dict) else []
    if not isinstance(trajectory, list):
        return []
    if history_length is None:
        return trajectory
    return trajectory[: max(0, min(len(trajectory), int(history_length)))]


def _session_to_a2a_status_event(
    session: Dict[str, Any],
    base_url: str,
    *,
    detail: str = "",
    timestamp: Any = None,
    final: Optional[bool] = None,
) -> Dict[str, Any]:
    task = _session_to_a2a_task(session, base_url)
    session_id = str(task.get("id", "") or "").strip()
    state = str(task.get("status", {}).get("state", "working") or "working").strip() or "working"
    status_timestamp = _isoformat_epoch(timestamp if timestamp is not None else session.get("updated_at") or session.get("created_at"))
    message_text = str(detail or _a2a_latest_detail(session) or f"Task is {state}.").strip()
    if final is None:
        final = state in {"completed", "failed", "canceled"}
    return {
        "kind": "status-update",
        "taskId": session_id,
        "contextId": session_id,
        "status": {
            "state": state,
            "timestamp": status_timestamp,
            "message": _a2a_message_payload(
                "ROLE_AGENT",
                message_text,
                message_id=f"{session_id}:status:{state}",
                task_id=session_id,
            ),
        },
        "final": bool(final),
        "metadata": task.get("metadata", {}),
    }


def _artifact_to_a2a_update(task: Dict[str, Any], artifact: Dict[str, Any], *, last_chunk: bool = True) -> Dict[str, Any]:
    session_id = str(task.get("id", "") or "").strip()
    return {
        "kind": "artifact-update",
        "taskId": session_id,
        "contextId": session_id,
        "artifact": artifact,
        "lastChunk": bool(last_chunk),
    }


def _session_to_a2a_task(
    session: Dict[str, Any],
    base_url: str,
    *,
    history_length: Optional[int] = None,
    include_artifacts: bool = True,
) -> Dict[str, Any]:
    session_id = str(session.get("session_id", "") or "").strip()
    objective = str(session.get("objective", "") or "").strip()
    state = _a2a_task_state(session)
    updated_at = session.get("updated_at") or session.get("created_at")
    latest_detail = _a2a_latest_detail(session)
    artifacts = _session_to_a2a_artifacts(session) if include_artifacts else []
    history_items = _history_subset(session, history_length)
    task: Dict[str, Any] = {
        "id": session_id,
        "kind": "task",
        "contextId": str(session.get("context_id", "") or session_id).strip() or session_id,
        "status": {
            "state": state,
            "timestamp": _isoformat_epoch(updated_at),
            "message": _a2a_message_payload(
                "agent",
                latest_detail or objective or f"Task is {state}.",
                message_id=f"{session_id}:status",
                task_id=session_id,
            ),
        },
        "metadata": {
            "objective": objective,
            "safety_mode": str(session.get("safety_mode", "") or "").strip(),
            "phase_count": len(session.get("phase_state", []) or []),
            "current_phase_index": int(session.get("current_phase_index", 0) or 0),
            "reviewer_gate": session.get("reviewer_gate", {}),
            "a2a_stream_url": f"{base_url.rstrip('/')}/a2a/tasks/{session_id}/events",
            "workflow_run_url": f"{base_url.rstrip('/')}/workflow/run/{session_id}",
        },
        "historyLength": len(history_items),
    }
    if objective:
        task["message"] = _a2a_message_payload(
            "ROLE_AGENT",
            objective,
            message_id=f"{session_id}:summary",
            task_id=session_id,
        )
    history = _session_history_to_a2a_messages({"session_id": session_id, "trajectory": history_items}, limit=max(1, len(history_items)))
    if history_length is not None:
        task["history"] = history
    elif history:
        task["history"] = history
    if artifacts:
        task["artifacts"] = artifacts
    return task


def _build_a2a_agent_card(base_url: str) -> Dict[str, Any]:
    parsed = urlsplit(base_url.rstrip("/"))
    hostname = parsed.hostname or ""
    if hostname in {"127.0.0.1", "::1"}:
        host = "localhost"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        origin = urlunsplit((parsed.scheme or "http", host, "", "", "")).rstrip("/")
    else:
        origin = base_url.rstrip("/")
    return {
        "protocolVersion": "0.3.0",
        "name": "NixOS Dev Quick Deploy Hybrid Coordinator",
        "description": (
            "A2A compatibility surface for the hybrid coordinator. "
            "It exposes guarded workflow planning and task execution over JSON-RPC."
        ),
        "endpoint": f"{origin}/",
        "preferredTransport": "JSONRPC",
        "version": SERVICE_VERSION,
        "provider": {
            "organization": "NixOS-Dev-Quick-Deploy",
        },
        "documentationUrl": f"{origin}/.well-known/agent-card.json",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "supportedInterfaces": [
            {
                "transport": "JSONRPC",
                "url": f"{origin}/",
                "features": {
                    "streaming": True,
                    "pushNotifications": False,
                },
            }
        ],
        "skills": [
            {
                "id": "workflow-orchestration",
                "name": "Workflow Orchestration",
                "description": "Starts guarded workflow runs with intent contracts and replayable trajectory history.",
                "tags": ["workflow", "orchestration", "guardrails"],
                "examples": ["Resume the previous deployment integration slice and report evidence."],
            },
            {
                "id": "runtime-review-gate",
                "name": "Reviewer Gate",
                "description": "Tracks reviewer-gate state and safety-mode transitions for coding-agent tasks.",
                "tags": ["review", "safety", "runtime"],
                "examples": ["Create a bounded fix plan and do not exit until the review gate is satisfied."],
            },
        ],
        "endpoints": {
            "rpc": f"{origin}/",
            "taskEvents": f"{origin}/a2a/tasks/{{taskId}}/events",
        },
    }


def _jsonrpc_success(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if isinstance(data, dict) and data:
        payload["error"]["data"] = data
    return payload


async def _load_agent_lessons_registry() -> Dict[str, Any]:
    path = _agent_lessons_registry_path()
    if not path.exists():
        return _default_agent_lessons_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_agent_lessons_registry()
    return _normalize_agent_lessons_registry(data)


async def _save_agent_lessons_registry(data: Dict[str, Any]) -> None:
    path = _agent_lessons_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_normalize_agent_lessons_registry(data), indent=2) + "\n", encoding="utf-8")


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


def _normalize_orchestration_lane_list(value: Any) -> List[str]:
    values = _normalize_string_list(value)
    out: List[str] = []
    seen = set()
    for item in values:
        lane = str(item or "").strip().lower()
        if lane and lane not in seen:
            seen.add(lane)
            out.append(lane)
    return out


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
            "prefer harness retrieval, memory recall, and periodic compaction over resending long prompt history",
        ],
        "no_early_exit_without": [
            "all requested checks completed",
            "known blockers documented with remediation",
            "context strategy or blocker documented when the task is long-running",
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


def _is_continuation_query(query: str) -> bool:
    query_lower = str(query or "").lower()
    direct_tokens = (
        "resume",
        "continue",
        "follow-up",
        "follow up",
        "prior context",
        "pick up where",
        "last agent",
        "ongoing",
    )
    if any(token in query_lower for token in direct_tokens):
        return True
    has_previous_ref = any(token in query_lower for token in ("previous", "prior", "last"))
    has_resume_target = any(
        token in query_lower
        for token in ("context", "patch", "deploy", "troubleshooting", "debug", "loop", "work")
    )
    return has_previous_ref and has_resume_target


def _build_workflow_plan(
    query: str,
    tools: Optional[List[Dict[str, str]]] = None,
    tool_security: Optional[Dict[str, Any]] = None,
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    if tools is None or tool_security is None:
        tools, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query))
    prompt_coaching: Dict[str, Any] = {}
    try:
        from hints_engine import HintsEngine  # type: ignore[import]
        prompt_coaching = HintsEngine().prompt_coaching_as_dict(query, agent_type="codex")
    except Exception:
        prompt_coaching = {}
    tool_catalog = {str(t.get("name", "")).strip(): dict(t) for t in tools if str(t.get("name", "")).strip()}
    continuation_query = _is_continuation_query(query)
    reasoning_pattern = _select_reasoning_pattern(query, prompt_coaching, continuation_query)
    aq_report_summary = _load_aq_report_status_summary()

    def pick_tool_names(names: set[str]) -> List[str]:
        return [name for name in tool_catalog if name in names]

    return {
        "objective": query,
        "workflow_version": "1.1",
        "phases": [
            {
                "id": "discover",
                "goal": "Collect high-signal context first.",
                "tools": pick_tool_names(
                    {"hints", "discovery", "route_search", "tree_search"}
                    | ({"memory_recall"} if continuation_query else set())
                ),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("discover", "react"),
                "exit_criteria": "Top risks identified.",
            },
            {
                "id": "plan",
                "goal": "Turn findings into verified steps.",
                "tools": pick_tool_names(
                    {"hints", "discovery"} | ({"memory_recall"} if continuation_query else set())
                ),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("plan", "react"),
                "exit_criteria": "Ordered task list exists.",
            },
            {
                "id": "execute",
                "goal": "Apply small reversible changes.",
                "tools": pick_tool_names(
                    {
                        "route_search",
                        "memory_recall",
                        "web_research_fetch",
                        "browser_research_fetch",
                        "curated_research_fetch",
                        "feedback",
                    }
                ),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("execute", "react"),
                "exit_criteria": "Primary objective implemented.",
            },
            {
                "id": "validate",
                "goal": "Run checks and confirm behavior.",
                "tools": pick_tool_names({"qa_check", "harness_eval", "health", "learning_stats"}),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("validate", "reflexion"),
                "exit_criteria": "Checks pass or failures are documented.",
            },
            {
                "id": "handoff",
                "goal": "Capture outcomes, risk, and rollback.",
                "tools": pick_tool_names({"feedback", "learning_stats"}),
                "reasoning_pattern": reasoning_pattern["phase_recommendations"].get("handoff", "reflexion"),
                "exit_criteria": "Handoff summary ready.",
            },
        ],
        "token_policy": {
            "approach": "progressive-disclosure",
            "rules": [
                {"id": "compact-first", "summary": "Start concise; load deeper context only when needed."},
                {"id": "retrieve-before-restating", "summary": "Prefer retrieval over prompt stuffing; escalate remote only when justified."},
                {"id": "cheap-probe-then-cache", "summary": "Use low-cost probing first and keep reusable prefixes compact for caching."},
            ],
        },
        "metadata": {
            "query_length": len(query),
            "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
            "prompt_coaching": _compact_prompt_coaching_metadata(prompt_coaching),
            "tool_catalog": (
                tool_catalog
                if include_debug_metadata
                else _compact_workflow_tool_catalog(tool_catalog)
            ),
            "tool_security": (
                tool_security
                if include_debug_metadata
                else _compact_tool_security(tool_security or {})
            ),
            "created_epoch_s": int(time.time()),
            "memory_recall_priority": continuation_query,
            "reasoning_pattern": reasoning_pattern,
            "optimization_watch": aq_report_summary.get("optimization_watch", {"available": False}),
        },
    }


def _select_reasoning_pattern(
    query: str,
    prompt_coaching: Dict[str, Any],
    continuation_query: bool,
) -> Dict[str, Any]:
    """Select a live agentic reasoning pattern for workflow planning/runtime."""
    normalized = str(query or "").strip().lower()
    coaching_summary = _compact_prompt_coaching_metadata(prompt_coaching)
    missing_count = int(coaching_summary.get("missing_count", 0) or 0)
    complexity_tokens = {
        "architecture",
        "design",
        "tradeoff",
        "compare",
        "strategy",
        "complex",
        "multi-step",
        "reasoning",
    }
    reflexion_tokens = {
        "retry",
        "regression",
        "failure",
        "postmortem",
        "improve",
        "root cause",
        "stability",
        "freeze",
    }
    react_tokens = {
        "debug",
        "investigate",
        "diagnose",
        "fix",
        "deploy",
        "integration",
        "service",
        "workflow",
    }
    self_consistency_tokens = {
        "consistent",
        "consistency",
        "independent answers",
        "majority vote",
        "cross-check",
    }
    plan_and_solve_tokens = {
        "step-by-step plan",
        "break down",
        "implementation plan",
        "plan this",
        "sequence of steps",
    }
    verification_tokens = {
        "verify",
        "verification",
        "validate",
        "fact-check",
        "prove",
        "confirm",
    }
    debate_tokens = {
        "debate",
        "argue both sides",
        "counterargument",
        "pros and cons",
        "tradeoffs",
    }

    complexity_score = float(min(1.0, (len(normalized.split()) / 40.0) + (missing_count / 10.0)))
    selection_basis: List[str] = []
    if any(token in normalized for token in debate_tokens):
        primary = "debate"
        selection_basis.append("multi-perspective debate cues")
    elif any(token in normalized for token in verification_tokens):
        primary = "chain_of_verification"
        selection_basis.append("verification-first cues")
    elif any(token in normalized for token in self_consistency_tokens):
        primary = "self_consistency"
        selection_basis.append("consensus-checking cues")
    elif any(token in normalized for token in plan_and_solve_tokens):
        primary = "plan_and_solve"
        selection_basis.append("explicit planning cues")
    elif any(token in normalized for token in complexity_tokens):
        primary = "tree_of_thoughts"
        selection_basis.append("complex deliberation cues")
    elif continuation_query or any(token in normalized for token in reflexion_tokens):
        primary = "reflexion"
        selection_basis.append("iterative recovery cues")
    elif any(token in normalized for token in react_tokens):
        primary = "react"
        selection_basis.append("tool-using execution cues")
    elif complexity_score >= 0.65:
        primary = "tree_of_thoughts"
        selection_basis.append("elevated prompt complexity")
    else:
        primary = "react"
        selection_basis.append("default action-first workflow")

    phase_recommendations = {
        "discover": "react",
        "plan": "tree_of_thoughts" if primary in {"tree_of_thoughts", "reflexion"} else "react",
        "execute": "react",
        "validate": "reflexion",
        "handoff": "reflexion",
    }
    if primary == "tree_of_thoughts":
        phase_recommendations["plan"] = "tree_of_thoughts"
    elif primary == "plan_and_solve":
        phase_recommendations["plan"] = "plan_and_solve"
        phase_recommendations["execute"] = "plan_and_solve"
    elif primary == "self_consistency":
        phase_recommendations["validate"] = "self_consistency"
    elif primary == "chain_of_verification":
        phase_recommendations["validate"] = "chain_of_verification"
    elif primary == "debate":
        phase_recommendations["discover"] = "debate"
        phase_recommendations["plan"] = "debate"
    elif primary == "reflexion":
        phase_recommendations["validate"] = "reflexion"
        phase_recommendations["handoff"] = "reflexion"

    alternatives = [
        name
        for name in (
            "react",
            "tree_of_thoughts",
            "reflexion",
            "self_consistency",
            "plan_and_solve",
            "chain_of_verification",
            "debate",
        )
        if name != primary
    ]
    return {
        "selected_pattern": primary,
        "selection_basis": selection_basis,
        "complexity_score": round(complexity_score, 3),
        "boost_multiplier": round(float(_get_pattern_boost(primary)), 3),
        "phase_recommendations": phase_recommendations,
        "alternatives": alternatives,
        "constitutional_guardrails": True,
    }


def _compact_prompt_coaching_metadata(prompt_coaching: Dict[str, Any]) -> Dict[str, Any]:
    """Avoid repeating the full coaching payload inside metadata."""
    if not isinstance(prompt_coaching, dict) or not prompt_coaching:
        return {}
    missing_fields = [
        str(item).strip() for item in (prompt_coaching.get("missing_fields", []) or []) if str(item).strip()
    ]
    token_discipline = prompt_coaching.get("token_discipline", {})
    if not isinstance(token_discipline, dict):
        token_discipline = {}
    return {
        "score": float(prompt_coaching.get("score", 0.0) or 0.0),
        "recommended_agent": str(prompt_coaching.get("recommended_agent", "codex") or "codex"),
        "missing_fields": missing_fields[:3],
        "missing_count": len(missing_fields),
        "token_plan": {
            "spend_tier": str(token_discipline.get("spend_tier", "lean") or "lean"),
            "recommended_input_budget": int(token_discipline.get("recommended_input_budget", 0) or 0),
        },
    }


def _query_prompt_coaching_response(
    prompt_coaching: Dict[str, Any],
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    """Return compact prompt coaching by default and preserve deep detail only on opt-in."""
    compact = _compact_prompt_coaching_metadata(prompt_coaching)
    if not include_debug_metadata:
        suggested_prompt = str(prompt_coaching.get("suggested_prompt", "") or "").strip()
        if suggested_prompt:
            compact["suggested_prompt"] = suggested_prompt
        return compact
    enriched = dict(prompt_coaching)
    enriched["summary"] = compact
    return enriched


def _compact_tooling_layer_response(
    tooling_layer: Dict[str, Any],
    include_debug_metadata: bool = False,
) -> Dict[str, Any]:
    """Keep normal query tooling metadata compact and operational."""
    planned_tools = list(tooling_layer.get("planned_tools", []) or [])
    executed_tools = list(tooling_layer.get("executed", []) or [])
    hints = list(tooling_layer.get("hints", []) or [])
    tool_security = tooling_layer.get("tool_security", {})
    if not isinstance(tool_security, dict):
        tool_security = {}
    compact = {
        "enabled": bool(tooling_layer.get("enabled", False)),
        "planned_tools": planned_tools[:3],
        "planned_count": len(planned_tools),
        "planned_more": max(0, len(planned_tools) - 3),
        "executed": executed_tools[:3],
        "executed_count": len(executed_tools),
        "executed_more": max(0, len(executed_tools) - 3),
        "hints_count": len(hints),
        "tool_security": {
            "blocked_count": len(tool_security.get("blocked", []) or []),
            "cache_hits": int(tool_security.get("cache_hits", 0) or 0),
            "first_seen": int(tool_security.get("first_seen", 0) or 0),
        },
    }
    if include_debug_metadata:
        enriched = dict(tooling_layer)
        enriched["summary"] = compact
        return enriched
    return compact


def _compact_tool_security(tool_security: Dict[str, Any]) -> Dict[str, Any]:
    """Keep tool-security state compact on default metadata surfaces."""
    if not isinstance(tool_security, dict):
        tool_security = {}
    return {
        "enabled": bool(tool_security.get("enabled", False)),
        "approved_count": len(tool_security.get("approved", []) or []),
        "blocked_count": len(tool_security.get("blocked", []) or []),
        "cache_hits": int(tool_security.get("cache_hits", 0) or 0),
        "first_seen": int(tool_security.get("first_seen", 0) or 0),
    }


def _compact_workflow_tool_catalog(tool_catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Keep workflow-plan tool metadata compact by default."""
    compact: Dict[str, Any] = {}
    if not isinstance(tool_catalog, dict):
        return compact
    for name, payload in tool_catalog.items():
        if not isinstance(payload, dict):
            continue
        tool_name = str(payload.get("name", "") or name).strip()
        if not tool_name:
            continue
        compact[tool_name] = {
            "endpoint": str(payload.get("endpoint", "") or "").strip(),
        }
    return compact


def _phase_tool_names(phase: Dict[str, Any]) -> List[str]:
    """Accept compact plan tool names and legacy tool dicts."""
    names: List[str] = []
    for tool in phase.get("tools", []):
        if isinstance(tool, str):
            name = tool.strip()
        elif isinstance(tool, dict):
            name = str(tool.get("name", "")).strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


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
    token_limit_raw = data.get("token_limit", env_token_limit)
    tool_call_limit_raw = data.get("tool_call_limit", env_tool_call_limit)
    return {
        "token_limit": int(env_token_limit if token_limit_raw in (None, "") else token_limit_raw),
        "tool_call_limit": int(env_tool_call_limit if tool_call_limit_raw in (None, "") else tool_call_limit_raw),
    }


def _default_usage() -> Dict[str, int]:
    return {"tokens_used": 0, "tool_calls_used": 0}


def _evaluation_history_bias(registry: Dict[str, Any], agent: str, profile: str, role: str) -> Dict[str, float]:
    agents = registry.get("agents") if isinstance(registry, dict) else {}
    if not isinstance(agents, dict):
        return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
    agent_row = agents.get(str(agent or "").strip())
    if not isinstance(agent_row, dict):
        return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
    profiles = agent_row.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    profile_row = profiles.get(str(profile or "").strip())
    if not isinstance(profile_row, dict):
        profile_row = {}
    roles = agent_row.get("roles")
    if not isinstance(roles, dict):
        roles = {}
    role_row = roles.get(_normalize_agent_role(role))
    if not isinstance(role_row, dict):
        role_row = {}

    def _bounded_score(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0

    def _bounded_count(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _weighted_component(avg_score: float, count: int, divisor: float) -> float:
        weight = min(1.0, count / divisor) if divisor > 0 else 0.0
        return avg_score * weight

    def _recent_agent_event_bias() -> Dict[str, float]:
        events = registry.get("recent_events") if isinstance(registry, dict) else []
        if not isinstance(events, list):
            return {"review_score": 0.0, "selection_score": 0.0, "runtime_score": 0.0}
        agent_key = str(agent or "").strip()
        profile_key = str(profile or "").strip()
        role_key = _normalize_agent_role(role)
        review_scores: List[float] = []
        runtime_scores: List[float] = []
        selection_events = 0
        scoped_events = 0
        agent_events = 0
        for item in events[-18:]:
            if not isinstance(item, dict):
                continue
            if str(item.get("agent", "") or "").strip() != agent_key:
                continue
            agent_events += 1
            profile_match = str(item.get("profile", "") or "").strip() == profile_key
            role_match = _normalize_agent_role(item.get("role")) == role_key
            if not profile_match and not role_match:
                continue
            scoped_events += 1
            event_type = str(item.get("event_type", "") or "").strip().lower()
            if event_type == "review":
                review_scores.append(_bounded_score(item.get("score", 0.0)))
            elif event_type == "runtime":
                runtime_scores.append(_bounded_score(item.get("runtime_score", 0.0)))
            elif event_type == "consensus":
                selection_events += 1
        recency_weight = min(1.0, scoped_events / 5.0) if scoped_events > 0 else min(0.5, agent_events / 10.0)
        review_score = (sum(review_scores) / len(review_scores)) if review_scores else 0.0
        runtime_score = (sum(runtime_scores) / len(runtime_scores)) if runtime_scores else 0.0
        selection_score = min(1.0, selection_events / 3.0)
        return {
            "review_score": round(review_score * recency_weight, 4),
            "selection_score": round(selection_score * recency_weight, 4),
            "runtime_score": round(runtime_score * recency_weight, 4),
        }

    review_events = _bounded_count(profile_row.get("review_events", 0))
    avg_review_score = _bounded_score(profile_row.get("average_review_score", 0.0))
    consensus_selected = _bounded_count(profile_row.get("consensus_selected", 0))
    runtime_events = _bounded_count(profile_row.get("runtime_events", 0))
    avg_runtime_score = _bounded_score(profile_row.get("average_runtime_score", 0.0))
    role_review_events = _bounded_count(role_row.get("review_events", 0))
    role_avg_review_score = _bounded_score(role_row.get("average_review_score", 0.0))
    role_consensus_selected = _bounded_count(role_row.get("consensus_selected", 0))
    role_runtime_events = _bounded_count(role_row.get("runtime_events", 0))
    role_avg_runtime_score = _bounded_score(role_row.get("average_runtime_score", 0.0))

    totals = agent_row.get("totals") if isinstance(agent_row.get("totals"), dict) else {}
    total_review_events = _bounded_count(totals.get("review_events", 0))
    total_runtime_events = _bounded_count(totals.get("runtime_events", 0))
    total_consensus_selected = _bounded_count(totals.get("consensus_selected", 0))
    total_avg_review_score = _bounded_score(totals.get("average_review_score", 0.0))
    total_avg_runtime_score = _bounded_score(totals.get("average_runtime_score", 0.0))
    recent_bias = _recent_agent_event_bias()

    review_component = (
        (0.40 * _weighted_component(avg_review_score, review_events, 5.0))
        + (0.20 * _weighted_component(role_avg_review_score, role_review_events, 8.0))
        + (0.20 * _weighted_component(total_avg_review_score, total_review_events, 12.0))
        + (0.20 * recent_bias["review_score"])
    )
    selection_component = (
        (0.45 * min(1.0, consensus_selected / 5.0))
        + (0.20 * min(1.0, role_consensus_selected / 6.0))
        + (0.15 * min(1.0, total_consensus_selected / 8.0))
        + (0.20 * recent_bias["selection_score"])
    )
    runtime_component = (
        (0.40 * _weighted_component(avg_runtime_score, runtime_events, 6.0))
        + (0.25 * _weighted_component(role_avg_runtime_score, role_runtime_events, 8.0))
        + (0.15 * _weighted_component(total_avg_runtime_score, total_runtime_events, 12.0))
        + (0.20 * recent_bias["runtime_score"])
    )
    return {
        "review_score": round(review_component, 4),
        "selection_score": round(selection_component, 4),
        "runtime_score": round(runtime_component, 4),
    }


def _agent_for_orchestration_lane(lane: str, requested_by: str, role: str) -> str:
    normalized_lane = str(lane or "").strip().lower()
    normalized_role = _normalize_agent_role(role)
    if normalized_role == "reviewer":
        return "codex"
    if normalized_lane == "research":
        return "gemini"
    if normalized_lane == "reasoning" or normalized_lane in _ORCHESTRATION_ESCALATION_LANES:
        return "remote"
    return requested_by


def _profile_for_orchestration_lane(lane: str, role: str, objective: str) -> str:
    normalized_lane = str(lane or "").strip().lower()
    normalized_role = _normalize_agent_role(role)
    local_handoff = _orchestration_prefers_local_handoff(objective)
    if normalized_lane == "research":
        return "remote-gemini"
    if normalized_lane == "reasoning" or normalized_lane in _ORCHESTRATION_ESCALATION_LANES:
        return "remote-reasoning"
    if normalized_lane == "diagnostics":
        return "local-tool-calling" if local_handoff or normalized_role == "collaborator" else "default"
    if normalized_lane in {"implementation", "hardening", "operations", "self-improvement"}:
        if local_handoff and normalized_role == "collaborator":
            return "local-tool-calling"
        return "remote-coding" if normalized_role == "orchestrator" else "default"
    return "default"


def _seed_agent_evaluation(policy: Dict[str, Any], orchestration: Dict[str, Any]) -> Dict[str, Any]:
    strategy = str(policy.get("selection_strategy", "orchestrator-first") or "orchestrator-first").strip()
    consensus_mode = str(policy.get("consensus_mode", "reviewer-gate") or "reviewer-gate").strip()
    requested_by = str(orchestration.get("requested_by", "human") or "human").strip() or "human"
    requester_role = str(orchestration.get("requester_role", "orchestrator") or "orchestrator").strip() or "orchestrator"
    objective = str(orchestration.get("objective") or orchestration.get("query") or "").strip()
    evaluation_registry = _load_agent_evaluations_registry_sync()

    candidates: List[Dict[str, Any]] = []

    def _add_candidate(candidate_id: str, lane: str, agent: str, role: str, components: Dict[str, float], basis: str) -> None:
        profile = _profile_for_orchestration_lane(lane, role, objective)
        history = _evaluation_history_bias(evaluation_registry, agent, profile, role)
        components = dict(components)
        components["historical_review"] = history["review_score"]
        components["historical_selection"] = history["selection_score"]
        components["historical_runtime_quality"] = history["runtime_score"]
        score = round(sum(float(value) for value in components.values()), 4)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "lane": lane,
                "agent": agent,
                "role": role,
                "profile": profile,
                "runtime_id": _ai_coordinator_default_runtime_id_for_profile(profile),
                "basis": basis,
                "score": score,
                "score_components": {key: round(float(value), 4) for key, value in components.items()},
                "history_bias": history,
            }
        )

    primary_lane = str(policy.get("primary_lane", "implementation") or "implementation").strip()
    reviewer_lane = str(policy.get("reviewer_lane", "codex-review") or "codex-review").strip()
    escalation_lane = str(policy.get("escalation_lane", "remote-reasoning") or "remote-reasoning").strip()
    collaborator_lanes = _normalize_orchestration_lane_list(policy.get("collaborator_lanes", []))

    base_requester_score = 0.4 if requester_role == "orchestrator" else 0.25
    _add_candidate(
        "primary",
        primary_lane,
        _agent_for_orchestration_lane(primary_lane, requested_by, requester_role),
        requester_role,
        {
            "strategy_fit": 0.4,
            "locality": 0.25 if strategy in {"local-first", "orchestrator-first"} else 0.15,
            "review_alignment": 0.15 if consensus_mode == "reviewer-gate" else 0.1,
            "requester_bias": base_requester_score,
        },
        "session requester aligned to primary lane",
    )
    _add_candidate(
        "reviewer",
        reviewer_lane,
        _agent_for_orchestration_lane(reviewer_lane, requested_by, "reviewer"),
        "reviewer",
        {
            "strategy_fit": 0.2,
            "locality": 0.2,
            "review_alignment": 0.45,
            "requester_bias": 0.05,
        },
        "reviewer gate candidate",
    )
    if escalation_lane != "none":
        remote_weight = 0.45 if strategy == "escalate-on-complexity" else 0.2
        _add_candidate(
            "escalation",
            escalation_lane,
            _agent_for_orchestration_lane(escalation_lane, requested_by, "escalation"),
            "escalation",
            {
                "strategy_fit": remote_weight,
                "locality": 0.05,
                "review_alignment": 0.15 if consensus_mode == "arbiter-review" else 0.1,
                "requester_bias": 0.05,
            },
            "escalation lane candidate",
        )
    for idx, lane in enumerate(collaborator_lanes, start=1):
        collaborator_agent = _agent_for_orchestration_lane(lane, requested_by, "collaborator")
        collaborator_locality = 0.05 if lane in _ORCHESTRATION_ESCALATION_LANES else 0.2
        collaborator_strategy_fit = 0.25 if strategy in {"evidence-first", "escalate-on-complexity"} else 0.18
        _add_candidate(
            f"collaborator-{idx}",
            lane,
            collaborator_agent,
            "collaborator",
            {
                "strategy_fit": collaborator_strategy_fit,
                "locality": collaborator_locality,
                "review_alignment": 0.12,
                "requester_bias": 0.04,
            },
            f"parallel collaborator lane candidate ({lane})",
        )

    candidates.sort(key=lambda item: (float(item.get("score", 0.0)), item.get("candidate_id", "")), reverse=True)
    selected = candidates[0] if candidates else {}
    arbiter_candidate = next((item for item in candidates if item.get("candidate_id") == "reviewer"), selected)
    arbiter_state: Dict[str, Any] = {}
    if consensus_mode == "arbiter-review":
        arbiter_state = {
            "required": True,
            "status": "pending",
            "arbiter": str((arbiter_candidate or {}).get("agent", "") or "codex"),
            "arbiter_lane": str((arbiter_candidate or {}).get("lane", "") or "codex-review"),
            "selected_candidate_id": None,
            "selected_lane": None,
            "selected_agent": None,
            "last_decision": None,
            "history": [],
        }
    return {
        "selection_strategy": strategy,
        "consensus_mode": consensus_mode,
        "status": "pending",
        "selected_candidate_id": selected.get("candidate_id"),
        "selected_lane": selected.get("lane"),
        "selected_agent": selected.get("agent"),
        "selected_role": selected.get("role"),
        "selected_profile": selected.get("profile"),
        "selected_runtime_id": selected.get("runtime_id"),
        "candidates": candidates,
        "history": [],
        "arbiter": arbiter_state,
    }


def _build_orchestration_team(
    policy: Dict[str, Any],
    orchestration: Dict[str, Any],
    consensus: Dict[str, Any],
) -> Dict[str, Any]:
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    selected_candidate_id = str(consensus.get("selected_candidate_id", "") or "").strip()
    primary_candidate = by_id.get(selected_candidate_id) or next(iter(by_id.values()), {})
    reviewer_candidate = by_id.get("reviewer") or {}
    escalation_candidate = by_id.get("escalation") or {}
    collaborator_candidates = [
        candidate
        for candidate_id, candidate in by_id.items()
        if candidate_id.startswith("collaborator-")
    ]
    requested_by = str(orchestration.get("requested_by", "human") or "human").strip() or "human"
    requester_role = str(orchestration.get("requester_role", "orchestrator") or "orchestrator").strip() or "orchestrator"
    allow_parallel = bool(policy.get("allow_parallel_subagents", False))
    max_parallel = max(1, int(policy.get("max_parallel_subagents", 1) or 1))
    selection_strategy = str(policy.get("selection_strategy", "orchestrator-first") or "orchestrator-first").strip()
    consensus_mode = str(consensus.get("consensus_mode", policy.get("consensus_mode", "reviewer-gate")) or "reviewer-gate").strip()

    team_members: List[Dict[str, Any]] = []

    def _append_member(candidate: Dict[str, Any], slot: str, required: bool, activation_reason: str) -> None:
        if not candidate:
            return
        team_members.append(
            {
                "slot": slot,
                "candidate_id": str(candidate.get("candidate_id", "") or "").strip(),
                "lane": str(candidate.get("lane", "") or "").strip(),
                "agent": str(candidate.get("agent", "") or "").strip(),
                "role": str(candidate.get("role", "") or "").strip(),
                "profile": str(candidate.get("profile", "") or "").strip(),
                "runtime_id": str(candidate.get("runtime_id", "") or "").strip(),
                "score": round(float(candidate.get("score", 0.0) or 0.0), 4),
                "required": required,
                "activation_reason": activation_reason,
            }
        )

    _append_member(primary_candidate, "primary", True, "highest-ranked primary execution candidate")
    _append_member(reviewer_candidate, "reviewer", True, "reviewer gate coverage")

    if escalation_candidate and (
        allow_parallel or selection_strategy == "escalate-on-complexity" or consensus_mode == "arbiter-review"
    ):
        _append_member(
            escalation_candidate,
            "escalation",
            consensus_mode == "arbiter-review" or selection_strategy == "escalate-on-complexity",
            "escalation lane reserved for complex or arbitrated tasks",
        )
    if allow_parallel and collaborator_candidates:
        for candidate in collaborator_candidates:
            lane = str(candidate.get("lane", "") or "").strip() or "unknown"
            _append_member(
                candidate,
                f"collaborator:{lane}",
                False,
                f"parallel collaborator lane activated for {lane}",
            )

    # Keep deterministic bounded team size while allowing limited multi-role composition.
    unique_members: List[Dict[str, Any]] = []
    seen_slots = set()
    for member in team_members:
        slot = str(member.get("slot", "") or "")
        if not slot or slot in seen_slots:
            continue
        seen_slots.add(slot)
        unique_members.append(member)
    required_members = [member for member in unique_members if bool(member.get("required"))]
    optional_members = [member for member in unique_members if not bool(member.get("required"))]
    optional_budget = max(0, max_parallel - 1)
    active_members = required_members + optional_members[:optional_budget]
    deferred_members = optional_members[optional_budget:]
    active_slots = [str(member.get("slot", "") or "") for member in active_members]
    deferred_slots = [str(member.get("slot", "") or "") for member in deferred_members]
    required_slots = [str(member.get("slot", "") or "") for member in required_members]
    return {
        "requested_by": requested_by,
        "requester_role": requester_role,
        "formation_mode": "dynamic-role-assignment",
        "selection_strategy": selection_strategy,
        "consensus_mode": consensus_mode,
        "allow_parallel_subagents": allow_parallel,
        "max_parallel_subagents": max_parallel,
        "required_slots": required_slots,
        "optional_slot_capacity": optional_budget,
        "active_slots": active_slots,
        "deferred_slots": deferred_slots,
        "members": active_members,
        "deferred_members": deferred_members,
    }


def _normalize_consensus_decisions(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "") or "").strip()
        reviewer = str(item.get("reviewer", "") or "").strip()[:64]
        verdict = str(item.get("verdict", "") or "").strip().lower()
        rationale = str(item.get("rationale", "") or "").strip()[:400]
        if not candidate_id or not reviewer or verdict not in {"accept", "reject", "prefer"}:
            continue
        normalized.append(
            {
                "candidate_id": candidate_id,
                "reviewer": reviewer,
                "verdict": verdict,
                "rationale": rationale,
            }
        )
    return normalized


def _apply_consensus_update(
    session: Dict[str, Any],
    *,
    selected_candidate_id: str,
    decisions: List[Dict[str, Any]],
    summary: str,
) -> Dict[str, Any]:
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    if selected_candidate_id not in by_id:
        raise ValueError("selected_candidate_id must match an existing consensus candidate")

    normalized_decisions = _normalize_consensus_decisions(decisions)
    if not normalized_decisions:
        raise ValueError("decisions must contain at least one valid reviewer decision")

    now = int(time.time())
    selected_candidate = by_id[selected_candidate_id]
    accept_count = len([item for item in normalized_decisions if item.get("verdict") in {"accept", "prefer"}])
    reject_count = len([item for item in normalized_decisions if item.get("verdict") == "reject"])
    consensus["status"] = "accepted" if accept_count >= reject_count else "rejected"
    consensus["selected_candidate_id"] = selected_candidate_id
    consensus["selected_lane"] = selected_candidate.get("lane")
    consensus["selected_agent"] = selected_candidate.get("agent")
    consensus["selected_role"] = selected_candidate.get("role")
    consensus["selected_profile"] = selected_candidate.get("profile")
    consensus["selected_runtime_id"] = selected_candidate.get("runtime_id")
    history = consensus.get("history") if isinstance(consensus.get("history"), list) else []
    history.append(
        {
            "ts": now,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "summary": summary,
            "decisions": normalized_decisions,
        }
    )
    consensus["history"] = history[-10:]
    session["consensus"] = consensus
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    trajectory.append(
        {
            "ts": now,
            "event_type": "consensus_update",
            "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
            "detail": f"consensus -> {consensus['status']} ({selected_candidate_id})",
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "decision_count": len(normalized_decisions),
        }
    )
    session["trajectory"] = trajectory
    session["updated_at"] = now
    return consensus


def _apply_arbiter_update(
    session: Dict[str, Any],
    *,
    selected_candidate_id: str,
    arbiter: str,
    verdict: str,
    rationale: str,
    summary: str,
    supporting_decisions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    if str(consensus.get("consensus_mode", "") or "").strip() != "arbiter-review":
        raise ValueError("arbiter decisions require consensus_mode=arbiter-review")
    candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidates
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }
    if selected_candidate_id not in by_id:
        raise ValueError("selected_candidate_id must match an existing consensus candidate")
    normalized_verdict = str(verdict or "").strip().lower()
    if normalized_verdict not in {"accept", "reject", "prefer"}:
        raise ValueError("verdict must be one of: accept, reject, prefer")
    normalized_arbiter = str(arbiter or "").strip()[:64]
    if not normalized_arbiter:
        raise ValueError("arbiter required")
    normalized_rationale = str(rationale or "").strip()[:400]
    if not normalized_rationale:
        raise ValueError("rationale required")
    normalized_summary = str(summary or "").strip()[:400] or normalized_rationale
    normalized_support = _normalize_consensus_decisions(supporting_decisions or [])

    now = int(time.time())
    selected_candidate = by_id[selected_candidate_id]
    arbiter_state = consensus.get("arbiter") if isinstance(consensus.get("arbiter"), dict) else {}
    history = arbiter_state.get("history") if isinstance(arbiter_state.get("history"), list) else []
    decision = {
        "ts": now,
        "arbiter": normalized_arbiter,
        "verdict": normalized_verdict,
        "selected_candidate_id": selected_candidate_id,
        "selected_lane": selected_candidate.get("lane"),
        "selected_agent": selected_candidate.get("agent"),
        "selected_role": selected_candidate.get("role"),
        "rationale": normalized_rationale,
        "summary": normalized_summary,
        "supporting_decisions": normalized_support,
    }
    history.append(decision)
    arbiter_state.update(
        {
            "required": True,
            "status": "resolved",
            "arbiter": normalized_arbiter,
            "arbiter_lane": str(arbiter_state.get("arbiter_lane", "") or "codex-review"),
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "selected_profile": selected_candidate.get("profile"),
            "selected_runtime_id": selected_candidate.get("runtime_id"),
            "last_decision": decision,
            "history": history[-10:],
        }
    )
    consensus["arbiter"] = arbiter_state
    consensus["status"] = "accepted" if normalized_verdict in {"accept", "prefer"} else "rejected"
    consensus["selected_candidate_id"] = selected_candidate_id
    consensus["selected_lane"] = selected_candidate.get("lane")
    consensus["selected_agent"] = selected_candidate.get("agent")
    consensus["selected_role"] = selected_candidate.get("role")
    consensus["selected_profile"] = selected_candidate.get("profile")
    consensus["selected_runtime_id"] = selected_candidate.get("runtime_id")
    consensus_history = consensus.get("history") if isinstance(consensus.get("history"), list) else []
    consensus_history.append(
        {
            "ts": now,
            "source": "arbiter",
            "arbiter": normalized_arbiter,
            "verdict": normalized_verdict,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "summary": normalized_summary,
            "decisions": normalized_support,
        }
    )
    consensus["history"] = consensus_history[-10:]
    session["consensus"] = consensus
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    trajectory.append(
        {
            "ts": now,
            "event_type": "arbiter_decision",
            "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
            "detail": f"arbiter -> {consensus['status']} ({selected_candidate_id})",
            "arbiter": normalized_arbiter,
            "verdict": normalized_verdict,
            "selected_candidate_id": selected_candidate_id,
            "selected_lane": selected_candidate.get("lane"),
            "selected_agent": selected_candidate.get("agent"),
            "selected_role": selected_candidate.get("role"),
            "supporting_decision_count": len(normalized_support),
        }
    )
    session["trajectory"] = trajectory
    session["updated_at"] = now
    return consensus


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
    session.setdefault(
        "reviewer_gate",
        {
            "required": False,
            "last_review": None,
            "history": [],
            "status": "not_required",
        },
    )
    policy = session.get("orchestration_policy") if isinstance(session.get("orchestration_policy"), dict) else {}
    orchestration = session.get("orchestration") if isinstance(session.get("orchestration"), dict) else {}
    session.setdefault("consensus", _seed_agent_evaluation(policy, orchestration))
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    if isinstance(consensus, dict) and not str(consensus.get("selected_role", "") or "").strip():
        selected_candidate_id = str(consensus.get("selected_candidate_id", "") or "").strip()
        candidates = consensus.get("candidates") if isinstance(consensus.get("candidates"), list) else []
        selected_candidate = next(
            (
                item
                for item in candidates
                if isinstance(item, dict) and str(item.get("candidate_id", "") or "").strip() == selected_candidate_id
            ),
            {},
        )
        if selected_candidate:
            consensus["selected_role"] = str(selected_candidate.get("role", "") or "").strip()
            consensus["selected_profile"] = str(selected_candidate.get("profile", "") or "").strip()
            consensus["selected_runtime_id"] = str(selected_candidate.get("runtime_id", "") or "").strip()
            session["consensus"] = consensus
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    if not team:
        session["team"] = _build_orchestration_team(policy, orchestration, session["consensus"])
    session["orchestration_runtime"] = _build_orchestration_runtime_contract(session)


def _build_workflow_run_session(
    query: str,
    data: Dict[str, Any],
    selected_blueprint: Optional[Dict[str, Any]],
    orchestration: Dict[str, Any],
    lesson_refs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    incoming_contract = data.get("intent_contract")
    if incoming_contract is None and selected_blueprint:
        incoming_contract = selected_blueprint.get("intent_contract", {})
    validation = _validate_intent_contract(_coerce_intent_contract(query, incoming_contract))
    orchestration_payload = dict(orchestration)
    orchestration_payload.setdefault("query", query)
    orchestration_payload.setdefault("objective", query)
    incoming_policy = data.get("orchestration_policy")
    effective_policy: Optional[Dict[str, Any]] = None
    if isinstance(selected_blueprint, dict) and isinstance(selected_blueprint.get("orchestration_policy"), dict):
        effective_policy = dict(selected_blueprint.get("orchestration_policy", {}))
    if isinstance(incoming_policy, dict):
        if effective_policy is None:
            effective_policy = {}
        effective_policy.update(incoming_policy)
    policy_validation = _validate_orchestration_policy(
        effective_policy,
        query=query,
    )
    session_id = str(uuid4())
    plan = _build_workflow_plan(query)
    now = time.time()
    phases = []
    for idx, phase in enumerate(plan.get("phases", [])):
        phases.append(
            {
                "id": phase.get("id", f"phase-{idx}"),
                "status": "in_progress" if idx == 0 else "pending",
                "started_at": now if idx == 0 else None,
                "completed_at": None,
                "notes": [],
            }
        )

    seeded_consensus = _seed_agent_evaluation(policy_validation["normalized"], orchestration_payload)
    seeded_team = _build_orchestration_team(policy_validation["normalized"], orchestration_payload, seeded_consensus)
    reasoning_pattern = (
        ((plan.get("metadata") or {}) if isinstance(plan.get("metadata"), dict) else {}).get("reasoning_pattern", {})
    )
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
        "blueprint_id": str(data.get("blueprint_id", "") or "").strip() or None,
        "blueprint_title": (
            str(selected_blueprint.get("title", "")).strip()
            if isinstance(selected_blueprint, dict)
            else ""
        ) or None,
        "intent_contract": validation["normalized"],
        "orchestration": orchestration_payload,
        "orchestration_policy": policy_validation["normalized"],
        "consensus": seeded_consensus,
        "team": seeded_team,
        "reasoning_pattern": reasoning_pattern,
        "reviewer_gate": {
            "required": _blueprint_requires_reviewer_gate(selected_blueprint),
            "last_review": None,
            "history": [],
            "status": "pending_review" if _blueprint_requires_reviewer_gate(selected_blueprint) else "not_required",
        },
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
                "requester_role": orchestration["requester_role"],
                "requested_by": orchestration["requested_by"],
                "delegate_via_coordinator_only": True,
                "reviewer_gate_required": _blueprint_requires_reviewer_gate(selected_blueprint),
                "primary_lane": policy_validation["normalized"]["primary_lane"],
                "consensus_mode": policy_validation["normalized"]["consensus_mode"],
                "arbiter_required": policy_validation["normalized"]["consensus_mode"] == "arbiter-review",
                "selected_candidate_id": seeded_consensus.get("selected_candidate_id"),
                "team_slots": seeded_team.get("active_slots", []),
                "reasoning_pattern": reasoning_pattern.get("selected_pattern", ""),
                "reasoning_pattern_boost": reasoning_pattern.get("boost_multiplier", 1.0),
            }
        ],
    }
    if lesson_refs:
        session["active_lesson_refs"] = lesson_refs
    return session


def _resolve_history_role(
    session: Dict[str, Any],
    *,
    agent: str,
    profile: str,
    review_type: str = "",
) -> str:
    agent_key = str(agent or "").strip()
    profile_key = str(profile or "").strip()
    if not agent_key:
        return "unknown"

    roles = set()
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    for member in team.get("members", []) if isinstance(team.get("members"), list) else []:
        if not isinstance(member, dict):
            continue
        if str(member.get("agent", "") or "").strip() == agent_key:
            role = _normalize_agent_role(member.get("slot") or member.get("role"))
            if role != "unknown":
                roles.add(role)

    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    for candidate in consensus.get("candidates", []) if isinstance(consensus.get("candidates"), list) else []:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("agent", "") or "").strip() != agent_key:
            continue
        candidate_role = _normalize_agent_role(candidate.get("role"))
        candidate_lane = str(candidate.get("lane", "") or "").strip()
        if profile_key and candidate_lane == profile_key and candidate_role != "unknown":
            return candidate_role
        if candidate_role != "unknown":
            roles.add(candidate_role)

    if len(roles) == 1:
        return next(iter(roles))

    normalized_review_type = str(review_type or "").strip().lower()
    if normalized_review_type == "plan_review" or profile_key == "remote-reasoning":
        return "escalation"
    if normalized_review_type in {"artifact_review", "patch_review", "acceptance"}:
        return "primary"
    return "unknown"


def _blueprint_requires_reviewer_gate(blueprint: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(blueprint, dict):
        return False
    phases = blueprint.get("phases", [])
    if not isinstance(phases, list):
        return False
    return any(bool(item.get("requires_approval")) for item in phases if isinstance(item, dict))


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


def _resolve_orchestration_workspace_mode(session: Dict[str, Any]) -> str:
    """Map workflow isolation state onto orchestration workspace modes."""
    isolation = _resolve_isolation_profile(session)
    workspace_root = str(isolation.get("workspace_root", "") or "").strip().lower()
    safety_mode = str(session.get("safety_mode", "plan-readonly") or "plan-readonly").strip().lower()

    if "/worktree" in workspace_root or workspace_root.endswith("/worktrees"):
        return IsolationMode.GIT_WORKTREE.value
    if safety_mode == "execute-mutating":
        return IsolationMode.COPY.value
    return IsolationMode.TEMP_DIR.value


def _build_orchestration_runtime_contract(session: Dict[str, Any]) -> Dict[str, Any]:
    """Expose the integrated orchestration-framework view for a workflow session."""
    team = session.get("team") if isinstance(session.get("team"), dict) else {}
    consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
    reasoning_pattern = session.get("reasoning_pattern") if isinstance(session.get("reasoning_pattern"), dict) else {}
    trajectory = session.get("trajectory") if isinstance(session.get("trajectory"), list) else []
    resolved_profile = _resolve_isolation_profile(session)
    members = team.get("members") if isinstance(team.get("members"), list) else []
    deferred_members = team.get("deferred_members") if isinstance(team.get("deferred_members"), list) else []

    # Get live orchestration framework state
    session_id = str(session.get("session_id", "") or "").strip()
    hq_session = _AGENT_HQ.get_session(session_id)
    hq_status = _AGENT_HQ.get_session_status(session_id) if hq_session else None
    delegation_status = _DELEGATION_API.get_queue_status()
    workspace_list = _WORKSPACE_MANAGER.list_workspaces(session_id=session_id)
    tool_report = _MCP_TOOL_INVOKER.get_usage_report()

    return {
        "framework": "multi-agent-orchestration-foundation",
        "framework_status": "live",
        "agent_hq": {
            "enabled": True,
            "session_id": session_id,
            "state": hq_session.state.value if hq_session else str(session.get("status", "unknown") or "unknown").strip(),
            "checkpointing": True,
            "timeline_events": len(trajectory),
            "live_session": hq_session is not None,
            "registered_agents": len(_AGENT_HQ.global_agents),
            "active_sessions": len(_AGENT_HQ.sessions),
            "checkpoint_count": len(hq_session.checkpoints) if hq_session else 0,
            "task_summary": hq_status.get("tasks", {}) if hq_status else {},
        },
        "delegation": {
            "enabled": True,
            "selection_strategy": str(team.get("selection_strategy", "") or "").strip(),
            "consensus_mode": str(consensus.get("consensus_mode", "") or "").strip(),
            "selected_agent": str(consensus.get("selected_agent", "") or "").strip(),
            "selected_lane": str(consensus.get("selected_lane", "") or "").strip(),
            "selected_profile": str(consensus.get("selected_profile", "") or "").strip(),
            "selected_runtime_id": str(consensus.get("selected_runtime_id", "") or "").strip(),
            "active_member_count": len(members),
            "deferred_member_count": len(deferred_members),
            "queue_size": delegation_status.get("queue_size", 0),
            "pending_delegations": delegation_status.get("pending_count", 0),
            "completed_delegations": delegation_status.get("completed_count", 0),
            "registered_targets": len(delegation_status.get("agents", {})),
        },
        "workspace": {
            "enabled": True,
            "mode": _resolve_orchestration_workspace_mode(session),
            "resolved_profile": resolved_profile,
            "network_policy": str(resolved_profile.get("network_policy", "") or "").strip(),
            "active_workspaces": len(workspace_list),
            "total_workspaces": len(_WORKSPACE_MANAGER.workspaces),
        },
        "tool_invocation": {
            "enabled": True,
            "catalog_size": len(workflow_tool_catalog("") or []),
            "status": ToolStatus.AVAILABLE.value,
            "cache_enabled": True,
            "reasoning_pattern": str(reasoning_pattern.get("selected_pattern", "") or "").strip(),
            "registered_tools": tool_report.get("tools_registered", 0),
            "total_invocations": tool_report.get("analytics", {}).get("total_invocations", 0),
            "pending_approvals": tool_report.get("pending_approvals", 0),
        },
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

    async def handle_well_known_mcp(request):
        """
        MCP Protocol Compliance: /.well-known/mcp.json endpoint.

        Exposes server capabilities, version, and supported protocols
        per MCP 2026 roadmap recommendations.
        """
        # Build tool catalog summary (use empty query for general catalog)
        try:
            tool_list = workflow_tool_catalog("")
            tool_count = len(tool_list) if isinstance(tool_list, list) else 0
            tool_summary = [
                {"name": t.get("name", ""), "description": (t.get("description", "") or "")[:100]}
                for t in (tool_list if isinstance(tool_list, list) else [])[:10]
            ]
        except Exception:
            tool_count = 0
            tool_summary = []

        payload = {
            "mcp_version": "2026.1",
            "server": {
                "name": "hybrid-coordinator",
                "version": "1.1.0",
                "description": "AI workflow orchestration and RAG coordination server",
            },
            "capabilities": {
                "augment_query": True,
                "route_search": True,
                "tree_search": True,
                "memory_store": True,
                "memory_recall": True,
                "hints": True,
                "workflow_orchestration": True,
                "multi_turn_context": True,
                "web_research": True,
                "browser_research": True,
                "delegation": True,
                "autoresearch": True,
            },
            "protocols": {
                "http": True,
                "mcp_stdio": True,
                "jsonrpc": True,
            },
            "tools": {
                "count": tool_count,
                "summary": tool_summary,
            },
            "endpoints": {
                "health": "/health",
                "health_detailed": "/health/detailed",
                "status": "/status",
                "hints": "/hints",
                "workflow_plan": "/workflow/plan",
                "delegate": "/control/ai-coordinator/delegate",
            },
            "rate_limiting": {
                "enabled": True,
                "default_rpm": 60,
            },
            "links": {
                "documentation": "https://github.com/yourusername/NixOS-Dev-Quick-Deploy",
                "health": "/health",
            },
        }
        return web.json_response(payload)

    async def handle_well_known_a2a(request: web.Request) -> web.Response:
        """Expose an A2A-style agent card backed by the hybrid coordinator."""
        base_url = f"{request.scheme}://{request.host}"
        return web.json_response(_build_a2a_agent_card(base_url))

    async def handle_a2a_task_events(request: web.Request) -> web.StreamResponse:
        """Replay task state as an A2A-style SSE stream for clients."""
        session_id = request.match_info.get("session_id", "")
        try:
            since = max(0, int(request.rel_url.query.get("since", "0") or 0))
        except ValueError:
            since = 0
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(session_id)
        if not session:
            return web.json_response({"error": "session not found"}, status=404)
        _ensure_session_runtime_fields(session)
        base_url = f"{request.scheme}://{request.host}"
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)
        snapshot = _session_to_a2a_task(session, base_url)
        await response.write(
            f"event: task\ndata: {json.dumps(snapshot, separators=(',', ':'))}\n\n".encode("utf-8")
        )
        await response.write(
            (
                f"event: status-update\ndata: "
                f"{json.dumps(_session_to_a2a_status_event(session, base_url, final=False), separators=(',', ':'))}\n\n"
            ).encode("utf-8")
        )
        for artifact in snapshot.get("artifacts", []) or []:
            if not isinstance(artifact, dict):
                continue
            await response.write(
                (
                    f"event: artifact-update\ndata: "
                    f"{json.dumps(_artifact_to_a2a_update(snapshot, artifact), separators=(',', ':'))}\n\n"
                ).encode("utf-8")
            )
        trajectory = list(session.get("trajectory", []) or [])
        for idx, event in enumerate(trajectory[since:], start=since):
            payload = _session_to_a2a_status_event(
                session,
                base_url,
                detail=str(event.get("detail", "") or str(event.get("event_type", "") or "workflow event")).strip(),
                timestamp=event.get("ts"),
                final=False,
            )
            payload["metadata"] = {
                **(payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}),
                "index": idx,
                "eventType": str(event.get("event_type", "")).strip(),
                "phaseId": str(event.get("phase_id", "")).strip(),
                "riskClass": str(event.get("risk_class", "")).strip(),
            }
            await response.write(
                f"event: status-update\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n".encode("utf-8")
            )
        await response.write(
            (
                f"event: status-update\ndata: "
                f"{json.dumps(_session_to_a2a_status_event(session, base_url), separators=(',', ':'))}\n\n"
            ).encode("utf-8")
        )
        await response.write_eof()
        return response

    async def handle_a2a_rpc(request: web.Request) -> web.Response:
        """Serve a compact A2A-compatible JSON-RPC surface over workflow sessions."""
        try:
            payload = await request.json()
        except Exception:
            return web.json_response(_jsonrpc_error(None, -32700, "parse error"))
        if not isinstance(payload, dict):
            return web.json_response(_jsonrpc_error(None, -32600, "invalid request"))

        request_id = _coerce_a2a_request_id(payload.get("id"))
        if payload.get("id") is not None and request_id is None:
            return web.json_response(_jsonrpc_error(None, -32600, "invalid request"))
        if str(payload.get("jsonrpc", "") or "") != "2.0":
            return web.json_response(_jsonrpc_error(request_id, -32600, "invalid request"))
        raw_method = payload.get("method")
        if not isinstance(raw_method, str) or not raw_method.strip():
            return web.json_response(_jsonrpc_error(request_id, -32600, "invalid request"))
        method = _normalize_a2a_method(raw_method)
        params = payload.get("params")
        if not isinstance(params, dict):
            return web.json_response(_jsonrpc_error(request_id, -32602, "invalid params"))
        base_url = f"{request.scheme}://{request.host}"

        try:
            if method == "agent/getCard":
                return web.json_response(_jsonrpc_success(request_id, _build_a2a_agent_card(base_url)))

            if method == "agent/getAuthenticatedExtendedCard":
                return web.json_response(_jsonrpc_error(request_id, -32007, "authentication required"))

            if method == "tasks/resubscribe":
                return web.json_response(_jsonrpc_error(request_id, -32003, "push notification not supported"))

            if method == "tasks/get":
                task_id = str(params.get("id") or params.get("taskId") or "").strip()
                if not task_id:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "task id required"))
                history_length = params.get("historyLength")
                if history_length is not None:
                    try:
                        history_length = int(history_length)
                    except (TypeError, ValueError):
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                    if history_length < 0:
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                async with _workflow_sessions_lock:
                    sessions = await _load_workflow_sessions()
                    session = sessions.get(task_id)
                if not session:
                    return web.json_response(_jsonrpc_error(request_id, -32001, "task not found"))
                _ensure_session_runtime_fields(session)
                return web.json_response(
                    _jsonrpc_success(
                        request_id,
                        _session_to_a2a_task(session, base_url, history_length=history_length),
                    )
                )

            if method == "tasks/list":
                context_id = str(params.get("contextId") or "").strip()
                status_filter = _normalize_a2a_status_filter(params.get("status"))
                if params.get("status") is not None and not status_filter:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid status"))
                explicit_page_size = "pageSize" in params
                page_size_raw = params.get("pageSize", params.get("limit", 50))
                try:
                    page_size = int(page_size_raw if page_size_raw is not None else 50)
                except (TypeError, ValueError):
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageSize"))
                if page_size < 0 or page_size > 100 or (explicit_page_size and page_size == 0):
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageSize"))
                history_length = params.get("historyLength")
                if history_length is not None:
                    try:
                        history_length = int(history_length)
                    except (TypeError, ValueError):
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                    if history_length < 0:
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                include_artifacts = bool(params.get("includeArtifacts", False))
                status_timestamp_after = str(params.get("statusTimestampAfter") or "").strip()
                cutoff_iso = ""
                if status_timestamp_after:
                    try:
                        cutoff_iso = datetime.fromisoformat(status_timestamp_after.replace("Z", "+00:00")).isoformat()
                    except ValueError:
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid statusTimestampAfter"))
                page_token = str(params.get("pageToken") or "").strip()
                start = 0
                if page_token:
                    try:
                        start = int(page_token)
                    except ValueError:
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
                    if start < 0:
                        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
                async with _workflow_sessions_lock:
                    sessions = await _load_workflow_sessions()
                    items = list(sessions.values())
                items.sort(key=lambda item: float(item.get("updated_at", 0) or 0), reverse=True)
                filtered: List[Dict[str, Any]] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    _ensure_session_runtime_fields(item)
                    task = _session_to_a2a_task(
                        item,
                        base_url,
                        history_length=history_length,
                        include_artifacts=include_artifacts,
                    )
                    if context_id and str(task.get("contextId", "") or "").strip() != context_id:
                        continue
                    if status_filter and str(task.get("status", {}).get("state", "") or "").strip() != status_filter:
                        continue
                    if cutoff_iso and str(task.get("status", {}).get("timestamp", "") or "") <= cutoff_iso:
                        continue
                    filtered.append(task)
                total_size = len(filtered)
                if start > total_size:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
                tasks = filtered[start : start + page_size] if page_size > 0 else []
                next_page_token = ""
                if start + len(tasks) < total_size:
                    next_page_token = str(start + len(tasks))
                return web.json_response(
                    _jsonrpc_success(
                        request_id,
                        {
                            "tasks": tasks,
                            "totalSize": total_size,
                            "pageSize": len(tasks),
                            "nextPageToken": next_page_token,
                        },
                    )
                )

            if method == "tasks/cancel":
                task_id = str(params.get("id") or params.get("taskId") or "").strip()
                if not task_id:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "task id required"))
                async with _workflow_sessions_lock:
                    sessions = await _load_workflow_sessions()
                    session = sessions.get(task_id)
                    if not session:
                        return web.json_response(_jsonrpc_error(request_id, -32001, "task not found"))
                    _ensure_session_runtime_fields(session)
                    now = time.time()
                    session["status"] = "canceled"
                    session["updated_at"] = now
                    session["trajectory"].append(
                        {
                            "ts": now,
                            "event_type": "task_canceled",
                            "phase_id": f"phase-{int(session.get('current_phase_index', 0) or 0)}",
                            "detail": str(params.get("reason", "") or "canceled via A2A RPC").strip(),
                        }
                    )
                    sessions[task_id] = session
                    await _save_workflow_sessions(sessions)
                return web.json_response(_jsonrpc_success(request_id, _session_to_a2a_task(session, base_url)))

            if method in {"message/send", "message/stream"}:
                message = params.get("message")
                text = _extract_a2a_text(message)
                if not text:
                    text = str(params.get("text", "") or "").strip()
                if not text:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "message text required"))

                task_id = str(
                    params.get("taskId")
                    or params.get("id")
                    or (message.get("taskId") if isinstance(message, dict) else "")
                    or ""
                ).strip()
                context_id = str(
                    params.get("contextId")
                    or (message.get("contextId") if isinstance(message, dict) else "")
                    or ""
                ).strip()
                async with _agent_lessons_lock:
                    lesson_registry = await _load_agent_lessons_registry()
                lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
                if task_id:
                    async with _workflow_sessions_lock:
                        sessions = await _load_workflow_sessions()
                        session = sessions.get(task_id)
                        if not session:
                            return web.json_response(_jsonrpc_error(request_id, -32001, "task not found"))
                        _ensure_session_runtime_fields(session)
                        now = time.time()
                        session["updated_at"] = now
                        session["status"] = "working"
                        session["trajectory"].append(
                            {
                                "ts": now,
                                "event_type": "message_send",
                                "phase_id": f"phase-{int(session.get('current_phase_index', 0) or 0)}",
                                "detail": text,
                                "risk_class": "safe",
                            }
                        )
                        if context_id:
                            session["context_id"] = context_id
                        sessions[task_id] = session
                        await _save_workflow_sessions(sessions)
                else:
                    blueprints_data = _load_and_validate_workflow_blueprints()
                    blueprint_id = str(params.get("blueprint_id", "") or "").strip()
                    selected_blueprint = (
                        blueprints_data.get("blueprint_by_id", {}).get(blueprint_id)
                        if blueprint_id
                        else None
                    )
                    start_data = {
                        "query": text,
                        "prompt": text,
                        "blueprint_id": blueprint_id,
                        "safety_mode": str(params.get("safetyMode") or params.get("safety_mode") or "plan-readonly"),
                        "token_limit": params.get("tokenLimit"),
                        "tool_call_limit": params.get("toolCallLimit"),
                        "intent_contract": params.get("intent_contract"),
                        "isolation_profile": params.get("isolationProfile"),
                        "workspace_root": params.get("workspaceRoot"),
                        "network_policy": params.get("networkPolicy"),
                        "agent": "a2a",
                        "role": "orchestrator",
                    }
                    orchestration = _coerce_orchestration_context(start_data)
                    session = _build_workflow_run_session(
                        query=text,
                        data=start_data,
                        selected_blueprint=selected_blueprint,
                        orchestration=orchestration,
                        lesson_refs=lesson_refs,
                    )
                    if context_id:
                        session["context_id"] = context_id
                    task_id = session["session_id"]
                    async with _workflow_sessions_lock:
                        sessions = await _load_workflow_sessions()
                        sessions[task_id] = session
                        await _save_workflow_sessions(sessions)

                task = _session_to_a2a_task(session, base_url)
                result = {
                    "task": task,
                    "message": {
                        "role": "ROLE_AGENT",
                        "parts": _a2a_text_parts(
                            f"Accepted task '{session.get('objective', '')}'. Track status via tasks/get or the task event stream."
                        ),
                        "messageId": f"{task_id}:accepted",
                        "taskId": task_id,
                    },
                    "stream": {
                        "url": f"{base_url.rstrip('/')}/a2a/tasks/{task_id}/events",
                    },
                }
                if lesson_refs:
                    result["active_lesson_refs"] = lesson_refs
                if method == "message/stream":
                    stream_response = web.StreamResponse(
                        status=200,
                        headers={
                            "Content-Type": "text/event-stream",
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                        },
                    )
                    await stream_response.prepare(request)
                    await stream_response.write(
                        (
                            f"event: task\ndata: "
                            f"{json.dumps(_jsonrpc_success(request_id, task), separators=(',', ':'))}\n\n"
                        ).encode("utf-8")
                    )
                    await stream_response.write(
                        (
                            f"event: status-update\ndata: "
                            f"{json.dumps(_jsonrpc_success(request_id, _session_to_a2a_status_event(session, base_url, final=False)), separators=(',', ':'))}\n\n"
                        ).encode("utf-8")
                    )
                    for artifact in task.get("artifacts", []) or []:
                        if not isinstance(artifact, dict):
                            continue
                        await stream_response.write(
                            (
                                f"event: artifact-update\ndata: "
                                f"{json.dumps(_jsonrpc_success(request_id, _artifact_to_a2a_update(task, artifact)), separators=(',', ':'))}\n\n"
                            ).encode("utf-8")
                        )
                    await stream_response.write(
                        (
                            f"event: message\ndata: "
                            f"{json.dumps(_jsonrpc_success(request_id, result.get('message', {})), separators=(',', ':'))}\n\n"
                        ).encode("utf-8")
                    )
                    await stream_response.write_eof()
                    return stream_response
                return web.json_response(_jsonrpc_success(request_id, result))

            return web.json_response(_jsonrpc_error(request_id, -32601, "method not found"))
        except Exception as exc:
            logger.error("handle_a2a_rpc error=%s", exc)
            return web.json_response(
                _jsonrpc_error(request_id, -32603, "internal error", {"detail": str(exc)[:240]}),
            )

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

        payload = {
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
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

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
        payload = {
            "status": service_status,
            "service": "hybrid-coordinator",
            "dependencies": deps,
            "performance": perf,
            "circuit_breakers": _CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {},
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload, status=200 if service_status in ("healthy", "degraded") else 503)

    async def handle_health_aggregate(request):
        """
        Phase 11.2 — Health aggregator endpoint.

        Pings all MCP servers, measures latency, aggregates health status,
        and maintains health history for trend analysis.
        """
        servers = {
            "hybrid-coordinator": {"url": "http://127.0.0.1:8003", "endpoint": "/health"},
            "aidb": {"url": os.getenv("AIDB_URL", "http://127.0.0.1:8002").strip(), "endpoint": "/health"},
            "ralph-wiggum": {"url": Config.RALPH_WIGGUM_URL.rstrip("/"), "endpoint": "/health"},
            "llama-cpp": {"url": os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080").strip(), "endpoint": "/health"},
            "qdrant": {"url": os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip(), "endpoint": "/collections"},
        }

        results: Dict[str, Any] = {}
        aggregate_start = time.time()

        async def ping_server(name: str, info: Dict[str, str]) -> Dict[str, Any]:
            url = f"{info['url']}{info['endpoint']}"
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(url)
                    latency_ms = round((time.time() - start) * 1000, 1)
                    body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                    status = "healthy" if resp.status_code < 400 else "degraded" if resp.status_code < 500 else "unhealthy"
                    return {
                        "status": status,
                        "http_status": resp.status_code,
                        "latency_ms": latency_ms,
                        "reported_status": body.get("status"),
                    }
            except Exception as exc:
                latency_ms = round((time.time() - start) * 1000, 1)
                return {
                    "status": "unreachable",
                    "latency_ms": latency_ms,
                    "error": str(exc)[:120],
                }

        # Ping all servers concurrently
        tasks = {name: ping_server(name, info) for name, info in servers.items()}
        for name, task in tasks.items():
            results[name] = await task

        aggregate_latency_ms = round((time.time() - aggregate_start) * 1000, 1)

        # Determine overall status
        statuses = [r.get("status", "unknown") for r in results.values()]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s in ("unhealthy", "unreachable") for s in statuses):
            overall = "degraded"
        else:
            overall = "partially_healthy"

        # Record health history
        snapshot = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall": overall,
            "servers": {k: v.get("status") for k, v in results.items()},
            "latencies": {k: v.get("latency_ms") for k, v in results.items()},
        }
        _HEALTH_HISTORY.append(snapshot)

        # Build trend from history
        trend = None
        if len(_HEALTH_HISTORY) >= 3:
            recent = list(_HEALTH_HISTORY)[-10:]
            healthy_count = sum(1 for h in recent if h.get("overall") == "healthy")
            if healthy_count >= 8:
                trend = "stable"
            elif healthy_count >= 5:
                trend = "fluctuating"
            else:
                trend = "degrading"

        payload = {
            "status": overall,
            "aggregate_latency_ms": aggregate_latency_ms,
            "servers": results,
            "trend": trend,
            "history_depth": len(_HEALTH_HISTORY),
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }

        return web.json_response(payload, status=200 if overall == "healthy" else 207)

    async def handle_stats(request):
        payload = {
            "status": "ok",
            "service": "hybrid-coordinator",
            "stats": _snapshot_stats(),
            "collections": list(_COLLECTIONS.keys()),
            "harness_stats": _HARNESS_STATS,
            "capability_discovery": _HYBRID_STATS.get("capability_discovery", {}),
            "circuit_breakers": _CIRCUIT_BREAKERS.get_all_stats() if _CIRCUIT_BREAKERS else {},
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
                planned, tool_security = _audit_planned_tools(query, workflow_tool_catalog(query))
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
                    and _is_continuation_query(query)
                    and any(p.get("name") == "memory_recall" for p in planned)
                ):
                    try:
                        _memory_start = time.perf_counter()
                        request_context["memory_recall_attempted"] = True
                        memory_result = await _recall_memory(
                            query=query,
                            memory_types=None,
                            limit=3,
                            retrieval_mode="hybrid",
                        )
                        memory_rows = memory_result.get("results", []) if isinstance(memory_result, dict) else []
                        memory_summaries = [
                            str(row.get("summary") or row.get("content") or "").strip()
                            for row in memory_rows
                            if isinstance(row, dict) and str(row.get("summary") or row.get("content") or "").strip()
                        ]
                        if memory_summaries:
                            request_context["memory_recall"] = memory_summaries[:3]
                            tooling_layer["memory_recall"] = memory_summaries[:2]
                        else:
                            request_context["memory_recall_miss"] = True
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
            cached_result = None
            if cache_enabled and _should_use_cache(query):
                cached_result = _get_cached_response(query, context=request_context)

            if cached_result:
                # Cache hit - use cached response
                cached_response, cache_metadata = cached_result
                result = {
                    "response": cached_response,
                    "from_cache": True,
                    "cache_metadata": cache_metadata,
                    "query": query,
                }
                logger.info(f"Cache hit for query: {query[:60]}...")
            else:
                # Cache miss - proceed with route_search
                result = await _route_search(
                    query=query,
                    mode=data.get("mode", "auto"),
                    prefer_local=prefer_local,
                    context=request_context,
                    limit=int(data.get("limit", 5)),
                    keyword_limit=int(data.get("keyword_limit", 5)),
                    score_threshold=float(data.get("score_threshold", 0.7)),
                    generate_response=generate_response,
                )

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

    async def handle_memory_store(request):
        try:
            data = await request.json()
            memory_type = normalize_memory_type(data.get("memory_type", ""))
            summary = coerce_memory_summary(data.get("summary"), data.get("content"))
            # Phase 1.3 — Profile memory store operation
            _mem_store_start = time.time()
            result = await _store_memory(
                memory_type=memory_type,
                summary=summary,
                content=data.get("content"),
                metadata=data.get("metadata"),
            )
            _mem_store_duration_ms = (time.time() - _mem_store_start) * 1000
            _PERFORMANCE_PROFILER.record_metric("memory_store", _mem_store_duration_ms, {"memory_type": memory_type})
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
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
            # Phase 1.3 — Profile memory recall operation
            _mem_recall_start = time.time()
            result = await _recall_memory(
                query=query,
                memory_types=data.get("memory_types"),
                limit=data.get("limit"),
                retrieval_mode=data.get("retrieval_mode", "hybrid"),
            )
            _mem_recall_duration_ms = (time.time() - _mem_recall_start) * 1000
            _PERFORMANCE_PROFILER.record_metric("memory_recall", _mem_recall_duration_ms, {"query_len": len(query), "mode": data.get("retrieval_mode", "hybrid")})
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
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
        payload = dict(_HARNESS_STATS)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

    async def handle_harness_scorecard(_request):
        payload = _build_scorecard()
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs and isinstance(payload, dict):
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

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
            payload = response.dict()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback(request):
        try:
            data = await request.json()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
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
                payload = {"status": "recorded", "feedback_id": feedback_id}
                if lesson_refs:
                    payload["active_lesson_refs"] = lesson_refs
                return web.json_response(payload)
            if interaction_id and outcome:
                await _update_outcome(interaction_id=interaction_id, outcome=outcome, user_feedback=user_feedback)
                payload = {"status": "updated"}
                if lesson_refs:
                    payload["active_lesson_refs"] = lesson_refs
                return web.json_response(payload)
            return web.json_response({"error": "missing_feedback_fields"}, status=400)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_simple_feedback(request):
        """Phase 3.1.1 — POST /feedback/{interaction_id}"""
        try:
            interaction_id = request.match_info.get("interaction_id", "")
            if not interaction_id:
                return web.json_response({"error": "interaction_id required in path"}, status=400)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
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
            payload = {"status": "recorded", "feedback_id": feedback_id}
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_feedback_evaluate(request):
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            feedback_response = await _feedback_api.evaluate_response(
                session_id=session_id,
                response=data.get("response", ""),
                confidence=data.get("confidence", 0.5),
                gaps=data.get("gaps", []),
                metadata=data.get("metadata"),
            )
            payload = feedback_response.dict()
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = dict(session_info)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_clear_session(request):
        try:
            session_id = request.match_info.get("session_id")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            await _multi_turn_manager.clear_session(session_id)
            payload = {"status": "cleared", "session_id": session_id}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = discovery_response.dict()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_token_budget_recommendations(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            recommendations = await _progressive_disclosure.get_token_budget_recommendations(
                query_type=data.get("query_type", "quick_lookup"),
                context_level=data.get("context_level", "standard"),
            )
            payload = dict(recommendations)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs and isinstance(result, dict):
            result["active_lesson_refs"] = lesson_refs
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
        # Phase 4.2 — update orchestration framework gauges
        try:
            # AgentHQ metrics
            ORCHESTRATION_ACTIVE_SESSIONS.set(len(_AGENT_HQ.sessions))
            ORCHESTRATION_REGISTERED_AGENTS.set(len(_AGENT_HQ.global_agents))
            # Count sessions by state
            from metrics import ORCHESTRATION_SESSIONS_BY_STATE
            state_counts: Dict[str, int] = {}
            for session in _AGENT_HQ.sessions.values():
                state_name = session.state.name if hasattr(session.state, "name") else str(session.state)
                state_counts[state_name] = state_counts.get(state_name, 0) + 1
            for state_name, count in state_counts.items():
                ORCHESTRATION_SESSIONS_BY_STATE.labels(state=state_name).set(count)
            # DelegationAPI metrics
            queue_status = _DELEGATION_API.get_queue_status()
            ORCHESTRATION_PENDING_DELEGATIONS.set(queue_status.get("pending_requests", 0))
            # WorkspaceManager metrics
            ORCHESTRATION_ACTIVE_WORKSPACES.set(len(_WORKSPACE_MANAGER.workspaces))
            from metrics import ORCHESTRATION_WORKSPACES_BY_MODE, ORCHESTRATION_WORKSPACE_DISK_BYTES
            mode_counts: Dict[str, int] = {}
            total_disk = 0
            for ws in _WORKSPACE_MANAGER.workspaces.values():
                mode_name = ws.mode.name if hasattr(ws.mode, "name") else str(ws.mode)
                mode_counts[mode_name] = mode_counts.get(mode_name, 0) + 1
                if ws.path.exists():
                    try:
                        total_disk += sum(f.stat().st_size for f in ws.path.rglob("*") if f.is_file())
                    except (OSError, PermissionError):
                        pass
            for mode_name, count in mode_counts.items():
                ORCHESTRATION_WORKSPACES_BY_MODE.labels(mode=mode_name).set(count)
            ORCHESTRATION_WORKSPACE_DISK_BYTES.set(total_disk)
            # MCPToolInvoker metrics
            tool_report = _MCP_TOOL_INVOKER.get_usage_report()
            from metrics import ORCHESTRATION_TOOLS_RATE_LIMITED
            ORCHESTRATION_TOOLS_RATE_LIMITED.set(tool_report.get("rate_limited_tools", 0))
            ORCHESTRATION_TOOL_PENDING_APPROVALS.set(tool_report.get("pending_approvals", 0))
            # Phase 1.3 — Bottleneck detection metrics
            from metrics import BOTTLENECK_COUNT, BOTTLENECK_AVG_DURATION_MS, BOTTLENECK_P95_DURATION_MS, OPTIMIZATION_RECOMMENDATIONS_PENDING
            bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(min_call_count=5, threshold_ms=50)
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for b in bottlenecks:
                severity_counts[b.severity] += 1
                BOTTLENECK_AVG_DURATION_MS.labels(operation=b.operation).set(b.avg_duration_ms)
                BOTTLENECK_P95_DURATION_MS.labels(operation=b.operation).set(b.p95_duration_ms)
            for severity, count in severity_counts.items():
                BOTTLENECK_COUNT.labels(severity=severity).set(count)
            recommendations = _PERFORMANCE_PROFILER.generate_optimization_recommendations(bottlenecks)
            rec_by_priority: Dict[int, int] = {}
            for r in recommendations:
                rec_by_priority[r.priority] = rec_by_priority.get(r.priority, 0) + 1
            for priority, count in rec_by_priority.items():
                OPTIMIZATION_RECOMMENDATIONS_PENDING.labels(priority=str(priority)).set(count)
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)

            if scope == "all":
                deleted = await cache.clear_all()
                logger.info("cache_invalidation trigger=%s scope=all deleted=%d", trigger, deleted)
                payload = {"status": "ok", "keys_deleted": deleted}
                if lesson_refs:
                    payload["active_lesson_refs"] = lesson_refs
                return web.json_response(payload)
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                stats["active_lesson_refs"] = lesson_refs
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
                    payload = json.load(f)
                    async with _agent_lessons_lock:
                        lesson_registry = await _load_agent_lessons_registry()
                    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
                    if lesson_refs and isinstance(payload, dict):
                        payload["active_lesson_refs"] = lesson_refs
                    return web.json_response(payload)
            if _learning_pipeline:
                stats = await _learning_pipeline.get_statistics()
                async with _agent_lessons_lock:
                    lesson_registry = await _load_agent_lessons_registry()
                lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
                if lesson_refs and isinstance(stats, dict):
                    stats["active_lesson_refs"] = lesson_refs
                return web.json_response(stats)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        payload = {
            "checkpoints": {"total": 0, "last_checkpoint": None},
            "backpressure": {"unprocessed_mb": 0, "paused": False},
            "backpressure_threshold_mb": 100,
            "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0},
        }
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

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
            payload = {"status": "ok", "patterns": len(patterns), "examples": examples_count}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {"status": "ok", "dataset_path": dataset_path_str, "examples": count}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {
                "status": "ok",
                "variant_a": stats_a,
                "variant_b": stats_b,
                "delta": {"avg_rating": delta},
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if proc.returncode == 0:
            MODEL_RELOADS.labels(service=service, status="success").inc()
            payload = {
                "status": "restarted",
                "service": service_unit,
                "duration_seconds": round(duration, 2),
            }
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        else:
            MODEL_RELOADS.labels(service=service, status="failure").inc()
            payload = {
                "status": "failed",
                "service": service_unit,
                "error": stderr.decode("utf-8", errors="replace")[:500],
            }
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload, status=500)

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
        payload = {"services": results}
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

    # ------------------------------------------------------------------
    # Phase 19.2.1/19.2.2 — /hints endpoint (agent-agnostic hint API)
    # ------------------------------------------------------------------

    def _get_remote_agent_status() -> Dict[str, Any]:
        """Return remote agent pool availability and rate-limit status."""
        try:
            stats = _AGENT_POOL_MANAGER.get_pool_stats()
            agents_detail = []
            for agent_id, agent in _AGENT_POOL_MANAGER.agents.items():
                is_rl = agent.is_rate_limited()
                eta_minutes = 0
                if is_rl and agent.last_rate_limit:
                    elapsed = (datetime.now() - agent.last_rate_limit).total_seconds()
                    remaining = max(0, 60 - elapsed)
                    eta_minutes = int(remaining / 60) + (1 if remaining % 60 > 0 else 0)

                agents_detail.append({
                    "agent_id": agent_id,
                    "name": agent.name,
                    "status": agent.status.value,
                    "tier": agent.tier.value,
                    "is_available": agent.is_available(),
                    "is_rate_limited": is_rl,
                    "current_load": agent.current_load,
                    "max_concurrent": agent.max_concurrent,
                    "success_rate": round(agent.success_rate(), 2),
                    "eta_available_minutes": eta_minutes if is_rl else None,
                    "last_rate_limit": agent.last_rate_limit.isoformat() if agent.last_rate_limit else None,
                })

            return {
                "pool_status": "ok",
                "total_agents": stats.total_agents,
                "available_agents": stats.available_agents,
                "free_agents_available": stats.free_agents_available,
                "agents": agents_detail,
            }
        except Exception as exc:
            logger.warning("agent_pool_status_unavailable error=%s", exc)
            return {
                "pool_status": "unavailable",
                "error": str(exc),
                "total_agents": 0,
                "available_agents": 0,
                "free_agents_available": 0,
                "agents": [],
            }

    async def handle_hints(request: web.Request) -> web.Response:
        """POST /hints or GET /hints?q= — return ranked workflow hints for any agent.

        Phase 19.3.2: When format=continue (GET param) or body contains 'fullInput'
        (Continue.dev HTTP context provider), returns [{"name","description","content"}].

        Phase 20.1: Returns agent availability and rate-limit status in metadata.
        """
        try:
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
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
                max_hints = int(body.get("max_hints", 4))
                agent_type = ctx.get("agent_type", "remote") if isinstance(ctx, dict) else "remote"
                include_debug_metadata = bool(body.get("include_debug_metadata") or body.get("debug"))
                # Phase 10.3 — Token-efficient hint delivery
                max_hint_tokens = int(body.get("max_hint_tokens", 0))
                compact_mode = bool(body.get("compact", False))
                # Context-aware token budgeting
                task_phase = body.get("task_phase", "")  # new_phase, continued_work, sub_task, refinement
                post_compaction = bool(body.get("post_compaction", False))
                # Phase 10.4 — Escalation: model requests expanded context
                force_escalation = bool(body.get("escalate", False))
            else:
                is_continue = request.rel_url.query.get("format") == "continue"
                query = request.rel_url.query.get("q", "")
                file_ext = request.rel_url.query.get("context", "")
                max_hints = int(request.rel_url.query.get("max", "4"))
                agent_type = request.rel_url.query.get("agent", "remote")
                include_debug_metadata = request.rel_url.query.get("debug", "0").strip().lower() in {"1", "true", "yes"}
                # Phase 10.3 — Token-efficient hint delivery
                max_hint_tokens = int(request.rel_url.query.get("max_tokens", "0"))
                compact_mode = request.rel_url.query.get("compact", "0").strip().lower() in {"1", "true", "yes"}
                # Context-aware token budgeting
                task_phase = request.rel_url.query.get("task_phase", "")
                post_compaction = request.rel_url.query.get("post_compaction", "0").strip().lower() in {"1", "true", "yes"}
                # Phase 10.4 — Escalation: model requests expanded context
                force_escalation = request.rel_url.query.get("escalate", "0").strip().lower() in {"1", "true", "yes"}

            try:
                import sys as _sys
                from pathlib import Path as _Path
                _hints_dir = _Path(__file__).parent
                if str(_hints_dir) not in _sys.path:
                    _sys.path.insert(0, str(_hints_dir))
                from hints_engine import HintsEngine  # type: ignore[import]
                engine = HintsEngine()
                # Phase 1.3 — Profile hints engine operation
                _hints_start = time.time()
                result = engine.rank_as_dict(
                    query,
                    context=file_ext,
                    max_hints=max_hints,
                    agent_type=agent_type,
                    include_debug_metadata=include_debug_metadata,
                    max_hint_tokens=max_hint_tokens,
                    compact_mode=compact_mode,
                    force_escalation=force_escalation,
                )
                _hints_duration_ms = (time.time() - _hints_start) * 1000
                _PERFORMANCE_PROFILER.record_metric("hints_engine_rank", _hints_duration_ms, {"query_len": len(query), "max_hints": max_hints})
            except Exception as exc:
                logger.warning("hints_engine_unavailable error=%s", exc)
                result = {
                    "hints": [],
                    "generated_at": "",
                    "query": query,
                    "error": f"hints_engine unavailable: {exc}",
                }

            # Phase 20.1 — Attach remote agent status to hint responses
            result["agent_status"] = _get_remote_agent_status()

            # Phase 19.3.2 — Continue.dev HTTP context provider format
            if is_continue:
                hints = result.get("hints", [])
                content_lines = [f"# AI Stack Hints\n\n"]
                for i, h in enumerate(hints, 1):
                    score_pct = f"{h.get('score', 0):.0%}"
                    block = (
                        f"{i}. [{h.get('type', 'hint')}] {h.get('title', '')} ({score_pct})\n"
                        f"   {h.get('snippet', '')[:120]}\n"
                    )
                    if include_debug_metadata and h.get("reason"):
                        block += f"   Reason: {h.get('reason', '')}\n"
                    content_lines.append(block + "\n")
                return web.json_response([{
                    "name": "aq-hints",
                    "description": f"AI Stack workflow hints" + (f" for: {query[:60]}" if query else ""),
                    "content": "".join(content_lines) or "No hints available — run aq-prompt-eval to score registry prompts.",
                    "active_lesson_refs": lesson_refs,
                }])

            # Agent-type-specific augmentation
            if result.get("hints") and agent_type in ("claude", "codex", "qwen", "aider", "gemini"):
                top = result["hints"][0]
                result["inject_prefix"] = top.get("snippet", "")[:150]
            result["active_lesson_refs"] = lesson_refs
            result["feedback_contract"] = {
                "endpoint": "/hints/feedback",
                "required_any_of": ["helpful", "score"],
                "required": ["hint_id"],
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

        payload = {"status": "recorded", "hint_id": hint_id}
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if lesson_refs:
            payload["active_lesson_refs"] = lesson_refs
        return web.json_response(payload)

    async def handle_agent_status(request: web.Request) -> web.Response:
        """GET/POST /agent-status — return remote agent pool availability and rate-limit status.

        Phase 20.1: Provides explicit endpoint for agents to check remote pool status.
        Returns ETA for rate-limited agents and availability counts.
        """
        try:
            detail = request.rel_url.query.get("detail", "0").strip().lower() in {"1", "true", "yes"}
            if request.method == "POST":
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                detail = detail or bool(body.get("detail", False))
                agent_filter = body.get("agent_id", "") or body.get("agent", "")
            else:
                agent_filter = request.rel_url.query.get("agent_id", "") or request.rel_url.query.get("agent", "")

            status_data = _get_remote_agent_status()

            if agent_filter:
                # Return status for specific agent
                matching = [a for a in status_data["agents"] if a["agent_id"] == agent_filter or a["name"].lower() == agent_filter.lower()]
                if not matching:
                    return web.json_response({
                        "error": f"agent not found: {agent_filter}",
                        "available_agents": status_data["available_agents"],
                        "hint": "Use GET /agent-status without filter to see all agents",
                    }, status=404)
                status_data["agents"] = matching
                status_data["filtered"] = True

            if not detail:
                # Compact view — remove verbose fields
                for agent in status_data.get("agents", []):
                    agent.pop("last_rate_limit", None)

            return web.json_response(status_data)
        except Exception as exc:
            logger.error("handle_agent_status error=%s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_workflow_plan(request: web.Request) -> web.Response:
        """Build a structured phase plan with explicit tool assignments."""
        try:
            if request.method == "POST":
                data = await request.json()
                query = (data.get("query") or data.get("prompt") or "").strip()
                include_debug_metadata = bool(data.get("include_debug_metadata") or data.get("debug"))
            else:
                data = {}
                query = (request.rel_url.query.get("q") or "").strip()
                include_debug_metadata = request.rel_url.query.get("debug", "0").strip().lower() in {"1", "true", "yes"}
            if not query:
                return web.json_response({"error": "query required"}, status=400)
            # Phase 1.3 — Profile workflow plan building
            _plan_start = time.time()
            result = _build_workflow_plan(query, include_debug_metadata=include_debug_metadata)
            _plan_duration_ms = (time.time() - _plan_start) * 1000
            _PERFORMANCE_PROFILER.record_metric("workflow_plan_build", _plan_duration_ms, {"query_len": len(query)})
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                result["active_lesson_refs"] = lesson_refs
                metadata = result.get("metadata")
                if isinstance(metadata, dict):
                    metadata["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
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
            result = build_tooling_manifest(
                query,
                tools,
                runtime=str(data.get("runtime") or request.rel_url.query.get("runtime") or "python"),
                max_tools=data.get("max_tools"),
                max_result_chars=data.get("max_result_chars"),
                phases=[
                    {
                        "id": str(phase.get("id", "")).strip(),
                        "tools": _phase_tool_names(phase),
                    }
                    for phase in plan.get("phases", [])
                    if isinstance(phase, dict)
                ],
                tool_security=tool_security,
            )
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                result["active_lesson_refs"] = lesson_refs
                metadata = result.get("metadata")
                if isinstance(metadata, dict):
                    metadata["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_web_research_fetch(request: web.Request) -> web.Response:
        """Bounded polite web fetch -> extract for explicit public URLs."""
        try:
            if not Config.AI_WEB_RESEARCH_ENABLED:
                return web.json_response({"error": "web_research_disabled"}, status=503)

            data = await request.json()
            urls = data.get("urls")
            if not isinstance(urls, list) or not urls:
                return web.json_response({"error": "urls list required"}, status=400)

            selectors = data.get("selectors")
            if selectors is not None and not isinstance(selectors, list):
                return web.json_response({"error": "selectors must be a list"}, status=400)

            max_text_chars = data.get("max_text_chars")
            if max_text_chars is not None:
                max_text_chars = int(max_text_chars or 0)

            result = await fetch_web_research(
                urls=urls,
                selectors=selectors if isinstance(selectors, list) else None,
                max_text_chars=max_text_chars,
            )
            request["audit_metadata"] = {
                "accepted_urls": int((result.get("metrics") or {}).get("accepted_urls", 0) or 0),
                "page_requests": int((result.get("metrics") or {}).get("page_requests", 0) or 0),
                "robots_requests": int((result.get("metrics") or {}).get("robots_requests", 0) or 0),
                "skipped_count": len(result.get("skipped", []) or []),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
        except ValueError as exc:
            return web.json_response({"error": "invalid_request", "detail": str(exc)}, status=400)
        except PermissionError as exc:
            return web.json_response({"error": "policy_blocked", "detail": str(exc)}, status=403)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_browser_research_fetch(request: web.Request) -> web.Response:
        """Bounded browser-assisted fetch -> extract for JS-heavy public URLs."""
        try:
            if not Config.AI_BROWSER_RESEARCH_ENABLED:
                return web.json_response({"error": "browser_research_disabled"}, status=503)

            data = await request.json()
            urls = data.get("urls")
            if not isinstance(urls, list) or not urls:
                return web.json_response({"error": "urls list required"}, status=400)

            selectors = data.get("selectors")
            if selectors is not None and not isinstance(selectors, list):
                return web.json_response({"error": "selectors must be a list"}, status=400)

            max_text_chars = data.get("max_text_chars")
            if max_text_chars is not None:
                max_text_chars = int(max_text_chars or 0)

            result = await fetch_browser_research(
                urls=urls,
                selectors=selectors if isinstance(selectors, list) else None,
                max_text_chars=max_text_chars,
            )
            request["audit_metadata"] = {
                "accepted_urls": int((result.get("metrics") or {}).get("accepted_urls", 0) or 0),
                "browser_requests": int((result.get("metrics") or {}).get("browser_requests", 0) or 0),
                "robots_requests": int((result.get("metrics") or {}).get("robots_requests", 0) or 0),
                "skipped_count": len(result.get("skipped", []) or []),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
        except ValueError as exc:
            return web.json_response({"error": "invalid_request", "detail": str(exc)}, status=400)
        except PermissionError as exc:
            return web.json_response({"error": "policy_blocked", "detail": str(exc)}, status=403)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_curated_research_fetch(request: web.Request) -> web.Response:
        """Run a manifest-backed bounded research workflow over approved explicit public URLs."""
        try:
            if not Config.AI_WEB_RESEARCH_ENABLED:
                return web.json_response({"error": "web_research_disabled"}, status=503)

            data = await request.json()
            workflow = str(data.get("workflow") or "").strip()
            if not workflow:
                return web.json_response({"error": "workflow required"}, status=400)
            inputs = data.get("inputs")
            if inputs is not None and not isinstance(inputs, dict):
                return web.json_response({"error": "inputs must be an object"}, status=400)

            max_text_chars = data.get("max_text_chars")
            if max_text_chars is not None:
                max_text_chars = int(max_text_chars or 0)

            result = await run_curated_research_workflow(
                workflow_slug=workflow,
                inputs=inputs if isinstance(inputs, dict) else None,
                max_text_chars=max_text_chars,
            )
            request["audit_metadata"] = {
                "workflow": workflow,
                "available_workflows": len(list_curated_research_workflows()),
                "selected_sources": len(result.get("selected_sources", []) or []),
                "page_requests": int((((result.get("fetch") or {}).get("metrics") or {}).get("page_requests", 0) or 0)),
                "needs_fallback": len([item for item in (result.get("results") or []) if item.get("status") != "ok"]),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(result, dict):
                result["active_lesson_refs"] = lesson_refs
            return web.json_response(result)
        except KeyError as exc:
            return web.json_response({"error": "unknown_workflow", "detail": str(exc)}, status=404)
        except ValueError as exc:
            return web.json_response({"error": "invalid_request", "detail": str(exc)}, status=400)
        except PermissionError as exc:
            return web.json_response({"error": "policy_blocked", "detail": str(exc)}, status=403)
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
            response_payload = response.json()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(response_payload, dict):
                response_payload["active_lesson_refs"] = lesson_refs
            return web.json_response(response_payload, status=response.status_code)
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
            response_payload = response.json()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs and isinstance(response_payload, dict):
                response_payload["active_lesson_refs"] = lesson_refs
            return web.json_response(response_payload, status=response.status_code)
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                session["active_lesson_refs"] = lesson_refs
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
                async with _agent_lessons_lock:
                    lesson_registry = await _load_agent_lessons_registry()
                lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
                if lesson_refs:
                    payload["active_lesson_refs"] = lesson_refs
                return web.json_response(payload)
            payload = dict(session)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
                reasoning_pattern = sess.get("reasoning_pattern", {})
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
                    "reasoning_pattern": {
                        "selected_pattern": reasoning_pattern.get("selected_pattern", ""),
                        "boost_multiplier": reasoning_pattern.get("boost_multiplier", 1.0),
                    },
                    "orchestration_runtime": sess.get("orchestration_runtime", {}),
                    "created_at": sess.get("created_at"),
                    "updated_at": sess.get("updated_at"),
                })
            items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
            payload = {"sessions": items, "count": len(items)}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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

            payload = {
                "nodes": nodes,
                "edges": edges,
                "roots": roots,
                "count": len(nodes),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {"session_id": new_id, "forked_from": session_id, "status": "created"}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
                    payload = dict(session)
                    async with _agent_lessons_lock:
                        lesson_registry = await _load_agent_lessons_registry()
                    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
                    if lesson_refs:
                        payload["active_lesson_refs"] = lesson_refs
                    return web.json_response(payload)

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
            payload = dict(session)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            response_payload = {
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
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                response_payload["active_lesson_refs"] = lesson_refs

            session_id = str(data.get("session_id", "") or "").strip()
            if session_id:
                now = int(time.time())
                reviewer = str(data.get("reviewer", "") or "codex").strip()[:64] or "codex"
                async with _workflow_sessions_lock:
                    sessions = await _load_workflow_sessions()
                    session = sessions.get(session_id)
                    if session:
                        _ensure_session_runtime_fields(session)
                        orchestration = session.get("orchestration")
                        review_type = _normalize_review_type(data.get("review_type"))
                        artifact_kind = _normalize_artifact_kind(data.get("artifact_kind"), review_type)
                        task_class = _normalize_task_class(data.get("task_class"), session)
                        reviewed_agent = str(
                            data.get("reviewed_agent")
                            or (orchestration.get("requesting_agent") if isinstance(orchestration, dict) else "")
                            or "unknown"
                        ).strip()[:64] or "unknown"
                        reviewed_profile = str(data.get("reviewed_profile") or "").strip()[:64]
                        reviewed_role = _resolve_history_role(
                            session,
                            agent=reviewed_agent,
                            profile=reviewed_profile or task_class,
                            review_type=review_type,
                        )
                        review_snapshot = {
                            "ts": now,
                            "passed": passed,
                            "score": response_payload["score"],
                            "reviewer": reviewer,
                            "review_type": review_type,
                            "artifact_kind": artifact_kind,
                            "task_class": task_class,
                            "reviewed_agent": reviewed_agent,
                            "reviewed_profile": reviewed_profile,
                            "reviewed_role": reviewed_role,
                            "criteria_ratio": round(criteria_ratio, 4),
                            "keyword_ratio": round(keyword_ratio, 4),
                            "criteria_threshold": min_criteria_ratio,
                            "keyword_threshold": min_keyword_ratio,
                            "criteria_total": criteria_total,
                            "keyword_total": keyword_total,
                        }
                        gate = session.get("reviewer_gate", {})
                        if not isinstance(gate, dict):
                            gate = {}
                        history = gate.get("history", [])
                        if not isinstance(history, list):
                            history = []
                        history.append(review_snapshot)
                        gate["required"] = bool(gate.get("required", False))
                        gate["last_review"] = review_snapshot
                        gate["history"] = history[-10:]
                        gate["status"] = "accepted" if passed else "rejected"
                        session["reviewer_gate"] = gate
                        session["updated_at"] = now
                        session.setdefault("trajectory", [])
                        session["trajectory"].append(
                            {
                                "ts": now,
                                "event_type": "review_acceptance",
                                "phase_id": f"phase-{int(session.get('current_phase_index', 0))}",
                                "detail": f"review gate -> {'accepted' if passed else 'rejected'}",
                                "score": response_payload["score"],
                                "review_type": review_type,
                                "artifact_kind": artifact_kind,
                                "task_class": task_class,
                                "reviewed_agent": reviewed_agent,
                                "reviewed_profile": reviewed_profile,
                                "reviewed_role": reviewed_role,
                                "reviewer": reviewer,
                            }
                        )
                        sessions[session_id] = session
                        await _save_workflow_sessions(sessions)
                        async with _agent_evaluations_lock:
                            evaluation_registry = await _load_agent_evaluations_registry()
                            evaluation_registry = _record_agent_review_event(
                                evaluation_registry,
                                agent=reviewed_agent,
                                profile=reviewed_profile or task_class,
                                role=reviewed_role,
                                passed=passed,
                                score=float(response_payload["score"]),
                                reviewer=reviewer,
                                review_type=review_type,
                                task_class=task_class,
                                ts=now,
                            )
                            await _save_agent_evaluations_registry(evaluation_registry)
                        response_payload["session_id"] = session_id
                        response_payload["reviewer_gate"] = gate
                    else:
                        response_payload["session_id"] = session_id
                        response_payload["reviewer_gate_error"] = "session_not_found"

            return web.json_response(response_payload)
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
            orchestration = _coerce_orchestration_context(data)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            session = _build_workflow_run_session(
                query=query,
                data=data,
                selected_blueprint=selected_blueprint,
                orchestration=orchestration,
                lesson_refs=lesson_refs,
            )
            session_id = session["session_id"]
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            if not include_replay:
                payload["trajectory_count"] = len(session.get("trajectory", []))
                payload.pop("trajectory", None)
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_consensus(request: web.Request) -> web.Response:
        """Record a bounded consensus/selection decision for a workflow run."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json()
            selected_candidate_id = str(data.get("selected_candidate_id", "") or "").strip()
            summary = str(data.get("summary", "") or "").strip()[:400]
            decisions = data.get("decisions")
            if not selected_candidate_id:
                return web.json_response({"error": "selected_candidate_id required"}, status=400)
            if not isinstance(decisions, list) or not decisions:
                return web.json_response({"error": "decisions must be a non-empty list"}, status=400)
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)
                try:
                    consensus = _apply_consensus_update(
                        session,
                        selected_candidate_id=selected_candidate_id,
                        decisions=decisions,
                        summary=summary,
                    )
                except ValueError as exc:
                    return web.json_response({"error": str(exc)}, status=400)
                session["team"] = _build_orchestration_team(
                    session.get("orchestration_policy", {}) if isinstance(session.get("orchestration_policy"), dict) else {},
                    session.get("orchestration", {}) if isinstance(session.get("orchestration"), dict) else {},
                    consensus,
                )
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
                async with _agent_evaluations_lock:
                    evaluation_registry = await _load_agent_evaluations_registry()
                    evaluation_registry = _record_agent_consensus_event(
                        evaluation_registry,
                        agent=str(consensus.get("selected_agent", "") or "unknown"),
                        lane=str(consensus.get("selected_lane", "") or "unknown"),
                        role=str(consensus.get("selected_role", "") or "unknown"),
                        selected_candidate_id=selected_candidate_id,
                        summary=summary,
                        ts=int(session.get("updated_at") or time.time()),
                    )
                    await _save_agent_evaluations_registry(evaluation_registry)
            return web.json_response({"status": "ok", "session_id": session_id, "consensus": consensus})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_arbiter(request: web.Request) -> web.Response:
        """Record a bounded arbiter decision for a workflow run in arbiter-review mode."""
        try:
            session_id = request.match_info.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)
            data = await request.json()
            selected_candidate_id = str(data.get("selected_candidate_id", "") or "").strip()
            arbiter = str(data.get("arbiter", "") or "").strip()
            verdict = str(data.get("verdict", "") or "").strip().lower()
            rationale = str(data.get("rationale", "") or "").strip()[:400]
            summary = str(data.get("summary", "") or "").strip()[:400]
            supporting_decisions = data.get("supporting_decisions")
            if not selected_candidate_id:
                return web.json_response({"error": "selected_candidate_id required"}, status=400)
            if not arbiter:
                return web.json_response({"error": "arbiter required"}, status=400)
            if verdict not in {"accept", "reject", "prefer"}:
                return web.json_response({"error": "verdict must be one of: accept, reject, prefer"}, status=400)
            if not rationale:
                return web.json_response({"error": "rationale required"}, status=400)
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
                if not session:
                    return web.json_response({"error": "session not found"}, status=404)
                _ensure_session_runtime_fields(session)
                try:
                    consensus = _apply_arbiter_update(
                        session,
                        selected_candidate_id=selected_candidate_id,
                        arbiter=arbiter,
                        verdict=verdict,
                        rationale=rationale,
                        summary=summary,
                        supporting_decisions=supporting_decisions if isinstance(supporting_decisions, list) else [],
                    )
                except ValueError as exc:
                    return web.json_response({"error": str(exc)}, status=400)
                session["team"] = _build_orchestration_team(
                    session.get("orchestration_policy", {}) if isinstance(session.get("orchestration_policy"), dict) else {},
                    session.get("orchestration", {}) if isinstance(session.get("orchestration"), dict) else {},
                    consensus,
                )
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
                if verdict in {"accept", "prefer"}:
                    async with _agent_evaluations_lock:
                        evaluation_registry = await _load_agent_evaluations_registry()
                        evaluation_registry = _record_agent_consensus_event(
                            evaluation_registry,
                            agent=str(consensus.get("selected_agent", "") or "unknown"),
                            lane=str(consensus.get("selected_lane", "") or "unknown"),
                            role=str(consensus.get("selected_role", "") or "unknown"),
                            selected_candidate_id=selected_candidate_id,
                            summary=summary or rationale,
                            ts=int(session.get("updated_at") or time.time()),
                        )
                        await _save_agent_evaluations_registry(evaluation_registry)
            return web.json_response({"status": "ok", "session_id": session_id, "consensus": consensus})
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_team(request: web.Request) -> web.Response:
        """Return the dynamic team assignment for a workflow run."""
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
                    "team": session.get("team", {}),
                    "consensus_mode": ((session.get("consensus") or {}) if isinstance(session.get("consensus"), dict) else {}).get("consensus_mode", ""),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_team_detailed(request: web.Request) -> web.Response:
        """Return detailed team formation with scoring breakdown and historical bias."""
        try:
            session_id = request.match_info.get("session_id", "")
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)

            _ensure_session_runtime_fields(session)
            consensus = session.get("consensus", {})
            team = session.get("team", {})
            phase_state = session.get("phase_state", [])
            current_idx = int(session.get("current_phase_index", 0))
            current_phase = None
            if 0 <= current_idx < len(phase_state):
                current_phase = phase_state[current_idx].get("id")

            # Extract candidates with full scoring breakdown
            candidates = consensus.get("candidates", [])
            selected_id = consensus.get("selected_candidate_id", "")

            # Build detailed team view
            team_details = {
                "session_id": session_id,
                "objective": session.get("objective", ""),
                "status": session.get("status", "unknown"),
                "current_phase": current_phase,
                "current_phase_index": current_idx,
                "safety_mode": session.get("safety_mode", "plan-readonly"),
                "budget": session.get("budget", {}),
                "usage": session.get("usage", {}),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at"),
                "reasoning_pattern": session.get("reasoning_pattern", {}),
                "consensus_mode": consensus.get("consensus_mode", ""),
                "selection_strategy": team.get("selection_strategy", ""),
                "team_members": team.get("members", []),
                "active_slots": team.get("active_slots", []),
                "required_slots": team.get("required_slots", []),
                "optional_slot_capacity": team.get("optional_slot_capacity", 0),
                "deferred_slots": team.get("deferred_slots", []),
                "deferred_members": team.get("deferred_members", []),
                "orchestration_runtime": session.get("orchestration_runtime", {}),
                "candidates": candidates,
                "selected_candidate_id": selected_id,
                "formation_mode": team.get("formation_mode", ""),
            }

            return web.json_response(team_details)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_run_arbiter_history(request: web.Request) -> web.Response:
        """Return arbiter decision history for a workflow run."""
        try:
            session_id = request.match_info.get("session_id", "")
            limit = int(request.rel_url.query.get("limit", "10"))
            limit = max(1, min(50, limit))

            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)

            consensus = session.get("consensus", {})
            arbiter_state = consensus.get("arbiter", {})

            if consensus.get("consensus_mode") != "arbiter-review":
                return web.json_response({
                    "session_id": session_id,
                    "arbiter_active": False,
                    "history": [],
                    "message": "arbiter mode not active"
                })

            history = arbiter_state.get("history", [])[-limit:]

            return web.json_response({
                "session_id": session_id,
                "arbiter_active": True,
                "arbiter": arbiter_state.get("arbiter", ""),
                "current_status": arbiter_state.get("status", ""),
                "history": history,
                "history_count": len(arbiter_state.get("history", []))
            })
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
            payload = {"session_id": session_id, "safety_mode": target_mode}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {
                "session_id": session_id,
                "isolation": session.get("isolation", {}),
                "resolved_profile": _resolve_isolation_profile(session),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {
                "session_id": session_id,
                "isolation": session.get("isolation", {}),
                "resolved_profile": _resolve_isolation_profile(session),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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

                event_ts = int(time.time())
                session["trajectory"].append(
                    {
                        "ts": event_ts,
                        "event_type": event_type,
                        "phase_id": phase_id,
                        "risk_class": risk_class,
                        "approved": approved,
                        "token_delta": token_delta,
                        "tool_call_delta": tool_call_delta,
                        "detail": detail,
                    }
                )
                session["updated_at"] = event_ts
                sessions[session_id] = session
                await _save_workflow_sessions(sessions)
                consensus = session.get("consensus") if isinstance(session.get("consensus"), dict) else {}
                runtime_agent = str(consensus.get("selected_agent", "") or "").strip()
                runtime_profile = str(consensus.get("selected_lane", "") or "").strip()
                runtime_role = str(consensus.get("selected_role", "") or "").strip()
                if runtime_agent and runtime_profile:
                    async with _agent_evaluations_lock:
                        evaluation_registry = await _load_agent_evaluations_registry()
                        evaluation_registry = _record_agent_runtime_event(
                            evaluation_registry,
                            agent=runtime_agent,
                            profile=runtime_profile,
                            role=runtime_role,
                            event_type=event_type,
                            risk_class=risk_class,
                            approved=approved,
                            token_delta=token_delta,
                            tool_call_delta=tool_call_delta,
                            detail=detail,
                            ts=event_ts,
                        )
                        await _save_agent_evaluations_registry(evaluation_registry)

            payload = {
                "session_id": session_id,
                "usage": session.get("usage", {}),
                "budget": session.get("budget", {}),
                "trajectory_count": len(session.get("trajectory", [])),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = {
                "session_id": session_id,
                "count": len(events),
                "events": events,
                "usage": session.get("usage", {}),
                "budget": session.get("budget", {}),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_workflow_blueprints(_request: web.Request) -> web.Response:
        """Return curated MCP workflow blueprints for common coding-agent tasks."""
        try:
            parsed = _load_and_validate_workflow_blueprints()
            items = parsed.get("blueprints", [])
            errors = parsed.get("errors", [])
            payload = {
                "blueprints": items,
                "count": len(items),
                "source": parsed.get("source", ""),
                "valid": len(errors) == 0,
                "errors": errors,
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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

    async def handle_ai_coordinator_status(_request: web.Request) -> web.Response:
        """Expose declarative coordinator runtime lanes and switchboard-backed readiness."""
        try:
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            runtimes = list((registry.get("runtimes", {}) or {}).values())
            swb_state = await _switchboard_ai_coordinator_state()
            remote_aliases = swb_state.get("remote_aliases", {})
            remote_configured = bool(swb_state.get("remote_configured", False))
            shared_skills = await _aidb_shared_skills_catalog(limit=10)
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            report_summary = _load_aq_report_status_summary()
            for runtime in runtimes:
                runtime_id = str(runtime.get("runtime_id", "")).strip()
                runtime = _apply_remote_runtime_status(runtime, runtime_id, remote_aliases, remote_configured)
            runtimes.sort(key=lambda item: str(item.get("runtime_id", "")))
            return web.json_response(
                {
                    "status": "ok",
                    "service": "ai-coordinator",
                    "switchboard_url": Config.SWITCHBOARD_URL,
                    "remote_configured": remote_configured,
                    "remote_aliases": remote_aliases,
                    "shared_skill_registry": {
                        "available": shared_skills.get("available", False),
                        "total": int(shared_skills.get("total", 0) or 0),
                        "skills": shared_skills.get("skills", []),
                        "truncated": bool(shared_skills.get("truncated", False)),
                    },
                    "agent_lessons": {
                        "available": lesson_registry.get("available", False),
                        "counts": lesson_registry.get("counts", {}),
                        "active_lessons": lesson_registry.get("active_lessons", []),
                    },
                    "report_summary": report_summary,
                    "provider_health": _provider_health_summary(),
                    "domain_disclosure": _get_domain_disclosure_summary(),
                    "active_lesson_refs": lesson_refs,
                    "runtimes": runtimes,
                    "count": len(runtimes),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_lessons(_request: web.Request) -> web.Response:
        """Expose the persistent agent-lesson registry."""
        try:
            async with _agent_lessons_lock:
                registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(registry, limit=2)
            return web.json_response(
                {
                    "status": "ok",
                    "service": "ai-coordinator",
                    "agent_lessons": registry,
                    "active_lesson_refs": lesson_refs,
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_lessons_review(request: web.Request) -> web.Response:
        """Update review state for a persisted agent lesson."""
        try:
            data = await request.json()
            requested_key = str(data.get("lesson_key") or "").strip()
            requested_state = str(data.get("state") or "").strip().lower()
            reviewer = str(data.get("reviewer") or "codex").strip()
            comment = str(data.get("comment") or "").strip()
            allowed_states = {"pending_review", "promoted", "avoided", "rejected"}
            if requested_state not in allowed_states:
                return web.json_response({"error": "state must be one of pending_review, promoted, avoided, rejected"}, status=400)
            async with _agent_lessons_lock:
                registry = await _load_agent_lessons_registry()
                entries = [item for item in (registry.get("entries") or []) if isinstance(item, dict)]
                target = None
                for item in entries:
                    lesson_key = str(item.get("lesson_key", "") or "").strip()
                    if requested_key and lesson_key == requested_key:
                        target = item
                        break
                if target is None:
                    return web.json_response({"error": "lesson not found"}, status=404)
                stamp = datetime.utcnow().isoformat() + "Z"
                target["state"] = requested_state
                target["review"] = {
                    "reviewer": reviewer[:64],
                    "comment": comment[:240],
                    "reviewed_at": stamp,
                }
                target["updated_at"] = stamp
                registry["entries"] = entries
                await _save_agent_lessons_registry(registry)
                registry = await _load_agent_lessons_registry()
                lesson_refs = _active_lesson_refs(registry, limit=2)
            return web.json_response(
                {
                    "status": "ok",
                    "service": "ai-coordinator",
                    "agent_lessons": registry,
                    "reviewed_lesson": target,
                    "active_lesson_refs": lesson_refs,
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_evaluations(_request: web.Request) -> web.Response:
        """Expose longitudinal agent evaluation and selection feedback."""
        try:
            async with _agent_evaluations_lock:
                registry = await _load_agent_evaluations_registry()
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            return web.json_response(
                {
                    "status": "ok",
                    "service": "ai-coordinator",
                    "agent_evaluations": registry,
                    "active_lesson_refs": lesson_refs,
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_evaluation_trends(_request: web.Request) -> web.Response:
        """Expose agent evaluation trends over time for operator analysis."""
        try:
            async with _agent_evaluations_lock:
                registry = await _load_agent_evaluations_registry()

            agents = registry.get("agents", {})
            trends = []

            for agent_name, agent_data in agents.items():
                profiles = agent_data.get("profiles", {})
                roles = agent_data.get("roles", {})
                totals = agent_data.get("totals", {})

                trends.append({
                    "agent": agent_name,
                    "total_review_events": totals.get("review_events", 0),
                    "total_consensus_selected": totals.get("consensus_selected", 0),
                    "total_runtime_events": totals.get("runtime_events", 0),
                    "average_review_score": totals.get("average_review_score", 0.0),
                    "average_runtime_score": totals.get("average_runtime_score", 0.0),
                    "profile_count": len(profiles),
                    "role_count": len(roles),
                    "last_event_at": agent_data.get("last_event_at"),
                    "profiles": {
                        profile_name: {
                            "review_events": profile_data.get("review_events", 0),
                            "consensus_selected": profile_data.get("consensus_selected", 0),
                            "runtime_events": profile_data.get("runtime_events", 0),
                            "average_review_score": profile_data.get("average_review_score", 0.0),
                            "average_runtime_score": profile_data.get("average_runtime_score", 0.0),
                        }
                        for profile_name, profile_data in profiles.items()
                    },
                    "roles": {
                        role_name: {
                            "review_events": role_data.get("review_events", 0),
                            "consensus_selected": role_data.get("consensus_selected", 0),
                            "runtime_events": role_data.get("runtime_events", 0),
                            "average_review_score": role_data.get("average_review_score", 0.0),
                            "average_runtime_score": role_data.get("average_runtime_score", 0.0),
                        }
                        for role_name, role_data in roles.items()
                    },
                })

            # Sort by total activity
            trends.sort(key=lambda x: x["total_review_events"] + x["total_consensus_selected"], reverse=True)

            return web.json_response({
                "status": "ok",
                "agent_count": len(trends),
                "trends": trends,
                "summary": registry.get("summary", {}),
                "recent_events": registry.get("recent_events", [])[-10:]
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_skills(request: web.Request) -> web.Response:
        """Expose the approved shared skill catalog for local and delegated runtimes."""
        try:
            limit_raw = request.query.get("limit", "25")
            try:
                limit = max(1, min(100, int(limit_raw)))
            except ValueError:
                limit = 25
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            payload = await _aidb_shared_skills_catalog(limit=limit)
            return web.json_response(
                {
                    "status": "ok",
                    "service": "ai-coordinator",
                    "shared_skill_registry": payload,
                    "active_lesson_refs": lesson_refs,
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_skill_usage_stats(_request: web.Request) -> web.Response:
        """
        GET /control/skills/usage — Get skill usage statistics.

        Batch 5.2: Skill Usage Tracking
        """
        try:
            stats = _get_skill_usage_stats()
            return web.json_response({
                "status": "ok",
                "service": "skill_usage_tracker",
                "usage_stats": stats,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_skill_recommendations(request: web.Request) -> web.Response:
        """
        GET /control/skills/recommendations — Get skill recommendations for an agent.

        Query params:
            agent: Agent/profile name
            task_type: Optional task type for context-aware recommendations

        Batch 5.2: Skill Recommendation Engine
        """
        try:
            agent = str(request.query.get("agent", "")).strip()
            task_type = str(request.query.get("task_type", "")).strip() or None

            if not agent:
                return web.json_response({"error": "agent parameter required"}, status=400)

            recommendations = _get_skill_recommendation(agent, task_type)

            return web.json_response({
                "status": "ok",
                "service": "skill_usage_tracker",
                "agent": agent,
                "task_type": task_type,
                "recommended_skills": recommendations,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_autoresearch_status(_request: web.Request) -> web.Response:
        """Get autoresearch experiment status and summary."""
        try:
            import sys
            autoresearch_path = Path(__file__).parent.parent.parent / "autoresearch"
            if str(autoresearch_path) not in sys.path:
                sys.path.insert(0, str(autoresearch_path))
            from autoresearch import ExperimentLedger
            ledger = ExperimentLedger()
            summary = ledger.get_experiment_summary()
            accepted = ledger.get_accepted_experiments(limit=5)
            return web.json_response({
                "status": "ok",
                "service": "autoresearch",
                "summary": summary,
                "recent_accepted": accepted,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_autoresearch_run(request: web.Request) -> web.Response:
        """Run autoresearch optimization experiments."""
        try:
            data = await request.json() if request.can_read_body else {}
            chat_variants = int(data.get("chat_variants", 3))
            embed_variants = int(data.get("embed_variants", 3))

            import sys
            autoresearch_path = Path(__file__).parent.parent.parent / "autoresearch"
            if str(autoresearch_path) not in sys.path:
                sys.path.insert(0, str(autoresearch_path))
            from local_model_optimizer import run_full_optimization

            result = await run_full_optimization(chat_variants, embed_variants)
            return web.json_response({
                "status": "ok",
                "service": "autoresearch",
                "result": result,
            })
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_prsi_pending(_request: web.Request) -> web.Response:
        """
        GET /control/prsi/pending — Fast read of pending PRSI actions from queue file.

        Does NOT shell out to aq-report (which is slow). Reads the queue JSON
        directly and returns only actions in a pending/awaiting-approval state.
        Intended for local model context injection and MCP tool calls.
        """
        queue_path = Path("/var/lib/nixos-ai-stack/prsi/action-queue.json")
        try:
            if not queue_path.exists():
                return web.json_response({
                    "status": "ok",
                    "pending": [],
                    "count": 0,
                    "queue_exists": False,
                })

            with open(queue_path) as f:
                queue = json.load(f)

            terminal_states = {"approved", "rejected", "executed", "completed",
                               "failed", "counterfactual_queued"}
            all_actions = queue.get("actions", [])
            pending = [
                {
                    "id": a.get("id", ""),
                    "type": a.get("type", ""),
                    "risk_level": a.get("risk_level", ""),
                    "state": a.get("state", ""),
                    "summary": str(a.get("action_detail", {}).get("summary", ""))[:200],
                    "created_at": a.get("created_at", ""),
                }
                for a in all_actions
                if a.get("state") not in terminal_states
            ]
            state_counts = {}
            for a in all_actions:
                s = a.get("state", "unknown")
                state_counts[s] = state_counts.get(s, 0) + 1

            return web.json_response({
                "status": "ok",
                "pending": pending,
                "count": len(pending),
                "state_counts": state_counts,
                "triage_cmd": "python3 scripts/automation/prsi-orchestrator.py list",
                "approve_cmd": "python3 scripts/automation/prsi-orchestrator.py approve --id <id> --by <name>",
                "execute_cmd": "python3 scripts/automation/prsi-orchestrator.py execute --limit 1",
            })
        except json.JSONDecodeError as exc:
            return web.json_response({"status": "error", "error": f"malformed queue JSON: {exc}"}, status=500)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_prsi_actions_list(_request: web.Request) -> web.Response:
        """
        GET /control/prsi/actions — List available PRSI optimization actions.

        Calls aq-report --format=json and returns structured_actions.
        """
        try:
            # Path from ai-stack/mcp-servers/hybrid-coordinator -> repo root
            repo_root = Path(__file__).parent.parent.parent.parent
            scripts_dir = repo_root / "scripts/ai"
            aq_report_path = scripts_dir / "aq-report"

            if not aq_report_path.exists():
                return web.json_response({
                    "status": "error",
                    "error": "aq-report script not found",
                    "path": str(aq_report_path)
                }, status=404)

            # Run aq-report to get structured actions
            # Use the python interpreter from the current process
            result = subprocess.run(
                [sys.executable, str(aq_report_path), "--format=json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return web.json_response({
                    "status": "error",
                    "error": "aq-report failed",
                    "stderr": result.stderr[:500]
                }, status=500)

            try:
                report_data = json.loads(result.stdout)
                actions = report_data.get("structured_actions", [])

                return web.json_response({
                    "status": "ok",
                    "service": "prsi",
                    "actions": actions,
                    "action_count": len(actions),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except json.JSONDecodeError as exc:
                return web.json_response({
                    "status": "error",
                    "error": "invalid JSON from aq-report",
                    "detail": str(exc)
                }, status=500)

        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_prsi_action_execute(request: web.Request) -> web.Response:
        """
        POST /control/prsi/actions/execute — Execute a PRSI optimization action.

        Body:
            {
                "action_id": "routing.01",  # Optional - defaults to running aq-optimizer
                "dry_run": true,            # Optional - defaults to true
                "action_type": "routing",   # Optional: routing, knowledge, maintenance
                "params": {}                # Optional: action-specific parameters
            }
        """
        try:
            data = await request.json() if request.can_read_body else {}
            dry_run = bool(data.get("dry_run", True))
            action_type = str(data.get("action_type", "")).strip()

            repo_root = Path(__file__).parent.parent.parent.parent
            scripts_dir = repo_root / "scripts/ai"

            # If no specific action type, run aq-optimizer
            if not action_type:
                aq_optimizer_path = scripts_dir / "aq-optimizer"
                if not aq_optimizer_path.exists():
                    return web.json_response({
                        "status": "error",
                        "error": "aq-optimizer script not found"
                    }, status=404)

                cmd = [sys.executable, str(aq_optimizer_path)]
                if dry_run:
                    cmd.append("--dry-run")
                cmd.append("--output-json")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                return web.json_response({
                    "status": "ok" if result.returncode == 0 else "failed",
                    "service": "prsi",
                    "tool": "aq-optimizer",
                    "dry_run": dry_run,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            # Handle gap remediation
            elif action_type == "gap_remediation":
                aq_gap_path = scripts_dir / "aq-gap-auto-remediate"
                if not aq_gap_path.exists():
                    return web.json_response({
                        "status": "error",
                        "error": "aq-gap-auto-remediate script not found"
                    }, status=404)

                cmd = [sys.executable, str(aq_gap_path)]
                if dry_run:
                    cmd.append("--dry-run")
                cmd.extend(["--limit", "5"])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                return web.json_response({
                    "status": "ok" if result.returncode == 0 else "failed",
                    "service": "prsi",
                    "tool": "aq-gap-auto-remediate",
                    "dry_run": dry_run,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            else:
                return web.json_response({
                    "status": "error",
                    "error": f"unknown action_type: {action_type}",
                    "supported_types": ["routing", "knowledge", "maintenance", "gap_remediation"]
                }, status=400)

        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_ai_coordinator_delegate(request: web.Request) -> web.Response:
        """Run a bounded delegated task through the selected ai-coordinator lane."""
        try:
            data = await request.json()
            task = str(data.get("task") or data.get("query") or "").strip()
            if not task:
                return web.json_response({"error": "task required"}, status=400)
            orchestration = _coerce_orchestration_context(data)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)

            requested_profile = str(data.get("profile") or "").strip().lower()
            prefer_local = bool(data.get("prefer_local", True))

            # Phase 9.3 — Use complexity routing for auto-selection
            routing_decision = _ai_coordinator_route_by_complexity(task, requested_profile, prefer_local)
            selected_profile = routing_decision["recommended_profile"]
            selected_runtime_id = _ai_coordinator_default_runtime_id_for_profile(selected_profile)

            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = (registry.get("runtimes", {}) or {}).get(selected_runtime_id)
            if not isinstance(runtime, dict):
                return web.json_response({"error": "runtime not found"}, status=404)

            swb_state = await _switchboard_ai_coordinator_state()
            remote_aliases = swb_state.get("remote_aliases", {})
            remote_configured = bool(swb_state.get("remote_configured", False))
            runtime = _apply_remote_runtime_status(runtime, selected_runtime_id, remote_aliases, remote_configured)

            status = str(runtime.get("status", "unknown")).strip().lower()
            if status not in {"ready", "degraded"}:
                # Phase 20.2: Instead of immediately failing, try failover chain
                logger.warning(
                    "delegation_failover: runtime %s unavailable (status=%s), attempting failover",
                    selected_runtime_id,
                    status,
                )

                # Build fallback chain based on task type
                fallback_chain = _build_delegation_fallback_chain(
                    task,
                    requested_profile,
                    prefer_local,
                )

                # Find next available target
                next_target = _select_next_available_delegation_target(
                    fallback_chain,
                    exclude_profiles={selected_profile},
                )

                if next_target:
                    logger.info(
                        "delegation_failover: selected fallback profile=%s runtime=%s reason='%s'",
                        next_target["profile"],
                        next_target["runtime_id"],
                        next_target["reason"],
                    )
                    # Update selected profile and runtime
                    selected_profile = next_target["profile"]
                    selected_runtime_id = next_target["runtime_id"]

                    # Reload runtime with new profile
                    async with _runtime_registry_lock:
                        registry = await _load_runtime_registry()
                        runtime = (registry.get("runtimes", {}) or {}).get(selected_runtime_id)
                    if not isinstance(runtime, dict):
                        return web.json_response(
                            {"error": "runtime not found after failover", "runtime_id": selected_runtime_id},
                            status=404,
                        )

                    # Re-check runtime status
                    swb_state = await _switchboard_ai_coordinator_state()
                    remote_aliases = swb_state.get("remote_aliases", {})
                    remote_configured = bool(swb_state.get("remote_configured", False))
                    runtime = _apply_remote_runtime_status(runtime, selected_runtime_id, remote_aliases, remote_configured)
                    status = str(runtime.get("status", "unknown")).strip().lower()

                    if status not in {"ready", "degraded"}:
                        # Even failover target is unavailable
                        return web.json_response(
                            {
                                "error": "runtime_unavailable_after_failover",
                                "requested_runtime": selected_runtime_id,
                                "failed_over_to": next_target,
                                "status": status,
                                "hint": "All delegation targets are currently unavailable. Retry later or use local execution.",
                            },
                            status=503,
                        )
                else:
                    # No failover targets available
                    return web.json_response(
                        {
                            "error": "runtime_unavailable_no_failover",
                            "runtime_id": selected_runtime_id,
                            "status": status,
                            "hint": "No alternative delegation targets available. Retry later or use local execution.",
                        },
                        status=503,
                    )

            messages = data.get("messages")
            if not isinstance(messages, list) or not messages:
                system_prompt = str(data.get("system_prompt") or "").strip()
                context = data.get("context") if isinstance(data.get("context"), dict) else None
                messages = _ai_coordinator_build_messages(
                    task,
                    system_prompt=system_prompt,
                    context=context,
                    profile=selected_profile,
                )
            progressive_context, progressive_context_meta = await _apply_progressive_context(
                task,
                messages,
                context=data.get("context") if isinstance(data.get("context"), dict) else None,
                profile_name=selected_profile,
                context_budget=int(data.get("max_tokens") or 0),
            )
            messages = progressive_context
            messages, prompt_optimization = _optimize_delegated_messages(messages, selected_profile)

            payload: Dict[str, Any] = {
                "messages": messages,
                "stream": False,
            }
            if "model" in data:
                payload["model"] = str(data.get("model") or "").strip()
            if "tools" in data and isinstance(data.get("tools"), list):
                payload["tools"] = data.get("tools")
            if "tool_choice" in data:
                payload["tool_choice"] = data.get("tool_choice")
            if "max_tokens" in data:
                payload["max_tokens"] = int(data.get("max_tokens") or 0)
            if "temperature" in data:
                payload["temperature"] = float(data.get("temperature"))

            timeout_s = float(data.get("timeout_s") or 60.0)
            finalization_applied = False
            finalization_status_code = None
            pool_agent: Optional[RemoteAgent] = None
            pool_agent_acquired = False
            pool_quality_score = 0.0
            request_started_at = time.perf_counter()

            # ── Local subprocess agent spawning ──────────────────────────────
            # For local runtimes, spawn actual subprocess agents instead of
            # just proxying HTTP to the switchboard. This enables independent
            # agent processes with their own tool sets, system prompts, and
            # state tracking.
            def _is_local_runtime(runtime_id: str) -> bool:
                return str(runtime_id or "").startswith("local-")

            async def _spawn_local_agent(
                role: str, task_text: str, system_prompt: str,
                max_tokens: int, temperature: float, timeout_sec: float,
            ) -> web.Response:
                """Spawn a local agent subprocess and wait for result."""
                import uuid as _uuid
                agent_id = str(_uuid.uuid4())[:8]
                state_dir = Path(os.environ.get("AGENT_STATE_DIR", "/tmp/agent-spawner"))
                state_dir.mkdir(parents=True, exist_ok=True)
                agent_state_file = state_dir / f"agent-{agent_id}.json"

                # Build agent code that calls switchboard for tool-augmented execution
                agent_code = '''
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
    state = {"id": AGENT_ID, "role": AGENT_ROLE,
             "status": "running", "started_at": time.time(), "tool_calls": 0}
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
                headers={"X-AI-Profile": _profile_for_role(os.environ["AGENT_ROLE"]),
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
                env = os.environ.copy()
                env.update({
                    "AGENT_ID": agent_id,
                    "AGENT_ROLE": role,
                    "AGENT_TASK": task_text,
                    "AGENT_SYSTEM_PROMPT": system_prompt,
                    "AGENT_STATE_FILE": str(agent_state_file),
                    "AGENT_MAX_TOKENS": str(max_tokens),
                    "AGENT_TEMPERATURE": str(temperature),
                    "AGENT_TIMEOUT": str(timeout_sec),
                    "SWITCHBOARD_URL": Config.SWITCHBOARD_URL,
                    "PYTHONUNBUFFERED": "1",
                })

                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-c", agent_code,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout_sec,
                    )
                except asyncio.TimeoutError:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    return web.json_response({
                        "error": "local_agent_timeout",
                        "agent_id": agent_id,
                        "timeout_s": timeout_sec,
                    }, status=504)

                if proc.returncode != 0:
                    error_msg = stderr.decode(errors="replace")[:500] if stderr else "unknown"
                    return web.json_response({
                        "error": "local_agent_failed",
                        "agent_id": agent_id,
                        "stderr": error_msg,
                    }, status=500)

                try:
                    result = json.loads(stdout.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    result = {"ok": False, "error": f"parse error: {stdout.decode(errors='replace')[:200]}"}

                if not result.get("ok"):
                    return web.json_response({
                        "error": result.get("error", "unknown"),
                        "agent_id": agent_id,
                    }, status=500)

                # Return in the same format as switchboard responses
                return web.json_response({
                    "id": f"agent-{agent_id}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": f"local-{role}",
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": result.get("content", "")},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "agent_metadata": {
                        "agent_id": agent_id,
                        "role": role,
                        "execution_mode": "local_subprocess",
                        "state_file": str(agent_state_file),
                    },
                })

            # If local runtime, spawn subprocess agent instead of HTTP proxy
            if _is_local_runtime(selected_runtime_id):
                # Determine agent role from profile
                role_map = {
                    "default": "coordinator",
                    "local-tool-calling": "coder",
                }
                agent_role = role_map.get(selected_profile, "coordinator")

                # Extract system prompt from messages
                system_prompt = ""
                user_task = task
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                    elif isinstance(msg, dict) and msg.get("role") == "user":
                        user_task = msg.get("content", task)

                local_response = await _spawn_local_agent(
                    role=agent_role,
                    task_text=user_task,
                    system_prompt=system_prompt or f"You are a {agent_role} agent. Execute the task using available tools.",
                    max_tokens=int(data.get("max_tokens", 4096)),
                    temperature=float(data.get("temperature", 0.3)),
                    timeout_sec=timeout_s,
                )
                return local_response

            if "model" not in payload and _remote_profile_uses_agent_pool(selected_profile):
                pool_agent = _select_agent_pool_candidate(
                    selected_profile,
                    min_context_window=int(payload.get("max_tokens") or 0),
                )
                if pool_agent and _AGENT_POOL_MANAGER.acquire_agent(pool_agent.agent_id):
                    pool_agent_acquired = True
                    payload["model"] = pool_agent.model_id

            async def _post_delegate(profile_name: str, delegate_payload: Optional[Dict[str, Any]] = None) -> httpx.Response:
                local_profiles = {"default", "local-tool-calling"}
                headers = {
                    "Content-Type": "application/json",
                    "X-AI-Profile": "continue-local" if profile_name == "default" else profile_name,
                }
                if profile_name in local_profiles:
                    headers["X-AI-Route"] = "local"
                else:
                    headers["X-AI-Route"] = "remote"
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    return await client.post(
                        f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                        headers=headers,
                        json=delegate_payload or payload,
                    )

            effective_profile = selected_profile
            effective_runtime_id = selected_runtime_id
            fallback_applied = False
            local_fallback_applied = False
            fallback_reason = ""
            failover_chain_used = False
            excluded_profiles = set()

            response = await _post_delegate(effective_profile)
            initial_response = response
            initial_body = response.json()

            # Phase 20.2: Enhanced failover chain for 402/429 errors
            if response.status_code in {402, 429}:
                # Mark agent as rate-limited if applicable
                if pool_agent:
                    _AGENT_POOL_MANAGER.mark_rate_limited(pool_agent.agent_id)
                    if pool_agent_acquired:
                        _AGENT_POOL_MANAGER.release_agent(pool_agent.agent_id, success=False, latency_ms=0.0, quality_score=0.0)
                        pool_agent_acquired = False

                # Add failed profile to exclusion list
                excluded_profiles.add(effective_profile)

                # Build and use failover chain
                failover_chain = _build_delegation_fallback_chain(
                    task,
                    requested_profile,
                    prefer_local,
                )

                next_target = _select_next_available_delegation_target(
                    failover_chain,
                    exclude_profiles=excluded_profiles,
                )

                if next_target:
                    failover_chain_used = True
                    effective_profile = next_target["profile"]
                    effective_runtime_id = next_target["runtime_id"]
                    fallback_applied = True
                    fallback_reason = f"failover chain: {response.status_code} on {selected_profile}, fell back to {effective_profile} ({next_target['reason']})"

                    logger.info(
                        "delegation_failover_chain: HTTP %d on profile=%s, failing over to profile=%s runtime=%s",
                        response.status_code,
                        selected_profile,
                        effective_profile,
                        effective_runtime_id,
                    )

                    # Select new pool agent if needed
                    if "model" not in data:
                        fallback_pool_agent = _select_agent_pool_candidate(
                            effective_profile,
                            min_context_window=int(payload.get("max_tokens") or 0),
                            exclude_agent_id=pool_agent.agent_id if pool_agent else "",
                        )
                        if fallback_pool_agent and _AGENT_POOL_MANAGER.acquire_agent(fallback_pool_agent.agent_id):
                            pool_agent = fallback_pool_agent
                            pool_agent_acquired = True
                            payload["model"] = fallback_pool_agent.model_id

                    # Retry with new profile
                    response = await _post_delegate(effective_profile)
                    runtime = _apply_remote_runtime_status(
                        dict((registry.get("runtimes", {}) or {}).get(effective_runtime_id) or {}),
                        effective_runtime_id,
                        remote_aliases,
                        remote_configured,
                    )
                else:
                    # No failover available, fall back to old behavior
                    if selected_runtime_id in {"openrouter-gemini", "openrouter-coding", "openrouter-reasoning", "openrouter-tool-calling"} and remote_configured and remote_aliases.get("free"):
                        effective_profile = "remote-free"
                        effective_runtime_id = "openrouter-free"
                        fallback_applied = True
                        fallback_reason = "remote profile returned 402/429; no failover chain available, retried on remote-free"
            body = response.json()

            initial_classification = classify_delegated_response(
                task=task,
                messages=messages,
                status_code=int(initial_response.status_code),
                body=initial_body,
                profile=selected_profile,
                runtime_id=selected_runtime_id,
                stage="initial",
                fallback_applied=fallback_applied,
            )
            final_classification = classify_delegated_response(
                task=task,
                messages=messages,
                status_code=int(response.status_code),
                body=body,
                profile=effective_profile,
                runtime_id=effective_runtime_id,
                stage="final",
                fallback_applied=fallback_applied,
            )
            if (
                "tool_call_without_final_text" in (final_classification.get("failure_classes") or [])
                and effective_profile == "remote-tool-calling"
                and response.status_code < 400
            ):
                salvage = final_classification.get("salvage") if isinstance(final_classification.get("salvage"), dict) else {}
                tool_calls = salvage.get("tool_calls") if isinstance(salvage.get("tool_calls"), list) else []
                if tool_calls:
                    finalization_messages = _ai_coordinator_build_tool_call_finalization_messages(
                        task,
                        tool_calls,
                        profile=effective_profile,
                    )
                    finalization_payload: Dict[str, Any] = {
                        "messages": finalization_messages,
                        "stream": False,
                        "max_tokens": min(int(data.get("max_tokens") or 300) or 300, 300),
                        "temperature": 0,
                    }
                    if "model" in payload:
                        finalization_payload["model"] = payload["model"]
                    async with httpx.AsyncClient(timeout=timeout_s) as client:
                        finalization_response = await client.post(
                            f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                            headers={
                                "Content-Type": "application/json",
                                "X-AI-Profile": effective_profile,
                                "X-AI-Route": "remote",
                            },
                            json=finalization_payload,
                        )
                    finalization_body = finalization_response.json()
                    finalization_classification = classify_delegated_response(
                        task=task,
                        messages=finalization_messages,
                        status_code=int(finalization_response.status_code),
                        body=finalization_body,
                        profile=effective_profile,
                        runtime_id=effective_runtime_id,
                        stage="post_tool_finalization",
                        fallback_applied=fallback_applied,
                    )
                    if finalization_response.status_code < 400 and not finalization_classification.get("is_failure"):
                        response = finalization_response
                        body = finalization_body
                        final_classification = finalization_classification
                        finalization_applied = True
                        finalization_status_code = int(finalization_response.status_code)
            elif (
                "empty_content" in (final_classification.get("failure_classes") or [])
                and effective_profile == "remote-reasoning"
                and response.status_code < 400
            ):
                salvage = final_classification.get("salvage") if isinstance(final_classification.get("salvage"), dict) else {}
                reasoning_excerpt = str(salvage.get("reasoning_excerpt") or "").strip()
                if reasoning_excerpt:
                    finalization_messages = _ai_coordinator_build_reasoning_finalization_messages(
                        task,
                        reasoning_excerpt,
                        profile=effective_profile,
                    )
                    finalization_payload: Dict[str, Any] = {
                        "messages": finalization_messages,
                        "stream": False,
                        "max_tokens": min(int(data.get("max_tokens") or 260) or 260, 260),
                        "temperature": 0,
                    }
                    if "model" in payload:
                        finalization_payload["model"] = payload["model"]
                    async with httpx.AsyncClient(timeout=timeout_s) as client:
                        finalization_response = await client.post(
                            f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                            headers={
                                "Content-Type": "application/json",
                                "X-AI-Profile": effective_profile,
                                "X-AI-Route": "remote",
                            },
                            json=finalization_payload,
                        )
                    finalization_body = finalization_response.json()
                    finalization_classification = classify_delegated_response(
                        task=task,
                        messages=finalization_messages,
                        status_code=int(finalization_response.status_code),
                        body=finalization_body,
                        profile=effective_profile,
                        runtime_id=effective_runtime_id,
                        stage="post_reasoning_finalization",
                        fallback_applied=fallback_applied,
                    )
                    if finalization_response.status_code < 400 and not finalization_classification.get("is_failure"):
                        response = finalization_response
                        body = finalization_body
                        final_classification = finalization_classification
                        finalization_applied = True
                        finalization_status_code = int(finalization_response.status_code)
            delegated_quality = {"available": False}
            if response.status_code < 400:
                delegated_quality = await _assess_delegated_response_quality(
                    task,
                    body,
                    agent_id=pool_agent.agent_id if pool_agent else effective_profile,
                )
                if delegated_quality.get("available"):
                    pool_quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
                    updated_text = str(delegated_quality.get("response_text") or "").strip()
                    if updated_text:
                        body = _inject_delegated_response_text(body, updated_text)
            local_fallback_needed = (
                prefer_local
                and not local_fallback_applied
                and effective_profile not in {"default", "local-tool-calling"}
                and (
                    response.status_code >= 400
                    or final_classification.get("is_failure")
                    or (
                        delegated_quality.get("available")
                        and not delegated_quality.get("passed")
                        and delegated_quality.get("fallback_recommended")
                    )
                )
            )
            if local_fallback_needed:
                local_profile = "local-tool-calling" if isinstance(payload.get("tools"), list) and payload.get("tools") else "default"
                local_runtime_id = _ai_coordinator_default_runtime_id_for_profile(local_profile)
                local_payload = dict(payload)
                local_payload.pop("model", None)
                local_response = await _post_delegate(local_profile, delegate_payload=local_payload)
                local_body = local_response.json()
                local_classification = classify_delegated_response(
                    task=task,
                    messages=messages,
                    status_code=int(local_response.status_code),
                    body=local_body,
                    profile=local_profile,
                    runtime_id=local_runtime_id,
                    stage="local_fallback",
                    fallback_applied=True,
                )
                if local_response.status_code < 400 and not local_classification.get("is_failure"):
                    response = local_response
                    body = local_body
                    final_classification = local_classification
                    effective_profile = local_profile
                    effective_runtime_id = local_runtime_id
                    runtime = dict((registry.get("runtimes", {}) or {}).get(effective_runtime_id) or {})
                    fallback_applied = True
                    local_fallback_applied = True
                    fallback_reason = "remote failure or failed delegated QA triggered bounded local retry"
                    delegated_quality = {"available": False, "fallback_recommended": True}
            capability_gaps: List[Any] = []
            capability_gap_failure_text = _build_gap_failure_text(final_classification, delegated_quality)
            if final_classification.get("is_failure") or (delegated_quality.get("available") and not delegated_quality.get("passed")):
                capability_gaps = _GAP_DETECTOR.detect_from_failure(
                    capability_gap_failure_text or f"delegated failure for {effective_profile}",
                    task,
                    {
                        "profile": effective_profile,
                        "requesting_agent": orchestration["requesting_agent"],
                        "requester_role": orchestration["requester_role"],
                    },
                )
            remediation_plans = [_plan_capability_gap_remediation(gap) for gap in capability_gaps]
            real_time_learning = await _apply_real_time_learning(
                task,
                body,
                profile_name=effective_profile,
                delegated_quality=delegated_quality,
                final_classification=final_classification,
                context=data.get("context") if isinstance(data.get("context"), dict) else None,
            ) if response.status_code < 400 else {"available": False}
            meta_learning = await _apply_meta_learning(
                task,
                body,
                profile_name=effective_profile,
                delegated_quality=delegated_quality,
            ) if response.status_code < 400 else {"available": False}
            recovered_artifact = (
                {"available": False}
                if not final_classification.get("is_failure")
                else build_recovered_artifact(task, final_classification)
            )
            try:
                record_delegation_feedback(
                    task=task,
                    requested_profile=requested_profile,
                    selected_profile=selected_profile,
                    selected_runtime_id=selected_runtime_id,
                    classification=initial_classification,
                    final_profile=effective_profile,
                    final_runtime_id=effective_runtime_id,
                    requesting_agent=orchestration["requesting_agent"],
                    requester_role=orchestration["requester_role"],
                )
            except OSError as exc:
                logger.error("delegation_feedback_write_failed error=%s", exc)
            if fallback_applied or final_classification.get("is_failure"):
                try:
                    record_delegation_feedback(
                        task=task,
                        requested_profile=requested_profile,
                        selected_profile=selected_profile,
                        selected_runtime_id=selected_runtime_id,
                        classification=final_classification,
                        final_profile=effective_profile,
                        final_runtime_id=effective_runtime_id,
                        requesting_agent=orchestration["requesting_agent"],
                        requester_role=orchestration["requester_role"],
                    )
                except OSError as exc:
                    logger.error("delegation_feedback_write_failed error=%s", exc)
            request["audit_metadata"] = {
                "selected_runtime_id": effective_runtime_id,
                "selected_profile": effective_profile,
                "requesting_agent": orchestration["requesting_agent"],
                "requester_role": orchestration["requester_role"],
                "delegate_via_coordinator_only": orchestration["delegate_via_coordinator_only"],
                "delegated_http_status": int(response.status_code),
                "fallback_applied": fallback_applied,
                "local_fallback_applied": local_fallback_applied,
                "delegation_failure_class": final_classification.get("primary_failure_class", ""),
                "delegation_failure_classes": final_classification.get("failure_classes", []),
                "delegation_salvage_useful": bool((final_classification.get("salvage") or {}).get("has_useful_data")),
                "delegation_recovery_class": recovered_artifact.get("recovery_class", "") if recovered_artifact.get("available") else "",
                "delegation_finalization_applied": finalization_applied,
                "delegation_handoff_requested": bool(final_classification.get("handoff_requested")),
                "agent_pool_agent_id": pool_agent.agent_id if pool_agent else "",
                "agent_pool_tier": pool_agent.tier.value if pool_agent else "",
                "agent_pool_provider": pool_agent.provider if pool_agent else "",
                "delegated_quality_score": pool_quality_score,
                "delegated_quality_passed": bool(delegated_quality.get("passed")) if delegated_quality.get("available") else False,
                "delegated_quality_refined": bool(delegated_quality.get("refinement_applied")) if delegated_quality.get("available") else False,
                "delegated_quality_cached_fallback": bool(delegated_quality.get("cached_fallback_used")) if delegated_quality.get("available") else False,
                "prompt_optimization_applied": bool(prompt_optimization.get("applied")),
                "prompt_tokens_before": int(prompt_optimization.get("original_tokens", 0) or 0),
                "prompt_tokens_after": int(prompt_optimization.get("compressed_tokens", 0) or 0),
                "progressive_context_applied": bool(progressive_context_meta.get("applied")),
                "progressive_context_tier": str(progressive_context_meta.get("tier", "") or ""),
                "progressive_context_category": str(progressive_context_meta.get("category", "") or ""),
                "capability_gap_count": len(capability_gaps),
                "real_time_learning_applied": bool(real_time_learning.get("available")),
                "meta_learning_applied": bool(meta_learning.get("available")),
            }

            if pool_agent and response.status_code in {402, 429}:
                _AGENT_POOL_MANAGER.mark_rate_limited(pool_agent.agent_id)
            if pool_agent and pool_agent_acquired:
                _AGENT_POOL_MANAGER.release_agent(
                    pool_agent.agent_id,
                    success=response.status_code < 400,
                    latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                    quality_score=pool_quality_score,
                )
                pool_agent_acquired = False
            _record_capability_gap_outcomes(
                capability_gaps,
                duration_seconds=max(0.0, time.perf_counter() - request_started_at),
                response_status=int(response.status_code),
                fallback_applied=fallback_applied,
                finalization_applied=finalization_applied,
                delegated_quality=delegated_quality,
            )
            prompt_tokens_before = int(prompt_optimization.get("original_tokens", 0) or 0)
            prompt_tokens_after = int(prompt_optimization.get("compressed_tokens", 0) or 0)
            DELEGATED_PROMPT_TOKENS_BEFORE.labels(profile=effective_profile).observe(prompt_tokens_before)
            DELEGATED_PROMPT_TOKENS_AFTER.labels(profile=effective_profile).observe(prompt_tokens_after)
            if prompt_tokens_before > prompt_tokens_after:
                DELEGATED_PROMPT_TOKEN_SAVINGS.labels(profile=effective_profile).inc(prompt_tokens_before - prompt_tokens_after)
            if delegated_quality.get("available"):
                quality_value = float(delegated_quality.get("quality_score", 0.0) or 0.0)
                DELEGATED_QUALITY_SCORE.labels(profile=effective_profile).observe(quality_value)
                quality_outcome = (
                    "passed" if delegated_quality.get("passed")
                    else "cached_fallback" if delegated_quality.get("cached_fallback_used")
                    else "refined" if delegated_quality.get("refinement_applied")
                    else "failed"
                )
                DELEGATED_QUALITY_EVENTS.labels(profile=effective_profile, outcome=quality_outcome).inc()
            if progressive_context_meta.get("applied"):
                PROGRESSIVE_CONTEXT_LOADS.labels(
                    category=str(progressive_context_meta.get("category", "") or "unknown"),
                    tier=str(progressive_context_meta.get("tier", "") or "unknown"),
                    profile=effective_profile,
                ).inc()
            for gap in capability_gaps:
                CAPABILITY_GAP_DETECTIONS.labels(
                    gap_type=gap.gap_type.value,
                    severity=gap.severity.name.lower(),
                ).inc()
            if real_time_learning.get("available"):
                REAL_TIME_LEARNING_EVENTS.labels(profile=effective_profile, event_type="learning_example").inc()
                if int(real_time_learning.get("executed_action_count", 0) or 0) > 0:
                    REAL_TIME_LEARNING_EVENTS.labels(profile=effective_profile, event_type="feedback_action").inc(
                        int(real_time_learning.get("executed_action_count", 0) or 0)
                    )
            if meta_learning.get("available"):
                META_LEARNING_ADAPTATIONS.labels(
                    domain=str(meta_learning.get("domain", "") or "unknown"),
                    method=str(meta_learning.get("method", "") or "unknown"),
                ).inc()

            return web.json_response(
                {
                    "status": "ok" if response.status_code < 400 else "error",
                    "task": task,
                    "orchestration": orchestration,
                    "selected_runtime": {
                        "runtime_id": effective_runtime_id,
                        "name": runtime.get("name", effective_runtime_id),
                        "profile": runtime.get("profile", effective_profile),
                        "model_alias": runtime.get("model_alias", ""),
                        "status": runtime.get("status", status),
                    },
                    # Phase 9.3 — Query complexity routing decision
                    "routing_decision": {
                        "complexity": routing_decision.get("complexity", "unknown"),
                        "auto_routed": routing_decision.get("auto_routed", False),
                        "rationale": routing_decision.get("rationale", ""),
                    },
                    "fallback": (
                        {
                            "applied": True,
                            "from_profile": selected_profile,
                            "to_profile": effective_profile,
                            "reason": fallback_reason or "delegated fallback applied",
                            "failover_chain_used": failover_chain_used,
                        }
                        if fallback_applied else {"applied": False}
                    ),
                    "failover_chain": (
                        {
                            "used": failover_chain_used,
                            "original_profile": selected_profile,
                            "final_profile": effective_profile,
                            "reason": fallback_reason,
                        }
                        if failover_chain_used else {"used": False}
                    ),
                    "finalization": {
                        "applied": finalization_applied,
                        "status_code": finalization_status_code,
                        "reason": (
                            "tool_call_without_final_text remediation"
                            if finalization_applied and effective_profile == "remote-tool-calling"
                            else "reasoning_only remediation"
                            if finalization_applied and effective_profile == "remote-reasoning"
                            else ""
                        ),
                    },
                    "active_lesson_refs": lesson_refs,
                    "delegation_feedback": {
                        "initial": initial_classification,
                        "final": final_classification,
                    },
                    "progressive_context": progressive_context_meta,
                    "prompt_optimization": prompt_optimization,
                    "capability_gaps": [
                        {
                            "gap_id": gap.gap_id,
                            "gap_type": gap.gap_type.value,
                            "severity": gap.severity.name.lower(),
                            "priority_score": round(float(gap.priority_score or 0.0), 4),
                            "description": gap.description,
                        }
                        for gap in capability_gaps
                    ],
                    "remediation_plans": remediation_plans,
                    "real_time_learning": real_time_learning,
                    "meta_learning": meta_learning,
                    "agent_pool": (
                        {
                            "applied": True,
                            "agent_id": pool_agent.agent_id,
                            "provider": pool_agent.provider,
                            "model_id": pool_agent.model_id,
                            "tier": pool_agent.tier.value,
                        }
                        if pool_agent else {"applied": False}
                    ),
                    "quality_assurance": delegated_quality,
                    "artifact_recovery": recovered_artifact,
                    "response": body,
                },
                status=response.status_code,
            )
        except httpx.HTTPError as exc:
            pool_agent = locals().get("pool_agent")
            pool_agent_acquired = bool(locals().get("pool_agent_acquired"))
            request_started_at = float(locals().get("request_started_at") or time.perf_counter())
            if pool_agent and pool_agent_acquired:
                _AGENT_POOL_MANAGER.release_agent(
                    pool_agent.agent_id,
                    success=False,
                    latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                    quality_score=0.0,
                )
            return web.json_response(_error_payload("switchboard_unavailable", exc), status=502)
        except Exception as exc:
            pool_agent = locals().get("pool_agent")
            pool_agent_acquired = bool(locals().get("pool_agent_acquired"))
            request_started_at = float(locals().get("request_started_at") or time.perf_counter())
            if pool_agent and pool_agent_acquired:
                _AGENT_POOL_MANAGER.release_agent(
                    pool_agent.agent_id,
                    success=False,
                    latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                    quality_score=0.0,
                )
            return web.json_response(_error_payload("internal_error", exc), status=500)

    # ------------------------------------------------------------------
    # Phase 12.1/12.2 — Model Coordination Endpoints
    # ------------------------------------------------------------------

    async def handle_model_route(request: web.Request) -> web.Response:
        """
        POST /control/models/route — Classify and route a task to appropriate model(s).

        Phase 12.1/12.2: Model role classification and dual-model routing.
        Returns routing decision with primary/secondary model assignments.
        """
        try:
            data = await request.json()
            task = str(data.get("task") or data.get("query") or "").strip()
            if not task:
                return web.json_response({"error": "task required"}, status=400)

            context = data.get("context") if isinstance(data.get("context"), dict) else {}
            prefer_local = bool(data.get("prefer_local", True))

            result = _classify_and_route_task(task, context, prefer_local=prefer_local)
            result["task"] = task

            return web.json_response(result)
        except Exception as exc:
            logger.error("handle_model_route error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_model_list(request: web.Request) -> web.Response:
        """GET /control/models — List available model profiles."""
        try:
            coordinator = _get_model_coordinator()
            models = coordinator.list_available_models()
            stats = coordinator.get_routing_stats()
            return web.json_response({
                "models": models,
                "routing_stats": stats,
            })
        except Exception as exc:
            logger.error("handle_model_list error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_cache_warming_queue(request: web.Request) -> web.Response:
        """
        POST /control/cache/warm — Queue queries for proactive cache warming.
        GET /control/cache/warm — Get current warming queue batch.
        """
        try:
            coordinator = _get_model_coordinator()
            if request.method == "POST":
                data = await request.json()
                queries = data.get("queries") if isinstance(data.get("queries"), list) else []
                if not queries:
                    query = str(data.get("query") or "").strip()
                    if query:
                        queries = [query]
                for q in queries:
                    domain = data.get("domain")
                    priority = int(data.get("priority", 1))
                    coordinator.queue_cache_warming(q, domain, priority)
                return web.json_response({
                    "status": "queued",
                    "count": len(queries),
                })
            else:
                batch_size = int(request.rel_url.query.get("batch_size", "5"))
                batch = coordinator.get_cache_warming_batch(batch_size)
                return web.json_response({
                    "batch": batch,
                    "queue_depth": len(batch),
                })
        except Exception as exc:
            logger.error("handle_cache_warming_queue error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_tool_suggestions(request: web.Request) -> web.Response:
        """GET /control/tools/suggestions — Get tool suggestions for a domain."""
        try:
            domain = request.rel_url.query.get("domain", "ai-harness")
            task_type = request.rel_url.query.get("task_type", "")
            coordinator = _get_model_coordinator()
            suggestions = coordinator.get_tool_suggestions(domain, task_type or None)
            return web.json_response({
                "domain": domain,
                "task_type": task_type or "general",
                "suggestions": suggestions,
            })
        except Exception as exc:
            logger.error("handle_tool_suggestions error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    # ------------------------------------------------------------------
    # LLM Router Endpoints (Tier-based Cost Optimization)
    # ------------------------------------------------------------------

    async def handle_llm_router_route(request: web.Request) -> web.Response:
        """
        POST /control/llm/route — Route task using tier-based cost optimization.

        Implements Local > Free > Paid routing strategy.
        Returns tier assignment and model selection.
        """
        try:
            from llm_router import get_router

            data = await request.json()
            task_description = str(data.get("task") or data.get("description") or "").strip()
            if not task_description:
                return web.json_response({"error": "task required"}, status=400)

            context = data.get("context") if isinstance(data.get("context"), dict) else {}

            router = get_router()
            tier, model = router.route_task(task_description, context)

            return web.json_response({
                "task": task_description,
                "tier": tier.value,
                "model": model,
                "routing_strategy": "tier-based cost optimization",
                "estimated_cost": router._estimate_cost(tier),
            })
        except ImportError:
            return web.json_response({
                "error": "llm_router not available",
                "fallback": "use /control/models/route instead"
            }, status=503)
        except Exception as exc:
            logger.error("handle_llm_router_route error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_llm_router_execute(request: web.Request) -> web.Response:
        """
        POST /control/llm/execute — Execute task with intelligent routing and auto-escalation.

        Executes task using tier-based routing with automatic escalation on failures.
        Returns result with tier, model, cost, and escalation information.
        """
        try:
            from llm_router import get_router

            data = await request.json()
            task = {
                "description": str(data.get("task") or data.get("description") or "").strip(),
                "context": data.get("context") if isinstance(data.get("context"), dict) else {},
                "type": data.get("type", "unknown"),
                "allow_escalation": bool(data.get("allow_escalation", True)),
            }

            if not task["description"]:
                return web.json_response({"error": "task required"}, status=400)

            router = get_router()
            result = await router.execute_with_routing(task)

            return web.json_response(result)
        except ImportError:
            return web.json_response({
                "error": "llm_router not available",
                "fallback": "use /query or /control/models/route instead"
            }, status=503)
        except Exception as exc:
            logger.error("handle_llm_router_execute error=%s", exc)
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_llm_router_metrics(request: web.Request) -> web.Response:
        """
        GET /control/llm/metrics — Get LLM router metrics and cost savings.

        Returns tier distribution, cost estimates, escalation rates, and savings.
        """
        try:
            from llm_router import get_router

            router = get_router()
            metrics = router.get_metrics()

            return web.json_response({
                "metrics": metrics,
                "target_distribution": {
                    "local": "80%",
                    "free": "15%",
                    "paid": "5%",
                },
                "cost_optimization_goal": "95% reduction ($600/mo → $30/mo)",
            })
        except ImportError:
            return web.json_response({
                "error": "llm_router not available",
                "message": "Tier-based routing not initialized"
            }, status=503)
        except Exception as exc:
            logger.error("handle_llm_router_metrics error=%s", exc)
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
                "service_unit": str(data.get("service_unit", "")),
                "healthcheck_url": str(data.get("healthcheck_url", "")),
                "tags": data.get("tags", []) if isinstance(data.get("tags", []), list) else [],
                "updated_at": now,
                "source": str(data.get("source", "runtime-register") or "runtime-register"),
                "persistent": bool(data.get("persistent", False)),
            }
            record = _enrich_runtime_record(record)
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                existing = registry["runtimes"].get(runtime_id, {})
                record["created_at"] = int(existing.get("created_at", now))
                record["deployments"] = existing.get("deployments", [])
                registry["runtimes"][runtime_id] = record
                await _save_runtime_registry(registry)
            payload = dict(record)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_list(_request: web.Request) -> web.Response:
        try:
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
            items = [_enrich_runtime_record(item) for item in registry.get("runtimes", {}).values()]
            items.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
            payload = {"runtimes": items, "count": len(items)}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = _enrich_runtime_record(runtime)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
            payload = _enrich_runtime_record(runtime)
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_deploy(request: web.Request) -> web.Response:
        """Record deployment events and optionally execute bounded runtime activation."""
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            data = await request.json()
            execute = bool(data.get("execute", False))
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
                runtime = _enrich_runtime_record(runtime)
                action_result: Dict[str, Any] | None = None
                response_status = 200
                if execute:
                    action_result, response_status = await _execute_runtime_service_action(runtime, action="deploy")
                    deployment["execution"] = action_result
                    deployment["status"] = "executed" if response_status == 200 else "activation_failed"
                runtime.setdefault("deployments", []).append(deployment)
                runtime["updated_at"] = int(time.time())
                if execute and action_result:
                    runtime["status"] = "ready" if response_status == 200 else "degraded"
                    runtime.setdefault("status_notes", []).append({
                        "ts": int(time.time()),
                        "text": f"runtime deploy execute={execute} status={deployment['status']}",
                    })
                registry["runtimes"][runtime_id] = runtime
                await _save_runtime_registry(registry)
            payload = {"runtime_id": runtime_id, "deployment": deployment}
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload, status=response_status)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_rollback(request: web.Request) -> web.Response:
        """Record rollback requests and optionally execute bounded runtime rollback."""
        try:
            runtime_id = request.match_info.get("runtime_id", "")
            data = await request.json()
            to_deployment_id = str(data.get("to_deployment_id", "")).strip()
            reason = str(data.get("reason", "")).strip()
            execute = bool(data.get("execute", False))
            if not to_deployment_id:
                return web.json_response({"error": "to_deployment_id required"}, status=400)
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = registry.get("runtimes", {}).get(runtime_id)
                if not runtime:
                    return web.json_response({"error": "runtime not found"}, status=404)
                runtime = _enrich_runtime_record(runtime)
                rollback_entry = {
                    "to_deployment_id": to_deployment_id,
                    "reason": reason,
                    "created_at": int(time.time()),
                }
                action_result: Dict[str, Any] | None = None
                response_status = 200
                if execute:
                    action_result, response_status = await _execute_runtime_service_action(runtime, action="rollback")
                    rollback_entry["execution"] = action_result
                    rollback_entry["status"] = "executed" if response_status == 200 else "rollback_failed"
                runtime.setdefault("rollbacks", []).append(rollback_entry)
                runtime["updated_at"] = int(time.time())
                if execute and action_result:
                    runtime["status"] = "ready" if response_status == 200 else "degraded"
                    runtime.setdefault("status_notes", []).append({
                        "ts": int(time.time()),
                        "text": f"runtime rollback execute={execute} status={rollback_entry.get('status', 'recorded')}",
                    })
                registry["runtimes"][runtime_id] = runtime
                await _save_runtime_registry(registry)
            payload = {"runtime_id": runtime_id, "to_deployment_id": to_deployment_id, "status": "recorded"}
            if execute:
                payload["execution"] = action_result
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload, status=response_status)
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_runtime_schedule_policy(_request: web.Request) -> web.Response:
        """Return active runtime scheduler policy (declarative source + defaults)."""
        try:
            path = _runtime_scheduler_policy_path()
            policy = _load_runtime_scheduler_policy()
            payload = {
                "policy": policy,
                "source": str(path),
                "exists": path.exists(),
            }
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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

            payload = {
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
            async with _agent_lessons_lock:
                lesson_registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
            if lesson_refs:
                payload["active_lesson_refs"] = lesson_refs
            return web.json_response(payload)
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
    async def handle_alerts_list(request: web.Request) -> web.Response:
        """Return active alert-engine alerts for dashboard and validation clients."""
        try:
            alert_engine = _get_alert_engine()
            severity = str(request.query.get("severity", "") or "").strip().lower()
            component = str(request.query.get("component", "") or "").strip()
            severity_filter = None
            if severity:
                try:
                    severity_filter = AlertSeverity(severity)
                except ValueError:
                    return web.json_response({"error": "invalid severity"}, status=400)
            alerts = alert_engine.get_active_alerts(severity=severity_filter, component=component or None)
            return web.json_response(
                {
                    "alerts": [alert.to_dict() for alert in alerts],
                    "count": len(alerts),
                    "severity_counts": {
                        level.value: sum(1 for alert in alerts if alert.severity == level)
                        for level in AlertSeverity
                    },
                    "stats": alert_engine.get_stats(),
                }
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_alert_acknowledge(request: web.Request) -> web.Response:
        """Acknowledge an alert via HTTP for dashboard integration."""
        try:
            alert_id = str(request.match_info.get("alert_id", "") or "").strip()
            if not alert_id:
                return web.json_response({"error": "alert_id required"}, status=400)
            alert_engine = _get_alert_engine()
            acknowledged = await alert_engine.acknowledge_alert(alert_id)
            status = 200 if acknowledged else 404
            return web.json_response(
                {
                    "alert_id": alert_id,
                    "acknowledged": acknowledged,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                status=status,
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_alert_resolve(request: web.Request) -> web.Response:
        """Resolve an alert via HTTP for validation cleanup and operator actions."""
        try:
            alert_id = str(request.match_info.get("alert_id", "") or "").strip()
            if not alert_id:
                return web.json_response({"error": "alert_id required"}, status=400)
            alert_engine = _get_alert_engine()
            resolved = await alert_engine.resolve_alert(alert_id)
            status = 200 if resolved else 404
            return web.json_response(
                {
                    "alert_id": alert_id,
                    "resolved": resolved,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                status=status,
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_alert_test_create(request: web.Request) -> web.Response:
        """Create a bounded test alert for smoke validation and dashboard wiring checks."""
        try:
            data = await request.json() if request.can_read_body else {}
            severity_raw = str(data.get("severity", "warning") or "warning").strip().lower()
            try:
                severity = AlertSeverity(severity_raw)
            except ValueError:
                return web.json_response({"error": "invalid severity"}, status=400)
            title = str(data.get("title") or "Phase 4.1 validation alert").strip()[:120] or "Phase 4.1 validation alert"
            message = str(data.get("message") or "Synthetic deployment-monitoring-alerting validation alert").strip()[:500]
            source = str(data.get("source") or "phase-4-1-smoke").strip()[:64] or "phase-4-1-smoke"
            component = str(data.get("component") or "deployment-monitoring").strip()[:64] or "deployment-monitoring"
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            alert = await _get_alert_engine().create_alert(
                title=title,
                message=message,
                severity=severity,
                source=source,
                component=component,
                metadata=metadata,
            )
            return web.json_response(
                {
                    "status": "created",
                    "alert": alert.to_dict(),
                },
                status=201,
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

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
    async def handle_model_optimization_readiness(request):
        import model_optimization
        result = await model_optimization.get_optimization_readiness()
        return web.json_response(result)

    async def handle_training_data_stats(request):
        import model_optimization
        result = await model_optimization.get_training_data_stats()
        return web.json_response(result)

    async def handle_training_data_flush(request):
        import model_optimization
        result = await model_optimization.flush_training_data()
        return web.json_response(result)

    async def handle_finetuning_jobs_list(request):
        import model_optimization
        status_filter = request.query.get("status")
        result = await model_optimization.get_finetuning_jobs(status_filter=status_filter)
        return web.json_response(result)

    async def handle_finetuning_jobs_create(request):
        import model_optimization
        data = await request.json()
        result = await model_optimization.start_finetuning_job(
            base_model=data.get("base_model", ""),
            task_type=data.get("task_type", "general"),
            training_data_path=data.get("training_data_path"),
        )
        return web.json_response(result)

    async def handle_model_performance(request):
        import model_optimization
        model_id = request.query.get("model_id")
        result = await model_optimization.get_model_performance(model_id=model_id)
        return web.json_response(result)

    async def handle_synthetic_training_generate(request):
        import model_optimization
        data = await request.json()
        result = await model_optimization.generate_synthetic_training_data(
            target_examples=data.get("target_examples", 50),
            categories=data.get("categories"),
            strategies=data.get("strategies"),
            min_quality=data.get("min_quality", 0.7),
        )
        return web.json_response(result)

    async def handle_active_learning_select(request):
        import model_optimization
        data = await request.json()
        result = await model_optimization.select_active_learning_examples(
            budget=data.get("budget", 25),
            strategy=data.get("strategy", "hybrid"),
            candidate_paths=data.get("candidate_paths"),
        )
        return web.json_response(result)

    async def handle_distillation_pipeline_run(request):
        import model_optimization
        data = await request.json()
        result = await model_optimization.run_distillation_pipeline(
            teacher_model=data.get("teacher_model", ""),
            student_model=data.get("student_model", ""),
            training_data_path=data.get("training_data_path"),
            quantization_method=data.get("quantization_method", "gguf"),
            quantization_bits=data.get("quantization_bits", 4),
            pruning_sparsity=data.get("pruning_sparsity", 0.2),
            enable_speculative_decoding=data.get("enable_speculative_decoding", True),
        )
        return web.json_response(result)

    async def handle_advanced_features_readiness(request):
        import advanced_features
        result = await advanced_features.get_advanced_features_readiness()
        return web.json_response(result)

    async def handle_advanced_agent_quality_profiles(request):
        import advanced_features
        result = await advanced_features.get_agent_quality_profiles()
        return web.json_response(result)

    async def handle_advanced_agent_failover_select(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.select_failover_remote_agent(
            min_composite_score=data.get("min_composite_score", 0.55),
        )
        return web.json_response(result)

    async def handle_advanced_agent_benchmarks(request):
        import advanced_features
        result = await advanced_features.get_agent_benchmarks()
        return web.json_response(result)

    async def handle_advanced_prompt_optimize(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.optimize_prompt_template(
            task_type=data.get("task_type", "implementation"),
            task=data.get("task", ""),
            context=data.get("context"),
            constraints=data.get("constraints"),
        )
        return web.json_response(result)

    async def handle_advanced_prompt_dynamic(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.generate_dynamic_prompt(
            query=data.get("query", ""),
            context=data.get("context"),
        )
        return web.json_response(result)

    async def handle_advanced_prompt_ab_stats(request):
        import advanced_features
        result = await advanced_features.get_prompt_ab_stats()
        return web.json_response(result)

    async def handle_advanced_prompt_ab_record(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.record_prompt_variant_outcome(
            task_type=data.get("task_type", "implementation"),
            variant_id=data.get("variant_id", ""),
            score=data.get("score", 0.0),
        )
        return web.json_response(result)

    async def handle_advanced_context_tier_select(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.select_context_tier(
            query=data.get("query", ""),
            context=data.get("context"),
        )
        return web.json_response(result)

    async def handle_advanced_context_tier_stats(request):
        import advanced_features
        result = await advanced_features.get_tier_selection_stats()
        return web.json_response(result)

    async def handle_advanced_failure_patterns(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.analyze_failure_patterns(
            query=data.get("query", ""),
            response=data.get("response", ""),
            error_message=data.get("error_message"),
            user_feedback=data.get("user_feedback"),
        )
        return web.json_response(result)

    async def handle_advanced_capability_gap_stats(request):
        import advanced_features
        result = await advanced_features.get_capability_gap_stats()
        return web.json_response(result)

    async def handle_advanced_learning_signal(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.record_learning_signal(
            query=data.get("query", ""),
            response=data.get("response", ""),
            outcome=data.get("outcome", "unknown"),
            explicit_score=data.get("explicit_score"),
        )
        return web.json_response(result)

    async def handle_advanced_learning_recommendations(request):
        import advanced_features
        data = await request.json()
        result = await advanced_features.get_learning_recommendations(
            query=data.get("query", ""),
        )
        return web.json_response(result)

    async def handle_advanced_learning_stats(request):
        import advanced_features
        result = await advanced_features.get_learning_stats()
        return web.json_response(result)

    # -------------------------------------------------------------------------
    # Phase 4.2 — Multi-Agent Orchestration Framework Endpoints
    # -------------------------------------------------------------------------

    async def handle_orchestration_status(request: web.Request) -> web.Response:
        """Get orchestration framework status."""
        try:
            return web.json_response({
                "status": "ok",
                "agent_hq": {
                    "registered_agents": len(_AGENT_HQ.global_agents),
                    "active_sessions": len(_AGENT_HQ.sessions),
                    "persistence_dir": str(_ORCHESTRATION_PERSISTENCE_DIR),
                },
                "delegation": _DELEGATION_API.get_queue_status(),
                "workspaces": {
                    "active": len(_WORKSPACE_MANAGER.workspaces),
                    "base_dir": str(_WORKSPACE_BASE_DIR),
                },
                "tool_invoker": _MCP_TOOL_INVOKER.get_usage_report(),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_agents_list(request: web.Request) -> web.Response:
        """List all registered agents."""
        try:
            agents = [agent.to_dict() for agent in _AGENT_HQ.global_agents.values()]
            return web.json_response({"agents": agents, "count": len(agents)})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_agents_register(request: web.Request) -> web.Response:
        """Register a new agent."""
        try:
            data = await request.json()
            name = str(data.get("name", "")).strip()
            if not name:
                return web.json_response({"error": "name required"}, status=400)
            capabilities = set(data.get("capabilities", []))
            metadata = data.get("metadata", {})
            agent = _AGENT_HQ.register_agent(name, capabilities, metadata)
            # Also register with delegation API
            _DELEGATION_API.register_agent(
                agent.agent_id,
                name,
                capabilities=capabilities,
                max_concurrent=int(data.get("max_concurrent", 5)),
            )
            return web.json_response({"status": "ok", "agent": agent.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_sessions_list(request: web.Request) -> web.Response:
        """List orchestration sessions."""
        try:
            state_filter = request.query.get("state")
            filter_enum = SessionState(state_filter) if state_filter else None
            sessions = _AGENT_HQ.list_sessions(state_filter=filter_enum)
            return web.json_response({
                "sessions": [s.to_dict() for s in sessions],
                "count": len(sessions),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_create(request: web.Request) -> web.Response:
        """Create a new orchestration session."""
        try:
            data = await request.json()
            name = str(data.get("name", "")).strip() or f"session-{int(time.time())}"
            context = data.get("context", {})
            session = _AGENT_HQ.create_session(name, context)
            return web.json_response({"status": "ok", "session": session.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_get(request: web.Request) -> web.Response:
        """Get session details."""
        try:
            session_id = request.match_info["session_id"]
            session = _AGENT_HQ.get_session(session_id)
            if not session:
                return web.json_response({"error": "session not found"}, status=404)
            status = _AGENT_HQ.get_session_status(session_id)
            return web.json_response({
                "session": session.to_dict(),
                "status": status,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_start(request: web.Request) -> web.Response:
        """Start or resume a session."""
        try:
            session_id = request.match_info["session_id"]
            success = await _AGENT_HQ.start_session(session_id)
            if not success:
                return web.json_response({"error": "failed to start session"}, status=400)
            return web.json_response({"status": "ok", "session_id": session_id, "state": "running"})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_pause(request: web.Request) -> web.Response:
        """Pause a running session."""
        try:
            session_id = request.match_info["session_id"]
            success = await _AGENT_HQ.pause_session(session_id)
            if not success:
                return web.json_response({"error": "failed to pause session"}, status=400)
            return web.json_response({"status": "ok", "session_id": session_id, "state": "paused"})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_checkpoint(request: web.Request) -> web.Response:
        """Create a checkpoint for a session."""
        try:
            session_id = request.match_info["session_id"]
            data = await request.json()
            name = str(data.get("name", "")).strip() or None
            checkpoint = _AGENT_HQ.create_checkpoint(session_id, name)
            if not checkpoint:
                return web.json_response({"error": "failed to create checkpoint"}, status=400)
            return web.json_response({"status": "ok", "checkpoint": checkpoint.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_session_restore(request: web.Request) -> web.Response:
        """Restore session from a checkpoint."""
        try:
            session_id = request.match_info["session_id"]
            data = await request.json()
            checkpoint_id = str(data.get("checkpoint_id", "")).strip()
            if not checkpoint_id:
                return web.json_response({"error": "checkpoint_id required"}, status=400)
            success = _AGENT_HQ.restore_checkpoint(session_id, checkpoint_id)
            if not success:
                return web.json_response({"error": "failed to restore checkpoint"}, status=400)
            return web.json_response({"status": "ok", "restored": checkpoint_id})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_task_submit(request: web.Request) -> web.Response:
        """Submit a task for delegation."""
        try:
            session_id = request.match_info["session_id"]
            data = await request.json()
            description = str(data.get("description", "")).strip()
            if not description:
                return web.json_response({"error": "description required"}, status=400)
            capabilities = set(data.get("required_capabilities", []))
            priority = int(data.get("priority", 5))
            task = await _AGENT_HQ.submit_task(
                session_id,
                description,
                priority=priority,
                required_capabilities=capabilities or None,
            )
            if not task:
                return web.json_response({"error": "failed to submit task"}, status=400)
            return web.json_response({"status": "ok", "task": task.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_delegate(request: web.Request) -> web.Response:
        """Delegate a task directly via the delegation API."""
        try:
            data = await request.json()
            description = str(data.get("description", "")).strip()
            if not description:
                return web.json_response({"error": "description required"}, status=400)
            capabilities = set(data.get("required_capabilities", []))
            preferred_agent = data.get("preferred_agent")
            priority = int(data.get("priority", 5))
            timeout = float(data.get("timeout_seconds", 300.0))
            wait = bool(data.get("wait", False))
            # Phase 1.3 — Profile delegation API call
            _delegate_start = time.time()
            result = await _DELEGATION_API.delegate(
                task_description=description,
                required_capabilities=capabilities or None,
                preferred_agent=preferred_agent,
                priority=priority,
                timeout_seconds=timeout,
                wait=wait,
            )
            _delegate_duration_ms = (time.time() - _delegate_start) * 1000
            _PERFORMANCE_PROFILER.record_metric("delegation_api_delegate", _delegate_duration_ms, {"wait": wait, "priority": priority})
            return web.json_response({"status": "ok", "result": result.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_workspace_create(request: web.Request) -> web.Response:
        """Create an isolated workspace."""
        try:
            data = await request.json()
            agent_id = str(data.get("agent_id", "")).strip()
            session_id = str(data.get("session_id", "")).strip()
            if not agent_id or not session_id:
                return web.json_response({"error": "agent_id and session_id required"}, status=400)
            mode_str = str(data.get("mode", "temp_dir")).strip().lower()
            mode = IsolationMode(mode_str) if mode_str in [m.value for m in IsolationMode] else IsolationMode.TEMP_DIR
            source_path = data.get("source_path")
            workspace = await _WORKSPACE_MANAGER.create_workspace(
                agent_id=agent_id,
                session_id=session_id,
                source_path=Path(source_path) if source_path else None,
                mode=mode,
            )
            return web.json_response({"status": "ok", "workspace": workspace.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_workspace_list(request: web.Request) -> web.Response:
        """List workspaces."""
        try:
            session_id = request.query.get("session_id")
            agent_id = request.query.get("agent_id")
            workspaces = _WORKSPACE_MANAGER.list_workspaces(session_id=session_id, agent_id=agent_id)
            return web.json_response({
                "workspaces": [w.to_dict() for w in workspaces],
                "count": len(workspaces),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_workspace_cleanup(request: web.Request) -> web.Response:
        """Clean up a workspace."""
        try:
            workspace_id = request.match_info["workspace_id"]
            force = request.query.get("force", "false").lower() == "true"
            success = await _WORKSPACE_MANAGER.cleanup_workspace(workspace_id, force=force)
            if not success:
                return web.json_response({"error": "failed to cleanup workspace"}, status=400)
            return web.json_response({"status": "ok", "cleaned": workspace_id})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_tool_register(request: web.Request) -> web.Response:
        """Register an MCP tool."""
        try:
            data = await request.json()
            tool_id = str(data.get("tool_id", "")).strip()
            name = str(data.get("name", "")).strip()
            description = str(data.get("description", "")).strip()
            server_id = str(data.get("server_id", "")).strip()
            if not all([tool_id, name, description, server_id]):
                return web.json_response({"error": "tool_id, name, description, server_id required"}, status=400)
            tool = _MCP_TOOL_INVOKER.register_tool(
                tool_id=tool_id,
                name=name,
                description=description,
                server_id=server_id,
                capabilities=set(data.get("capabilities", [])),
                estimated_cost=float(data.get("estimated_cost", 0.0)),
                requires_approval=bool(data.get("requires_approval", False)),
                rate_limit=data.get("rate_limit"),
            )
            return web.json_response({"status": "ok", "tool": tool.to_dict()})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_tool_invoke(request: web.Request) -> web.Response:
        """Invoke an MCP tool."""
        try:
            data = await request.json()
            tool_id = str(data.get("tool_id", "")).strip()
            if not tool_id:
                return web.json_response({"error": "tool_id required"}, status=400)
            params = data.get("params", {})
            agent_id = str(data.get("agent_id", "system")).strip()
            result = await _MCP_TOOL_INVOKER.invoke(
                tool_id=tool_id,
                params=params,
                agent_id=agent_id,
            )
            return web.json_response({"status": "ok", "result": result})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_orchestration_tool_search(request: web.Request) -> web.Response:
        """Search for tools."""
        try:
            query = request.query.get("q", "")
            capabilities = request.query.get("capabilities", "").split(",") if request.query.get("capabilities") else []
            max_results = int(request.query.get("max_results", 10))
            tools = _MCP_TOOL_INVOKER.search_tools(
                query=query,
                capabilities=set(c.strip() for c in capabilities if c.strip()) or None,
                max_results=max_results,
            )
            return web.json_response({
                "tools": [t.to_dict() for t in tools],
                "count": len(tools),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    # Phase 1.3 — Live Bottleneck Detection & Performance Profiling endpoints
    async def handle_bottleneck_status(request: web.Request) -> web.Response:
        """Get current bottleneck detection status and summary."""
        try:
            min_call_count = int(request.query.get("min_calls", 10))
            threshold_ms = float(request.query.get("threshold_ms", 100))
            bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
                min_call_count=min_call_count,
                threshold_ms=threshold_ms,
            )
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for b in bottlenecks:
                severity_counts[b.severity] += 1
            return web.json_response({
                "status": "ok",
                "operations_tracked": len(_PERFORMANCE_PROFILER.metrics),
                "total_metrics": sum(len(m) for m in _PERFORMANCE_PROFILER.metrics.values()),
                "bottleneck_count": len(bottlenecks),
                "severity_breakdown": severity_counts,
                "window_minutes": _PERFORMANCE_PROFILER.window_size.total_seconds() / 60,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_bottleneck_list(request: web.Request) -> web.Response:
        """List all detected bottlenecks with details."""
        try:
            min_call_count = int(request.query.get("min_calls", 10))
            threshold_ms = float(request.query.get("threshold_ms", 100))
            severity_filter = request.query.get("severity")
            bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
                min_call_count=min_call_count,
                threshold_ms=threshold_ms,
            )
            if severity_filter:
                bottlenecks = [b for b in bottlenecks if b.severity == severity_filter]
            return web.json_response({
                "bottlenecks": [
                    {
                        "operation": b.operation,
                        "severity": b.severity,
                        "avg_ms": round(b.avg_duration_ms, 2),
                        "p95_ms": round(b.p95_duration_ms, 2),
                        "p99_ms": round(b.p99_duration_ms, 2),
                        "call_count": b.call_count,
                        "total_time_ms": round(b.total_time_ms, 2),
                        "percentage_of_total": round(b.percentage_of_total, 2),
                        "recommendation": b.recommendation,
                    }
                    for b in bottlenecks
                ],
                "count": len(bottlenecks),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_bottleneck_recommendations(request: web.Request) -> web.Response:
        """Get optimization recommendations for detected bottlenecks."""
        try:
            min_call_count = int(request.query.get("min_calls", 10))
            threshold_ms = float(request.query.get("threshold_ms", 100))
            max_priority = int(request.query.get("max_priority", 5))
            bottlenecks = _PERFORMANCE_PROFILER.identify_bottlenecks(
                min_call_count=min_call_count,
                threshold_ms=threshold_ms,
            )
            recommendations = _PERFORMANCE_PROFILER.generate_optimization_recommendations(bottlenecks)
            recommendations = [r for r in recommendations if r.priority <= max_priority]
            return web.json_response({
                "recommendations": [
                    {
                        "priority": r.priority,
                        "operation": r.bottleneck.operation,
                        "severity": r.bottleneck.severity,
                        "estimated_improvement_pct": r.estimated_improvement,
                        "implementation_effort": r.implementation_effort,
                        "description": r.description,
                        "action_items": r.action_items,
                    }
                    for r in recommendations
                ],
                "count": len(recommendations),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_bottleneck_operation_stats(request: web.Request) -> web.Response:
        """Get detailed statistics for a specific operation."""
        try:
            operation = request.query.get("operation")
            if not operation:
                return web.json_response({"error": "operation parameter required"}, status=400)
            stats = _PERFORMANCE_PROFILER.get_statistics(operation)
            return web.json_response(stats)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_bottleneck_report(request: web.Request) -> web.Response:
        """Export a full performance report as JSON."""
        try:
            report_path = _PERFORMANCE_PROFILER.export_report()
            with open(report_path) as f:
                report = json.load(f)
            return web.json_response(report)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_bottleneck_record(request: web.Request) -> web.Response:
        """Record a performance metric (used by internal components)."""
        try:
            data = await request.json()
            operation = data.get("operation")
            duration_ms = data.get("duration_ms")
            metadata = data.get("metadata", {})
            if not operation or duration_ms is None:
                return web.json_response(
                    {"error": "operation and duration_ms required"}, status=400
                )
            _PERFORMANCE_PROFILER.record_metric(operation, duration_ms, metadata)
            from metrics import PROFILED_OPERATIONS, PROFILED_OPERATION_DURATION
            PROFILED_OPERATIONS.labels(operation=operation).inc()
            PROFILED_OPERATION_DURATION.labels(operation=operation).observe(duration_ms / 1000)
            return web.json_response({"status": "recorded"})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_openai_models(request: web.Request) -> web.Response:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/models")
            content_type = response.headers.get("content-type", "application/json")
            return web.Response(
                status=response.status_code,
                body=response.content,
                content_type=content_type.split(";", 1)[0] if content_type else None,
            )
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_openai_chat_completions(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            if not isinstance(data, dict):
                return web.json_response({"error": "json object body required"}, status=400)
            return await _proxy_openai_request_via_coordinator(request, data, path="chat/completions")
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    async def handle_openai_completions(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            if not isinstance(data, dict):
                return web.json_response({"error": "json object body required"}, status=400)
            return await _proxy_openai_request_via_coordinator(request, data, path="completions")
        except Exception as exc:
            return web.json_response(_error_payload("internal_error", exc), status=500)

    http_app.router.add_get("/.well-known/mcp.json", handle_well_known_mcp)
    http_app.router.add_get("/.well-known/agent.json", handle_well_known_a2a)
    http_app.router.add_get("/.well-known/agent-card.json", handle_well_known_a2a)
    http_app.router.add_get("/v1/models", handle_openai_models)
    http_app.router.add_post("/v1/chat/completions", handle_openai_chat_completions)
    http_app.router.add_post("/v1/completions", handle_openai_completions)
    http_app.router.add_get("/health", handle_health)
    http_app.router.add_get("/health/detailed", handle_health_detailed)
    http_app.router.add_get("/health/aggregate", handle_health_aggregate)  # Phase 11.2
    http_app.router.add_get("/alerts", handle_alerts_list)
    http_app.router.add_post("/alerts/test", handle_alert_test_create)
    http_app.router.add_post("/alerts/{alert_id}/acknowledge", handle_alert_acknowledge)
    http_app.router.add_post("/alerts/{alert_id}/resolve", handle_alert_resolve)
    http_app.router.add_get("/status", handle_status)
    http_app.router.add_get("/stats", handle_stats)
    http_app.router.add_post("/augment_query", handle_augment_query)
    http_app.router.add_post("/query", handle_query)
    http_app.router.add_post("/v1/orchestrate", handle_orchestrate)  # Phase 0 Slice 0.2
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
    http_app.router.add_get("/agent-status", handle_agent_status)      # Phase 20.1
    http_app.router.add_post("/agent-status", handle_agent_status)     # Phase 20.1
    http_app.router.add_post("/workflow/plan", handle_workflow_plan)
    http_app.router.add_get("/workflow/plan", handle_workflow_plan)
    http_app.router.add_post("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_get("/workflow/tooling-manifest", handle_workflow_tooling_manifest)
    http_app.router.add_post("/research/web/fetch", handle_web_research_fetch)
    http_app.router.add_post("/research/web/browser-fetch", handle_browser_research_fetch)
    http_app.router.add_post("/research/workflows/curated-fetch", handle_curated_research_fetch)
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
    http_app.router.add_get("/workflow/run/{session_id}/team", handle_workflow_run_team)
    http_app.router.add_get("/workflow/run/{session_id}/team/detailed", handle_workflow_run_team_detailed)
    http_app.router.add_get("/workflow/run/{session_id}/arbiter/history", handle_workflow_run_arbiter_history)
    http_app.router.add_post("/workflow/run/{session_id}/consensus", handle_workflow_run_consensus)
    http_app.router.add_post("/workflow/run/{session_id}/arbiter", handle_workflow_run_arbiter)
    http_app.router.add_post("/workflow/run/{session_id}/mode", handle_workflow_run_mode)
    http_app.router.add_get("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_get)
    http_app.router.add_post("/workflow/run/{session_id}/isolation", handle_workflow_run_isolation_set)
    http_app.router.add_post("/workflow/run/{session_id}/event", handle_workflow_run_event)
    http_app.router.add_get("/workflow/run/{session_id}/replay", handle_workflow_run_replay)
    http_app.router.add_post("/", handle_a2a_rpc)
    http_app.router.add_post("/a2a", handle_a2a_rpc)
    http_app.router.add_get("/a2a/tasks/{session_id}/events", handle_a2a_task_events)
    http_app.router.add_get("/workflow/blueprints", handle_workflow_blueprints)
    http_app.router.add_get("/parity/scorecard", handle_parity_scorecard)
    http_app.router.add_get("/control/ai-coordinator/status", handle_ai_coordinator_status)
    http_app.router.add_get("/control/ai-coordinator/lessons", handle_ai_coordinator_lessons)
    http_app.router.add_post("/control/ai-coordinator/lessons/review", handle_ai_coordinator_lessons_review)
    http_app.router.add_get("/control/ai-coordinator/evaluations", handle_ai_coordinator_evaluations)
    http_app.router.add_get("/control/ai-coordinator/evaluations/trends", handle_ai_coordinator_evaluation_trends)
    http_app.router.add_get("/control/ai-coordinator/skills", handle_ai_coordinator_skills)
    http_app.router.add_post("/control/ai-coordinator/delegate", handle_ai_coordinator_delegate)
    # Batch 5.2 — Skill Usage Tracking and Recommendations
    http_app.router.add_get("/control/skills/usage", handle_skill_usage_stats)
    http_app.router.add_get("/control/skills/recommendations", handle_skill_recommendations)
    # Phase 12.1/12.2 — Model Coordination endpoints
    http_app.router.add_post("/control/models/route", handle_model_route)
    http_app.router.add_get("/control/models", handle_model_list)
    http_app.router.add_post("/control/cache/warm", handle_cache_warming_queue)
    http_app.router.add_get("/control/cache/warm", handle_cache_warming_queue)
    http_app.router.add_get("/control/tools/suggestions", handle_tool_suggestions)
    # LLM Router endpoints (Tier-based cost optimization)
    http_app.router.add_post("/control/llm/route", handle_llm_router_route)
    http_app.router.add_post("/control/llm/execute", handle_llm_router_execute)
    http_app.router.add_get("/control/llm/metrics", handle_llm_router_metrics)
    http_app.router.add_get("/control/autoresearch/status", handle_autoresearch_status)
    http_app.router.add_post("/control/autoresearch/run", handle_autoresearch_run)
    # Batch 3.2 — PRSI Action Execution endpoints
    http_app.router.add_get("/control/prsi/pending", handle_prsi_pending)
    http_app.router.add_get("/control/prsi/actions", handle_prsi_actions_list)
    http_app.router.add_post("/control/prsi/actions/execute", handle_prsi_action_execute)
    http_app.router.add_post("/control/runtimes/register", handle_runtime_register)
    http_app.router.add_get("/control/runtimes", handle_runtime_list)
    http_app.router.add_get("/control/runtimes/{runtime_id}", handle_runtime_get)
    http_app.router.add_post("/control/runtimes/{runtime_id}/status", handle_runtime_status)
    http_app.router.add_post("/control/runtimes/{runtime_id}/deployments", handle_runtime_deploy)
    http_app.router.add_post("/control/runtimes/{runtime_id}/rollback", handle_runtime_rollback)
    http_app.router.add_get("/control/runtimes/schedule/policy", handle_runtime_schedule_policy)
    http_app.router.add_post("/control/runtimes/schedule/select", handle_runtime_schedule)

    # Phase 5 — Model Optimization endpoints
    http_app.router.add_get("/control/ai-coordinator/model-optimization/readiness", handle_model_optimization_readiness)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/training-data/stats", handle_training_data_stats)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/training-data/flush", handle_training_data_flush)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/finetuning/jobs", handle_finetuning_jobs_list)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/finetuning/jobs", handle_finetuning_jobs_create)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/performance", handle_model_performance)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/synthetic-data/generate", handle_synthetic_training_generate)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/active-learning/select", handle_active_learning_select)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/distillation/run", handle_distillation_pipeline_run)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/readiness", handle_advanced_features_readiness)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/offloading/quality-profiles", handle_advanced_agent_quality_profiles)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/offloading/failover-select", handle_advanced_agent_failover_select)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/offloading/benchmarks", handle_advanced_agent_benchmarks)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/optimize", handle_advanced_prompt_optimize)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/dynamic", handle_advanced_prompt_dynamic)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/prompt/ab-stats", handle_advanced_prompt_ab_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/ab-record", handle_advanced_prompt_ab_record)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/context/tier-select", handle_advanced_context_tier_select)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/context/tier-stats", handle_advanced_context_tier_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/capability-gap/failure-patterns", handle_advanced_failure_patterns)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/capability-gap/stats", handle_advanced_capability_gap_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/learning/signal", handle_advanced_learning_signal)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/learning/recommendations", handle_advanced_learning_recommendations)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/learning/stats", handle_advanced_learning_stats)

    # Phase 1: WebSocket alert endpoint
    http_app.router.add_get("/ws/alerts", handle_alerts_websocket)

    # Phase 4.2 — Multi-Agent Orchestration Framework endpoints
    http_app.router.add_get("/control/orchestration/status", handle_orchestration_status)
    http_app.router.add_get("/control/orchestration/agents", handle_orchestration_agents_list)
    http_app.router.add_post("/control/orchestration/agents/register", handle_orchestration_agents_register)
    http_app.router.add_get("/control/orchestration/sessions", handle_orchestration_sessions_list)
    http_app.router.add_post("/control/orchestration/sessions", handle_orchestration_session_create)
    http_app.router.add_get("/control/orchestration/sessions/{session_id}", handle_orchestration_session_get)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/start", handle_orchestration_session_start)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/pause", handle_orchestration_session_pause)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/checkpoint", handle_orchestration_session_checkpoint)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/restore", handle_orchestration_session_restore)
    http_app.router.add_post("/control/orchestration/sessions/{session_id}/tasks", handle_orchestration_task_submit)
    http_app.router.add_post("/control/orchestration/delegate", handle_orchestration_delegate)
    http_app.router.add_get("/control/orchestration/workspaces", handle_orchestration_workspace_list)
    http_app.router.add_post("/control/orchestration/workspaces", handle_orchestration_workspace_create)
    http_app.router.add_delete("/control/orchestration/workspaces/{workspace_id}", handle_orchestration_workspace_cleanup)
    http_app.router.add_post("/control/orchestration/tools/register", handle_orchestration_tool_register)
    http_app.router.add_post("/control/orchestration/tools/invoke", handle_orchestration_tool_invoke)
    http_app.router.add_get("/control/orchestration/tools/search", handle_orchestration_tool_search)

    # Phase 1.3 — Live Bottleneck Detection & Performance Profiling routes
    http_app.router.add_get("/control/bottleneck/status", handle_bottleneck_status)
    http_app.router.add_get("/control/bottleneck/list", handle_bottleneck_list)
    http_app.router.add_get("/control/bottleneck/recommendations", handle_bottleneck_recommendations)
    http_app.router.add_get("/control/bottleneck/operation", handle_bottleneck_operation_stats)
    http_app.router.add_get("/control/bottleneck/report", handle_bottleneck_report)
    http_app.router.add_post("/control/bottleneck/record", handle_bottleneck_record)

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

    # =========================================================================
    # Minor IndyDevDan Patterns - Evidence, Safety, Message Bus, Capability
    # =========================================================================

    # Evidence Storage - for structured evidence capture during task execution
    _evidence_store: dict[str, list[dict]] = {}

    async def handle_evidence_record(request: web.Request) -> web.Response:
        """Record evidence for a task/session (IndyDevDan pattern: Structured Evidence Capture)."""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)

            evidence = {
                "id": f"ev-{int(time.time() * 1000)}",
                "session_id": session_id,
                "task_id": data.get("task_id", ""),
                "agent_id": data.get("agent_id", ""),
                "evidence_type": data.get("type", "general"),  # command, test, file_change, validation
                "content": data.get("content", {}),
                "command": data.get("command", ""),
                "output": data.get("output", ""),
                "exit_code": data.get("exit_code"),
                "files_changed": data.get("files_changed", []),
                "timestamp": time.time(),
                "tags": data.get("tags", []),
            }

            if session_id not in _evidence_store:
                _evidence_store[session_id] = []
            _evidence_store[session_id].append(evidence)

            return web.json_response({
                "status": "recorded",
                "evidence_id": evidence["id"],
                "session_id": session_id,
                "total_evidence": len(_evidence_store[session_id]),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_evidence_list(request: web.Request) -> web.Response:
        """List evidence for a session with optional filtering."""
        try:
            session_id = request.query.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)

            evidence_list = _evidence_store.get(session_id, [])
            evidence_type = request.query.get("type")
            if evidence_type:
                evidence_list = [e for e in evidence_list if e["evidence_type"] == evidence_type]

            task_id = request.query.get("task_id")
            if task_id:
                evidence_list = [e for e in evidence_list if e["task_id"] == task_id]

            return web.json_response({
                "session_id": session_id,
                "evidence": evidence_list,
                "count": len(evidence_list),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/evidence/record", handle_evidence_record)
    http_app.router.add_get("/control/evidence/list", handle_evidence_list)

    # Safety Gate Pre-Hooks - block destructive operations
    _safety_hooks: list[dict] = [
        {"pattern": "rm -rf /", "action": "block", "reason": "System wipe attempt"},
        {"pattern": "git push --force", "action": "warn", "reason": "Force push can lose history"},
        {"pattern": "DROP TABLE", "action": "block", "reason": "Destructive SQL operation"},
        {"pattern": "nixos-rebuild switch", "action": "require_approval", "reason": "System change"},
        {"pattern": "sudo rm", "action": "warn", "reason": "Privileged file deletion"},
    ]

    async def handle_safety_check(request: web.Request) -> web.Response:
        """Check if a command/operation is safe to execute (IndyDevDan pattern: Safety Gates)."""
        try:
            data = await request.json()
            command = data.get("command", "")
            operation = data.get("operation", "")
            context = data.get("context", {})

            check_text = command or operation
            if not check_text:
                return web.json_response({"error": "command or operation required"}, status=400)

            violations = []
            for hook in _safety_hooks:
                pattern = hook["pattern"]
                if pattern.lower() in check_text.lower():
                    violations.append({
                        "pattern": pattern,
                        "action": hook["action"],
                        "reason": hook["reason"],
                    })

            if not violations:
                return web.json_response({
                    "safe": True,
                    "command": check_text,
                    "action": "allow",
                })

            # Determine overall action (most restrictive wins)
            actions = [v["action"] for v in violations]
            if "block" in actions:
                overall_action = "block"
            elif "require_approval" in actions:
                overall_action = "require_approval"
            else:
                overall_action = "warn"

            return web.json_response({
                "safe": overall_action not in ("block", "require_approval"),
                "command": check_text,
                "action": overall_action,
                "violations": violations,
                "recommendation": "Request approval or modify command" if overall_action != "warn" else "Proceed with caution",
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_safety_register_hook(request: web.Request) -> web.Response:
        """Register a new safety hook pattern."""
        try:
            data = await request.json()
            pattern = data.get("pattern", "")
            action = data.get("action", "warn")
            reason = data.get("reason", "Custom safety rule")

            if not pattern:
                return web.json_response({"error": "pattern required"}, status=400)
            if action not in ("block", "warn", "require_approval"):
                return web.json_response({"error": "action must be block/warn/require_approval"}, status=400)

            hook = {"pattern": pattern, "action": action, "reason": reason}
            _safety_hooks.append(hook)

            return web.json_response({
                "status": "registered",
                "hook": hook,
                "total_hooks": len(_safety_hooks),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/safety/check", handle_safety_check)
    http_app.router.add_post("/control/safety/register-hook", handle_safety_register_hook)

    # Inter-Agent Message Bus - pub/sub for parallel agent coordination
    _message_bus_topics: dict[str, list[dict]] = {}
    _message_bus_subscribers: dict[str, list[str]] = {}  # topic -> [agent_ids]

    async def handle_message_bus_publish(request: web.Request) -> web.Response:
        """Publish a message to a topic (IndyDevDan pattern: Inter-Agent Message Bus)."""
        try:
            data = await request.json()
            topic = data.get("topic", "")
            if not topic:
                return web.json_response({"error": "topic required"}, status=400)

            message = {
                "id": f"msg-{int(time.time() * 1000)}",
                "topic": topic,
                "from_agent": data.get("from_agent", ""),
                "payload": data.get("payload", {}),
                "message_type": data.get("type", "info"),  # info, request, response, event
                "timestamp": time.time(),
                "correlation_id": data.get("correlation_id", ""),
            }

            if topic not in _message_bus_topics:
                _message_bus_topics[topic] = []
            _message_bus_topics[topic].append(message)

            # Keep only last 100 messages per topic
            if len(_message_bus_topics[topic]) > 100:
                _message_bus_topics[topic] = _message_bus_topics[topic][-100:]

            subscriber_count = len(_message_bus_subscribers.get(topic, []))

            return web.json_response({
                "status": "published",
                "message_id": message["id"],
                "topic": topic,
                "subscriber_count": subscriber_count,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_message_bus_subscribe(request: web.Request) -> web.Response:
        """Subscribe an agent to a topic."""
        try:
            data = await request.json()
            topic = data.get("topic", "")
            agent_id = data.get("agent_id", "")

            if not topic or not agent_id:
                return web.json_response({"error": "topic and agent_id required"}, status=400)

            if topic not in _message_bus_subscribers:
                _message_bus_subscribers[topic] = []
            if agent_id not in _message_bus_subscribers[topic]:
                _message_bus_subscribers[topic].append(agent_id)

            return web.json_response({
                "status": "subscribed",
                "topic": topic,
                "agent_id": agent_id,
                "total_subscribers": len(_message_bus_subscribers[topic]),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_message_bus_poll(request: web.Request) -> web.Response:
        """Poll messages from a topic for an agent."""
        try:
            topic = request.query.get("topic", "")
            agent_id = request.query.get("agent_id", "")
            since = float(request.query.get("since", "0"))
            limit = int(request.query.get("limit", "50"))

            if not topic:
                return web.json_response({"error": "topic required"}, status=400)

            messages = _message_bus_topics.get(topic, [])
            # Filter messages after 'since' timestamp
            if since > 0:
                messages = [m for m in messages if m["timestamp"] > since]
            # Exclude own messages if agent_id provided
            if agent_id:
                messages = [m for m in messages if m["from_agent"] != agent_id]

            messages = messages[-limit:]

            return web.json_response({
                "topic": topic,
                "messages": messages,
                "count": len(messages),
                "latest_timestamp": messages[-1]["timestamp"] if messages else since,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/message-bus/publish", handle_message_bus_publish)
    http_app.router.add_post("/control/message-bus/subscribe", handle_message_bus_subscribe)
    http_app.router.add_get("/control/message-bus/poll", handle_message_bus_poll)

    # Historical Capability Scoring - track agent performance over time
    _capability_history: dict[str, list[dict]] = {}  # agent_id -> [outcomes]

    async def handle_capability_record_outcome(request: web.Request) -> web.Response:
        """Record a capability outcome for an agent (IndyDevDan pattern: Historical Scoring)."""
        try:
            data = await request.json()
            agent_id = data.get("agent_id", "")
            capability = data.get("capability", "")

            if not agent_id or not capability:
                return web.json_response({"error": "agent_id and capability required"}, status=400)

            outcome = {
                "id": f"out-{int(time.time() * 1000)}",
                "agent_id": agent_id,
                "capability": capability,
                "task_id": data.get("task_id", ""),
                "success": data.get("success", True),
                "quality_score": data.get("quality_score", 1.0),  # 0.0 to 1.0
                "duration_seconds": data.get("duration_seconds"),
                "error_type": data.get("error_type"),
                "notes": data.get("notes", ""),
                "timestamp": time.time(),
            }

            if agent_id not in _capability_history:
                _capability_history[agent_id] = []
            _capability_history[agent_id].append(outcome)

            # Keep only last 500 outcomes per agent
            if len(_capability_history[agent_id]) > 500:
                _capability_history[agent_id] = _capability_history[agent_id][-500:]

            return web.json_response({
                "status": "recorded",
                "outcome_id": outcome["id"],
                "agent_id": agent_id,
                "capability": capability,
                "total_outcomes": len(_capability_history[agent_id]),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_capability_score(request: web.Request) -> web.Response:
        """Get capability scores for an agent based on historical performance."""
        try:
            agent_id = request.query.get("agent_id", "")
            capability = request.query.get("capability")
            window_hours = int(request.query.get("window_hours", "168"))  # Default 1 week

            if not agent_id:
                return web.json_response({"error": "agent_id required"}, status=400)

            outcomes = _capability_history.get(agent_id, [])
            cutoff = time.time() - (window_hours * 3600)
            outcomes = [o for o in outcomes if o["timestamp"] > cutoff]

            if capability:
                outcomes = [o for o in outcomes if o["capability"] == capability]

            if not outcomes:
                return web.json_response({
                    "agent_id": agent_id,
                    "capability": capability,
                    "scores": {},
                    "message": "No historical data available",
                })

            # Calculate scores by capability
            capabilities: dict[str, list[dict]] = {}
            for o in outcomes:
                cap = o["capability"]
                if cap not in capabilities:
                    capabilities[cap] = []
                capabilities[cap].append(o)

            scores = {}
            for cap, cap_outcomes in capabilities.items():
                total = len(cap_outcomes)
                successes = sum(1 for o in cap_outcomes if o["success"])
                avg_quality = sum(o.get("quality_score", 1.0) for o in cap_outcomes) / total
                durations = [o["duration_seconds"] for o in cap_outcomes if o.get("duration_seconds")]
                avg_duration = sum(durations) / len(durations) if durations else None

                scores[cap] = {
                    "success_rate": successes / total,
                    "average_quality": round(avg_quality, 3),
                    "sample_count": total,
                    "average_duration_seconds": round(avg_duration, 2) if avg_duration else None,
                    "recent_errors": [o["error_type"] for o in cap_outcomes[-5:] if o.get("error_type")],
                }

            # Calculate overall score
            overall_success = sum(1 for o in outcomes if o["success"]) / len(outcomes)
            overall_quality = sum(o.get("quality_score", 1.0) for o in outcomes) / len(outcomes)

            return web.json_response({
                "agent_id": agent_id,
                "window_hours": window_hours,
                "overall": {
                    "success_rate": round(overall_success, 3),
                    "average_quality": round(overall_quality, 3),
                    "total_outcomes": len(outcomes),
                },
                "by_capability": scores,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/capability/record-outcome", handle_capability_record_outcome)
    http_app.router.add_get("/control/capability/score", handle_capability_score)

    # Rollback Execution API - execute rollback commands safely
    _rollback_registry: dict[str, dict] = {}  # session_id -> rollback_info

    async def handle_rollback_register(request: web.Request) -> web.Response:
        """Register a rollback procedure for a session/task."""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)

            rollback_info = {
                "session_id": session_id,
                "task_id": data.get("task_id", ""),
                "rollback_commands": data.get("commands", []),
                "rollback_files": data.get("files", {}),  # {path: original_content}
                "description": data.get("description", ""),
                "registered_at": time.time(),
                "registered_by": data.get("agent_id", ""),
                "status": "registered",
            }

            _rollback_registry[session_id] = rollback_info

            return web.json_response({
                "status": "registered",
                "session_id": session_id,
                "command_count": len(rollback_info["rollback_commands"]),
                "file_count": len(rollback_info["rollback_files"]),
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_rollback_execute(request: web.Request) -> web.Response:
        """Execute a registered rollback (IndyDevDan pattern: Safe Rollback)."""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            dry_run = data.get("dry_run", True)  # Default to dry-run for safety

            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)

            rollback_info = _rollback_registry.get(session_id)
            if not rollback_info:
                return web.json_response({"error": f"No rollback registered for session {session_id}"}, status=404)

            if dry_run:
                return web.json_response({
                    "status": "dry_run",
                    "session_id": session_id,
                    "would_execute": rollback_info["rollback_commands"],
                    "would_restore_files": list(rollback_info["rollback_files"].keys()),
                    "description": rollback_info["description"],
                    "message": "Set dry_run=false to execute",
                })

            # Execute rollback (file restoration only - command execution requires approval)
            restored_files = []
            for file_path, content in rollback_info["rollback_files"].items():
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    restored_files.append(file_path)
                except Exception as e:
                    logger.warning("Failed to restore %s: %s", file_path, e)

            rollback_info["status"] = "executed"
            rollback_info["executed_at"] = time.time()
            rollback_info["restored_files"] = restored_files

            return web.json_response({
                "status": "executed",
                "session_id": session_id,
                "restored_files": restored_files,
                "pending_commands": rollback_info["rollback_commands"],
                "message": "Files restored. Execute commands manually for safety.",
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_rollback_status(request: web.Request) -> web.Response:
        """Get rollback status for a session."""
        try:
            session_id = request.query.get("session_id", "")
            if not session_id:
                return web.json_response({"error": "session_id required"}, status=400)

            rollback_info = _rollback_registry.get(session_id)
            if not rollback_info:
                return web.json_response({
                    "session_id": session_id,
                    "has_rollback": False,
                    "message": "No rollback registered",
                })

            return web.json_response({
                "session_id": session_id,
                "has_rollback": True,
                "status": rollback_info["status"],
                "registered_at": rollback_info["registered_at"],
                "command_count": len(rollback_info["rollback_commands"]),
                "file_count": len(rollback_info["rollback_files"]),
                "description": rollback_info["description"],
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    http_app.router.add_post("/control/rollback/register", handle_rollback_register)
    http_app.router.add_post("/control/rollback/execute", handle_rollback_execute)
    http_app.router.add_get("/control/rollback/status", handle_rollback_status)

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
