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

import ast
import asyncio
import difflib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Operator intervention channel (first cut) — lazily loaded, fails open so a missing/broken
# control module never disrupts the agent loop.
_CONTROL_MOD: Any = None


def _control_channel():
    global _CONTROL_MOD
    if _CONTROL_MOD is None:
        try:
            from importlib.machinery import SourceFileLoader
            _CONTROL_MOD = SourceFileLoader(
                "control_channel", str(Path(__file__).with_name("control_channel.py"))
            ).load_module()
        except Exception:
            _CONTROL_MOD = False
    return _CONTROL_MOD or None

import httpx

# shared/ lives at ai-stack/mcp-servers/shared/ — add parent to path once.
_MCP_SERVERS_PATH = str(Path(__file__).resolve().parents[1] / "mcp-servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)
_AI_LIB_PATH = str(Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib")
if _AI_LIB_PATH not in sys.path:
    sys.path.insert(0, _AI_LIB_PATH)

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
from context_risk import compact_context_if_needed

# P2 (closed-local-improvement-loop): GBNF-constrained tool-call decoding. AQ_LOCAL_GBNF remains
# DEFAULT OFF. Values true/1/on keep the original all-turn grammar plumbing for benchmarking; value
# "repair" constrains only a malformed tool-call retry so final-answer turns are unaffected.
try:
    import tool_grammar  # noqa: E402  (same dir: ai-stack/local-agents/)
except Exception:  # noqa: BLE001 — never let an optional import break the executor
    tool_grammar = None  # type: ignore
_LOCAL_GBNF_MODE = os.environ.get("AQ_LOCAL_GBNF", "").strip().lower()
_LOCAL_GBNF_ALWAYS_ENABLED = _LOCAL_GBNF_MODE in ("1", "true", "yes", "on")
_LOCAL_GBNF_REPAIR_ENABLED = _LOCAL_GBNF_ALWAYS_ENABLED or _LOCAL_GBNF_MODE in ("repair", "retry")

# Record/replay harness (velocity multiplier — deterministic offline replay of local
# inference; see .agents/plans/record-replay-harness/DESIGN.md). Default-OFF
# (AQ_LLM_CASSETTE_MODE unset -> "off") is a strict no-op in _call_llama; wrapped in
# try/except so a broken/missing module never disrupts live inference in that default
# case. BUT: if the operator explicitly requested replay/replay-record (the env var
# is already set at import time), an import failure here must NOT silently degrade to
# live inference — that would defeat replay's "no network" guarantee and mask a real
# regression as a false pass. Fail closed by re-raising in that one case.
try:
    import llm_cassette  # noqa: E402  (same dir: ai-stack/local-agents/)
except Exception as _cassette_import_err:  # noqa: BLE001
    llm_cassette = None  # type: ignore
    _requested_cassette_mode = os.environ.get("AQ_LLM_CASSETTE_MODE", "").strip().lower()
    if _requested_cassette_mode in ("replay", "replay-record"):
        raise RuntimeError(
            f"llm_cassette import failed but AQ_LLM_CASSETTE_MODE={_requested_cassette_mode!r} "
            "was requested — refusing to silently fall back to live inference."
        ) from _cassette_import_err

# Hard-error exceptions from the record/replay harness that must NEVER be masked by a
# generic transient-retry catch (see the LLM-call retry block in _execute_with_tools):
# a strict-replay miss, a replay misconfiguration, or a payload digest mismatch are
# deliberate fail-closed signals, not transport flakiness.
_CASSETTE_HARD_EXCEPTIONS: Tuple[type, ...] = (
    (llm_cassette.ReplayMiss, llm_cassette.ReplayConfigError, llm_cassette.ReplayDigestMismatch)
    if llm_cassette is not None
    else ()
)

# P1 (closed-local-improvement-loop): capture local failures as labeled training samples.
try:
    import training_capture  # noqa: E402
except Exception:  # noqa: BLE001
    training_capture = None  # type: ignore

# Slice 2b (local-embed-context): embed-backed semantic context cache for the prune
# path — best-effort, fail-open. Lives at ai-stack/local-agents/context_cache.py
# (same dir as this module; see F5 in SLICE2-LOCAL-DECOMPOSITION.md).
try:
    import context_cache  # noqa: E402  (same dir: ai-stack/local-agents/)
except Exception:  # noqa: BLE001 — never let an optional import break the executor
    context_cache = None  # type: ignore

# Slice 0.2 (local-context-supply-chain): the read_file gate reuses context_assembler's
# Tier-0 file-chunking helpers (line-aware chunk + '[path:start-end]' citation framing)
# rather than reimplementing them — same embed/Qdrant round-trip pattern, no new code
# path. Best-effort import; the gate fails closed (bounded head, never raw oversized
# file) when this is unavailable — see _gate_large_file_content.
try:
    from context_assembler import (  # noqa: E402  (same dir: ai-stack/local-agents/)
        _chunk_file as _rf_chunk_file,
        _parse_chunk_citation as _rf_parse_chunk_citation,
    )
except Exception:  # noqa: BLE001
    _rf_chunk_file = None  # type: ignore
    _rf_parse_chunk_citation = None  # type: ignore

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

# Dogfood payload budget: deliberately opt-in and isolated from ordinary local
# delegation.  The receipt is count-only so the progress sidecar remains safe
# to expose in operator tooling (no prompt, tool schema, or grammar contents).
# 2026-08-25: raised 14_000 -> 32_000. The old value was BELOW both the real payload
# (~21_896 chars with the full context supply chain) and the model's own
# LLAMA_MAX_PROMPT_CHARS=24_000 prompt guard, so AQ_LOCAL_DOGFOOD_BUDGET rejected every
# dogfood task in 0.4s before HTTP. The payload JSON is legitimately larger than the
# prompt guard (it adds tool schemas + grammar + envelope), so the cap must sit ABOVE
# 24_000; 32_000 gives that headroom while still catching a truly runaway payload.
_DOGFOOD_PAYLOAD_JSON_LIMIT = 32_000  # default; override via AQ_DOGFOOD_PAYLOAD_JSON_LIMIT
_DOGFOOD_FIRST_CALL_MAX_TOKENS = 192


def _dogfood_payload_json_limit() -> int:
    """Max payload JSON chars before dogfood fails closed, read at call time.

    Env-tunable (AQ_DOGFOOD_PAYLOAD_JSON_LIMIT) so operators can adjust the runaway-payload
    ceiling without a code change, and so tests can assert the fail-closed path deterministically
    instead of pinning the module default (which broke test-noaction when the default was raised
    14_000 -> 32_000 and a fixed-size probe stopped exceeding it). Invalid/<=0 values fall back to
    the default.
    """
    raw = os.environ.get("AQ_DOGFOOD_PAYLOAD_JSON_LIMIT", "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return _DOGFOOD_PAYLOAD_JSON_LIMIT


def _dogfood_payload_budget_enabled() -> bool:
    """Return true only for the exact explicitly-enabled dogfood mode."""
    return os.environ.get("AQ_LOCAL_DOGFOOD_BUDGET", "") == "1"


_DOGFOOD_TASK_TYPE_CLASSES = frozenset({
    "structured", "lookup", "code", "reasoning", "agent", "research", "deep_reasoning",
})


def _unicode_chars(value: Any) -> int:
    """Count Unicode characters in canonical JSON/text, never returning content."""
    if not value:
        return 0
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return len(value)


def _dogfood_task_type_class(task_type: Optional[str]) -> str:
    """Keep sidecar receipts count-only: no raw caller-controlled task type."""
    return task_type if task_type in _DOGFOOD_TASK_TYPE_CLASSES else "unknown"


def _dogfood_payload_budget_receipt(
    payload: Dict[str, Any], *, task_type: Optional[str], call_number: int
) -> Dict[str, Any]:
    """Create a deterministic, count-only receipt for one llama request."""
    messages = payload.get("messages") or []
    system_chars = sum(
        _unicode_chars(message.get("content") or "")
        for message in messages
        if message.get("role") == "system"
    )
    non_system_chars = sum(
        _unicode_chars(message.get("content") or "")
        for message in messages
        if message.get("role") != "system"
    )
    payload_json_chars = _unicode_chars(payload)
    return {
        "budget_mode": "AQ_LOCAL_DOGFOOD_BUDGET",
        "call_number": call_number,
        "task_type_class": _dogfood_task_type_class(task_type),
        "system_unicode_chars": system_chars,
        "non_system_unicode_chars": non_system_chars,
        "tools_unicode_chars": _unicode_chars(payload.get("tools")),
        "grammar_unicode_chars": _unicode_chars(payload.get("grammar")),
        "payload_json_unicode_chars": payload_json_chars,
        "estimated_tokens": (payload_json_chars + 3) // 4,
        "max_tokens": payload.get("max_tokens"),
    }


def _enforce_dogfood_payload_budget(
    payload: Dict[str, Any], *, task_type: Optional[str], call_number: int
) -> Optional[Dict[str, Any]]:
    """Persist a receipt and fail closed before HTTP when dogfood is oversized."""
    if not _dogfood_payload_budget_enabled():
        return None
    receipt = _dogfood_payload_budget_receipt(
        payload, task_type=task_type, call_number=call_number
    )
    limit = _dogfood_payload_json_limit()
    rejected = receipt["payload_json_unicode_chars"] > limit
    progress_file = os.getenv("AGENT_PROGRESS_FILE")
    if progress_file:
        try:
            progress_path = Path(progress_file)
            try:
                prior = json.loads(progress_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                prior = {}
            if not isinstance(prior, dict):
                prior = {}
            prior["payload_budget"] = receipt
            if rejected:
                prior["status"] = "payload_budget_rejected"
            progress_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
        except OSError:
            pass
    if rejected:
        raise RuntimeError(
            "dogfood payload budget exceeded before HTTP: "
            f"{receipt['payload_json_unicode_chars']} Unicode JSON chars > {limit}"
        )
    return receipt


def _shed_oldest_assistant_tool_pair(messages: List[Dict]) -> Tuple[List[Dict], bool]:
    """Drop one superseded turn without breaking assistant/tool adjacency.

    Initial agent context may contain more than the usual system+user pair, so
    the first assistant/tool turn is not reliably at indexes 2/3.
    """
    for index in range(2, max(2, len(messages) - 2)):
        if (
            messages[index].get("role") == "assistant"
            and messages[index + 1].get("role") == "tool"
        ):
            return messages[:index] + messages[index + 2 :], True
    return messages, False

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
# Slice 0.2 (local-context-supply-chain): git_add/git_commit removed — local NEVER
# commits (structural, not prompt-hoped). See _AEXEC_COMMIT_TOOLS + AQ_LOCAL_ALLOW_COMMIT.
_AEXEC_ALWAYS_TOOLS: frozenset[str] = frozenset(["read_file", "write_file", "edit_file", "run_command"])

# Commit tools — excluded from the model-visible tool schema AND blocked at the point
# of execution (belt-and-suspenders: the SI-slice system prompt names them by name, so
# a schema-only filter would not stop a call the model emits anyway). Gated behind
# AQ_LOCAL_ALLOW_COMMIT (default off) rather than deleted — the handlers/registration
# in builtin_tools/git_tools.py are untouched.
_AEXEC_COMMIT_TOOLS: frozenset[str] = frozenset(["git_add", "git_commit"])
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


# ── Slice 0.2 (local-context-supply-chain) — enforcement flags ──────────────────
# read_file gate: kill switch AQ_READ_FILE_GATE=0 restores pre-0.2 whole-file behavior.
_READ_FILE_GATE_ENABLED: bool = _env_flag("AQ_READ_FILE_GATE", True)
# ~1500 tok at ~4 chars/tok — matches the DESIGN.md AFTER-run-1 finding: front-loaded
# spans (~1200 tok) + a whole 17KB (~4.3K tok) file blew LLAMA_MAX_PROMPT_CHARS=24000.
_READ_FILE_GATE_CHAR_BUDGET: int = int(os.getenv("AQ_READ_FILE_GATE_CHARS", "6000"))
# Structural no-commit: local NEVER commits by default. Escape hatch, not deletion.
_LOCAL_ALLOW_COMMIT: bool = _env_flag("AQ_LOCAL_ALLOW_COMMIT", False)
# Repeated-read stagnation: on the FIRST threshold breach for a file, inject a one-shot
# edit-forcing intervention (delivered as the read_file tool result, role:"tool") instead
# of aborting immediately. The relevant code is already front-loaded verbatim in context
# under "## Relevant prior knowledge" — the abort was throwing away tasks local could
# complete. A SECOND breach (re-read after the intervention) still aborts as before.
# Kill switch AQ_REREAD_INTERVENTION=0 restores the plain-abort behavior.
_REREAD_INTERVENTION_ENABLED: bool = _env_flag("AQ_REREAD_INTERVENTION", True)


def _normalized_exact_read_range(arguments: Dict[str, Any]) -> Optional[Tuple[str, int, int]]:
    """Return a canonical (path, inclusive-start, inclusive-end) exact read range.

    This deliberately accepts only requests that supplied *both* bounds.  A partial
    range (``start_line`` only or ``end_line`` only) has an open-ended meaning in the
    file tool, so claiming it is covered without executing the tool would be unsafe.
    Path normalization is lexical only: resolving symlinks would perform filesystem
    work on the guard path and could change the tool's existing path semantics.
    """
    if not isinstance(arguments, dict):
        return None
    raw_path = arguments.get("file_path") or arguments.get("path")
    start = arguments.get("start_line")
    end = arguments.get("end_line")
    if not raw_path or start is None or end is None:
        return None
    try:
        normalized_start = int(start)
        normalized_end = int(end)
    except (TypeError, ValueError):
        return None
    if normalized_start < 1 or normalized_end < normalized_start:
        return None
    return os.path.normpath(str(raw_path)), normalized_start, normalized_end


def _range_is_covered(
    coverage: Dict[str, List[Tuple[int, int]]],
    requested: Tuple[str, int, int],
) -> bool:
    """Whether one successful prior exact read wholly covers ``requested``."""
    path, start, end = requested
    return any(previous_start <= start and end <= previous_end
               for previous_start, previous_end in coverage.get(path, []))

# No-action stagnation: on implementer/edit tasks, the model sometimes returns a
# prose PLAN with no parseable tool call at all ("Thought: I would change X so
# that...") and the loop — finding no tool call — treats that as the final
# answer and completes with zero edits. The task's whole point was to EDIT a
# file, so accepting narration as completion is a silent failure. On the FIRST
# such prose-only response (implementer task, zero successful edits so far,
# not a refusal), inject a one-shot corrective nudge instead of completing. A
# SECOND prose-only response still completes as before (never loop forever).
# Kill switch AQ_NOACTION_INTERVENTION=0 restores the plain-completion behavior.
_NOACTION_INTERVENTION_ENABLED: bool = _env_flag("AQ_NOACTION_INTERVENTION", True)
_RETRY_RESPONSE_CHAR_BUDGET = 512


def _bounded_retry_response(response: str) -> str:
    """Keep retry context useful without replaying an entire failed response."""
    if len(response) <= _RETRY_RESPONSE_CHAR_BUDGET:
        return response
    marker = "\n...[retry response truncated]...\n"
    tail_chars = 128
    head_chars = _RETRY_RESPONSE_CHAR_BUDGET - len(marker) - tail_chars
    return response[:head_chars] + marker + response[-tail_chars:]

# Edit-failure feedback: now that the tool-call grammar is fixed, the dominant
# local-agent failure mode is edit_file failing on an old_string byte-mismatch
# (the model paraphrases, or reconstructs old_string from a partial view) and
# then blindly retrying the same mismatch until the task hits its time cap
# (measured: a 12-task dogfood run with grammar ON — ~80% of tasks failed this
# way; example: 1 edit_file attempt, 3 mismatch failures, no edit landed). On
# the FIRST such mismatch failure for a given target file, inject the file's
# EXACT current text for the region the model was trying to edit as the tool
# result (instead of the bare failure) so the model can copy a byte-matching
# old_string on retry. Bounded to _EDIT_FEEDBACK_MAX_PER_FILE fires per file so
# a persistently-failing edit still eventually ends rather than looping
# forever. Kill switch AQ_EDIT_FEEDBACK=0 restores the plain-failure behavior.
_EDIT_FEEDBACK_ENABLED: bool = _env_flag("AQ_EDIT_FEEDBACK", True)
_EDIT_FEEDBACK_MAX_PER_FILE: int = int(os.getenv("AQ_EDIT_FEEDBACK_MAX_PER_FILE", "2"))
_EDIT_FEEDBACK_CHAR_BUDGET: int = int(
    os.getenv("AQ_EDIT_FEEDBACK_CHARS", str(_READ_FILE_GATE_CHAR_BUDGET))
)

# Substrings the edit_file/write_file handlers use to signal an old_string
# byte-mismatch specifically (vs. a different failure class — file-not-found,
# permission, path-validation, OSError — none of which are fixable by showing
# the model more of the file, so those fall through to the plain failure).
_EDIT_MISMATCH_SIGNAL_PHRASES: tuple[str, ...] = (
    "old_string not found", "not found in", "no replacement made",
    "does not match", "did not match",
)

# Post-edit VERIFY-AND-COACH gate (issues-backlog: local-correctness-baseline-
# and-verify-gate). STEWARDSHIP scaffolding (CLAUDE.md Rule 21), not a
# punitive gate: local now RELIABLY LANDS edits (the grammar + edit-feedback
# fixes above worked) but measured dogfood runs show ~0 of those landed edits
# are actually CORRECT. Two dominant failure modes:
#   1. DEAD CODE — a new function/branch is added (e.g. `_gemini_cooldown_status()`)
#      but never wired in / called anywhere — the edit LOOKS like a fix but
#      changes nothing on the live path.
#   2. NO-OP — only a comment or whitespace changed (e.g. a code comment's
#      example flags edited), no behavioral change, doesn't fix the issue.
# After a successful edit_file/write_file/write_region, run cheap STATIC
# checks (no LLM, no test run) on THAT edit's diff before accepting it as
# progress. A failing check injects SPECIFIC, actionable coaching as the tool
# result (role:"tool", mirrors the _EDIT_FEEDBACK_ENABLED pattern above) and
# `continue`s the loop so local gets an immediate retry — bounded to
# _EDIT_VERIFY_MAX_PER_FILE fires per file so a persistently-trivial edit
# still eventually passes through (never blocks forever; the runner/reviewer
# catches it downstream, per Rule 15 activation gate). Fail-safe: any error
# in the verify logic falls through to accepting the edit as-is (never crash
# or hang the loop on a static-analysis bug). Kill switch AQ_EDIT_VERIFY=0
# restores plain accept-on-success behavior.
_EDIT_VERIFY_ENABLED: bool = _env_flag("AQ_EDIT_VERIFY", True)
_EDIT_VERIFY_MAX_PER_FILE: int = int(os.getenv("AQ_EDIT_VERIFY_MAX_PER_FILE", "2"))
# Behavioral verify: the task's ACTUAL check (a test/command) run after the edit.
# The static checks (no-op/dead-code/lint/freshness) are necessary but not
# sufficient — they pass a plausible SEMANTIC wrong-fix (e.g. dogfood-03 hardcoding
# --json: valid bash, right file, still wrong). Only running the task's real check
# catches that. Opt-in via AQ_EDIT_VERIFY_CMD (empty = disabled); "{file}" in the
# command is substituted with the edited path. Bounded + fail-safe.
_BEHAVIORAL_VERIFY_CMD: str = os.getenv("AQ_EDIT_VERIFY_CMD", "").strip()
_BEHAVIORAL_VERIFY_TIMEOUT_S: int = int(os.getenv("AQ_EDIT_VERIFY_TIMEOUT_S", "120"))
_DECLARED_SINGLE_FILE_SCOPE_RE = re.compile(
    r"(?m)^DECLARED SINGLE-FILE SCOPE: ([^\r\n]+)$"
)
_VERIFIED_EDIT_SYNTHESIS_MAX_TOKENS = 96

# Heuristic substrings indicating the model is explicitly declining/stopping
# rather than narrating a plan it forgot to execute. Kept conservative and
# lowercase-matched — false negatives (treated as a plan) just cost one nudge
# turn; false positives (treated as a refusal) would let a real stall through,
# so favor recognizing genuine refusal language.
_REFUSAL_SIGNAL_PHRASES: tuple[str, ...] = (
    "cannot safely", "can't safely", "unable to safely", "not safe to",
    "unsafe to make", "under-specified", "underspecified", "under specified",
    "insufficient information", "not enough information", "requires clarification",
    "need clarification", "too ambiguous", "out of scope", "cannot determine",
    "cannot proceed safely", "i cannot complete this", "i'm unable to complete",
    "will not make this change", "refuse to make", "decline to make",
    "no changes were made because", "cannot make this change",
)


def _looks_like_refusal(text: str) -> bool:
    """True if prose reads as an explicit stop/refusal rather than a forgotten-action plan."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in _REFUSAL_SIGNAL_PHRASES)


def _declared_single_file_scope(objective: str) -> Optional[str]:
    """Return one safe repo-relative declared scope, otherwise None.

    This marker is an opt-in contract for bounded dogfood tasks.  It is exact
    and deliberately rejects duplicates, absolute paths, traversal, and any
    value which escapes the repository root.
    """
    matches = _DECLARED_SINGLE_FILE_SCOPE_RE.findall(objective or "")
    if len(matches) != 1:
        return None
    raw = matches[0].strip()
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        root = _REPO_ROOT_PATH.resolve()
        resolved = (root / candidate).resolve()
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return relative.as_posix()


def _repo_relative_path(file_path: str) -> Optional[str]:
    """Normalize a tool path to a repo-relative path without granting access."""
    if not file_path:
        return None
    try:
        root = _REPO_ROOT_PATH.resolve()
        candidate = Path(file_path)
        resolved = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
        return resolved.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None


def _tool_shaped_synthesis(text: str) -> bool:
    """Recognize output that must never be interpreted as a follow-up tool call."""
    stripped = (text or "").lstrip()
    return bool(re.match(r'\{\s*"(?:function|tool|name)"\s*:', stripped))


def _looks_like_edit_mismatch(error_text: str) -> bool:
    """True if an edit_file failure message signals an old_string byte-mismatch."""
    lowered = (error_text or "").lower()
    return any(phrase in lowered for phrase in _EDIT_MISMATCH_SIGNAL_PHRASES)


def _build_edit_mismatch_feedback(
    file_path: str,
    attempted_old_string: str,
    char_budget: int = _READ_FILE_GATE_CHAR_BUDGET,
    context_lines: int = 12,
) -> Optional[str]:
    """One-shot edit-mismatch feedback body: the file's EXACT current text for
    the region the model was trying to edit, bounded to char_budget.

    Anchors on the first non-blank line of the model's attempted old_string
    (exact substring match first, difflib fuzzy match as fallback) and slices
    +/- context_lines around it. Falls back to a bounded head-of-file slice if
    no anchor can be found. Fail-safe: returns None (never raises) on any
    error — the caller falls through to the plain failure result.
    """
    try:
        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if not path.exists() or not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        anchor_line_no: Optional[int] = None
        attempted_lines = [ln.strip() for ln in (attempted_old_string or "").splitlines() if ln.strip()]
        if attempted_lines:
            anchor = attempted_lines[0]
            for i, line in enumerate(lines):
                if anchor in line:
                    anchor_line_no = i
                    break
            if anchor_line_no is None:
                best_ratio = 0.0
                best_i: Optional[int] = None
                for i, line in enumerate(lines):
                    ratio = difflib.SequenceMatcher(None, anchor, line.strip()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_i = i
                if best_ratio >= 0.4:
                    anchor_line_no = best_i

        if anchor_line_no is not None:
            start = max(0, anchor_line_no - context_lines)
            end = min(len(lines), anchor_line_no + context_lines + 1)
            region = "\n".join(lines[start:end])
            header = f"{file_path} lines {start + 1}-{end} (exact current content):"
        else:
            region = content
            header = f"{file_path} (exact current content, head):"

        if len(region) > char_budget:
            region = region[:char_budget] + "\n... [truncated]"

        return f"{header}\n```\n{region}\n```"
    except Exception:  # noqa: BLE001 — feedback is best-effort, never fatal
        return None


_READ_FILE_GATE_NOTE = (
    "\n\n[GATE] This large file is summarized above (outline + the most "
    "task-relevant sections, with line numbers). Reading the whole file again "
    "returns THIS SAME summary and will stall you — do NOT do it. To make "
    "progress, do exactly one of: (a) if the code you need to change is shown "
    "above, call edit_file NOW with your change; or (b) call "
    "read_file(file_path, start_line=N, end_line=M) for one SPECIFIC region you "
    "have not seen yet. Prefer (a)."
)

# Regex/AST-lite top-level structure scan — (pattern, kind). Order matters: first
# match wins per line. Covers Python/JS/TS defs+classes, shell functions, and
# Markdown/section headers — the common shapes in this repo's read_file traffic.
_OUTLINE_LINE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(?:async\s+def|def)\s+([A-Za-z_]\w*)\s*\("), "def"),
    (re.compile(r"^\s*class\s+([A-Za-z_]\w*)"), "class"),
    (re.compile(r"^\s*function\s+([A-Za-z_]\w*)\s*\("), "function"),
    (re.compile(r"^\s*([A-Za-z_]\w*)\s*\(\)\s*\{"), "function"),  # bash foo() {
    (re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("), "function"),
    (re.compile(r"^(#{1,6})\s+(.+)$"), "section"),  # Markdown headers
]


def _build_file_outline(content: str, file_path: str, max_entries: int = 40) -> str:
    """Compact top-level outline (def/class/section headers + line ranges).

    Simple regex scan, not a real AST — good enough to orient an agent on where to
    request an exact span. Never raises: any scan error degrades to a minimal
    one-line fallback so the caller's fail-closed budget path still has something
    to work with.
    """
    try:
        lines = content.splitlines()
        entries: List[Tuple[int, str]] = []  # (line_no, label)
        for i, line in enumerate(lines, start=1):
            for pattern, kind in _OUTLINE_LINE_PATTERNS:
                m = pattern.match(line)
                if not m:
                    continue
                label = f"{m.group(1)} {m.group(2).strip()}" if kind == "section" else f"{kind} {m.group(1)}"
                entries.append((i, label))
                break
            if len(entries) >= max_entries:
                break
        if not entries:
            return f"## Outline: {file_path} ({len(lines)} lines) — no top-level def/class/section markers found"
        out = [f"## Outline: {file_path} ({len(lines)} lines)"]
        for idx, (line_no, label) in enumerate(entries):
            end = (entries[idx + 1][0] - 1) if idx + 1 < len(entries) else len(lines)
            out.append(f"  {label}  L{line_no}-{end}")
        return "\n".join(out)
    except Exception:  # noqa: BLE001 — outline is a nice-to-have, never fatal
        return f"## Outline: {file_path} (outline scan failed)"


@dataclass
class _EditVerdict:
    """Outcome of one post-edit verify-and-coach static check."""
    passed: bool
    reason: str = ""
    coaching_message: str = ""
    # Completion candidates require a REAL, explicitly-run behavioral check.
    # Static-only edits remain valid normal progress, but must not short-circuit a
    # declared dogfood run.
    behavioral_check_ran: bool = False
    behavioral_check_passed: bool = False


@dataclass(frozen=True)
class _BehavioralVerifyResult:
    """Closed outcome for one declared behavioral verification invocation."""
    failure_output: Optional[str]
    ran: bool
    passed: bool


# Whole-line-comment prefix by extension for the NO-OP check. Best-effort only
# (no tokenizer, doesn't track multi-line string literals) — good enough to
# tell "this edit touched only comments/whitespace" from a real code change.
# Default '#' covers this repo's dominant Python/shell/Nix/YAML mix.
_COMMENT_PREFIX_BY_EXT: Dict[str, str] = {
    ".js": "//", ".ts": "//", ".jsx": "//", ".tsx": "//",
    ".go": "//", ".rs": "//", ".c": "//", ".cpp": "//", ".java": "//",
}


def _non_comment_code_lines(lines: List[str], file_path: str) -> List[str]:
    """Stripped, non-blank lines that are NOT whole-line comments."""
    prefix = _COMMENT_PREFIX_BY_EXT.get(Path(file_path).suffix.lower(), "#")
    return [s for s in (ln.strip() for ln in lines) if s and not s.startswith(prefix)]


def _edit_diff_lines(
    tool_name: str,
    arguments: Dict[str, Any],
    pre_content: Optional[str],
) -> Tuple[List[str], List[str]]:
    """Best-effort (removed_lines, added_lines) for one edit_file/write_file/
    write_region call.

    edit_file's old_string/new_string ARE the diff — no file read needed.
    write_region/write_file need the caller's pre-edit snapshot (captured
    before dispatch, since the file already reflects the post-edit state by
    the time the result reaches the verify gate); if no snapshot was
    captured, `removed` is [] — an UNKNOWN removed side, not a claim the
    removed side was empty. Callers must not treat [] as "definitely a
    no-op" for write_region/write_file.
    """
    if tool_name == "edit_file":
        removed = str(arguments.get("old_string") or "").splitlines()
        added = str(arguments.get("new_string") or "").splitlines()
        return removed, added
    if tool_name == "write_region":
        added = str(arguments.get("new_text") or "").splitlines()
        removed: List[str] = []
        if pre_content is not None:
            try:
                start = int(arguments.get("start_line"))
                end = int(arguments.get("end_line"))
                removed = pre_content.splitlines()[start - 1:end]
            except (TypeError, ValueError, IndexError):
                removed = []
        return removed, added
    if tool_name == "write_file":
        added = str(arguments.get("content") or "").splitlines()
        removed = pre_content.splitlines() if pre_content is not None else []
        return removed, added
    return [], []


def _looks_like_noop_edit(removed: List[str], added: List[str], file_path: str) -> bool:
    """True only when the removed side is KNOWN (non-empty) and both sides
    reduce to the same non-comment/non-blank content — i.e. the edit changed
    only comments/whitespace. An unknown removed side (write_region/write_file
    with no captured pre-image) never triggers this: a false "no-op" coach
    would block a real fix, which is worse than missing one here.
    """
    if not removed:
        return False
    return (
        _non_comment_code_lines(removed, file_path)
        == _non_comment_code_lines(added, file_path)
    )


# Freshness-gaming detection (dogfood-07): a "stale artifact / regenerate" task
# where the ONLY change is bumping a timestamp/date value in a freshness-named field
# is gaming the freshness signal (CLAUDE.md Rule 19 names hand-editing a freshness
# timestamp as gaming), NOT a real fix — the artifact's content is unchanged.
_FRESHNESS_KEY_RE = re.compile(
    r'\b(generated|last[_-]?(evaluated|updated|modified|run|refreshed?|checked)'
    r'|lastmodified|last_modified|updated|refreshed|regenerated|as[_-]?of'
    r'|timestamp|mtime|date)\b',
    re.I,
)
# ISO-8601 date/datetime, or a 10-digit unix epoch (2001..2033 range starts with 1).
_DATE_LIKE_RE = re.compile(
    r'\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?'
    r'|\b1[0-9]{9}\b',
)


def _looks_like_freshness_gaming(removed: List[str], added: List[str]) -> bool:
    """True only when the edit changes NOTHING but a date/timestamp value on a
    freshness-named field — the hallmark of faking freshness instead of doing the
    work (regenerating the artifact). Requires a KNOWN removed side; a large edit
    (a genuine regeneration touches far more than a stamp) never triggers this.
    """
    rem = [l for l in removed if l.strip()]
    add = [l for l in added if l.strip()]
    if not rem or not add:
        return False
    if len(rem) > 4 or len(add) > 4:
        return False  # a real regenerate rewrites content, not just a stamp
    # Mask date-like tokens on both sides; if what's left is identical, the ONLY
    # thing that changed was date/timestamp values.
    def _mask(lines: List[str]) -> List[str]:
        return sorted(_DATE_LIKE_RE.sub("#DATE#", l) for l in lines)
    if _mask(rem) != _mask(add):
        return False  # something other than a date changed -> real edit
    # And at least one changed line must actually be a freshness-named field
    # (otherwise a legit date value elsewhere isn't gaming).
    if not any(_FRESHNESS_KEY_RE.search(l) for l in rem + add):
        return False
    # Guard against the degenerate "no date actually changed" case.
    return any(_DATE_LIKE_RE.search(l) for l in rem)


def _extract_added_definitions(added: List[str]) -> List[str]:
    """Names of new top-level def/class/function statements in `added` lines,
    reusing the same structural scan the read_file outline uses (Python
    def/class, JS/TS function/const-arrow, shell `NAME() {`)."""
    names: List[str] = []
    for line in added:
        for pattern, kind in _OUTLINE_LINE_PATTERNS:
            if kind == "section":  # Markdown headers aren't code definitions
                continue
            m = pattern.match(line)
            if m:
                names.append(m.group(1))
                break
    return names


def _find_dead_added_definition(
    added: List[str], removed: List[str], post_edit_content: str,
) -> Optional[str]:
    """First GENUINELY NEW def/class/function name with zero references
    anywhere else in the file after the edit (only the definition itself
    matches) — i.e. dead code.

    "Genuinely new" excludes any name whose def line was ALSO present on the
    removed side — e.g. an edit that only changes an existing function's
    signature (`def add(a, b):` -> `def add(a, b=0):`) re-includes that def
    line in both old_string and new_string; that is a MODIFICATION of an
    existing function, not a new addition, and must never be flagged as dead
    just because the file has no other caller of a function that already
    existed before this edit.

    Best-effort word-boundary count for the reference check itself: a
    docstring or comment mention would also count as "referenced" (avoids
    the more expensive false-positive of flagging live code as dead).
    """
    pre_existing = set(_extract_added_definitions(removed))
    for name in _extract_added_definitions(added):
        if name in pre_existing:
            continue
        try:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            if len(pattern.findall(post_edit_content)) <= 1:
                return name
        except re.error:
            continue
    return None


# LINT / name-resolution check — the THIRD failure mode (issues-backlog:
# local-edit-third-failure-mode-undefined-name), distinct from no-op and dead
# code: an edit that PARSES fine and isn't dead code but still crashes at
# runtime — e.g. `re.match(...)` added to a file with no `import re`. Python
# is checked with pyflakes when importable (precise undefined-name detection);
# shell is checked with `bash -n` (+ shellcheck errors when installed). Both
# paths degrade to syntax-only when the precise tool is unavailable — never
# raise, never block the loop on a missing optional dependency.
_PY_LINT_EXTENSIONS = frozenset({".py", ".pyi"})
_SHELL_LINT_EXTENSIONS = frozenset({".sh", ".bash"})
_PYFLAKES_LOC_RE = re.compile(r"^\S*?:\d+(?::\d+)?:\s*")
_UNDEFINED_NAME_RE = re.compile(r"undefined name '([\w.]+)'")


def _detect_lint_language(file_path: str, content: str) -> Optional[str]:
    """'python' | 'shell' | None. Extension first, shebang second — a repo
    script can be extensionless with a shebang (e.g. `aq-role-route` is a
    `#!/usr/bin/env python3` script with no `.py` suffix)."""
    suffix = Path(file_path).suffix.lower()
    if suffix in _PY_LINT_EXTENSIONS:
        return "python"
    if suffix in _SHELL_LINT_EXTENSIONS:
        return "shell"
    first_line = content.splitlines()[0] if content else ""
    if first_line.startswith("#!"):
        shebang = first_line.lower()
        if "python" in shebang:
            return "python"
        if "bash" in shebang or "/sh" in shebang or shebang.rstrip().endswith(" sh"):
            return "shell"
    return None


def _pyflakes_messages(content: str, label: str) -> Optional[List[str]]:
    """Bare pyflakes message text (location prefix stripped, so pre/post diffs
    aren't thrown off by line numbers shifting). Returns None — a sentinel,
    NOT "clean" — when pyflakes isn't importable, so callers can fall back to
    compile-only checking instead of silently treating "no findings" as
    "found nothing to report"."""
    try:
        from pyflakes.api import check as _pyflakes_check_fn
        from pyflakes.reporter import Reporter
    except ImportError:
        return None
    import io
    out, err = io.StringIO(), io.StringIO()
    try:
        _pyflakes_check_fn(content, label, Reporter(out, err))
    except Exception:
        return []  # pyflakes itself choked — treat as "no findings", not "unavailable"
    raw = out.getvalue().splitlines() + err.getvalue().splitlines()
    return [_PYFLAKES_LOC_RE.sub("", ln, count=1).strip() for ln in raw if ln.strip()]


def _python_compile_error(content: str, label: str) -> Optional[str]:
    """Syntax-only fallback for when pyflakes is unavailable. Never raises."""
    try:
        compile(content, label, "exec", ast.PyCF_ONLY_AST)
        return None
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    except Exception as e:  # noqa: BLE001 — any other compile-time failure counts too
        return f"{type(e).__name__}: {e}"


def _lint_diff_python(post_content: str, pre_content: Optional[str]) -> Optional[str]:
    """New Python lint finding introduced by this edit, or None. Diffs
    pre/post pyflakes output as multisets so a pre-existing warning is never
    re-flagged just because the edit shifted its line number."""
    post_msgs = _pyflakes_messages(post_content, "post_edit.py")
    if post_msgs is not None:
        if pre_content is not None:
            pre_msgs = _pyflakes_messages(pre_content, "pre_edit.py") or []
            new_msgs = list((Counter(post_msgs) - Counter(pre_msgs)).elements())
        else:
            # No pre-image: conservative — only the undefined-name class this
            # check exists to catch, not the full pyflakes noise floor (unused
            # imports etc.) that may well predate this edit.
            new_msgs = [m for m in post_msgs if "undefined name" in m]
        return "; ".join(sorted(set(new_msgs))[:5]) if new_msgs else None

    # Fallback: pyflakes not importable in this env — compile-only syntax check.
    post_err = _python_compile_error(post_content, "post_edit.py")
    if post_err is None:
        return None
    if pre_content is not None and _python_compile_error(pre_content, "pre_edit.py") is not None:
        return None  # pre-existing syntax error — not introduced by this edit
    return post_err


def _shell_syntax_error(content: str) -> Optional[str]:
    """`bash -n` (parse-only, no execution) syntax check. Never raises."""
    try:
        proc = subprocess.run(
            ["bash", "-n"], input=content, capture_output=True, text=True, timeout=5,
        )
        if proc.returncode != 0:
            return (proc.stderr or "").strip()[:400] or "bash -n: syntax error"
        return None
    except Exception:
        return None


def _shellcheck_error_messages(content: str) -> Optional[List[str]]:
    """shellcheck error-level (not style/info) findings, or None if shellcheck
    isn't installed — a sentinel distinct from "clean", same contract as
    _pyflakes_messages."""
    if shutil.which("shellcheck") is None:
        return None
    try:
        proc = subprocess.run(
            ["shellcheck", "-f", "json", "-s", "bash", "-"],
            input=content, capture_output=True, text=True, timeout=8,
        )
        findings = json.loads(proc.stdout or "[]")
    except Exception:
        return []  # shellcheck itself choked — treat as "no findings"
    return [
        f"{item.get('level')}: {item.get('message')}"
        for item in findings if item.get("level") == "error"
    ]


def _lint_diff_shell(post_content: str, pre_content: Optional[str]) -> Optional[str]:
    """New shell lint finding introduced by this edit, or None."""
    post_syntax_err = _shell_syntax_error(post_content)
    if post_syntax_err is not None:
        pre_had_same_error = (
            pre_content is not None and _shell_syntax_error(pre_content) is not None
        )
        if not pre_had_same_error:
            return f"bash -n: {post_syntax_err}"

    post_sc = _shellcheck_error_messages(post_content)
    if post_sc:
        if pre_content is not None:
            pre_sc = _shellcheck_error_messages(pre_content) or []
            new_sc = list((Counter(post_sc) - Counter(pre_sc)).elements())
        else:
            new_sc = []  # no pre-image: trust only the bash -n hard-error path above
        if new_sc:
            return "; ".join(sorted(set(new_sc))[:5])
    return None


def _lint_check_edited_file(
    file_path: str, post_edit_content: str, pre_edit_content: Optional[str],
) -> Optional[str]:
    """Cheap post-edit LINT / name-resolution check on the FULL edited file —
    catches would-crash edits that pass the no-op and dead-code checks (valid
    syntax, genuinely new code, wired in) but reference something undefined,
    e.g. `re.match(...)` with no `import re`. Lints post-edit content and,
    when pre-edit content is available (see _reconstruct_pre_edit_content),
    diffs against pre-edit findings so ONLY newly-introduced issues are
    reported — pre-existing lint debt this edit didn't touch is never
    flagged. Returns a short finding string, or None (clean / not a
    lintable language / lint itself failed). Fail-safe: never raises.
    """
    lang = _detect_lint_language(file_path, post_edit_content)
    if lang == "python":
        return _lint_diff_python(post_edit_content, pre_edit_content)
    if lang == "shell":
        return _lint_diff_shell(post_edit_content, pre_edit_content)
    return None


def _reconstruct_pre_edit_content(
    tool_name: str,
    arguments: Dict[str, Any],
    post_edit_content: str,
    pre_content: Optional[str],
) -> Optional[str]:
    """Full pre-edit FILE content for the lint-diff check (as opposed to
    _edit_diff_lines' removed/added LINES). write_region/write_file already
    have a real pre-edit snapshot captured before dispatch — reuse it as-is.
    edit_file has no such snapshot (the line-diff check never needed one:
    old_string/new_string ARE the diff), but since edit_file is an exact
    substring replacement, the pre-edit file can be reconstructed by
    reversing it on the post-edit content. Conservative: only reconstructs
    when new_string appears EXACTLY ONCE in the post-edit content — an
    ambiguous multi-match reversal could silently rebuild the wrong file —
    and returns None (unknown pre-image) otherwise, which callers already
    treat safely as "be conservative, don't over-flag."
    """
    if tool_name in ("write_region", "write_file"):
        return pre_content
    if tool_name == "edit_file":
        new_string = str(arguments.get("new_string") or "")
        old_string = str(arguments.get("old_string") or "")
        if not new_string or post_edit_content.count(new_string) != 1:
            return None
        return post_edit_content.replace(new_string, old_string, 1)
    return None


# Task-relevance heuristic input: ONLY backtick-quoted symbols/snippets or bare
# file paths with an extension — freeform prose parsing is too false-positive-
# prone for a coaching gate. An objective with none of these shapes yields no
# targets, and the check is skipped entirely (never flags on no signal).
_TASK_TARGET_TOKEN_RE = re.compile(
    r"`([^`\s][^`]{1,78}[^`\s]|[^`\s])`"       # `backtick_quoted_symbol_or_snippet`
    r"|(\b[\w./-]*/[\w./-]+\.[A-Za-z]{1,5}\b)"  # bare/relative file path w/ extension
)


def _extract_task_named_targets(objective: str) -> List[str]:
    """Conservative extraction of specific symbols/files the task objective
    names — see _TASK_TARGET_TOKEN_RE. Best-effort + optional by design."""
    if not objective:
        return []
    targets: List[str] = []
    for m in _TASK_TARGET_TOKEN_RE.finditer(objective):
        token = (m.group(1) or m.group(2) or "").strip()
        if token:
            targets.append(token)
    return targets


def _edit_touches_named_targets(
    targets: List[str], file_path: str, removed: List[str], added: List[str],
) -> bool:
    haystack = file_path + "\n" + "\n".join(removed) + "\n" + "\n".join(added)
    return any(t in haystack or t.rstrip("()") in haystack for t in targets)


def _behavioral_verify_result(file_path: str) -> _BehavioralVerifyResult:
    """Run the declared check and retain whether it actually executed.

    The legacy verification gate is deliberately fail-open when a check is
    unavailable.  Completion candidates are stricter: they need evidence that
    the declared command ran and returned zero, rather than merely observing no
    failure text.  Keeping that distinction here avoids changing normal task
    behavior.
    """
    if not _BEHAVIORAL_VERIFY_CMD:
        return _BehavioralVerifyResult(None, ran=False, passed=False)
    cmd = _BEHAVIORAL_VERIFY_CMD.replace("{file}", shlex.quote(file_path))
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True,
            timeout=_BEHAVIORAL_VERIFY_TIMEOUT_S, cwd=os.getcwd(),
        )
    except Exception:  # noqa: BLE001 — existing verify gate remains fail-open
        return _BehavioralVerifyResult(None, ran=False, passed=False)
    if proc.returncode == 0:
        return _BehavioralVerifyResult(None, ran=True, passed=True)
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    return _BehavioralVerifyResult(
        tail[-800:] if tail else f"check exited with status {proc.returncode}",
        ran=True,
        passed=False,
    )


def _behavioral_verify(file_path: str) -> Optional[str]:
    """Run the task's declared behavioral check (AQ_EDIT_VERIFY_CMD) after an edit.

    Returns None on PASS (exit 0) or a truncated failure output on non-zero exit.
    This is the gate that catches SEMANTIC wrong-fixes the static checks cannot:
    an edit that parses, lints, isn't a no-op, touches the right file, yet breaks
    the behavior (dogfood-03 hardcoding --json). Only a real run surfaces it.

    Fail-safe: a failure to RUN the command (missing tool, timeout, exception) is
    NOT a test failure — it degrades to None (skip) so a broken harness never
    blocks a legitimate edit. Only a genuine non-zero exit of the check coaches.
    """
    return _behavioral_verify_result(file_path).failure_output


def _verify_edit_quality(
    tool_name: str,
    arguments: Dict[str, Any],
    file_path: str,
    pre_content: Optional[str],
    task_objective: str,
) -> _EditVerdict:
    """Cheap static checks on ONE edit's diff — no LLM, no test run.

    STEWARDSHIP framing (CLAUDE.md Rule 21): the coaching messages are
    specific and actionable, never a bare rejection — the goal is to help
    local land its NEXT attempt, not to punish this one. Never raises on its
    own — callers additionally wrap this in try/except (fail-safe: a bug in
    this function must never block or crash the loop, only skip coaching).
    """
    removed, added = _edit_diff_lines(tool_name, arguments, pre_content)

    if _looks_like_noop_edit(removed, added, file_path):
        return _EditVerdict(
            passed=False,
            reason="noop_comment_or_whitespace_only",
            coaching_message=(
                "Your edit only changed a comment or whitespace — it does not "
                "change the program's behavior, so it does not fix the task. "
                "Make the actual code/logic change the task requires (a new "
                "condition, a different value, a call to the right function, "
                "etc.), then retry the edit."
            ),
        )

    if _looks_like_freshness_gaming(removed, added):
        return _EditVerdict(
            passed=False,
            reason="freshness_timestamp_gaming",
            coaching_message=(
                "Your edit only bumped a date/timestamp field — that fakes the "
                "freshness signal without regenerating the artifact, so the "
                "stale content is still stale. If the task is to refresh/rebuild "
                "an artifact, run the generator/command that regenerates it (its "
                "content AND its timestamp), don't hand-edit the timestamp. If "
                "you can't regenerate it here, say so instead of editing the date."
            ),
        )

    post_edit_content: Optional[str] = None
    try:
        p = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if p.exists() and p.is_file():
            post_edit_content = p.read_text(encoding="utf-8")
    except OSError:
        post_edit_content = None

    if post_edit_content is not None:
        dead_name = _find_dead_added_definition(added, removed, post_edit_content)
        if dead_name:
            return _EditVerdict(
                passed=False,
                reason=f"dead_code:{dead_name}",
                coaching_message=(
                    f"You added `{dead_name}` but nothing calls it anywhere else "
                    f"in the file — it's dead code that changes no behavior on "
                    f"the live path. Wire it in: call `{dead_name}` from the "
                    f"place the task needs the new behavior, or, if a separate "
                    f"function isn't needed, fold the change in inline instead."
                ),
            )

        # THIRD failure mode (issues-backlog: local-edit-third-failure-mode-
        # undefined-name): the edit parses, isn't a no-op, isn't dead code —
        # but still references something undefined and would crash at
        # runtime (e.g. `re.match(...)` with no `import re`). Lint-diffed
        # against the pre-edit file so only NEW breakage is coached, never
        # pre-existing lint debt. Wrapped separately so a lint-tooling bug
        # (missing pyflakes/shellcheck, subprocess failure, etc.) degrades to
        # "skip this check" without affecting the checks above/below it.
        lint_issue: Optional[str] = None
        try:
            pre_edit_full = _reconstruct_pre_edit_content(
                tool_name, arguments, post_edit_content, pre_content,
            )
            lint_issue = _lint_check_edited_file(file_path, post_edit_content, pre_edit_full)
        except Exception:  # noqa: BLE001 — fail-safe: skip the lint check, never crash the loop
            lint_issue = None
        if lint_issue:
            name_match = _UNDEFINED_NAME_RE.search(lint_issue)
            if name_match:
                bad_name = name_match.group(1)
                coaching_message = (
                    f"Your edit uses `{bad_name}` but it's not imported/defined "
                    f"in this file — add `import {bad_name}` at the top (or the "
                    f"correct import for it), or use a different approach that "
                    f"doesn't need it."
                )
            else:
                coaching_message = (
                    f"Your edit introduces a problem that will break the file: "
                    f"{lint_issue}. Fix that before moving on."
                )
            return _EditVerdict(
                passed=False,
                reason=f"lint_new_error:{lint_issue[:80]}",
                coaching_message=coaching_message,
            )

    targets = _extract_task_named_targets(task_objective or "")
    if targets and not _edit_touches_named_targets(targets, file_path, removed, added):
        named = ", ".join(f"`{t}`" for t in targets)
        return _EditVerdict(
            passed=False,
            reason="task_relevance_miss",
            coaching_message=(
                f"Your edit doesn't touch {named} — the task specifically names "
                f"that target. Re-read the task and edit the right place."
            ),
        )

    # BEHAVIORAL verify (last, and only once the static checks pass): run the
    # task's actual check. This is what turns "confidently wrong" into "iterate to
    # correct" — the static gates above cannot see a semantic wrong-fix.
    behavioral_result = _behavioral_verify_result(file_path)
    if behavioral_result.failure_output:
        return _EditVerdict(
            passed=False,
            reason="behavioral_verify_failed",
            coaching_message=(
                "Your edit is syntactically fine but FAILS the task's own check "
                "when actually run:\n\n" + behavioral_result.failure_output + "\n\nThat's a behavior "
                "bug, not a syntax one. Read the failure above, change what the code "
                "DOES (not just how it reads), and retry the edit."
            ),
        )

    return _EditVerdict(
        passed=True,
        behavioral_check_ran=behavioral_result.ran,
        behavioral_check_passed=behavioral_result.passed,
    )


def _gate_large_file_content(
    content: str,
    file_path: str,
    task_objective: str,
    task_id: str,
    budget_chars: Optional[int] = None,
) -> Tuple[str, bool]:
    """Slice 0.2 read_file gate (the load-bearing fix — see DESIGN.md AFTER-run-1).

    Files at/under budget pass through unchanged: (content, False).

    Oversized files return (outline + top task-relevant chunks + note, True). Chunks
    are retrieved by ephemeral-indexing the file via context_cache.cache_evicted +
    retrieve_ctx (same Tier-0 pattern as context_assembler.py's file-targeted
    retrieval) against `task_objective`, k=4, each carrying a real
    '[path:start-end]' citation baked in by context_assembler._chunk_file.

    FAIL-CLOSED on size (the actual invariant this gate exists to enforce): if the
    outline/retrieval path fails for ANY reason (missing deps, dead embed/Qdrant,
    empty retrieval, or a result that still doesn't fit), this falls back to a
    bounded head of the raw content plus the same note. It NEVER returns content
    larger than `budget_chars` and it NEVER raises.
    """
    budget = budget_chars if budget_chars is not None else _READ_FILE_GATE_CHAR_BUDGET
    if len(content) <= budget:
        return content, False

    gated: Optional[str] = None
    try:
        outline = _build_file_outline(content, file_path)
        chunk_blocks: List[str] = []
        if context_cache is not None and _rf_chunk_file is not None:
            chunks = _rf_chunk_file(content, file_path)
            if chunks:
                ephemeral_id = f"{task_id}-rfgate-{abs(hash(file_path)) % 1_000_000}"
                collection = context_cache.cache_evicted(ephemeral_id, chunks, timeout=8.0)
                if collection:
                    try:
                        retrieved = context_cache.retrieve_ctx(
                            collection, task_objective or file_path, k=4, timeout=8.0,
                        )
                    finally:
                        context_cache.delete_collection(collection, timeout=8.0)
                    for raw in retrieved:
                        parsed = _rf_parse_chunk_citation(raw) if _rf_parse_chunk_citation else None
                        if not parsed:
                            continue
                        citation, body = parsed
                        # NOTE: strip('\n') only, never strip() — a bare .strip()
                        # eats leading whitespace CHARACTERS from the chunk's
                        # first line, which is indentation whenever a chunk
                        # boundary lands mid-indented-block (the norm: _chunk_file
                        # slices at a flat FILE_CHUNK_LINES stride, blind to code
                        # structure). That silently mangles the one property this
                        # gate exists to preserve: a byte-exact edit_file
                        # old_string built from the chunk. strip('\n') only trims
                        # incidental leading/trailing blank lines.
                        chunk_blocks.append(f"[{citation}]\n" + body.strip("\n"))
        # Full success requires BOTH the outline AND at least one retrieved chunk —
        # per spec this gate returns outline+chunks together, not one or the other.
        # Any partial failure (embed/Qdrant down, cache_evicted None, zero relevant
        # chunks) falls all the way through to the bounded-head fail-closed path
        # below rather than emitting a half-useful outline-only result.
        gated = (
            outline + "\n\n## Top task-relevant chunks\n" + "\n\n".join(chunk_blocks)
            if chunk_blocks else None
        )
    except Exception:  # noqa: BLE001 — fail CLOSED below, never raise, never return raw content
        gated = None

    if not gated:
        gated = content[: max(budget - len(_READ_FILE_GATE_NOTE), 0)]
    gated = gated + _READ_FILE_GATE_NOTE
    if len(gated) > budget:
        # Belt-and-suspenders: outline+chunks (or even the head slice above) can still
        # overshoot budget (e.g. a huge outline). Unconditional final clamp is what
        # actually guarantees the size invariant, independent of which path produced `gated`.
        gated = gated[: max(budget - len(_READ_FILE_GATE_NOTE), 0)] + _READ_FILE_GATE_NOTE
    # ABSOLUTE final clamp: when budget < len(note) the note-aware clamp above still
    # returns the whole note (> budget). A hard slice guarantees len(gated) <= budget
    # in every case (fail-closed on size is not negotiable, even for a tiny budget).
    if len(gated) > budget:
        gated = gated[:budget]
    return gated, True


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

    # Populated only by the declared verified-edit completion path.  It is a
    # closed, typed receipt suitable for progress/event surfaces.
    completion_evidence: Optional[Dict[str, Any]] = None

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
            "completion_evidence": self.completion_evidence,
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
        wall_budget_s: float = 0.0,
    ) -> Task:
        """
        Execute a task using local agent with tool use.

        Args:
            task: Task to execute
            agent_type: Type of agent to use
            max_tool_calls: Hard ceiling on tool calls for this run. 0 (default)
                means "use the AQ_AGENT_MAX_TOOL_CALLS env override, or the
                built-in default of 40 if that's unset too" — NOT unlimited.
                Stagnation/progress guards still fire first (smarter, earlier
                exits); this is the outer backstop that guarantees the loop
                terminates even when tool outputs keep changing and evade
                every stagnation counter. Pass an explicit value > 0 to raise
                (or lower) the ceiling for a deliberately long-running task.
            wall_budget_s: Hard wall-clock budget in seconds for this run. 0
                (default) means "use the AQ_AGENT_WALL_BUDGET_S env override,
                or the built-in default of 3600s (1h) if that's unset too" —
                NOT unlimited. Same backstop role as max_tool_calls, for the
                case where a slow single call would otherwise outlast the
                tool-call ceiling.

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
                wall_budget_s=wall_budget_s,
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
                    "completion_evidence": task.completion_evidence,
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
        wall_budget_s: float = 0.0,
    ) -> Tuple[Any, int]:
        """
        Execute task with tool use loop.

        Tool use loop:
        1. Send prompt + tools to model
        2. Parse response for tool calls
        3. Execute tool calls
        4. Append results to context
        5. Repeat until no more tool calls, a stagnation/progress guard fires,
           or a hard termination bound (tool-call ceiling / wall-clock budget)
           trips. The loop body is NEVER unbounded: see the "Hard termination
           bounds" block below for the always-enforced backstop (HIGH — Codex
           review finding 5, .agent/collaboration/codex-review-local-agent-batch-20260821.md).
        """
        # Get tools for model.
        # A.6 — _all_tools is the full registry snapshot (hot-swap source, never depleted).
        # _active_tools starts as the full set and may expand mid-loop via _refresh_active_tools.
        # The system prompt is rebuilt whenever _active_tools changes so the model always
        # sees the current tool surface without a full context reload.
        _all_tools = self.tool_registry.get_tools_for_model()
        # Slice 0.2 — structural no-commit: exclude git_add/git_commit from the
        # model-visible schema by default. Filtering here (the hot-swap source) also
        # keeps them out of _refresh_active_tools' candidate pool, so no later
        # keyword-triggered hot-swap can reintroduce them either.
        if not _LOCAL_ALLOW_COMMIT:
            _all_tools = [t for t in _all_tools if t.get("name") not in _AEXEC_COMMIT_TOOLS]
        _active_tools = list(_all_tools)

        # Build initial prompt
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(
                    agent_type, _active_tools, task.objective,
                    task.context.get("_local_skill_projection", ""),
                ),
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

        # Hard termination bounds (HIGH — Codex review finding 5, 20260821: the loop used
        # `while True` and accepted max_tool_calls but IGNORED it — see the old docstring
        # this replaced, "governed by stagnation/progress guards ... not by a fixed
        # tool-call ceiling"). The stagnation guards below only catch IDENTICAL repeated
        # results; an agent that alternates tool calls with results that keep CHANGING
        # (but make no real progress) resets every stagnation counter and can loop
        # indefinitely, burning the APU with no exit. These two bounds are the outer
        # backstop — checked first, at the top of every iteration — that guarantees
        # termination regardless of what the stagnation guards see. They never preempt
        # the stagnation guards: those fire mid-iteration (smarter, earlier exits) before
        # the loop ever reaches the top of the next iteration where these are checked.
        # Overridable per call (max_tool_calls / wall_budget_s params, e.g. for a
        # deliberately long-running task) or via env (AQ_AGENT_MAX_TOOL_CALLS /
        # AQ_AGENT_WALL_BUDGET_S) — but the default is ALWAYS bounded, never unlimited.
        if max_tool_calls and max_tool_calls > 0:
            _HARD_TOOL_CALL_CEILING = max_tool_calls
        else:
            try:
                _HARD_TOOL_CALL_CEILING = int(os.environ.get("AQ_AGENT_MAX_TOOL_CALLS", "40"))
            except ValueError:
                _HARD_TOOL_CALL_CEILING = 40
        if wall_budget_s and wall_budget_s > 0:
            _HARD_WALL_BUDGET_S = float(wall_budget_s)
        else:
            try:
                _HARD_WALL_BUDGET_S = float(os.environ.get("AQ_AGENT_WALL_BUDGET_S", "3600"))
            except ValueError:
                _HARD_WALL_BUDGET_S = 3600.0

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
        # Implementation tasks abort early on over-exploration. Analysis-only work may
        # read much more, but must checkpoint through store_memory/write_file and may
        # not spin on the same file path.
        _reads_without_edit = 0
        _read_path_counts: dict = {}
        _ANALYSIS_ONLY_TASK_TYPES = frozenset({
            "research", "analysis", "analysis_only", "research_only",
            "planning", "prd", "deep_reasoning",
        })
        _is_analysis_only_task = (task.task_type or "").lower() in _ANALYSIS_ONLY_TASK_TYPES
        # Stagnation thresholds are env-tunable so we can empirically probe where the
        # boundary is the GUARD vs the model (capability-envelope experiments). Defaults
        # unchanged — set AI_AGENT_* only for controlled runs. Large-file multi-edit
        # tasks legitimately re-read to locate several edit sites; too-tight limits abort
        # a capable model prematurely.
        _env_int = lambda name, default: max(1, int(os.environ.get(name, str(default))))
        _IMPLEMENTATION_MAX_READS_WITHOUT_EDIT = _env_int("AI_AGENT_IMPL_MAX_READS_WITHOUT_EDIT", 8)
        _IMPLEMENTATION_READS_HARD_LIMIT = _env_int("AI_AGENT_IMPL_READS_HARD_LIMIT", 12)
        _ANALYSIS_MAX_READS_WITHOUT_CHECKPOINT = _env_int("AI_AGENT_ANALYSIS_MAX_READS", 24)
        _ANALYSIS_READS_HARD_LIMIT = _env_int("AI_AGENT_ANALYSIS_READS_HARD_LIMIT", 80)
        _REPEATED_READ_PATH_LIMIT = _env_int("AI_AGENT_REPEATED_READ_PATH_LIMIT", 4)
        _MAX_READS_WITHOUT_EDIT = (
            _ANALYSIS_MAX_READS_WITHOUT_CHECKPOINT
            if _is_analysis_only_task else _IMPLEMENTATION_MAX_READS_WITHOUT_EDIT
        )
        _READS_HARD_LIMIT = (
            _ANALYSIS_READS_HARD_LIMIT
            if _is_analysis_only_task else _IMPLEMENTATION_READS_HARD_LIMIT
        )
        _exploration_nudge_sent = False
        # Repeated-read stagnation: fires the edit-forcing intervention exactly once per
        # task. Set True the moment the intervention message is queued (not only on full
        # success) so a second breach — with or without a mid-construction error — falls
        # straight through to the plain abort rather than looping interventions forever.
        _reread_intervention_sent = False
        # Exact ranged-read coverage: once a successful explicit [start, end]
        # result has reached the model, a later range wholly inside it is redundant.
        # Keep this separate from the broad repeated-path guard: legitimate
        # non-overlapping reads must continue to reach the real file tool.
        _successful_exact_read_coverage: Dict[str, List[Tuple[int, int]]] = {}
        _redundant_range_intervention_sent = False
        _redundant_range_abort_message: Optional[str] = None
        # No-action guard: counts successful edit_file/write_file calls this run, and
        # whether the one-shot no-action intervention has already fired. See the
        # _NOACTION_INTERVENTION_ENABLED block above for the full rationale.
        _edits_made = 0
        _no_action_intervention_sent = False
        # Edit-failure feedback: fires per target file (a task may edit several
        # files), bounded to _EDIT_FEEDBACK_MAX_PER_FILE per path. See the
        # _EDIT_FEEDBACK_ENABLED block above for the full rationale.
        _edit_feedback_counts: dict = {}  # file_path → feedback-fire count
        # Post-edit verify-and-coach gate (see _EDIT_VERIFY_ENABLED above):
        # per-file coaching-fire count (bounded to _EDIT_VERIFY_MAX_PER_FILE),
        # and the pre-edit content snapshot captured right before each
        # edit_file/write_file/write_region dispatch (write_region/write_file
        # need the "before" side to compute a diff — the file already
        # reflects the "after" side by the time the tool result reaches us).
        _edit_verify_counts: dict = {}  # file_path → coach-fire count
        _verify_pre_edit_content: dict = {}  # file_path → content before the in-flight call
        # A completion candidate is intentionally opt-in: normal tasks keep the
        # ordinary tool loop.  For the marked case, retain every accepted write
        # so an out-of-scope earlier edit can never be hidden by a later good one.
        _declared_completion_scope = _declared_single_file_scope(task.objective)
        _accepted_write_paths: list[str] = []
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
            "edit_file", "write_file", "write_region", "git_add", "git_commit",
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
        _dogfood_initial_llm_call_pending = True

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

        _ctrl_cursor = 0  # operator control-channel read cursor (messages consumed)
        while True:
            # Hard termination bounds — checked FIRST, every iteration, before any LLM
            # call is made. This is the outer backstop (see setup block above): every
            # stagnation/progress guard for the PRIOR iteration's tool result has already
            # had its chance to return early, so reaching here means none of them fired.
            if tool_call_count >= _HARD_TOOL_CALL_CEILING:
                hard_bound_msg = (
                    f"Hard tool-call ceiling {_HARD_TOOL_CALL_CEILING} reached at call "
                    f"{tool_call_count} — loop terminated to guarantee bounded execution "
                    "(stagnation guards did not catch this run because tool outputs kept "
                    "changing). Override with the max_tool_calls param or "
                    "AQ_AGENT_MAX_TOOL_CALLS for a deliberately long-running task."
                )
                logger.warning(
                    "hard tool-call ceiling reached: count=%d limit=%d — terminating loop",
                    tool_call_count, _HARD_TOOL_CALL_CEILING,
                )
                _cancel_watchdog()
                await self._emit_agent_event(
                    task.id, "agent_hard_bound",
                    {
                        "bound": "max_tool_calls",
                        "tool_call_count": tool_call_count,
                        "limit": _HARD_TOOL_CALL_CEILING,
                    },
                    _watchdog_last_activity,
                )
                return hard_bound_msg, total_tokens

            _hard_bound_elapsed = time.time() - _loop_start
            if _hard_bound_elapsed >= _HARD_WALL_BUDGET_S:
                hard_bound_msg = (
                    f"Hard wall-clock budget {_HARD_WALL_BUDGET_S:.0f}s reached "
                    f"({_hard_bound_elapsed:.1f}s elapsed) at tool call {tool_call_count} — "
                    "loop terminated to guarantee bounded execution. Override with the "
                    "wall_budget_s param or AQ_AGENT_WALL_BUDGET_S for a deliberately "
                    "long-running task."
                )
                logger.warning(
                    "hard wall-clock budget reached: elapsed=%.1fs limit=%.1fs call=%d — terminating loop",
                    _hard_bound_elapsed, _HARD_WALL_BUDGET_S, tool_call_count,
                )
                _cancel_watchdog()
                await self._emit_agent_event(
                    task.id, "agent_hard_bound",
                    {
                        "bound": "wall_budget_s",
                        "elapsed_s": round(_hard_bound_elapsed, 1),
                        "limit_s": _HARD_WALL_BUDGET_S,
                        "tool_call_count": tool_call_count,
                    },
                    _watchdog_last_activity,
                )
                return hard_bound_msg, total_tokens

            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
            await self._emit_agent_event(
                task.id, "agent_step_start",
                {"tool_call_count": tool_call_count},
                _watchdog_last_activity,
            )

            # Operator intervention channel — poll the per-task control queue between turns
            # and inject any operator messages into the conversation (or a soft-stop on
            # cancel). Fails open: the loop is never disrupted by a control-channel error.
            try:
                _cc = _control_channel()
                if _cc is not None:
                    _new_ctrl, _ctrl_cursor = _cc.poll(task.id, _ctrl_cursor)
                    for _cm in _new_ctrl:
                        _txt = (_cm.get("text") or "").strip()
                        if _cm.get("kind") == "cancel":
                            messages.append({"role": "user", "content":
                                "[OPERATOR INTERVENTION — STOP] Finalize now and stop. " + _txt})
                        elif _txt:
                            messages.append({"role": "user", "content":
                                "[OPERATOR INTERVENTION] " + _txt})
                    if _new_ctrl:
                        await self._emit_agent_event(
                            task.id, "operator_inject",
                            {"count": len(_new_ctrl)}, _watchdog_last_activity,
                        )
            except Exception:
                pass

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
                # Slice 2b — semantic scratchpad: recover the evicted middle by relevance
                # to the current objective, inserted AFTER the pinned prefix (index 4,
                # never spliced into it) so llama.cpp prefix-cache reuse is preserved.
                # context_cache is sync (httpx.Client) — offload via asyncio.to_thread so
                # the event loop never blocks. Fail-open: any error → no scratchpad, same
                # as today's pinned+sliding behavior.
                _scratch = None
                if context_cache is not None:
                    try:
                        _dropped_texts = [m.get("content") or "" for m in messages[4:-4]
                                          if m.get("role") in {"assistant", "tool"} and m.get("content")]
                        if _dropped_texts:
                            _coll = await asyncio.to_thread(context_cache.cache_evicted, str(task.id), _dropped_texts)
                            if _coll:
                                _retr = await asyncio.to_thread(context_cache.retrieve_ctx, _coll, str(task.objective), 6)
                                _scratch = context_cache.scratchpad_message(_retr)  # pure, no I/O
                    except Exception:
                        _scratch = None
                messages = pinned + ([_scratch] if _scratch else []) + sliding
                logger.debug(
                    "context_prune(pinned+sliding): pinned=%d sliding=%d total=%d chars_before=%d scratch=%s",
                    len(pinned), len(sliding), len(messages), _ctx_chars, bool(_scratch),
                )
            elif _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 6:
                # Fallback for 6 < len ≤ 8: shed the oldest complete pair.  A
                # context-system message may precede it, so locate roles instead
                # of assuming the pair is fixed at indexes 2/3.
                messages, _shed_pair = _shed_oldest_assistant_tool_pair(messages)
                if _shed_pair:
                    logger.debug("context_prune(shed-oldest-pair): messages now %d", len(messages))
                else:
                    logger.debug(
                        "context_prune(shed-oldest-pair): SKIP — no complete superseded assistant/tool pair",
                    )

            # Call model — use larger budget once tools have been used so that
            # the final synthesis turn (no tool_call in response) isn't capped at
            # the tool-call budget (512).  First call keeps 512 since the model
            # almost always emits a tool call there (short JSON, EOS quick).
            call_max_tokens = (
                _DOGFOOD_FIRST_CALL_MAX_TOKENS
                if _dogfood_payload_budget_enabled() and _dogfood_initial_llm_call_pending
                else (AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS)
            )
            _dogfood_initial_llm_call_pending = False
            try:
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=call_max_tokens,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            except _CASSETTE_HARD_EXCEPTIONS:
                # A strict-replay miss / replay misconfiguration / payload digest
                # mismatch is a deliberate fail-closed signal from the record/replay
                # harness, not a transient transport failure — propagate untouched.
                # Retrying here would mask it behind a mis-parameterized (task_type
                # dropped) second call, silently replaying the wrong thing instead of
                # surfacing the regression.
                _cancel_watchdog()
                raise
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
                    task_type=task.task_type,
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
                    if _LOCAL_GBNF_REPAIR_ENABLED:
                        repair_messages = messages + [
                            {"role": "assistant", "content": _bounded_retry_response(response)},
                            {
                                "role": "user",
                                "content": (
                                    "The previous output was malformed tool-call JSON. "
                                    "Return exactly one valid JSON tool call matching the available tool schema. "
                                    "No prose."
                                ),
                            },
                        ]
                        try:
                            repaired_response, repair_tokens = await self._call_llama(
                                repair_messages,
                                role=role,
                                max_tokens=AGENT_TOOL_CALL_MAX_TOKENS,
                                task_type=task.task_type,
                                task_id=task.id,
                                call_number=tool_call_count + 1,
                                force_tool_grammar=True,
                            )
                            total_tokens += repair_tokens
                            repaired_tool_call = self.tool_registry.parse_tool_call_from_llama(repaired_response)
                            if repaired_tool_call:
                                logger.info(
                                    "gbnf-repair: recovered malformed tool call at call %d",
                                    tool_call_count + 1,
                                )
                                response = repaired_response
                                tool_call = repaired_tool_call
                        except Exception as _repair_err:
                            logger.warning(
                                "gbnf-repair: constrained retry failed at call %d: %s",
                                tool_call_count + 1,
                                str(_repair_err)[:120],
                            )
                    if not tool_call:
                        logger.warning(
                            "final-response-is-tool-call: response looks like truncated tool call at "
                            "call %d — requesting prose synthesis (max_tokens=256)",
                            tool_call_count,
                        )
                        # P1: this is an unambiguous local failure — the model emitted a tool-call JSON
                        # the parser rejected (truncated/malformed). Capture it as a labeled training
                        # sample so the loop can learn from it. Best-effort; never breaks the turn.
                        if training_capture is not None:
                            last_user = next((m.get("content", "") for m in reversed(messages)
                                              if m.get("role") == "user"), "")
                            training_capture.capture_failure(
                                prompt=last_user,
                                bad_output=response,
                                failure_class="invalid_tool_json",
                                tools_available=[t.name for t in self.tool_registry.tools.values()
                                                 if getattr(t, "enabled", True)],
                                source="agent_executor.parse_failed",
                                model_provenance={"lane": "local", "call_number": tool_call_count},
                            )
                        messages.append({
                            "role": "assistant",
                            "content": _bounded_retry_response(response),
                        })
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
                if not tool_call:
                    # No-action guard: an implementer/edit task with zero successful
                    # edits so far that returns non-empty prose with no tool call is a
                    # narrated PLAN ("Thought: I would change X..."), not completion —
                    # accepting it silently ends the task having changed nothing. Refuse
                    # it ONCE and force an edit_file call instead. A genuine refusal
                    # ("cannot safely...", "under-specified...") still completes normally,
                    # and a second prose-only response completes too (no infinite loop).
                    # Fail-safe: any error here falls through to the existing completion
                    # path below rather than crashing the turn.
                    if (
                        _NOACTION_INTERVENTION_ENABLED
                        and not _is_analysis_only_task
                        and _edits_made == 0
                        and not _no_action_intervention_sent
                        and response.strip()
                    ):
                        try:
                            if not _looks_like_refusal(response):
                                _no_action_intervention_sent = True
                                intervention_msg = (
                                    "You described the change but did NOT make it — no "
                                    "file has been edited yet. Do NOT answer in prose. "
                                    "Call edit_file NOW: use the exact code from the "
                                    "'## Relevant prior knowledge' block above as "
                                    "old_string and your changed version as new_string. "
                                    "The task is only complete once edit_file has "
                                    "changed the file."
                                )
                                messages.append({
                                    "role": "assistant",
                                    "content": _bounded_retry_response(response),
                                })
                                messages.append({
                                    "role": "user",
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "no-action intervention: prose-only response with 0 "
                                    "edits made at call %d — injecting one-shot "
                                    "edit-forcing nudge instead of completing",
                                    tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "noaction_intervention",
                                    {"tool_call_count": tool_call_count},
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _noaction_err:
                            logger.warning(
                                "no-action-intervention construction failed (%s) — "
                                "falling through to normal completion", _noaction_err,
                            )
                            # Fall through to the plain completion below (fail-safe:
                            # never let a broken intervention crash or hang the loop).
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

            # Post-edit verify-and-coach gate: snapshot the file's content
            # BEFORE dispatch for write_region/write_file (edit_file carries
            # its own before/after in old_string/new_string, no read needed).
            # Must happen here, before execute_tool_call runs, or the "before"
            # side is already gone by the time the result comes back. Fail-
            # safe: any read error just leaves no snapshot — the verify gate
            # treats that as "unknown before-content" and skips checks that
            # need it, it never blocks the edit itself.
            if (
                _EDIT_VERIFY_ENABLED
                and tool_call.tool_name in ("write_region", "write_file")
            ):
                try:
                    _ev_snap_path = str(
                        tool_call.arguments.get("file_path")
                        or tool_call.arguments.get("path") or ""
                    )
                    if _ev_snap_path:
                        _ev_snap_p = (
                            Path(_ev_snap_path) if Path(_ev_snap_path).is_absolute()
                            else Path.cwd() / _ev_snap_path
                        )
                        if _ev_snap_p.exists() and _ev_snap_p.is_file():
                            _verify_pre_edit_content[_ev_snap_path] = _ev_snap_p.read_text(
                                encoding="utf-8",
                            )
                except Exception:
                    pass  # fail-safe: verify gate degrades to "no pre-image" mode

            _exact_read_request = (
                _normalized_exact_read_range(tool_call.arguments)
                if tool_call.tool_name == "read_file" else None
            )

            # Slice 0.2 — structural no-commit: block execution at the point of the call
            # itself, not just the advertised schema. The SI-slice system prompt still
            # names git_add/git_commit by name (STEP 6), so a schema-only filter would
            # not stop a call the model emits anyway — this is what makes "local CANNOT
            # commit" structural rather than prompt-hoped. AQ_LOCAL_ALLOW_COMMIT=1 is the
            # explicit escape hatch; the handlers in builtin_tools/git_tools.py are
            # untouched, only this call site refuses to reach them.
            if _exact_read_request and _range_is_covered(
                _successful_exact_read_coverage, _exact_read_request,
            ):
                _covered_path, _covered_start, _covered_end = _exact_read_request
                if not _redundant_range_intervention_sent:
                    # Do not call the filesystem-backed tool.  This synthetic successful
                    # result is intentionally delivered through the ordinary role:tool
                    # path below, so the model receives the correction on its next turn.
                    _redundant_range_intervention_sent = True
                    tool_call.status = "completed"
                    tool_call.result = {
                        "success": True,
                        "content": (
                            f"[REREAD GUARD] {_covered_path!r} lines "
                            f"{_covered_start}-{_covered_end} are already fully covered by "
                            "a successful exact read in this task. Do not re-read this span. "
                            "Use the exact known text to call edit_file, request a genuinely "
                            "non-overlapping line range, or conclude the task."
                        ),
                        "metadata": {
                            "redundant_range_intercepted": True,
                            "start_line": _covered_start,
                            "end_line": _covered_end,
                        },
                    }
                    result = tool_call
                    logger.warning(
                        "redundant ranged read intercepted: path=%r range=%d-%d call=%d",
                        _covered_path, _covered_start, _covered_end, tool_call_count + 1,
                    )
                else:
                    tool_call.status = "failed"
                    tool_call.error = (
                        f"Redundant ranged-read guard: {_covered_path!r} lines "
                        f"{_covered_start}-{_covered_end} were already supplied. "
                        "A prior corrective result required an edit, a non-overlapping range, "
                        "or completion; repeated defiance is aborted fail-closed."
                    )
                    tool_call.result = {"success": False, "error": tool_call.error, "blocked": True}
                    _redundant_range_abort_message = tool_call.error
                    result = tool_call
            elif tool_call.tool_name in _AEXEC_COMMIT_TOOLS and not _LOCAL_ALLOW_COMMIT:
                tool_call.status = "blocked"
                tool_call.error = (
                    f"{tool_call.tool_name} is disabled for local agents (structural "
                    "no-commit gate). Local NEVER commits — finish validation and STOP; "
                    "the orchestrator commits after remote review. Override: "
                    "AQ_LOCAL_ALLOW_COMMIT=1 (not recommended)."
                )
                tool_call.result = {"success": False, "error": tool_call.error, "blocked": True}
                result = tool_call
            else:
                result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Slice 0.2 — read_file gate (the load-bearing fix): an oversized whole-file
            # read on top of front-loaded context blows the prompt-char budget (DESIGN.md
            # AFTER-run-1: 25920 > 24000 LLAMA_MAX_PROMPT_CHARS). Skip when an explicit
            # line range was requested — that's already a bounded, caller-chosen span.
            if (
                _READ_FILE_GATE_ENABLED
                and result.tool_name == "read_file"
                and result.status == "completed"
                and isinstance(result.result, dict)
                and result.result.get("success")
                and isinstance(result.result.get("content"), str)
                and tool_call.arguments.get("start_line") is None
                and tool_call.arguments.get("end_line") is None
            ):
                _rf_path = str(
                    tool_call.arguments.get("file_path")
                    or (result.result.get("metadata") or {}).get("path")
                    or ""
                )
                _gated_content, _rf_gated = _gate_large_file_content(
                    result.result["content"], _rf_path, task.objective, task.id,
                )
                if _rf_gated:
                    result.result["content"] = _gated_content
                    _rf_meta = result.result.setdefault("metadata", {})
                    _rf_meta["read_file_gate"] = True

            # Record only actual successful explicit ranges.  Synthetic guard results
            # do not extend coverage, and whole/partial reads remain out of scope.
            if (
                _exact_read_request
                and result.status == "completed"
                and isinstance(result.result, dict)
                and result.result.get("success")
                and not (result.result.get("metadata") or {}).get("redundant_range_intercepted")
            ):
                _coverage_path, _coverage_start, _coverage_end = _exact_read_request
                _returned_lines = (result.result.get("metadata") or {}).get("lines")
                try:
                    _returned_lines = int(_returned_lines)
                except (TypeError, ValueError):
                    _returned_lines = 0
                # The file handler can be asked for an end past EOF.  Coverage must
                # describe only the lines it actually returned, never the requested
                # endpoint.  Missing/empty metadata is conservatively uncacheable.
                if _returned_lines > 0:
                    _successful_exact_read_coverage.setdefault(_coverage_path, []).append(
                        (_coverage_start, min(_coverage_end, _coverage_start + _returned_lines - 1))
                    )

            # P1.4: a valid tool call that executed cleanly is a POSITIVE sample — capture it directly
            # here (the reliable source) rather than mining hybrid-events (only ~0.03% of which are
            # inference completions — the root cause of the ingest's samples_added:0). Best-effort;
            # ingest dedupes by content hash. Guarded so it never affects the turn.
            # Synthetic guard results teach the model nothing about a successful tool
            # execution.  Never label an intercepted redundant read as a positive
            # sample: it was deliberately not dispatched to the filesystem tool.
            _is_synthetic_redundant_read = bool(
                isinstance(result.result, dict)
                and (result.result.get("metadata") or {}).get("redundant_range_intercepted")
            )
            if (
                training_capture is not None
                and not getattr(result, "error", None)
                and not _is_synthetic_redundant_read
            ):
                _last_user = next((m.get("content", "") for m in reversed(messages)
                                   if m.get("role") == "user"), "")
                if _last_user and response:
                    training_capture.capture_success(
                        prompt=_last_user,
                        good_output=response,
                        source="agent_executor.tool_success",
                        model_provenance={"lane": "local", "tool": getattr(result, "tool_name", "")},
                    )

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
            try:
                compacted_result, _context_risk = compact_context_if_needed(
                    formatted_result,
                    source=result.tool_name,
                    label=f"{task.id}-{result.tool_name}",
                    kind="agent-tool-result",
                    min_chars=int(os.getenv("SWB_CONTEXT_OUTPUT_GC_MIN_CHARS", "2400")),
                    summary_chars=int(os.getenv("SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS", "900")),
                )
                if _context_risk.get("context_risk"):
                    await self._emit_agent_event(
                        task.id, "context_compaction",
                        {
                            "tool_name": result.tool_name,
                            "artifact_path": _context_risk.get("artifact_path"),
                            "raw_chars": _context_risk.get("raw_chars"),
                            "risk_reasons": _context_risk.get("risk_reasons", []),
                            "context_route": _context_risk.get("context_route"),
                        },
                        _watchdog_last_activity,
                    )
                    formatted_result = compacted_result
            except Exception as _compact_err:
                logger.debug("context compaction error (non-fatal): %s", _compact_err)

            # Persist the final post-format prompt value (after all local
            # sanitization/compaction), so offline replay reproduces the next-turn
            # request identity without re-executing the original tool side effect.
            if llm_cassette is not None:
                llm_cassette.record_formatted_tool_result(result.tool_name, formatted_result)

            if _redundant_range_abort_message:
                logger.warning("redundant ranged-read guard: aborting at call %d", tool_call_count)
                _cancel_watchdog()
                return _redundant_range_abort_message, total_tokens

            # Stagnation detection: same (tool_name, result_prefix) repeated beyond
            # threshold → model is looping without state change. Abort early via a
            # progress guard — this is the SMART early exit; context pruning +
            # working-memory checkpoints keep prior findings reachable across long
            # implementation loops so it's safe to let this run well below the hard
            # tool-call ceiling / wall-clock budget (checked at the top of the loop,
            # see "Hard termination bounds" in the setup block above) which is the
            # dumb-but-guaranteed outer backstop.
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
                read_path = str(result.arguments.get("file_path") or result.arguments.get("path") or "")
                if read_path:
                    _read_path_counts[read_path] = _read_path_counts.get(read_path, 0) + 1
                    if _read_path_counts[read_path] >= _REPEATED_READ_PATH_LIMIT:
                        # First breach: inject a one-shot edit-forcing intervention instead
                        # of aborting. The relevant code is already front-loaded verbatim
                        # under "## Relevant prior knowledge" — the plain abort discarded
                        # tasks local could complete once nudged off the read->edit stall.
                        # Delivered as the read_file tool result (role:"tool") so the model
                        # actually sees it as the outcome of ITS OWN last tool call next turn.
                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
                            try:
                                _reread_intervention_sent = True
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                intervention_msg = (
                                    f"You have read {read_path!r} "
                                    f"{_read_path_counts[read_path]} times and it keeps returning "
                                    "the same content — reading it again will not help. STOP "
                                    "reading. The relevant code for this task is ALREADY in your "
                                    "context above under '## Relevant prior knowledge' as exact "
                                    "fenced code blocks (byte-identical to the file). Call "
                                    "edit_file NOW: use the exact text from one of those code "
                                    "blocks as old_string (it will match), and provide your "
                                    "changed version as new_string. Do not call read_file on "
                                    "this file again."
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "repeated-read intervention: path=%r reads=%d call=%d — "
                                    "injecting one-shot edit-forcing nudge instead of aborting",
                                    read_path, _read_path_counts[read_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "reread_intervention",
                                    {
                                        "file_path": read_path,
                                        "reads": _read_path_counts[read_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                            except Exception as _interv_err:
                                logger.warning(
                                    "reread-intervention construction failed (%s) — "
                                    "falling back to plain abort", _interv_err,
                                )
                                # Fall through to the plain abort below (fail-safe: never
                                # let a broken intervention crash or hang the loop).
                        stagnation_msg = (
                            f"Repeated-read stagnation: {read_path!r} was read "
                            f"{_read_path_counts[read_path]} times without progress. "
                            f"Aborting at tool call {tool_call_count}."
                        )
                        logger.warning(
                            "repeated-read stagnation: path=%r reads=%d call=%d",
                            read_path, _read_path_counts[read_path], tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens
            elif result.tool_name in ("edit_file", "write_file", "write_region"):
                _reads_without_edit = 0
                _read_path_counts.clear()
                if not _is_tool_failure:
                    # Post-edit verify-and-coach gate (STEWARDSHIP, CLAUDE.md
                    # Rule 21 — help local reach its best self, not a punitive
                    # block). The edit LANDED (write succeeded); before
                    # counting it as real progress, run the cheap static
                    # checks in _verify_edit_quality. A failing edit gets
                    # SPECIFIC coaching as the next tool result and a `continue`
                    # so local retries immediately, bounded to
                    # _EDIT_VERIFY_MAX_PER_FILE fires per file — a
                    # persistently-trivial edit still falls through and counts
                    # (never blocks forever; downstream runner/reviewer catches
                    # it). Fail-safe: any error here just skips coaching and
                    # counts the edit normally, exactly like the plain
                    # accept-on-success path this gate sits in front of.
                    _ev_path = str(
                        (result.arguments or {}).get("file_path")
                        or (result.arguments or {}).get("path") or ""
                    )
                    _ev_verdict: Optional[_EditVerdict] = None
                    if _EDIT_VERIFY_ENABLED:
                        try:
                            _ev_verdict = _verify_edit_quality(
                                tool_name=result.tool_name,
                                arguments=result.arguments or {},
                                file_path=_ev_path,
                                pre_content=_verify_pre_edit_content.get(_ev_path),
                                task_objective=task.objective,
                            )
                        except Exception as _ev_exc:
                            logger.warning(
                                "edit-verify check failed (%s) — falling through "
                                "to plain accept (fail-safe)", _ev_exc,
                            )
                            _ev_verdict = None

                    _ev_fires = _edit_verify_counts.get(_ev_path, 0)
                    _ev_coached = False
                    if (
                        _EDIT_VERIFY_ENABLED
                        and _ev_verdict is not None
                        and not _ev_verdict.passed
                        and _ev_fires < _EDIT_VERIFY_MAX_PER_FILE
                    ):
                        try:
                            _edit_verify_counts[_ev_path] = _ev_fires + 1
                            _iv_brace = response.rfind('{"function"')
                            if _iv_brace == -1:
                                _iv_brace = response.rfind("{")
                            _iv_clean_call = (
                                response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                            )
                            messages.append({"role": "assistant", "content": _iv_clean_call})
                            messages.append({
                                "role": "tool",
                                "name": result.tool_name,
                                "content": _ev_verdict.coaching_message,
                            })
                            logger.warning(
                                "edit-verify coach: path=%r reason=%s attempt=%d call=%d — "
                                "injecting coaching feedback instead of counting as progress",
                                _ev_path, _ev_verdict.reason,
                                _edit_verify_counts[_ev_path], tool_call_count,
                            )
                            await self._emit_agent_event(
                                task.id, "edit_verify_coach",
                                {
                                    "file_path": _ev_path,
                                    "reason": _ev_verdict.reason,
                                    "attempt": _edit_verify_counts[_ev_path],
                                    "tool_call_count": tool_call_count,
                                },
                                _watchdog_last_activity,
                            )
                            _ev_coached = True
                        except Exception as _ev_inject_exc:
                            logger.warning(
                                "edit-verify coach injection failed (%s) — "
                                "falling through to plain accept", _ev_inject_exc,
                            )
                            # Fall through: count the edit normally below (fail-safe).

                    if _ev_coached:
                        continue
                    _edits_made += 1
                    _accepted_path = _repo_relative_path(_ev_path)
                    # Retain an explicit non-matching sentinel rather than
                    # dropping an unnormalizable path: it must disqualify the
                    # candidate, not disappear from the all-writes evidence.
                    _accepted_write_paths.append(_accepted_path or "<outside-repository>")

                    # Verified-edit completion: after the successful write has
                    # passed all static checks AND an explicitly configured
                    # behavioral command actually ran and returned zero, one
                    # bounded prose-only synthesis replaces another full tool
                    # turn.  No parser/dispatcher touches the synthesis output.
                    # This is deliberately unavailable to unmarked, static-only,
                    # malformed, multi-file, or out-of-scope tasks.
                    if (
                        _declared_completion_scope is not None
                        and _EDIT_VERIFY_ENABLED
                        and _ev_verdict is not None
                        and _ev_verdict.passed
                        and _ev_verdict.behavioral_check_ran
                        and _ev_verdict.behavioral_check_passed
                        and _accepted_path == _declared_completion_scope
                        and _accepted_write_paths
                        and all(path == _declared_completion_scope for path in _accepted_write_paths)
                    ):
                        completion_evidence = {
                            "kind": "verified_edit_completion",
                            "scope": _declared_completion_scope,
                            "accepted_write_count": len(_accepted_write_paths),
                            "behavioral_check": "ran_exit_0",
                            "synthesis": "one_no_tools_call_max_96",
                        }
                        task.completion_evidence = completion_evidence
                        await self._emit_agent_event(
                            task.id,
                            "verified_edit_completion_candidate",
                            completion_evidence,
                            _watchdog_last_activity,
                        )
                        synthesis_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "Return one concise plain-text completion sentence. "
                                    "No JSON. No tools. No commands."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    "The declared single-file edit was statically and behaviorally "
                                    f"verified for {_declared_completion_scope}. State completion."
                                ),
                            },
                        ]
                        try:
                            synthesis, synthesis_tokens = await self._call_llama(
                                synthesis_messages,
                                role=role,
                                max_tokens=_VERIFIED_EDIT_SYNTHESIS_MAX_TOKENS,
                                task_id=task.id,
                                call_number=tool_call_count + 1,
                                allow_tool_grammar=False,
                            )
                            total_tokens += synthesis_tokens
                        except Exception as _synthesis_error:  # bounded deterministic fallback
                            logger.warning(
                                "verified-edit completion synthesis failed (%s); using receipt", _synthesis_error,
                            )
                            synthesis = ""
                        final_synthesis = (synthesis or "").strip()
                        if not final_synthesis or _tool_shaped_synthesis(final_synthesis):
                            final_synthesis = (
                                f"COMPLETED: verified edit completed for {_declared_completion_scope}."
                            )
                        task.completion_evidence = {
                            **completion_evidence,
                            "synthesis_fallback": final_synthesis.startswith("COMPLETED: verified edit"),
                        }
                        await self._emit_agent_event(
                            task.id,
                            "verified_edit_completion",
                            task.completion_evidence,
                            _watchdog_last_activity,
                        )
                        _cancel_watchdog()
                        return final_synthesis, total_tokens
                elif result.tool_name == "edit_file":
                    # Edit-failure feedback: old_string byte-mismatch is now the
                    # dominant local-agent failure mode (see _EDIT_FEEDBACK_ENABLED
                    # above). On the FIRST such mismatch failure for this file
                    # (bounded to _EDIT_FEEDBACK_MAX_PER_FILE), inject the file's
                    # EXACT current text for the attempted region as the tool
                    # result instead of the bare failure, then let the loop
                    # continue — never crash or hang on a broken feedback build.
                    _ef_err = str((result.result or {}).get("error", "")) if result.result else ""
                    _ef_path = str(
                        (result.arguments or {}).get("file_path")
                        or (result.arguments or {}).get("path")
                        or ""
                    )
                    _ef_fires = _edit_feedback_counts.get(_ef_path, 0)
                    if (
                        _EDIT_FEEDBACK_ENABLED
                        and _ef_path
                        and _looks_like_edit_mismatch(_ef_err)
                        and _ef_fires < _EDIT_FEEDBACK_MAX_PER_FILE
                    ):
                        try:
                            _ef_region = _build_edit_mismatch_feedback(
                                _ef_path,
                                str((result.arguments or {}).get("old_string") or ""),
                                char_budget=_EDIT_FEEDBACK_CHAR_BUDGET,
                            )
                            if _ef_region:
                                _edit_feedback_counts[_ef_path] = _ef_fires + 1
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                feedback_msg = (
                                    "edit_file FAILED: your old_string did not match the "
                                    "file. The file's EXACT current text for that region is "
                                    "below — copy an exact substring of THIS as your "
                                    "old_string (character-for-character, including "
                                    "indentation) and retry edit_file.\n\n" + _ef_region
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": feedback_msg,
                                })
                                logger.warning(
                                    "edit-mismatch feedback: path=%r attempt=%d call=%d — "
                                    "injecting exact-region feedback instead of plain failure",
                                    _ef_path, _edit_feedback_counts[_ef_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "edit_feedback_intervention",
                                    {
                                        "file_path": _ef_path,
                                        "attempt": _edit_feedback_counts[_ef_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _ef_err_exc:
                            logger.warning(
                                "edit-feedback construction failed (%s) — "
                                "falling through to plain failure", _ef_err_exc,
                            )
                            # Fall through to the normal failure-result append below.
            elif _is_analysis_only_task and result.tool_name == "store_memory":
                _reads_without_edit = 0
                _read_path_counts.clear()

            # Validation stall: detect repeated validate_before_commit/run_command
            # without any intervening commit. Model validated the code is ready but
            # won't pull the trigger. Nudge it to git_add → git_commit immediately.
            if result.tool_name in ("validate_before_commit", "run_command") and result.status == "completed":
                _validation_passes_without_commit += 1
            elif result.tool_name in ("write_file", "edit_file", "write_region", "git_add", "git_commit"):
                _validation_passes_without_commit = 0

            # Observation stagnation: track harness query calls vs action calls.
            if result.tool_name in _OBSERVATION_QUERY_TOOLS:
                _observations_without_action += 1
            elif result.tool_name in _OBSERVATION_ACTION_TOOLS:
                _observations_without_action = 0

            if _reads_without_edit >= _READS_HARD_LIMIT:
                if _is_analysis_only_task:
                    stagnation_msg = (
                        f"Analysis checkpoint stagnation: {_reads_without_edit} consecutive "
                        f"reads without store_memory or write_file checkpoint — model stuck "
                        f"in analysis phase. Aborting at tool call {tool_call_count}."
                    )
                else:
                    stagnation_msg = (
                        f"Exploration stagnation: {_reads_without_edit} consecutive reads without "
                        f"any edit_file or write_file — model stuck in exploration phase. "
                        f"Aborting at tool call {tool_call_count}."
                    )
                logger.warning(
                    "exploration/checkpoint stagnation: %d reads task_type=%r call=%d",
                    _reads_without_edit, task.task_type, tool_call_count,
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
            # Analysis-only tasks should finalize into a report at this point; asking
            # them to "act" can send the model back into planning/tool loops.
            if (
                _is_analysis_only_task
                and _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION
                and not _observation_nudge_sent
            ):
                _observation_nudge_sent = True
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "FINALIZE NOW. Do not call another tool. Do not continue planning. "
                        "Use the tool results already in context to answer the original task. "
                        "Start with 'COMPLETED:' and include concrete findings, ranked items "
                        "or decisions when requested, security/validation notes, and next safe "
                        "repo-local slice recommendations."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                return synthesis.strip(), total_tokens

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
                if _is_analysis_only_task:
                    nudge_content = (
                        f"ANALYSIS TASK: You have read {_reads_without_edit} files. "
                        f"Continue gathering context as needed, but checkpoint before "
                        f"{_READS_HARD_LIMIT} reads with store_memory or write_file. "
                        "Do not keep rereading the same files."
                    )
                else:
                    # Single-edit-first nudge (converged on independently by codex, 578bc847,
                    # + this session). Measured basis: the local model read-loops on
                    # multi-site edit tasks but succeeds at ONE edit (EXP3), so reframing to
                    # "make exactly ONE edit now, others later" targets the stuck read->edit
                    # transition. EFFECTIVENESS INCONCLUSIVE: the one validation run
                    # (reference-local-agent-capability-envelope EXP5) read-looped to call 17
                    # with 0 edits but was cut off by a first-token wedge, not a clean finish
                    # — needs a clean non-wedged run to confirm. Low-risk (only fires when the
                    # agent is already stuck). The proven multi-edit path remains the external
                    # decomposer (scripts/ai/aq-sequential-edit).
                    nudge_content = (
                        f"STOP READING — you have read {_reads_without_edit} times without "
                        "editing. Do NOT read again. Make exactly ONE edit now: pick the "
                        "single most concrete change from the BEHAVIORAL CONTRACT and emit "
                        "ONE edit_file call for it (exact old_string anchor + new_string). "
                        "Ignore every other change this turn — you will make them one at a "
                        "time in the following turns. One edit_file call, now."
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

    def _tool_call_grammar(self, *, force_repair: bool = False) -> Optional[str]:
        """P2: GBNF constraining output to the tool-call envelope over the ENABLED tools. Returns None
        unless AQ_LOCAL_GBNF is set (default OFF) or a repair-only retry explicitly requests it.
        Cached on the instance keyed by the enabled-tool set (the lease can hot-swap mid-run)."""
        if tool_grammar is None:
            return None
        if force_repair:
            if not _LOCAL_GBNF_REPAIR_ENABLED:
                return None
        elif not _LOCAL_GBNF_ALWAYS_ENABLED:
            return None
        try:
            names = sorted(t.name for t in self.tool_registry.tools.values() if getattr(t, "enabled", True))
            cache_key = tuple(names)
            cached = getattr(self, "_gbnf_cache", None)
            if cached and cached[0] == cache_key:
                return cached[1]
            grammar, _hit = tool_grammar.tool_call_grammar(names)
            self._gbnf_cache = (cache_key, grammar)
            return grammar
        except Exception:  # noqa: BLE001 — grammar is an optimization; never break the call on it
            return None

    def _cassette_replay(
        self, payload: Dict[str, Any], task_type: Optional[str]
    ) -> Optional[Tuple[str, int]]:
        """Record/replay harness hook — consult the cassette before the HTTP call.

        Returns (content, tokens) on a replay hit (caller must return it immediately,
        skipping the network entirely); None means "proceed live" (default-off mode,
        record mode, replay-record miss, or on-miss=passthrough). Raises
        llm_cassette.ReplayMiss only when the operator explicitly asked for strict
        replay (AQ_LLM_CASSETTE_ON_MISS=error, the default in replay mode) — that is a
        deliberate test-failure signal, not swallowed here.
        """
        if llm_cassette is None:
            return None
        return llm_cassette.replay_lookup(payload, task_type)

    def _cassette_record(
        self,
        payload: Dict[str, Any],
        task_type: Optional[str],
        content: str,
        tokens: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record/replay harness hook — tee a live result into the cassette. No-op
        unless AQ_LLM_CASSETTE_MODE is record/replay-record; never raises."""
        if llm_cassette is None:
            return
        llm_cassette.maybe_record(payload, task_type, content, tokens, meta)

    async def _call_llama(
        self,
        messages: List[Dict],
        role: Optional[str] = None,
        max_tokens: int = AGENT_TOOL_CALL_MAX_TOKENS,
        task_type: Optional[str] = None,
        task_id: Optional[str] = None,
        call_number: int = 0,
        force_tool_grammar: bool = False,
        allow_tool_grammar: bool = True,
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
                temperature, frequency_penalty, thinking_budget, and enable_thinking.
                When None, hardcoded temperature=0.2, frequency_penalty=0.05 (legacy).
            allow_tool_grammar: False omits the GBNF tool-call grammar even when
                AQ_LOCAL_GBNF is enabled.  Use only for bounded prose-only turns.

        Returns:
            (response_text, tokens_used) — tokens_used is total_tokens from the usage chunk.
        """
        use_streaming = _env_flag("LLAMA_USE_STREAMING", default=True)
        chunk_timeout = _env_float("LLAMA_CHUNK_TIMEOUT", default=120.0)
        first_token_timeout = _env_float(
            "LLAMA_FIRST_TOKEN_TIMEOUT",
            default=min(chunk_timeout, 600.0),
        )

        # Agent tool calls: 512 tokens (50-100 for JSON + 400 for summary).
        # At 1-2 tok/s on Renoir APU, 512 tokens = 256-512s max generation.
        # 4096 would risk 68-minute slot locks when clients disconnect.
        # When task_type is set the profile drives temperature; otherwise use 0.2.
        _temperature: Optional[float] = None if task_type else 0.2

        # Prefill-wedge guard (root-cause fix for orphaned-slot cascades): a single oversized prompt
        # — e.g. an un-compacted large-file read that slipped past the >8-message context pruning —
        # causes a prefill longer than first_token_timeout on the single-slot APU. The client gives up
        # but llama.cpp keeps prefilling, ORPHANING the only slot and wedging ALL subsequent local
        # dispatches (a wedged slot then starves unrelated tasks — this is how a victim task fails with
        # 0 tool calls). Fail FAST here with a clean, capturable error instead of sending a request that
        # will wedge the slot. Ceiling ~6000 tok leaves headroom under the 8192 ctx for generation.
        _prompt_chars = sum(len(m.get("content") or "") for m in messages)
        _max_prompt_chars = int(os.getenv("LLAMA_MAX_PROMPT_CHARS", "24000"))
        if _prompt_chars > _max_prompt_chars:
            raise RuntimeError(
                f"prompt too large for single-slot prefill: {_prompt_chars} chars > {_max_prompt_chars} "
                "(LLAMA_MAX_PROMPT_CHARS) — refusing to send; an oversized prefill would orphan/wedge the "
                "llama.cpp slot. Trim context: ranged reads, tool-result compaction, or fewer files."
            )

        if not use_streaming:
            # Legacy non-streaming path — 300s wall-clock limit.
            _payload_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role}
            if _temperature is not None:
                _payload_kwargs["temperature"] = _temperature
            if task_type:
                _payload_kwargs["task_type"] = task_type
            _gbnf = (
                self._tool_call_grammar(force_repair=force_tool_grammar)
                if allow_tool_grammar else None
            )
            if _gbnf:
                _payload_kwargs["grammar"] = _gbnf
            payload = build_llama_payload(messages, **_payload_kwargs)
            _enforce_dogfood_payload_budget(
                payload, task_type=task_type, call_number=call_number
            )

            # Record/replay harness — replay hit skips the HTTP call entirely (no-op
            # when AQ_LLM_CASSETTE_MODE=off, the default).
            _cassette_hit = self._cassette_replay(payload, task_type)
            if _cassette_hit is not None:
                return _cassette_hit

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                    timeout=300.0,
                    headers={"x-ai-profile": os.environ.get("AGENT_SWITCHBOARD_PROFILE", "local-agent")},
                )
                if response.status_code != 200:
                    raise Exception(f"llama.cpp error: {response.status_code} {response.text}")
                data = response.json()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                content = data["choices"][0]["message"]["content"]
                self._cassette_record(payload, task_type, content, tokens, {"path": "legacy"})
                return content, tokens

        # Streaming path: collect SSE delta chunks.
        # Pass stream=True so build_llama_payload includes stream_options.include_usage=True,
        # which causes llama.cpp to emit a final usage-only chunk for token tracking.
        # httpx.Timeout(read=chunk_timeout) is per-read-operation (per chunk), not total.
        _stream_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role, "stream": True}
        if _temperature is not None:
            _stream_kwargs["temperature"] = _temperature
        if task_type:
            _stream_kwargs["task_type"] = task_type
        _gbnf = (
            self._tool_call_grammar(force_repair=force_tool_grammar)
            if allow_tool_grammar else None
        )
        if _gbnf:
            _stream_kwargs["grammar"] = _gbnf
        payload = build_llama_payload(messages, **_stream_kwargs)
        budget_receipt = _enforce_dogfood_payload_budget(
            payload, task_type=task_type, call_number=call_number
        )

        # Record/replay harness — replay hit skips SSE streaming entirely (no-op when
        # AQ_LLM_CASSETTE_MODE=off, the default).
        _cassette_hit = self._cassette_replay(payload, task_type)
        if _cassette_hit is not None:
            return _cassette_hit

        read_timeout = min(chunk_timeout, first_token_timeout)
        timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=10.0, pool=5.0)

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
                progress = {
                    "task_id": task_id,
                    "status": status,
                    "tool_call_count": call_number,
                    "llm_stream_chunks": len(collected),
                    "llm_stream_chars": sum(len(part) for part in collected),
                    "max_tokens": max_tokens,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
                }
                if budget_receipt is not None:
                    progress["payload_budget"] = budget_receipt
                Path(progress_file).write_text(json.dumps(progress, indent=2))
                last_progress_write = now
            except Exception:
                pass

        # Live stream tail — the raw LLM output/reasoning as it streams, for near-real-time
        # monitoring in aq-tui-dashboard --matrix (reads .agents/delegation/streams/<id>.txt).
        # Throttled ~0.7s; independent of AGENT_PROGRESS_FILE. This is what lets the operator
        # watch a local agent's thoughts/output live, like its native CLI.
        _stream_dir = Path(__file__).resolve().parents[2] / ".agents" / "delegation" / "streams"
        _stream_file = _stream_dir / f"{task_id}.txt"
        _last_stream_write = [0.0]

        def _write_stream_tail(final: bool = False) -> None:
            now = time.time()
            if not final and now - _last_stream_write[0] < 0.7:
                return
            _last_stream_write[0] = now
            try:
                _stream_dir.mkdir(parents=True, exist_ok=True)
                _stream_file.write_text("".join(collected)[-4000:])
            except OSError:
                pass

        try:
            _write_stream_progress("llm_waiting", force=True)
            _stream_start = time.monotonic()
            # x-ai-profile: local-agent -> if the endpoint is the switchboard (:8085),
            # route to the passthrough local-agent lane (no card injection / payload
            # transform) so we gain the switchboard's concurrency + observability without
            # changing agent behavior. Harmless (ignored) when hitting llama.cpp directly.
            _route_headers = {"x-ai-profile": os.environ.get("AGENT_SWITCHBOARD_PROFILE", "local-agent")}
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                    headers=_route_headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(f"llama.cpp error: {response.status_code} {body.decode()[:200]}")

                    async for raw_line in response.aiter_lines():
                        # Wall-clock first-token watchdog. llama.cpp emits keep-alive/empty
                        # SSE lines during a long single-slot prefill, which reset httpx's
                        # per-read timer — so the per-chunk read timeout never bounds
                        # first-token and a wedged prefill hangs for the full (hours-long)
                        # chunk_timeout. Enforce an explicit wall-clock bound until the first
                        # CONTENT token; fires even while keep-alives arrive. Measured: this
                        # is what let runs wedge 10-23 min with 0 tokens.
                        if not collected and (time.monotonic() - _stream_start) > first_token_timeout:
                            raise RuntimeError(
                                f"LLM first-token timeout: no content within "
                                f"{first_token_timeout:.0f}s of request start "
                                "(single-slot prefill wedge or context too large)."
                            )
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
                            _write_stream_tail()
        except httpx.ReadTimeout:
            raise RuntimeError(
                f"LLM no-progress timeout: server silent for >{read_timeout:.0f}s "
                f"(first_token_timeout={first_token_timeout:.0f}, chunk_timeout={chunk_timeout:.0f}; "
                "context may be too large or the inference slot may be wedged)"
            )
        except httpx.ConnectError as _ce:
            raise RuntimeError(f"LLM connection refused at {self.llama_endpoint}: {_ce}") from _ce
        except httpx.NetworkError as _ne:
            raise RuntimeError(f"LLM network error: {_ne}") from _ne

        _write_stream_tail(final=True)
        content = "".join(collected)
        self._cassette_record(payload, task_type, content, tokens_used, {"path": "streaming"})
        return content, tokens_used

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
        skill_projection: str = "",
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
        _commit_policy_line = (
            "- validate_before_commit MUST pass before git_add. Call it once, then act on result.\n"
            if _LOCAL_ALLOW_COMMIT else
            "- LOCAL AGENTS DO NOT COMMIT: git_add/git_commit are disabled by default (structural\n"
            "  gate, AQ_LOCAL_ALLOW_COMMIT=0). After validate_before_commit passes, STOP — do not\n"
            "  call git_add or git_commit. The orchestrator commits after remote review.\n"
        )
        _behavioral_contract = (
            "\n\nBEHAVIORAL CONTRACT:\n"
            "- Read before writing. One change at a time. Stay in the assigned slice.\n"
            + _commit_policy_line +
            "- ALWAYS use RELATIVE paths (e.g. .agent/memory/issues-backlog.md not /home/user/...).\n"
            "- To change code, prefer write_region(file_path, start_line, end_line, new_text) using the line\n"
            "  numbers shown in the '## Relevant prior knowledge' citations (e.g. '[file:271-290]') — it does\n"
            "  NOT require matching existing text. Use edit_file only for tiny single-line tweaks.\n"
            "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
            "  Only use write_file if you must create a new file from scratch.\n"
            "- READ LIMIT: At most 4 read_file calls per slice. After 4 reads, STOP reading — you have enough\n"
            "  context. Call edit_file immediately. If edit_file fails with 'old_string not found', THEN read more.\n"
            "- PREFER RANGED READS: call read_file(path, start_line=, end_line=) for a targeted span instead of\n"
            "  a whole-file read — large files are auto-summarized (outline + top chunks) past ~1500 tokens anyway.\n"
            "- If context is already provided under '## Relevant prior knowledge' (front-loaded), do NOT re-fetch\n"
            "  it via read_file/query_aidb/get_hint — only fetch more if that block is insufficient.\n"
            "- SURGICAL FINALITY: validation gate passes → finalize IMMEDIATELY (commit if allowed,\n"
            "  else STOP). No cleanup. No refactor. Adjacent improvements are separate tasks.\n"
        )

        # Self-improvement slice instructions (~722 tokens). Only injected when the task
        # explicitly involves issue-fixing / improvement cycles — saves context and avoids
        # confusing the model when it's doing factory, research, or delegation tasks.
        # Keep this classifier semantic.  Generic words such as "slice" appear in
        # ordinary bounded coding tasks and used to inject the full backlog workflow,
        # adding thousands of prompt characters to unrelated dogfood turns.
        _SI_KEYWORDS = frozenset({
            "self-improvement", "issues-backlog", "open issue",
            "improvement cycle", "fix issue",
        })
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
            + (
                "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
                "        git_commit('<type>(<scope>): <description>')\n"
                "        git_commit adds Co-Authored-By automatically — do NOT add it in the message.\n"
                if _LOCAL_ALLOW_COMMIT else
                "STEP 6: Do NOT call git_add or git_commit — local agents never commit (structural\n"
                "        gate). Leave changes unstaged; the orchestrator commits after remote review.\n"
                "        Proceed directly to STEP 7.\n"
            ) +
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

        # Inject active aq-loop STATE context when a loop run is detected.
        # Reads LOOP_STATE.json lazily — zero cost when not in a loop.
        _loop_ctx = ""
        _loop_state_path = Path(__file__).resolve().parents[2] / ".agent" / "collaboration" / "LOOP_STATE.json"
        if _loop_state_path.exists():
            try:
                import json as _json
                _ls = _json.loads(_loop_state_path.read_text())
                if _ls.get("phase") in ("EXECUTE", "VERIFY"):
                    _loop_ctx = (
                        f"\n\n[LOOP STATE — iter {_ls.get('iteration')}/{_ls.get('max_iterations')} "
                        f"loop={_ls.get('loop_id','')}]\n"
                        f"Intent: {_ls.get('intent','')[:120]}\n"
                        "After store_memory succeeds, output ONLY: COMPLETED: <one sentence>. STOP."
                    )
            except Exception:
                pass

        # Only aq-agent-loop's bounded projection may reach the system prompt.
        # Treat any malformed/excessive context as absent rather than widening it.
        if not isinstance(skill_projection, str) or len(skill_projection) > 2_000:
            skill_projection = ""

        # AGENT type gets behavioral contract always; SI slice only for self-improvement tasks.
        # Non-SI tasks save ~722 tokens (self-improvement step-by-step is irrelevant noise
        # for factory, research, delegation, and monitoring tasks).
        if agent_type == AgentType.AGENT:
            _workflow_contract = _behavioral_contract + (_si_slice if _is_si_task else "")
            return base_prompt[agent_type] + _workflow_contract + _loop_ctx + _tool_call_format + tools_desc + skill_projection + extensions
        return base_prompt[agent_type] + _loop_ctx + _tool_call_format + tools_desc + skill_projection + extensions

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
