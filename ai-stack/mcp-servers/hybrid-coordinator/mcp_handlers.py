"""
MCP tool definitions and dispatch for hybrid-coordinator.

Contains the list_tools constant and call_tool dispatch logic.
The app object (@app.list_tools / @app.call_tool) stays in server.py;
server.py wraps these helpers in thin decorator stubs.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import mcp_handlers
    mcp_handlers.init(augment_query_fn=..., ...)

    @app.list_tools()
    async def list_tools():
        return mcp_handlers.TOOL_DEFINITIONS

    @app.call_tool()
    async def call_tool(name, arguments):
        return await mcp_handlers.dispatch_tool(name, arguments)
"""

import json
import logging
import os
from pathlib import Path
import pwd
import shutil
import time as _time
from typing import Any, Callable, Dict, List, Optional
import asyncio

from mcp.types import TextContent, Tool
from shared.tool_audit import write_audit_entry as _write_audit_entry
from tooling_manifest import build_tooling_manifest, workflow_tool_catalog
from memory_manager import coerce_memory_summary, normalize_memory_type

logger = logging.getLogger("hybrid-coordinator")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_AQ_QA_SCRIPT = _REPO_ROOT / "scripts" / "ai" / "aq-qa"
_FLAGSHIP_CLI_SMOKE_SCRIPT = _REPO_ROOT / "scripts" / "testing" / "smoke-flagship-cli-surfaces.sh"
_QA_PHASE_ALIASES = {
    "phase0": "0",
    "phase1": "1",
    "phase2": "2",
    "phase3": "3",
    "phase4": "4",
    "phase5": "5",
    "phase6": "6",
    "phase7": "7",
    "phase8": "8",
    "phase9": "9",
    "phase10": "10",
    "all": "all",
}


def _resolve_bash_binary() -> str:
    candidates = [
        os.environ.get("BASH"),
        shutil.which("bash"),
        "/run/current-system/sw/bin/bash",
        "/bin/bash",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("bash binary not found for aq-qa execution")


def _resolve_python3_binary() -> str:
    candidates = [
        os.environ.get("PYTHON3"),
        shutil.which("python3"),
        "/run/current-system/sw/bin/python3",
        "/usr/bin/python3",
        "/bin/python3",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("python3 binary not found for aq-qa execution")


def _build_qa_exec_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        operator_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        operator_home = Path(env.get("HOME") or _REPO_ROOT)
    env.setdefault("HOME", str(operator_home))

    bash_bin = _resolve_bash_binary()
    python3_bin = _resolve_python3_binary()
    path_entries = [
        str(Path(bash_bin).parent),
        str(Path(python3_bin).parent),
        str(operator_home / ".nix-profile" / "bin"),
        str(operator_home / ".npm-global" / "bin"),
        str(operator_home / ".local" / "bin"),
        str(operator_home / ".cargo" / "bin"),
        "/run/current-system/sw/bin",
        "/usr/bin",
        "/bin",
    ]
    existing_path = env.get("PATH", "")
    if existing_path:
        path_entries.extend(segment for segment in existing_path.split(":") if segment)
    env["PATH"] = ":".join(dict.fromkeys(path_entries))
    env.setdefault("BASH", bash_bin)
    env.setdefault("PYTHON3", python3_bin)
    return env


def _normalize_qa_phase(value: Any) -> str:
    phase = str(value or "0").strip().lower()
    if not phase:
        return "0"
    return _QA_PHASE_ALIASES.get(phase, phase)


async def run_qa_check_as_dict(arguments: Dict[str, Any]) -> Dict[str, Any]:
    phase = _normalize_qa_phase(arguments.get("phase", "0"))
    output_format = str(arguments.get("format", "json")).strip().lower()
    include_sudo = bool(arguments.get("include_sudo", False))
    capability_only = bool(arguments.get("capability_only", False))

    # Batch 2.1: Increase default timeout and add phase-specific timeouts
    # Phase 2/3 runtime checks take longer due to package/confinement loops
    phase_timeouts = {
        "0": 90,   # Smoke tests
        "1": 120,  # Infrastructure checks
        "2": 180,  # Runtime/package/confinement loops
        "3": 180,  # AppArmor/confinement loops
        "4": 120,  # Context engineering checks
        "5": 120,  # Security hardening checks
        "6": 120,  # Monitoring checks
        "7": 120,  # Self-improvement checks
        "8": 180,  # End-to-end workflow checks
        "9": 120,  # Optimisation checks
        "10": 120,  # Regression checks
        "all": 900,  # Full QA batch
    }
    default_timeout = phase_timeouts.get(phase, 120)
    timeout_seconds = int(arguments.get("timeout_seconds") or default_timeout)
    if timeout_seconds < 5:
        timeout_seconds = 5
    if output_format not in {"json", "text"}:
        raise ValueError("format must be 'json' or 'text'")
    if phase not in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "all"}:
        raise ValueError("phase must be one of 0-10 or all")
    if capability_only and phase != "0":
        raise ValueError("capability_only mode is only supported for phase 0")
    if not _AQ_QA_SCRIPT.exists():
        raise FileNotFoundError(f"aq-qa script not found at {_AQ_QA_SCRIPT}")

    env = _build_qa_exec_env()
    if capability_only:
        if not _FLAGSHIP_CLI_SMOKE_SCRIPT.exists():
            raise FileNotFoundError(f"flagship CLI smoke script not found at {_FLAGSHIP_CLI_SMOKE_SCRIPT}")
        cmd = [_resolve_bash_binary(), str(_FLAGSHIP_CLI_SMOKE_SCRIPT)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(_REPO_ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=min(timeout_seconds, 30))
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError("capability-only QA smoke timed out")
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        passed = 1 if proc.returncode == 0 else 0
        failed = 0 if proc.returncode == 0 else 1
        result: Dict[str, Any] = {
            "status": "ok" if proc.returncode == 0 else "failed",
            "phase": phase,
            "format": output_format,
            "exit_code": int(proc.returncode),
            "command": cmd,
            "stdout": stdout_text if output_format == "text" else None,
            "stderr": stderr_text or None,
            "qa_result": {
                "phase": phase,
                "scope": "capability_only",
                "passed": passed,
                "failed": failed,
                "skipped": 0,
                "duration_s": 0,
                "tests": [
                    {
                        "id": "0.6.1",
                        "status": "PASS" if proc.returncode == 0 else "FAIL",
                        "description": "flagship agent CLI help smokes",
                    }
                ],
            },
        }
        if output_format == "text":
            result["stdout"] = stdout_text
        return result

    cmd = [_resolve_bash_binary(), str(_AQ_QA_SCRIPT), phase]
    if output_format == "json":
        cmd.append("--json")
    if include_sudo:
        cmd.append("--sudo")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"aq-qa timed out after {timeout_seconds}s")

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    result: Dict[str, Any] = {
        "status": "ok" if proc.returncode == 0 else "failed",
        "phase": phase,
        "format": output_format,
        "exit_code": int(proc.returncode),
        "command": cmd,
        "stdout": stdout_text if output_format == "text" else None,
        "stderr": stderr_text or None,
    }
    if output_format == "json":
        try:
            result["qa_result"] = json.loads(stdout_text or "{}")
        except json.JSONDecodeError as exc:
            result["status"] = "error"
            result["parse_error"] = str(exc)
            result["stdout"] = stdout_text
    return result


def _write_audit(
    tool_name: str,
    outcome: str,
    error_message: "str | None",
    latency_ms: float,
    parameters: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Delegate to shared audit module (Phase 12.3.2: writes via sidecar socket)."""
    _write_audit_entry(
        service='hybrid-coordinator',
        tool_name=tool_name,
        caller_identity='anonymous',
        parameters=parameters,
        risk_tier='low',
        outcome=outcome,
        error_message=error_message,
        latency_ms=latency_ms,
        metadata=metadata,
    )

# ---------------------------------------------------------------------------
# Injected dependencies (set via init())
# ---------------------------------------------------------------------------
_augment_query: Optional[Callable] = None
_route_search: Optional[Callable] = None
_hybrid_search: Optional[Callable] = None
_store_memory: Optional[Callable] = None
_recall_memory: Optional[Callable] = None
_run_harness_eval: Optional[Callable] = None
_record_learning_feedback: Optional[Callable] = None
_track_interaction: Optional[Callable] = None
_update_outcome: Optional[Callable] = None
_generate_dataset: Optional[Callable] = None
_embed_fn: Optional[Callable] = None
_qdrant: Optional[Any] = None
_HARNESS_STATS: Optional[Dict] = None


def init(
    *,
    augment_query_fn: Callable,
    route_search_fn: Callable,
    hybrid_search_fn: Callable,
    store_memory_fn: Callable,
    recall_memory_fn: Callable,
    run_harness_eval_fn: Callable,
    record_learning_feedback_fn: Callable,
    track_interaction_fn: Callable,
    update_outcome_fn: Callable,
    generate_dataset_fn: Callable,
    embed_fn: Callable,
    qdrant_client: Any,
    harness_stats: Dict,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _augment_query, _route_search, _hybrid_search, _store_memory, _recall_memory
    global _run_harness_eval, _record_learning_feedback, _track_interaction, _update_outcome
    global _generate_dataset, _embed_fn, _qdrant, _HARNESS_STATS
    _augment_query = augment_query_fn
    _route_search = route_search_fn
    _hybrid_search = hybrid_search_fn
    _store_memory = store_memory_fn
    _recall_memory = recall_memory_fn
    _run_harness_eval = run_harness_eval_fn
    _record_learning_feedback = record_learning_feedback_fn
    _track_interaction = track_interaction_fn
    _update_outcome = update_outcome_fn
    _generate_dataset = generate_dataset_fn
    _embed_fn = embed_fn
    _qdrant = qdrant_client
    _HARNESS_STATS = harness_stats


# ---------------------------------------------------------------------------
# Tool definitions (pure data — no dependencies)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name="augment_query",
        description="Augment a query with relevant context from local knowledge base",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to augment with context",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Type of agent requesting context (local or remote)",
                    "enum": ["local", "remote"],
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="track_interaction",
        description="Record an interaction for learning and analysis",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
                "agent_type": {"type": "string"},
                "model_used": {"type": "string"},
                "context_ids": {"type": "array", "items": {"type": "string"}},
                "tokens_used": {"type": "integer"},
                "latency_ms": {"type": "integer"},
            },
            "required": ["query", "response", "agent_type", "model_used"],
        },
    ),
    Tool(
        name="update_outcome",
        description="Update interaction outcome and trigger learning",
        inputSchema={
            "type": "object",
            "properties": {
                "interaction_id": {"type": "string"},
                "outcome": {
                    "type": "string",
                    "enum": ["success", "partial", "failure"],
                },
                "user_feedback": {"type": "integer", "minimum": -1, "maximum": 1},
            },
            "required": ["interaction_id", "outcome"],
        },
    ),
    Tool(
        name="generate_training_data",
        description="Export high-value interactions to JSONL interaction archive",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="search_context",
        description="Search specific collection for relevant context",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collection": {
                    "type": "string",
                    "enum": [
                        "codebase-context",
                        "skills-patterns",
                        "error-solutions",
                        "best-practices",
                    ],
                },
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query", "collection"],
        },
    ),
    Tool(
        name="hybrid_search",
        description="Run hybrid search combining vector similarity and keyword matching",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collections": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 5},
                "keyword_limit": {"type": "integer", "default": 5},
                "score_threshold": {"type": "number", "default": 0.7},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="route_search",
        description="Route a query to SQL, semantic, keyword, tree, or hybrid search",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                    "default": "auto",
                },
                "prefer_local": {"type": "boolean", "default": True},
                "context": {"type": "object"},
                "limit": {"type": "integer", "default": 5},
                "keyword_limit": {"type": "integer", "default": 5},
                "score_threshold": {"type": "number", "default": 0.7},
                "generate_response": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="store_agent_memory",
        description="Store episodic, semantic, or procedural memory items",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": ["episodic", "semantic", "procedural"],
                },
                "summary": {"type": "string"},
                "content": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["memory_type", "summary"],
        },
    ),
    Tool(
        name="recall_agent_memory",
        description="Recall memory using hybrid or tree retrieval mode",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "memory_types": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 8},
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["hybrid", "tree"],
                    "default": "hybrid",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="run_harness_eval",
        description="Run deterministic harness evaluation with scorecard output",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                    "default": "auto",
                },
                "expected_keywords": {"type": "array", "items": {"type": "string"}},
                "max_latency_ms": {"type": "integer"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="harness_stats",
        description="Get cumulative harness evaluation statistics and failure taxonomy",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="learning_feedback",
        description="Store user corrections and feedback for learning",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "correction": {"type": "string"},
                "original_response": {"type": "string"},
                "interaction_id": {"type": "string"},
                "rating": {"type": "integer", "minimum": -1, "maximum": 1},
                "tags": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string"},
                "variant": {"type": "string"},
            },
            "required": ["query", "correction"],
        },
    ),
    # Phase 19.3.1 — get_workflow_hints: agent-agnostic ranked hint retrieval
    Tool(
        name="get_workflow_hints",
        description=(
            "Get ranked workflow hints, prompt templates, and recommendations for the current "
            "task context. Call this BEFORE starting a complex task (NixOS module changes, "
            "systemd service additions, aider code generation, retrieval tuning) to receive "
            "optimized patterns derived from historical performance data and the prompt registry. "
            "Returns prompt template snippets, CLAUDE.md workflow rules, and recurring gap topics "
            "relevant to the query. Works for all agent types."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Task description or partial query to match hints against",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "File extension or domain context to filter hints "
                        "(e.g. '.nix', '.py', 'nixos', 'rag', 'aider', 'systemd')"
                    ),
                    "default": "",
                },
                "max_hints": {
                    "type": "integer",
                    "description": "Maximum number of hints to return (default: 3)",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="tooling_manifest",
        description=(
            "Return a compact, code-execution-friendly tool manifest for the current task. "
            "Use this when you want the minimal tool surface, import-on-demand guidance, "
            "and bounded result budgets instead of loading full tool schemas into context."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Task objective used to tailor the manifest",
                },
                "runtime": {
                    "type": "string",
                    "enum": ["python", "typescript"],
                    "default": "python",
                },
                "max_tools": {
                    "type": "integer",
                    "default": 6,
                    "minimum": 1,
                    "maximum": 20,
                },
                "max_result_chars": {
                    "type": "integer",
                    "default": 4000,
                    "minimum": 256,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="run_qa_check",
        description=(
            "Run the repo QA phase runner (`aq-qa`) with bounded timeout and return "
            "structured validation output. Use this for service health, runtime smoke, "
            "or infrastructure checks during validation and reviewer gates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "description": "QA phase to run: 0-10, phase0-phase10, or all",
                    "default": "0",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 5,
                    "maximum": 600,
                },
                "include_sudo": {
                    "type": "boolean",
                    "default": False,
                },
            },
        },
    ),
    # Phase 5 — Model Optimization Tools
    Tool(
        name="capture_training_example",
        description="Capture a high-quality interaction for model training data",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user query"},
                "response": {"type": "string", "description": "The model response"},
                "outcome": {"type": "string", "enum": ["success", "partial", "failure", "unknown"]},
                "user_feedback": {"type": "integer", "minimum": -1, "maximum": 1},
                "latency_ms": {"type": "number"},
            },
            "required": ["query", "response"],
        },
    ),
    Tool(
        name="flush_training_data",
        description="Save pending training examples to disk for fine-tuning",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_training_data_stats",
        description="Get statistics on captured training data",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="start_finetuning_job",
        description="Create a fine-tuning job for local model optimization",
        inputSchema={
            "type": "object",
            "properties": {
                "base_model": {"type": "string", "description": "Base model to fine-tune"},
                "task_type": {
                    "type": "string",
                    "enum": ["code_generation", "code_review", "debugging", "documentation", "general"],
                    "default": "general",
                },
                "training_data_path": {"type": "string", "description": "Path to training data"},
            },
            "required": ["base_model"],
        },
    ),
    Tool(
        name="get_finetuning_jobs",
        description="List fine-tuning jobs and their status",
        inputSchema={
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "enum": ["pending", "running", "completed", "failed"]},
            },
        },
    ),
    Tool(
        name="record_model_performance",
        description="Record performance metrics for a model",
        inputSchema={
            "type": "object",
            "properties": {
                "model_id": {"type": "string"},
                "task_type": {"type": "string"},
                "accuracy": {"type": "number"},
                "latency_ms": {"type": "number"},
                "quality_score": {"type": "number"},
            },
            "required": ["model_id", "task_type", "accuracy", "latency_ms", "quality_score"],
        },
    ),
    Tool(
        name="get_model_performance",
        description="Get model performance metrics and trends",
        inputSchema={
            "type": "object",
            "properties": {
                "model_id": {"type": "string", "description": "Specific model ID or omit for all models"},
            },
        },
    ),
    Tool(
        name="get_optimization_readiness",
        description="Get Phase 5 model optimization readiness status",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="generate_synthetic_training_data",
        description="Generate synthetic training data into writable runtime storage",
        inputSchema={
            "type": "object",
            "properties": {
                "target_examples": {"type": "integer", "minimum": 1, "default": 50},
                "categories": {"type": "array", "items": {"type": "string"}},
                "strategies": {"type": "array", "items": {"type": "string"}},
                "min_quality": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.7},
            },
        },
    ),
    Tool(
        name="select_active_learning_examples",
        description="Select the most valuable training examples using active learning",
        inputSchema={
            "type": "object",
            "properties": {
                "budget": {"type": "integer", "minimum": 1, "default": 25},
                "strategy": {
                    "type": "string",
                    "enum": ["uncertainty", "diversity", "qbc", "expected_gradient", "hybrid"],
                    "default": "hybrid",
                },
                "candidate_paths": {"type": "array", "items": {"type": "string"}},
            },
        },
    ),
    Tool(
        name="run_distillation_pipeline",
        description="Run a bounded distillation, quantization, and pruning pipeline",
        inputSchema={
            "type": "object",
            "properties": {
                "teacher_model": {"type": "string"},
                "student_model": {"type": "string"},
                "training_data_path": {"type": "string"},
                "quantization_method": {
                    "type": "string",
                    "enum": ["int8", "int4", "gptq", "awq", "gguf"],
                    "default": "gguf",
                },
                "quantization_bits": {"type": "integer", "minimum": 4, "maximum": 8, "default": 4},
                "pruning_sparsity": {"type": "number", "minimum": 0.0, "maximum": 0.95, "default": 0.2},
                "enable_speculative_decoding": {"type": "boolean", "default": True},
            },
            "required": ["teacher_model", "student_model"],
        },
    ),
    Tool(
        name="get_advanced_features_readiness",
        description="Get readiness and activation status for advanced Phase 6-10 feature primitives",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_agent_quality_profiles",
        description="Get composite remote-agent quality profiles for offloading decisions",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="select_failover_remote_agent",
        description="Select a failover-capable remote agent using quality-aware tier escalation",
        inputSchema={
            "type": "object",
            "properties": {
                "min_composite_score": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.55},
            },
        },
    ),
    Tool(
        name="get_agent_benchmarks",
        description="Get observed agent-pool performance benchmarks",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="optimize_prompt_template",
        description="Generate an optimized prompt template variant for a task",
        inputSchema={
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "task": {"type": "string"},
                "context": {"type": "string"},
                "constraints": {"type": "string"},
            },
            "required": ["task_type", "task"],
        },
    ),
    Tool(
        name="generate_dynamic_prompt",
        description="Generate a task-adaptive prompt variant from a raw query",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="record_prompt_variant_outcome",
        description="Record an A/B outcome for an optimized prompt variant",
        inputSchema={
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "variant_id": {"type": "string"},
                "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["task_type", "variant_id", "score"],
        },
    ),
    Tool(
        name="get_prompt_ab_stats",
        description="Get current prompt-template A/B statistics",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="select_context_tier",
        description="Select an appropriate context-loading tier for a query",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_tier_selection_stats",
        description="Get context-tier selection statistics",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="analyze_failure_patterns",
        description="Analyze failure patterns without persisting a full capability-gap record",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
                "error_message": {"type": "string"},
                "user_feedback": {"type": "object"},
            },
            "required": ["query", "response"],
        },
    ),
    Tool(
        name="get_capability_gap_stats",
        description="Get capability-gap statistics and failure-pattern coverage",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="record_learning_signal",
        description="Record a learning signal into the advanced online-learning module",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
                "outcome": {"type": "string"},
                "explicit_score": {"type": "number"},
            },
            "required": ["query", "response", "outcome"],
        },
    ),
    Tool(
        name="get_learning_recommendations",
        description="Get recommendations based on recorded online-learning patterns",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_advanced_learning_stats",
        description="Get learning statistics from the advanced online-learning module",
        inputSchema={"type": "object", "properties": {}},
    ),
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def dispatch_tool(name: str, arguments: Any) -> List[TextContent]:
    """Dispatch an MCP tool call by name."""
    _start = _time.perf_counter()
    try:
        if name == "augment_query":
            query = arguments.get("query", "")
            agent_type = arguments.get("agent_type", "remote")
            result = await _augment_query(query, agent_type)
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "track_interaction":
            interaction_id = await _track_interaction(
                query=arguments.get("query", ""),
                response=arguments.get("response", ""),
                agent_type=arguments.get("agent_type", "unknown"),
                model_used=arguments.get("model_used", "unknown"),
                context_ids=arguments.get("context_ids", []),
                tokens_used=arguments.get("tokens_used", 0),
                latency_ms=arguments.get("latency_ms", 0),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"interaction_id": interaction_id}))]

        elif name == "update_outcome":
            await _update_outcome(
                interaction_id=arguments.get("interaction_id", ""),
                outcome=arguments.get("outcome", "unknown"),
                user_feedback=arguments.get("user_feedback", 0),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"status": "updated"}))]

        elif name == "generate_training_data":
            dataset_path = await _generate_dataset()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"dataset_path": dataset_path}))]

        elif name == "search_context":
            query = arguments.get("query", "")
            collection = arguments.get("collection", "codebase-context")
            limit = arguments.get("limit", 5)
            query_embedding = await _embed_fn(query)
            results = _qdrant.query_points(
                collection_name=collection,
                query=query_embedding,
                limit=limit,
                score_threshold=0.7,
            ).points
            formatted = [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(formatted, indent=2))]

        elif name == "hybrid_search":
            result = await _hybrid_search(
                query=arguments.get("query", ""),
                collections=arguments.get("collections"),
                limit=arguments.get("limit", 5),
                keyword_limit=arguments.get("keyword_limit", 5),
                score_threshold=arguments.get("score_threshold", 0.7),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "route_search":
            result = await _route_search(
                query=arguments.get("query", ""),
                mode=arguments.get("mode", "auto"),
                prefer_local=arguments.get("prefer_local", True),
                context=arguments.get("context"),
                limit=arguments.get("limit", 5),
                keyword_limit=arguments.get("keyword_limit", 5),
                score_threshold=arguments.get("score_threshold", 0.7),
                generate_response=arguments.get("generate_response", False),
            )
            _write_audit(
                name,
                'success',
                None,
                (_time.perf_counter() - _start) * 1000,
                arguments,
                metadata={
                    "strategy_tag": result.get("route", "unknown"),
                    "backend": result.get("backend", "none"),
                },
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "store_agent_memory":
            memory_type = normalize_memory_type(arguments.get("memory_type", ""))
            summary = coerce_memory_summary(arguments.get("summary"), arguments.get("content"))
            result = await _store_memory(
                memory_type=memory_type,
                summary=summary,
                content=arguments.get("content"),
                metadata=arguments.get("metadata"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "recall_agent_memory":
            result = await _recall_memory(
                query=arguments.get("query", ""),
                memory_types=arguments.get("memory_types"),
                limit=arguments.get("limit"),
                retrieval_mode=arguments.get("retrieval_mode", "hybrid"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_harness_eval":
            result = await _run_harness_eval(
                query=arguments.get("query", ""),
                expected_keywords=arguments.get("expected_keywords"),
                mode=arguments.get("mode", "auto"),
                max_latency_ms=arguments.get("max_latency_ms"),
            )
            metrics = result.get("metrics") if isinstance(result, dict) else {}
            _write_audit(
                name,
                'success',
                None,
                (_time.perf_counter() - _start) * 1000,
                arguments,
                metadata={
                    "harness_status": result.get("status") if isinstance(result, dict) else "",
                    "harness_passed": bool(result.get("passed")) if isinstance(result, dict) else False,
                    "harness_overall_score": metrics.get("overall_score") if isinstance(metrics, dict) else None,
                    "harness_failure_category": result.get("failure_category") if isinstance(result, dict) else None,
                },
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "harness_stats":
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(_HARNESS_STATS, indent=2))]

        elif name == "learning_feedback":
            feedback_id = await _record_learning_feedback(
                query=arguments.get("query", ""),
                correction=arguments.get("correction", ""),
                original_response=arguments.get("original_response"),
                interaction_id=arguments.get("interaction_id"),
                rating=arguments.get("rating"),
                tags=arguments.get("tags"),
                model=arguments.get("model"),
                variant=arguments.get("variant"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps({"feedback_id": feedback_id}))]

        # Phase 19.3.1 — get_workflow_hints
        elif name == "get_workflow_hints":
            import sys as _sys
            from pathlib import Path as _Path
            _hints_dir = _Path(__file__).parent
            if str(_hints_dir) not in _sys.path:
                _sys.path.insert(0, str(_hints_dir))
            try:
                from hints_engine import HintsEngine  # type: ignore[import]
                engine = HintsEngine()
                result = engine.rank_as_dict(
                    query=arguments.get("query", ""),
                    context=arguments.get("context", ""),
                    max_hints=int(arguments.get("max_hints", 3)),
                )
            except ImportError:
                result = {
                    "hints": [],
                    "query": arguments.get("query", ""),
                    "error": "hints_engine not available — run `scripts/ai/aq-hints` from CLI instead",
                }
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "tooling_manifest":
            query = arguments.get("query", "")
            tools = workflow_tool_catalog(query)
            result = build_tooling_manifest(
                query,
                tools,
                runtime=arguments.get("runtime", "python"),
                max_tools=arguments.get("max_tools"),
                max_result_chars=arguments.get("max_result_chars"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_qa_check":
            result = await run_qa_check_as_dict(arguments)
            qa_result = result.get("qa_result") if isinstance(result, dict) else {}
            _write_audit(
                name,
                'success' if result.get("status") == "ok" else 'error',
                result.get("stderr"),
                (_time.perf_counter() - _start) * 1000,
                arguments,
                metadata={
                    "phase": result.get("phase"),
                    "exit_code": result.get("exit_code"),
                    "qa_passed": (qa_result or {}).get("passed") if isinstance(qa_result, dict) else None,
                    "qa_failed": (qa_result or {}).get("failed") if isinstance(qa_result, dict) else None,
                    "qa_skipped": (qa_result or {}).get("skipped") if isinstance(qa_result, dict) else None,
                },
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Phase 5 — Model Optimization Tools
        elif name == "capture_training_example":
            import model_optimization
            result = await model_optimization.capture_training_example(
                query=arguments.get("query", ""),
                response=arguments.get("response", ""),
                outcome=arguments.get("outcome", "unknown"),
                user_feedback=arguments.get("user_feedback"),
                latency_ms=arguments.get("latency_ms"),
                metadata=arguments.get("metadata"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "flush_training_data":
            import model_optimization
            result = await model_optimization.flush_training_data()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_training_data_stats":
            import model_optimization
            result = await model_optimization.get_training_data_stats()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "start_finetuning_job":
            import model_optimization
            result = await model_optimization.start_finetuning_job(
                base_model=arguments.get("base_model", ""),
                task_type=arguments.get("task_type", "general"),
                training_data_path=arguments.get("training_data_path"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_finetuning_jobs":
            import model_optimization
            result = await model_optimization.get_finetuning_jobs(
                status_filter=arguments.get("status_filter"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "record_model_performance":
            import model_optimization
            result = await model_optimization.record_model_performance(
                model_id=arguments.get("model_id", ""),
                task_type=arguments.get("task_type", "general"),
                accuracy=arguments.get("accuracy", 0.0),
                latency_ms=arguments.get("latency_ms", 0.0),
                quality_score=arguments.get("quality_score", 0.0),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_model_performance":
            import model_optimization
            result = await model_optimization.get_model_performance(
                model_id=arguments.get("model_id"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_optimization_readiness":
            import model_optimization
            result = await model_optimization.get_optimization_readiness()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "generate_synthetic_training_data":
            import model_optimization
            result = await model_optimization.generate_synthetic_training_data(
                target_examples=arguments.get("target_examples", 50),
                categories=arguments.get("categories"),
                strategies=arguments.get("strategies"),
                min_quality=arguments.get("min_quality", 0.7),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "select_active_learning_examples":
            import model_optimization
            result = await model_optimization.select_active_learning_examples(
                budget=arguments.get("budget", 25),
                strategy=arguments.get("strategy", "hybrid"),
                candidate_paths=arguments.get("candidate_paths"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_distillation_pipeline":
            import model_optimization
            result = await model_optimization.run_distillation_pipeline(
                teacher_model=arguments.get("teacher_model", ""),
                student_model=arguments.get("student_model", ""),
                training_data_path=arguments.get("training_data_path"),
                quantization_method=arguments.get("quantization_method", "gguf"),
                quantization_bits=arguments.get("quantization_bits", 4),
                pruning_sparsity=arguments.get("pruning_sparsity", 0.2),
                enable_speculative_decoding=arguments.get("enable_speculative_decoding", True),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_advanced_features_readiness":
            import advanced_features
            result = await advanced_features.get_advanced_features_readiness()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_agent_quality_profiles":
            import advanced_features
            result = await advanced_features.get_agent_quality_profiles()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "select_failover_remote_agent":
            import advanced_features
            result = await advanced_features.select_failover_remote_agent(
                min_composite_score=arguments.get("min_composite_score", 0.55),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_agent_benchmarks":
            import advanced_features
            result = await advanced_features.get_agent_benchmarks()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "optimize_prompt_template":
            import advanced_features
            result = await advanced_features.optimize_prompt_template(
                task_type=arguments.get("task_type", "implementation"),
                task=arguments.get("task", ""),
                context=arguments.get("context"),
                constraints=arguments.get("constraints"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "generate_dynamic_prompt":
            import advanced_features
            result = await advanced_features.generate_dynamic_prompt(
                query=arguments.get("query", ""),
                context=arguments.get("context"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "record_prompt_variant_outcome":
            import advanced_features
            result = await advanced_features.record_prompt_variant_outcome(
                task_type=arguments.get("task_type", "implementation"),
                variant_id=arguments.get("variant_id", ""),
                score=arguments.get("score", 0.0),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_prompt_ab_stats":
            import advanced_features
            result = await advanced_features.get_prompt_ab_stats()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "select_context_tier":
            import advanced_features
            result = await advanced_features.select_context_tier(
                query=arguments.get("query", ""),
                context=arguments.get("context"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_tier_selection_stats":
            import advanced_features
            result = await advanced_features.get_tier_selection_stats()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "analyze_failure_patterns":
            import advanced_features
            result = await advanced_features.analyze_failure_patterns(
                query=arguments.get("query", ""),
                response=arguments.get("response", ""),
                error_message=arguments.get("error_message"),
                user_feedback=arguments.get("user_feedback"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_capability_gap_stats":
            import advanced_features
            result = await advanced_features.get_capability_gap_stats()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "record_learning_signal":
            import advanced_features
            result = await advanced_features.record_learning_signal(
                query=arguments.get("query", ""),
                response=arguments.get("response", ""),
                outcome=arguments.get("outcome", "unknown"),
                explicit_score=arguments.get("explicit_score"),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_learning_recommendations":
            import advanced_features
            result = await advanced_features.get_learning_recommendations(
                query=arguments.get("query", ""),
            )
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_advanced_learning_stats":
            import advanced_features
            result = await advanced_features.get_learning_stats()
            _write_audit(name, 'success', None, (_time.perf_counter() - _start) * 1000, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")
    except ValueError as exc:
        _write_audit(name, 'client_error', str(exc), (_time.perf_counter() - _start) * 1000, arguments)
        raise
    except Exception as exc:
        _write_audit(name, 'error', str(exc), (_time.perf_counter() - _start) * 1000, arguments)
        raise
