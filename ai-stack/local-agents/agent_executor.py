#!/usr/bin/env python3
"""
Local Agent Executor - Workflow Integration

Enables local llama.cpp agents to execute tasks with tool use:
- Tool-augmented inference
- Multi-step task execution
- Result validation
- Performance tracking
- Automatic failover to remote agents

Part of Phase 11 Batch 11.3: Workflow Integration
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# shared/ lives at ai-stack/mcp-servers/shared/ — add parent to path once.
_MCP_SERVERS_PATH = str(Path(__file__).resolve().parents[1] / "mcp-servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)

# Phase 184: Antigravity Collective Integration
# lib/l4-coord uses a hyphen — not importable via dotted path. Add the agents
# subdir directly so imports work without renaming the on-disk directory.
_L4_COORD_AGENTS = str(Path(__file__).resolve().parents[2] / "lib" / "l4-coord" / "agents")
if _L4_COORD_AGENTS not in sys.path:
    sys.path.insert(0, _L4_COORD_AGENTS)

from collaborative_planning import (  # noqa: E402
    CollaborativePlanning, PlanningMode, PhaseType
)
from collective_memory import CollectiveMemory  # noqa: E402

from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS, AGENT_TASK_MAX_TOKENS  # noqa: E402
from tool_registry import ToolCall, ToolRegistry, get_registry

# Phase 164B — MIC-G context sanitizer: scrub prompt-injection patterns from tool results
# before they are injected into the LLM context window.  Import is best-effort; if the
# security module is unavailable (e.g. minimal install) the agent continues without it.
try:
    _SECURITY_PATH = str(Path(__file__).resolve().parents[1] / "security")
    if _SECURITY_PATH not in sys.path:
        sys.path.insert(0, _SECURITY_PATH)
    from context_sanitizer import sanitize_tool_result as _sanitize_tool_result
    _CONTEXT_SANITIZER_AVAILABLE = True
except ImportError:
    _CONTEXT_SANITIZER_AVAILABLE = False
    _sanitize_tool_result = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_TELEMETRY_DIR = Path(os.getenv("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry"))
# Agent events are written to the user-spool path (.agents/telemetry/hybrid-events.jsonl)
# rather than the service-owned /var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl.
# Reason: hybrid-events.jsonl is owned by ai-hybrid:ai-stack with 0640 permissions —
# aq-agent-loop runs as hyperd (ai-stack group, read-only) so every direct write
# silently fails with PermissionError. training_ingest.py reads BOTH paths via
# USER_EVENTS_SPOOL, so agent telemetry lands in training data without privilege issues.
_REPO_ROOT_PATH = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parents[2]))
_HYBRID_EVENTS = _REPO_ROOT_PATH / ".agents" / "telemetry" / "hybrid-events.jsonl"
_HYBRID_EVENTS.parent.mkdir(parents=True, exist_ok=True)

# Phase E — agent-run-events.jsonl path: prefer harness_paths SSOT; fall back to absolute path.
# Never use a relative path — agent_executor.py may run from Nix store (EROFS).
try:
    _HP_PATH = str(Path(__file__).resolve().parent)
    if _HP_PATH not in sys.path:
        sys.path.insert(0, _HP_PATH)
    from harness_paths import AGENT_RUN_EVENTS as _AGENT_RUN_EVENTS_PATH
except ImportError:
    _AGENT_RUN_EVENTS_PATH = Path(os.environ.get(  # type: ignore[assignment]
        "AQ_AGENT_RUN_EVENTS_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl",
    ))

# Per-task monotonic sequence counter for agent-run-events.jsonl.
# Keyed by task_id. Cleaned up on agent_complete/agent_failed to prevent unbounded growth.
_agent_event_seq: dict[str, int] = {}

_CODE_TASK_RE = re.compile(
    r"\b(implement|write|code|script|function|class|patch|refactor|debug|fix|test)\b",
    re.IGNORECASE,
)

# ── Phase A.6: keyword sets for per-iteration tool hot-swap ──────────────────
# Mirror the sets in local_agent_runtime.py so both runtimes share the same
# signal vocabulary.  Tools described as text in the system prompt are refreshed
# by rebuilding messages[0] after each tool call result.
_AEXEC_MEMORY_KW = frozenset(["remember", "store", "save", "record", "note", "memorize", "persist"])
_AEXEC_WORKFLOW_KW = frozenset(["workflow", "pipeline", "prsi", "self-improve", "optimization"])
_AEXEC_DELEGATE_KW = frozenset(["delegate", "remote", "escalate", "assign", "handoff", "codex", "claude", "opencode"])
_AEXEC_HEALTH_KW = frozenset(["health", "status", "check", "verify", "diagnose", "monitor", "running", "alive"])
_AEXEC_MESH_KW = frozenset(["mesh", "agents", "team", "capabilities", "federated", "who can"])
_AEXEC_OBJECTIVE_KW = frozenset(["objective", "what to work", "no task", "need direction", "what should", "propose", "suggest work"])

# Tool names that are always present (never hot-swapped in/out).
_AEXEC_ALWAYS_TOOLS: frozenset[str] = frozenset(["read_file", "write_file", "edit_file", "run_command", "git_add", "git_commit"])
# Tools eligible for hot-swap injection keyed by the keyword set that triggers them.
_AEXEC_HOTSWAP_MAP: list[tuple[frozenset[str], list[str]]] = [
    (_AEXEC_MEMORY_KW,    ["store_memory"]),
    (_AEXEC_WORKFLOW_KW,  ["get_workflow_status", "execute_workflow"]),
    (_AEXEC_DELEGATE_KW,  ["delegate_to_remote"]),
    (_AEXEC_HEALTH_KW,    ["harness_health"]),
    (_AEXEC_MESH_KW,      ["mesh_discovery"]),
    (_AEXEC_OBJECTIVE_KW, ["discover_objectives"]),
]

# Tools that gate the loop: after one of these returns, inject a synthesis nudge
# and return immediately instead of continuing the tool call loop.
# This prevents the agent from taking action before the user approves a proposal.
_TERMINAL_TOOLS: frozenset[str] = frozenset({"discover_objectives"})


def _refresh_active_tools(
    tool_name: str,
    result_text: str,
    current_tools: List[Dict],
    all_tools: List[Dict],
    max_tools: int = 8,
) -> List[Dict]:
    """Hot-swap active tool set for agent_executor based on tool result content.

    Monotonic expansion: never removes already-active tools.
    all_tools is the full registry snapshot — source of new schemas.
    max_tools is generous (8) here because tool descriptions are text, not JSON schemas.
    """
    current_names = {t["name"] for t in current_tools}
    result_lower = result_text.lower()
    additions: list[str] = []

    for kw_set, candidates in _AEXEC_HOTSWAP_MAP:
        if any(k in result_lower for k in kw_set):
            for candidate in candidates:
                if candidate not in current_names:
                    additions.append(candidate)

    if not additions:
        return current_tools

    # Build lookup from full registry
    all_by_name = {t["name"]: t for t in all_tools}
    result_tools = list(current_tools)
    for name in additions:
        if len(result_tools) >= max_tools:
            break
        if name in all_by_name and name not in current_names:
            result_tools.append(all_by_name[name])
            current_names.add(name)
    return result_tools


def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean environment flag."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    """Parse a float environment setting with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %.2f", name, value, default)
        return default


async def _store_prune_checkpoint(coordinator_url: str, task_id: str, summary: str) -> None:
    """Fire-and-forget: save pruned context summary to working memory before eviction.

    Called via asyncio.create_task() — never blocks the agent loop.
    Skipped silently on any network/coordinator error.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as _pc_client:
            await _pc_client.post(
                f"{coordinator_url.rstrip('/')}/memory/store",
                json={
                    "content": summary,
                    "memory_type": "semantic",
                    "source": "agent-executor-prune",
                    "importance": 0.5,
                    "tags": [f"task_id:{task_id}", "prune_checkpoint", "working_memory"],
                },
            )
    except Exception:
        pass


class AgentType(Enum):
    """Local agent types — capability class (what the model CAN do).
    Orthogonal to role (what the model is AUTHORISED to do this session).
    AgentType routes execution shape; role injects authority context.
    """
    AGENT = "agent"      # Task execution (full tool-use loop)
    PLANNER = "planner"  # Strategy/planning
    CHAT = "chat"        # User interaction
    EMBEDDED = "embedded"  # Retrieval only — no text generation, never gets role injection


# Maps each AgentType to its default role when task.role is not explicitly set.
# Roles defined in docs/architecture/role-matrix.md (SSOT).
# EMBEDDED maps to None — no role injection for embedding-only agents.
AGENT_TYPE_DEFAULT_ROLE: Dict[AgentType, Optional[str]] = {
    AgentType.AGENT:    "implementer",
    AgentType.PLANNER:  "architect",
    AgentType.CHAT:     "implementer",
    AgentType.EMBEDDED: None,
}

# Roles each AgentType is eligible for (authority ceiling per capability class).
AGENT_TYPE_ELIGIBLE_ROLES: Dict[AgentType, List[str]] = {
    AgentType.AGENT:    ["implementer", "reviewer"],
    AgentType.PLANNER:  ["architect", "orchestrator", "implementer"],
    AgentType.CHAT:     ["implementer"],
    AgentType.EMBEDDED: [],
}


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    FALLBACK = "fallback"  # Fell back to remote agent


@dataclass
class Task:
    """Task for agent execution"""
    id: str
    objective: str
    context: Dict[str, Any] = field(default_factory=dict)

    # Routing factors
    complexity: float = 0.5  # 0.0-1.0
    latency_critical: bool = False
    quality_critical: bool = False
    requires_flagship: bool = False

    # Execution state
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    degraded_reason: Optional[str] = None
    execution_time_ms: float = 0.0

    # Agent tracking
    assigned_agent: Optional[str] = None
    tool_calls_made: List[ToolCall] = field(default_factory=list)

    # Role — authority class for this task (from role-matrix.md SSOT).
    # None = auto-assign from AGENT_TYPE_DEFAULT_ROLE at dispatch.
    # EMBEDDED agents always get None (no role injection).
    role: Optional[str] = None

    # Phase 104 — reviewer_id: the assigned_agent of the original implementation task.
    # Set by the orchestrator when dispatching a review; used to detect self-review
    # (role-matrix.md §8: a reviewer may not review their own work).
    reviewer_id: Optional[str] = None

    # Phase 172 — task_type selects a modal llm_config TaskProfile for this task.
    # Profiles control temperature, thinking mode, and thinking_budget.
    # None = default agent profile (enable_thinking=False, temperature=0.2).
    # Use "research" or "deep_reasoning" for PRSI / multi-hop planning tasks.
    task_type: Optional[str] = None

    # Headless Antigravity — force remote routing
    force_remote: bool = False
    remote_profile: Optional[str] = None
    remote_model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "objective": self.objective,
            "context": self.context,
            "complexity": self.complexity,
            "latency_critical": self.latency_critical,
            "quality_critical": self.quality_critical,
            "requires_flagship": self.requires_flagship,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "degraded_reason": self.degraded_reason,
            "execution_time_ms": self.execution_time_ms,
            "assigned_agent": self.assigned_agent,
            "tool_calls_count": len(self.tool_calls_made),
            "role": self.role,
            "reviewer_id": self.reviewer_id,
            "force_remote": self.force_remote,
            "remote_profile": self.remote_profile,
            "remote_model": self.remote_model,
        }


@dataclass
class AgentPerformance:
    """Performance tracking for an agent"""
    agent_type: AgentType

    # Counters
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    fallback_tasks: int = 0

    # Timing
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0

    # Quality
    avg_result_quality: float = 0.0  # 0.0-1.0
    quality_samples: int = 0

    # Tool use
    total_tool_calls: int = 0
    successful_tool_calls: int = 0

    def update(self, task: Task):
        """Update performance metrics from completed task"""
        self.total_tasks += 1

        if task.status == TaskStatus.COMPLETED:
            self.successful_tasks += 1
        elif task.status == TaskStatus.FAILED:
            self.failed_tasks += 1
        elif task.status == TaskStatus.FALLBACK:
            self.fallback_tasks += 1

        self.total_execution_time_ms += task.execution_time_ms
        self.avg_execution_time_ms = self.total_execution_time_ms / self.total_tasks

        self.total_tool_calls += len(task.tool_calls_made)
        self.successful_tool_calls += len([
            tc for tc in task.tool_calls_made if tc.status == "completed"
        ])

    def get_success_rate(self) -> float:
        """Get success rate (0.0-1.0)"""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    def get_tool_success_rate(self) -> float:
        """Get tool call success rate"""
        if self.total_tool_calls == 0:
            return 0.0
        return self.successful_tool_calls / self.total_tool_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_type": self.agent_type.value,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "fallback_tasks": self.fallback_tasks,
            "success_rate": self.get_success_rate(),
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "total_tool_calls": self.total_tool_calls,
            "tool_success_rate": self.get_tool_success_rate(),
            "avg_result_quality": self.avg_result_quality,
        }


class LocalAgentExecutor:
    """
    Executes tasks using local llama.cpp agents with tool use.

    Features:
    - Tool-augmented inference
    - Multi-step task execution
    - Performance tracking
    - Automatic failover to remote agents
    """

    def __init__(
        self,
        llama_endpoint: str = os.environ.get("LLAMA_CPP_URL", os.environ.get("LLAMA_URL", "http://127.0.0.1:8080")),
        tool_registry: Optional[ToolRegistry] = None,
        enable_fallback: bool = True,
        fallback_endpoint: str = os.environ.get("COORDINATOR_URL", os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")),
        offline_mode: Optional[bool] = None,
        allow_degraded_local_execution: Optional[bool] = None,
        remote_timeout_seconds: Optional[float] = None,
        remote_probe_timeout_seconds: Optional[float] = None,
    ):
        self.llama_endpoint = llama_endpoint
        self.tool_registry = tool_registry or get_registry()
        self.enable_fallback = enable_fallback
        self.fallback_endpoint = fallback_endpoint
        self.offline_mode = (
            _env_flag("LOCAL_AGENT_OFFLINE_MODE", False)
            if offline_mode is None
            else offline_mode
        )
        self.allow_degraded_local_execution = (
            _env_flag("LOCAL_AGENT_ALLOW_DEGRADED_LOCAL", True)
            if allow_degraded_local_execution is None
            else allow_degraded_local_execution
        )
        self.remote_timeout_seconds = (
            _env_float("LOCAL_AGENT_REMOTE_TIMEOUT_SECONDS", 600.0)
            if remote_timeout_seconds is None
            else remote_timeout_seconds
        )
        self.remote_probe_timeout_seconds = (
            _env_float("LOCAL_AGENT_REMOTE_PROBE_TIMEOUT_SECONDS", 2.0)
            if remote_probe_timeout_seconds is None
            else remote_probe_timeout_seconds
        )
        # Cached prompt extensions — loaded once per executor instance (extensions only
        # change with a rebuild, so per-process caching is safe and avoids a YAML read
        # on every LLM call in a long-running agent task).
        self._prompt_extensions_cache: Optional[str] = None
        self._remote_endpoint_healthy: Optional[bool] = None
        self._remote_endpoint_checked_at: float = 0.0

        # Performance tracking per agent type
        self.performance: Dict[AgentType, AgentPerformance] = {
            agent_type: AgentPerformance(agent_type)
            for agent_type in AgentType
        }

        logger.info(
            f"Local agent executor initialized: llama={llama_endpoint}, "
            f"fallback={enable_fallback}, offline_mode={self.offline_mode}, "
            f"allow_degraded_local={self.allow_degraded_local_execution}"
        )

    # ── Phase E — agent-run-events.jsonl event emission ──────────────────────

    async def _async_append_jsonl(self, path: Path, event: dict) -> None:
        """Append one JSON line to path. Never raises — fire-and-forget."""
        try:
            try:
                import aiofiles  # type: ignore[import]
                async with aiofiles.open(path, "a", encoding="utf-8") as _f:
                    await _f.write(json.dumps(event) + "\n")
            except ImportError:
                # aiofiles not available: fall back to asyncio.to_thread
                def _sync_write() -> None:
                    with path.open("a", encoding="utf-8") as _f:
                        _f.write(json.dumps(event) + "\n")
                await asyncio.to_thread(_sync_write)
        except Exception:
            pass  # fire-and-forget: never propagate

    async def _emit_agent_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict,
        _watchdog_last_activity: "list[float] | None" = None,
    ) -> None:
        """Emit a structured event to agent-run-events.jsonl. Fire-and-forget."""
        path = Path(os.environ.get("AQ_AGENT_RUN_EVENTS_PATH", str(_AGENT_RUN_EVENTS_PATH)))
        seq = _agent_event_seq.get(task_id, 0) + 1
        _agent_event_seq[task_id] = seq
        if _watchdog_last_activity is not None:
            _watchdog_last_activity[0] = time.time()
        event = {
            "task_id": task_id,
            "seq": seq,
            "event_type": event_type,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            **payload,
        }
        asyncio.create_task(self._async_append_jsonl(path, event))

    async def _emit_terminal_agent_event(self, task: Task, event_type: str, payload: dict) -> None:
        """Emit a terminal event and release per-task sequence state."""
        await self._emit_agent_event(task.id, event_type, payload)
        _agent_event_seq.pop(task.id, None)

    def route_task(self, task: Task) -> Tuple[bool, str]:
        """
        Route task to local or remote agent.

        Returns:
            (use_local, reason)
        """
        remote_routing_available = self.enable_fallback and not self.offline_mode

        if task.force_remote:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Task forced to remote but remote routing unavailable; degrading to local"
            return False, "Task forced to remote"

        # Always use remote for flagship-required tasks
        if task.requires_flagship:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Flagship requested but remote routing unavailable; degrading to local"
            return False, "Task requires flagship model"

        # Use local for simple, non-critical tasks
        if task.complexity < 0.5 and not task.quality_critical:
            return True, "Simple task, local agent capable"

        # Use local for latency-critical tasks
        if task.latency_critical:
            return True, "Latency critical, local preferred"

        # Use remote for quality-critical tasks
        if task.quality_critical:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Quality critical task degraded to local because remote routing is unavailable"
            return False, "Quality critical, remote preferred"

        # Check local agent performance
        agent_perf = self.performance[AgentType.AGENT]
        if agent_perf.total_tasks > 10:
            success_rate = agent_perf.get_success_rate()

            # Fallback to remote if local success rate too low
            if success_rate < 0.7:
                if not remote_routing_available and self.allow_degraded_local_execution:
                    return True, f"Local success rate low ({success_rate:.1%}) but remote routing unavailable"
                return False, f"Local success rate low ({success_rate:.1%})"

        # Default to local
        return True, "Default to local (cost-efficient)"

    async def execute_task(
        self,
        task: Task,
        agent_type: AgentType = AgentType.AGENT,
        max_tool_calls: int = 0,
    ) -> Task:
        """
        Execute a task using local agent with tool use.

        Args:
            task: Task to execute
            agent_type: Type of agent to use
            max_tool_calls: Deprecated compatibility parameter. Tool loops are
                governed by stagnation/progress guards, context pruning, and the
                stall watchdog, not by a fixed tool-call ceiling.

        Returns:
            Updated task with result or error
        """
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.assigned_agent = f"local-{agent_type.value}"

        # Auto-assign role from capability→default mapping if not explicitly set.
        # EMBEDDED agents never get a role (no text generation to guide).
        if task.role is None:
            task.role = AGENT_TYPE_DEFAULT_ROLE.get(agent_type)

        # Phase 58A.5: validate role eligibility — clamp ineligible assignments to default.
        eligible_roles = AGENT_TYPE_ELIGIBLE_ROLES.get(agent_type)
        if task.role is not None and eligible_roles is not None and task.role not in eligible_roles:
            logger.warning(
                "Task %s: agent_type=%s is not eligible for role=%s (eligible: %s); clamping to default",
                task.id, agent_type.value, task.role, eligible_roles,
            )
            task.role = AGENT_TYPE_DEFAULT_ROLE.get(agent_type)

        # Phase 104: self-review guard — role-matrix.md §8 prohibits reviewing own work.
        # reviewer_id holds the assigned_agent of the original implementation task.
        # This is advisory (warning, not block) — blocking is the orchestrator's responsibility.
        if task.role == "reviewer" and task.reviewer_id is not None:
            if task.reviewer_id == task.assigned_agent:
                logger.warning(
                    "Task %s: self-review detected — reviewer_id=%r matches assigned_agent=%r. "
                    "Role matrix §8: a reviewer may not review their own work. "
                    "Proceeding — orchestrator should reassign to a different agent.",
                    task.id, task.reviewer_id, task.assigned_agent,
                )

        # Route task
        use_local, route_reason = self.route_task(task)

        if not use_local:
            if self.enable_fallback:
                if not await self._remote_fallback_available():
                    if self.allow_degraded_local_execution:
                        use_local = True
                        task.degraded_reason = (
                            f"{route_reason}; remote fallback unavailable, executing locally"
                        )
                        logger.warning("Task %s degraded to local execution: %s", task.id, task.degraded_reason)
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = f"{route_reason}; remote fallback unavailable"
                        task.execution_time_ms = (time.time() - start_time) * 1000
                        await self._emit_terminal_agent_event(
                            task,
                            "agent_failed",
                            {
                                "error": task.error,
                                "run_attempt": len(task.tool_calls_made),
                            },
                        )
                        self.performance[agent_type].update(task)
                        return task
                else:
                    logger.info(f"Task {task.id} routed to remote: {route_reason}")
                    return await self._fallback_to_remote(task)
            elif self.allow_degraded_local_execution:
                use_local = True
                task.degraded_reason = f"{route_reason}; remote fallback disabled, executing locally"
            else:
                task.status = TaskStatus.FAILED
                task.error = f"{route_reason}; remote fallback disabled"
                task.execution_time_ms = (time.time() - start_time) * 1000
                await self._emit_terminal_agent_event(
                    task,
                    "agent_failed",
                    {
                        "error": task.error,
                        "run_attempt": len(task.tool_calls_made),
                    },
                )
                self.performance[agent_type].update(task)
                return task

        if task.degraded_reason is None and "degrading to local" in route_reason.lower():
            task.degraded_reason = route_reason

        logger.info(f"Task {task.id} executing locally: {route_reason}")

        # Execute with tool use loop
        _task_tokens_used = 0
        try:
            result, _task_tokens_used = await self._execute_with_tools(
                task,
                agent_type,
                max_tool_calls,
                role=task.role,
            )

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.execution_time_ms = (time.time() - start_time) * 1000

            # Write completed task fact to MemoryBroker
            if self.fallback_endpoint:
                try:
                    async with httpx.AsyncClient() as _mb_client:
                        await _mb_client.post(
                            f"{self.fallback_endpoint.rstrip('/')}/api/memory/facts",
                            json={
                                "fact": f"Task {task.id} completed: {task.objective[:200]}",
                                "source": "agent-executor",
                                "session_id": task.id,
                                "confidence": 0.8,
                                "role": task.role,
                            },
                            timeout=5.0,
                        )
                except Exception:
                    pass

            # Emit agent_step_complete event for training ingest pipeline
            if task.result and _HYBRID_EVENTS.parent.exists():
                try:
                    _event = json.dumps({
                        "event_type": "agent_step_complete",
                        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                        "query": task.objective,
                        "response": task.result if isinstance(task.result, str) else json.dumps(task.result),
                        "latency_ms": task.execution_time_ms,
                        "session_id": task.id,
                        "tool_calls": len(task.tool_calls_made),
                        "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        "tokens_used": _task_tokens_used,
                        "useful_ratio": 1.0,  # local inference: enable_thinking=False, all tokens are useful
                    })
                    with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
                        _hef.write(_event + "\n")
                except Exception:
                    pass

            logger.info(
                f"Task {task.id} completed: {task.execution_time_ms:.1f}ms, "
                f"{len(task.tool_calls_made)} tool calls"
            )
            # Trigger training ingest in background to capture this completion.
            _ingest_script = _REPO_ROOT_PATH / "ai-stack" / "local-agents" / "training_ingest.py"
            if _ingest_script.exists():
                try:
                    asyncio.create_task(asyncio.to_thread(
                        lambda: __import__("subprocess").run(
                            [sys.executable, str(_ingest_script), "--hours", "2"],
                            capture_output=True, timeout=60,
                        )
                    ))
                except Exception:
                    pass
            await self._emit_terminal_agent_event(
                task,
                "agent_complete",
                {
                    "result_preview": str(task.result)[:200] if task.result is not None else "",
                    "run_attempt": len(task.tool_calls_made),
                },
            )

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.execution_time_ms = (time.time() - start_time) * 1000

            logger.error(f"Task {task.id} failed: {e}")

            # Fallback to remote on failure
            if self.enable_fallback and await self._remote_fallback_available():
                logger.info(f"Falling back to remote for task {task.id}")
                return await self._fallback_to_remote(task)
            if self.enable_fallback and task.error:
                task.error = f"{task.error}; remote fallback unavailable"
            await self._emit_terminal_agent_event(
                task,
                "agent_failed",
                {
                    "error": task.error or str(e),
                    "run_attempt": len(task.tool_calls_made),
                },
            )

        # Update performance tracking
        self.performance[agent_type].update(task)

        return task

    async def _execute_with_tools(
        self,
        task: Task,
        agent_type: AgentType,
        max_tool_calls: int,
        role: Optional[str] = None,
    ) -> Tuple[Any, int]:
        """
        Execute task with tool use loop.

        Tool use loop:
        1. Send prompt + tools to model
        2. Parse response for tool calls
        3. Execute tool calls
        4. Append results to context
        5. Repeat until no more tool calls or max reached
        """
        # Get tools for model.
        # A.6 — _all_tools is the full registry snapshot (hot-swap source, never depleted).
        # _active_tools starts as the full set and may expand mid-loop via _refresh_active_tools.
        # The system prompt is rebuilt whenever _active_tools changes so the model always
        # sees the current tool surface without a full context reload.
        _all_tools = self.tool_registry.get_tools_for_model()
        _active_tools = list(_all_tools)

        # Build initial prompt
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(agent_type, _active_tools, task.objective),
            },
            {
                "role": "user",
                "content": (
                    "Think step by step before calling any tools. "
                    "State your reasoning (Thought: ...) before each tool call.\n\n"
                    + task.objective
                ),
            },
        ]

        # Add context if provided
        if task.context:
            messages.append({
                "role": "system",
                "content": f"Context: {json.dumps(task.context)}",
            })

        # F.3 — working-memory auto-prefetch: inject prior-task scratch notes into the
        # system prompt so the model starts with relevant prior findings without needing
        # to call get_working_memory explicitly. 3 s hard timeout — skip on any error.
        if self.fallback_endpoint:
            try:
                async with httpx.AsyncClient(timeout=3.0) as _wm_client:
                    _wm_resp = await _wm_client.post(
                        f"{self.fallback_endpoint.rstrip('/')}/memory/recall",
                        json={"query": task.objective[:200], "memory_types": ["semantic"], "limit": 3},
                    )
                    if _wm_resp.status_code == 200:
                        _wm_results = _wm_resp.json().get("results", [])[:3]
                        _wm_lines = [
                            f"- {r['content'][:200]}"
                            for r in _wm_results if r.get("content")
                        ]
                        if _wm_lines:
                            messages[0]["content"] += (
                                "\n\nPRIOR WORKING MEMORY:\n" + "\n".join(_wm_lines)
                            )
                            logger.debug("working_memory_prefetch: injected %d entries", len(_wm_lines))
            except Exception:
                pass

        # Tool use loop
        tool_call_count = 0
        total_tokens = 0
        _loop_start = time.time()

        # Phase E — stall watchdog: fire advisory event if no activity for STALL_TIMEOUT seconds.
        # STALL_TIMEOUT_OVERRIDE env var enables short timeouts for CI testing (e.g. 5s).
        # Watchdog is advisory only — never aborts the loop.
        STALL_TIMEOUT = int(os.environ.get("STALL_TIMEOUT_OVERRIDE", "300"))
        _watchdog_last_activity: list[float] = [time.time()]
        _loop = asyncio.get_running_loop()
        _watchdog_handle: asyncio.TimerHandle

        def _cancel_watchdog() -> None:
            if not _watchdog_handle.cancelled():
                _watchdog_handle.cancel()

        def _fire_stall() -> None:
            if task.status != TaskStatus.RUNNING:
                _cancel_watchdog()
                return
            elapsed = time.time() - _watchdog_last_activity[0]
            if elapsed >= STALL_TIMEOUT - 1:
                asyncio.create_task(self._emit_agent_event(
                    task.id, "agent_stall",
                    {"elapsed_s": round(elapsed, 1), "advisory": True},
                    _watchdog_last_activity,
                ))
            # Reschedule for the next interval
            nonlocal _watchdog_handle
            _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)

        _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)

        # Stagnation guard: track (tool_name, result_prefix) for recent calls.
        # Thresholds: 3 for read_file (pure observation, no state change expected after 3
        # identical reads); 5 for run_command and others (allows brief polling loops).
        # If the threshold is exceeded, abort with a degraded result rather than burning
        # the full budget on a runaway loop.
        _recent_tools: list = []
        _STAGNATION_THRESHOLD_READ = 3   # read_file: identical result = definitely stuck
        _STAGNATION_THRESHOLD_OTHER = 5  # run_command etc: allow polling for state change

        # File-not-found stagnation: track paths that returned ok=False.
        # If the same path fails 3 times, the file genuinely does not exist and
        # the model is stuck in a search loop — abort rather than burn the budget.
        _failed_reads: dict = {}  # path → failure count
        _FAILED_READ_LIMIT = 3

        # Per-tool failure stagnation: tracks how many times any single tool has returned
        # success=False (or a non-zero exit_code). If the same tool keeps failing regardless
        # of intervening calls (e.g. harness_health → store_memory → harness_health loop),
        # the observation stagnation guard won't fire because action calls reset the counter.
        # This guard catches persistent infra failures the model cannot fix.
        _tool_failure_counts: dict = {}  # tool_name → failure count
        _TOOL_FAILURE_HARD_LIMIT = 5

        # Exploration stagnation: tracks reads since the last edit/write tool call.
        # Research/analysis/PRD tasks legitimately read 10+ files before writing — use
        # higher limits for those task_types. Implementation tasks default to 8/12.
        _reads_without_edit = 0
        _RESEARCH_TASK_TYPES = frozenset({"research", "analysis", "prd", "reasoning"})
        _is_research_task = (task.task_type or "").lower() in _RESEARCH_TASK_TYPES
        _MAX_READS_WITHOUT_EDIT = 15 if _is_research_task else 8
        _READS_HARD_LIMIT = 25 if _is_research_task else 12
        _exploration_nudge_sent = False
        _validation_passes_without_commit = 0
        _VALIDATION_STALL_NUDGE = 3

        # Observation stagnation: harness query tools (get_hint, query_aidb, etc.) called
        # repeatedly without taking any action. Distinguishable from exploration stagnation
        # (which tracks read_file). Research tasks legitimately query multiple sources, so
        # threshold is higher than read_file's 3. Soft nudge at 6; hard abort at 10.
        _OBSERVATION_QUERY_TOOLS = frozenset({
            "get_hint", "query_aidb", "get_prsi_pending", "get_working_memory",
            "mesh_discovery", "harness_health", "query_context", "get_context",
            "collective_memory_search",
        })
        _OBSERVATION_ACTION_TOOLS = frozenset({
            "store_memory", "run_command", "run_harness_cli", "delegate_to_remote",
            "edit_file", "write_file", "git_add", "git_commit",
        })
        _observations_without_action = 0
        _MAX_OBSERVATIONS_WITHOUT_ACTION = 6
        _OBSERVATIONS_HARD_LIMIT = 10
        _observation_nudge_sent = False

        # Observability: progress sidecar path (set by aq-agent-loop via env var).
        # Updated after every tool call so dashboards and `dispatch.py watch` can
        # read current state without waiting for the final JSON output.
        _progress_file = os.getenv("AGENT_PROGRESS_FILE")
        _steps_file = os.getenv("AGENT_STEPS_FILE")

        def _emit_step_telemetry(tc_result, call_number: int, prose_before: str) -> None:
            """Write per-tool-call telemetry to all three observability surfaces."""
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
            elapsed = time.time() - _loop_start

            # 1. hybrid-events.jsonl — feeds dashboard + training_ingest
            if _HYBRID_EVENTS.parent.exists():
                try:
                    events = []
                    if prose_before.strip():
                        events.append(json.dumps({
                            "event_type": "agent_thinking",
                            "timestamp": ts,
                            "task_id": task.id,
                            "session_id": task.id,
                            "tool_call_number": call_number,
                            "thinking": prose_before[:500],
                            "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        }))
                    events.append(json.dumps({
                        "event_type": "agent_tool_call",
                        "timestamp": ts,
                        "task_id": task.id,
                        "session_id": task.id,
                        "tool_name": tc_result.tool_name,
                        "tool_call_number": call_number,
                        "success": tc_result.status == "completed",
                        "execution_time_ms": tc_result.execution_time_ms,
                        "error": tc_result.error,
                        "elapsed_s": round(elapsed, 1),
                        "objective_preview": task.objective[:120],
                        "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                    }))
                    # tool_result event: successful tool calls → training pairs.
                    # query = task objective + tool invocation context.
                    # response = the actual tool output (training signal for tool-use).
                    if tc_result.status == "completed" and tc_result.result is not None:
                        _args_str = json.dumps(tc_result.arguments)[:200] if hasattr(tc_result, "arguments") else ""
                        try:
                            _res_str = json.dumps(tc_result.result)[:1500]
                        except (TypeError, ValueError):
                            _res_str = str(tc_result.result)[:1500]
                        events.append(json.dumps({
                            "event_type": "tool_result",
                            "timestamp": ts,
                            "task_id": task.id,
                            "session_id": task.id,
                            "tool_name": tc_result.tool_name,
                            "query": f"Task: {task.objective[:200]} | Tool: {tc_result.tool_name}({_args_str})",
                            "response": _res_str,
                            "success": True,
                            "execution_time_ms": tc_result.execution_time_ms,
                            "elapsed_s": round(elapsed, 1),
                            "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        }))
                    with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
                        _hef.write("\n".join(events) + "\n")
                except Exception:
                    pass

            # 2. Progress sidecar — single JSON, overwritten each step
            if _progress_file:
                try:
                    Path(_progress_file).write_text(json.dumps({
                        "task_id": task.id,
                        "status": "running",
                        "tool_call_count": call_number,
                        "last_tool": tc_result.tool_name,
                        "last_tool_success": tc_result.status == "completed",
                        "last_tool_ms": round(tc_result.execution_time_ms or 0, 1),
                        "last_error": tc_result.error,
                        "elapsed_s": round(elapsed, 1),
                        "objective_preview": task.objective[:120],
                        "timestamp": ts,
                    }, indent=2))
                except Exception:
                    pass

            # 3. Steps JSONL — append-only, one line per step, for streaming tail
            if _steps_file:
                try:
                    with open(_steps_file, "a", encoding="utf-8") as _sf:
                        _sf.write(json.dumps({
                            "step": call_number,
                            "tool": tc_result.tool_name,
                            "ok": tc_result.status == "completed",
                            "ms": round(tc_result.execution_time_ms or 0),
                            "elapsed_s": round(elapsed, 1),
                            "ts": ts,
                            "error": tc_result.error,
                        }) + "\n")
                except Exception:
                    pass

        while True:
            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
            await self._emit_agent_event(
                task.id, "agent_step_start",
                {"tool_call_count": tool_call_count},
                _watchdog_last_activity,
            )

            # Context guard — Pinned + Sliding strategy:
            # Qwen3-35B SWA forces full re-prefill on every call (no KV cache reuse
            # across turns). At 10 tok/s prefill on Renoir APU, 7k tokens = ~12 min/call.
            # Target: keep context under ~3000 tokens (~12000 chars at 4 chars/tok).
            #
            # Strategy (avoids the "last-N-pairs" failure mode where the model loses
            # its initial discovery — e.g. which issue to fix — by step 5-6):
            #   PINNED  = messages[0:4]  — system + user + first call + first result
            #             These hold the task objective and initial grep/discovery output.
            #   SLIDING = messages[-4:]  — last 2 assistant+tool pairs (most recent work)
            #   Combined = PINNED + SLIDING when len(messages) > 8.
            #   When len ≤ 8, all messages fit; no pruning needed.
            _CTX_CHAR_BUDGET = 12000  # ~3000 tokens (4 chars/tok)
            _ctx_chars = sum(len((m.get("content") or "")) for m in messages)
            if _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 8:
                pinned = messages[:4]   # system + user + first_assistant + first_tool
                sliding = messages[-4:]  # last 2 assistant+tool pairs
                # When len > 8, pinned ends at index 3 and sliding starts at len-4.
                # The minimum gap between them is (len-4) - 3 = len-7 ≥ 2, so overlap
                # is never possible here. Simple concatenation is correct.
                # F.2 — prune checkpoint: compact the about-to-be-dropped middle messages
                # into working memory before evicting them, so prior findings remain
                # recoverable via get_working_memory. Fire-and-forget.
                if self.fallback_endpoint:
                    _dropped = messages[4:-4]
                    _prune_text = " | ".join(
                        (m.get("content") or "")[:120]
                        for m in _dropped
                        if m.get("role") in {"assistant", "tool"} and m.get("content")
                    )[:600]
                    if _prune_text:
                        asyncio.create_task(
                            _store_prune_checkpoint(self.fallback_endpoint, task.id, _prune_text)
                        )
                messages = pinned + sliding
                logger.debug(
                    "context_prune(pinned+sliding): pinned=%d sliding=%d total=%d chars_before=%d",
                    len(pinned), len(sliding), len(messages), _ctx_chars,
                )
            elif _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 6:
                # Fallback for 6 < len ≤ 8: can't do full pinned+sliding, just shed oldest pair.
                # Verify messages[2:4] form a valid (assistant, tool) pair before dropping —
                # a dangling role:tool without its role:assistant corrupts the conversation graph.
                _m2_role = messages[2].get("role") if len(messages) > 2 else None
                _m3_role = messages[3].get("role") if len(messages) > 3 else None
                if _m2_role == "assistant" and _m3_role == "tool":
                    messages = messages[:2] + messages[4:]
                    logger.debug("context_prune(shed-oldest-pair): messages now %d", len(messages))
                else:
                    logger.debug(
                        "context_prune(shed-oldest-pair): SKIP — messages[2:4] roles=%s/%s not assistant/tool pair",
                        _m2_role, _m3_role,
                    )

            # Call model — use larger budget once tools have been used so that
            # the final synthesis turn (no tool_call in response) isn't capped at
            # the tool-call budget (512).  First call keeps 512 since the model
            # almost always emits a tool call there (short JSON, EOS quick).
            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
            try:
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=call_max_tokens,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            except Exception as _llm_err:
                # Retry once with reduced budget on transient failures (timeout, connection drop).
                logger.warning(
                    "LLM call %d failed (%r), retrying with 512 tokens",
                    tool_call_count + 1, str(_llm_err)[:120],
                )
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=512,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            total_tokens += tok
            if not response.strip():
                # Retry once with a nudge before failing the task. Empty responses happen
                # when the server is cold or the model stalls — a single retry recovers most
                # transient cases without burning the full budget.
                _ctx_chars_at_fail = sum(len((m.get("content") or "")) for m in messages)
                logger.warning(
                    "empty response at call %d (ctx ~%d chars) — retrying once with nudge",
                    tool_call_count + 1, _ctx_chars_at_fail,
                )
                _nudge_messages = messages + [{
                    "role": "user",
                    "content": "Your previous response was empty. Please provide a JSON tool call or a plain-text final answer now.",
                }]
                response, _retry_tok = await self._call_llama(
                    _nudge_messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += _retry_tok
                if response.strip():
                    messages = _nudge_messages
                else:
                    raise RuntimeError(
                        f"LLM returned empty response at call {tool_call_count + 1} "
                        f"(context ~{_ctx_chars_at_fail} chars)"
                    )

            # Parse tool call
            tool_call = self.tool_registry.parse_tool_call_from_llama(response)

            if not tool_call:
                # No tool call — could be prose synthesis (correct) or a truncated/malformed
                # tool-call JSON (model tried to call a tool but got cut off at max_tokens, or
                # the parser rejected it due to embedded newlines in string values).
                # Detect the latter by checking for the {"function" prefix that Qwen3 uses.
                # Fire on ANY turn — tool_call_count > 0 was too narrow; the model can output
                # a JSON tool call as its very first response if the parse failed (e.g. embedded
                # bare newlines in old_string/new_string values).
                if response.lstrip().startswith('{"function"'):
                    logger.warning(
                        "final-response-is-tool-call: response looks like truncated tool call at "
                        "call %d — requesting prose synthesis (max_tokens=256)",
                        tool_call_count,
                    )
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "The previous output was incomplete. "
                            "Write ONE prose sentence starting with 'COMPLETED:' summarising what was done. "
                            "No JSON. No tool calls."
                        ),
                    })
                    prose, syn_tokens = await self._call_llama(
                        messages,
                        role=role,
                        max_tokens=256,
                        task_id=task.id,
                        call_number=tool_call_count + 1,
                    )
                    total_tokens += syn_tokens
                    _cancel_watchdog()
                    return prose.strip() if prose.strip() else response, total_tokens
                # Phase E — agent_synthesis_start: no tool call in response after ≥1 tool calls.
                if tool_call_count > 0:
                    await self._emit_agent_event(
                        task.id, "agent_synthesis_start",
                        {"tool_call_count": tool_call_count},
                        _watchdog_last_activity,
                    )
                _cancel_watchdog()
                return response, total_tokens

            # Phase E — agent_tool_intent: emitted after parsing, before dispatch.
            await self._emit_agent_event(
                task.id, "agent_tool_intent",
                {
                    "tool_name": tool_call.tool_name,
                    "tool_args_preview": json.dumps(
                        tool_call.arguments,
                        sort_keys=True,
                        default=str,
                    )[:200],
                },
                _watchdog_last_activity,
            )

            # Execute tool call
            tool_call.model_id = f"local-{agent_type.value}"
            tool_call.session_id = task.id

            result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Phase E — agent_tool_result: emitted after dispatch returns.
            await self._emit_agent_event(
                task.id, "agent_tool_result",
                {
                    "tool_name": result.tool_name,
                    "result_preview": str(result.result)[:200] if result.result is not None else "",
                },
                _watchdog_last_activity,
            )

            # Format result for model, then sanitize for prompt-injection patterns.
            # context_sanitizer scrubs IGNORE/SYSTEM/OVERRIDE patterns from tool output
            # before it reaches the model context (MIC-G P2 — External Content Injection).
            formatted_result = self.tool_registry.format_tool_result(result)
            if _CONTEXT_SANITIZER_AVAILABLE and _sanitize_tool_result is not None:
                try:
                    formatted_result, _violations = _sanitize_tool_result(
                        formatted_result, source=result.tool_name,
                    )
                    if _violations:
                        logger.warning(
                            "context_sanitizer: %d violation(s) in %s result: %s",
                            len(_violations), result.tool_name, _violations[:3],
                        )
                except Exception as _san_err:
                    logger.debug("context_sanitizer error (non-fatal): %s", _san_err)

            # Stagnation detection: same (tool_name, result_prefix) repeated beyond
            # threshold → model is looping without state change. Abort early via a
            # progress guard. There is intentionally no hard max-tool-call ceiling:
            # context pruning + working-memory checkpoints keep prior findings
            # reachable across long implementation loops.
            # Thresholds are tool-specific:
            #   read_file  → 3: pure observation; identical result 3× = definitely stuck.
            #   run_command → 5: polling loops (e.g. tail, systemctl) legitimately repeat.
            threshold = (
                _STAGNATION_THRESHOLD_READ
                if result.tool_name == "read_file"
                else _STAGNATION_THRESHOLD_OTHER
            )
            _recent_tools.append((result.tool_name, formatted_result[:200]))
            if len(_recent_tools) > threshold:
                _recent_tools.pop(0)
            if (
                len(_recent_tools) == threshold
                and len({t for t, _ in _recent_tools}) == 1   # same tool name
                and len({r for _, r in _recent_tools}) == 1   # same result prefix
            ):
                stagnation_msg = (
                    f"Stagnation detected: '{result.tool_name}' called {threshold} consecutive "
                    f"times with identical result — loop aborted to prevent runaway. "
                    f"Last result prefix: {formatted_result[:300]}"
                )
                logger.warning(
                    "stagnation: tool=%r threshold=%d — aborting loop at call %d",
                    result.tool_name, threshold, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # File-not-found stagnation: if the same path keeps returning an error
            # (file not found), the model is stuck in a search loop. Abort early.
            if result.tool_name == "read_file" and (
                result.status == "failed"
                or (result.result is not None and not result.result.get("success", True))
            ):
                _fp = (result.arguments or {}).get("file_path", "")
                if _fp:
                    _failed_reads[_fp] = _failed_reads.get(_fp, 0) + 1
                    if _failed_reads[_fp] >= _FAILED_READ_LIMIT:
                        stagnation_msg = (
                            f"File-not-found stagnation: '{_fp}' has returned an error "
                            f"{_FAILED_READ_LIMIT} times — file does not exist or is inaccessible. "
                            f"Aborting loop at call {tool_call_count} to prevent runaway search."
                        )
                        logger.warning(
                            "file-not-found stagnation: path=%r failed %d times — aborting at call %d",
                            _fp, _FAILED_READ_LIMIT, tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens

            # Per-tool failure stagnation: track tools that persistently return errors.
            # Catches loops like harness_health(fail)→store_memory(ok)→harness_health(fail)
            # that reset the observation counter but never make forward progress.
            _is_tool_failure = (
                result.status == "failed"
                or (
                    result.result is not None
                    and (
                        not result.result.get("success", True)
                        or result.result.get("exit_code", 0) not in (None, 0)
                        or result.result.get("error") is not None
                    )
                )
            )
            if _is_tool_failure:
                _tool_failure_counts[result.tool_name] = _tool_failure_counts.get(result.tool_name, 0) + 1
                if _tool_failure_counts[result.tool_name] >= _TOOL_FAILURE_HARD_LIMIT:
                    stagnation_msg = (
                        f"Tool-failure stagnation: '{result.tool_name}' has failed "
                        f"{_tool_failure_counts[result.tool_name]} times — persistent infra error, "
                        f"not fixable by the agent. Aborting at call {tool_call_count}."
                    )
                    logger.warning(
                        "tool-failure stagnation: tool=%r failed %d times — aborting at call %d",
                        result.tool_name, _tool_failure_counts[result.tool_name], tool_call_count,
                    )
                    _cancel_watchdog()
                    return stagnation_msg, total_tokens

            # Exploration stagnation: count reads vs edits/writes.
            # Reset counter on any write action; abort if model reads too many files
            # without acting (prevents over-exploration in self-improvement tasks).
            if result.tool_name == "read_file":
                _reads_without_edit += 1
            elif result.tool_name in ("edit_file", "write_file"):
                _reads_without_edit = 0

            # Validation stall: detect repeated validate_before_commit/run_command
            # without any intervening commit. Model validated the code is ready but
            # won't pull the trigger. Nudge it to git_add → git_commit immediately.
            if result.tool_name in ("validate_before_commit", "run_command") and result.status == "completed":
                _validation_passes_without_commit += 1
            elif result.tool_name in ("write_file", "edit_file", "git_add", "git_commit"):
                _validation_passes_without_commit = 0

            # Observation stagnation: track harness query calls vs action calls.
            if result.tool_name in _OBSERVATION_QUERY_TOOLS:
                _observations_without_action += 1
            elif result.tool_name in _OBSERVATION_ACTION_TOOLS:
                _observations_without_action = 0

            if _reads_without_edit >= _READS_HARD_LIMIT:
                stagnation_msg = (
                    f"Exploration stagnation: {_reads_without_edit} consecutive reads without "
                    f"any edit_file or write_file — model stuck in exploration phase. "
                    f"Aborting at tool call {tool_call_count}."
                )
                logger.warning(
                    "exploration stagnation: %d reads without edit — aborting at call %d",
                    _reads_without_edit, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            if _observations_without_action >= _OBSERVATIONS_HARD_LIMIT:
                stagnation_msg = (
                    f"Observation stagnation: {_observations_without_action} consecutive "
                    f"harness query calls (get_hint/query_aidb/etc.) without any action — "
                    f"model is stuck in an observation loop. "
                    f"Aborting at tool call {tool_call_count}."
                )
                logger.warning(
                    "observation stagnation: %d queries without action — aborting at call %d",
                    _observations_without_action, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # Extract the clean JSON from the response so the assistant turn
            # contains only the tool call object, not any leading prose.
            # Qwen3's chat template strips unknown roles — "function" is not
            # in its vocabulary; "tool" is the correct role for tool results.
            brace = response.rfind('{"function"')
            if brace == -1:
                brace = response.rfind("{")
            clean_call = response[brace:].strip() if brace != -1 else response.strip()

            # Capture prose before the tool call JSON (model's reasoning/thinking).
            # This is the text the model emitted BEFORE the structured tool call —
            # the "thinking aloud" surface that would otherwise be invisible.
            prose_before = response[:brace].strip() if brace > 0 else ""

            # Emit per-step telemetry to all observability surfaces (non-blocking).
            _emit_step_telemetry(result, tool_call_count, prose_before)

            messages.append({
                "role": "assistant",
                "content": clean_call,
            })
            messages.append({
                "role": "tool",
                "name": result.tool_name,
                "content": formatted_result,
            })

            # A.6 — hot-swap: expand active tool set based on what the result reveals.
            # Monotonic expansion only (never shrinks). Rebuilds messages[0] (system prompt)
            # when new tools are added so the model sees the expanded surface next call.
            _prev_tool_count = len(_active_tools)
            _active_tools = _refresh_active_tools(
                result.tool_name, formatted_result, _active_tools, _all_tools,
            )
            if len(_active_tools) > _prev_tool_count:
                messages[0] = {
                    "role": "system",
                    "content": self._get_system_prompt(agent_type, _active_tools, task.objective),
                }
                logger.debug(
                    "tool_hotswap: +%d tools after %s (total=%d)",
                    len(_active_tools) - _prev_tool_count, result.tool_name, len(_active_tools),
                )

            # Terminal tool gate: discover_objectives (and any future proposal tools) must
            # not be followed by action — the user must approve first. Inject a synthesis
            # nudge and return immediately so the agent produces a human-readable proposal
            # instead of continuing the tool loop.
            if result.tool_name in _TERMINAL_TOOLS:
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "Present the proposed objectives above as a numbered list. "
                        "For each include: rank, source, priority, and reasoning. "
                        "End with: 'Please reply with a number to select, or describe a different goal.' "
                        "Do NOT call any tools. Do NOT take any action."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                logger.info("terminal_tool_gate: %s → synthesis returned", result.tool_name)
                return synthesis.strip() if synthesis.strip() else formatted_result, total_tokens

            # Observation stall nudge: too many harness query calls without any action.
            if _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION and not _observation_nudge_sent:
                _observation_nudge_sent = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"OBSERVATION STALL: You have called harness query tools "
                        f"({_observations_without_action} times: get_hint, query_aidb, etc.) "
                        "without taking any action. You have enough context. Now act: "
                        "call store_memory with your findings, OR call run_harness_cli, "
                        "OR write/edit a file. Do NOT call get_hint or query_aidb again "
                        "until after you have taken at least one action."
                    ),
                })
                logger.info(
                    "observation-stall nudge injected after %d queries without action at call %d",
                    _observations_without_action, tool_call_count,
                )

            # Soft nudge: inject a user message when reads-without-edit reaches the soft limit.
            # Appears before the next LLM call so the model can course-correct without aborting.
            if _reads_without_edit == _MAX_READS_WITHOUT_EDIT and not _exploration_nudge_sent:
                _exploration_nudge_sent = True
                if _is_research_task:
                    nudge_content = (
                        f"RESEARCH TASK: You have read {_reads_without_edit} files. "
                        f"Continue gathering context as needed (hard limit: {_READS_HARD_LIMIT} reads). "
                        "Begin writing your output file by that point."
                    )
                else:
                    nudge_content = (
                        f"EXPLORATION WARNING: You have read {_reads_without_edit} files without "
                        "making any edits. You have enough context. Execute the required "
                        "edit_file calls from the BEHAVIORAL CONTRACT now."
                    )
                messages.append({"role": "user", "content": nudge_content})
                logger.info(
                    "exploration-nudge injected after %d reads without edit at call %d",
                    _reads_without_edit, tool_call_count,
                )

            # Validation stall nudge: code passed validation N times but model won't commit.
            if _validation_passes_without_commit >= _VALIDATION_STALL_NUDGE:
                messages.append({
                    "role": "user",
                    "content": (
                        f"COMMIT STALL: validate_before_commit or run_command has passed "
                        f"{_validation_passes_without_commit} times without a git_commit. "
                        "The code is ready. If edit_file for the [DONE] marker is failing, "
                        "call git_add now with only the changed code files, then git_commit "
                        "immediately. Do NOT validate again."
                    ),
                })
                logger.info(
                    "validation-stall nudge injected after %d passes without commit at call %d",
                    _validation_passes_without_commit, tool_call_count,
                )
                _validation_passes_without_commit = 0

    async def _call_llama(
        self,
        messages: List[Dict],
        role: Optional[str] = None,
        max_tokens: int = AGENT_TOOL_CALL_MAX_TOKENS,
        task_type: Optional[str] = None,
        task_id: Optional[str] = None,
        call_number: int = 0,
    ) -> Tuple[str, int]:
        """
        Call local llama.cpp server using SSE streaming.

        Uses per-chunk read timeout (LLAMA_CHUNK_TIMEOUT env, default 120s) instead of a
        wall-clock total timeout so long-reasoning tasks never time out as long as tokens
        flow.  Falls back to a non-streaming POST if streaming is explicitly disabled via
        LLAMA_USE_STREAMING=false.

        Args:
            messages: Conversation messages
            task_type: Optional llm_config profile name. When set, profile drives
                temperature, thinking_budget, and enable_thinking. When None, the
                hardcoded temperature=0.2 default is used (no profile).

        Returns:
            (response_text, tokens_used) — tokens_used is total_tokens from the usage chunk.
        """
        use_streaming = _env_flag("LLAMA_USE_STREAMING", default=True)
        chunk_timeout = _env_float("LLAMA_CHUNK_TIMEOUT", default=120.0)

        # Agent tool calls: 512 tokens (50-100 for JSON + 400 for summary).
        # At 1-2 tok/s on Renoir APU, 512 tokens = 256-512s max generation.
        # 4096 would risk 68-minute slot locks when clients disconnect.
        # When task_type is set the profile drives temperature; otherwise use 0.2.
        _temperature: Optional[float] = None if task_type else 0.2

        if not use_streaming:
            # Legacy non-streaming path — 300s wall-clock limit.
            _payload_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role}
            if _temperature is not None:
                _payload_kwargs["temperature"] = _temperature
            if task_type:
                _payload_kwargs["task_type"] = task_type
            payload = build_llama_payload(messages, **_payload_kwargs)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                    timeout=300.0,
                )
                if response.status_code != 200:
                    raise Exception(f"llama.cpp error: {response.status_code} {response.text}")
                data = response.json()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return data["choices"][0]["message"]["content"], tokens

        # Streaming path: collect SSE delta chunks.
        # Pass stream=True so build_llama_payload includes stream_options.include_usage=True,
        # which causes llama.cpp to emit a final usage-only chunk for token tracking.
        # httpx.Timeout(read=chunk_timeout) is per-read-operation (per chunk), not total.
        _stream_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role, "stream": True}
        if _temperature is not None:
            _stream_kwargs["temperature"] = _temperature
        if task_type:
            _stream_kwargs["task_type"] = task_type
        payload = build_llama_payload(messages, **_stream_kwargs)
        timeout = httpx.Timeout(connect=10.0, read=chunk_timeout, write=10.0, pool=5.0)

        collected: List[str] = []
        tokens_used = 0
        progress_file = os.getenv("AGENT_PROGRESS_FILE")
        last_progress_write = 0.0

        def _write_stream_progress(status: str, force: bool = False) -> None:
            nonlocal last_progress_write
            if not progress_file:
                return
            now = time.time()
            if not force and len(collected) % 10 != 0 and now - last_progress_write < 30:
                return
            try:
                Path(progress_file).write_text(json.dumps({
                    "task_id": task_id,
                    "status": status,
                    "tool_call_count": call_number,
                    "llm_stream_chunks": len(collected),
                    "llm_stream_chars": sum(len(part) for part in collected),
                    "max_tokens": max_tokens,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
                }, indent=2))
                last_progress_write = now
            except Exception:
                pass

        try:
            _write_stream_progress("llm_waiting", force=True)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(f"llama.cpp error: {response.status_code} {body.decode()[:200]}")

                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[len("data: "):]
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [{}])
                        if not choices:
                            # Usage-only chunk emitted when stream_options.include_usage=True
                            usage = chunk.get("usage", {})
                            if usage:
                                tokens_used = usage.get("total_tokens", 0)
                                _write_stream_progress("llm_usage", force=True)
                            continue
                        delta = choices[0].get("delta", {})
                        token = delta.get("content") or ""
                        if token:
                            collected.append(token)
                            _write_stream_progress("llm_streaming")
        except httpx.ReadTimeout:
            raise RuntimeError(
                f"LLM prefill/generation timeout: server silent for >{chunk_timeout:.0f}s "
                f"(context may be too large; LLAMA_CHUNK_TIMEOUT={chunk_timeout:.0f})"
            )
        except httpx.ConnectError as _ce:
            raise RuntimeError(f"LLM connection refused at {self.llama_endpoint}: {_ce}") from _ce
        except httpx.NetworkError as _ne:
            raise RuntimeError(f"LLM network error: {_ne}") from _ne

        return "".join(collected), tokens_used

    async def _fallback_to_remote(self, task: Task) -> Task:
        """
        Fallback to remote agent (hybrid coordinator).

        Gap-pattern fix (44x): on provider 429/503, capture error details and
        retry once with a simplified payload (reduced max_tokens, stripped context).
        This prevents the same large payload from triggering the same rate-limit error.

        Args:
            task: Task to execute remotely

        Returns:
            Updated task with remote result
        """
        start_time = time.time()
        task.status = TaskStatus.FALLBACK
        task.assigned_agent = "remote-fallback"
        task.degraded_reason = None

        _RETRY_STATUSES = {429, 503, 502}

        try:
            async with httpx.AsyncClient() as client:
                profile = self._select_remote_profile(task)
                base_payload = self._build_remote_delegate_payload(task, profile)
                delegate_response = await client.post(
                    f"{self.fallback_endpoint}/control/ai-coordinator/delegate",
                    json=base_payload,
                    timeout=self.remote_timeout_seconds,
                )

                if delegate_response.status_code in _RETRY_STATUSES:
                    # Gap rule: log provider-specific failure, simplify payload, retry once.
                    logger.warning(
                        "remote_delegate_provider_error: status=%d detail=%s — retrying with simplified payload",
                        delegate_response.status_code,
                        delegate_response.text[:120],
                    )
                    await asyncio.sleep(2.0)
                    simplified = {
                        "task": task.objective[:800],
                        "profile": "remote-free",
                        "prefer_local": True,
                        "max_tokens": 400,
                    }
                    delegate_response = await client.post(
                        f"{self.fallback_endpoint}/control/ai-coordinator/delegate",
                        json=simplified,
                        timeout=self.remote_timeout_seconds,
                    )

                if delegate_response.status_code == 200:
                    data = delegate_response.json()
                    response_text = self._extract_remote_response_text(data)
                    if response_text:
                        task.result = response_text
                        task.status = TaskStatus.COMPLETED
                    else:
                        task.error = (
                            "Remote delegate returned no response text; "
                            "falling back to /query compatibility path"
                        )
                else:
                    task.error = (
                        f"Remote delegate failed [{delegate_response.status_code}]: "
                        f"{delegate_response.text[:200]}"
                    )

                if task.status != TaskStatus.COMPLETED:
                    response = await client.post(
                        f"{self.fallback_endpoint}/query",
                        json={
                            "query": task.objective,
                            "context": task.context,
                        },
                        timeout=self.remote_timeout_seconds,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        task.result = data.get("response", "")
                        task.status = TaskStatus.COMPLETED
                    else:
                        logger.warning(
                            "remote_query_fallback_error: status=%d detail=%s",
                            response.status_code, response.text[:120],
                        )
                        task.error = f"Remote fallback failed [{response.status_code}]: {response.text[:200]}"
                        task.status = TaskStatus.FAILED

        except Exception as e:
            task.error = f"Remote fallback error: {e}"
            task.status = TaskStatus.FAILED

        task.execution_time_ms = (time.time() - start_time) * 1000

        return task

    def _select_remote_profile(self, task: Task) -> str:
        """Map local-agent fallback tasks onto canonical coordinator profiles."""
        if task.remote_profile:
            return task.remote_profile
        objective = str(task.objective or "")
        if task.requires_flagship or task.quality_critical:
            return "remote-reasoning"
        if _CODE_TASK_RE.search(objective):
            return "remote-coding"
        return "remote-free"

    def _build_remote_delegate_payload(self, task: Task, profile: str) -> Dict[str, Any]:
        """Build coordinator delegate payload for local-agent fallback."""
        payload = {
            "task": task.objective,
            "profile": profile,
            "prefer_local": False,
            "context": dict(task.context or {}),
            "max_tokens": 1200 if profile == "remote-reasoning" else 900,
            "temperature": 0.2,
            "metadata": {
                "entrypoint": "local-agents",
                "task_id": task.id,
                "requires_flagship": task.requires_flagship,
                "quality_critical": task.quality_critical,
                "latency_critical": task.latency_critical,
                "complexity": task.complexity,
            },
        }
        if task.remote_model:
            payload["model"] = task.remote_model
        return payload

    def _extract_remote_response_text(self, data: Any) -> str:
        """Extract assistant text from common coordinator/delegate payloads."""
        if isinstance(data, str):
            return data.strip()
        if not isinstance(data, dict):
            return ""

        for field in ("result", "response", "output", "content", "text"):
            value = data.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        nested_result = data.get("result")
        if isinstance(nested_result, dict):
            nested_text = self._extract_remote_response_text(nested_result)
            if nested_text:
                return nested_text

        nested_data = data.get("data")
        if isinstance(nested_data, dict):
            nested_text = self._extract_remote_response_text(nested_data)
            if nested_text:
                return nested_text

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        return ""

    def _get_system_prompt(
        self,
        agent_type: AgentType,
        tools: List[Dict],
        objective_hint: str = "",
    ) -> str:
        """Get system prompt for agent type with tool descriptions.

        Injects the LOCAL-AGENT.md canonical operating contract (behavioral rules,
        7-step workflow, harness-first principle) so the model runs with its full
        operating instructions, then appends learned gap rules from
        config/harness-prompt-extensions.yaml.

        objective_hint: used to decide whether to include the self-improvement slice
        (~722 tokens). Omitting it for non-SI tasks saves context and avoids model
        confusion when the task has nothing to do with issue fixing.
        """
        _tool_call_format = (
            "\n\nTOOL USE PROTOCOL (strict — follow exactly):\n"
            "When you need to call a tool, respond with ONLY this JSON and nothing else:\n"
            '{"function": "<tool_name>", "arguments": {<param>: <value>, ...}}\n'
            "Rules:\n"
            "- No prose, no markdown, no explanation before or after the JSON.\n"
            "- One tool call per response.\n"
            "- After receiving the tool result, call the next tool or give your final answer.\n"
            "- When the task is complete, respond with plain text (NOT JSON) summarising what was done.\n"
            "- NEVER wrap the JSON in ```json``` code blocks.\n"
        )

        # Compact workflow contract — always injected for AGENT type.
        # Full operating contract: .agent/LOCAL-AGENT.md
        _behavioral_contract = (
            "\n\nBEHAVIORAL CONTRACT:\n"
            "- Read before writing. One change at a time. Stay in the assigned slice.\n"
            "- validate_before_commit MUST pass before git_add. Call it once, then act on result.\n"
            "- ALWAYS use RELATIVE paths (e.g. .agent/memory/issues-backlog.md not /home/user/...).\n"
            "- ALWAYS prefer edit_file over write_file for targeted changes.\n"
            "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
            "  Only use write_file if you must create a new file from scratch.\n"
            "- READ LIMIT: At most 4 read_file calls per slice. After 4 reads, STOP reading — you have enough\n"
            "  context. Call edit_file immediately. If edit_file fails with 'old_string not found', THEN read more.\n"
            "- SURGICAL FINALITY: validation gate passes → commit IMMEDIATELY. No cleanup. No refactor.\n"
            "  Adjacent improvements are separate tasks. One fix per slice.\n"
        )

        # Self-improvement slice instructions (~722 tokens). Only injected when the task
        # explicitly involves issue-fixing / improvement cycles — saves context and avoids
        # confusing the model when it's doing factory, research, or delegation tasks.
        _SI_KEYWORDS = frozenset({"self-improvement", "slice", "issues-backlog", "open issue", "improvement cycle", "fix issue", "aq-qa"})
        _is_si_task = bool(objective_hint and any(kw in objective_hint.lower() for kw in _SI_KEYWORDS))
        _si_slice = (
            "\n\nSELF-IMPROVEMENT SLICE — when asked to run/execute a self-improvement slice:\n"
            "PRE-FLIGHT (mandatory — 3 harness lookups before touching any file):\n"
            "  get_hint(query='<issue-title in 5 words>')        → harness-curated guidance\n"
            "  query_aidb(query='<issue-title>')                 → known fix patterns (63+ seeded)\n"
            "  get_working_memory()                              → prior cycle context\n"
            "  All 3 may return empty — proceed to STEP 1 regardless. NEVER repeat these 3 calls.\n"
            "STEP 1: run_command('grep -n \"\\[OPEN\\]\" .agent/memory/issues-backlog.md')\n"
            "        → pick the first OPEN issue; note its line number N\n"
            "        read_file('.agent/memory/issues-backlog.md', start_line=N, end_line=N+12)\n"
            "STEP 2: announce ONE sentence: 'Fixing: [OPEN] <title> — <one-line description>'\n"
            "STEP 3: edit_file(<target-file>, <exact-old-string>, <exact-new-string>)\n"
            "        Use the EXACT text from the issue 'Action:' line as old_string.\n"
            "        new_string is the replacement. edit_file handles reading internally.\n"
            "        If edit_file fails ('old_string not found'), read_file the target to check the exact text,\n"
            "        then retry edit_file with corrected old_string.\n"
            "STEP 4: validate — run_command('python3 -m py_compile <f>') for .py; 'bash -n <f>' for .sh\n"
            "STEP 5: run_command('scripts/governance/tier0-validation-gate.sh --pre-commit')\n"
            "        If gate fails, fix the problem and re-run. Gate passes → go to STEP 5b immediately.\n"
            "STEP 5b: edit_file('.agent/memory/issues-backlog.md', '[OPEN] <issue-title>', '[DONE] <issue-title>')\n"
            "         Marks the fixed issue as done. Use the exact issue title from STEP 2.\n"
            "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
            "        git_commit('<type>(<scope>): <description>')\n"
            "        git_commit adds Co-Authored-By automatically — do NOT add it in the message.\n"
            "STEP 7: store_memory('<fix-pattern-in-one-sentence>', context_type='error-solutions', importance=0.8)\n"
            "        Seeds fix into AIDB so all agents learn from it.\n"
            "        Example: 'Fix: unconditional break exits loop before JSON fallback — indent break inside if-block.'\n"
            "DONE:   After store_memory returns success, your FINAL output MUST start with:\n"
            "        'COMPLETED: <what was fixed in one sentence>.'\n"
            "        Example: 'COMPLETED: Added validate_before_commit to _SLIM_TOOLS frozenset.'\n"
            "        Output ONLY that sentence. No JSON. No tool calls. STOP.\n"
            "Execute all steps in sequence without stopping. Do NOT target uncommitted changes.\n"
        )

        base_prompt = {
            AgentType.AGENT: (
                "You are AQ, an expert coding and systems developer on NixOS. "
                "You have full tool access: file read/write, shell commands, git operations, "
                "and harness coordination (get_hint, query_aidb, store_memory, get_working_memory). "
                "HARNESS-FIRST: before reading any file or writing any code, call "
                "get_hint + query_aidb(collection='error-solutions') + get_working_memory "
                "to load institutional knowledge. The harness has 63+ seeded fix patterns — "
                "always check before solving from scratch."
            ),
            AgentType.PLANNER: (
                "You are an expert systems planner. Research the environment and produce "
                "accurate, phased implementation plans for NixOS-based AI infrastructure."
            ),
            AgentType.CHAT: (
                "You are AQ, an expert developer helping the user interact with the NixOS AI stack. "
                "Stay grounded in actual system state. Use tools to verify facts before answering."
            ),
            AgentType.EMBEDDED: (
                "You are an expert retrieval agent. Find precise evidence in the "
                "NixOS codebase, documentation, and agentic memory to support architectural decisions."
            ),
        }

        # Progressive disclosure: tool names + required params only (~8 tok/tool).
        # Full schemas live in tool_registry for server-side validation — the model
        # doesn't need them. Context is served on demand via hints/RAG/session-start.
        def _minimal_tool(t: Dict) -> str:
            props = t.get("parameters", {}).get("properties", {})
            req = t.get("parameters", {}).get("required", [])
            all_params = list(props.keys())
            # Show required params starred, optional params unstarred; cap at 4 params
            params = ", ".join(
                f"{k}*" if k in req else k for k in all_params[:4]
            ) + ("..." if len(all_params) > 4 else "")
            return f"{t['name']}({params})"

        tools_desc = "\n\nTools: " + "  ".join(_minimal_tool(t) for t in tools)
        extensions = self._load_prompt_extensions()

        # AGENT type gets behavioral contract always; SI slice only for self-improvement tasks.
        # Non-SI tasks save ~722 tokens (self-improvement step-by-step is irrelevant noise
        # for factory, research, delegation, and monitoring tasks).
        if agent_type == AgentType.AGENT:
            _workflow_contract = _behavioral_contract + (_si_slice if _is_si_task else "")
            return base_prompt[agent_type] + _workflow_contract + _tool_call_format + tools_desc + extensions
        return base_prompt[agent_type] + _tool_call_format + tools_desc + extensions

    def _load_prompt_extensions(self) -> str:
        """Load learned gap rules from harness-prompt-extensions.yaml.

        Returns an empty string on any error so prompt building never fails.
        Rules are injected as a compact advisory section to minimise token overhead.
        Result is cached per-instance — extensions only change with a rebuild, so
        re-reading the YAML on every LLM call in a 252-tool-call agent loop is waste.
        """
        if self._prompt_extensions_cache is not None:
            return self._prompt_extensions_cache
        _REPO_ROOT = Path(__file__).resolve().parents[2]
        ext_path = _REPO_ROOT / "config" / "harness-prompt-extensions.yaml"
        if not ext_path.exists():
            self._prompt_extensions_cache = ""
            return ""
        try:
            import yaml  # type: ignore[import]
            docs = [doc for doc in yaml.safe_load_all(ext_path.read_text()) if isinstance(doc, dict)]
            data = docs[-1] if docs else {}
            rules = data.get("rules") or []
            if not rules:
                self._prompt_extensions_cache = ""
                return ""
            lines = ["\n\n[Learned gap rules — apply these on every task:]"]
            for r in rules[:5]:  # cap at 5 to limit token overhead
                pattern = r.get("pattern", "")
                if pattern:
                    lines.append(f"- {pattern}")
            result = "\n".join(lines)
            self._prompt_extensions_cache = result
            return result
        except Exception as exc:
            logger.debug("harness-prompt-extensions load skipped: %s", exc)
            self._prompt_extensions_cache = ""
            return ""

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all agents"""
        return {
            agent_type.value: perf.to_dict()
            for agent_type, perf in self.performance.items()
        }

    async def _remote_fallback_available(self) -> bool:
        """Check whether the remote fallback path should be used."""
        if not self.enable_fallback or self.offline_mode:
            return False
        if time.time() - self._remote_endpoint_checked_at < 15 and self._remote_endpoint_healthy is not None:
            return self._remote_endpoint_healthy
        healthy = await self._probe_remote_fallback()
        self._remote_endpoint_healthy = healthy
        self._remote_endpoint_checked_at = time.time()
        return healthy

    async def _probe_remote_fallback(self) -> bool:
        """Probe the remote fallback endpoint with a short timeout."""
        health_url = f"{self.fallback_endpoint.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=self.remote_probe_timeout_seconds)
            return response.status_code < 400
        except Exception as exc:
            logger.info("Remote fallback probe failed for %s: %s", health_url, exc)
            return False


    async def execute_collaborative_task(
        self,
        task: Task,
        team_id: str = "default-collective",
        mode: PlanningMode = PlanningMode.PARALLEL
    ) -> Task:
        """
        Execute a task using the multi-agent collaborative collective (MACC).
        Uses CollaborativePlanning to synthesize a multi-phase strategy and
        then executes each phase using specialized agents.
        """
        logger.info("Executing collaborative task: %s (team=%s)", task.objective, team_id)
        _start_time = time.time()

        planner = CollaborativePlanning()
        memory = CollectiveMemory()
        plan_id = planner.create_plan(task.id, team_id, mode=mode)

        # Register team in collective memory
        memory.blackboard_set(team_id, "status", "planning")
        memory.blackboard_set(team_id, "objective", task.objective)

        # Initial 'lead' contribution for planning
        contribution_content = f"Orchestrating collective for task: {task.objective}"
        planner.add_contribution(
            plan_id,
            "antigravity-lead",
            contribution_content,
            confidence=0.9
        )
        memory.blackboard_set(team_id, "latest_contribution", contribution_content)

        # Synthesize and finalize plan (simplified for now)
        plan = await planner.synthesize_plan(plan_id)
        plan = planner.finalize_plan(plan_id)

        task.result = f"Collective Plan Finalized (ID: {plan_id})\n"
        task.result += f"Phases: {len(plan.phases)}\n"

        for i, phase in enumerate(plan.phases):
            task.result += f"Phase {i+1}: [{phase.phase_type.value}] {phase.description}\n"
            # In a full implementation, we would spawn specialized agents here.
            # For the initial integration, we execute the description as a sub-task.
            phase_task = Task(
                id=f"{task.id}-p{i}",
                objective=phase.description,
                complexity=task.complexity / len(plan.phases),
                latency_critical=task.latency_critical
            )
            logger.info("Executing phase %d: %s", i+1, phase.description)
            result = await self.execute_task(phase_task)
            task.result += f"  Status: {result.status.value}\n"
            if result.result:
                task.result += f"  Output: {result.result[:200]}...\n"

        task.status = TaskStatus.COMPLETED
        task.execution_time_ms = (time.time() - _start_time) * 1000

        # Archive collaboration
        phase_outcomes = []
        for i, phase in enumerate(plan.phases):
            phase_outcomes.append(f"phase{i+1}:{phase.phase_type.value}")
        await memory.archive_collaboration(team_id, {
            "task_summary": task.objective,
            "roles": ["orchestrator", "implementer", "reviewer"],
            "outcome": "success",
            "duration_s": task.execution_time_ms / 1000.0,
            "patterns": phase_outcomes,
            "plan_id": plan_id,
        })
        memory.blackboard_set(team_id, "status", "completed")

        return task


# Global executor instance
_EXECUTOR: Optional[LocalAgentExecutor] = None


def get_executor() -> LocalAgentExecutor:
    """Get global executor instance"""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = LocalAgentExecutor()
    return _EXECUTOR


if __name__ == "__main__":
    # Test agent executor
    logging.basicConfig(level=logging.INFO)

    async def test():
        from local_agents import initialize_builtin_tools

        # Initialize tools
        registry = get_registry()
        initialize_builtin_tools(registry)

        # Create executor
        executor = LocalAgentExecutor(tool_registry=registry)

        # Test task
        task = Task(
            id="test-123",
            objective="Get system information and list Python files in current directory",
            complexity=0.3,
            latency_critical=True,
        )

        # Execute task
        result = await executor.execute_task(task)

        print(f"\nTask result:")
        print(f"  Status: {result.status.value}")
        print(f"  Result: {result.result}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
        print(f"  Tool calls: {len(result.tool_calls_made)}")

        # Get performance stats
        stats = executor.get_performance_stats()
        print(f"\nPerformance stats:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
