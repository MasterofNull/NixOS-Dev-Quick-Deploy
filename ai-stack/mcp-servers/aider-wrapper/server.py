#!/usr/bin/env python3
"""
Aider-Wrapper MCP Server v3.1
Async Aider invocations with a semaphore-gated task queue and status polling.
"""

import asyncio
import hashlib
import os
import sys
import json
import re
import socket
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import uvicorn
import structlog

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.auth_middleware import get_api_key_dependency

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def load_api_key() -> Optional[str]:
    """Load API key from runtime secret file only."""
    secret_file = os.environ.get("AIDER_WRAPPER_API_KEY_FILE", "/run/secrets/aider_wrapper_api_key")
    if Path(secret_file).exists():
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return None


api_key = load_api_key()
require_auth = get_api_key_dependency(
    service_name="aider-wrapper",
    expected_key=api_key,
    optional=not api_key,
)

app = FastAPI(
    title="Aider-Wrapper MCP Server v3",
    description="Real Aider integration for autonomous code modification",
    version="3.1.0",
)

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE = os.getenv("AIDER_WORKSPACE", "/workspace")
LLAMA_CPP_URL = f"http://{os.getenv('LLAMA_CPP_HOST', 'llama-cpp')}:{os.getenv('LLAMA_CPP_PORT', '8080')}"
MODEL_NAME = os.getenv("LLAMA_CPP_MODEL", "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
AIDER_BIN = os.getenv("AIDER_BIN", "aider")
# Maximum concurrent Aider processes (memory-intensive; default 1)
AIDER_MAX_CONCURRENCY = int(os.getenv("AIDER_MAX_CONCURRENCY", "1"))
AIDER_MAX_CONCURRENCY = max(1, AIDER_MAX_CONCURRENCY)
AIDER_TASK_TIMEOUT = float(os.getenv("AIDER_TASK_TIMEOUT_SECONDS", "600.0"))
AIDER_TERMINATE_GRACE_SECONDS = float(os.getenv("AIDER_TERMINATE_GRACE_SECONDS", "5.0"))
AIDER_WATCHDOG_INTERVAL_SECONDS = float(os.getenv("AIDER_WATCHDOG_INTERVAL_SECONDS", "10.0"))
AIDER_WATCHDOG_MAX_RUNTIME_SECONDS = float(
    os.getenv("AIDER_WATCHDOG_MAX_RUNTIME_SECONDS", str(min(180.0, AIDER_TASK_TIMEOUT)))
)

# Phase 14.1.1 — bubblewrap filesystem sandbox for Aider subprocess.
# When AI_AIDER_SANDBOX=true: aider runs inside bwrap with /nix/store read-only,
# workspace read-write, isolated /tmp, and full network (loopback for llama.cpp API).
# Network is NOT isolated here; systemd IPAddressDeny at the service level restricts
# egress to loopback only.
AI_AIDER_SANDBOX = os.getenv("AI_AIDER_SANDBOX", "false").lower() == "true"
BWRAP_PATH = os.getenv("BWRAP_PATH", "bwrap")
AI_AIDER_SANDBOX_FALLBACK_UNSAFE = os.getenv(
    "AI_AIDER_SANDBOX_FALLBACK_UNSAFE", "true"
).lower() == "true"
AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY = os.getenv("AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY", "true").lower() == "true"
AIDER_SMALL_SCOPE_MAP_TOKENS = int(os.getenv("AIDER_SMALL_SCOPE_MAP_TOKENS", "384"))
AI_AIDER_ANALYSIS_FAST_MODE = os.getenv("AI_AIDER_ANALYSIS_FAST_MODE", "true").lower() == "true"
AIDER_ANALYSIS_MAP_TOKENS = int(os.getenv("AIDER_ANALYSIS_MAP_TOKENS", "0"))
AIDER_ANALYSIS_MAX_RUNTIME_SECONDS = float(
    os.getenv("AIDER_ANALYSIS_MAX_RUNTIME_SECONDS", "75.0")
)
AI_AIDER_ANALYSIS_ROUTE_TO_HYBRID = os.getenv("AI_AIDER_ANALYSIS_ROUTE_TO_HYBRID", "true").lower() == "true"
AI_AIDER_AUTO_FILE_SCOPE = os.getenv("AI_AIDER_AUTO_FILE_SCOPE", "true").lower() == "true"
AIDER_AUTO_FILE_SCOPE_MAX = int(os.getenv("AIDER_AUTO_FILE_SCOPE_MAX", "6"))
AIDER_DEFAULT_MAP_TOKENS = int(os.getenv("AIDER_DEFAULT_MAP_TOKENS", "512"))

# Phase 19.3.3 — aq-hints injection: prepend top ranked hint to aider --message.
# Fetches from HINTS_URL (hybrid-coordinator /hints), enriching the task with
# context from registry.yaml, query gaps, and CLAUDE.md workflow rules.
AI_HINTS_ENABLED = os.getenv("AI_HINTS_ENABLED", "false").lower() == "true"
AI_HINTS_MIN_SCORE = float(os.getenv("AI_HINTS_MIN_SCORE", "0.45"))
AI_HINTS_MIN_SNIPPET_CHARS = int(os.getenv("AI_HINTS_MIN_SNIPPET_CHARS", "24"))
AI_HINTS_MIN_TOKEN_OVERLAP = int(os.getenv("AI_HINTS_MIN_TOKEN_OVERLAP", "1"))
AI_HINTS_BYPASS_OVERLAP_SCORE = float(os.getenv("AI_HINTS_BYPASS_OVERLAP_SCORE", "0.72"))
AI_TOOLING_PLAN_ENABLED = os.getenv("AI_TOOLING_PLAN_ENABLED", "true").lower() == "true"
HINTS_URL = os.getenv(
    "HINTS_URL",
    f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/hints",
)
HINT_FEEDBACK_URL = os.getenv(
    "HINT_FEEDBACK_URL",
    (HINTS_URL.rstrip("/") + "/feedback") if HINTS_URL.rstrip("/").endswith("/hints")
    else f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/hints/feedback",
)
WORKFLOW_PLAN_URL = os.getenv(
    "WORKFLOW_PLAN_URL",
    f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/workflow/plan",
)
HYBRID_API_KEY = os.getenv("HYBRID_API_KEY", "")
HYBRID_API_KEY_FILE = os.getenv("HYBRID_API_KEY_FILE", "/run/secrets/hybrid_api_key")


def _load_hybrid_api_key() -> str:
    """Load hybrid API key for authenticated /hints calls."""
    if HYBRID_API_KEY:
        return HYBRID_API_KEY.strip()
    p = Path(HYBRID_API_KEY_FILE)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""

# Phase 19.3.4 — hint adoption tracking: written alongside tool-audit.jsonl.
_audit_dir = Path(os.getenv(
    "TOOL_AUDIT_LOG_PATH", "/var/log/nixos-ai-stack/tool-audit.jsonl"
)).parent
HINT_AUDIT_LOG_PATH = Path(os.getenv("HINT_AUDIT_LOG_PATH", str(_audit_dir / "hint-audit.jsonl")))
TASK_AUDIT_LOG_PATH = Path(os.getenv("TASK_AUDIT_LOG_PATH", str(_audit_dir / "aider-task-audit.jsonl")))

# ============================================================================
# In-memory task store
# ============================================================================

_tasks: Dict[str, dict] = {}
_task_semaphore: Optional[asyncio.Semaphore] = None
_task_processes: Dict[str, asyncio.subprocess.Process] = {}
_task_cancel_reasons: Dict[str, str] = {}
_watchdog_task: Optional[asyncio.Task] = None

_ANALYSIS_ONLY_HINTS = (
    "analysis only",
    "analyze",
    "summarize",
    "summary",
    "explain",
    "review",
    "no file edits",
    "do not edit",
    "without editing",
)
_MUTATION_HINTS = (
    "edit",
    "modify",
    "change",
    "patch",
    "refactor",
    "implement",
    "write code",
    "fix",
    "update file",
)


def _is_analysis_only_task(prompt: str, files: List[str]) -> bool:
    text = (prompt or "").strip().lower()
    if not text:
        return False
    has_analysis = any(h in text for h in _ANALYSIS_ONLY_HINTS)
    has_mutation = any(h in text for h in _MUTATION_HINTS)
    # Bias toward fast analysis profile when prompt explicitly forbids edits
    # or when it's a pure explanation/review request over a bounded file list.
    return ("no file edits" in text or "do not edit" in text) or (
        has_analysis and not has_mutation
    )


def _derive_effective_files(workspace: Path, prompt: str, files: List[str], max_files: int) -> List[str]:
    """Use declared files first, then infer file paths from prompt mentions."""
    existing: List[str] = []
    seen = set()
    for rel in (files or []):
        r = str(rel).strip()
        if not r or r in seen:
            continue
        p = workspace / r
        if p.exists() and p.is_file():
            seen.add(r)
            existing.append(r)
    if existing or not AI_AIDER_AUTO_FILE_SCOPE:
        return existing[:max_files]

    text = prompt or ""
    path_pattern = r"(?:`([^`]+)`|([A-Za-z0-9._/-]+\.[A-Za-z0-9_]+))"
    matches = re.findall(path_pattern, text)
    for m in matches:
        raw = (m[0] or m[1] or "").strip()
        if not raw:
            continue
        raw = raw.lstrip("./")
        if raw in seen:
            continue
        p = workspace / raw
        if p.exists() and p.is_file():
            seen.add(raw)
            existing.append(raw)
        if len(existing) >= max_files:
            break
    return existing[:max_files]


def _read_file_snippets(workspace: Path, files: List[str], max_files: int = 3, max_chars: int = 1200) -> List[Dict[str, str]]:
    snippets: List[Dict[str, str]] = []
    for rel in (files or [])[:max_files]:
        path = workspace / rel
        try:
            if not path.exists() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            snippets.append({
                "file": rel,
                "snippet": text[:max_chars],
            })
        except Exception:
            continue
    return snippets


def _heuristic_analysis_summary(prompt: str, snippets: List[Dict[str, str]]) -> str:
    if not snippets:
        return "Analysis complete: no readable file snippets were available for the requested task."
    files = ", ".join(s.get("file", "unknown") for s in snippets[:3])
    first = snippets[0].get("snippet", "").strip().replace("\n", " ")
    first = " ".join(first.split())
    if len(first) > 140:
        first = first[:140].rstrip() + "..."
    return f"Analysis complete for {files}; key excerpt indicates: {first or 'content reviewed.'}"


async def _run_analysis_fastpath(prompt: str, workspace: Path, files: List[str]) -> str:
    """Analysis-only fast path using hybrid coordinator /query."""
    hybrid_key = _load_hybrid_api_key()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if hybrid_key:
        headers["X-API-Key"] = hybrid_key
    payload = {
        "query": prompt[:2000],
        "prefer_local": True,
        "generate_response": True,
        "context": {
            "analysis_only": True,
            "skip_gap_tracking": True,
            "source": "aider-wrapper-analysis-fastpath",
            "file_snippets": _read_file_snippets(workspace, files),
        },
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}/query",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    loop = asyncio.get_event_loop()

    def _fetch() -> Dict:
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())

    result = await loop.run_in_executor(None, _fetch)
    if not isinstance(result, dict):
        raise RuntimeError("analysis fastpath returned invalid payload")
    text = (
        result.get("response")
        or result.get("answer")
        or result.get("content")
        or ""
    )
    output = str(text).strip()
    if not output:
        raise RuntimeError("analysis fastpath returned empty response")
    return output


def _write_hint_audit(task_id: str, hint_id: str, hint_snippet: str, accepted: bool) -> None:
    """Phase 19.3.4 — append a hint adoption record to hint-audit.jsonl."""
    try:
        task_tooling = _tasks.get(task_id, {}).get("tooling", {})
        entry = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": "aider-wrapper",
            "task_id": task_id,
            "hint_id": hint_id,
            "hint_snippet": hint_snippet[:80],
            "hint_accepted": accepted,
            "tooling_plan_injected": bool(task_tooling.get("tooling_plan_injected", False)),
            "analysis_only_profile": bool(task_tooling.get("analysis_only_profile", False)),
            "analysis_fastpath_used": bool(task_tooling.get("analysis_fastpath_used", False)),
        })
        HINT_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HINT_AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as exc:
        logger.debug("hint_audit_write_failed", error=str(exc))


async def _submit_hint_feedback(
    task_id: str,
    hint_id: str,
    helpful: bool,
    score: float,
    comment: str = "",
    agent_preferences: Optional[Dict[str, List[str]]] = None,
) -> None:
    if not hint_id:
        return
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    hybrid_key = _load_hybrid_api_key()
    if hybrid_key:
        headers["X-API-Key"] = hybrid_key
    payload = {
        "task_id": task_id,
        "hint_id": hint_id,
        "helpful": bool(helpful),
        "score": max(-1.0, min(1.0, float(score))),
        "comment": comment[:240],
        "agent": "aider-wrapper",
    }
    if isinstance(agent_preferences, dict):
        payload["agent_preferences"] = {
            "preferred_tools": list(agent_preferences.get("preferred_tools", []))[:8],
            "preferred_data_sources": list(agent_preferences.get("preferred_data_sources", []))[:8],
            "preferred_hint_types": list(agent_preferences.get("preferred_hint_types", []))[:8],
            "preferred_tags": list(agent_preferences.get("preferred_tags", []))[:8],
        }
    req = urllib.request.Request(
        HINT_FEEDBACK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    loop = asyncio.get_event_loop()

    def _send() -> None:
        with urllib.request.urlopen(req, timeout=2):
            return None

    try:
        await loop.run_in_executor(None, _send)
    except Exception as exc:
        logger.debug("hint_feedback_submit_failed", task_id=task_id, hint_id=hint_id, error=str(exc))


def _write_task_audit(task_id: str, status: str, completed: bool) -> None:
    """Append aider task outcome + tooling metadata for report quality analysis."""
    try:
        entry = _tasks.get(task_id, {})
        req = entry.get("request", {}) if isinstance(entry.get("request"), dict) else {}
        tooling = entry.get("tooling", {}) if isinstance(entry.get("tooling"), dict) else {}
        result = entry.get("result", {}) if isinstance(entry.get("result"), dict) else {}
        prompt = str(req.get("prompt", "") or "")
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": "aider-wrapper",
            "task_id": task_id,
            "status": status,
            "completed": bool(completed),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16] if prompt else "",
            "tooling_plan_injected": bool(tooling.get("tooling_plan_injected", False)),
            "hint_injected": bool(tooling.get("hint_injected", False)),
            "analysis_only_profile": bool(tooling.get("analysis_only_profile", False)),
            "analysis_fastpath_used": bool(tooling.get("analysis_fastpath_used", False)),
            "duration_seconds": float(result.get("duration_seconds", 0.0) or 0.0),
            "exit_code": int(result.get("exit_code", 0) or 0),
            "files_modified_count": len(result.get("files_modified", []) or []),
        }
        TASK_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TASK_AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as exc:
        logger.warning("task_audit_write_failed", path=str(TASK_AUDIT_LOG_PATH), error=str(exc))


def _hint_token_overlap(prompt: str, top_hint: Dict[str, object]) -> int:
    prompt_tokens = {
        tok for tok in re.findall(r"[a-z0-9_]{4,}", (prompt or "").lower())
        if tok not in {"with", "from", "that", "this", "into", "task", "prompt", "file", "code"}
    }
    if not prompt_tokens:
        return 0
    hint_parts: List[str] = []
    for key in ("title", "snippet", "reason"):
        val = top_hint.get(key)
        if isinstance(val, str):
            hint_parts.append(val.lower())
    tags = top_hint.get("tags")
    if isinstance(tags, list):
        hint_parts.extend(str(t).lower() for t in tags if isinstance(t, str))
    hint_tokens = set(re.findall(r"[a-z0-9_]{4,}", " ".join(hint_parts)))
    return len(prompt_tokens.intersection(hint_tokens))


def _select_hint_for_injection(prompt: str, hints: List[Dict[str, object]]) -> Tuple[Optional[Dict[str, object]], int]:
    """
    Choose an eligible hint from ranked candidates.
    Prefers relevance (token overlap), then score, and rotates deterministically
    across near-ties so one hint ID does not dominate every task.
    """
    eligible: List[Tuple[Dict[str, object], float, int, int]] = []
    for hint in hints:
        snippet = str(hint.get("snippet", "") or "").strip()
        if not snippet or len(snippet) < AI_HINTS_MIN_SNIPPET_CHARS:
            continue
        try:
            score = float(hint.get("score", 1.0))
        except (TypeError, ValueError):
            score = 1.0
        overlap = _hint_token_overlap(prompt, hint)
        overlap_ok = (
            overlap >= AI_HINTS_MIN_TOKEN_OVERLAP
            or score >= AI_HINTS_BYPASS_OVERLAP_SCORE
        )
        if score >= AI_HINTS_MIN_SCORE and overlap_ok:
            hint_id = str(hint.get("id", "") or "")
            if hint_id.startswith("runtime_tool_error_"):
                score -= 0.18
            eligible.append((hint, score, overlap, len(snippet)))

    if not eligible:
        return None, 0

    # Primary objective: maximize relevance and success likelihood.
    # Secondary objective: minimize injected-token footprint via shorter snippets.
    eligible.sort(key=lambda item: (item[2], item[1], -item[3]), reverse=True)
    best_overlap = eligible[0][2]
    best_score = eligible[0][1]
    tie_bucket = [
        item for item in eligible
        if item[2] >= best_overlap and item[1] >= (best_score - 0.03)
    ]

    if len(tie_bucket) == 1:
        selected = tie_bucket[0]
    else:
        prompt_hash = int(hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:8], 16)
        selected = tie_bucket[prompt_hash % len(tie_bucket)]
    return selected[0], selected[2]


def _apply_bwrap(cmd: List[str], workspace: str) -> List[str]:
    """Phase 14.1.1 — wrap cmd in a bubblewrap filesystem sandbox.

    Security model:
      - /nix/store bound read-only   — all Nix executables/libraries accessible
      - workspace bound read-write   — aider is allowed to modify code files here
      - /tmp as tmpfs                — isolated, cleared after each invocation
      - /etc, /dev, /proc mounted    — needed for git, tty detection, process ops
      - Network NOT isolated         — loopback needed for llama.cpp API on :8080;
                                      systemd IPAddressDeny restricts actual egress
    """
    ws = str(workspace)
    return [
        BWRAP_PATH,
        "--ro-bind", "/nix/store", "/nix/store",   # Nix executables (read-only)
        "--bind", ws, ws,                           # workspace (read-write)
        "--ro-bind", "/etc", "/etc",                # git config, passwd, CA certs
        "--dev", "/dev",                            # /dev/null, /dev/urandom etc.
        "--proc", "/proc",                          # needed by some git operations
        "--tmpfs", "/tmp",                          # isolated temp directory
        "--new-session",                            # detach from controlling tty
        "--die-with-parent",                        # clean up on wrapper exit
        "--",
    ] + cmd


# ============================================================================
# Request / Response Models
# ============================================================================

class TaskRequest(BaseModel):
    """Task request for Aider execution."""
    prompt: str = Field(..., description="Task description for Aider")
    files: List[str] = Field(default_factory=list, description="Files to include in context")
    model: str = Field(default="openai/gpt-4o", description="Model to use (ignored, uses llama.cpp)")
    max_tokens: int = Field(default=4000, description="Max tokens")
    workspace: str = Field(default=WORKSPACE, description="Working directory")
    # Ralph compatibility fields
    context: Optional[dict] = Field(default=None, description="Additional context from Ralph")
    iteration: Optional[int] = Field(default=1, description="Iteration number from Ralph")
    mode: Optional[str] = Field(default="autonomous", description="Execution mode")


class TaskResponse(BaseModel):
    """Completed task result (nested inside status response)."""
    status: str
    output: str
    error: Optional[str] = None
    files_modified: List[str] = []
    git_commits: List[str] = []
    duration_seconds: float = 0.0
    exit_code: int = 0
    completed: bool = False


class TaskSubmitResponse(BaseModel):
    """Immediate response from task submission."""
    task_id: str
    status: str = "queued"
    message: str = "Task submitted"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    aider_available: bool
    workspace: str
    llama_cpp_url: str


class TaskSummaryResponse(BaseModel):
    """Current queue depth and last observed terminal task state."""
    active_tasks: int
    last_task_status: str
    last_task_id: Optional[str] = None


# ============================================================================
# FastAPI startup: initialise semaphore + verify aider binary
# ============================================================================

@app.on_event("startup")
async def _startup() -> None:
    global _task_semaphore, _watchdog_task
    _task_semaphore = asyncio.Semaphore(AIDER_MAX_CONCURRENCY)
    logger.info("aider_wrapper_starting", version="3.1.0", workspace=WORKSPACE,
                max_concurrency=AIDER_MAX_CONCURRENCY)
    try:
        proc = await asyncio.create_subprocess_exec(
            AIDER_BIN, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode == 0:
            logger.info("aider_found", version=stdout.decode("utf-8", errors="replace").strip())
        else:
            logger.error("aider_not_found", message="Aider binary not available")
    except asyncio.TimeoutError:
        logger.error("aider_version_check_timeout")
    except Exception as exc:
        logger.error("aider_check_failed", error=str(exc))

    _watchdog_task = asyncio.create_task(_task_watchdog_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        _watchdog_task.cancel()
        try:
            await _watchdog_task
        except asyncio.CancelledError:
            pass


def _now_iso() -> str:
    return datetime.now().isoformat()


def _set_terminal_task(
    task_id: str,
    *,
    status: str,
    output: str,
    error: str,
    files_modified: List[str],
    git_commits: List[str],
    duration_seconds: float,
    exit_code: int,
    completed: bool,
) -> None:
    _tasks[task_id].update({
        "status": status,
        "finished_at": _now_iso(),
        "result": {
            "status": status,
            "output": output,
            "error": error,
            "files_modified": files_modified,
            "git_commits": git_commits,
            "duration_seconds": duration_seconds,
            "exit_code": exit_code,
            "completed": completed,
        },
    })
    _write_task_audit(task_id, status, completed)


async def _terminate_process(task_id: str, proc: asyncio.subprocess.Process, reason: str) -> None:
    """Graceful terminate with hard kill escalation."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=AIDER_TERMINATE_GRACE_SECONDS)
    except Exception:
        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            pass
    logger.warning("aider_task_process_terminated", task_id=task_id, reason=reason)


async def _task_watchdog_loop() -> None:
    """Kill runaway running tasks that exceed watchdog runtime."""
    while True:
        try:
            await asyncio.sleep(max(1.0, AIDER_WATCHDOG_INTERVAL_SECONDS))
            now = datetime.now().timestamp()
            for task_id, entry in list(_tasks.items()):
                if entry.get("status") != "running":
                    continue
                started_raw = entry.get("started_at")
                if not isinstance(started_raw, str):
                    continue
                try:
                    started_ts = datetime.fromisoformat(started_raw).timestamp()
                except ValueError:
                    continue
                runtime = now - started_ts
                if runtime < AIDER_WATCHDOG_MAX_RUNTIME_SECONDS:
                    continue
                proc = _task_processes.get(task_id)
                if proc is None:
                    continue
                _task_cancel_reasons[task_id] = "watchdog_timeout"
                await _terminate_process(task_id, proc, "watchdog_timeout")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("aider_watchdog_error", error=str(exc))


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    aider_available = False
    try:
        proc = await asyncio.create_subprocess_exec(
            AIDER_BIN, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            aider_available = proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
    except Exception:
        pass

    return {
        "status": "healthy" if aider_available else "degraded",
        "version": "3.1.0",
        "aider_available": aider_available,
        "workspace": WORKSPACE,
        "llama_cpp_url": LLAMA_CPP_URL,
    }


# ============================================================================
# Internal: async Aider runner (semaphore-gated)
# ============================================================================

async def _run_aider_task(task_id: str, task: TaskRequest) -> None:
    """Run one Aider task, respecting the concurrency semaphore. Updates _tasks in place."""
    global _task_semaphore
    if _task_semaphore is None:
        # Defensive lazy init in case startup hook did not run.
        _task_semaphore = asyncio.Semaphore(AIDER_MAX_CONCURRENCY)
    elif _task_semaphore.locked():
        # Self-heal leaked semaphore lock when no other non-terminal tasks exist.
        other_active = any(
            tid != task_id and str(entry.get("status", "")) in {"queued", "waiting", "running"}
            for tid, entry in _tasks.items()
        )
        if not other_active:
            logger.warning(
                "aider_task_semaphore_reset",
                reason="leaked_lock_without_active_tasks",
                max_concurrency=AIDER_MAX_CONCURRENCY,
            )
            _task_semaphore = asyncio.Semaphore(AIDER_MAX_CONCURRENCY)
    _tasks[task_id]["status"] = "waiting"
    async with _task_semaphore:
        if task_id in _task_cancel_reasons:
            _set_terminal_task(
                task_id,
                status="canceled",
                output="",
                error=_task_cancel_reasons.pop(task_id, "Task canceled before execution"),
                files_modified=[],
                git_commits=[],
                duration_seconds=0.0,
                exit_code=130,
                completed=False,
            )
            return
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = _now_iso()
        start_time = datetime.now()

        workspace_path = Path(task.workspace)
        if not workspace_path.exists():
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error=f"Workspace does not exist: {task.workspace}",
                files_modified=[],
                git_commits=[],
                duration_seconds=0.0,
                exit_code=1,
                completed=False,
            )
            return

        try:
            effective_files = _derive_effective_files(
                workspace_path,
                task.prompt,
                task.files or [],
                max_files=max(1, AIDER_AUTO_FILE_SCOPE_MAX),
            )
            analysis_only = AI_AIDER_ANALYSIS_FAST_MODE and _is_analysis_only_task(task.prompt, effective_files)
        except Exception as exc:
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error=f"Task preflight failed: {exc}",
                files_modified=[],
                git_commits=[],
                duration_seconds=0.0,
                exit_code=1,
                completed=False,
            )
            return
        logger.info("aider_task_start", task_id=task_id,
                    prompt_length=len(task.prompt), files=task.files,
                    effective_files=effective_files,
                    iteration=task.iteration, workspace=task.workspace,
                    analysis_only=analysis_only)

        # Phase 19.3.3 — fetch top aq-hint and prepend to prompt for steered execution.
        hint_id = ""
        hint_snippet = ""
        hint_injected = False
        _tasks[task_id]["tooling"] = {
            "hints_enabled": AI_HINTS_ENABLED,
            "hint_injected": False,
            "hint_id": "",
            "tooling_plan_enabled": AI_TOOLING_PLAN_ENABLED,
            "tooling_plan_injected": False,
            "tooling_plan_phase_count": 0,
            "hint_score": 0.0,
            "hint_token_overlap": 0,
            "analysis_only_profile": analysis_only,
            "analysis_fastpath_used": False,
            "task_timeout_seconds": (
                min(AIDER_TASK_TIMEOUT, AIDER_ANALYSIS_MAX_RUNTIME_SECONDS)
                if analysis_only
                else AIDER_TASK_TIMEOUT
            ),
        }
        message_for_aider = task.prompt
        if AI_HINTS_ENABLED:
            try:
                params = urllib.parse.urlencode({"q": task.prompt[:240], "max": "5"})
                hints_headers = {"Accept": "application/json"}
                hybrid_key = _load_hybrid_api_key()
                if hybrid_key:
                    hints_headers["X-API-Key"] = hybrid_key
                req = urllib.request.Request(
                    f"{HINTS_URL}?{params}",
                    headers=hints_headers,
                )
                loop = asyncio.get_event_loop()
                def _fetch_hint():
                    with urllib.request.urlopen(req, timeout=2) as r:
                        return json.loads(r.read())
                hints_data = await loop.run_in_executor(None, _fetch_hint)
                top_hints = hints_data.get("hints", [])
                if top_hints:
                    top, token_overlap = _select_hint_for_injection(task.prompt, top_hints)
                else:
                    top, token_overlap = None, 0
                if top:
                    hint_id = str(top.get("id", "")).strip()
                    hint_snippet = str(top.get("snippet", "")).strip()[:150]
                    raw_score = top.get("score", 1.0)
                    try:
                        hint_score = float(raw_score)
                    except (TypeError, ValueError):
                        hint_score = 1.0
                    if hint_snippet:
                        message_for_aider = f"CONTEXT (aq-hints): {hint_snippet}\n\n{task.prompt}"
                        hint_injected = True
                        _tasks[task_id]["tooling"]["hint_injected"] = True
                        _tasks[task_id]["tooling"]["hint_id"] = hint_id
                        _tasks[task_id]["tooling"]["hint_score"] = hint_score
                        _tasks[task_id]["tooling"]["hint_token_overlap"] = token_overlap
                        logger.info("hint_injected", task_id=task_id, hint_id=hint_id, hint_score=hint_score)
                else:
                    logger.debug("hint_injection_skipped", task_id=task_id, reason="no eligible hint")
            except Exception as exc:
                logger.debug("hint_fetch_skipped", task_id=task_id, error=str(exc))

        # Semantic tooling plan auto-injection: exposes planned tool phases to
        # aider so task execution can follow the stack's orchestrated tool layer.
        if AI_TOOLING_PLAN_ENABLED:
            try:
                plan_headers = {"Accept": "application/json", "Content-Type": "application/json"}
                hybrid_key = _load_hybrid_api_key()
                if hybrid_key:
                    plan_headers["X-API-Key"] = hybrid_key
                plan_req = urllib.request.Request(
                    WORKFLOW_PLAN_URL,
                    data=json.dumps({"query": task.prompt[:500]}).encode("utf-8"),
                    headers=plan_headers,
                    method="POST",
                )
                loop = asyncio.get_event_loop()
                def _fetch_plan():
                    with urllib.request.urlopen(plan_req, timeout=2) as r:
                        return json.loads(r.read())
                plan_data = await loop.run_in_executor(None, _fetch_plan)
                phases: List[dict] = []
                if isinstance(plan_data, dict):
                    # Prefer current schema: top-level "phases".
                    top_level = plan_data.get("phases", [])
                    if isinstance(top_level, list):
                        phases = [p for p in top_level if isinstance(p, dict)]
                    # Backward-compatible fallback: nested under "plan.phases".
                    if not phases:
                        legacy = plan_data.get("plan", {})
                        legacy_phases = legacy.get("phases", []) if isinstance(legacy, dict) else []
                        if isinstance(legacy_phases, list):
                            phases = [p for p in legacy_phases if isinstance(p, dict)]
                if phases:
                    phase_lines = []
                    for phase in phases[:3]:
                        pid = str(phase.get("id", "phase")).strip()
                        tools = [
                            str(t.get("name", "")).strip()
                            for t in (phase.get("tools", []) if isinstance(phase.get("tools", []), list) else [])
                            if isinstance(t, dict) and str(t.get("name", "")).strip()
                        ]
                        if tools:
                            phase_lines.append(f"- {pid}: {', '.join(tools[:4])}")
                    if phase_lines:
                        plan_prefix = "TOOLING PLAN (auto):\n" + "\n".join(phase_lines) + "\n\n"
                        message_for_aider = plan_prefix + message_for_aider
                        _tasks[task_id]["tooling"]["tooling_plan_injected"] = True
                        _tasks[task_id]["tooling"]["tooling_plan_phase_count"] = len(phase_lines)
                        logger.info("tooling_plan_injected", task_id=task_id, phases=len(phase_lines))
            except Exception as exc:
                logger.debug("tooling_plan_fetch_skipped", task_id=task_id, error=str(exc))

        # Analysis-only fast path: route through hybrid /query with bounded file snippets.
        if analysis_only and AI_AIDER_ANALYSIS_ROUTE_TO_HYBRID:
            snippets_for_fallback = _read_file_snippets(workspace_path, effective_files)
            try:
                output = await _run_analysis_fastpath(task.prompt, workspace_path, effective_files)
                duration = (datetime.now() - start_time).total_seconds()
                _tasks[task_id]["tooling"]["analysis_fastpath_used"] = True
                logger.info("aider_analysis_fastpath_complete", task_id=task_id, duration=duration)
                if hint_injected:
                    _write_hint_audit(task_id, hint_id, hint_snippet, accepted=True)
                _set_terminal_task(
                    task_id,
                    status="success",
                    output=output,
                    error="",
                    files_modified=[],
                    git_commits=[],
                    duration_seconds=duration,
                    exit_code=0,
                    completed=False,
                )
                return
            except Exception as exc:
                logger.warning("aider_analysis_fastpath_failed", task_id=task_id, error=str(exc))
                duration = (datetime.now() - start_time).total_seconds()
                fallback_output = _heuristic_analysis_summary(task.prompt, snippets_for_fallback)
                _tasks[task_id]["tooling"]["analysis_fastpath_used"] = True
                if hint_injected:
                    _write_hint_audit(task_id, hint_id, hint_snippet, accepted=True)
                _set_terminal_task(
                    task_id,
                    status="success",
                    output=fallback_output,
                    error="",
                    files_modified=[],
                    git_commits=[],
                    duration_seconds=duration,
                    exit_code=0,
                    completed=False,
                )
                return

        base_cmd = [
            AIDER_BIN,
            "--yes",
            "--no-auto-commits",
            "--model", f"openai/{MODEL_NAME}",
            "--openai-api-base", f"{LLAMA_CPP_URL}/v1",
            "--openai-api-key", "dummy",
        ]
        if AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY and effective_files:
            base_cmd.append("--subtree-only")
        if analysis_only:
            base_cmd.extend(["--map-tokens", str(max(0, AIDER_ANALYSIS_MAP_TOKENS))])
            base_cmd.append("--no-git")
            base_cmd.append("--no-gitignore")
        elif effective_files:
            base_cmd.extend(["--map-tokens", str(max(0, AIDER_SMALL_SCOPE_MAP_TOKENS))])
        else:
            base_cmd.extend(["--map-tokens", str(max(0, AIDER_DEFAULT_MAP_TOKENS))])
        for file in effective_files:
            file_path = workspace_path / file
            if file_path.exists():
                base_cmd.extend(["--read", str(file_path)] if analysis_only else ["--file", str(file_path)])
            else:
                logger.warning("file_not_found", file=file)
        base_cmd.extend(["--message", message_for_aider])

        # Phase 14.1.1 — optionally wrap in bubblewrap filesystem sandbox.
        cmd = list(base_cmd)
        sandbox_applied = False
        if AI_AIDER_SANDBOX:
            cmd = _apply_bwrap(cmd, task.workspace)
            sandbox_applied = True
            logger.info("aider_sandbox_enabled", bwrap=BWRAP_PATH)

        logger.info("executing_aider", command=" ".join(cmd[:10]))

        output = ""
        error_text: Optional[str] = None
        returncode = 1

        async def _run_command(exec_cmd: List[str], timeout_s: float) -> tuple[str, str, int]:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                cwd=task.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _task_processes[task_id] = proc
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s
                )
                return (
                    stdout_bytes.decode("utf-8", errors="replace"),
                    stderr_bytes.decode("utf-8", errors="replace"),
                    int(proc.returncode),
                )
            except asyncio.TimeoutError:
                _task_cancel_reasons[task_id] = "timeout"
                await _terminate_process(task_id, proc, "timeout")
                raise
            finally:
                _task_processes.pop(task_id, None)

        try:
            task_timeout = (
                min(AIDER_TASK_TIMEOUT, AIDER_ANALYSIS_MAX_RUNTIME_SECONDS)
                if analysis_only
                else AIDER_TASK_TIMEOUT
            )
            output, stderr_text, returncode = await _run_command(cmd, task_timeout)
            if returncode != 0:
                error_text = stderr_text
                if (
                    sandbox_applied
                    and AI_AIDER_SANDBOX_FALLBACK_UNSAFE
                    and (
                        "No permissions to creating new namespace" in stderr_text
                        or "unprivileged_userns_clone" in stderr_text
                        or "Operation not permitted" in stderr_text
                    )
                ):
                    logger.warning(
                        "aider_sandbox_fallback_unsandboxed task_id=%s reason=userns_unavailable",
                        task_id,
                    )
                    output, stderr_text, returncode = await _run_command(base_cmd, task_timeout)
                    error_text = stderr_text if returncode != 0 else None

        except asyncio.TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_timeout", task_id=task_id, duration=duration)
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error="Aider execution timed out",
                files_modified=[],
                git_commits=[],
                duration_seconds=duration,
                exit_code=124,
                completed=False,
            )
            return

        except Exception as exc:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("aider_exception", task_id=task_id, error=str(exc), duration=duration)
            _set_terminal_task(
                task_id,
                status="error",
                output="",
                error=f"Exception: {exc}",
                files_modified=[],
                git_commits=[],
                duration_seconds=duration,
                exit_code=1,
                completed=False,
            )
            return

        duration = (datetime.now() - start_time).total_seconds()

        # Detect modified files from Aider stdout
        files_modified = []
        for line in output.split("\n"):
            if "modified:" in line.lower() or "created:" in line.lower():
                parts = line.split()
                if len(parts) > 1:
                    files_modified.append(parts[-1])

        # Collect recent git commits
        git_commits = []
        try:
            git_proc = await asyncio.create_subprocess_exec(
                "git", "log", "--oneline", "-5",
                cwd=task.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                git_stdout, _ = await asyncio.wait_for(git_proc.communicate(), timeout=5.0)
                if git_proc.returncode == 0:
                    git_commits = [
                        line.strip()
                        for line in git_stdout.decode("utf-8").split("\n")
                        if line.strip()
                    ][:3]
            except asyncio.TimeoutError:
                git_proc.kill()
        except Exception:
            pass

        cancelled_reason = _task_cancel_reasons.pop(task_id, "")
        cancelled = bool(cancelled_reason)
        completed = (returncode == 0 and len(files_modified) > 0 and not cancelled)
        final_status = "canceled" if cancelled else ("success" if returncode == 0 else "error")
        if cancelled and not error_text:
            error_text = cancelled_reason

        logger.info("aider_task_complete", task_id=task_id, exit_code=returncode,
                    files_modified=len(files_modified), duration=duration, completed=completed)

        # Phase 19.3.4 — record hint adoption outcome.
        # Consider a hint successful when task execution succeeds, even if no
        # file mutation was required (for example, analysis-only or no-op fixes).
        hint_accepted = final_status == "success"
        if hint_injected:
            _write_hint_audit(task_id, hint_id, hint_snippet, accepted=hint_accepted)
            feedback_score = 1.0 if hint_accepted else -1.0
            hint_type = "runtime_signal" if hint_id.startswith("runtime_") else (
                "gap_topic" if hint_id.startswith("gap_") else "prompt_template"
            )
            await _submit_hint_feedback(
                task_id=task_id,
                hint_id=hint_id,
                helpful=hint_accepted,
                score=feedback_score,
                comment=f"status={final_status}; exit_code={returncode}; files_modified={len(files_modified)}",
                agent_preferences={
                    "preferred_tools": ["hints", "workflow_plan", "route_search"],
                    "preferred_data_sources": ["tool_audit", "aq_report", "query_gaps", "registry"],
                    "preferred_hint_types": [hint_type],
                    "preferred_tags": ["efficiency", "tooling", "runtime"],
                },
            )

        _set_terminal_task(
            task_id,
            status=final_status,
            output=output,
            error=error_text or "",
            files_modified=files_modified,
            git_commits=git_commits,
            duration_seconds=duration,
            exit_code=returncode,
            completed=completed,
        )


# ============================================================================
# Task Submission
# ============================================================================

async def _do_submit(task: TaskRequest) -> TaskSubmitResponse:
    task_id = str(uuid4())
    _tasks[task_id] = {
        "status": "queued",
        "submitted_at": _now_iso(),
        "request": task.model_dump(),
        "tooling": {
            "hints_enabled": AI_HINTS_ENABLED,
            "hint_injected": False,
            "hint_id": "",
            "tooling_plan_enabled": AI_TOOLING_PLAN_ENABLED,
            "tooling_plan_injected": False,
            "tooling_plan_phase_count": 0,
            "hint_score": 0.0,
            "hint_token_overlap": 0,
            "analysis_only_profile": False,
            "analysis_fastpath_used": False,
            "task_timeout_seconds": AIDER_TASK_TIMEOUT,
        },
    }
    asyncio.create_task(_run_aider_task(task_id, task))
    logger.info("aider_task_queued", task_id=task_id, workspace=task.workspace)
    return TaskSubmitResponse(task_id=task_id)


@app.post("/tasks", response_model=TaskSubmitResponse)
async def submit_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """Submit a task. Returns task_id immediately; poll GET /tasks/{task_id}/status."""
    return await _do_submit(task)


@app.post("/execute", response_model=TaskSubmitResponse)
@app.post("/api/execute", response_model=TaskSubmitResponse)
async def execute_task(task: TaskRequest, auth: str = Depends(require_auth)):
    """Legacy alias for POST /tasks."""
    return await _do_submit(task)


# ============================================================================
# Task Status Polling
# ============================================================================

@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str, auth: str = Depends(require_auth)):
    """Poll task status. Terminal states: success, error."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    entry = _tasks[task_id]
    response: dict = {"task_id": task_id, "status": entry["status"]}
    for key in ("submitted_at", "started_at", "finished_at"):
        if key in entry:
            response[key] = entry[key]
    if "tooling" in entry:
        response["tooling"] = entry["tooling"]
    if "result" in entry:
        response["result"] = entry["result"]
    return response


@app.post("/tasks/{task_id}/stop")
@app.post("/tasks/{task_id}/cancel")
async def stop_task(task_id: str, auth: str = Depends(require_auth)):
    """Cancel a queued/waiting/running task with kill escalation."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    entry = _tasks[task_id]
    status = str(entry.get("status", "unknown"))
    if status in {"success", "error", "canceled"}:
        return {"task_id": task_id, "status": status, "message": "Task already terminal"}

    _task_cancel_reasons[task_id] = "canceled_by_user"
    proc = _task_processes.get(task_id)
    if proc is not None:
        await _terminate_process(task_id, proc, "canceled_by_user")
        entry["status"] = "canceling"
        return {"task_id": task_id, "status": "canceling", "message": "Cancellation requested"}

    # queued/waiting state: mark immediately terminal and skip execution
    _set_terminal_task(
        task_id,
        status="canceled",
        output="",
        error="canceled_by_user",
        files_modified=[],
        git_commits=[],
        duration_seconds=0.0,
        exit_code=130,
        completed=False,
    )
    _task_cancel_reasons.pop(task_id, None)
    return {"task_id": task_id, "status": "canceled", "message": "Task canceled"}


@app.get("/tasks/summary", response_model=TaskSummaryResponse)
async def get_task_summary(auth: str = Depends(require_auth)):
    """Return queue summary for dashboard polling."""
    active_states = {"queued", "waiting", "running"}
    terminal_states = {"success", "error", "canceled"}

    active_tasks = 0
    last_task_id: Optional[str] = None
    last_task_status = "none"
    last_finished_epoch = -1.0

    for task_id, entry in _tasks.items():
        status = str(entry.get("status", "unknown"))
        if status in active_states:
            active_tasks += 1
            continue
        if status not in terminal_states:
            continue

        finished_at_raw = entry.get("finished_at")
        finished_epoch = 0.0
        if isinstance(finished_at_raw, str):
            try:
                finished_epoch = datetime.fromisoformat(finished_at_raw).timestamp()
            except ValueError:
                finished_epoch = 0.0
        if finished_epoch >= last_finished_epoch:
            last_finished_epoch = finished_epoch
            last_task_id = task_id
            last_task_status = status

    return TaskSummaryResponse(
        active_tasks=active_tasks,
        last_task_status=last_task_status,
        last_task_id=last_task_id,
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("AIDER_WRAPPER_PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
