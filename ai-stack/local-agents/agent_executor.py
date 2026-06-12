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
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# shared/ lives at ai-stack/mcp-servers/shared/ — add parent to path once.
_MCP_SERVERS_PATH = str(Path(__file__).resolve().parents[1] / "mcp-servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)

from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS, AGENT_TASK_MAX_TOKENS  # noqa: E402
from tool_registry import ToolCall, ToolRegistry, get_registry

logger = logging.getLogger(__name__)

_TELEMETRY_DIR = Path(os.getenv("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry"))
_HYBRID_EVENTS = _TELEMETRY_DIR / "hybrid-events.jsonl"

_CODE_TASK_RE = re.compile(
    r"\b(implement|write|code|script|function|class|patch|refactor|debug|fix|test)\b",
    re.IGNORECASE,
)


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
        llama_endpoint: str = os.environ.get("LLAMA_CPP_URL", ""),
        tool_registry: Optional[ToolRegistry] = None,
        enable_fallback: bool = True,
        fallback_endpoint: str = os.environ.get("COORDINATOR_URL", ""),
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
            _env_float("LOCAL_AGENT_REMOTE_TIMEOUT_SECONDS", 60.0)
            if remote_timeout_seconds is None
            else remote_timeout_seconds
        )
        self.remote_probe_timeout_seconds = (
            _env_float("LOCAL_AGENT_REMOTE_PROBE_TIMEOUT_SECONDS", 2.0)
            if remote_probe_timeout_seconds is None
            else remote_probe_timeout_seconds
        )
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

    def route_task(self, task: Task) -> Tuple[bool, str]:
        """
        Route task to local or remote agent.

        Returns:
            (use_local, reason)
        """
        remote_routing_available = self.enable_fallback and not self.offline_mode

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
        max_tool_calls: int = 10,
    ) -> Task:
        """
        Execute a task using local agent with tool use.

        Args:
            task: Task to execute
            agent_type: Type of agent to use
            max_tool_calls: Maximum tool calls allowed

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
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "query": task.objective,
                        "response": task.result if isinstance(task.result, str) else json.dumps(task.result),
                        "latency_ms": task.execution_time_ms,
                        "session_id": task.id,
                        "tool_calls": len(task.tool_calls_made),
                        "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        "tokens_used": _task_tokens_used,
                    })
                    with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
                        _hef.write(_event + "\n")
                except Exception:
                    pass

            logger.info(
                f"Task {task.id} completed: {task.execution_time_ms:.1f}ms, "
                f"{len(task.tool_calls_made)} tool calls"
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
        # Get tools for model
        tools = self.tool_registry.get_tools_for_model()

        # Build initial prompt
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(agent_type, tools),
            },
            {
                "role": "user",
                "content": task.objective,
            },
        ]

        # Add context if provided
        if task.context:
            messages.append({
                "role": "system",
                "content": f"Context: {json.dumps(task.context)}",
            })

        # Tool use loop
        tool_call_count = 0
        total_tokens = 0

        while tool_call_count < max_tool_calls:
            # Context guard: prune oldest assistant+tool pairs when history is large.
            # Keep system message [0] + user message [1] + last N tool call pairs intact.
            # 4 chars/token, 8192 ctx, leave ~2000 tokens for generation headroom.
            _CTX_CHAR_BUDGET = (8192 - 2000) * 4  # ~24768 chars
            _ctx_chars = sum(len(str(m.get("content", ""))) for m in messages)
            if _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 4:
                # Drop the oldest assistant+tool pair (indices 2+3 after system+user)
                messages = messages[:2] + messages[4:]
                logger.debug("context_prune: dropped oldest tool pair, messages now %d", len(messages))

            # Call model — use larger budget once tools have been used so that
            # the final synthesis turn (no tool_call in response) isn't capped at
            # the tool-call budget (512).  First call keeps 512 since the model
            # almost always emits a tool call there (short JSON, EOS quick).
            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
            try:
                response, tok = await self._call_llama(messages, role=role, max_tokens=call_max_tokens)
            except Exception as _llm_err:
                # Retry once with reduced budget on transient failures (timeout, connection drop).
                logger.warning(
                    "LLM call %d failed (%r), retrying with 512 tokens",
                    tool_call_count + 1, str(_llm_err)[:120],
                )
                response, tok = await self._call_llama(messages, role=role, max_tokens=512)
            total_tokens += tok
            if not response.strip():
                raise RuntimeError(
                    f"LLM returned empty response at call {tool_call_count + 1} "
                    f"(context ~{sum(len(str(m.get('content','') or '')) for m in messages)} chars)"
                )

            # Parse tool call
            tool_call = self.tool_registry.parse_tool_call_from_llama(response)

            if not tool_call:
                # No tool call, return response as final answer
                return response, total_tokens

            # Execute tool call
            tool_call.model_id = f"local-{agent_type.value}"
            tool_call.session_id = task.id

            result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Format result for model
            formatted_result = self.tool_registry.format_tool_result(result)

            # Extract the clean JSON from the response so the assistant turn
            # contains only the tool call object, not any leading prose.
            # Qwen3's chat template strips unknown roles — "function" is not
            # in its vocabulary; "tool" is the correct role for tool results.
            brace = response.rfind('{"function"')
            if brace == -1:
                brace = response.rfind("{")
            clean_call = response[brace:].strip() if brace != -1 else response.strip()

            messages.append({
                "role": "assistant",
                "content": clean_call,
            })
            messages.append({
                "role": "tool",
                "name": result.tool_name,
                "content": formatted_result,
            })

        # Max tool calls reached, return current state
        logger.warning(f"Task {task.id} reached max tool calls ({max_tool_calls})")
        return f"Task incomplete: reached max tool calls ({max_tool_calls})", total_tokens

    async def _call_llama(self, messages: List[Dict], role: Optional[str] = None, max_tokens: int = AGENT_TOOL_CALL_MAX_TOKENS) -> Tuple[str, int]:
        """
        Call local llama.cpp server using SSE streaming.

        Uses per-chunk read timeout (LLAMA_CHUNK_TIMEOUT env, default 120s) instead of a
        wall-clock total timeout so long-reasoning tasks never time out as long as tokens
        flow.  Falls back to a non-streaming POST if streaming is explicitly disabled via
        LLAMA_USE_STREAMING=false.

        Args:
            messages: Conversation messages

        Returns:
            (response_text, tokens_used) — tokens_used is total_tokens from the usage chunk.
        """
        use_streaming = _env_flag("LLAMA_USE_STREAMING", default=True)
        chunk_timeout = _env_float("LLAMA_CHUNK_TIMEOUT", default=120.0)

        # Agent tool calls: 512 tokens (50-100 for JSON + 400 for summary).
        # At 1-2 tok/s on Renoir APU, 512 tokens = 256-512s max generation.
        # 4096 would risk 68-minute slot locks when clients disconnect.

        if not use_streaming:
            # Legacy non-streaming path — 300s wall-clock limit.
            payload = build_llama_payload(
                messages,
                max_tokens=max_tokens,
                temperature=0.2,
                role=role,
            )
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
        payload = build_llama_payload(
            messages,
            max_tokens=max_tokens,
            temperature=0.2,
            role=role,
            stream=True,
        )
        timeout = httpx.Timeout(connect=10.0, read=chunk_timeout, write=10.0, pool=5.0)

        collected: List[str] = []
        tokens_used = 0

        try:
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
                            continue
                        delta = choices[0].get("delta", {})
                        token = delta.get("content") or ""
                        if token:
                            collected.append(token)
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
        objective = str(task.objective or "")
        if task.requires_flagship or task.quality_critical:
            return "remote-reasoning"
        if _CODE_TASK_RE.search(objective):
            return "remote-coding"
        return "remote-free"

    def _build_remote_delegate_payload(self, task: Task, profile: str) -> Dict[str, Any]:
        """Build coordinator delegate payload for local-agent fallback."""
        return {
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

    def _get_system_prompt(self, agent_type: AgentType, tools: List[Dict]) -> str:
        """Get system prompt for agent type with tool descriptions.

        Injects the LOCAL-AGENT.md canonical operating contract (behavioral rules,
        7-step workflow, harness-first principle) so the model runs with its full
        operating instructions, then appends learned gap rules from
        config/harness-prompt-extensions.yaml.
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

        # Compact workflow contract — kept short to avoid large prefill on constrained APU.
        # Full operating contract: .agent/LOCAL-AGENT.md
        _workflow_contract = (
            "\n\nBEHAVIORAL CONTRACT:\n"
            "- Read before writing. One change at a time. Stay in the assigned slice.\n"
            "- validate_before_commit MUST pass before git_add. Call it once, then act on result.\n"
            "- ALWAYS use RELATIVE paths (e.g. .agent/memory/issues-backlog.md not /home/user/...).\n"
            "- Do NOT re-read a file already in your context. Use start_line/end_line for targeted reads.\n"
            "\n\nSELF-IMPROVEMENT SLICE — when asked to run/execute a self-improvement slice:\n"
            "STEP 1: run_command('grep -n \"\\[OPEN\\]\" .agent/memory/issues-backlog.md')\n"
            "        → pick the first OPEN issue; note its line number N\n"
            "        read_file('.agent/memory/issues-backlog.md', start_line=N, end_line=N+12)\n"
            "STEP 2: announce ONE sentence: 'Fixing: [OPEN] <title> — <one-line description>'\n"
            "STEP 3: read_file(<target-file-from-issue>) then write_file to implement the fix\n"
            "STEP 4: validate — run_command('python3 -m py_compile <f>') for .py; 'bash -n <f>' for .sh\n"
            "STEP 5: run_command('scripts/governance/tier0-validation-gate.sh --pre-commit')\n"
            "        If gate fails, fix the problem and re-run. If gate passes, proceed immediately.\n"
            "STEP 6: git_add([<files>]) then git_commit('<type>(<scope>): <description>')\n"
            "        git_commit adds Co-Authored-By automatically — do NOT add it in the message.\n"
            "STEP 7: store_memory('<fix-pattern-in-one-sentence>', context_type='error-solutions', importance=0.8)\n"
            "        This seeds the fix into AIDB so Gemini, Codex, and future local sessions can learn from it.\n"
            "        Example: 'Fix: unconditional break in for-loop exits before JSON fallback is read — indent break inside if-block.'\n"
            "DONE:   After store_memory returns, output ONE sentence:\n"
            "        'Committed <hash-prefix>: <what changed> — gate passed, memory seeded, ready for review.'\n"
            "        STOP. Do not call any more tools.\n"
            "Execute all steps without stopping. Do NOT target uncommitted git changes.\n"
        )

        base_prompt = {
            AgentType.AGENT: (
                "You are AQ, an expert coding and systems developer on NixOS. "
                "You have full tool access: file read/write, shell commands, git operations. "
                "The harness is your force multiplier — use RAG, hints, and memory to extend "
                "your effective reasoning beyond what fits in context."
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

        # AGENT type gets the full workflow contract; other types get only tool call format
        if agent_type == AgentType.AGENT:
            return base_prompt[agent_type] + _workflow_contract + _tool_call_format + tools_desc + extensions
        return base_prompt[agent_type] + _tool_call_format + tools_desc + extensions

    def _load_prompt_extensions(self) -> str:
        """Load learned gap rules from harness-prompt-extensions.yaml.

        Returns an empty string on any error so prompt building never fails.
        Rules are injected as a compact advisory section to minimise token overhead.
        """
        _REPO_ROOT = Path(__file__).resolve().parents[2]
        ext_path = _REPO_ROOT / "config" / "harness-prompt-extensions.yaml"
        if not ext_path.exists():
            return ""
        try:
            import yaml  # type: ignore[import]
            docs = [doc for doc in yaml.safe_load_all(ext_path.read_text()) if isinstance(doc, dict)]
            data = docs[-1] if docs else {}
            rules = data.get("rules") or []
            if not rules:
                return ""
            lines = ["\n\n[Learned gap rules — apply these on every task:]"]
            for r in rules[:5]:  # cap at 5 to limit token overhead
                pattern = r.get("pattern", "")
                if pattern:
                    lines.append(f"- {pattern}")
            return "\n".join(lines)
        except Exception as exc:
            logger.debug("harness-prompt-extensions load skipped: %s", exc)
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
        from tool_registry import initialize_builtin_tools

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
